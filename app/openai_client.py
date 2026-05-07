import os
import json
import urllib.error
import urllib.request
from datetime import datetime

from app.db import CRITERIA

DOCUMENT_TYPES = [
    "Invitation",
    "Attendance",
    "Thank You Note",
    "Acceptance or Selection",
    "Certificate or Completion",
    "Confirmation Email",
    "Agenda or Program",
    "Photo or Screenshot",
    "Receipt or Payment Proof",
    "Publication or Media",
    "Recommendation or Support",
    "Appointment or Contract",
    "Impact or Results",
    "Other",
]

SUPPORT_CATEGORIES = [
    "auth",
    "data_sync",
    "storage",
    "ui",
    "assistant",
    "access",
    "performance",
    "other",
]


class OpenAIService:
    def __init__(self, config: dict):
        self.config = config

    def api_key(self) -> str:
        env_name = self.config.get("api_key_env", "OPENAI_API_KEY")
        return os.environ.get(env_name) or self.config.get("api_key", "")

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled")) and bool(self.api_key())

    def summarize_upload(self, title: str, criterion_code: str) -> tuple[str, int]:
        if not self.enabled:
            return (
                f"AI is unavailable right now. Uploaded evidence is queued for builder review under {criterion_code}.",
                45,
            )
        api_key = self.api_key()
        prompt = (
            "You are helping an EB1A member portal classify and summarize uploaded evidence. "
            "Return concise JSON with keys summary and quality_score. "
            f"Evidence title: {title}. Criterion code: {criterion_code}."
        )
        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "evidence_summary",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "summary": {"type": "string"},
                            "quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
                        },
                        "required": ["summary", "quality_score"],
                    },
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "OpenAI-User": self.config.get("user", "ascend-suite-local"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.get("timeout_seconds", 60))) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return "Evidence received and ready for Ascend review.", 45
        text = raw.get("output_text")
        if not text:
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        parsed = json.loads(text or "{}")
        return parsed.get("summary", "AI summary unavailable."), int(parsed.get("quality_score", 50))

    def analyze_evidence_upload(
        self,
        member_context: str,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
    ) -> dict:
        criteria = [{"code": code, "name": name, "description": description} for code, name, description in CRITERIA]
        document_excerpt = extract_document_excerpt(file_name, content_type, file_bytes)
        if not self.enabled:
            result = fallback_analysis(member_context, file_name, document_excerpt, criteria)
            result["source"] = "disabled"
            return result

        prompt = (
            "You are helping an EB1A member portal review uploaded evidence before it is saved. "
            "Classify the evidence into exactly one allowed category. "
            "Use Other when the document does not clearly match any identified EB1A evidence criterion. "
            "Also classify the document into one practical evidence document type. "
            "Use both the member context and document content excerpt. "
            "Create a clear member-friendly description that summarizes what the document appears to prove. "
            "Return concise JSON only.\n\n"
            f"Allowed criteria JSON: {json.dumps(criteria)}\n"
            f"Allowed document types JSON: {json.dumps(DOCUMENT_TYPES)}\n"
            f"File name: {file_name}\n"
            f"Content type: {content_type}\n"
            f"Member context: {member_context}\n"
            f"Document content excerpt: {document_excerpt}"
        )
        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "evidence_analysis",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "criterion_code": {"type": "string"},
                            "criterion_name": {"type": "string"},
                            "document_type": {"type": "string"},
                            "title": {"type": "string"},
                            "ai_description": {"type": "string"},
                            "quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
                            "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                        },
                        "required": [
                            "criterion_code",
                            "criterion_name",
                            "document_type",
                            "title",
                            "ai_description",
                            "quality_score",
                            "confidence",
                        ],
                    },
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "Content-Type": "application/json",
                "OpenAI-User": self.config.get("user", "ascend-suite-local"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.get("timeout_seconds", 60))) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            result = fallback_analysis(member_context, file_name, document_excerpt, criteria)
            result["source"] = "fallback"
            return result
        text = raw.get("output_text")
        if not text:
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        result = normalize_analysis(json.loads(text or "{}"), criteria, file_name, member_context)
        result["source"] = "openai"
        return result

    def generate_petition_package(self, case_payload: dict) -> dict:
        compact_payload = compact_case_payload(case_payload)
        if not self.enabled:
            result = fallback_petition_package(compact_payload)
            result["source"] = "disabled"
            return result

        prompt = (
            "You are helping an EB1A attorney portal generate an early petition strategy draft. "
            "Use the available member profile, evidence history, folder organization, builder tasks, and planner history. "
            "Be practical and specific. Identify strengths, gaps, risks, challenges, recommended fixes, dependencies from the member, dependencies from external parties, and clear clarification questions for the member. "
            "Do not mention missing system data unless it creates a real legal or workflow risk. "
            "Return concise JSON only.\n\n"
            f"Case payload JSON: {json.dumps(compact_payload)}"
        )
        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "petition_generator",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "executive_summary": {"type": "string"},
                            "petition_positioning": {"type": "string"},
                            "readiness_assessment": {"type": "string"},
                            "proposed_sections": {"type": "array", "items": {"type": "string"}},
                            "strengths": {"type": "array", "items": {"type": "string"}},
                            "gaps": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                            "recommended_fixes": {"type": "array", "items": {"type": "string"}},
                            "member_dependencies": {"type": "array", "items": {"type": "string"}},
                            "external_dependencies": {"type": "array", "items": {"type": "string"}},
                            "clarification_questions": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "executive_summary",
                            "petition_positioning",
                            "readiness_assessment",
                            "proposed_sections",
                            "strengths",
                            "gaps",
                            "risks",
                            "recommended_fixes",
                            "member_dependencies",
                            "external_dependencies",
                            "clarification_questions",
                        ],
                    },
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "Content-Type": "application/json",
                "OpenAI-User": self.config.get("user", "ascend-suite-local"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.get("timeout_seconds", 60))) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            result = fallback_petition_package(compact_payload)
            result["source"] = "fallback"
            return result
        text = raw.get("output_text")
        if not text:
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        result = normalize_petition_package(json.loads(text or "{}"), compact_payload)
        result["source"] = "openai"
        return result

    def answer_portal_question(self, assistant_payload: dict) -> dict:
        if not self.enabled:
            result = fallback_portal_assistant(assistant_payload)
            result["source"] = "disabled"
            return result

        detail_requested = bool(assistant_payload.get("detail_requested"))
        mode_label = "detailed answer" if detail_requested else "summary answer"

        prompt = (
            "You are Ascend Navigator, an internal assistant for Ascend HSI role-based portals. "
            "You are not a general-purpose ChatGPT assistant. "
            "Stay strictly within Ascend Product Suite, EB1A case workflows, portal users, member profiles, evidence, assignments, petition preparation, messages, support, and navigation. "
            "If a question is outside that scope, refuse briefly and redirect the user to an Ascend-related question. "
            "Answer only from the provided portal data, retrieved document excerpts, and thread context. "
            "Do not invent facts, documents, folders, quotes, or legal conclusions. "
            "If something is missing, say so clearly and suggest the next best follow-up. "
            f"The user is currently asking for a {mode_label}. "
            "For summary answers, answer only the question that was asked in one or two direct sentences. "
            "Do not default to a general member summary unless the question explicitly asks for one. "
            "For detailed answers, make the detailed_answer more descriptive and include storage-backed references when relevant. "
            "When the retrieved documents contain the answer, ground the response in those document excerpts first. "
            "If the question asks for a specific document, identify the best-matching retrieved document and explain why it fits. "
            "Use only the provided reference ids when there is a relevant storage-backed citation. "
            "For summary answers, set detail_prompt to exactly 'Elaborate'. "
            "Set response_mode to 'detailed' only when the user is explicitly asking for the deeper answer.\n\n"
            f"Assistant payload JSON: {json.dumps(assistant_payload)}"
        )
        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "portal_assistant_answer",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "summary": {"type": "string"},
                            "detailed_answer": {"type": "string"},
                            "detail_prompt": {"type": "string"},
                            "suggested_follow_up": {"type": "string"},
                            "needs_more_detail": {"type": "boolean"},
                            "response_mode": {"type": "string", "enum": ["summary", "detailed"]},
                            "reference_ids": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "summary",
                            "detailed_answer",
                            "detail_prompt",
                            "suggested_follow_up",
                            "needs_more_detail",
                            "response_mode",
                            "reference_ids",
                        ],
                    },
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "Content-Type": "application/json",
                "OpenAI-User": self.config.get("user", "ascend-suite-local"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.get("timeout_seconds", 60))) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            result = fallback_portal_assistant(assistant_payload)
            result["source"] = "fallback"
            return result
        text = raw.get("output_text")
        if not text:
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        reference_lookup = {item["id"]: item for item in assistant_payload.get("references", []) if item.get("id")}
        try:
            parsed = json.loads(text or "{}")
        except json.JSONDecodeError:
            result = fallback_portal_assistant(assistant_payload)
            result["source"] = "fallback"
            return result
        return {
            "summary": str(parsed.get("summary") or "").strip() or "I reviewed the current portal data, but the answer still needs a quick manual follow-up.",
            "detailed_answer": str(parsed.get("detailed_answer") or "").strip() or "The current thread does not provide enough detail for a stronger answer.",
            "detail_prompt": str(parsed.get("detail_prompt") or "").strip() or "Elaborate",
            "suggested_follow_up": str(parsed.get("suggested_follow_up") or "").strip() or "Ask for a deeper evidence trail or the next recommended action.",
            "needs_more_detail": bool(parsed.get("needs_more_detail", not detail_requested)),
            "response_mode": "detailed" if str(parsed.get("response_mode") or "").strip() == "detailed" else ("detailed" if detail_requested else "summary"),
            "references": [reference_lookup[item_id] for item_id in parsed.get("reference_ids", []) if item_id in reference_lookup],
            "source": "openai",
        }

    def triage_support_ticket(self, ticket_payload: dict) -> dict:
        if not self.enabled:
            result = fallback_support_ticket(ticket_payload)
            result["source"] = "disabled"
            return result

        prompt = (
            "You are Ascend Beacon, an internal IT support triage assistant for a role-based immigration case platform. "
            "Read the user-reported issue and return concise JSON only. "
            "Classify the likely technical area, decide whether this seems like expected behavior, a likely product bug, or something that still needs verification, "
            "explain the reasoning briefly, write a short user-facing receipt summary, write an admin-facing triage summary, identify the most likely root cause, "
            "and provide specific next actions for the admin team. "
            "Take the reported priority, blocking flag, and any attachment descriptions into account when writing the summaries. "
            "Do not promise a fix. Do not invent logs or code paths that are not implied by the report. "
            "If the report sounds ambiguous, say so clearly and mark it as needs_verification.\n\n"
            f"Support ticket payload JSON: {json.dumps(ticket_payload)}"
        )
        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "support_ticket_triage",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "category": {"type": "string", "enum": SUPPORT_CATEGORIES},
                            "behavior_assessment": {"type": "string", "enum": ["expected_behavior", "likely_bug", "needs_verification"]},
                            "user_summary": {"type": "string"},
                            "admin_summary": {"type": "string"},
                            "reasoning": {"type": "string"},
                            "root_cause": {"type": "string"},
                            "next_actions": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "category",
                            "behavior_assessment",
                            "user_summary",
                            "admin_summary",
                            "reasoning",
                            "root_cause",
                            "next_actions",
                        ],
                    },
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key()}",
                "Content-Type": "application/json",
                "OpenAI-User": self.config.get("user", "ascend-suite-local"),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=int(self.config.get("timeout_seconds", 60))) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            result = fallback_support_ticket(ticket_payload)
            result["source"] = "fallback"
            return result
        text = raw.get("output_text")
        if not text:
            for item in raw.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        try:
            parsed = json.loads(text or "{}")
        except json.JSONDecodeError:
            result = fallback_support_ticket(ticket_payload)
            result["source"] = "fallback"
            return result
        fallback = fallback_support_ticket(ticket_payload)
        next_actions = parsed.get("next_actions")
        cleaned_actions = [str(item).strip() for item in next_actions if str(item).strip()] if isinstance(next_actions, list) else []
        return {
            "category": parsed.get("category") if parsed.get("category") in SUPPORT_CATEGORIES else fallback["category"],
            "behavior_assessment": parsed.get("behavior_assessment") if parsed.get("behavior_assessment") in {"expected_behavior", "likely_bug", "needs_verification"} else fallback["behavior_assessment"],
            "user_summary": str(parsed.get("user_summary") or fallback["user_summary"]).strip(),
            "admin_summary": str(parsed.get("admin_summary") or fallback["admin_summary"]).strip(),
            "reasoning": str(parsed.get("reasoning") or fallback["reasoning"]).strip(),
            "root_cause": str(parsed.get("root_cause") or fallback["root_cause"]).strip(),
            "next_actions": cleaned_actions[:5] or fallback["next_actions"],
            "source": "openai",
        }


def compact_case_payload(case_payload: dict) -> dict:
    payload = dict(case_payload or {})
    payload["evidence_files"] = list((case_payload or {}).get("evidence_files", []))[:60]
    payload["tasks"] = list((case_payload or {}).get("tasks", []))[:20]
    payload["planner_items"] = list((case_payload or {}).get("planner_items", []))[:20]
    payload["recent_messages"] = list((case_payload or {}).get("recent_messages", []))[:12]
    return payload


def fallback_petition_package(case_payload: dict) -> dict:
    criteria = case_payload.get("criteria_summary", [])
    started = [item for item in criteria if int(item.get("evidence_count") or 0) > 0]
    missing = [item for item in criteria if int(item.get("evidence_count") or 0) == 0]
    evidence = case_payload.get("evidence_files", [])
    profile = case_payload.get("profile", {})
    member_name = case_payload.get("member_name") or profile.get("preferred_name") or profile.get("first_name") or "Member"
    strengths = [
        f"{item['name']} already has {item['evidence_count']} documented item(s) in the system."
        for item in started[:4]
    ] or ["The record has at least some uploaded material that can be shaped into a petition narrative."]
    gaps = [
        f"{item['name']} does not yet show active evidence in the current record."
        for item in missing[:5]
    ]
    risks = []
    if len(evidence) < 8:
        risks.append("The current evidence volume appears light for a confident petition-ready narrative.")
    if not profile.get("biography"):
        risks.append("The member biography is not yet filled in, which weakens the attorney's positioning context.")
    if not profile.get("proposed_final_merits_summary"):
        risks.append("A final merits positioning summary is not yet drafted in the profile.")
    if not risks:
        risks.append("The current record looks usable, but criterion balance and corroboration should still be reviewed carefully.")
    open_tasks = [item for item in case_payload.get("tasks", []) if item.get("status") == "open"]
    recommended_fixes = [
        f"Close the open task: {item['title']}."
        for item in open_tasks[:3]
    ]
    if missing:
        recommended_fixes.append(f"Target at least one stronger document for {missing[0]['name']} next.")
    if not recommended_fixes:
        recommended_fixes.append("Review the existing evidence set and add corroboration where official proofs are thin.")
    member_dependencies = [
        "Confirm the professional biography, top achievements, and final merits summary in the profile.",
        "Upload stronger official documents for the weakest criteria.",
    ]
    if open_tasks:
        member_dependencies.insert(0, f"Complete {len(open_tasks)} open builder-assigned task(s) already in the system.")
    external_dependencies = [
        "Official letters, certificates, invitations, or confirmations from third-party organizations may still be needed.",
        "Selective or independent corroboration may be required where evidence is self-described but not formally supported.",
    ]
    clarification_questions = [
        f"What do you consider the top two or three achievements that should anchor {member_name}'s EB1A story?",
        "Which uploaded items are the strongest official proofs versus informal supporting material?",
        "Are there any important achievements, roles, awards, or publications not yet uploaded into the platform?",
    ]
    if missing:
        clarification_questions.append(f"What is the realistic plan and timing to strengthen {missing[0]['name']}?")
    proposed_sections = [
        "Attorney case overview",
        "Member background and field positioning",
        "Criterion-by-criterion strengths",
        "Primary gaps and corrective strategy",
        "Outstanding member and external dependencies",
    ]
    return {
        "executive_summary": f"This draft uses the current platform record to frame {member_name}'s potential EB1A petition narrative and surface what still needs to be clarified or strengthened.",
        "petition_positioning": "The current record should be positioned around the member's strongest documented criteria first, while weaker or thinly supported criteria are treated as active build areas rather than overclaimed strengths.",
        "readiness_assessment": f"{len(started)} criteria show active evidence, while {len(missing)} remain unstarted or thin in the current record.",
        "proposed_sections": proposed_sections,
        "strengths": strengths,
        "gaps": gaps or ["No obvious category gaps were detected from the current structured data."],
        "risks": risks,
        "recommended_fixes": recommended_fixes,
        "member_dependencies": member_dependencies,
        "external_dependencies": external_dependencies,
        "clarification_questions": clarification_questions,
    }


def normalize_petition_package(raw: dict, case_payload: dict) -> dict:
    fallback = fallback_petition_package(case_payload)

    def ensure_list(key: str) -> list[str]:
        value = raw.get(key)
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if cleaned:
                return cleaned[:8]
        return fallback[key]

    return {
        "executive_summary": str(raw.get("executive_summary") or fallback["executive_summary"]).strip(),
        "petition_positioning": str(raw.get("petition_positioning") or fallback["petition_positioning"]).strip(),
        "readiness_assessment": str(raw.get("readiness_assessment") or fallback["readiness_assessment"]).strip(),
        "proposed_sections": ensure_list("proposed_sections"),
        "strengths": ensure_list("strengths"),
        "gaps": ensure_list("gaps"),
        "risks": ensure_list("risks"),
        "recommended_fixes": ensure_list("recommended_fixes"),
        "member_dependencies": ensure_list("member_dependencies"),
        "external_dependencies": ensure_list("external_dependencies"),
        "clarification_questions": ensure_list("clarification_questions"),
    }


def fallback_support_ticket(ticket_payload: dict) -> dict:
    portal = str(ticket_payload.get("portal") or "portal").strip()
    issue_location = str(ticket_payload.get("issue_location") or "").strip()
    short_description = str(ticket_payload.get("short_description") or "").strip()
    details = str(ticket_payload.get("details") or "").strip()
    current_url = str(ticket_payload.get("current_url") or "").strip()
    screenshot_url = str(ticket_payload.get("screenshot_url") or "").strip()
    priority = str(ticket_payload.get("priority") or "normal").strip().lower() or "normal"
    is_blocking = bool(ticket_payload.get("is_blocking"))
    attachments = ticket_payload.get("attachments") or []
    attachment_notes = " ".join(
        f"{item.get('file_name', '')} {item.get('description', '')}"
        for item in attachments
        if isinstance(item, dict)
    )
    combined = " ".join([portal, issue_location, short_description, details, current_url, screenshot_url, priority, attachment_notes]).lower()

    category = "other"
    root_cause = "The report is technical, but the likely failure area is not specific enough yet from the current description."
    next_actions = [
        "Reproduce the issue from the same portal and capture the exact step where behavior diverges.",
        "Check recent operational events around the reported time window.",
        "Review whether the problem is isolated to one portal, one member record, or all users.",
    ]

    if any(token in combined for token in ("login", "sign in", "password", "credential", "session", "logout", "auth")):
        category = "auth"
        root_cause = "The report points to an authentication or session-state problem in the selected portal."
        next_actions = [
            "Review recent auth failures and session events for the affected account.",
            "Verify the user is using the correct portal-specific credentials.",
            "Reset the affected session if stale auth state is suspected.",
        ]
    elif any(token in combined for token in ("upload", "evidence", "document", "file", "drive", "storage", "missing", "not visible", "cannot open")):
        category = "data_sync"
        root_cause = "The report suggests a document visibility, storage-link, or cross-portal data sync mismatch."
        next_actions = [
            "Compare the stored document row with the expected client and case assignment.",
            "Verify the portal is filtering the correct member, criterion, and status.",
            "Check whether the storage link or mirrored file path is missing or stale.",
        ]
    elif any(token in combined for token in ("openai", "ai", "assistant", "navigator", "chatbot", "chat")):
        category = "assistant"
        root_cause = "The report centers on the assistant layer, likely in prompt routing, context retrieval, or fallback behavior."
        next_actions = [
            "Inspect the latest assistant request and response path for the reported portal.",
            "Verify the selected member context and retrieved references matched the user question.",
            "Check whether the environment is using the OpenAI path or fallback mode.",
        ]
    elif any(token in combined for token in ("access", "permission", "assigned", "not allowed", "cannot see", "can't see", "unable to see")):
        category = "access"
        root_cause = "The report suggests a role-based access or assignment-scoping mismatch."
        next_actions = [
            "Confirm the user's role and current assignment mapping for the selected member.",
            "Verify portal-specific access rules for the requested view or action.",
            "Compare the visible roster with the database assignment state.",
        ]
    elif any(token in combined for token in ("slow", "loading", "hang", "stuck", "spinning", "blank", "crash", "frozen")):
        category = "performance"
        root_cause = "The report suggests a frontend load, performance, or long-running request problem."
        next_actions = [
            "Reproduce the slow or hanging flow while checking the portal's backing API call.",
            "Inspect recent operational errors and long-running requests for the same endpoint.",
            "Verify whether one stale local process or config mismatch is affecting the portal.",
        ]
    elif any(token in combined for token in ("button", "layout", "font", "scroll", "screen", "page", "modal", "click", "ui", "design")):
        category = "ui"
        root_cause = "The report points to a frontend rendering or interaction issue in the current portal screen."
        next_actions = [
            "Reproduce the layout or interaction issue on the reported portal section.",
            "Inspect the component state and any portal-specific conditional rendering around that screen.",
            "Check whether the issue is isolated to one role or shared across the common shell.",
        ]

    behavior_assessment = "needs_verification"
    if any(token in combined for token in ("can't", "cannot", "unable", "error", "failed", "fail", "missing", "wrong", "stuck", "doesn't", "doesnt", "not visible", "not working", "won't", "wont")):
        behavior_assessment = "likely_bug"
    elif any(token in combined for token in ("expected", "by design", "designed", "intended", "supposed to")):
        behavior_assessment = "expected_behavior"

    if behavior_assessment == "expected_behavior":
        reasoning = "The report includes language that suggests the user may be checking whether a current behavior is intentional, so this should be verified against product design before treating it as a defect."
    elif behavior_assessment == "likely_bug":
        reasoning = f"The report describes a broken or missing workflow in the {portal.lower()}, and the keywords point most strongly to the {category.replace('_', ' ')} area."
    else:
        reasoning = f"The issue is technical and likely related to the {category.replace('_', ' ')} area, but the current description is still too ambiguous to call it expected behavior or a confirmed bug."

    if is_blocking and behavior_assessment != "expected_behavior":
        reasoning += " The user also marked the issue as blocking, so it should be prioritized for faster reproduction."
    if priority in {"high", "urgent"} and behavior_assessment != "expected_behavior":
        reasoning += f" The reported priority is {priority}, which raises the urgency of the next admin review."

    user_summary = f"Ascend Beacon logged this as a {behavior_assessment.replace('_', ' ')} report from the {portal} and queued it for admin review."
    if is_blocking:
        user_summary += " The issue was marked as blocking."
    admin_summary = (
        f"Reported from {portal}"
        + (f" at {issue_location}" if issue_location else "")
        + f". Initial triage points to {category.replace('_', ' ')} with assessment `{behavior_assessment}`."
    )
    if priority in {"low", "high", "urgent"}:
        admin_summary += f" Reported priority: {priority}."
    if is_blocking:
        admin_summary += " User marked this as blocking."
    return {
        "category": category,
        "behavior_assessment": behavior_assessment,
        "user_summary": user_summary,
        "admin_summary": admin_summary,
        "reasoning": reasoning,
        "root_cause": root_cause,
        "next_actions": next_actions,
    }


def fallback_portal_assistant(assistant_payload: dict) -> dict:
    context = assistant_payload.get("context", {})
    member = context.get("member") or {}
    metrics = context.get("metrics") or {}
    role = assistant_payload.get("actor_role", "builder")
    role_label = role.replace("_", " ").title()
    question = assistant_payload.get("question", "").strip()
    detail_requested = bool(assistant_payload.get("detail_requested"))
    references = select_relevant_references(question, assistant_payload.get("references", []))
    retrieved_documents = context.get("retrieved_documents") or []
    next_steps = context.get("next_steps") or []
    strengths = context.get("strengths") or []
    gaps = context.get("gaps") or []
    member_name = member.get("display_name") or "the selected member"
    readiness = int(metrics.get("readiness_score") or 0)
    evidence_count = int(metrics.get("evidence_count") or len(context.get("evidence", [])) or 0)
    open_tasks = int(metrics.get("open_tasks") or len([item for item in context.get("tasks", []) if item.get("status") == "open"]))
    focus = next_steps[0] if next_steps else "review the thinnest criterion coverage and choose the next strongest supporting document"

    summary = direct_portal_answer(
        question,
        member_name,
        references,
        retrieved_documents,
        focus,
        readiness,
        evidence_count,
        open_tasks,
    )
    detail = [
        f"{role_label} context shows {member_name} at {readiness}% readiness.",
        f"Current strengths: {', '.join(strengths[:3]) if strengths else 'no strong criterion cluster has separated itself yet'}.",
        f"Current gaps: {', '.join(gaps[:3]) if gaps else 'no obvious criterion gap is fully empty, but some areas still need stronger corroboration'}.",
        f"Recommended next action: {focus}.",
    ]
    if references:
        detail.append(
            "Storage-backed references available now: "
            + "; ".join(f"{item.get('label', item.get('title', 'Reference'))} ({item.get('location', 'Storage path unavailable')})" for item in references[:3])
            + "."
        )
    excerpt_summaries = [
        f"{item.get('file_name', item.get('title', 'Document'))} says {str(item.get('excerpt', '')).strip()[:140]}"
        for item in retrieved_documents[:2]
        if str(item.get("excerpt", "")).strip()
    ]
    if excerpt_summaries:
        detail.append(
            "Retrieved document context: " + "; ".join(excerpt_summaries) + "."
        )
    if role == "leader":
        detail.append("Leader-level answers can also use assignment and domain rollup context from the current roster.")
    elif role == "attorney":
        detail.append("Attorney answers are case-planning support and should still be reviewed as legal work product.")
    else:
        detail.append("Builder answers are tuned toward member momentum, active tasks, and the next strongest profile-building move.")
    return {
        "summary": summary,
        "detailed_answer": " ".join(detail),
        "detail_prompt": "Elaborate",
        "suggested_follow_up": "Ask for a deeper evidence trail, a storage-backed reference list, or the top three follow-ups for this member.",
        "needs_more_detail": not detail_requested,
        "response_mode": "detailed" if detail_requested else "summary",
        "references": references,
    }


def direct_portal_answer(
    question: str,
    member_name: str,
    references: list[dict],
    retrieved_documents: list[dict],
    focus: str,
    readiness: int,
    evidence_count: int,
    open_tasks: int,
) -> str:
    lowered = question.lower()
    primary = (retrieved_documents or references or [{}])[0]
    label = primary.get("label") or primary.get("file_name") or primary.get("title") or "the matching file"
    created_at = format_answer_date(primary.get("created_at", ""))
    if "when" in lowered and any(token in lowered for token in ("media", "assignment", "file", "document", "complete")):
        if created_at:
            return f"Based on the current evidence, the last matching file appears on {created_at}."
        return f"Based on the current evidence, `{label}` is the best match, but I do not see a reliable completion date."
    if "when" in lowered and created_at:
        return f"Based on the current evidence, `{label}` is dated {created_at}."
    if any(token in lowered for token in ("which", "what file", "what document", "best document", "best file")):
        return f"Based on the current evidence, `{label}` looks like the best match."
    if "where" in lowered and primary.get("location"):
        return f"Based on the current evidence, the best matching file is under {primary.get('location')}."
    return (
        f"Based on the current evidence, {member_name} is at {readiness}% readiness with {evidence_count} evidence item"
        f"{'' if evidence_count == 1 else 's'} and {open_tasks} open task"
        f"{'' if open_tasks == 1 else 's'}. The clearest next move is to {focus}."
    )


def format_answer_date(raw_value: str) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).strftime("%B %d, %Y")
        except ValueError:
            continue
    return value


def select_relevant_references(question: str, references: list[dict]) -> list[dict]:
    if not references:
        return []
    words = {token.strip(".,:;!?()[]{}").lower() for token in question.split() if token.strip()}
    ranked: list[tuple[int, dict]] = []
    for item in references:
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ("title", "label", "location", "summary", "document_type", "criterion_name")
        ).lower()
        score = sum(1 for word in words if len(word) > 2 and word in haystack)
        ranked.append((score, item))
    ranked.sort(key=lambda entry: entry[0], reverse=True)
    selected = [item for score, item in ranked if score > 0][:3]
    return selected or references[:2]


def extract_document_excerpt(file_name: str, content_type: str, file_bytes: bytes) -> str:
    if content_type.startswith("text/") or file_name.lower().endswith((".txt", ".md", ".csv", ".json")):
        return file_bytes[:18000].decode("utf-8", errors="replace")
    decoded = file_bytes[:18000].decode("utf-8", errors="ignore")
    if decoded.strip():
        return decoded
    return "Document text could not be extracted automatically. Use filename, content type, and member context."


def fallback_analysis(member_context: str, file_name: str, document_excerpt: str, criteria: list[dict]) -> dict:
    combined = f"{file_name} {member_context} {document_excerpt}".lower()
    keyword_map = [
        ("awards", ["award", "prize", "honor", "winner"]),
        ("memberships", ["member", "membership", "fellow", "association"]),
        ("published_material", ["published about", "media", "press", "news", "article about"]),
        ("judging", ["judge", "reviewer", "peer review", "evaluation", "panel"]),
        ("original_contributions", ["patent", "contribution", "impact", "innovation", "original"]),
        ("scholarly_articles", ["journal", "publication", "paper", "scholarly", "citation"]),
        ("leading_critical_role", ["lead", "manager", "director", "critical role", "principal"]),
        ("high_salary", ["salary", "compensation", "pay", "remuneration"]),
    ]
    selected_code = "other"
    for code, keywords in keyword_map:
        if any(keyword in combined for keyword in keywords):
            selected_code = code
            break
    criterion = next((item for item in criteria if item["code"] == selected_code), criteria[-1])
    document_type = infer_document_type(combined)
    title = file_name.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip() or "Uploaded evidence"
    context = member_context.strip() or "The member uploaded this document for EB1A evidence review."
    return {
        "criterion_code": criterion["code"],
        "criterion_name": criterion["name"],
        "document_type": document_type,
        "title": title[:120],
        "ai_description": f"{context} This document appears relevant to {criterion['name']} and should be reviewed by Ascend.",
        "quality_score": 45,
        "confidence": 45,
    }


def normalize_analysis(raw: dict, criteria: list[dict], file_name: str, member_context: str) -> dict:
    allowed = {item["code"]: item for item in criteria}
    criterion_code = raw.get("criterion_code", "")
    if criterion_code not in allowed:
        criterion_code = "other"
    criterion = allowed[criterion_code]
    document_type = str(raw.get("document_type") or "Other").strip()
    if document_type not in DOCUMENT_TYPES:
        document_type = "Other"
    title = str(raw.get("title") or file_name.rsplit(".", 1)[0] or "Uploaded evidence").strip()
    description = str(raw.get("ai_description") or member_context or "Evidence uploaded for Ascend review.").strip()
    return {
        "criterion_code": criterion["code"],
        "criterion_name": criterion["name"],
        "document_type": document_type,
        "title": title[:160],
        "ai_description": description,
        "quality_score": int(raw.get("quality_score") or 50),
        "confidence": int(raw.get("confidence") or 50),
    }


def infer_document_type(combined: str) -> str:
    keyword_map = [
        ("Invitation", ["invite", "invitation", "invited", "nomination invitation"]),
        ("Attendance", ["attended", "attendance", "participated", "participant", "joined", "session attended"]),
        ("Thank You Note", ["thank you", "thanks for", "appreciation", "grateful"]),
        ("Acceptance or Selection", ["accepted", "selected", "selection", "chosen", "approved"]),
        ("Certificate or Completion", ["certificate", "completed", "completion", "credential", "badge"]),
        ("Confirmation Email", ["confirmation", "confirmed", "registration successful"]),
        ("Agenda or Program", ["agenda", "program", "schedule", "itinerary"]),
        ("Photo or Screenshot", ["screenshot", "photo", "image", ".png", ".jpg", ".jpeg"]),
        ("Receipt or Payment Proof", ["receipt", "invoice", "payment", "transaction"]),
        ("Publication or Media", ["publication", "published", "media", "article", "press"]),
        ("Recommendation or Support", ["recommendation", "support letter", "endorsement"]),
        ("Appointment or Contract", ["appointment", "contract", "agreement", "offer"]),
        ("Impact or Results", ["result", "impact", "outcome", "metrics", "report"]),
    ]
    for label, keywords in keyword_map:
        if any(keyword in combined for keyword in keywords):
            return label
    return "Other"

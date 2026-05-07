import os
import json
import html
import re
import urllib.error
import urllib.request
import zipfile
import zlib
from datetime import datetime
from xml.etree import ElementTree as ET

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

    def generate_endeavor_letter(self, case_payload: dict, prompt_config: dict) -> dict:
        compact_payload = compact_endeavor_payload(case_payload)
        normalized_config = normalize_endeavor_prompt_config(prompt_config, compact_payload)
        compiled_prompt = build_endeavor_letter_prompt(compact_payload, normalized_config)
        if not self.enabled:
            result = fallback_endeavor_letter(compact_payload, normalized_config)
            result["compiled_prompt"] = compiled_prompt
            result["normalized_prompt_config"] = normalized_config
            result["source"] = "disabled"
            return result

        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": compiled_prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "endeavor_letter_generator",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "date_line": {"type": "string"},
                            "re_line": {"type": "string"},
                            "beneficiary_line": {"type": "string"},
                            "subject_line": {"type": "string"},
                            "salutation": {"type": "string"},
                            "opening_paragraph": {"type": "string"},
                            "sections": {
                                "type": "array",
                                "minItems": 4,
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "heading": {"type": "string"},
                                        "body": {"type": "string"},
                                    },
                                    "required": ["heading", "body"],
                                },
                            },
                            "closing_paragraph": {"type": "string"},
                            "signature_line": {"type": "string"},
                        },
                        "required": [
                            "title",
                            "date_line",
                            "re_line",
                            "beneficiary_line",
                            "subject_line",
                            "salutation",
                            "opening_paragraph",
                            "sections",
                            "closing_paragraph",
                            "signature_line",
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
            result = fallback_endeavor_letter(compact_payload, normalized_config)
            result["compiled_prompt"] = compiled_prompt
            result["normalized_prompt_config"] = normalized_config
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
        result = normalize_endeavor_letter(json.loads(text or "{}"), compact_payload, normalized_config)
        result["compiled_prompt"] = compiled_prompt
        result["normalized_prompt_config"] = normalized_config
        result["source"] = "openai"
        return result

    def generate_recommendation_letter(self, case_payload: dict, prompt_config: dict) -> dict:
        compact_payload = compact_recommendation_payload(case_payload)
        normalized_config = normalize_recommendation_prompt_config(prompt_config, compact_payload)
        compiled_prompt = build_recommendation_letter_prompt(compact_payload, normalized_config)
        if not self.enabled:
            result = fallback_recommendation_letter(compact_payload, normalized_config)
            result["compiled_prompt"] = compiled_prompt
            result["normalized_prompt_config"] = normalized_config
            result["source"] = "disabled"
            return result

        payload = {
            "model": self.config.get("model", "gpt-5.4-mini"),
            "input": compiled_prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "recommendation_letter_generator",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {"type": "string"},
                            "date_line": {"type": "string"},
                            "re_line": {"type": "string"},
                            "addressee_line": {"type": "string"},
                            "salutation": {"type": "string"},
                            "opening_paragraph": {"type": "string"},
                            "sections": {
                                "type": "array",
                                "minItems": 4,
                                "maxItems": 4,
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "heading": {"type": "string"},
                                        "body": {"type": "string"},
                                    },
                                    "required": ["heading", "body"],
                                },
                            },
                            "closing_paragraph": {"type": "string"},
                            "signature_line": {"type": "string"},
                        },
                        "required": [
                            "title",
                            "date_line",
                            "re_line",
                            "addressee_line",
                            "salutation",
                            "opening_paragraph",
                            "sections",
                            "closing_paragraph",
                            "signature_line",
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
            result = fallback_recommendation_letter(compact_payload, normalized_config)
            result["compiled_prompt"] = compiled_prompt
            result["normalized_prompt_config"] = normalized_config
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
        result = normalize_recommendation_letter(json.loads(text or "{}"), compact_payload, normalized_config)
        result["compiled_prompt"] = compiled_prompt
        result["normalized_prompt_config"] = normalized_config
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


def compact_endeavor_payload(case_payload: dict) -> dict:
    payload = dict(case_payload or {})
    payload["evidence_files"] = list((case_payload or {}).get("evidence_files", []))[:80]
    payload["parsed_evidence"] = list((case_payload or {}).get("parsed_evidence", []))[:80]
    payload["tasks"] = list((case_payload or {}).get("tasks", []))[:20]
    payload["planner_items"] = list((case_payload or {}).get("planner_items", []))[:20]
    payload["recent_messages"] = list((case_payload or {}).get("recent_messages", []))[:12]
    return payload


def compact_recommendation_payload(case_payload: dict) -> dict:
    payload = compact_endeavor_payload(case_payload)
    payload["selected_project"] = dict((case_payload or {}).get("selected_project") or {})
    payload["letter_kind"] = str((case_payload or {}).get("letter_kind") or "independent").strip()
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


def normalize_endeavor_prompt_config(raw: dict, case_payload: dict) -> dict:
    profile = case_payload.get("profile", {}) or {}
    member_name = case_payload.get("member_name") or profile.get("preferred_name") or profile.get("first_name") or "the member"
    field = " ".join(
        part for part in [
            profile.get("primary_field", "").strip(),
            profile.get("specialization", "").strip(),
        ] if part
    ).strip() or profile.get("industry_domain", "").strip() or "the member's field of expertise"
    role_line = " • ".join(
        part for part in [
            profile.get("current_title", "").strip(),
            profile.get("current_employer", "").strip(),
        ] if part
    )
    strengths = [item.get("criterion_name") or item.get("name") for item in case_payload.get("criteria_summary", []) if int(item.get("evidence_count") or 0) > 0]
    evidence_titles = [item.get("title") or item.get("file_name") for item in case_payload.get("evidence_files", [])[:6] if item.get("title") or item.get("file_name")]
    planner_focus = [item.get("description") for item in case_payload.get("planner_items", [])[:3] if item.get("description")]

    defaults = {
        "who_you_are": "You are an expert EB1A Attorney looking at multiple successful cases. Write down the endeavor letter so that USCIS officer is convinced naturally without RFE.",
        "field_of_expertise": field,
        "proposed_endeavor": f"{member_name} will continue advancing {field} in the United States through ongoing professional work, technical leadership, and field-shaping contributions.",
        "current_work_continuity": f"The letter should connect the proposed endeavor directly to {role_line or 'the member’s current professional responsibilities'} and prior evidence-backed achievements.",
        "future_work_plan": " ".join(planner_focus) or "Explain the specific work the member plans to continue in the United States over the near and medium term, including applied innovation, publications, judging, mentoring, and other lawful field contributions where supported.",
        "national_importance": f"Explain why this work matters in the United States, focusing on practical impact, innovation, sector value, and downstream benefit rather than generic praise. Relevant domain: {profile.get('industry_domain', '').strip() or field}.",
        "evidence_emphasis": "; ".join(evidence_titles) or "Use the uploaded evidence set to ground the member's prior achievements, role progression, recognition, and future work trajectory.",
        "attorney_strategy_notes": f"Emphasize continuity, credibility, and a fact-grounded future plan. Strongest criterion areas currently reflected in the record: {', '.join(strengths[:4]) or 'use the strongest documented criteria first'}.",
        "tone_guidance": "Write in first person, professional, concrete, and measured. Keep the storyline natural and cohesive. Avoid bullet points, numbered-list phrasing, overclaiming, speculation, and unsupported legal conclusions.",
        "length_constraints": "Keep the final letter within two pages, roughly 700 to 900 words, and closely follow the attached endeavor-letter template format.",
    }
    cleaned = {}
    raw = raw or {}
    for key, default in defaults.items():
        value = str(raw.get(key) or default).strip()
        cleaned[key] = value or default
    return cleaned


def build_endeavor_letter_prompt(case_payload: dict, prompt_config: dict) -> str:
    compact_payload = compact_endeavor_payload(case_payload)
    return (
        f"{prompt_config.get('who_you_are', '').strip()} "
        "You are helping an EB1A attorney portal draft a member-specific endeavor letter. "
        "Use the attached-style format only as a template shell, but do not reuse or echo any original source-letter facts or wording. "
        "Write a fresh first-person letter grounded only in the provided member profile, structured evidence metadata, parsed document excerpts, planner history, and recent case context. "
        "The final letter must stay within two pages, be concrete, fact-based, and useful for an EB1A filing record. "
        "Do not invent employers, metrics, publications, projects, awards, or future plans that are not reasonably supported by the payload or attorney prompt guidance. "
        "Use a formal letter structure with these elements: title, date line, USCIS reference lines, beneficiary line, subject line, salutation, opening paragraph, four body paragraphs or paragraph groups, closing paragraph, and signature line. "
        "The body should naturally cover: field and importance, established experience and continuity, proposed future endeavor in the United States, and direct U.S. benefit plus near-term continuation plan. "
        "Do not write bullet points, numbered sections, list markers, or memo-style outline headings in the final letter. If you use headings in the JSON, keep them short, optional, and non-numbered. "
        "Favor concise, evidence-backed prose and smooth transitions so the final letter reads as one natural storyline. "
        "Return JSON only.\n\n"
        f"Attorney prompt configuration JSON: {json.dumps(prompt_config)}\n\n"
        f"Case payload JSON: {json.dumps(compact_payload)}"
    )


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


def fallback_endeavor_letter(case_payload: dict, prompt_config: dict) -> dict:
    profile = case_payload.get("profile", {}) or {}
    member_name = case_payload.get("member_name") or profile.get("preferred_name") or profile.get("first_name") or "Member"
    role_line = " at ".join(
        part for part in [
            profile.get("current_title", "").strip(),
            profile.get("current_employer", "").strip(),
        ] if part
    ) or profile.get("current_title", "").strip() or "the member's current professional role"
    field = prompt_config.get("field_of_expertise") or profile.get("primary_field") or "the member's field of expertise"
    strengths = [item.get("criterion_name") or item.get("name") for item in case_payload.get("criteria_summary", []) if int(item.get("evidence_count") or 0) > 0]
    evidence_refs = [item.get("title") or item.get("file_name") for item in case_payload.get("evidence_files", [])[:4] if item.get("title") or item.get("file_name")]
    sections = [
        {
            "heading": "",
            "body": f"My field is {field}. I intend to continue applying this expertise in the United States through practical, high-impact work that addresses real needs in my domain. The work reflected in my record shows sustained progression, technical responsibility, and applied contributions rather than isolated activity.",
        },
        {
            "heading": "",
            "body": f"My proposed endeavor is a direct continuation of the same expertise reflected in my prior record and my current role as {role_line}. The evidence already uploaded in my case file, including {', '.join(evidence_refs[:3]) or 'the current documentary record'}, supports the continuity of my work, my recognition, and the areas in which I have already made meaningful contributions.",
        },
        {
            "heading": "",
            "body": prompt_config.get("proposed_endeavor") or f"I intend to continue advancing {field} in the United States through ongoing professional work, innovation, and field-level contributions that build naturally on my existing expertise.",
        },
        {
            "heading": "",
            "body": f"My continued work will benefit the United States because it applies proven expertise to important problems with operational, technical, and broader field value. The record already reflects evidence across {', '.join(strengths[:4]) or 'multiple EB1A criteria'}, and I intend to continue building on that foundation through concrete work, ongoing innovation, and responsible professional contributions in the United States.",
        },
    ]
    return normalize_endeavor_letter(
        {
            "title": "Statement of Proposed Endeavor and Intention to Continue Work in the Area of Expertise",
            "date_line": "Date: __________",
            "re_line": "Re: Form I-140, EB-1A Extraordinary Ability Petition",
            "beneficiary_line": f"Petitioner/Beneficiary: {member_name}",
            "subject_line": f"Subject: Statement of Proposed Endeavor and Continuing Work in {field}",
            "salutation": "Dear Officer:",
            "opening_paragraph": f"I respectfully submit this statement to explain the work I have performed, the work I am performing now, and the work I intend to continue performing in the United States. My proposed endeavor remains in the same field of expertise reflected throughout my record, and it builds directly on my demonstrated experience, recognition, and ongoing professional responsibilities.",
            "sections": sections,
            "closing_paragraph": "For these reasons, I respectfully affirm my intention to continue working in my area of expertise in the United States and to build on the same field-specific contributions reflected in my petition record.",
            "signature_line": member_name,
        },
        case_payload,
        prompt_config,
    )


def normalize_endeavor_letter(raw: dict, case_payload: dict, prompt_config: dict) -> dict:
    profile = case_payload.get("profile", {}) or {}
    member_name = case_payload.get("member_name") or profile.get("preferred_name") or profile.get("first_name") or "Member"
    sections = raw.get("sections") if isinstance(raw.get("sections"), list) else []
    normalized_sections = []
    fallback_headings = [
        "",
        "",
        "",
        "",
    ]
    for index in range(4):
        candidate = sections[index] if index < len(sections) and isinstance(sections[index], dict) else {}
        heading = clip_words(str(candidate.get("heading") or fallback_headings[index]).strip(), 10)
        body = clip_words(str(candidate.get("body") or "").strip(), 130)
        if not body:
            body = clip_words((prompt_config.get("proposed_endeavor") or prompt_config.get("current_work_continuity") or "").strip(), 110)
        normalized_sections.append({"heading": heading, "body": body})

    letter = {
        "title": clip_words(str(raw.get("title") or "Statement of Proposed Endeavor and Intention to Continue Work in the Area of Expertise").strip(), 18),
        "date_line": str(raw.get("date_line") or "Date: __________").strip() or "Date: __________",
        "re_line": clip_words(str(raw.get("re_line") or "Re: Form I-140, EB-1A Extraordinary Ability Petition").strip(), 14),
        "beneficiary_line": clip_words(str(raw.get("beneficiary_line") or f"Petitioner/Beneficiary: {member_name}").strip(), 16),
        "subject_line": clip_words(str(raw.get("subject_line") or f"Subject: Statement of Proposed Endeavor and Continuing Work in {prompt_config.get('field_of_expertise') or 'the area of expertise'}").strip(), 28),
        "salutation": str(raw.get("salutation") or "Dear Officer:").strip() or "Dear Officer:",
        "opening_paragraph": clip_words(str(raw.get("opening_paragraph") or "").strip(), 120),
        "sections": normalized_sections,
        "closing_paragraph": clip_words(str(raw.get("closing_paragraph") or "").strip(), 90),
        "signature_line": clip_words(str(raw.get("signature_line") or member_name).strip(), 8),
    }
    if not letter["opening_paragraph"]:
        letter["opening_paragraph"] = clip_words(
            f"I respectfully submit this statement to describe the work I have performed, the work I am currently performing, and the work I intend to continue performing in the United States in {prompt_config.get('field_of_expertise') or 'my field of expertise'}.",
            120,
        )
    if not letter["closing_paragraph"]:
        letter["closing_paragraph"] = "I respectfully confirm my intention to continue this work in the United States."
    letter["plain_text"] = render_endeavor_letter_text(letter)
    letter["estimated_word_count"] = word_count(letter["plain_text"])
    letter["estimated_page_count"] = max(1, (letter["estimated_word_count"] + 449) // 450)
    if letter["estimated_page_count"] > 2:
        letter["closing_paragraph"] = clip_words(letter["closing_paragraph"], 60)
        letter["plain_text"] = render_endeavor_letter_text(letter)
        letter["estimated_word_count"] = word_count(letter["plain_text"])
        letter["estimated_page_count"] = max(1, (letter["estimated_word_count"] + 449) // 450)
    return letter


def render_endeavor_letter_text(letter: dict) -> str:
    parts = [
        letter.get("title", ""),
        letter.get("date_line", ""),
        "U.S. Citizenship and Immigration Services",
        letter.get("re_line", ""),
        letter.get("beneficiary_line", ""),
        letter.get("subject_line", ""),
        letter.get("salutation", ""),
        letter.get("opening_paragraph", ""),
    ]
    for section in letter.get("sections", []):
        if section.get("heading"):
            parts.append(section.get("heading", ""))
        parts.append(section.get("body", ""))
    parts.extend([letter.get("closing_paragraph", ""), letter.get("signature_line", "")])
    return "\n\n".join(part.strip() for part in parts if str(part).strip())


def normalize_recommendation_prompt_config(raw: dict, case_payload: dict) -> dict:
    profile = case_payload.get("profile", {}) or {}
    project = case_payload.get("selected_project", {}) or {}
    member_name = case_payload.get("member_name") or profile.get("preferred_name") or profile.get("first_name") or "the member"
    project_title = project.get("title") or project.get("project_name") or project.get("contribution_title") or "the selected project"
    criterion_name = project.get("criterion_name") or "the selected EB1A criterion"
    field = " ".join(part for part in [profile.get("primary_field", ""), profile.get("specialization", "")] if str(part).strip()).strip()
    field = field or profile.get("industry_domain", "") or "the member's field"
    defaults = {
        "who_you_are": "You are an expert EB1A attorney drafting a recommendation letter for review and signature by a recommender.",
        "letter_kind": str(case_payload.get("letter_kind") or "independent").strip() or "independent",
        "recommender_name": "Recommender Name",
        "recommender_title": "Recommender Title",
        "recommender_organization": "Recommender Organization",
        "recommender_relationship": "Explain how the recommender knows the member and why their view is credible.",
        "project_focus": f"Focus on {project_title} and connect it to {criterion_name}.",
        "facts_to_confirm": "Confirm dates, project scope, member's personal contribution, measurable impact, and why the work mattered beyond routine job duties.",
        "independence_guidance": "For independent letters, explain the recommender's independence and field authority. For dependent/project letters, explain firsthand knowledge and role-specific credibility.",
        "attorney_strategy_notes": f"Ground every claim in the selected project and the evidence packet for {member_name}; avoid generic praise.",
        "tone_guidance": "Professional, concrete, fact-based, and suitable for a recommender to review and sign. Do not overclaim or invent facts.",
        "length_constraints": "Keep the letter around one to two pages with a natural opening, four concise body sections, and a signature block.",
        "field_of_expertise": field,
    }
    cleaned = {}
    raw = raw or {}
    for key, default in defaults.items():
        value = str(raw.get(key) or default).strip()
        cleaned[key] = value or default
    return cleaned


def build_recommendation_letter_prompt(case_payload: dict, prompt_config: dict) -> str:
    compact_payload = compact_recommendation_payload(case_payload)
    return (
        f"{prompt_config.get('who_you_are', '').strip()} "
        "Draft a fresh EB1A recommendation/support letter grounded only in the supplied member profile, selected Critical Role or Original Contribution project, evidence metadata, parsed excerpts, and attorney prompt fields. "
        "The selected project is mandatory context; do not write a generic letter detached from that project. "
        "The letter should be ready for attorney review and recommender signature, not addressed as a legal memo. "
        "Do not invent employers, project names, metrics, awards, publications, or external validation not supported by the payload or attorney prompt. "
        "Use formal letter format with date, USCIS addressee, RE line, salutation, opening paragraph, four body sections, closing paragraph, and signature line. "
        "Return JSON only.\n\n"
        f"Attorney prompt configuration JSON: {json.dumps(prompt_config)}\n\n"
        f"Case payload JSON: {json.dumps(compact_payload)}"
    )


def fallback_recommendation_letter(case_payload: dict, prompt_config: dict) -> dict:
    profile = case_payload.get("profile", {}) or {}
    project = case_payload.get("selected_project", {}) or {}
    member_name = case_payload.get("member_name") or profile.get("preferred_name") or profile.get("first_name") or "Member"
    field = prompt_config.get("field_of_expertise") or profile.get("primary_field") or "the member's field"
    project_title = project.get("title") or project.get("project_name") or project.get("contribution_title") or "the selected project"
    criterion_name = project.get("criterion_name") or "the selected EB1A criterion"
    recommender_name = prompt_config.get("recommender_name") or "Recommender Name"
    recommender_title = prompt_config.get("recommender_title") or "Recommender Title"
    recommender_org = prompt_config.get("recommender_organization") or "Recommender Organization"
    relationship = prompt_config.get("recommender_relationship") or "I am familiar with the member's work through the selected project."
    sections = [
        {
            "heading": "Basis for this recommendation",
            "body": f"I am providing this letter based on my knowledge of {member_name}'s work in {field}. {relationship} My comments are focused on {project_title}, which relates to {criterion_name}.",
        },
        {
            "heading": "Project and role",
            "body": f"In connection with {project_title}, {member_name}'s role should be described through concrete responsibilities, dates, and the specific contribution that distinguished the work from routine participation.",
        },
        {
            "heading": "Impact and significance",
            "body": prompt_config.get("facts_to_confirm") or "The recommender should confirm measurable results, adoption, business value, field value, or other evidence showing why the contribution mattered.",
        },
        {
            "heading": "Why this supports the petition",
            "body": f"The facts above can help explain why {member_name}'s work supports {criterion_name}, especially when paired with independent evidence, project records, metrics, and the broader petition record.",
        },
    ]
    return normalize_recommendation_letter(
        {
            "title": "Recommendation Letter",
            "date_line": "Date: __________",
            "re_line": f"Re: Recommendation for {member_name}",
            "addressee_line": "U.S. Citizenship and Immigration Services",
            "salutation": "Dear Officer:",
            "opening_paragraph": f"I am pleased to provide this recommendation in support of {member_name}. I currently serve as {recommender_title} at {recommender_org}.",
            "sections": sections,
            "closing_paragraph": f"For these reasons, I believe {member_name}'s work on {project_title} is meaningful and should be considered as part of the overall EB1A record.",
            "signature_line": f"{recommender_name}\n{recommender_title}\n{recommender_org}",
        },
        case_payload,
        prompt_config,
    )


def normalize_recommendation_letter(raw: dict, case_payload: dict, prompt_config: dict) -> dict:
    project = case_payload.get("selected_project", {}) or {}
    member_name = case_payload.get("member_name") or (case_payload.get("profile", {}) or {}).get("preferred_name") or "Member"
    project_title = project.get("title") or project.get("project_name") or project.get("contribution_title") or "selected project"
    sections = raw.get("sections") if isinstance(raw.get("sections"), list) else []
    normalized_sections = []
    fallback_headings = ["Basis for recommendation", "Project and personal role", "Impact and corroboration", "Petition relevance"]
    for index in range(4):
        candidate = sections[index] if index < len(sections) and isinstance(sections[index], dict) else {}
        heading = clip_words(str(candidate.get("heading") or fallback_headings[index]).strip(), 8)
        body = clip_words(str(candidate.get("body") or "").strip(), 150)
        if not body:
            body = clip_words((prompt_config.get("facts_to_confirm") or prompt_config.get("project_focus") or project_title).strip(), 120)
        normalized_sections.append({"heading": heading, "body": body})
    letter = {
        "title": clip_words(str(raw.get("title") or "Recommendation Letter").strip(), 12),
        "date_line": str(raw.get("date_line") or "Date: __________").strip() or "Date: __________",
        "addressee_line": clip_words(str(raw.get("addressee_line") or "U.S. Citizenship and Immigration Services").strip(), 12),
        "re_line": clip_words(str(raw.get("re_line") or f"Re: Recommendation for {member_name}").strip(), 18),
        "salutation": str(raw.get("salutation") or "Dear Officer:").strip() or "Dear Officer:",
        "opening_paragraph": clip_words(str(raw.get("opening_paragraph") or "").strip(), 120),
        "sections": normalized_sections,
        "closing_paragraph": clip_words(str(raw.get("closing_paragraph") or "").strip(), 90),
        "signature_line": str(raw.get("signature_line") or prompt_config.get("recommender_name") or "Recommender Name").strip(),
        "selected_project_title": project_title,
        "letter_kind": prompt_config.get("letter_kind", "independent"),
    }
    if not letter["opening_paragraph"]:
        letter["opening_paragraph"] = clip_words(f"I am pleased to provide this recommendation in support of {member_name}, with specific focus on {project_title}.", 120)
    if not letter["closing_paragraph"]:
        letter["closing_paragraph"] = f"I respectfully offer this letter for consideration with {member_name}'s petition record."
    letter["plain_text"] = render_recommendation_letter_text(letter)
    letter["estimated_word_count"] = word_count(letter["plain_text"])
    letter["estimated_page_count"] = max(1, (letter["estimated_word_count"] + 449) // 450)
    return letter


def render_recommendation_letter_text(letter: dict) -> str:
    parts = [
        letter.get("title", ""),
        letter.get("date_line", ""),
        letter.get("addressee_line", ""),
        letter.get("re_line", ""),
        letter.get("salutation", ""),
        letter.get("opening_paragraph", ""),
    ]
    for section in letter.get("sections", []):
        if section.get("heading"):
            parts.append(section.get("heading", ""))
        parts.append(section.get("body", ""))
    parts.extend([letter.get("closing_paragraph", ""), letter.get("signature_line", "")])
    return "\n\n".join(part.strip() for part in parts if str(part).strip())


def clip_words(text: str, max_words: int) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return " ".join(words).strip()
    clipped = " ".join(words[:max_words]).rstrip(" ,;:")
    return f"{clipped}."


def word_count(text: str) -> int:
    return len(str(text or "").split())


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
    lower_name = file_name.lower()
    if lower_name.endswith(".docx"):
        excerpt = extract_docx_text(file_bytes)
        if excerpt:
            return excerpt[:18000]
    if content_type == "application/pdf" or lower_name.endswith(".pdf"):
        excerpt = extract_pdf_text(file_bytes)
        if excerpt:
            return excerpt[:18000]
    if content_type.startswith("text/") or file_name.lower().endswith((".txt", ".md", ".csv", ".json")):
        return file_bytes[:18000].decode("utf-8", errors="replace")
    decoded = file_bytes[:18000].decode("utf-8", errors="ignore")
    if decoded.strip():
        return decoded
    return "Document text could not be extracted automatically. Use filename, content type, and member context."


def extract_docx_text(file_bytes: bytes) -> str:
    try:
        with zipfile.ZipFile(io_bytes(file_bytes)) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespaces):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespaces)]
        combined = "".join(texts).strip()
        if combined:
            paragraphs.append(combined)
    return "\n".join(paragraphs)


def extract_pdf_text(file_bytes: bytes) -> str:
    extracted = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", file_bytes, re.S):
        stream = match.group(1)
        for candidate in (stream, try_inflate(stream)):
            if not candidate:
                continue
            text = decode_pdf_text_fragments(candidate)
            if text:
                extracted.append(text)
        if len(" ".join(extracted)) > 18000:
            break
    return "\n".join(extracted)[:18000]


def try_inflate(stream: bytes) -> bytes:
    try:
        return zlib.decompress(stream)
    except zlib.error:
        return b""


def decode_pdf_text_fragments(stream: bytes) -> str:
    fragments = []
    for raw in re.findall(rb"\((.*?)\)", stream, re.S):
        cleaned = raw.replace(rb"\\(", b"(").replace(rb"\\)", b")").replace(rb"\\n", b" ").replace(rb"\\r", b" ")
        text = cleaned.decode("latin-1", errors="ignore")
        text = re.sub(r"\s+", " ", text).strip()
        if text and any(ch.isalnum() for ch in text):
            fragments.append(text)
    return "\n".join(fragments[:120])


def io_bytes(file_bytes: bytes):
    from io import BytesIO
    return BytesIO(file_bytes)


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
    description = clean_evidence_description(raw.get("ai_description") or member_context or "Evidence uploaded for Ascend review.")
    return {
        "criterion_code": criterion["code"],
        "criterion_name": criterion["name"],
        "document_type": document_type,
        "title": title[:160],
        "ai_description": description,
        "quality_score": int(raw.get("quality_score") or 50),
        "confidence": int(raw.get("confidence") or 50),
    }


def clean_evidence_description(value: str) -> str:
    description = str(value or "").strip()
    description = re.sub(r"^(?:evidence|document|file)\s*[:\-]\s*", "", description, flags=re.IGNORECASE).strip()
    description = re.sub(r"^evidence\s+", "", description, flags=re.IGNORECASE).strip()
    return description or "Evidence uploaded for Ascend review."


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

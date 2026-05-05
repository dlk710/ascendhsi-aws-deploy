import unittest
from unittest.mock import patch
import urllib.error
import json

from app.openai_client import OpenAIService, fallback_portal_assistant, fallback_support_ticket


class OpenAIServiceTests(unittest.TestCase):
    def test_disabled_without_api_key(self):
        service = OpenAIService({"enabled": True, "api_key_env": "OPENAI_API_KEY"})
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(service.enabled)

    def test_enabled_with_configured_api_key(self):
        service = OpenAIService({"enabled": True, "api_key_env": "OPENAI_API_KEY", "api_key": "test-key"})
        with patch.dict("os.environ", {}, clear=True):
            self.assertTrue(service.enabled)
            self.assertEqual(service.api_key(), "test-key")

    def test_environment_key_overrides_configured_key(self):
        service = OpenAIService({"enabled": True, "api_key_env": "OPENAI_API_KEY", "api_key": "config-key"})
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}, clear=True):
            self.assertEqual(service.api_key(), "env-key")

    def test_summary_falls_back_when_disabled(self):
        service = OpenAIService({"enabled": False, "api_key_env": "OPENAI_API_KEY"})
        summary, score = service.summarize_upload("Reviewer Invite", "judging")
        self.assertIn("AI is unavailable", summary)
        self.assertEqual(score, 45)

    def test_analyze_evidence_falls_back_when_disabled(self):
        service = OpenAIService({"enabled": False, "api_key_env": "OPENAI_API_KEY"})
        result = service.analyze_evidence_upload(
            "This is an invitation to review technical papers.",
            "reviewer-invite.txt",
            "text/plain",
            b"Please review this manuscript for our conference.",
        )
        self.assertEqual(result["criterion_code"], "judging")
        self.assertIn("Judging", result["criterion_name"])
        self.assertTrue(result["ai_description"])

    def test_analyze_evidence_uses_other_when_unmatched(self):
        service = OpenAIService({"enabled": False, "api_key_env": "OPENAI_API_KEY"})
        result = service.analyze_evidence_upload(
            "This is a general planning note.",
            "personal-note.txt",
            "text/plain",
            b"Buy office supplies and update the meeting agenda.",
        )
        self.assertEqual(result["criterion_code"], "other")
        self.assertEqual(result["criterion_name"], "Other")

    def test_petition_generator_falls_back_when_disabled(self):
        service = OpenAIService({"enabled": False, "api_key_env": "OPENAI_API_KEY"})
        result = service.generate_petition_package({
            "member_name": "Vas",
            "profile": {"current_title": "Scientist"},
            "criteria_summary": [{"code": "judging", "name": "Judging", "evidence_count": 2}, {"code": "awards", "name": "Awards and Prizes", "evidence_count": 0}],
            "evidence_files": [{"title": "Reviewer invitation", "criterion_name": "Judging"}],
            "tasks": [{"title": "Upload award certificate", "status": "open"}],
            "planner_items": [],
            "recent_messages": [],
        })
        self.assertTrue(result["executive_summary"])
        self.assertTrue(result["clarification_questions"])

    def test_analyze_evidence_falls_back_on_rate_limit(self):
        service = OpenAIService({"enabled": True, "api_key": "test-key", "timeout_seconds": 1})
        error = urllib.error.HTTPError(
            url="https://api.openai.com/v1/responses",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        with patch("urllib.request.urlopen", side_effect=error):
            result = service.analyze_evidence_upload(
                "This is an invitation to review technical papers.",
                "reviewer-invite.txt",
                "text/plain",
                b"Please review this manuscript.",
            )
        self.assertEqual(result["criterion_code"], "judging")
        self.assertTrue(result["ai_description"])

    def test_portal_assistant_fallback_returns_references(self):
        result = fallback_portal_assistant({
            "actor_role": "attorney",
            "question": "Which stored evidence should I review first?",
            "detail_requested": False,
            "context": {
                "member": {"display_name": "Vas"},
                "metrics": {"readiness_score": 62, "evidence_count": 3, "open_tasks": 2},
                "strengths": ["Judging (2)"],
                "gaps": ["Awards and Prizes"],
                "next_steps": ["review the judging evidence for stronger official corroboration"],
            },
            "references": [
                {"id": "ref_1", "label": "reviewer-invite.pdf", "location": "Judging/Invitations", "summary": "Reviewer invitation from conference"},
                {"id": "ref_2", "label": "award-certificate.pdf", "location": "Awards/Certificates", "summary": "Award certificate draft"},
            ],
        })
        self.assertIn("best match", result["summary"].lower())
        self.assertTrue(result["references"])
        self.assertIn("Storage-backed references", result["detailed_answer"])
        self.assertEqual(result["response_mode"], "summary")
        self.assertTrue(result["detail_prompt"])

    def test_portal_assistant_uses_openai_endpoint_when_enabled(self):
        service = OpenAIService({"enabled": True, "api_key": "test-key", "timeout_seconds": 1})

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                payload = {
                    "output_text": json.dumps({
                        "summary": "Short answer",
                        "detailed_answer": "Longer answer with references.",
                        "detail_prompt": "Ask for the detailed answer with storage-backed references.",
                        "suggested_follow_up": "Ask which file should be reviewed first.",
                        "needs_more_detail": True,
                        "response_mode": "summary",
                        "reference_ids": ["ref_1"],
                    })
                }
                return json.dumps(payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            result = service.answer_portal_question({
                "actor_role": "attorney",
                "question": "What should I focus on next?",
                "detail_requested": False,
                "thread": [{"role": "user", "content": "Give me the quick summary first."}],
                "context": {
                    "member": {"display_name": "Vas"},
                    "retrieved_documents": [
                        {"file_name": "reviewer-invite.txt", "excerpt": "Reviewer invitation excerpt for the matched judging evidence."}
                    ],
                },
                "references": [{"id": "ref_1", "label": "reviewer-invite.txt", "location": "Judging", "url": "file:///tmp/reviewer-invite.txt"}],
            })

        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertIn("Reviewer invitation excerpt", request.data.decode("utf-8"))
        self.assertEqual(result["source"], "openai")
        self.assertEqual(result["response_mode"], "summary")
        self.assertEqual(result["references"][0]["label"], "reviewer-invite.txt")
        self.assertIn("detailed answer", result["detail_prompt"].lower())

    def test_support_ticket_fallback_triage(self):
        result = fallback_support_ticket({
            "portal": "Attorney Portal",
            "issue_location": "Attorney Portal / Evidence Review / Omar Hassan",
            "short_description": "Uploaded evidence is not visible",
            "details": "The file appears in the member portal but not in the attorney portal.",
            "current_url": "http://127.0.0.1:3001/",
            "priority": "high",
            "is_blocking": True,
            "attachments": [{"file_name": "issue.png", "description": "Attorney portal evidence list missing Omar upload"}],
        })
        self.assertEqual(result["category"], "data_sync")
        self.assertEqual(result["behavior_assessment"], "likely_bug")
        self.assertTrue(result["next_actions"])
        self.assertIn("blocking", result["user_summary"].lower())
        self.assertIn("high", result["admin_summary"].lower())

    def test_support_ticket_uses_openai_endpoint_when_enabled(self):
        service = OpenAIService({"enabled": True, "api_key": "test-key", "timeout_seconds": 1})

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                payload = {
                    "output_text": json.dumps({
                        "category": "ui",
                        "behavior_assessment": "likely_bug",
                        "user_summary": "Ticket received.",
                        "admin_summary": "Likely frontend issue in the builder portal.",
                        "reasoning": "The report points to a rendering problem after the click flow.",
                        "root_cause": "A portal-specific UI state likely failed to refresh.",
                        "next_actions": ["Reproduce in the builder portal", "Check the related frontend state update"],
                    })
                }
                return json.dumps(payload).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            result = service.triage_support_ticket({
                "portal": "Profile Builder Portal",
                "issue_location": "Profile Builder Portal / Assigned Members",
                "short_description": "Member card does not refresh",
                "details": "After saving a task, the member card still shows stale counts.",
            })

        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
        self.assertIn("Assigned Members", request.data.decode("utf-8"))
        self.assertEqual(result["source"], "openai")
        self.assertEqual(result["category"], "ui")
        self.assertEqual(result["behavior_assessment"], "likely_bug")
        self.assertTrue(result["next_actions"])


if __name__ == "__main__":
    unittest.main()

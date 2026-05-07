import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.config import AppConfig
from app.services import EvidenceService


class PortalAssistantServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.config = AppConfig(
            app_name="test",
            database_path=root / "db.sqlite",
            upload_root=root / "uploads",
            drive_mirror_root=root / "drive",
            default_client={"client_id": "client_1", "case_id": "case_1", "display_name": "Vas"},
        )
        patches = [
            patch("app.services.load_app_config", return_value=self.config),
            patch("app.services.load_storage_config", return_value={"enabled": False, "provider": "s3", "bucket_env": "ASCEND_STORAGE_BUCKET"}),
            patch("app.services.load_openai_config", return_value={"enabled": False}),
        ]
        self.patchers = patches
        for patcher in self.patchers:
            patcher.start()
        self.service = EvidenceService()

    def tearDown(self):
        self.service.conn.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def test_builder_assistant_reply_uses_selected_member_context(self):
        result = self.service.portal_assistant_reply(
            "builder",
            "What should I focus on next for this member?",
            client_id="client_1",
            thread=[{"role": "user", "content": "Start with the biggest gap."}],
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["assistant_name"], "Ascend Navigator")
        self.assertEqual(result["member"]["client_id"], "client_1")
        self.assertTrue(result["summary"])
        self.assertEqual(result["response_mode"], "summary")
        self.assertTrue(result["detail_prompt"])

    def test_assistant_blocks_out_of_scope_general_questions_before_model_call(self):
        self.service.openai.answer_portal_question = Mock(return_value={"summary": "Should not be called"})

        result = self.service.portal_assistant_reply(
            "builder",
            "What is the weather in Paris today?",
            client_id="client_1",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["source"], "guardrail")
        self.assertIn("Ascend Product Suite", result["summary"])
        self.service.openai.answer_portal_question.assert_not_called()

    def test_attorney_assistant_reply_returns_storage_references(self):
        result = self.service.portal_assistant_reply(
            "attorney",
            "Which stored evidence should I review first?",
            client_id="client_1",
            actor_email="attorney@ascendhsi.com",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["member"]["client_id"], "client_1")
        self.assertTrue(result["summary"])
        self.assertIn("match", result["summary"].lower())
        self.assertIsInstance(result["references"], list)
        self.assertTrue(result["detail_prompt"])

    def test_decorate_file_prefers_s3_open_url(self):
        sample = self.config.upload_root / "clients" / "client_1" / "cases" / "case_1" / "evidence" / "awards" / "ev_1" / "original" / "sample.txt"
        sample.parent.mkdir(parents=True, exist_ok=True)
        sample.write_text("sample evidence", encoding="utf-8")
        storage = Mock()
        storage.enabled = True
        storage.ensure_folder_path.return_value = "active/clients/client_1/cases/case_1/evidence/awards/ev_1/original"
        storage.upload_file.return_value = {"id": "active/clients/client_1/sample.txt", "webViewLink": "https://signed.example.com/sample.txt"}
        self.service.storage.object_storage = storage
        record = {
            "id": "ev_1",
            "client_id": "client_1",
            "case_id": "case_1",
            "criterion_code": "awards",
            "file_name": "sample.txt",
            "document_type": "Other",
            "description": "",
            "local_path": str(sample),
            "drive_path": str(sample),
            "drive_mirror_path": str(sample),
            "drive_file_id": "",
            "drive_web_url": "",
            "folder_id": "",
        }
        decorated = self.service._decorate_file(record, [])
        self.assertEqual(decorated["open_url"], "https://signed.example.com/sample.txt")
        self.assertEqual(decorated["drive_web_url"], "https://signed.example.com/sample.txt")
        storage.upload_file.assert_called_once()

    def test_assistant_retrieves_best_matching_uploaded_document(self):
        self.config.upload_root.mkdir(parents=True, exist_ok=True)
        awards_file = self.config.upload_root / "award-letter.txt"
        awards_file.write_text("This award letter confirms national recognition and selection for the innovation prize.", encoding="utf-8")
        judging_file = self.config.upload_root / "review-note.txt"
        judging_file.write_text("This note is about peer review service for a conference panel.", encoding="utf-8")
        self.service.conn.execute(
            """
            INSERT INTO evidence_items(
              id, client_id, case_id, criterion_code, document_type, title, description, file_name, content_type,
              local_path, drive_mirror_path, status, ai_summary, quality_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
            """,
            (
                "ev_award",
                "client_1",
                "case_1",
                "awards",
                "Award Letter",
                "Innovation prize letter",
                "",
                "award-letter.txt",
                "text/plain",
                str(awards_file),
                str(awards_file),
                "Award recognition evidence.",
                80,
            ),
        )
        self.service.conn.execute(
            """
            INSERT INTO evidence_items(
              id, client_id, case_id, criterion_code, document_type, title, description, file_name, content_type,
              local_path, drive_mirror_path, status, ai_summary, quality_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
            """,
            (
                "ev_judging",
                "client_1",
                "case_1",
                "judging",
                "Review Note",
                "Conference review note",
                "",
                "review-note.txt",
                "text/plain",
                str(judging_file),
                str(judging_file),
                "Judging support evidence.",
                75,
            ),
        )
        self.service.conn.commit()

        result = self.service.portal_assistant_reply(
            "builder",
            "Which award document best supports this member's recognition?",
            client_id="client_1",
        )

        self.assertTrue(result["references"])
        self.assertEqual(result["references"][0]["label"], "award-letter.txt")
        self.assertIn("award", result["references"][0]["excerpt"].lower())


if __name__ == "__main__":
    unittest.main()

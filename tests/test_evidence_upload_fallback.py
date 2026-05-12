import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.config import AppConfig
from app.google_drive import GoogleDriveConfigError
from app.services import EvidenceService


class EvidenceUploadFallbackTests(unittest.TestCase):
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
        self.patchers = [
            patch("app.services.load_app_config", return_value=self.config),
            patch("app.services.load_google_drive_config", return_value={"enabled": True, "folder_id": "folder", "folder_url": "url", "mode": "local_drive_mirror"}),
            patch("app.services.load_openai_config", return_value={"enabled": False}),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.service = EvidenceService()

    def tearDown(self):
        self.service.conn.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def test_member_upload_falls_back_to_local_mirror_when_remote_drive_is_unavailable(self):
        drive = Mock()
        drive.enabled = True
        drive.ensure_folder_path.side_effect = GoogleDriveConfigError("Google Drive token missing")
        self.service.storage.google_drive = drive

        uploaded = self.service.upload_evidence(
            criterion_code="judging",
            document_type="Invitation",
            title="Reviewer Invitation",
            description="Fabricated upload for local fallback testing.",
            file_name="reviewer-invitation.txt",
            content_type="text/plain",
            file_bytes=b"fabricated evidence",
            ai_summary="Uploaded with fallback storage.",
            quality_score=88,
        )

        record = self.service.conn.execute(
            "SELECT local_path, drive_mirror_path, drive_path FROM evidence_items WHERE id = ?",
            (uploaded["evidence_id"],),
        ).fetchone()
        event = self.service.conn.execute(
            "SELECT status FROM operational_events WHERE event_type = 'evidence_storage_fallback'",
        ).fetchone()

        self.assertEqual(uploaded["status"], "success")
        self.assertTrue(Path(record["local_path"]).exists())
        self.assertTrue(Path(record["drive_mirror_path"]).exists())
        self.assertEqual(record["drive_mirror_path"], record["drive_path"])
        self.assertEqual(event["status"], "fallback")


if __name__ == "__main__":
    unittest.main()

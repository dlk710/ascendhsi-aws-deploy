import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.storage import EvidenceStorage, safe_file_name


class StorageTests(unittest.TestCase):
    def test_safe_file_name(self):
        self.assertEqual(safe_file_name("IEEE Reviewer Invite!.pdf"), "IEEE-Reviewer-Invite-.pdf")

    def test_store_mirrors_file_by_client_case_and_criterion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text("hello", encoding="utf-8")
            storage = EvidenceStorage(root / "uploads", root / "drive")
            stored = storage.store("client_1", "case_1", "judging", "review.txt", source)
            self.assertTrue(Path(stored.local_path).exists())
            self.assertTrue(Path(stored.drive_path).exists())
            self.assertIn("clients/client_1/cases/case_1/evidence/judging", stored.local_path)
            self.assertEqual(Path(stored.local_path).read_text(encoding="utf-8"), "hello")

    def test_store_uses_google_drive_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text("hello", encoding="utf-8")
            drive = Mock()
            drive.enabled = True
            drive.ensure_folder_path.return_value = "folder-id"
            drive.upload_file.return_value = {"id": "drive-file-id", "webViewLink": "https://drive/file"}
            storage = EvidenceStorage(root / "uploads", root / "drive", drive)
            stored = storage.store("client_1", "case_1", "judging", "review.txt", source)
            drive.ensure_folder_path.assert_called_once()
            drive.upload_file.assert_called_once()
            self.assertEqual(stored.local_path, "")
            self.assertEqual(stored.drive_file_id, "drive-file-id")
            self.assertIn("clients/client_1/cases/case_1/evidence/judging", stored.drive_path)


if __name__ == "__main__":
    unittest.main()

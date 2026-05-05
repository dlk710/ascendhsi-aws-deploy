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

    def test_store_uses_s3_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            source.write_text("hello", encoding="utf-8")
            object_storage = Mock()
            object_storage.enabled = True
            object_storage.ensure_folder_path.return_value = "active/clients/client_1/cases/case_1/evidence/judging/ev_1/original"
            object_storage.upload_file.return_value = {"id": "active/clients/client_1/cases/case_1/evidence/judging/review.txt", "webViewLink": "https://signed.example.com/review.txt"}
            storage = EvidenceStorage(root / "uploads", root / "drive", object_storage)
            stored = storage.store("client_1", "case_1", "judging", "review.txt", source)
            object_storage.ensure_folder_path.assert_called_once()
            object_storage.upload_file.assert_called_once()
            self.assertEqual(stored.local_path, "")
            self.assertEqual(stored.drive_file_id, "active/clients/client_1/cases/case_1/evidence/judging/review.txt")
            self.assertIn("clients/client_1/cases/case_1/evidence/judging", stored.drive_path)


if __name__ == "__main__":
    unittest.main()

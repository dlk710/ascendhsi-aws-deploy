import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.storage import EvidenceStorage, S3StorageClient, safe_file_name


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

    def test_evidence_s3_client_reads_aws_storage_env_aliases(self):
        env = {
            "ASCEND_STORAGE_BUCKET": "ascend-dev-storage",
            "ASCEND_ARCHIVE_BUCKET": "ascend-dev-archive",
            "ASCEND_S3_SERVER_SIDE_ENCRYPTION": "AES256",
            "AWS_REGION": "us-east-2",
        }
        with patch.dict("os.environ", env, clear=True):
            client = S3StorageClient()
        self.assertTrue(client.enabled)
        self.assertEqual(client.bucket, "ascend-dev-storage")
        self.assertEqual(client.archive_bucket, "ascend-dev-archive")
        self.assertEqual(client.region, "us-east-2")
        self.assertEqual(client.archive_uri("s3://ascend-dev-storage/clients/client_1/file.pdf"), "s3://ascend-dev-archive/archive/clients/client_1/file.pdf")


if __name__ == "__main__":
    unittest.main()

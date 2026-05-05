import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.s3_storage import S3ConfigError, S3StorageClient, S3StorageError


class S3StorageClientTests(unittest.TestCase):
    def test_requires_bucket_when_enabled(self):
        client = S3StorageClient({"enabled": True, "bucket_env": "ASCEND_STORAGE_BUCKET"})
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(S3ConfigError):
                client.require_bucket()

    def test_reads_bucket_from_environment(self):
        client = S3StorageClient({"enabled": True, "bucket_env": "ASCEND_STORAGE_BUCKET"})
        with patch.dict("os.environ", {"ASCEND_STORAGE_BUCKET": "ascend-active"}, clear=True):
            self.assertEqual(client.require_bucket(), "ascend-active")

    def test_builds_presigned_url_through_sdk_client(self):
        mock_sdk = Mock()
        mock_sdk.generate_presigned_url.return_value = "https://signed.example.com/file.txt"
        client = S3StorageClient({"enabled": True, "bucket": "ascend-active"})
        client._client = mock_sdk
        self.assertEqual(client.build_file_url("active/clients/file.txt"), "https://signed.example.com/file.txt")

    def test_move_file_to_folder_copies_then_deletes(self):
        mock_sdk = Mock()
        client = S3StorageClient(
            {
                "enabled": True,
                "bucket": "ascend-active",
                "archive_bucket": "ascend-archive",
                "key_prefix": "active",
                "archive_prefix": "archive",
                "archive_storage_class": "GLACIER_IR",
            }
        )
        client._client = mock_sdk
        with patch.object(client, "build_file_url", return_value="https://signed.example.com/archive.txt"):
            moved = client.move_file_to_folder("active/clients/client_1/file.txt", "archive/clients/client_1")
        self.assertEqual(moved["bucket"], "ascend-archive")
        self.assertEqual(moved["storageClass"], "GLACIER_IR")
        mock_sdk.copy_object.assert_called_once()
        mock_sdk.delete_object.assert_called_once()

    def test_healthcheck_wraps_sdk_errors(self):
        mock_sdk = Mock()
        mock_sdk.head_bucket.side_effect = RuntimeError("boom")
        client = S3StorageClient({"enabled": True, "bucket": "ascend-active"})
        client._client = mock_sdk
        with self.assertRaises(S3StorageError):
            client.healthcheck()


if __name__ == "__main__":
    unittest.main()

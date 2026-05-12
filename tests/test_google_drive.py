import unittest
from unittest.mock import patch
import urllib.error

from app.google_drive import GoogleDriveClient, GoogleDriveConfigError, GoogleDriveUploadError


class GoogleDriveClientTests(unittest.TestCase):
    def test_requires_access_token_when_enabled(self):
        client = GoogleDriveClient({"enabled": True, "access_token_env": "GOOGLE_DRIVE_ACCESS_TOKEN"})
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(GoogleDriveConfigError):
                client.require_token()

    def test_reads_access_token_from_configured_env(self):
        client = GoogleDriveClient({"enabled": True, "access_token_env": "GOOGLE_DRIVE_ACCESS_TOKEN"})
        with patch.dict("os.environ", {"GOOGLE_DRIVE_ACCESS_TOKEN": "token"}, clear=True):
            self.assertEqual(client.require_token(), "token")

    def test_request_json_wraps_http_errors(self):
        client = GoogleDriveClient({"enabled": True, "access_token_env": "GOOGLE_DRIVE_ACCESS_TOKEN"})
        error = urllib.error.HTTPError(
            url="https://example.com",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=None,
        )
        error.fp = type("FakeFp", (), {"read": lambda self: b"forbidden"})()
        with patch.dict("os.environ", {"GOOGLE_DRIVE_ACCESS_TOKEN": "token"}, clear=True), \
             patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(GoogleDriveUploadError):
                client.request_json("GET", "https://example.com")

    def test_move_file_to_folder_removes_existing_parent(self):
        client = GoogleDriveClient({"enabled": True, "access_token_env": "GOOGLE_DRIVE_ACCESS_TOKEN"})
        with patch.object(client, "get_file_parents", return_value=["old_parent"]), \
             patch.object(client, "request_json", return_value={"id": "file_1", "parents": ["archive_parent"]}) as request_json:
            moved = client.move_file_to_folder("file_1", "archive_parent")

        self.assertEqual(moved["parents"], ["archive_parent"])
        method, url, payload = request_json.call_args.args
        self.assertEqual(method, "PATCH")
        self.assertEqual(payload, {})
        self.assertIn("addParents=archive_parent", url)
        self.assertIn("removeParents=old_parent", url)


if __name__ == "__main__":
    unittest.main()

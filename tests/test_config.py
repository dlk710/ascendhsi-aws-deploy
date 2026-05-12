import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import load_app_config, load_google_drive_config, load_openai_config


class ConfigTests(unittest.TestCase):
    def test_app_config_loads_default_client(self):
        config = load_app_config()
        self.assertEqual(config.default_client["display_name"], "Vas")
        self.assertTrue(str(config.database_path).endswith("data/db/ascend_suite.sqlite"))

    def test_app_config_respects_runtime_path_overrides(self):
        env = {
            "ASCEND_DATABASE_PATH": "/tmp/ascend/ascend.sqlite",
            "ASCEND_UPLOAD_ROOT": "/tmp/ascend/uploads",
            "ASCEND_MIRROR_ROOT": "/tmp/ascend/mirror",
        }
        with patch.dict("os.environ", env, clear=True):
            config = load_app_config()
        self.assertEqual(config.database_path, Path("/tmp/ascend/ascend.sqlite"))
        self.assertEqual(config.upload_root, Path("/tmp/ascend/uploads"))
        self.assertEqual(config.drive_mirror_root, Path("/tmp/ascend/mirror"))

    def test_google_drive_folder_is_configured(self):
        config = load_google_drive_config()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["folder_id"], "1Qmv1b5BetW2UvF3jxOtx4WzQO3_fSIV9")
        self.assertIn("drive.google.com", config["folder_url"])
        self.assertEqual(config["access_token_env"], "GOOGLE_DRIVE_ACCESS_TOKEN")

    def test_openai_config_is_separate_and_enabled(self):
        config = load_openai_config()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["user"], "ascend-local")
        self.assertEqual(config["api_key"], "")
        self.assertEqual(config["api_key_env"], "OPENAI_API_KEY")


if __name__ == "__main__":
    unittest.main()

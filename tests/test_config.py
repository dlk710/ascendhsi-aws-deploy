import unittest

from app.config import load_app_config, load_google_drive_config, load_openai_config


class ConfigTests(unittest.TestCase):
    def test_app_config_loads_default_client(self):
        config = load_app_config()
        self.assertEqual(config.default_client["display_name"], "Vas")
        self.assertTrue(str(config.database_path).endswith("data/db/ascend_suite.sqlite"))

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

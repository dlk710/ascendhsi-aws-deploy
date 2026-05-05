import os
import unittest
from unittest.mock import patch

from app.config import load_app_config, load_openai_config, load_storage_config


class ConfigTests(unittest.TestCase):
    def test_app_config_loads_default_client(self):
        config = load_app_config()
        self.assertEqual(config.default_client["display_name"], "Vas")
        self.assertTrue(str(config.database_path).endswith("data/db/ascend_suite.sqlite"))
        self.assertEqual(config.database_backend, "sqlite")

    def test_app_config_switches_to_database_url(self):
        with patch.dict(os.environ, {"ASCEND_DATABASE_URL": "postgresql://ascend:pw@db.internal:5432/ascend"}, clear=False):
            config = load_app_config()
        self.assertEqual(config.database_url, "postgresql://ascend:pw@db.internal:5432/ascend")
        self.assertEqual(config.database_backend, "postgresql")

    def test_storage_config_is_s3_ready(self):
        config = load_storage_config()
        self.assertEqual(config["provider"], "s3")
        self.assertEqual(config["bucket_env"], "ASCEND_STORAGE_BUCKET")
        self.assertEqual(config["archive_bucket_env"], "ASCEND_ARCHIVE_BUCKET")
        self.assertEqual(config["archive_storage_class"], "GLACIER_IR")

    def test_openai_config_is_separate_and_enabled(self):
        config = load_openai_config()
        self.assertTrue(config["enabled"])
        self.assertEqual(config["user"], "ascend-local")
        self.assertEqual(config["api_key"], "")
        self.assertEqual(config["api_key_env"], "OPENAI_API_KEY")


if __name__ == "__main__":
    unittest.main()

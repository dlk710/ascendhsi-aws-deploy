import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import EvidenceService


class RoadmapServiceTests(unittest.TestCase):
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
            patch("app.services.load_storage_config", return_value={"enabled": False, "provider": "s3", "bucket_env": "ASCEND_STORAGE_BUCKET"}),
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

    def test_member_dashboard_includes_eb1a_command_center(self):
        dashboard = self.service.member_dashboard()
        command_center = dashboard["case_command_center"]

        self.assertEqual(len(command_center["criterion_tracker"]), 10)
        self.assertTrue(command_center["timeline"])
        self.assertTrue(any(item["optional"] for item in command_center["timeline"]))
        self.assertTrue(command_center["onboarding"])
        self.assertIn("profile_actions", command_center)

    def test_builder_detail_includes_builder_and_legal_workbenches(self):
        detail = self.service.builder_member_detail("client_1")

        self.assertIn("builder_workbench", detail)
        self.assertTrue(detail["builder_workbench"]["narrative_queue"])
        self.assertTrue(detail["builder_workbench"]["evidence_request_queue"])
        self.assertIn("legal_workbench", detail)
        self.assertTrue(detail["legal_workbench"]["pre_filing_checklist"])
        self.assertTrue(detail["legal_workbench"]["recommendation_letters"]["project_options"])

    def test_leader_dashboard_includes_performance_and_revenue_rollups(self):
        dashboard = self.service.leader_dashboard()

        self.assertIn("attorney_performance", dashboard)
        self.assertIn("revenue_analytics", dashboard)
        self.assertTrue(dashboard["revenue_analytics"]["rows"])
        self.assertIn("Planning estimate", dashboard["revenue_analytics"]["assumption"])

    def test_admin_dashboard_includes_product_ops_controls(self):
        dashboard = self.service.admin_operational_dashboard()

        self.assertIn("user_management", dashboard)
        self.assertIn("product_ops", dashboard)
        self.assertTrue(dashboard["product_ops"]["readiness_rows"])
        self.assertIn("audit_log", dashboard)


if __name__ == "__main__":
    unittest.main()

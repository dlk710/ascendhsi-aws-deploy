import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import EvidenceService


class IssueLogServiceTests(unittest.TestCase):
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
            patch("app.services.load_google_drive_config", return_value={"folder_id": "folder", "folder_url": "url", "mode": "test"}),
            patch("app.services.load_openai_config", return_value={"enabled": False, "timeout_seconds": 5}),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.service = EvidenceService()

    def tearDown(self):
        self.service.conn.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def test_create_issue_log_assigns_bug_id_and_persists_sync_metadata(self):
        with patch.object(self.service, "_sync_issue_log_to_aws", return_value={
            "aws_table_name": "ascend_product_issue_logs",
            "aws_sync_status": "synced",
            "aws_sync_message": "Mirrored to DynamoDB.",
            "last_synced_at": "2026-05-06 16:30:00",
        }):
            created = self.service.create_issue_log(
                actor_email="admin@ascendhsi.com",
                title="Cost Explorer AWS gap",
                portal="Admin Portal",
                section="Cost Explorer",
                priority="P1",
                status="open",
                description="AWS costs do not load in the admin portal.",
                reported_by="Maya Thompson",
            )

        self.assertTrue(created["bug_id"].startswith("BUG-"))
        self.assertEqual(created["portal"], "Admin Portal")
        self.assertEqual(created["aws_sync_status"], "synced")
        backlog = self.service.issue_log_backlog()
        self.assertEqual(backlog["priority_counts"]["P1"], 1)
        self.assertEqual(backlog["status_counts"]["open"], 1)

    def test_update_issue_log_can_close_bug_and_refresh_sync_metadata(self):
        with patch.object(self.service, "_sync_issue_log_to_aws", return_value={
            "aws_table_name": "ascend_product_issue_logs",
            "aws_sync_status": "synced",
            "aws_sync_message": "Mirrored to DynamoDB.",
            "last_synced_at": "2026-05-06 16:30:00",
        }):
            created = self.service.create_issue_log(
                actor_email="admin@ascendhsi.com",
                title="Message thread issue",
                portal="Admin Portal",
                section="Messages",
                priority="P2",
                status="open",
                description="Thread detail view is misaligned.",
                reported_by="Maya Thompson",
            )
            updated = self.service.update_issue_log(created["bug_id"], priority="P0", status="closed", actor_email="admin@ascendhsi.com")

        self.assertEqual(updated["priority"], "P0")
        self.assertEqual(updated["status"], "closed")
        self.assertTrue(updated["closed_at"])
        backlog = self.service.issue_log_backlog()
        self.assertEqual(backlog["priority_counts"]["P0"], 1)
        self.assertEqual(backlog["status_counts"]["closed"], 1)

    def test_remove_issue_log_hides_row_and_mirrors_deleted_timestamp(self):
        sync_payloads = []

        def fake_sync(issue):
            sync_payloads.append(dict(issue))
            return {
                "aws_table_name": "ascend_product_issue_logs",
                "aws_sync_status": "synced",
                "aws_sync_message": "Mirrored to DynamoDB.",
                "last_synced_at": "2026-05-06 16:30:00",
            }

        with patch.object(self.service, "_sync_issue_log_to_aws", side_effect=fake_sync):
            created = self.service.create_issue_log(
                actor_email="admin@ascendhsi.com",
                title="Debug table row issue",
                portal="Admin Portal",
                section="Debug Console",
                priority="P2",
                status="open",
                description="Debug rows need to be removable.",
                reported_by="Maya Thompson",
            )
            removed = self.service.remove_issue_log(created["bug_id"], actor_email="admin@ascendhsi.com")

        self.assertEqual(removed["status"], "removed")
        self.assertTrue(removed["deleted_at"])
        self.assertTrue(sync_payloads[-1]["deleted_at"])
        self.assertEqual(self.service.issue_log_backlog()["items"], [])

    def test_admin_health_reports_aws_stack_components(self):
        dashboard = self.service.admin_operational_dashboard()
        names = {item["name"] for item in dashboard["portal_health"]}
        self.assertIn("CloudFront CDN", names)
        self.assertIn("ECS Fargate", names)
        self.assertIn("RDS PostgreSQL", names)
        self.assertIn("S3 Evidence Buckets", names)
        self.assertIn("DynamoDB Bug Log", names)
        self.assertNotIn("SQLite", names)
        self.assertTrue(all(item.get("layer") for item in dashboard["response_times"]))


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from botocore.exceptions import ClientError

from app.config import AppConfig
from app.db import one, rows
from app.services import EvidenceService


class SupportTicketServiceTests(unittest.TestCase):
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
        patches = [
            patch("app.services.load_app_config", return_value=self.config),
            patch("app.services.load_storage_config", return_value={"enabled": False, "provider": "s3", "bucket_env": "ASCEND_STORAGE_BUCKET"}),
            patch("app.services.load_openai_config", return_value={"enabled": False}),
        ]
        self.patchers = patches
        for patcher in self.patchers:
            patcher.start()
        self.service = EvidenceService()

    def tearDown(self):
        self.service.conn.close()
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def test_member_support_ticket_creates_mailbox_thread(self):
        result = self.service.report_support_ticket(
            "member",
            "Evidence upload looks stuck",
            "The upload spinner never completed after I selected the file.",
            issue_location="Member Portal / Evidence Intake",
            priority="high",
            is_blocking=True,
            current_url="http://127.0.0.1:3001/",
            actor_client_id="client_1",
            attachments=[
                {
                    "file_name": "stuck-upload.png",
                    "content_type": "image/png",
                    "description": "Shows the loading spinner still running.",
                    "file_bytes": b"fake-image",
                }
            ],
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["assistant_name"], "Ascend Beacon")
        self.assertTrue(result["ticket"]["ticket_number"].startswith("ASC-IT-"))
        stored = one(self.service.conn, "SELECT * FROM support_tickets WHERE id = ?", (result["ticket"]["id"],))
        self.assertEqual(stored["short_description"], "Evidence upload looks stuck")
        self.assertEqual(stored["priority"], "high")
        self.assertEqual(stored["is_blocking"], 1)
        self.assertEqual(stored["behavior_assessment"], "likely_bug")
        attachments = rows(self.service.conn, "SELECT * FROM support_ticket_attachments WHERE ticket_id = ?", (result["ticket"]["id"],))
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["file_name"], "stuck-upload.png")
        self.assertTrue(Path(attachments[0]["local_path"]).exists())
        self.assertEqual(result["ticket"]["attachments"][0]["description"], "Shows the loading spinner still running.")
        self.assertTrue(result["ticket"]["attachments"][0]["open_url"].startswith("file://"))
        thread_messages = rows(self.service.conn, "SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at ASC", (result["mailbox_thread_id"],))
        self.assertEqual(len(thread_messages), 2)
        self.assertIn("Likely root cause", thread_messages[0]["body"])
        self.assertIn("Priority: High", thread_messages[0]["body"])
        self.assertIn("Attachments:", thread_messages[0]["body"])
        self.assertIn("opened ticket", thread_messages[1]["body"].lower())

    def test_admin_dashboard_includes_support_summary(self):
        self.service.report_support_ticket(
            "member",
            "Planner row would not save",
            "The save button returned no visible change and the row stayed unsaved.",
            issue_location="Member Portal / Event Planner",
            actor_client_id="client_1",
        )

        dashboard = self.service.admin_operational_dashboard()

        self.assertEqual(dashboard["metrics"]["open_support_tickets"], 1)
        self.assertEqual(dashboard["support_summary"]["open_count"], 1)
        self.assertTrue(dashboard["support_tickets"])
        self.assertIn("ticket_number", dashboard["support_tickets"][0])

    def test_aws_cost_summary_keeps_actuals_when_forecast_unavailable(self):
        class FakeCostExplorerClient:
            def get_cost_and_usage(self, **request):
                if request.get("GroupBy"):
                    return {
                        "ResultsByTime": [
                            {
                                "Groups": [
                                    {
                                        "Keys": ["Amazon Simple Storage Service"],
                                        "Metrics": {"UnblendedCost": {"Amount": "2.50", "Unit": "USD"}},
                                    }
                                ]
                            }
                        ]
                    }
                return {
                    "ResultsByTime": [
                        {"Total": {"UnblendedCost": {"Amount": "1.25", "Unit": "USD"}}},
                        {"Total": {"UnblendedCost": {"Amount": "0.75", "Unit": "USD"}}},
                    ]
                }

            def get_cost_forecast(self, **_request):
                raise ClientError(
                    {"Error": {"Code": "DataUnavailableException", "Message": "Insufficient amount of historical data."}},
                    "GetCostForecast",
                )

        with patch("boto3.client", return_value=FakeCostExplorerClient()):
            summary = self.service._fetch_aws_cost_summary()

        self.assertEqual(summary["status"], "available")
        self.assertIn("Forecast unavailable", summary["detail"])
        self.assertEqual(summary["recurring"][1]["actual"], 2.0)
        self.assertEqual(summary["services"][0]["name"], "Amazon Simple Storage Service")

    def test_aws_cost_summary_preserves_sub_cent_actuals(self):
        class FakeCostExplorerClient:
            def get_cost_and_usage(self, **request):
                if request.get("GroupBy"):
                    return {
                        "ResultsByTime": [
                            {
                                "Groups": [
                                    {
                                        "Keys": ["Amazon Elastic Load Balancing"],
                                        "Metrics": {"UnblendedCost": {"Amount": "0.0042", "Unit": "USD"}},
                                    }
                                ]
                            }
                        ]
                    }
                return {
                    "ResultsByTime": [
                        {
                            "TimePeriod": {"Start": "2026-05-01"},
                            "Total": {"UnblendedCost": {"Amount": "0.0021", "Unit": "USD"}},
                        },
                        {
                            "TimePeriod": {"Start": "2026-05-02"},
                            "Total": {"UnblendedCost": {"Amount": "0.0021", "Unit": "USD"}},
                        },
                    ]
                }

            def get_cost_forecast(self, **_request):
                raise ClientError(
                    {"Error": {"Code": "DataUnavailableException", "Message": "Insufficient amount of historical data."}},
                    "GetCostForecast",
                )

        with patch("boto3.client", return_value=FakeCostExplorerClient()):
            summary = self.service._fetch_aws_cost_summary()

        self.assertEqual(summary["status"], "available")
        self.assertEqual(summary["recurring"][1]["actual"], 0.0042)
        self.assertEqual(summary["services"][0]["amount"], 0.0042)
        self.assertEqual(summary["trend"][0]["amount"], 0.0021)
        self.assertIn("Sub-cent", summary["precision_note"])

    def test_member_support_ticket_requires_description_for_each_attachment(self):
        with self.assertRaisesRegex(ValueError, "description is required for each attachment"):
            self.service.report_support_ticket(
                "member",
                "Evidence upload looks stuck",
                "The upload spinner never completed after I selected the file.",
                issue_location="Member Portal / Evidence Intake",
                actor_client_id="client_1",
                attachments=[
                    {
                        "file_name": "stuck-upload.png",
                        "content_type": "image/png",
                        "description": "   ",
                        "file_bytes": b"fake-image",
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()

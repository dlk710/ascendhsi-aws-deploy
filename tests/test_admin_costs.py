import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from botocore.exceptions import ClientError

from app.config import AppConfig
from app.services import ADMIN_COST_SNAPSHOT_SOURCE, EvidenceService


class AdminCostServiceTests(unittest.TestCase):
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

    def test_admin_cost_dashboard_exposes_local_ai_call_breakdown_without_snapshot(self):
        self.service.record_operational_event("portal_assistant", status="success", portal="builder", endpoint="/api/assistant/reply", message="Builder AI call")
        self.service.record_operational_event("petition_generator", status="fallback", portal="attorney", endpoint="/api/attorney/petition-generator", message="Attorney AI call")
        self.service.conn.execute(
            """
            INSERT INTO support_tickets(
              id, ticket_number, reporter_role, reporter_key, reporter_name, portal,
              short_description, details, triage_source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sup_1", "ASC-IT-TEST-1", "member", "client_1", "Vas", "Member Portal", "Upload issue", "Spinner stayed active", "openai"),
        )
        self.service.conn.commit()

        dashboard = self.service.admin_cost_dashboard()

        self.assertEqual(dashboard["status"], "needs_refresh")
        self.assertEqual(dashboard["openai"]["call_totals"]["total_calls"], 3)
        self.assertTrue(any(item["function"] == "Portal Assistant" for item in dashboard["openai"]["call_breakdown"]))
        self.assertTrue(any(item["function"] == "Support Ticket Triage" for item in dashboard["openai"]["call_breakdown"]))

    def test_refresh_admin_cost_dashboard_persists_snapshot_and_merges_ai_calls(self):
        self.service.record_operational_event("openai_summary", status="success", portal="member", endpoint="/api/evidence", message="Summary call")
        with patch.object(self.service, "_fetch_aws_cost_summary", return_value={
            "status": "available",
            "title": "AWS Cloud Costs",
            "detail": "Refreshed from AWS Cost Explorer.",
            "currency": "USD",
            "recurring": [{"period": "Monthly", "actual": 120.5, "projected": 180.25, "basis": "Month-to-date actual vs projected month-end total."}],
            "services": [{"name": "Amazon S3", "amount": 75.1}],
            "trend": [{"date": "2026-05-01", "amount": 4.2}],
        }), patch.object(self.service, "_fetch_openai_cost_summary", return_value={
            "status": "available",
            "title": "OpenAI Costs",
            "detail": "Refreshed from OpenAI billing.",
            "currency": "USD",
            "recurring": [{"period": "Monthly", "actual": 14.2, "projected": 22.9, "basis": "Month-to-date actual vs current month run rate projection."}],
            "line_items": [{"name": "responses", "amount": 14.2}],
            "trend": [{"date": "2026-05-01", "amount": 0.8}],
            "call_breakdown": [],
            "portal_totals": [],
            "call_totals": {"total_calls": 0, "openai_calls": 0, "fallback_calls": 0, "failed_calls": 0},
        }):
            refreshed = self.service.refresh_admin_cost_dashboard()

        row = self.service.conn.execute(
            "SELECT source, status FROM admin_cost_snapshots WHERE source = ?",
            (ADMIN_COST_SNAPSHOT_SOURCE,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "success")
        self.assertEqual(refreshed["aws"]["status"], "available")

        dashboard = self.service.admin_cost_dashboard()
        self.assertEqual(dashboard["openai"]["call_totals"]["total_calls"], 1)
        self.assertEqual(dashboard["aws"]["services"][0]["name"], "Amazon S3")

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


if __name__ == "__main__":
    unittest.main()

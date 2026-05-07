import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import DEFAULT_MEMBER_PASSWORD, EvidenceService


class LeaderPortalServiceTests(unittest.TestCase):
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

    def test_leader_dashboard_includes_executive_rollups(self):
        dashboard = self.service.leader_dashboard()

        self.assertIn("metrics", dashboard)
        self.assertIn("funnel", dashboard)
        self.assertIn("timeline", dashboard)
        self.assertIn("watchlist", dashboard)
        self.assertIn("builder_capacity", dashboard)
        self.assertIn("attorney_capacity", dashboard)
        self.assertIn("forecast", dashboard)
        self.assertEqual(len(dashboard["timeline"]), 6)
        self.assertTrue(dashboard["funnel"])
        self.assertTrue(dashboard["watchlist"])
        self.assertIn("stage_label", dashboard["members"][0])
        self.assertIn("risk_level", dashboard["members"][0])
        self.assertIn("first_name", dashboard["members"][0])
        self.assertIn("last_name", dashboard["members"][0])
        self.assertIn("email", dashboard["members"][0])
        self.assertIn("phone", dashboard["members"][0])

    def test_staff_login_rejects_credentials_for_wrong_portal(self):
        with self.assertRaises(ValueError) as context:
            self.service.login_staff("leader@ascendhsi.com", DEFAULT_MEMBER_PASSWORD, {}, "attorney")

        self.assertIn("Leader Portal", str(context.exception))
        self.assertIn("Attorney Portal", str(context.exception))

        result = self.service.login_staff("leader@ascendhsi.com", DEFAULT_MEMBER_PASSWORD, {}, "leader")
        self.assertEqual(result["user"]["role"], "leader")

    def test_leader_dashboard_flags_unassigned_members_for_attention(self):
        self.service.leader_invite_member(
            "Mina",
            "Shah",
            "mina@example.com",
            industry_domain="Technology",
            primary_field="Machine Learning",
        )

        dashboard = self.service.leader_dashboard()
        invited_member = next(item for item in dashboard["members"] if item["display_name"] == "Mina Shah")

        self.assertEqual(invited_member["stage_label"], "Invited")
        self.assertIn(invited_member["risk_level"], {"Moderate", "High"})
        self.assertTrue(any(flag in invited_member["risk_flags"] for flag in {"Registration pending", "Builder unassigned"}))

    def test_leader_invite_can_optionally_assign_builder_and_attorney(self):
        dashboard = self.service.leader_dashboard()
        builder_id = dashboard["builders"][0]["id"]
        attorney_id = dashboard["attorneys"][0]["id"]

        result = self.service.leader_invite_member(
            "Mina",
            "Route",
            "mina.route@example.com",
            industry_domain="Technology",
            builder_id=builder_id,
            attorney_id=attorney_id,
        )

        self.assertEqual(result["builder_id"], builder_id)
        self.assertEqual(result["attorney_id"], attorney_id)
        member = next(item for item in self.service.leader_dashboard()["members"] if item["client_id"] == result["client_id"])
        self.assertEqual(member["builder_id"], builder_id)
        self.assertEqual(member["attorney_id"], attorney_id)

    def test_leader_can_access_attorney_evidence_view(self):
        sample = self.config.upload_root / "sample.txt"
        sample.parent.mkdir(parents=True, exist_ok=True)
        sample.write_text("evidence", encoding="utf-8")
        self.service.conn.execute(
            """
            INSERT INTO evidence_items(
              id, client_id, case_id, criterion_code, document_type, title, description, file_name, content_type,
              local_path, drive_mirror_path, status, ai_summary, quality_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
            """,
            (
                "ev_leader_1",
                "client_1",
                "case_1",
                "awards",
                "Other",
                "Award evidence",
                "",
                "sample.txt",
                "text/plain",
                str(sample),
                str(sample),
                "Summary",
                60,
            ),
        )
        self.service.conn.commit()

        evidence = self.service.attorney_member_evidence("client_1", actor_role="leader")

        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["file_name"], "sample.txt")


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import EvidenceService


class ProductBacklogTimelineRecommendationTests(unittest.TestCase):
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

    def test_product_feature_request_captures_priority_value_and_screenshot(self):
        created = self.service.create_product_feature_request(
            actor_email="leader@ascendhsi.com",
            title="Attorney recommendation letter queue",
            request_type="new_feature",
            target_portals="Attorney, Member",
            priority="P1",
            business_value="Speeds attorney drafting and member signature loops.",
            description="Create an AI-assisted recommendation letter workspace with review and send-to-member actions.",
            acceptance_criteria="Attorney can generate, approve, and send a downloadable letter.",
            attachments=[{"file_name": "letter-workspace.png", "content_type": "image/png", "bytes": b"fake-image"}],
        )

        self.assertEqual(created["priority"], "P1")
        self.assertEqual(created["request_type"], "new_feature")
        self.assertEqual(created["attachment_count"], 1)
        self.assertTrue(Path(created["attachments"][0]["local_path"]).exists())

        updated = self.service.update_product_feature_request(created["id"], priority="P0", status="in_progress", actor_email="leader@ascendhsi.com")
        backlog = self.service.product_feature_backlog()

        self.assertEqual(updated["priority"], "P0")
        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(backlog["priority_counts"]["P0"], 1)
        self.assertEqual(backlog["status_counts"]["in_progress"], 1)

    def test_petition_delivery_timeline_uses_case_state_and_includes_rfe_window(self):
        self.service.upload_evidence(
            criterion_code="judging",
            document_type="Invitation",
            title="Judging invitation",
            description="Fabricated judging invitation.",
            file_name="judging-invite.pdf",
            content_type="application/pdf",
            file_bytes=b"evidence",
            quality_score=80,
        )
        self.service.create_builder_task(
            "client_1",
            "Upload independent recommendation target",
            "Collect recommender context.",
            "original_contributions",
            "2025-01-01",
        )

        timeline = self.service.petition_delivery_timeline("client_1", actor_role="leader")

        self.assertTrue(timeline["ok"])
        self.assertEqual(timeline["member"]["client_id"], "client_1")
        self.assertEqual(len(timeline["stages"]), 7)
        self.assertEqual(timeline["rfe_support"]["style"], "dotted")
        self.assertTrue(timeline["summary"]["target_filing_date"])
        self.assertTrue(any("Task overdue" in item["message"] for item in timeline["alerts"]))

    def test_attorney_recommendation_letter_flow_requires_project_and_notifies_member(self):
        critical_role = self.service.create_critical_role_project(
            organization_name="Global Trust Platform",
            role_title="Senior Product Manager",
            project_name="Evidence Automation",
            role_summary="Owned the strategic product charter.",
            contributions_summary="Led cross-functional delivery with legal, engineering, and operations.",
            business_value_summary="Reduced manual review time for enterprise evidence workflows.",
            quantitative_metrics="42% faster evidence review.",
            workflow_status="submitted",
        )
        self.service.create_original_contribution_entry(
            contribution_title="Adaptive Evidence Routing",
            organization_name="Global Trust Platform",
            job_title="Senior Product Manager",
            originality_summary="Created a new routing model for evidence workflows.",
            distinct_contribution_summary="Designed the model and launch path.",
            impact_metrics="18% fewer escalations.",
            field_wide_impact="Adopted by partner compliance teams.",
            workflow_status="submitted",
        )

        workspace = self.service.recommendation_letter_workspace("client_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")
        self.assertEqual(len(workspace["projects"]), 2)

        with self.assertRaisesRegex(ValueError, "Select a Critical Role or Original Contribution project"):
            self.service.attorney_recommendation_letter_generator("client_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

        generated = self.service.attorney_recommendation_letter_generator(
            "client_1",
            letter_kind="dependent",
            project_type="critical_role",
            project_id=critical_role["id"],
            prompt_config={
                "recommender_name": "Dana Smith",
                "recommender_title": "VP Product",
                "recommender_organization": "Global Trust Platform",
                "recommender_relationship": "I sponsored the project and observed the member's leadership.",
                "facts_to_confirm": "Confirm dates, role scope, and the 42% review-time improvement.",
            },
            actor_role="attorney",
            actor_email="attorney@ascendhsi.com",
        )
        letter_id = generated["letter_record"]["id"]
        self.assertEqual(generated["status"], "fallback")
        self.assertIn("Evidence Automation", generated["letter_record"]["letter"]["plain_text"])

        with self.assertRaisesRegex(ValueError, "Approve recommendation letter"):
            self.service.send_recommendation_letter_to_member(letter_id, actor_role="attorney", actor_email="attorney@ascendhsi.com")

        approved = self.service.update_recommendation_letter_status(letter_id, "approved", actor_role="attorney", actor_email="attorney@ascendhsi.com")
        self.assertEqual(approved["status"], "approved")

        sent = self.service.send_recommendation_letter_to_member(letter_id, actor_role="attorney", actor_email="attorney@ascendhsi.com")
        self.assertEqual(sent["letter"]["status"], "sent_to_member")

        download = self.service.recommendation_letter_download(letter_id)
        self.assertIn("Recommendation Letter", download["content"])

        messages = self.service.message_center("member", actor_client_id="client_1")
        latest = messages["threads"][0]["latest_message"]
        self.assertIn("Download link: /api/recommendation-letters/", latest["body"])
        self.assertEqual(messages["unread_count"], 1)


if __name__ == "__main__":
    unittest.main()

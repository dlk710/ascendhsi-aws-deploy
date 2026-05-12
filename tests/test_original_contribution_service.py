import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import EvidenceService


class OriginalContributionServiceTests(unittest.TestCase):
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

    def test_create_update_delete_original_contribution_entry(self):
        created = self.service.create_original_contribution_entry(
            contribution_title="Project Nova",
            contribution_category="Work-related",
            field_of_expertise="Technical Product Management",
            organization_name="Organization 1",
            originality_summary="Created a first-of-its-kind integration testing workflow.",
            distinct_contribution_summary="Personally led ideation, design direction, and launch strategy.",
            impact_metrics="Reduced testing time by 90% and improved release confidence.",
            field_wide_impact="Changed how teams test platform integrations at scale.",
        )

        self.assertEqual(created["contribution_title"], "Project Nova")
        self.assertEqual(created["summary_line"], "Project Nova • Organization 1 • Work-related")
        self.assertFalse(created["export_evidence_id"])
        self.assertFalse(created["has_export_artifact"])

        profile = self.service.member_profile()
        self.assertEqual(profile["original_contribution_entry_count"], 1)
        self.assertEqual(profile["original_contribution_entries"][0]["contribution_title"], "Project Nova")
        self.assertFalse(profile["original_contribution_entries"][0]["export_open_url"])

        detail = self.service.builder_member_detail("client_1")
        self.assertEqual(detail["original_contribution_entries"][0]["contribution_title"], "Project Nova")
        self.assertEqual(detail["original_contribution_entries"][0]["export_file_name"], "")

        updated = self.service.update_original_contribution_entry(
            created["id"],
            adoption_scale="Used across thousands of apps.",
            attorney_friendly_summary="This contribution was original, measurable, and influential within the field.",
            workflow_status="submitted",
        )
        self.assertIn("thousands", updated["adoption_scale"])
        self.assertTrue(updated["export_evidence_id"])
        self.assertTrue(updated["has_export_artifact"])

        deleted = self.service.delete_original_contribution_entry(created["id"])
        self.assertTrue(deleted["ok"])
        self.assertEqual(self.service.original_contribution_entries(), [])

    def test_original_contribution_requires_core_fields(self):
        with self.assertRaisesRegex(ValueError, "contribution_title is required"):
            self.service.create_original_contribution_entry(
                contribution_title="",
                originality_summary="Original summary",
                distinct_contribution_summary="Distinct summary",
                impact_metrics="Metrics",
                field_wide_impact="Field impact",
                workflow_status="submitted",
            )

    def test_member_profile_backfills_export_for_legacy_submitted_original_contribution(self):
        self.service.conn.execute(
            """
            INSERT INTO original_contribution_entries(
              id, client_id, case_id, contribution_title, contribution_category, organization_name,
              originality_summary, distinct_contribution_summary, impact_metrics, field_wide_impact,
              workflow_status, export_evidence_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "oce_legacy_1",
                "client_1",
                "case_1",
                "Legacy Contribution",
                "Work-related",
                "Legacy Org",
                "Introduced an original process improvement.",
                "Personally designed and led the implementation.",
                "Cut review time by 60%.",
                "Influenced how similar teams approached the same problem.",
                "submitted",
                "",
            ),
        )
        self.service.conn.commit()

        profile = self.service.member_profile()
        self.assertEqual(profile["original_contribution_entry_count"], 1)
        self.assertTrue(profile["original_contribution_entries"][0]["has_export_artifact"])
        self.assertTrue(profile["original_contribution_entries"][0]["export_file_name"].endswith(".pdf"))

    def test_member_profile_does_not_backfill_export_for_draft_original_contribution(self):
        self.service.conn.execute(
            """
            INSERT INTO original_contribution_entries(
              id, client_id, case_id, contribution_title, contribution_category, organization_name,
              originality_summary, distinct_contribution_summary, impact_metrics, field_wide_impact,
              workflow_status, export_evidence_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "oce_draft_1",
                "client_1",
                "case_1",
                "Draft Contribution",
                "Work-related",
                "Draft Org",
                "Introduced an original process improvement.",
                "Personally designed and led the implementation.",
                "Cut review time by 60%.",
                "Influenced how similar teams approached the same problem.",
                "draft",
                "",
            ),
        )
        self.service.conn.commit()

        profile = self.service.member_profile()
        self.assertEqual(profile["original_contribution_entry_count"], 1)
        self.assertFalse(profile["original_contribution_entries"][0]["has_export_artifact"])
        self.assertEqual(profile["original_contribution_entries"][0]["export_file_name"], "")


if __name__ == "__main__":
    unittest.main()

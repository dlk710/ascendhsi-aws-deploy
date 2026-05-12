import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import EvidenceService


class CriticalRoleProjectServiceTests(unittest.TestCase):
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

    def test_create_update_delete_critical_role_project(self):
        created = self.service.create_critical_role_project(
            organization_name="Organization 1",
            role_title="Senior Product Manager",
            role_start_date="2023-01-01",
            is_current_role=True,
            project_name="Project Atlas",
            project_start_date="2023-03-01",
            project_status="Active",
            role_summary="Owned the strategic charter for a critical AI commerce product.",
            contributions_summary="Defined product vision, secured executive buy-in, and led launch execution.",
            business_value_summary="Drove revenue expansion and faster release cycles.",
            quantitative_metrics="50% faster releases; 15% spend uplift in new markets.",
        )

        self.assertEqual(created["organization_name"], "Organization 1")
        self.assertTrue(created["is_current_role"])
        self.assertEqual(created["role_date_label"], "2023-01-01 to Present")
        self.assertEqual(created["workflow_status"], "draft")
        self.assertFalse(created["export_evidence_id"])
        self.assertFalse(created["has_export_artifact"])

        profile = self.service.member_profile()
        self.assertEqual(profile["critical_role_project_count"], 1)
        self.assertEqual(profile["critical_role_projects"][0]["project_name"], "Project Atlas")
        self.assertFalse(profile["critical_role_projects"][0]["export_open_url"])

        detail = self.service.builder_member_detail("client_1")
        self.assertEqual(detail["critical_role_projects"][0]["project_name"], "Project Atlas")
        self.assertEqual(detail["critical_role_projects"][0]["export_file_name"], "")

        updated = self.service.update_critical_role_project(
            created["id"],
            project_status="Launched",
            business_value_summary="Drove revenue expansion, faster releases, and stronger user trust.",
            attorney_friendly_summary="Served in a leading role on a strategically important project for a distinguished organization.",
            workflow_status="submitted",
        )
        self.assertEqual(updated["project_status"], "Launched")
        self.assertIn("leading role", updated["attorney_friendly_summary"].lower())
        self.assertTrue(updated["export_evidence_id"])
        self.assertTrue(updated["has_export_artifact"])

        deleted = self.service.delete_critical_role_project(created["id"])
        self.assertTrue(deleted["ok"])
        self.assertEqual(self.service.critical_role_projects(), [])

    def test_critical_role_project_requires_core_fields(self):
        with self.assertRaisesRegex(ValueError, "organization_name is required"):
            self.service.create_critical_role_project(
                organization_name="",
                role_title="Senior Product Manager",
                project_name="Project Atlas",
                role_summary="Role summary",
                contributions_summary="Contribution summary",
                business_value_summary="Value summary",
                workflow_status="submitted",
            )

    def test_member_profile_backfills_export_for_legacy_submitted_critical_role_project(self):
        self.service.conn.execute(
            """
            INSERT INTO critical_role_projects(
              id, client_id, case_id, organization_name, role_title, is_current_role, project_name,
              project_status, role_summary, contributions_summary, business_value_summary, workflow_status,
              export_evidence_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "crp_legacy_1",
                "client_1",
                "case_1",
                "Legacy Org",
                "Senior PM",
                1,
                "Legacy Project",
                "Active",
                "Led a critical portfolio initiative.",
                "Drove the rollout across teams.",
                "Improved adoption and efficiency.",
                "submitted",
                "",
            ),
        )
        self.service.conn.commit()

        profile = self.service.member_profile()
        self.assertEqual(profile["critical_role_project_count"], 1)
        self.assertTrue(profile["critical_role_projects"][0]["has_export_artifact"])
        self.assertTrue(profile["critical_role_projects"][0]["export_file_name"].endswith(".pdf"))

    def test_member_profile_does_not_backfill_export_for_draft_critical_role_project(self):
        self.service.conn.execute(
            """
            INSERT INTO critical_role_projects(
              id, client_id, case_id, organization_name, role_title, is_current_role, project_name,
              project_status, role_summary, contributions_summary, business_value_summary, workflow_status,
              export_evidence_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "crp_draft_1",
                "client_1",
                "case_1",
                "Draft Org",
                "Senior PM",
                1,
                "Draft Project",
                "Active",
                "Led a critical portfolio initiative.",
                "Drove the rollout across teams.",
                "Improved adoption and efficiency.",
                "draft",
                "",
            ),
        )
        self.service.conn.commit()

        profile = self.service.member_profile()
        self.assertEqual(profile["critical_role_project_count"], 1)
        self.assertFalse(profile["critical_role_projects"][0]["has_export_artifact"])
        self.assertEqual(profile["critical_role_projects"][0]["export_file_name"], "")


if __name__ == "__main__":
    unittest.main()

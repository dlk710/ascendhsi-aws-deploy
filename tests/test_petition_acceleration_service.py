import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import AppConfig
from app.services import EvidenceService


class PetitionAccelerationServiceTests(unittest.TestCase):
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

    def upload(self, criterion_code, title, file_name, document_type="Other", quality_score=80, duplicate_action=""):
        return self.service.upload_evidence(
            criterion_code=criterion_code,
            document_type=document_type,
            title=title,
            description=f"Fabricated test evidence for {title}.",
            file_name=file_name,
            content_type="application/pdf",
            file_bytes=b"fabricated evidence",
            ai_summary=f"Fabricated summary for {title}.",
            quality_score=quality_score,
            duplicate_action=duplicate_action,
        )

    def test_workspace_covers_p0_p1_functions_with_fabricated_data(self):
        self.service.update_member_profile(
            first_name="Vas",
            last_name="Patel",
            email="vas@ascendhsi.com",
            current_title="Senior Product Manager",
            current_employer="Global Trust Platform",
            industry_domain="Technology",
            primary_field="AI product infrastructure",
            specialization="Trust and safety automation",
            biography="Senior product leader building AI systems for regulated enterprise workflows.",
            top_achievements="Launched products used by enterprise compliance teams.",
            judging_summary="Invited to judge AI product awards and review finalist submissions.",
            leading_roles_summary="Led critical trust automation programs at a distinguished technology organization.",
            original_contributions_summary="Created an original evidence automation framework adopted by enterprise teams.",
            proposed_final_merits_summary="The case should emphasize original AI infrastructure work, critical product leadership, and independent judging.",
            profile_confirmed=True,
        )
        self.upload("judging", "AI Awards Judge Invitation", "judge-invitation.pdf", "Invitation", 90)
        self.upload("judging", "AI Awards Thank You", "judge-thank-you.pdf", "Thank You Note", 82)
        self.upload("judging", "AI Awards Certificate", "judge-certificate.pdf", "Certificate or Completion", 88)
        self.upload("original_contributions", "Adoption Metrics", "impact-metrics.pdf", "Impact or Results", 84)
        self.upload("original_contributions", "Duplicate Metrics", "impact-metrics.pdf", "Impact or Results", 78, duplicate_action="copy")
        self.upload("published_material", "Low Quality Press Scan", "scan-press.pdf", "Publication or Media", 20)
        critical_role = self.service.create_critical_role_project(
            organization_name="Global Trust Platform",
            role_title="Senior Product Manager",
            project_name="Evidence Automation",
            role_summary="Owned the product strategy and launch path.",
            contributions_summary="Led cross-functional delivery across engineering, legal, and operations.",
            business_value_summary="Reduced manual review time for enterprise evidence workflows.",
            quantitative_metrics="Reduced review time by 42% across three pilot teams.",
            organization_distinctiveness="Global enterprise platform serving regulated organizations.",
            workflow_status="submitted",
        )
        original = self.service.create_original_contribution_entry(
            contribution_title="Adaptive Evidence Routing",
            originality_summary="Created a first-of-its-kind routing model for evidence workflows.",
            distinct_contribution_summary="Designed the model, workflow, and operational rollout.",
            impact_metrics="42% faster review and 18% fewer escalations.",
            field_wide_impact="Adopted as a reference workflow by partner compliance teams.",
            organization_name="Global Trust Platform",
            job_title="Senior Product Manager",
            workflow_status="submitted",
        )
        self.service.create_builder_task(
            "client_1",
            "Collect independent expert letter",
            "Ask an external expert to confirm field significance.",
            "original_contributions",
            "2026-06-01",
        )

        workspace = self.service.petition_acceleration_workspace("client_1", actor_role="leader")

        self.assertTrue(workspace["ok"])
        self.assertEqual(len(workspace["feature_index"]), 21)
        self.assertIn("claim_map", workspace["p0"])
        self.assertIn("document_qa", workspace["p1"])
        judging_claim = next(item for item in workspace["p0"]["claim_map"] if item["criterion_code"] == "judging")
        self.assertEqual(judging_claim["status"], "petition_ready")
        self.assertGreaterEqual(len(judging_claim["source_links"]), 3)
        self.assertTrue(workspace["p0"]["top_next_actions"])
        judging_pack = next(item for item in workspace["p0"]["criterion_request_packs"] if item["criterion_code"] == "judging")
        self.assertIn("invitation", judging_pack["member_prompt"].lower())
        workflow_items = workspace["p0"]["draft_resume_submit_workflow"]["items"]
        self.assertTrue(any(item["id"] == critical_role["id"] and item["export_evidence_id"] for item in workflow_items))
        self.assertTrue(any(item["id"] == original["id"] and item["export_evidence_id"] for item in workflow_items))
        qa_types = {item["type"] for item in workspace["p1"]["document_qa"]["flags"]}
        self.assertIn("duplicate_file_name", qa_types)
        self.assertIn("low_quality_scan", qa_types)
        exhibits = workspace["p1"]["exhibit_assembly_manager"]["exhibits"]
        self.assertTrue(exhibits)
        self.assertEqual(exhibits[0]["exhibit_number"], "ASC-001")
        self.assertTrue(workspace["p1"]["uscis_upload_packager"]["bundles"])
        self.assertTrue(workspace["p1"]["filing_qa_checklist"]["checks"])
        self.assertIn("buckets", workspace["p0"]["attorney_review_queue"])
        self.assertTrue(workspace["p1"]["portfolio_heatmap"]["rows"])

    def test_workspace_surfaces_high_gaps_for_sparse_case(self):
        workspace = self.service.petition_acceleration_workspace("client_1", actor_role="leader")

        high_gaps = [item for item in workspace["p0"]["gap_detector"]["gaps"] if item["severity"] == "high"]
        self.assertTrue(high_gaps)
        self.assertGreaterEqual(workspace["snapshot"]["high_severity_gaps"], 1)
        self.assertTrue(any(item["criterion_code"] == "original_contributions" for item in high_gaps))


if __name__ == "__main__":
    unittest.main()

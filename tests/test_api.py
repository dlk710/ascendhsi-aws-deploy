import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api import app
from app.services import DuplicateEvidenceError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.member_headers = {"Authorization": "Bearer member_token"}
        self.builder_headers = {"Authorization": "Bearer builder_token"}
        self.leader_headers = {"Authorization": "Bearer leader_token"}
        self.attorney_headers = {"Authorization": "Bearer attorney_token"}
        self.member_user = {"client_id": "client_1", "case_id": "case_1", "display_name": "Vas"}
        self.builder_user = {"email": "builder@ascendhsi.com", "role": "builder", "display_name": "Ava"}
        self.leader_user = {"email": "leader@ascendhsi.com", "role": "leader", "display_name": "Ava Morales"}
        self.attorney_user = {"email": "attorney@ascendhsi.com", "role": "attorney", "display_name": "Sophia Chen"}

    def admin_headers(self):
        return {"Authorization": "Bearer admin_token"}

    def allow_admin_session(self, service):
        service.staff_session.return_value = {"display_name": "Maya Thompson", "role": "admin"}

    def allow_leader_session(self, service):
        service.staff_session.return_value = self.leader_user

    def allow_attorney_session(self, service):
        service.staff_session.return_value = self.attorney_user

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "ascend-suite-api")

    def test_ready_uses_operational_dashboard(self):
        service = Mock()
        service.admin_operational_dashboard.return_value = {
            "portal_health": [
                {"name": "S3 Evidence Buckets", "status": "healthy"},
                {"name": "OpenAI", "status": "healthy"},
            ]
        }
        with patch("app.api.service", return_value=service):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["storage"]["name"], "S3 Evidence Buckets")
        service.admin_operational_dashboard.assert_called_once()

    def test_visa_compass_lead_capture_uses_service(self):
        service = Mock()
        service.capture_marketing_lead.return_value = {"ok": True, "lead": {"id": "lead_1", "email": "prospect@example.com"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/marketing/leads/visa-compass",
                json={
                    "email": "prospect@example.com",
                    "phone": "555-111-2222",
                    "answers": {"goal": "green_card"},
                    "result": {"top_match": "eb1a", "match_label": "EB-1A", "readiness_score": 72},
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lead"]["id"], "lead_1")
        kwargs = service.capture_marketing_lead.call_args.kwargs
        self.assertEqual(kwargs["email"], "prospect@example.com")
        self.assertEqual(kwargs["phone"], "555-111-2222")
        self.assertEqual(kwargs["lead_source"], "visa_compass")

    def test_dashboard_uses_service(self):
        service = Mock()
        service.member_session.return_value = self.member_user
        service.member_dashboard.return_value = {
            "client": {"display_name": "Vas"},
            "metrics": {"evidence_count": 1},
            "criteria": [],
        }
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/dashboard", headers=self.member_headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["client"]["display_name"], "Vas")
        service.member_dashboard.assert_called_once_with("client_1", "case_1", "Vas")

    def test_dashboard_rejects_non_member_token_with_json_error(self):
        service = Mock()
        service.member_session.side_effect = ValueError("Session token is invalid")
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/dashboard", headers={"Authorization": "Bearer staff_token"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["status"], "failed")
        self.assertEqual(response.json()["detail"]["error"], "Session token is invalid")

    def test_login_uses_service(self):
        service = Mock()
        service.login_member.return_value = {"token": "sess_1", "member": {"display_name": "Vas"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/auth/login", data={"username": "vas@ascend.com", "password": "secret123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "sess_1")
        args = service.login_member.call_args.args
        self.assertEqual(args[:2], ("vas@ascend.com", "secret123"))
        self.assertIn("client_ip", args[2])

    def test_registration_invite_lookup_uses_service(self):
        service = Mock()
        service.member_registration_invite.return_value = {"ok": True, "email": "sam@example.com"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/registration-invite", params={"token": "invite_token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "sam@example.com")
        service.member_registration_invite.assert_called_once_with("invite_token")

    def test_invited_member_registration_uses_service(self):
        service = Mock()
        service.register_invited_member.return_value = {"ok": True, "token": "sess_new", "member": {"display_name": "Sam"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/member/register", data={"token": "invite_token", "password": "secret123", "phone": "555-1234"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "sess_new")
        args = service.register_invited_member.call_args.args
        self.assertEqual(args[:3], ("invite_token", "secret123", "555-1234"))
        self.assertIn("client_ip", args[3])

    def test_change_password_uses_service(self):
        service = Mock()
        service.change_member_password.return_value = {"ok": True, "status": "password_updated"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/auth/change-password",
                data={"current_password": "old-pass", "new_password": "new-pass-123"},
                headers={"Authorization": "Bearer sess_1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "password_updated")

    def test_builder_login_uses_service(self):
        service = Mock()
        service.login_builder.return_value = {"token": "bsess_1", "builder": {"display_name": "Ava"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/builder/auth/login", data={"username": "builder@ascendhsi.com", "password": "secret123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "bsess_1")

    def test_staff_login_uses_service(self):
        service = Mock()
        service.login_staff.return_value = {"token": "ssess_1", "user": {"display_name": "Marcus Reed", "role": "attorney"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/staff/auth/login", data={"username": "marcus.reed@ascendhsi.com", "password": "secret123", "portal_role": "attorney"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "ssess_1")
        args = service.login_staff.call_args.args
        self.assertEqual(args[:2], ("marcus.reed@ascendhsi.com", "secret123"))
        self.assertIn("client_ip", args[2])
        self.assertEqual(args[3], "attorney")

    def test_staff_auth_me_uses_service(self):
        service = Mock()
        service.staff_session.return_value = {"display_name": "Marcus Reed", "role": "attorney"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/staff/auth/me", headers={"Authorization": "Bearer ssess_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "attorney")

    def test_staff_change_password_uses_service(self):
        service = Mock()
        service.change_staff_password.return_value = {"ok": True, "status": "password_updated"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/staff/auth/change-password",
                data={"current_password": "old-pass", "new_password": "new-pass-123"},
                headers={"Authorization": "Bearer ssess_1"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "password_updated")

    def test_builder_dashboard_uses_service(self):
        service = Mock()
        service.builder_session.return_value = self.builder_user
        service.builder_dashboard.return_value = {"builder": {"display_name": "Ava"}, "metrics": {}, "members": [], "opportunities": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/builder/dashboard", headers=self.builder_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["builder"]["display_name"], "Ava")

    def test_leader_dashboard_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.leader_dashboard.return_value = {"metrics": {"member_count": 2}, "members": [], "builders": [], "attorneys": [], "invites": [], "domain_summary": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/leader/dashboard", headers=self.leader_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["member_count"], 2)

    def test_leader_invite_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.leader_invite_member.return_value = {"ok": True, "client_id": "client_2", "display_name": "Sam Lee"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/leader/invites",
                headers=self.leader_headers,
                data={
                    "first_name": "Sam",
                    "last_name": "Lee",
                    "email": "sam@example.com",
                    "industry_domain": "Technology",
                    "builder_id": "bld_1",
                    "attorney_id": "att_1",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "Sam Lee")
        service.leader_invite_member.assert_called_once_with("Sam", "Lee", "sam@example.com", "Technology", "", "", "", "bld_1", "att_1")

    def test_member_referrals_use_service(self):
        service = Mock()
        service.member_session.return_value = self.member_user
        service.member_referrals.return_value = {"settings": {"is_enabled": True}, "referrals": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/referrals", headers=self.member_headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["settings"]["is_enabled"])
        service.member_referrals.assert_called_once_with("client_1", "case_1")

    def test_create_member_referral_uses_service(self):
        service = Mock()
        service.member_session.return_value = self.member_user
        service.create_member_referral.return_value = {"ok": True, "referral": {"id": "ref_1", "prospect_name": "Sam Lee"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/member/referrals",
                headers=self.member_headers,
                data={
                    "prospect_name": "Sam Lee",
                    "prospect_email": "sam@example.com",
                    "prospect_phone": "555-0100",
                    "relationship": "Friend",
                    "notes": "Strong technical leader",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["referral"]["id"], "ref_1")
        service.create_member_referral.assert_called_once_with("client_1", "case_1", "Sam Lee", "sam@example.com", "555-0100", "Friend", "Strong technical leader")

    def test_leader_referrals_use_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.leader_referral_dashboard.return_value = {"settings": {"is_enabled": True}, "metrics": {"total_referrals": 2}, "referrals": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/leader/referrals", headers=self.leader_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["total_referrals"], 2)
        service.leader_referral_dashboard.assert_called_once_with()

    def test_leader_referral_settings_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.update_referral_settings.return_value = {"settings": {"is_enabled": False}}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/leader/referrals/settings",
                headers=self.leader_headers,
                data={
                    "is_enabled": "false",
                    "referred_bonus_amount": "600",
                    "referrer_bonus_amount": "300",
                    "promotion_name": "Summer promo",
                    "eligibility_note": "After six months",
                    "actor_email": "leader@ascendhsi.com",
                },
            )
        self.assertEqual(response.status_code, 200)
        service.update_referral_settings.assert_called_once_with(
            "false",
            "600",
            "300",
            promotion_name="Summer promo",
            eligibility_note="After six months",
            actor_email="leader@ascendhsi.com",
        )

    def test_leader_referral_status_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.update_referral_status.return_value = {"referrals": [{"id": "ref_1", "status": "qualified"}]}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/leader/referrals/ref_1",
                headers=self.leader_headers,
                data={"status": "qualified", "actor_email": "leader@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        service.update_referral_status.assert_called_once_with(
            "ref_1",
            "qualified",
            contract_signed_at="",
            six_months_completed_at="",
            paid_at="",
            disqualification_reason="",
            actor_email="leader@ascendhsi.com",
        )

    def test_leader_builder_assignment_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.leader_assign_builder.return_value = {"ok": True, "builder_name": "Ava Morales"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch("/api/leader/members/client_1/builder-assignment", headers=self.leader_headers, data={"builder_id": "bld_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["builder_name"], "Ava Morales")

    def test_leader_attorney_assignment_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.leader_assign_attorney.return_value = {"ok": True, "attorney_name": "Sophia Chen"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch("/api/leader/members/client_1/attorney-assignment", headers=self.leader_headers, data={"attorney_id": "att_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["attorney_name"], "Sophia Chen")

    def test_leader_product_backlog_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.product_feature_backlog.return_value = {"items": [{"id": "feat_1", "title": "Timeline alerts"}], "priority_counts": {"P0": 1}}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/leader/product-backlog", headers=self.leader_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["title"], "Timeline alerts")
        service.product_feature_backlog.assert_called_once_with()

    def test_create_leader_product_backlog_item_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.create_product_feature_request.return_value = {"id": "feat_1", "title": "Letter queue", "attachment_count": 1}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/leader/product-backlog",
                headers=self.leader_headers,
                data={
                    "title": "Letter queue",
                    "request_type": "new_feature",
                    "target_portals": "Attorney, Member",
                    "priority": "P1",
                    "business_value": "Speeds review",
                    "description": "Add recommendation letter workflow",
                    "acceptance_criteria": "Can approve and send",
                    "actor_email": "leader@ascendhsi.com",
                },
                files=[("screenshots", ("queue.png", b"fake-image", "image/png"))],
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["attachment_count"], 1)
        service.create_product_feature_request.assert_called_once()
        kwargs = service.create_product_feature_request.call_args.kwargs
        self.assertEqual(kwargs["priority"], "P1")
        self.assertEqual(kwargs["attachments"][0]["file_name"], "queue.png")
        self.assertEqual(kwargs["attachments"][0]["bytes"], b"fake-image")

    def test_update_leader_product_backlog_item_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.update_product_feature_request.return_value = {"id": "feat_1", "priority": "P0", "status": "in_progress"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/leader/product-backlog/feat_1",
                headers=self.leader_headers,
                data={"priority": "P0", "status": "in_progress", "actor_email": "leader@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "in_progress")
        service.update_product_feature_request.assert_called_once_with("feat_1", priority="P0", status="in_progress", actor_email="leader@ascendhsi.com")

    def test_admin_operations_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.admin_operational_dashboard.return_value = {"metrics": {"openai_endpoint_calls": 4}, "portal_health": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/operations", headers=self.admin_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["openai_endpoint_calls"], 4)

    def test_admin_operations_rejects_missing_token(self):
        service = Mock()
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/operations")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["error"], "Authorization required")
        service.admin_operational_dashboard.assert_not_called()

    def test_admin_operations_rejects_non_admin_role(self):
        service = Mock()
        service.staff_session.return_value = {"display_name": "Sophia Chen", "role": "attorney"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/operations", headers={"Authorization": "Bearer attorney_token"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["error"], "Insufficient permissions")
        service.admin_operational_dashboard.assert_not_called()

    def test_admin_issue_log_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.issue_log_backlog.return_value = {"items": [{"bug_id": "BUG-20260506-AB12"}], "priority_counts": {"P1": 1}}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/issue-log", headers=self.admin_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["bug_id"], "BUG-20260506-AB12")

    def test_create_admin_issue_log_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.create_issue_log.return_value = {"bug_id": "BUG-20260506-AB12", "status": "open"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/admin/issue-log",
                headers=self.admin_headers(),
                data={
                    "title": "Cost refresh fails",
                    "portal": "Admin Portal",
                    "section": "Cost Explorer",
                    "priority": "P1",
                    "status": "open",
                    "description": "Refresh call fails to populate AWS costs.",
                    "reported_by": "Maya Thompson",
                    "actor_email": "admin@ascendhsi.com",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bug_id"], "BUG-20260506-AB12")

    def test_update_admin_issue_log_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.update_issue_log.return_value = {"bug_id": "BUG-20260506-AB12", "status": "closed"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/admin/issue-log/BUG-20260506-AB12",
                headers=self.admin_headers(),
                data={"priority": "P0", "status": "closed", "actor_email": "admin@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "closed")
        service.update_issue_log.assert_called_once_with("BUG-20260506-AB12", priority="P0", status="closed", actor_email="admin@ascendhsi.com")

    def test_remove_admin_issue_log_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.remove_issue_log.return_value = {"ok": True, "status": "removed", "bug_id": "BUG-20260506-AB12"}
        with patch("app.api.service", return_value=service):
            response = self.client.request(
                "DELETE",
                "/api/admin/issue-log/BUG-20260506-AB12",
                headers=self.admin_headers(),
                data={"actor_email": "admin@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "removed")
        service.remove_issue_log.assert_called_once_with("BUG-20260506-AB12", actor_email="admin@ascendhsi.com")

    def test_admin_costs_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.admin_cost_dashboard.return_value = {"status": "needs_refresh", "aws": {}, "openai": {}}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/costs", headers=self.admin_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "needs_refresh")

    def test_admin_costs_refresh_uses_service(self):
        service = Mock()
        self.allow_admin_session(service)
        service.refresh_admin_cost_dashboard.return_value = {"status": "success", "aws": {"status": "available"}, "openai": {"status": "available"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/admin/costs/refresh", headers=self.admin_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_attorney_petition_generator_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.attorney_petition_generator.return_value = {"ok": True, "status": "success", "executive_summary": "Draft"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/attorney/petition-generator", headers=self.attorney_headers, params={"client_id": "client_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        service.attorney_petition_generator.assert_called_once_with("client_1", attorney_email="attorney@ascendhsi.com")

    def test_generic_petition_acceleration_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.petition_acceleration_workspace.return_value = {"ok": True, "status": "success", "feature_index": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get(
                "/api/petition-acceleration",
                headers=self.leader_headers,
                params={"client_id": "client_1", "actor_role": "leader", "actor_email": "leader@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        service.petition_acceleration_workspace.assert_called_once_with("client_1", actor_role="leader", actor_email="leader@ascendhsi.com")

    def test_member_petition_acceleration_uses_session_member(self):
        service = Mock()
        service.member_session.return_value = {"client_id": "client_1", "case_id": "case_1", "display_name": "Vas"}
        service.petition_acceleration_workspace.return_value = {"ok": True, "status": "success"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/petition-acceleration", headers={"Authorization": "Bearer sess_1"})
        self.assertEqual(response.status_code, 200)
        service.member_session.assert_called_once_with("sess_1")
        service.petition_acceleration_workspace.assert_called_once_with("client_1", actor_role="member")

    def test_attorney_petition_acceleration_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.petition_acceleration_workspace.return_value = {"ok": True, "status": "success"}
        with patch("app.api.service", return_value=service):
            response = self.client.get(
                "/api/attorney/members/client_1/petition-acceleration",
                headers=self.attorney_headers,
                params={"attorney_email": "attorney@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        service.petition_acceleration_workspace.assert_called_once_with("client_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

    def test_attorney_endeavor_letter_generator_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.attorney_endeavor_letter_generator.return_value = {"ok": True, "status": "success", "letter": {"title": "Statement"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/endeavor-letter-generator",
                headers=self.attorney_headers,
                json={
                    "client_id": "client_1",
                    "actor_role": "attorney",
                    "actor_email": "attorney@ascendhsi.com",
                    "prompt_config": {"proposed_endeavor": "Continue high-impact research"},
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        service.attorney_endeavor_letter_generator.assert_called_once_with(
            "client_1",
            prompt_config={"proposed_endeavor": "Continue high-impact research"},
            actor_role="attorney",
            actor_email="attorney@ascendhsi.com",
        )

    def test_member_filing_timeline_uses_service(self):
        service = Mock()
        service.petition_delivery_timeline.return_value = {"ok": True, "summary": {"target_filing_date": "2026-08-01"}, "stages": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get(
                "/api/members/client_1/filing-timeline",
                params={"actor_role": "leader", "actor_email": "leader@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["target_filing_date"], "2026-08-01")
        service.petition_delivery_timeline.assert_called_once_with(
            "client_1",
            actor_role="leader",
            actor_email="leader@ascendhsi.com",
            actor_client_id="",
        )

    def test_recommendation_letter_workspace_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.recommendation_letter_workspace.return_value = {"ok": True, "projects": [{"id": "crp_1"}], "letters": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get(
                "/api/attorney/members/client_1/recommendation-letter-workspace",
                headers=self.attorney_headers,
                params={"actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["projects"][0]["id"], "crp_1")
        service.recommendation_letter_workspace.assert_called_once_with("client_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

    def test_recommendation_letter_generator_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.attorney_recommendation_letter_generator.return_value = {"ok": True, "letter_record": {"id": "recltr_1"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/recommendation-letter-generator",
                headers=self.attorney_headers,
                json={
                    "client_id": "client_1",
                    "letter_kind": "dependent",
                    "project_type": "critical_role",
                    "project_id": "crp_1",
                    "actor_role": "attorney",
                    "actor_email": "attorney@ascendhsi.com",
                    "prompt_config": {"recommender_name": "Dana"},
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["letter_record"]["id"], "recltr_1")
        service.attorney_recommendation_letter_generator.assert_called_once_with(
            "client_1",
            letter_kind="dependent",
            project_type="critical_role",
            project_id="crp_1",
            prompt_config={"recommender_name": "Dana"},
            actor_role="attorney",
            actor_email="attorney@ascendhsi.com",
        )

    def test_send_recommendation_letter_to_member_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.send_recommendation_letter_to_member.return_value = {"ok": True, "letter": {"id": "recltr_1", "status": "sent_to_member"}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/recommendation-letters/recltr_1/send-to-member",
                headers=self.attorney_headers,
                json={"actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["letter"]["status"], "sent_to_member")
        service.send_recommendation_letter_to_member.assert_called_once_with(
            "recltr_1",
            actor_role="attorney",
            actor_email="attorney@ascendhsi.com",
        )

    def test_download_recommendation_letter_returns_text(self):
        service = Mock()
        service.recommendation_letter_download.return_value = {
            "file_name": "letter.txt",
            "content_type": "text/plain; charset=utf-8",
            "content": "Recommendation letter text",
        }
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/recommendation-letters/recltr_1/download")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "Recommendation letter text")
        self.assertIn("letter.txt", response.headers["content-disposition"])
        service.recommendation_letter_download.assert_called_once_with("recltr_1")

    def test_portal_assistant_reply_uses_service(self):
        service = Mock()
        service.portal_assistant_reply.return_value = {
            "ok": True,
            "status": "fallback",
            "assistant_name": "Ascend Navigator",
            "summary": "Next best move is to review the weakest criterion.",
            "detailed_answer": "Detailed answer",
            "detail_prompt": "Ask for the detailed answer with storage-backed references.",
            "response_mode": "summary",
            "references": [],
        }
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/assistant/reply",
                json={
                    "actor_role": "attorney",
                    "actor_email": "attorney@ascendhsi.com",
                    "client_id": "client_1",
                    "question": "What should I focus on next?",
                    "thread": [{"role": "user", "content": "Start with the biggest gap."}],
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_name"], "Ascend Navigator")
        self.assertEqual(response.json()["response_mode"], "summary")
        service.portal_assistant_reply.assert_called_once_with(
            "attorney",
            "What should I focus on next?",
            client_id="client_1",
            actor_email="attorney@ascendhsi.com",
            thread=[{"role": "user", "content": "Start with the biggest gap."}],
        )

    def test_support_ticket_create_uses_service(self):
        service = Mock()
        service.report_support_ticket.return_value = {
            "ok": True,
            "status": "created",
            "assistant_name": "Ascend Beacon",
            "ticket": {"ticket_number": "ASC-IT-20260429-ABCD"},
            "mailbox_thread_id": "thd_support_1",
        }
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/support/tickets",
                data={
                    "actor_role": "member",
                    "actor_client_id": "client_1",
                    "issue_location": "Member Portal / Evidence Intake",
                    "short_description": "Evidence upload looks stuck",
                    "details": "The screen kept spinning after I selected the file.",
                    "priority": "urgent",
                    "is_blocking": "true",
                    "attachment_descriptions_json": "[\"Spinner still active after upload\"]",
                },
                files=[("attachments", ("issue.png", b"fake-image", "image/png"))],
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_name"], "Ascend Beacon")
        service.report_support_ticket.assert_called_once_with(
            "member",
            "Evidence upload looks stuck",
            "The screen kept spinning after I selected the file.",
            issue_location="Member Portal / Evidence Intake",
            current_url="",
            priority="urgent",
            is_blocking=True,
            screenshot_url="",
            screenshot_notes="",
            actor_email="",
            actor_client_id="client_1",
            related_client_id="",
            attachments=[
                {
                    "file_name": "issue.png",
                    "content_type": "image/png",
                    "description": "Spinner still active after upload",
                    "file_bytes": b"fake-image",
                }
            ],
        )

    def test_attorney_batch_intake_create_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.attorney_batch_intake_create.return_value = {"id": "bat_1", "counts": {"items": 2}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/batch-intake",
                headers=self.attorney_headers,
                data={"client_id": "client_1", "member_context": "Large intake from counsel", "actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"},
                files={"file": ("intake.zip", b"PK\x03\x04", "application/zip")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "bat_1")
        service.attorney_batch_intake_create.assert_called_once()

    def test_attorney_member_evidence_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.attorney_member_evidence.return_value = [{"id": "ev_1", "file_name": "review.pdf"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get(
                "/api/attorney/members/client_1/evidence",
                headers=self.attorney_headers,
                params={"actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["file_name"], "review.pdf")
        service.attorney_member_evidence.assert_called_once_with("client_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

    def test_batch_intake_sessions_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.batch_intake_sessions.return_value = [{"id": "bat_1"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/batch-intake/sessions", headers=self.leader_headers, params={"client_id": "client_1", "actor_role": "leader"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "bat_1")
        service.batch_intake_sessions.assert_called_once_with("client_1", actor_role="leader", actor_email="leader@ascendhsi.com")

    def test_attorney_batch_intake_session_uses_service(self):
        service = Mock()
        self.allow_attorney_session(service)
        service.attorney_batch_intake_session.return_value = {"id": "bat_1", "items": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/attorney/batch-intake/bat_1", headers=self.attorney_headers, params={"actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "bat_1")
        service.attorney_batch_intake_session.assert_called_once_with("bat_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

    def test_update_attorney_batch_intake_item_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.update_attorney_batch_intake_item.return_value = {"id": "bat_1", "items": [{"id": "bti_1"}]}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/attorney/batch-intake/bat_1/items/bti_1",
                headers=self.leader_headers,
                data={"criterion_code": "judging", "review_status": "ready", "actor_role": "leader"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "updated")
        service.update_attorney_batch_intake_item.assert_called_once_with("bat_1", "bti_1", criterion_code="judging", review_status="ready", actor_role="leader", actor_email="leader@ascendhsi.com")

    def test_bulk_update_attorney_batch_intake_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.bulk_update_attorney_batch_intake.return_value = {"id": "bat_1", "items": []}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/batch-intake/bat_1/bulk-update",
                headers=self.leader_headers,
                data={"item_ids": "bti_1,bti_2", "review_status": "ready", "actor_role": "leader"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "updated")
        service.bulk_update_attorney_batch_intake.assert_called_once_with("bat_1", ["bti_1", "bti_2"], actor_role="leader", actor_email="leader@ascendhsi.com", review_status="ready")

    def test_commit_attorney_batch_intake_uses_service(self):
        service = Mock()
        self.allow_leader_session(service)
        service.commit_attorney_batch_intake.return_value = {"ok": True, "status": "committed", "committed_count": 4}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/attorney/batch-intake/bat_1/commit", headers=self.leader_headers, data={"actor_role": "leader"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "committed")
        service.commit_attorney_batch_intake.assert_called_once_with("bat_1", actor_role="leader", actor_email="leader@ascendhsi.com")

    def test_message_center_uses_service(self):
        service = Mock()
        service.message_center.return_value = {"threads": [], "recipient_options": [], "unread_count": 0}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/messages", params={"actor_role": "admin", "actor_email": "admin@ascendhsi.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 0)

    def test_create_message_uses_service(self):
        service = Mock()
        service.send_message.return_value = {"id": "msg_1", "subject": "Help needed"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/messages",
                data={
                    "actor_role": "member",
                    "actor_client_id": "client_1",
                    "subject": "Help needed",
                    "body": "I am stuck",
                    "recipient_role": "admin",
                    "recipient_key": "admin@ascendhsi.com",
                    "urgent": "true",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "msg_1")

    def test_set_message_read_uses_service(self):
        service = Mock()
        service.set_message_read.return_value = {"id": "msg_1", "is_read": 1}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/messages/msg_1/read",
                data={"actor_role": "admin", "actor_email": "admin@ascendhsi.com", "is_read": "true"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["is_read"], 1)

    def test_member_profile_uses_service(self):
        service = Mock()
        service.member_session.return_value = self.member_user
        service.member_profile.return_value = {"first_name": "Vas", "last_name": "D", "email": "vas@ascend.com"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/profile", headers=self.member_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["first_name"], "Vas")
        service.member_profile.assert_called_once_with("client_1", "case_1")

    def test_update_member_profile_calls_service(self):
        service = Mock()
        service.member_session.return_value = self.member_user
        service.update_member_profile.return_value = {"first_name": "Vas", "last_name": "D", "email": "vas@ascend.com"}
        with patch("app.api.service", return_value=service):
            response = self.client.put(
                "/api/member/profile",
                headers=self.member_headers,
                data={
                    "first_name": "Vas",
                    "last_name": "D",
                    "email": "vas@ascend.com",
                    "industry_domain": "Technology",
                    "profile_confirmed": "true",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "vas@ascend.com")

    def test_member_critical_role_projects_uses_service(self):
        service = Mock()
        service.critical_role_projects.return_value = [{"id": "crp_1", "project_name": "Project Atlas"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/critical-role-projects")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["project_name"], "Project Atlas")
        service.critical_role_projects.assert_called_once_with()

    def test_create_member_critical_role_project_calls_service(self):
        service = Mock()
        service.create_critical_role_project.return_value = {"id": "crp_1", "project_name": "Project Atlas"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/member/critical-role-projects",
                data={
                    "organization_name": "Organization 1",
                    "role_title": "Senior Product Manager",
                    "project_name": "Project Atlas",
                    "role_summary": "Owned a critical payments platform charter.",
                    "contributions_summary": "Led concept, roadmap, launch, and stakeholder buy-in.",
                    "business_value_summary": "Enabled faster releases and meaningful revenue lift.",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "crp_1")
        service.create_critical_role_project.assert_called_once()

    def test_update_member_critical_role_project_calls_service(self):
        service = Mock()
        service.update_critical_role_project.return_value = {"id": "crp_1", "project_name": "Project Atlas"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/member/critical-role-projects/crp_1",
                data={
                    "organization_name": "Organization 1",
                    "role_title": "Senior Product Manager",
                    "project_name": "Project Atlas",
                    "role_summary": "Updated role summary",
                    "contributions_summary": "Updated contributions",
                    "business_value_summary": "Updated value",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["project_name"], "Project Atlas")
        service.update_critical_role_project.assert_called_once()

    def test_delete_member_critical_role_project_calls_service(self):
        service = Mock()
        service.delete_critical_role_project.return_value = {"ok": True, "status": "deleted", "project_id": "crp_1"}
        with patch("app.api.service", return_value=service):
            response = self.client.delete("/api/member/critical-role-projects/crp_1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "deleted")
        service.delete_critical_role_project.assert_called_once_with("crp_1", client_id=None, case_id=None)

    def test_member_original_contributions_uses_service(self):
        service = Mock()
        service.original_contribution_entries.return_value = [{"id": "oce_1", "contribution_title": "Project Nova"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/original-contributions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["contribution_title"], "Project Nova")
        service.original_contribution_entries.assert_called_once_with()

    def test_create_member_original_contribution_calls_service(self):
        service = Mock()
        service.create_original_contribution_entry.return_value = {"id": "oce_1", "contribution_title": "Project Nova"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/member/original-contributions",
                data={
                    "contribution_title": "Project Nova",
                    "originality_summary": "Created a first-of-its-kind testing workflow.",
                    "distinct_contribution_summary": "Personally led ideation, roadmap, and launch.",
                    "impact_metrics": "90% time reduction",
                    "field_wide_impact": "Changed how teams test integrations at scale.",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "oce_1")
        service.create_original_contribution_entry.assert_called_once()

    def test_update_member_original_contribution_calls_service(self):
        service = Mock()
        service.update_original_contribution_entry.return_value = {"id": "oce_1", "contribution_title": "Project Nova"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/member/original-contributions/oce_1",
                data={
                    "contribution_title": "Project Nova",
                    "originality_summary": "Updated originality summary",
                    "distinct_contribution_summary": "Updated distinct contribution",
                    "impact_metrics": "Updated metrics",
                    "field_wide_impact": "Updated field impact",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["contribution_title"], "Project Nova")
        service.update_original_contribution_entry.assert_called_once()

    def test_delete_member_original_contribution_calls_service(self):
        service = Mock()
        service.delete_original_contribution_entry.return_value = {"ok": True, "status": "deleted", "entry_id": "oce_1"}
        with patch("app.api.service", return_value=service):
            response = self.client.delete("/api/member/original-contributions/oce_1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "deleted")
        service.delete_original_contribution_entry.assert_called_once_with("oce_1", client_id=None, case_id=None)

    def test_duplicate_upload_returns_conflict(self):
        service = Mock()
        service.upload_evidence.side_effect = DuplicateEvidenceError(
            {"id": "ev_1", "file_name": "review.pdf", "title": "Review", "criterion_code": "judging"}
        )
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/evidence",
                data={"criterion_code": "judging", "document_type": "Invitation", "title": "Review", "description": ""},
                files={"file": ("review.pdf", b"hello", "application/pdf")},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["status"], "duplicate")

    def test_analyze_evidence_returns_draft(self):
        service = Mock()
        service.analyze_evidence.return_value = {
            "ok": True,
            "status": "draft",
            "criterion_code": "judging",
            "criterion_name": "Judging",
            "title": "Reviewer invitation",
            "ai_description": "Summarizes a reviewer invitation.",
            "quality_score": 55,
            "confidence": 70,
        }
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/evidence/analyze",
                data={"member_context": "This is a reviewer invitation."},
                files={"file": ("review.txt", b"hello", "text/plain")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["criterion_code"], "judging")
        service.analyze_evidence.assert_called_once()

    def test_workspace_returns_payload(self):
        service = Mock()
        service.criterion_workspace.return_value = {"criterion": {"code": "judging"}, "folders": [], "files": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/criteria/judging/workspace")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["criterion"]["code"], "judging")

    def test_create_folder_calls_service(self):
        service = Mock()
        service.create_folder.return_value = {"id": "fld_1", "name": "Invites"}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/criteria/judging/folders", data={"name": "Invites", "parent_id": "", "color": "#1f6f5b"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Invites")

    def test_move_evidence_calls_service(self):
        service = Mock()
        service.move_evidence_to_folder.return_value = {"id": "ev_1", "folder_id": "fld_1"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch("/api/evidence/ev_1/folder", data={"folder_id": "fld_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["folder_id"], "fld_1")

    def test_upload_evidence_passes_folder_id_to_service(self):
        service = Mock()
        service.member_session.return_value = {"client_id": "client_1", "case_id": "case_1"}
        service.upload_evidence.return_value = {"evidence_id": "ev_1", "file_name": "invite.pdf"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/evidence",
                headers={"Authorization": "Bearer tok_1"},
                data={
                    "criterion_code": "judging",
                    "document_type": "Invitation",
                    "title": "Reviewer invitation",
                    "folder_id": "fld_1",
                },
                files={"file": ("invite.pdf", b"hello", "application/pdf")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.upload_evidence.call_args.kwargs["folder_id"], "fld_1")

    def test_update_folder_without_parent_preserves_parent(self):
        service = Mock()
        service.update_folder.return_value = {"id": "fld_1", "name": "Invitations"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch("/api/folders/fld_1", data={"name": "Invitations", "color": "#2f7d67"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("parent_id", service.update_folder.call_args.kwargs)

    def test_planner_items_returns_payload(self):
        service = Mock()
        service.planner_items.return_value = [{"id": "pln_1", "member_role": "Reviewer"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/planner")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["member_role"], "Reviewer")

    def test_create_planner_item_calls_service(self):
        service = Mock()
        service.create_planner_item.return_value = {"id": "pln_1", "member_role": "Reviewer"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/member/planner",
                data={
                    "member_role": "Reviewer",
                    "issued_by": "IEEE",
                    "description": "Peer review invitation",
                    "planned_completion_date": "2026-05-01",
                    "status": "planned",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "pln_1")


if __name__ == "__main__":
    unittest.main()

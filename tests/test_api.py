import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.api import app
from app.services import DuplicateEvidenceError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "ascend-suite-api")

    def test_ready_uses_operational_dashboard(self):
        service = Mock()
        service.admin_operational_dashboard.return_value = {
            "portal_health": [
                {"name": "Amazon S3", "status": "healthy", "detail": "ascend-active"},
                {"name": "OpenAI", "status": "degraded", "detail": "gpt-5.4-mini"},
            ]
        }
        with patch("app.api.service", return_value=service):
            response = self.client.get("/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["storage"]["name"], "Amazon S3")

    def test_dashboard_uses_service(self):
        service = Mock()
        service.dashboard.return_value = {
            "client": {"display_name": "Vas"},
            "metrics": {"evidence_count": 1},
            "criteria": [],
        }
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["client"]["display_name"], "Vas")
        service.dashboard.assert_called_once_with()

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
            response = self.client.post("/api/staff/auth/login", data={"username": "marcus.reed@ascendhsi.com", "password": "secret123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], "ssess_1")

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
        service.builder_dashboard.return_value = {"builder": {"display_name": "Ava"}, "metrics": {}, "members": [], "opportunities": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/builder/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["builder"]["display_name"], "Ava")

    def test_leader_dashboard_uses_service(self):
        service = Mock()
        service.leader_dashboard.return_value = {"metrics": {"member_count": 2}, "members": [], "builders": [], "attorneys": [], "invites": [], "domain_summary": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/leader/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["member_count"], 2)

    def test_leader_invite_uses_service(self):
        service = Mock()
        service.leader_invite_member.return_value = {"ok": True, "client_id": "client_2", "display_name": "Sam Lee"}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/leader/invites",
                data={"first_name": "Sam", "last_name": "Lee", "email": "sam@example.com", "industry_domain": "Technology"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "Sam Lee")

    def test_leader_builder_assignment_uses_service(self):
        service = Mock()
        service.leader_assign_builder.return_value = {"ok": True, "builder_name": "Ava Morales"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch("/api/leader/members/client_1/builder-assignment", data={"builder_id": "bld_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["builder_name"], "Ava Morales")

    def test_leader_attorney_assignment_uses_service(self):
        service = Mock()
        service.leader_assign_attorney.return_value = {"ok": True, "attorney_name": "Sophia Chen"}
        with patch("app.api.service", return_value=service):
            response = self.client.patch("/api/leader/members/client_1/attorney-assignment", data={"attorney_id": "att_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["attorney_name"], "Sophia Chen")

    def test_admin_operations_uses_service(self):
        service = Mock()
        service.staff_session.return_value = {"display_name": "Maya Thompson", "role": "admin"}
        service.admin_operational_dashboard.return_value = {"metrics": {"openai_endpoint_calls": 4}, "portal_health": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/operations", headers={"Authorization": "Bearer ssess_admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["metrics"]["openai_endpoint_calls"], 4)

    def test_admin_operations_rejects_missing_token(self):
        service = Mock()
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/operations")
        self.assertEqual(response.status_code, 401)
        service.admin_operational_dashboard.assert_not_called()

    def test_admin_operations_rejects_non_admin_role(self):
        service = Mock()
        service.staff_session.return_value = {"display_name": "Ava Morales", "role": "leader"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/admin/operations", headers={"Authorization": "Bearer ssess_leader"})
        self.assertEqual(response.status_code, 403)
        service.admin_operational_dashboard.assert_not_called()

    def test_attorney_petition_generator_uses_service(self):
        service = Mock()
        service.attorney_petition_generator.return_value = {"ok": True, "status": "success", "executive_summary": "Draft"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/attorney/petition-generator", params={"client_id": "client_1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        service.attorney_petition_generator.assert_called_once_with("client_1")

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
        service.attorney_batch_intake_create.return_value = {"id": "bat_1", "counts": {"items": 2}}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/batch-intake",
                data={"client_id": "client_1", "member_context": "Large intake from counsel", "actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"},
                files={"file": ("intake.zip", b"PK\x03\x04", "application/zip")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "bat_1")
        service.attorney_batch_intake_create.assert_called_once()

    def test_attorney_member_evidence_uses_service(self):
        service = Mock()
        service.attorney_member_evidence.return_value = [{"id": "ev_1", "file_name": "review.pdf"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get(
                "/api/attorney/members/client_1/evidence",
                params={"actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["file_name"], "review.pdf")
        service.attorney_member_evidence.assert_called_once_with("client_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

    def test_batch_intake_sessions_uses_service(self):
        service = Mock()
        service.batch_intake_sessions.return_value = [{"id": "bat_1"}]
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/batch-intake/sessions", params={"client_id": "client_1", "actor_role": "leader"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["id"], "bat_1")
        service.batch_intake_sessions.assert_called_once_with("client_1", actor_role="leader", actor_email="")

    def test_attorney_batch_intake_session_uses_service(self):
        service = Mock()
        service.attorney_batch_intake_session.return_value = {"id": "bat_1", "items": []}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/attorney/batch-intake/bat_1", params={"actor_role": "attorney", "actor_email": "attorney@ascendhsi.com"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], "bat_1")
        service.attorney_batch_intake_session.assert_called_once_with("bat_1", actor_role="attorney", actor_email="attorney@ascendhsi.com")

    def test_update_attorney_batch_intake_item_uses_service(self):
        service = Mock()
        service.update_attorney_batch_intake_item.return_value = {"id": "bat_1", "items": [{"id": "bti_1"}]}
        with patch("app.api.service", return_value=service):
            response = self.client.patch(
                "/api/attorney/batch-intake/bat_1/items/bti_1",
                data={"criterion_code": "judging", "review_status": "ready", "actor_role": "leader"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "updated")
        service.update_attorney_batch_intake_item.assert_called_once_with("bat_1", "bti_1", criterion_code="judging", review_status="ready", actor_role="leader")

    def test_bulk_update_attorney_batch_intake_uses_service(self):
        service = Mock()
        service.bulk_update_attorney_batch_intake.return_value = {"id": "bat_1", "items": []}
        with patch("app.api.service", return_value=service):
            response = self.client.post(
                "/api/attorney/batch-intake/bat_1/bulk-update",
                data={"item_ids": "bti_1,bti_2", "review_status": "ready", "actor_role": "leader"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "updated")
        service.bulk_update_attorney_batch_intake.assert_called_once_with("bat_1", ["bti_1", "bti_2"], actor_role="leader", actor_email="", review_status="ready")

    def test_commit_attorney_batch_intake_uses_service(self):
        service = Mock()
        service.commit_attorney_batch_intake.return_value = {"ok": True, "status": "committed", "committed_count": 4}
        with patch("app.api.service", return_value=service):
            response = self.client.post("/api/attorney/batch-intake/bat_1/commit", data={"actor_role": "leader"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "committed")
        service.commit_attorney_batch_intake.assert_called_once_with("bat_1", actor_role="leader", actor_email="")

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
        service.member_profile.return_value = {"first_name": "Vas", "last_name": "D", "email": "vas@ascend.com"}
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/profile")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["first_name"], "Vas")
        service.member_profile.assert_called_once_with()

    def test_member_dashboard_rejects_non_member_token_as_json(self):
        service = Mock()
        service.member_session.side_effect = ValueError("Session not found")
        with patch("app.api.service", return_value=service):
            response = self.client.get("/api/member/dashboard", headers={"Authorization": "Bearer ssess_leader"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["content-type"].split(";")[0], "application/json")
        self.assertEqual(response.json()["detail"]["status"], "failed")

    def test_update_member_profile_calls_service(self):
        service = Mock()
        service.update_member_profile.return_value = {"first_name": "Vas", "last_name": "D", "email": "vas@ascend.com"}
        with patch("app.api.service", return_value=service):
            response = self.client.put(
                "/api/member/profile",
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

import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
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
            patch("app.services.load_google_drive_config", return_value={"folder_id": "folder", "folder_url": "url", "mode": "test"}),
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
        self.assertIn("member_uid", dashboard["members"][0])
        self.assertIn("builder_id", dashboard["members"][0])
        self.assertIn("attorney_id", dashboard["members"][0])
        self.assertIn("first_name", dashboard["members"][0])
        self.assertIn("last_name", dashboard["members"][0])
        self.assertIn("email", dashboard["members"][0])
        self.assertIn("phone", dashboard["members"][0])
        self.assertGreaterEqual(dashboard["members"][0]["member_uid"], 100001)
        self.assertGreaterEqual(dashboard["builders"][0]["builder_uid"], 200001)
        self.assertGreaterEqual(dashboard["attorneys"][0]["attorney_uid"], 300001)

    def test_staff_login_rejects_credentials_for_wrong_portal(self):
        with self.assertRaises(ValueError) as context:
            self.service.login_staff("leader@ascendhsi.com", DEFAULT_MEMBER_PASSWORD, {}, "attorney")

        self.assertIn("Leader Portal", str(context.exception))
        self.assertIn("Attorney Portal", str(context.exception))

        result = self.service.login_staff("leader@ascendhsi.com", DEFAULT_MEMBER_PASSWORD, {}, "leader")
        self.assertEqual(result["user"]["role"], "leader")

    def test_messages_use_numeric_actor_keys_with_legacy_visibility(self):
        leader_actor = self.service._actor_identity("leader", "leader@ascendhsi.com")
        member_actor = self.service._actor_identity("member", actor_client_id="client_1")

        self.assertEqual(leader_actor["key"], str(leader_actor["numeric_identifier"]))
        self.assertEqual(member_actor["key"], str(member_actor["numeric_identifier"]))
        self.assertNotEqual(leader_actor["key"], leader_actor["email"])
        self.assertNotEqual(member_actor["key"], member_actor["client_id"])

        sent = self.service.send_message(
            "leader",
            "Numeric identity check",
            "Please confirm the numeric message key.",
            "member",
            member_actor["key"],
            actor_email="leader@ascendhsi.com",
        )

        self.assertEqual(sent["sender_key"], leader_actor["key"])
        self.assertEqual(sent["recipient_key"], member_actor["key"])
        member_messages = self.service.message_center("member", actor_client_id="client_1")
        self.assertEqual(member_messages["unread_count"], 1)

        self.service.conn.execute(
            """
            INSERT INTO messages(
              id, thread_id, sender_role, sender_key, sender_name,
              recipient_role, recipient_key, recipient_name, subject, body
            )
            VALUES (?, ?, 'leader', ?, 'Ava Morales', 'member', ?, 'Vas', 'Legacy message', 'Legacy body')
            """,
            ("msg_legacy", "thd_legacy", leader_actor["legacy_key"], member_actor["legacy_key"]),
        )
        self.service.conn.commit()

        legacy_visible = self.service.message_center("member", actor_client_id="client_1")
        self.assertTrue(any(thread["thread_id"] == "thd_legacy" for thread in legacy_visible["threads"]))

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

    def test_leader_invite_sends_registration_link_and_member_registers(self):
        with patch.object(self.service, "_send_member_registration_email", return_value={"status": "sent", "sent_at": "2026-05-08T00:00:00"}) as send_email:
            result = self.service.leader_invite_member(
                "Mina",
                "Register",
                "mina.register@example.com",
                industry_domain="Technology",
            )

        self.assertEqual(result["email_delivery_status"], "sent")
        self.assertIn("registration=", result["registration_link"])
        send_email.assert_called_once()
        token = parse_qs(urlparse(result["registration_link"]).query)["registration"][0]
        invite = self.service.member_registration_invite(token)
        self.assertEqual(invite["email"], "mina.register@example.com")

        with self.assertRaises(ValueError):
            self.service.login_member("mina.register@example.com", DEFAULT_MEMBER_PASSWORD, {})

        registration = self.service.register_invited_member(token, "SecurePass123", "555-0100", {})
        self.assertEqual(registration["status"], "registered")
        self.assertEqual(registration["member"]["email"], "mina.register@example.com")
        login = self.service.login_member("mina.register@example.com", "SecurePass123", {})
        self.assertEqual(login["member"]["client_id"], result["client_id"])

    def test_leader_invite_resends_pending_invite_for_existing_email(self):
        with patch.object(self.service, "_send_member_registration_email", return_value={"status": "sent", "sent_at": "2026-05-08T00:00:00"}) as send_email:
            first = self.service.leader_invite_member("Mina", "Retry", "mina.retry@example.com", industry_domain="Technology")
            second = self.service.leader_invite_member("Mina", "Retry", "mina.retry@example.com", industry_domain="Technology")

        self.assertTrue(second["resent"])
        self.assertEqual(second["client_id"], first["client_id"])
        self.assertEqual(second["invite_id"], first["invite_id"])
        self.assertNotEqual(second["registration_link"], first["registration_link"])
        self.assertEqual(send_email.call_count, 2)
        invite_count = self.service.conn.execute(
            "SELECT COUNT(*) FROM member_registration_invites WHERE LOWER(email) = 'mina.retry@example.com'"
        ).fetchone()[0]
        account_count = self.service.conn.execute(
            "SELECT COUNT(*) FROM member_accounts WHERE LOWER(email) = 'mina.retry@example.com'"
        ).fetchone()[0]
        self.assertEqual(invite_count, 1)
        self.assertEqual(account_count, 1)

    def test_referral_program_tracks_member_submission_and_leader_status(self):
        summary = self.service.create_member_referral(
            "client_1",
            "case_1",
            "Riya Patel",
            "riya.referral@example.com",
            "",
            "Friend",
            "Strong technology leader interested in Ascend.",
        )

        referral = summary["referral"]
        self.assertEqual(referral["status"], "submitted")
        self.assertEqual(referral["referrer_bonus_amount"], 250)
        self.assertEqual(referral["referred_bonus_amount"], 500)

        leader_dashboard = self.service.leader_referral_dashboard()
        self.assertEqual(leader_dashboard["metrics"]["total_referrals"], 1)
        self.assertEqual(leader_dashboard["referrals"][0]["prospect_email"], "riya.referral@example.com")

        qualified = self.service.update_referral_status(referral["id"], "qualified", actor_email="leader@ascendhsi.com")
        updated = qualified["referrals"][0]
        self.assertEqual(updated["status"], "qualified")
        self.assertTrue(updated["eligible_at"])
        self.assertEqual(qualified["metrics"]["pending_payout_amount"], 750)

    def test_referral_program_can_be_disabled_and_amounts_configured(self):
        disabled = self.service.update_referral_settings(
            "false",
            "600",
            "300",
            promotion_name="Summer growth promo",
            eligibility_note="Paid after contract and six months.",
            actor_email="leader@ascendhsi.com",
        )

        self.assertFalse(disabled["settings"]["is_enabled"])
        self.assertEqual(disabled["settings"]["referred_bonus_amount"], 600)
        self.assertEqual(disabled["settings"]["referrer_bonus_amount"], 300)

        with self.assertRaises(ValueError):
            self.service.create_member_referral("client_1", "case_1", "Paused Prospect", "paused@example.com")

        self.service.update_referral_settings(
            "true",
            "600",
            "300",
            promotion_name="Summer growth promo",
            eligibility_note="Paid after contract and six months.",
            actor_email="leader@ascendhsi.com",
        )
        summary = self.service.create_member_referral("client_1", "case_1", "Active Prospect", "active@example.com")
        self.assertEqual(summary["referral"]["referred_bonus_amount"], 600)
        self.assertEqual(summary["referral"]["referrer_bonus_amount"], 300)

    def test_leader_invite_blocks_registered_existing_member_email(self):
        with patch.object(self.service, "_send_member_registration_email", return_value={"status": "sent", "sent_at": "2026-05-08T00:00:00"}):
            result = self.service.leader_invite_member("Mina", "Registered", "mina.registered@example.com", industry_domain="Technology")
        token = parse_qs(urlparse(result["registration_link"]).query)["registration"][0]
        self.service.register_invited_member(token, "SecurePass123", "", {})

        with self.assertRaises(ValueError) as context:
            self.service.leader_invite_member("Mina", "Registered", "mina.registered@example.com", industry_domain="Technology")

        self.assertIn("registered member", str(context.exception).lower())

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

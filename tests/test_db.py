import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db import initialize, one, rows, seed_default_case


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_initialize_creates_criteria(self):
        criteria = rows(self.conn, "SELECT code FROM criteria")
        self.assertGreaterEqual(len(criteria), 8)
        self.assertIn("judging", {item["code"] for item in criteria})
        self.assertIn("other", {item["code"] for item in criteria})

    def test_initialize_persists_criteria_display_order(self):
        criteria = rows(self.conn, "SELECT code, display_order FROM criteria ORDER BY display_order, name")
        self.assertEqual(criteria[0]["display_order"], 1)
        self.assertEqual(criteria[0]["code"], "awards")
        self.assertEqual(criteria[-1]["code"], "other")

    def test_initialize_creates_planner_table(self):
        tables = rows(self.conn, "SELECT name FROM sqlite_master WHERE type = 'table'")
        self.assertIn("planner_items", {item["name"] for item in tables})

    def test_initialize_creates_member_profile_table(self):
        tables = rows(self.conn, "SELECT name FROM sqlite_master WHERE type = 'table'")
        self.assertIn("member_profiles", {item["name"] for item in tables})

    def test_initialize_creates_member_account_tables(self):
        tables = rows(self.conn, "SELECT name FROM sqlite_master WHERE type = 'table'")
        names = {item["name"] for item in tables}
        self.assertIn("member_accounts", names)
        self.assertIn("member_sessions", names)
        self.assertIn("profile_builders", names)
        self.assertIn("profile_builder_accounts", names)
        self.assertIn("profile_builder_sessions", names)
        self.assertIn("builder_member_assignments", names)
        self.assertIn("opportunity_library", names)
        self.assertIn("attorneys", names)
        self.assertIn("staff_accounts", names)
        self.assertIn("staff_sessions", names)
        self.assertIn("attorney_member_assignments", names)
        self.assertIn("member_registration_invites", names)
        self.assertIn("operational_events", names)
        self.assertIn("messages", names)
        self.assertIn("support_tickets", names)
        self.assertIn("support_ticket_attachments", names)
        self.assertIn("batch_intake_sessions", names)
        self.assertIn("batch_intake_items", names)
        self.assertIn("admin_cost_snapshots", names)
        self.assertIn("marketing_leads", names)

    def test_account_tables_track_last_login_audit_fields(self):
        for table in ("member_accounts", "profile_builder_accounts", "staff_accounts"):
            columns = rows(self.conn, f"PRAGMA table_info({table})")
            names = {item["name"] for item in columns}
            self.assertIn("last_login_at", names)
            self.assertIn("last_login_ip", names)
            self.assertIn("last_login_user_agent", names)

        columns = rows(self.conn, "PRAGMA table_info(operational_events)")
        names = {item["name"] for item in columns}
        self.assertIn("actor_role", names)
        self.assertIn("actor_key", names)

    def test_seed_default_case(self):
        seed_default_case(self.conn, "client_1", "case_1", "Vas")
        client = one(self.conn, "SELECT * FROM clients WHERE id = ?", ("client_1",))
        case = one(self.conn, "SELECT * FROM cases WHERE id = ?", ("case_1",))
        self.assertEqual(client["display_name"], "Vas")
        self.assertEqual(case["case_type"], "EB1A")


if __name__ == "__main__":
    unittest.main()

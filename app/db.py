import sqlite3
from pathlib import Path
import re
from typing import Any

from app.config import AppConfig


CRITERIA = [
    ("awards", "Awards and Prizes", "Nationally or internationally recognized prizes or awards."),
    ("memberships", "Memberships", "Memberships requiring outstanding achievement."),
    ("published_material", "Published Material", "Published material about the member and their work."),
    ("judging", "Judging", "Judging the work of others in the field."),
    ("original_contributions", "Original Contributions", "Original contributions of major significance."),
    ("scholarly_articles", "Scholarly Articles", "Authorship of scholarly articles."),
    ("leading_critical_role", "Leading or Critical Role", "Leading or critical role for distinguished organizations."),
    ("high_salary", "High Salary", "High salary or remuneration compared to others in the field."),
    ("comparable_evidence", "Comparable Evidence", "Comparable evidence when criteria do not readily apply."),
    ("other", "Other", "Documents that do not clearly match an identified EB1A evidence category."),
]


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS clients (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_type TEXT NOT NULL DEFAULT 'EB1A',
  status TEXT NOT NULL DEFAULT 'evidence_collection',
  readiness_score INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS criteria (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  display_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS evidence_items (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  criterion_code TEXT NOT NULL REFERENCES criteria(code),
  document_type TEXT NOT NULL DEFAULT 'Other',
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  file_name TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  local_path TEXT NOT NULL,
  drive_mirror_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  ai_summary TEXT NOT NULL DEFAULT '',
  quality_score INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_folders (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  criterion_code TEXT NOT NULL REFERENCES criteria(code),
  parent_id TEXT REFERENCES evidence_folders(id),
  name TEXT NOT NULL,
  color TEXT NOT NULL DEFAULT '#1f6f5b',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evidence_search (
  evidence_id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  file_name TEXT NOT NULL DEFAULT '',
  ai_summary TEXT NOT NULL DEFAULT '',
  client_id TEXT NOT NULL DEFAULT '',
  case_id TEXT NOT NULL DEFAULT '',
  criterion_code TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  case_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planner_items (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  criterion_code TEXT REFERENCES criteria(code),
  folder_id TEXT REFERENCES evidence_folders(id),
  member_role TEXT NOT NULL DEFAULT '',
  issued_by TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  planned_completion_date TEXT NOT NULL DEFAULT '',
  actual_completion_date TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'planned',
  comments TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS member_profiles (
  client_id TEXT PRIMARY KEY REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  first_name TEXT NOT NULL DEFAULT '',
  last_name TEXT NOT NULL DEFAULT '',
  preferred_name TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '',
  date_of_birth TEXT NOT NULL DEFAULT '',
  country_of_citizenship TEXT NOT NULL DEFAULT '',
  country_of_residence TEXT NOT NULL DEFAULT '',
  city_state TEXT NOT NULL DEFAULT '',
  current_title TEXT NOT NULL DEFAULT '',
  current_employer TEXT NOT NULL DEFAULT '',
  employer_type TEXT NOT NULL DEFAULT '',
  industry_domain TEXT NOT NULL DEFAULT '',
  primary_field TEXT NOT NULL DEFAULT '',
  specialization TEXT NOT NULL DEFAULT '',
  years_experience TEXT NOT NULL DEFAULT '',
  highest_degree TEXT NOT NULL DEFAULT '',
  degree_field TEXT NOT NULL DEFAULT '',
  institution TEXT NOT NULL DEFAULT '',
  graduation_year TEXT NOT NULL DEFAULT '',
  linkedin_url TEXT NOT NULL DEFAULT '',
  personal_website TEXT NOT NULL DEFAULT '',
  google_scholar_url TEXT NOT NULL DEFAULT '',
  orcid_id TEXT NOT NULL DEFAULT '',
  biography TEXT NOT NULL DEFAULT '',
  top_achievements TEXT NOT NULL DEFAULT '',
  awards_summary TEXT NOT NULL DEFAULT '',
  memberships_summary TEXT NOT NULL DEFAULT '',
  publications_summary TEXT NOT NULL DEFAULT '',
  judging_summary TEXT NOT NULL DEFAULT '',
  original_contributions_summary TEXT NOT NULL DEFAULT '',
  leading_roles_summary TEXT NOT NULL DEFAULT '',
  media_summary TEXT NOT NULL DEFAULT '',
  salary_summary TEXT NOT NULL DEFAULT '',
  proposed_final_merits_summary TEXT NOT NULL DEFAULT '',
  target_filing_window TEXT NOT NULL DEFAULT '',
  profile_confirmed INTEGER NOT NULL DEFAULT 0,
  profile_confirmed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS member_accounts (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_password_changed_at TEXT,
  last_login_at TEXT,
  last_login_ip TEXT NOT NULL DEFAULT '',
  last_login_user_agent TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS member_sessions (
  token TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES member_accounts(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profile_builders (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profile_builder_accounts (
  id TEXT PRIMARY KEY,
  builder_id TEXT NOT NULL REFERENCES profile_builders(id),
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_password_changed_at TEXT,
  last_login_at TEXT,
  last_login_ip TEXT NOT NULL DEFAULT '',
  last_login_user_agent TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS profile_builder_sessions (
  token TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES profile_builder_accounts(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attorneys (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  email TEXT NOT NULL DEFAULT '',
  focus_domains TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS staff_accounts (
  id TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  actor_key TEXT NOT NULL,
  username TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_password_changed_at TEXT,
  last_login_at TEXT,
  last_login_ip TEXT NOT NULL DEFAULT '',
  last_login_user_agent TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS staff_sessions (
  token TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES staff_accounts(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS builder_member_assignments (
  id TEXT PRIMARY KEY,
  builder_id TEXT NOT NULL REFERENCES profile_builders(id),
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attorney_member_assignments (
  id TEXT PRIMARY KEY,
  attorney_id TEXT NOT NULL REFERENCES attorneys(id),
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS member_registration_invites (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  email TEXT NOT NULL,
  invited_by TEXT NOT NULL DEFAULT 'leader',
  status TEXT NOT NULL DEFAULT 'invited',
  token_hash TEXT NOT NULL DEFAULT '',
  token_expires_at TEXT NOT NULL DEFAULT '',
  email_delivery_status TEXT NOT NULL DEFAULT 'pending',
  email_sent_at TEXT,
  email_error TEXT NOT NULL DEFAULT '',
  invite_sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  registered_at TEXT,
  notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS opportunity_library (
  id TEXT PRIMARY KEY,
  criterion_code TEXT NOT NULL REFERENCES criteria(code),
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  target_evidence_type TEXT NOT NULL DEFAULT 'Other',
  suggested_due_days INTEGER NOT NULL DEFAULT 14,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operational_events (
  id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'info',
  portal TEXT NOT NULL DEFAULT '',
  client_id TEXT NOT NULL DEFAULT '',
  case_id TEXT NOT NULL DEFAULT '',
  endpoint TEXT NOT NULL DEFAULT '',
  error_code TEXT NOT NULL DEFAULT '',
  message TEXT NOT NULL DEFAULT '',
  metadata TEXT NOT NULL DEFAULT '{}',
  actor_role TEXT NOT NULL DEFAULT '',
  actor_key TEXT NOT NULL DEFAULT '',
  related_client_id TEXT NOT NULL DEFAULT '',
  related_case_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_issue_logs (
  bug_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  portal TEXT NOT NULL DEFAULT '',
  section TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'P2',
  status TEXT NOT NULL DEFAULT 'open',
  description TEXT NOT NULL DEFAULT '',
  reported_by TEXT NOT NULL DEFAULT '',
  created_by_role TEXT NOT NULL DEFAULT 'admin',
  created_by_key TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at TEXT,
  aws_table_name TEXT NOT NULL DEFAULT '',
  aws_sync_status TEXT NOT NULL DEFAULT 'pending',
  aws_sync_message TEXT NOT NULL DEFAULT '',
  last_synced_at TEXT,
  deleted_at TEXT,
  deleted_by_key TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS product_feature_requests (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  request_type TEXT NOT NULL DEFAULT 'enhancement',
  target_portals TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'P2',
  status TEXT NOT NULL DEFAULT 'backlog',
  business_value TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  acceptance_criteria TEXT NOT NULL DEFAULT '',
  requested_by TEXT NOT NULL DEFAULT '',
  created_by_role TEXT NOT NULL DEFAULT 'leader',
  created_by_key TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_feature_request_attachments (
  id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL REFERENCES product_feature_requests(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  local_path TEXT NOT NULL DEFAULT '',
  drive_path TEXT NOT NULL DEFAULT '',
  drive_file_id TEXT NOT NULL DEFAULT '',
  drive_web_url TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS critical_role_projects (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  organization_name TEXT NOT NULL DEFAULT '',
  organization_unit TEXT NOT NULL DEFAULT '',
  organization_location TEXT NOT NULL DEFAULT '',
  organization_website TEXT NOT NULL DEFAULT '',
  employment_type TEXT NOT NULL DEFAULT '',
  role_title TEXT NOT NULL DEFAULT '',
  role_start_date TEXT NOT NULL DEFAULT '',
  role_end_date TEXT NOT NULL DEFAULT '',
  is_current_role INTEGER NOT NULL DEFAULT 0,
  project_name TEXT NOT NULL DEFAULT '',
  project_start_date TEXT NOT NULL DEFAULT '',
  project_end_date TEXT NOT NULL DEFAULT '',
  project_status TEXT NOT NULL DEFAULT 'Active',
  organization_achievements TEXT NOT NULL DEFAULT '',
  organization_distinctiveness TEXT NOT NULL DEFAULT '',
  role_summary TEXT NOT NULL DEFAULT '',
  role_responsibilities TEXT NOT NULL DEFAULT '',
  role_evolution TEXT NOT NULL DEFAULT '',
  leadership_scope TEXT NOT NULL DEFAULT '',
  cross_functional_partners TEXT NOT NULL DEFAULT '',
  project_summary TEXT NOT NULL DEFAULT '',
  business_need TEXT NOT NULL DEFAULT '',
  strategic_importance TEXT NOT NULL DEFAULT '',
  contributions_summary TEXT NOT NULL DEFAULT '',
  innovation_originality TEXT NOT NULL DEFAULT '',
  business_value_summary TEXT NOT NULL DEFAULT '',
  quantitative_metrics TEXT NOT NULL DEFAULT '',
  revenue_impact TEXT NOT NULL DEFAULT '',
  cost_savings TEXT NOT NULL DEFAULT '',
  efficiency_gain TEXT NOT NULL DEFAULT '',
  user_or_customer_impact TEXT NOT NULL DEFAULT '',
  market_or_geographic_impact TEXT NOT NULL DEFAULT '',
  compliance_or_risk_impact TEXT NOT NULL DEFAULT '',
  peer_distinction_summary TEXT NOT NULL DEFAULT '',
  mentorship_leadership TEXT NOT NULL DEFAULT '',
  executive_visibility TEXT NOT NULL DEFAULT '',
  evidence_available TEXT NOT NULL DEFAULT '',
  attorney_friendly_summary TEXT NOT NULL DEFAULT '',
  workflow_status TEXT NOT NULL DEFAULT 'draft',
  submitted_at TEXT,
  export_evidence_id TEXT NOT NULL DEFAULT '',
  export_generated_at TEXT,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS original_contribution_entries (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  contribution_title TEXT NOT NULL DEFAULT '',
  contribution_category TEXT NOT NULL DEFAULT 'Work-related',
  field_of_expertise TEXT NOT NULL DEFAULT '',
  job_title TEXT NOT NULL DEFAULT '',
  organization_name TEXT NOT NULL DEFAULT '',
  project_name TEXT NOT NULL DEFAULT '',
  contribution_start_date TEXT NOT NULL DEFAULT '',
  contribution_end_date TEXT NOT NULL DEFAULT '',
  contribution_status TEXT NOT NULL DEFAULT 'Completed',
  originality_summary TEXT NOT NULL DEFAULT '',
  challenging_paradigms TEXT NOT NULL DEFAULT '',
  prior_state_of_field TEXT NOT NULL DEFAULT '',
  work_vs_external_context TEXT NOT NULL DEFAULT '',
  personal_role TEXT NOT NULL DEFAULT '',
  distinct_contribution_summary TEXT NOT NULL DEFAULT '',
  technical_or_business_problem TEXT NOT NULL DEFAULT '',
  solution_or_innovation TEXT NOT NULL DEFAULT '',
  unique_features TEXT NOT NULL DEFAULT '',
  impact_metrics TEXT NOT NULL DEFAULT '',
  adoption_scale TEXT NOT NULL DEFAULT '',
  beneficiary_summary TEXT NOT NULL DEFAULT '',
  time_savings TEXT NOT NULL DEFAULT '',
  cost_savings TEXT NOT NULL DEFAULT '',
  revenue_impact TEXT NOT NULL DEFAULT '',
  quality_or_risk_impact TEXT NOT NULL DEFAULT '',
  field_wide_impact TEXT NOT NULL DEFAULT '',
  recognition_and_influence TEXT NOT NULL DEFAULT '',
  media_or_public_mentions TEXT NOT NULL DEFAULT '',
  adoption_letters_targets TEXT NOT NULL DEFAULT '',
  evidence_available TEXT NOT NULL DEFAULT '',
  attorney_friendly_summary TEXT NOT NULL DEFAULT '',
  workflow_status TEXT NOT NULL DEFAULT 'draft',
  submitted_at TEXT,
  export_evidence_id TEXT NOT NULL DEFAULT '',
  export_generated_at TEXT,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  thread_id TEXT NOT NULL,
  parent_message_id TEXT REFERENCES messages(id),
  sender_role TEXT NOT NULL,
  sender_key TEXT NOT NULL,
  sender_name TEXT NOT NULL,
  sender_email TEXT NOT NULL DEFAULT '',
  recipient_role TEXT NOT NULL,
  recipient_key TEXT NOT NULL,
  recipient_name TEXT NOT NULL,
  recipient_email TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  urgent INTEGER NOT NULL DEFAULT 0,
  is_read INTEGER NOT NULL DEFAULT 0,
  read_at TEXT,
  deleted_by_sender INTEGER NOT NULL DEFAULT 0,
  deleted_by_recipient INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_tickets (
  id TEXT PRIMARY KEY,
  ticket_number TEXT NOT NULL UNIQUE,
  reporter_role TEXT NOT NULL,
  reporter_key TEXT NOT NULL,
  reporter_name TEXT NOT NULL,
  reporter_email TEXT NOT NULL DEFAULT '',
  reporter_client_id TEXT NOT NULL DEFAULT '',
  reporter_case_id TEXT NOT NULL DEFAULT '',
  related_client_id TEXT NOT NULL DEFAULT '',
  related_case_id TEXT NOT NULL DEFAULT '',
  portal TEXT NOT NULL DEFAULT '',
  issue_location TEXT NOT NULL DEFAULT '',
  current_url TEXT NOT NULL DEFAULT '',
  short_description TEXT NOT NULL,
  details TEXT NOT NULL DEFAULT '',
  priority TEXT NOT NULL DEFAULT 'normal',
  is_blocking INTEGER NOT NULL DEFAULT 0,
  screenshot_url TEXT NOT NULL DEFAULT '',
  screenshot_notes TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  category TEXT NOT NULL DEFAULT 'other',
  behavior_assessment TEXT NOT NULL DEFAULT 'needs_verification',
  user_summary TEXT NOT NULL DEFAULT '',
  admin_summary TEXT NOT NULL DEFAULT '',
  reasoning TEXT NOT NULL DEFAULT '',
  root_cause TEXT NOT NULL DEFAULT '',
  next_actions_json TEXT NOT NULL DEFAULT '[]',
  triage_source TEXT NOT NULL DEFAULT '',
  mailbox_thread_id TEXT NOT NULL DEFAULT '',
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS support_ticket_attachments (
  id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  local_path TEXT NOT NULL DEFAULT '',
  drive_path TEXT NOT NULL DEFAULT '',
  drive_file_id TEXT NOT NULL DEFAULT '',
  drive_web_url TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recommendation_letters (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  letter_kind TEXT NOT NULL DEFAULT 'independent',
  criterion_code TEXT NOT NULL DEFAULT '',
  project_type TEXT NOT NULL DEFAULT '',
  project_id TEXT NOT NULL DEFAULT '',
  recommender_name TEXT NOT NULL DEFAULT '',
  recommender_title TEXT NOT NULL DEFAULT '',
  recommender_organization TEXT NOT NULL DEFAULT '',
  recommender_relationship TEXT NOT NULL DEFAULT '',
  attorney_notes TEXT NOT NULL DEFAULT '',
  prompt_config_json TEXT NOT NULL DEFAULT '{}',
  letter_json TEXT NOT NULL DEFAULT '{}',
  plain_text TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'generated',
  generated_by_key TEXT NOT NULL DEFAULT '',
  approved_at TEXT,
  sent_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS batch_intake_sessions (
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  uploaded_zip_name TEXT NOT NULL,
  source_note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft',
  extraction_root TEXT NOT NULL DEFAULT '',
  item_count INTEGER NOT NULL DEFAULT 0,
  committed_count INTEGER NOT NULL DEFAULT 0,
  skipped_file_count INTEGER NOT NULL DEFAULT 0,
  skipped_files_json TEXT NOT NULL DEFAULT '[]',
  created_by_role TEXT NOT NULL DEFAULT 'attorney',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  committed_at TEXT
);

CREATE TABLE IF NOT EXISTS batch_intake_items (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES batch_intake_sessions(id) ON DELETE CASCADE,
  client_id TEXT NOT NULL REFERENCES clients(id),
  case_id TEXT NOT NULL REFERENCES cases(id),
  zip_path TEXT NOT NULL DEFAULT '',
  original_file_name TEXT NOT NULL,
  extracted_path TEXT NOT NULL DEFAULT '',
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  criterion_code TEXT NOT NULL REFERENCES criteria(code),
  document_type TEXT NOT NULL DEFAULT 'Other',
  title TEXT NOT NULL,
  ai_description TEXT NOT NULL DEFAULT '',
  quality_score INTEGER NOT NULL DEFAULT 0,
  confidence INTEGER NOT NULL DEFAULT 0,
  analysis_source TEXT NOT NULL DEFAULT '',
  suggested_folder_name TEXT NOT NULL DEFAULT '',
  folder_decision TEXT NOT NULL DEFAULT 'root',
  assigned_folder_id TEXT REFERENCES evidence_folders(id),
  assigned_folder_name TEXT NOT NULL DEFAULT '',
  duplicate_evidence_id TEXT NOT NULL DEFAULT '',
  duplicate_action TEXT NOT NULL DEFAULT '',
  review_status TEXT NOT NULL DEFAULT 'ready',
  commit_evidence_id TEXT NOT NULL DEFAULT '',
  commit_message TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_cost_snapshots (
  source TEXT PRIMARY KEY,
  refreshed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status TEXT NOT NULL DEFAULT 'pending',
  payload TEXT NOT NULL DEFAULT '{}',
  detail TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS marketing_leads (
  id TEXT PRIMARY KEY,
  lead_source TEXT NOT NULL DEFAULT 'visa_compass',
  campaign TEXT NOT NULL DEFAULT 'Ascend Visa Compass',
  email TEXT NOT NULL,
  phone TEXT NOT NULL DEFAULT '',
  name TEXT NOT NULL DEFAULT '',
  source_url TEXT NOT NULL DEFAULT '',
  top_match TEXT NOT NULL DEFAULT '',
  match_label TEXT NOT NULL DEFAULT '',
  readiness_score INTEGER NOT NULL DEFAULT 0,
  answers_json TEXT NOT NULL DEFAULT '{}',
  result_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'new',
  user_agent TEXT NOT NULL DEFAULT '',
  client_ip TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class CursorAdapter:
    def __init__(self, cursor: Any, driver: str):
        self.cursor = cursor
        self.driver = driver

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        return dict(row)

    def fetchall(self):
        values = self.cursor.fetchall()
        if values and isinstance(values[0], dict):
            return values
        return [dict(row) for row in values]


class ConnectionAdapter:
    def __init__(self, driver: str, connection: Any):
        self.driver = driver
        self.connection = connection

    def _normalize_query(self, query: str) -> str:
        normalized = query
        if self.driver == "postgres":
            normalized = normalized.replace("CURRENT_TIMESTAMP", "(CURRENT_TIMESTAMP::text)")
            normalized = normalized.replace("datetime('now', '-30 day')", "((CURRENT_TIMESTAMP - INTERVAL '30 days')::text)")
            normalized = normalized.replace("datetime('now', '-14 day')", "((CURRENT_TIMESTAMP - INTERVAL '14 days')::text)")
            normalized = normalized.replace("datetime('now', '-1 day')", "((CURRENT_TIMESTAMP - INTERVAL '1 day')::text)")
            normalized = normalized.replace("%", "%%")
            normalized = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", normalized)
            normalized = normalized.replace("?", "%s")
        return normalized

    def execute(self, query: str, params: tuple[Any, ...] = ()):
        cursor = self.connection.execute(self._normalize_query(query), params)
        return CursorAdapter(cursor, self.driver)

    def executemany(self, query: str, seq_of_params):
        if self.driver == "sqlite":
            cursor = self.connection.executemany(query, seq_of_params)
        else:
            cursor = self.connection.cursor()
            cursor.executemany(self._normalize_query(query), seq_of_params)
        return CursorAdapter(cursor, self.driver)

    def executescript(self, script: str) -> None:
        if self.driver == "sqlite":
            self.connection.executescript(script)
            return
        for statement in _split_sql_script(_normalize_schema_for_postgres(script)):
            self.connection.execute(statement)

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def _split_sql_script(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in script.splitlines():
        current.append(line)
        if line.strip().endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
    tail = "\n".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _normalize_schema_for_postgres(script: str) -> str:
    return script.replace(" DEFAULT CURRENT_TIMESTAMP", " DEFAULT (CURRENT_TIMESTAMP::text)")


def connect(config_or_path: AppConfig | Path) -> ConnectionAdapter | sqlite3.Connection:
    if isinstance(config_or_path, AppConfig):
        if config_or_path.database_url:
            return _postgres_connect(config_or_path.database_url)
        return _sqlite_connect(config_or_path.database_path)
    return _sqlite_connect(config_or_path)


def _sqlite_connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _postgres_connect(database_url: str) -> ConnectionAdapter:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("psycopg is required when ASCEND_DATABASE_URL is set.") from exc
    conn = psycopg.connect(database_url, row_factory=dict_row)
    return ConnectionAdapter("postgres", conn)


def _driver(conn: Any) -> str:
    return getattr(conn, "driver", "sqlite")


def initialize(conn: ConnectionAdapter | sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    seed_criteria(conn)
    ensure_column(conn, "evidence_items", "drive_path", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "evidence_items", "drive_file_id", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "evidence_items", "drive_web_url", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "evidence_items", "archive_path", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "evidence_items", "archived_at", "TEXT")
    ensure_column(conn, "evidence_items", "archive_reason", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "evidence_items", "folder_id", "TEXT REFERENCES evidence_folders(id)")
    ensure_column(conn, "evidence_items", "document_type", "TEXT NOT NULL DEFAULT 'Other'")
    for table in ("member_accounts", "profile_builder_accounts", "staff_accounts"):
        ensure_column(conn, table, "last_login_at", "TEXT")
        ensure_column(conn, table, "last_login_ip", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, table, "last_login_user_agent", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "member_profiles", "industry_domain", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "messages", "thread_id", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "messages", "parent_message_id", "TEXT REFERENCES messages(id)")
    ensure_column(conn, "operational_events", "actor_role", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "operational_events", "actor_key", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "operational_events", "related_client_id", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "operational_events", "related_case_id", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "product_issue_logs", "closed_at", "TEXT")
    ensure_column(conn, "product_issue_logs", "aws_table_name", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "product_issue_logs", "aws_sync_status", "TEXT NOT NULL DEFAULT 'pending'")
    ensure_column(conn, "product_issue_logs", "aws_sync_message", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "product_issue_logs", "last_synced_at", "TEXT")
    ensure_column(conn, "product_issue_logs", "deleted_at", "TEXT")
    ensure_column(conn, "product_issue_logs", "deleted_by_key", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "product_feature_requests", "acceptance_criteria", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "recommendation_letters", "approved_at", "TEXT")
    ensure_column(conn, "recommendation_letters", "sent_at", "TEXT")
    ensure_column(conn, "critical_role_projects", "workflow_status", "TEXT NOT NULL DEFAULT 'draft'")
    ensure_column(conn, "critical_role_projects", "submitted_at", "TEXT")
    ensure_column(conn, "critical_role_projects", "export_evidence_id", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "critical_role_projects", "export_generated_at", "TEXT")
    ensure_column(conn, "critical_role_projects", "deleted_at", "TEXT")
    ensure_column(conn, "original_contribution_entries", "workflow_status", "TEXT NOT NULL DEFAULT 'draft'")
    ensure_column(conn, "original_contribution_entries", "submitted_at", "TEXT")
    ensure_column(conn, "original_contribution_entries", "job_title", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "original_contribution_entries", "export_evidence_id", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "original_contribution_entries", "export_generated_at", "TEXT")
    ensure_column(conn, "original_contribution_entries", "deleted_at", "TEXT")
    ensure_column(conn, "tasks", "assigned_by_builder_id", "TEXT REFERENCES profile_builders(id)")
    ensure_column(conn, "tasks", "opportunity_id", "TEXT REFERENCES opportunity_library(id)")
    ensure_column(conn, "tasks", "criterion_code", "TEXT REFERENCES criteria(code)")
    ensure_column(conn, "tasks", "due_date", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "support_tickets", "priority", "TEXT NOT NULL DEFAULT 'normal'")
    ensure_column(conn, "support_tickets", "is_blocking", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "member_registration_invites", "token_hash", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "member_registration_invites", "token_expires_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "member_registration_invites", "email_delivery_status", "TEXT NOT NULL DEFAULT 'pending'")
    ensure_column(conn, "member_registration_invites", "email_sent_at", "TEXT")
    ensure_column(conn, "member_registration_invites", "email_error", "TEXT NOT NULL DEFAULT ''")
    ensure_column(conn, "criteria", "display_order", "INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def seed_criteria(conn: ConnectionAdapter | sqlite3.Connection) -> None:
    rows_to_seed = [(code, name, description, index) for index, (code, name, description) in enumerate(CRITERIA, start=1)]
    if _driver(conn) == "postgres":
        for code, name, description, display_order in rows_to_seed:
            conn.execute(
                """
                INSERT INTO criteria(code, name, description, display_order)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (code)
                DO UPDATE SET
                  name = EXCLUDED.name,
                  description = EXCLUDED.description,
                  display_order = EXCLUDED.display_order
                """,
                (code, name, description, display_order),
            )
    else:
        conn.executemany(
            "INSERT OR IGNORE INTO criteria(code, name, description, display_order) VALUES (?, ?, ?, ?)",
            rows_to_seed,
        )
        for code, name, description, display_order in rows_to_seed:
            conn.execute(
                "UPDATE criteria SET name = ?, description = ?, display_order = ? WHERE code = ?",
                (name, description, display_order, code),
            )


def ensure_column(conn: ConnectionAdapter | sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if _driver(conn) == "postgres":
        existing_rows = rows(
            conn,
            """
            SELECT column_name AS name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table,),
        )
        existing = {row["name"] for row in existing_rows}
    else:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition.split()[0] if False else column + ' ' + definition}")


def seed_default_case(conn: ConnectionAdapter | sqlite3.Connection, client_id: str, case_id: str, display_name: str) -> None:
    if _driver(conn) == "postgres":
        conn.execute(
            "INSERT INTO clients(id, display_name) VALUES (?, ?) ON CONFLICT (id) DO NOTHING",
            (client_id, display_name),
        )
        conn.execute(
            "INSERT INTO cases(id, client_id, readiness_score) VALUES (?, ?, ?) ON CONFLICT (id) DO NOTHING",
            (case_id, client_id, 18),
        )
    else:
        conn.execute(
            "INSERT OR IGNORE INTO clients(id, display_name) VALUES (?, ?)",
            (client_id, display_name),
        )
        conn.execute(
            "INSERT OR IGNORE INTO cases(id, client_id, readiness_score) VALUES (?, ?, ?)",
            (case_id, client_id, 18),
        )
    conn.commit()


def rows(conn: ConnectionAdapter | sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    result = conn.execute(query, params).fetchall()
    if result and isinstance(result[0], dict):
        return result
    return [dict(row) for row in result]


def one(conn: ConnectionAdapter | sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return row if isinstance(row, dict) else dict(row)

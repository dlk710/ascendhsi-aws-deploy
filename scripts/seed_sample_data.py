import io
import json
import shutil
import sqlite3
import sys
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ROOT, load_app_config
from app.services import EvidenceService


PASSWORD = "Ascend123!"

MEMBERS = [
    {
        "client_id": "client_vas_001",
        "case_id": "case_eb1a_001",
        "display_name": "Vasanth Rao",
        "first_name": "Vasanth",
        "last_name": "Rao",
        "preferred_name": "Vas",
        "email": "vas@ascendhsi.com",
        "status": "evidence_collection",
        "readiness_score": 68,
        "industry_domain": "Technology",
        "primary_field": "Applied AI",
        "current_title": "Principal AI Architect",
        "current_employer": "Synapse Cloud",
        "biography": "AI leader focused on large-scale enterprise decision systems.",
        "attorney_email": "marcus.reed@ascendhsi.com",
    },
    {
        "client_id": "client_priya_002",
        "case_id": "case_eb1a_002",
        "display_name": "Priya Nair",
        "first_name": "Priya",
        "last_name": "Nair",
        "preferred_name": "Priya",
        "email": "priya.nair@ascendhsi.com",
        "status": "intake",
        "readiness_score": 32,
        "industry_domain": "Healthcare",
        "primary_field": "Digital Health",
        "current_title": "Clinical Data Scientist",
        "current_employer": "Northwell Analytics",
        "biography": "Builds clinical analytics programs across provider systems.",
        "attorney_email": "marcus.reed@ascendhsi.com",
    },
    {
        "client_id": "client_daniel_003",
        "case_id": "case_eb1a_003",
        "display_name": "Daniel Kim",
        "first_name": "Daniel",
        "last_name": "Kim",
        "preferred_name": "Daniel",
        "email": "daniel.kim@ascendhsi.com",
        "status": "petition_drafting",
        "readiness_score": 84,
        "industry_domain": "Pharma",
        "primary_field": "Biostatistics",
        "current_title": "Director of Biostatistics",
        "current_employer": "Helix Therapeutics",
        "biography": "Leads statistical design and publication strategy for oncology programs.",
        "attorney_email": "attorney@ascendhsi.com",
    },
    {
        "client_id": "client_elena_004",
        "case_id": "case_eb1a_004",
        "display_name": "Elena Rodriguez",
        "first_name": "Elena",
        "last_name": "Rodriguez",
        "preferred_name": "Elena",
        "email": "elena.rodriguez@ascendhsi.com",
        "status": "evidence_collection",
        "readiness_score": 57,
        "industry_domain": "Insurance",
        "primary_field": "Claims Analytics",
        "current_title": "Head of Data Science",
        "current_employer": "Aegis Mutual",
        "biography": "Builds claims intelligence systems and enterprise fraud programs.",
        "attorney_email": "marcus.reed@ascendhsi.com",
    },
    {
        "client_id": "client_omar_005",
        "case_id": "case_eb1a_005",
        "display_name": "Omar Hassan",
        "first_name": "Omar",
        "last_name": "Hassan",
        "preferred_name": "Omar",
        "email": "omar.hassan@ascendhsi.com",
        "status": "legal_review",
        "readiness_score": 76,
        "industry_domain": "Technology",
        "primary_field": "Cybersecurity",
        "current_title": "Security Research Lead",
        "current_employer": "Aperture Defense",
        "biography": "Leads vulnerability research and public cyber defense thought leadership.",
        "attorney_email": "marcus.reed@ascendhsi.com",
    },
]

ATTORNEYS = [
    {"id": "att_sophia_001", "display_name": "Sophia Chen", "email": "attorney@ascendhsi.com", "focus_domains": "Technology, Pharma"},
    {"id": "att_marcus_002", "display_name": "Marcus Reed", "email": "marcus.reed@ascendhsi.com", "focus_domains": "Healthcare, Insurance"},
]

STAFF_ACCOUNTS = [
    {"role": "attorney", "email": "attorney@ascendhsi.com"},
    {"role": "attorney", "email": "marcus.reed@ascendhsi.com"},
    {"role": "leader", "email": "leader@ascendhsi.com"},
    {"role": "leader", "email": "jonathan.price@ascendhsi.com"},
    {"role": "admin", "email": "admin@ascendhsi.com"},
]


def reset_local_state() -> None:
    config = load_app_config()
    if config.database_path.exists():
        config.database_path.unlink()
    for suffix in ("-wal", "-shm"):
        extra = Path(f"{config.database_path}{suffix}")
        if extra.exists():
            extra.unlink()
    shutil.rmtree(config.upload_root, ignore_errors=True)
    shutil.rmtree(config.drive_mirror_root, ignore_errors=True)
    config.upload_root.mkdir(parents=True, exist_ok=True)
    config.drive_mirror_root.mkdir(parents=True, exist_ok=True)


def account_hash(service: EvidenceService, password: str) -> str:
    return service._hash_password(password)


def seed_members(service: EvidenceService) -> None:
    conn = service.conn
    builder = service.default_builder()

    conn.execute("UPDATE clients SET display_name = ? WHERE id = ?", (MEMBERS[0]["display_name"], MEMBERS[0]["client_id"]))
    conn.execute(
        """
        UPDATE cases
        SET status = ?, readiness_score = ?
        WHERE id = ?
        """,
        (MEMBERS[0]["status"], MEMBERS[0]["readiness_score"], MEMBERS[0]["case_id"]),
    )
    conn.execute(
        """
        UPDATE member_profiles
        SET first_name = ?, last_name = ?, preferred_name = ?, email = ?, current_title = ?,
            current_employer = ?, industry_domain = ?, primary_field = ?, biography = ?,
            target_filing_window = ?, proposed_final_merits_summary = ?, updated_at = CURRENT_TIMESTAMP
        WHERE client_id = ? AND case_id = ?
        """,
        (
            MEMBERS[0]["first_name"],
            MEMBERS[0]["last_name"],
            MEMBERS[0]["preferred_name"],
            MEMBERS[0]["email"],
            MEMBERS[0]["current_title"],
            MEMBERS[0]["current_employer"],
            MEMBERS[0]["industry_domain"],
            MEMBERS[0]["primary_field"],
            MEMBERS[0]["biography"],
            "2026-Q4",
            "Strong national impact narrative anchored in enterprise-scale applied AI deployments.",
            MEMBERS[0]["client_id"],
            MEMBERS[0]["case_id"],
        ),
    )
    conn.execute(
        """
        UPDATE member_accounts
        SET username = ?, email = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP
        WHERE client_id = ? AND case_id = ?
        """,
        (MEMBERS[0]["email"], MEMBERS[0]["email"], account_hash(service, PASSWORD), MEMBERS[0]["client_id"], MEMBERS[0]["case_id"]),
    )

    for member in MEMBERS[1:]:
        conn.execute("INSERT INTO clients(id, display_name) VALUES (?, ?)", (member["client_id"], member["display_name"]))
        conn.execute(
            "INSERT INTO cases(id, client_id, case_type, status, readiness_score) VALUES (?, ?, 'EB1A', ?, ?)",
            (member["case_id"], member["client_id"], member["status"], member["readiness_score"]),
        )
        conn.execute(
            """
            INSERT INTO member_profiles(
              client_id, case_id, first_name, last_name, preferred_name, email,
              current_title, current_employer, industry_domain, primary_field,
              biography, target_filing_window, proposed_final_merits_summary, profile_confirmed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                member["client_id"],
                member["case_id"],
                member["first_name"],
                member["last_name"],
                member["preferred_name"],
                member["email"],
                member["current_title"],
                member["current_employer"],
                member["industry_domain"],
                member["primary_field"],
                member["biography"],
                "2026-Q4",
                f"Evidence strategy for {member['display_name']} is progressing toward a stronger final merits narrative.",
            ),
        )
        conn.execute(
            """
            INSERT INTO member_accounts(id, client_id, case_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (f"acct_{member['client_id']}", member["client_id"], member["case_id"], member["email"], member["email"], account_hash(service, PASSWORD)),
        )
        conn.execute(
            """
            INSERT INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (f"asg_{member['client_id']}", builder["builder_id"], member["client_id"], member["case_id"]),
        )
        conn.execute(
            """
            INSERT INTO member_registration_invites(id, client_id, case_id, email, invited_by, status, invite_sent_at, registered_at, notes)
            VALUES (?, ?, ?, ?, 'leader', 'registered', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'Seeded sample account')
            """,
            (f"inv_{member['client_id']}", member["client_id"], member["case_id"], member["email"]),
        )
    conn.commit()


def seed_staff_accounts(service: EvidenceService) -> None:
    conn = service.conn
    password_hash = account_hash(service, PASSWORD)
    for staff in STAFF_ACCOUNTS:
        existing = conn.execute(
            "SELECT id FROM staff_accounts WHERE role = ? AND actor_key = ?",
            (staff["role"], staff["email"]),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE staff_accounts
                SET username = ?, email = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP, last_password_changed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (staff["email"], staff["email"], password_hash, existing["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO staff_accounts(id, role, actor_key, username, email, password_hash, last_password_changed_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (f"staff_{staff['role']}_{uuid.uuid4().hex[:8]}", staff["role"], staff["email"], staff["email"], staff["email"], password_hash),
            )
    conn.commit()


def seed_attorneys(service: EvidenceService) -> None:
    conn = service.conn
    conn.execute("DELETE FROM attorney_member_assignments")
    conn.execute("DELETE FROM attorneys")
    for attorney in ATTORNEYS:
        conn.execute(
            "INSERT INTO attorneys(id, display_name, email, focus_domains) VALUES (?, ?, ?, ?)",
            (attorney["id"], attorney["display_name"], attorney["email"], attorney["focus_domains"]),
        )
    for member in MEMBERS:
        attorney = next(item for item in ATTORNEYS if item["email"] == member["attorney_email"])
        conn.execute(
            """
            INSERT INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (f"aat_{member['client_id']}", attorney["id"], member["client_id"], member["case_id"]),
        )
    conn.commit()


def seed_evidence_and_folders(service: EvidenceService) -> dict[str, dict[str, str]]:
    folder_ids: dict[str, dict[str, str]] = {}
    evidence_plan = {
        "client_vas_001": [
            ("judging", "IEEE Reviews", "reviewer-invite.txt", "Reviewer invitation showing field judging activity."),
            ("scholarly_articles", "Publications", "journal-paper.txt", "Published journal article and citation summary."),
            ("original_contributions", "Impact Reports", "impact-report.txt", "Summary of measurable product impact and adoption."),
        ],
        "client_priya_002": [
            ("leading_critical_role", "Clinical Programs", "leadership-note.txt", "Program leadership note for health system initiative."),
            ("memberships", "Associations", "membership-acceptance.txt", "Selective membership acceptance confirmation."),
        ],
        "client_daniel_003": [
            ("scholarly_articles", "Publications", "oncology-paper.txt", "Peer-reviewed oncology methodology article."),
            ("judging", "Conference Panels", "panel-invite.txt", "Conference panel reviewer invitation."),
            ("awards", "Recognition", "award-letter.txt", "Industry recognition letter."),
            ("leading_critical_role", "Leadership", "director-role.txt", "Leadership role confirmation in drug development."),
        ],
        "client_elena_004": [
            ("original_contributions", "Fraud Platform", "fraud-results.txt", "Results summary for a fraud analytics platform."),
            ("high_salary", "Compensation", "compensation-summary.txt", "Compensation benchmark summary."),
            ("published_material", "Press", "press-coverage.txt", "Coverage about analytics work and market impact."),
        ],
        "client_omar_005": [
            ("judging", "Security Reviews", "cfp-review.txt", "Security conference CFP review participation."),
            ("published_material", "Media", "media-feature.txt", "Media feature covering public cyber defense research."),
            ("leading_critical_role", "Leadership", "research-lead.txt", "Critical role letter for research leadership."),
        ],
    }

    for member in MEMBERS:
        folder_ids[member["client_id"]] = {}
        for criterion_code, folder_name, file_name, description in evidence_plan[member["client_id"]]:
            key = f"{criterion_code}:{folder_name}"
            if key not in folder_ids[member["client_id"]]:
                folder = service.create_folder(criterion_code, folder_name, client_id=member["client_id"], case_id=member["case_id"])
                folder_ids[member["client_id"]][key] = folder["id"]
            service.upload_evidence(
                criterion_code=criterion_code,
                document_type="Other",
                title=file_name.replace(".txt", "").replace("-", " ").title(),
                description=description,
                file_name=file_name,
                content_type="text/plain",
                file_bytes=description.encode("utf-8"),
                ai_summary=description,
                quality_score=72,
                client_id=member["client_id"],
                case_id=member["case_id"],
                folder_id=folder_ids[member["client_id"]][key],
            )
    return folder_ids


def seed_planner_and_tasks(service: EvidenceService, folder_ids: dict[str, dict[str, str]]) -> None:
    conn = service.conn
    planner_rows = [
        ("client_vas_001", "case_eb1a_001", "Reviewer invitation follow-up", "2026-06-15", "planned", "judging", folder_ids["client_vas_001"]["judging:IEEE Reviews"]),
        ("client_priya_002", "case_eb1a_002", "Collect hospital program letter", "2026-06-28", "in_progress", "leading_critical_role", folder_ids["client_priya_002"]["leading_critical_role:Clinical Programs"]),
        ("client_daniel_003", "case_eb1a_003", "Finalize award corroboration packet", "2026-05-21", "planned", "awards", folder_ids["client_daniel_003"]["awards:Recognition"]),
        ("client_elena_004", "case_eb1a_004", "Secure compensation benchmarking letter", "2026-06-08", "blocked", "high_salary", folder_ids["client_elena_004"]["high_salary:Compensation"]),
        ("client_omar_005", "case_eb1a_005", "Capture media interview transcript", "2026-05-30", "planned", "published_material", folder_ids["client_omar_005"]["published_material:Media"]),
    ]
    for client_id, case_id, description, due_date, status, criterion_code, folder_id in planner_rows:
        conn.execute(
            """
            INSERT INTO planner_items(
              id, client_id, case_id, criterion_code, folder_id, member_role, issued_by,
              description, planned_completion_date, status, comments
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"pln_{uuid.uuid4().hex[:12]}",
                client_id,
                case_id,
                criterion_code,
                folder_id,
                "Attorney",
                "Ascend",
                description,
                due_date,
                status,
                "Seeded planner item for portal QA.",
            ),
        )
    conn.commit()

    task_map = {
        "client_vas_001": ("Document original contribution metrics", "Add customer adoption and impact exhibits.", "original_contributions", "2026-05-22"),
        "client_priya_002": ("Strengthen leadership narrative", "Collect institutional role letters and program scope details.", "leading_critical_role", "2026-05-29"),
        "client_daniel_003": ("Prepare petition exhibits list", "Draft the working exhibit map for counsel review.", "scholarly_articles", "2026-05-18"),
        "client_elena_004": ("Gather salary evidence", "Compile compensation and market comparison materials.", "high_salary", "2026-05-25"),
        "client_omar_005": ("Refine public impact chronology", "Build a chronology of media and review activity.", "published_material", "2026-05-23"),
    }
    for client_id, (title, description, criterion_code, due_date) in task_map.items():
        service.create_builder_task(client_id, title, description, criterion_code, due_date=due_date)


def seed_messages(service: EvidenceService) -> None:
    service.send_message(
        actor_role="leader",
        actor_email="leader@ascendhsi.com",
        subject="Portfolio review cadence",
        body="Please prioritize Daniel Kim and Omar Hassan this week for legal review readiness.",
        recipient_role="attorney",
        recipient_key="attorney@ascendhsi.com",
        urgent=True,
    )
    service.send_message(
        actor_role="attorney",
        actor_email="attorney@ascendhsi.com",
        subject="Need final judging support",
        body="Please upload the thank-you note that confirms the IEEE reviewer activity.",
        recipient_role="member",
        recipient_key="client_daniel_003",
        urgent=False,
    )
    service.send_message(
        actor_role="member",
        actor_client_id="client_priya_002",
        subject="Need clarity on evidence foldering",
        body="Can you confirm whether the clinical leadership letter should go under leading role or original contributions?",
        recipient_role="builder",
        recipient_key="builder@ascendhsi.com",
        urgent=False,
    )
    service.send_message(
        actor_role="admin",
        actor_email="admin@ascendhsi.com",
        subject="Seeded environment ready",
        body="Local sample data refresh completed for integration testing.",
        recipient_role="leader",
        recipient_key="leader@ascendhsi.com",
        urgent=False,
    )


def make_zip(entries: list[tuple[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, contents in entries:
            archive.writestr(path, contents)
    return buffer.getvalue()


def seed_batch_sessions(service: EvidenceService) -> None:
    vas_zip = make_zip(
        [
            ("Judging/peer-review-note.txt", "Peer review note for IEEE editorial board."),
            ("Awards/nomination-letter.txt", "National innovation nomination letter."),
        ]
    )
    vas_session = service.attorney_batch_intake_create(
        "client_vas_001",
        "Batch intake from Marcus for Vas",
        "vas-batch.zip",
        vas_zip,
        created_by_role="attorney",
        actor_role="attorney",
        actor_email="marcus.reed@ascendhsi.com",
    )
    service.bulk_update_attorney_batch_intake(
        vas_session["id"],
        [item["id"] for item in vas_session["items"]],
        review_status="ready",
        actor_role="attorney",
        actor_email="marcus.reed@ascendhsi.com",
    )
    service.commit_attorney_batch_intake(vas_session["id"], actor_role="attorney", actor_email="marcus.reed@ascendhsi.com")

    elena_zip = make_zip(
        [
            ("Press/news-mention.txt", "Press mention covering fraud platform adoption."),
            ("Compensation/bonus-summary.txt", "Bonus and salary summary from compensation committee."),
        ]
    )
    service.attorney_batch_intake_create(
        "client_elena_004",
        "Leader-created batch session left in review for Elena",
        "elena-batch.zip",
        elena_zip,
        created_by_role="leader",
        actor_role="leader",
    )


def write_credentials_file() -> Path:
    output = ROOT / "docs" / "local-sample-credentials.md"
    lines = [
        "# Local Sample Credentials",
        "",
        "Password for every login below: `Ascend123!`",
        "",
        "## Member Portal",
    ]
    for member in MEMBERS:
        lines.append(f"- {member['display_name']}: `{member['email']}`")
    lines.extend(
        [
            "",
            "## Profile Builder Portal",
            "- Ava Morales: `builder@ascendhsi.com`",
            "",
            "## Attorney Portal",
            "- Sophia Chen: `attorney@ascendhsi.com`",
            "- Marcus Reed: `marcus.reed@ascendhsi.com`",
            "",
            "## Leader Portal",
            "- Ava Morales: `leader@ascendhsi.com`",
            "- Jonathan Price: `jonathan.price@ascendhsi.com`",
            "",
            "## Admin Portal",
            "- Maya Thompson: `admin@ascendhsi.com`",
        ]
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def collect_summary(service: EvidenceService) -> dict:
    conn = service.conn
    return {
        "members": conn.execute("SELECT COUNT(*) FROM member_profiles").fetchone()[0],
        "attorneys": conn.execute("SELECT COUNT(*) FROM attorneys").fetchone()[0],
        "leaders_preview": 2,
        "admin_preview": 1,
        "builder_accounts": conn.execute("SELECT COUNT(*) FROM profile_builder_accounts").fetchone()[0],
        "evidence_items": conn.execute("SELECT COUNT(*) FROM evidence_items WHERE status != 'archived'").fetchone()[0],
        "planner_items": conn.execute("SELECT COUNT(*) FROM planner_items").fetchone()[0],
        "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        "messages": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        "batch_sessions": conn.execute("SELECT COUNT(*) FROM batch_intake_sessions").fetchone()[0],
    }


def main() -> None:
    reset_local_state()
    service = EvidenceService()
    seed_members(service)
    seed_attorneys(service)
    seed_staff_accounts(service)
    folder_ids = seed_evidence_and_folders(service)
    seed_planner_and_tasks(service, folder_ids)
    seed_messages(service)
    seed_batch_sessions(service)
    credentials_path = write_credentials_file()
    print(json.dumps({"ok": True, "summary": collect_summary(service), "credentials_file": str(credentials_path)}, indent=2))


if __name__ == "__main__":
    main()

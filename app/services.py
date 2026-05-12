import mimetypes
import hashlib
import json
import os
import re
import secrets
import tempfile
import time
import zipfile
import calendar
from datetime import date, datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlencode
import uuid

import requests
from botocore.exceptions import ClientError

PLANNER_STATUSES = {"planned", "in_progress", "completed", "blocked"}
DEFAULT_MEMBER_PASSWORD = "Ascend123!"
DEFAULT_MEMBER_EMAIL = "vas@ascendhsi.com"
ADMIN_COST_SNAPSHOT_SOURCE = "cost_explorer"
ISSUE_PRIORITIES = {"P0", "P1", "P2", "P3"}
ISSUE_STATUSES = {
    "new",
    "open",
    "triaged",
    "in_progress",
    "testing",
    "blocked",
    "fixed_local",
    "fixed",
    "closed",
    "wont_do",
    "duplicate",
}
REFERRAL_STATUSES = {"submitted", "contacted", "contract_signed", "qualified", "paid", "disqualified"}
MEMBER_REWRITE_MAX_FIELD_CHARS = 6000
MEMBER_REWRITE_MAX_CONTEXT_VALUE_CHARS = 1000
MEMBER_REWRITE_MAX_CONTEXT_TOTAL_CHARS = 12000
MEMBER_REWRITE_RATE_LIMIT_PER_MINUTE = 20

from app.config import load_app_config, load_google_drive_config, load_openai_config
from app.db import connect, initialize, next_numeric_identifier, one, rows, seed_default_case
from app.google_drive import GoogleDriveClient, GoogleDriveConfigError, GoogleDriveUploadError
from app.openai_client import DOCUMENT_TYPES, OpenAIService, extract_document_excerpt, infer_document_type
from app.storage import EvidenceStorage, safe_file_name
from app.template_exports import render_critical_role_pdf, render_original_contribution_pdf


class DuplicateEvidenceError(RuntimeError):
    def __init__(self, duplicate: dict):
        super().__init__("A file with this name already exists in this category.")
        self.duplicate = duplicate


class EvidenceService:
    def __init__(self):
        self.config = load_app_config()
        self.google_drive_config = load_google_drive_config()
        self.openai = OpenAIService(load_openai_config())
        self.storage = EvidenceStorage(
            self.config.upload_root,
            self.config.drive_mirror_root,
            GoogleDriveClient(self.google_drive_config),
        )
        self.conn = connect(self.config.database_path)
        initialize(self.conn)
        seed_default_case(
            self.conn,
            self.config.default_client["client_id"],
            self.config.default_client["case_id"],
            self.config.default_client["display_name"],
        )
        self._ensure_default_profile()
        self._ensure_default_account()
        self._ensure_default_builder()
        self._ensure_default_builder_assignment()
        self._ensure_default_attorneys()
        self._ensure_default_staff_accounts()
        self._ensure_default_attorney_assignment()
        self._ensure_default_opportunities()

    def _system_users(self) -> list[dict]:
        return [
            {"role": "leader", "key": "leader@ascendhsi.com", "name": "Ava Morales", "email": "leader@ascendhsi.com"},
            {"role": "leader", "key": "jonathan.price@ascendhsi.com", "name": "Jonathan Price", "email": "jonathan.price@ascendhsi.com"},
            {"role": "admin", "key": "admin@ascendhsi.com", "name": "Maya Thompson", "email": "admin@ascendhsi.com"},
        ]

    def _numeric_key(self, value: int | str | None) -> str:
        try:
            numeric = int(value or 0)
        except (TypeError, ValueError):
            numeric = 0
        return str(numeric) if numeric > 0 else ""

    def _actor_key_candidates(self, actor: dict) -> list[str]:
        keys = []
        for value in [actor.get("key", ""), actor.get("legacy_key", "")]:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in keys:
                keys.append(cleaned)
        return keys

    def _identity_payload(
        self,
        role: str,
        numeric_identifier: int | str | None,
        legacy_key: str,
        name: str,
        email: str = "",
        **extra: object,
    ) -> dict:
        numeric_key = self._numeric_key(numeric_identifier)
        payload = {
            "role": role,
            "key": numeric_key or legacy_key,
            "legacy_key": legacy_key,
            "numeric_identifier": int(numeric_identifier or 0),
            "name": name,
            "email": email.strip().lower(),
        }
        payload.update(extra)
        return payload

    def _system_user_account(self, role: str, actor_email: str = "") -> tuple[dict, dict | None]:
        cleaned_role = role.strip().lower()
        cleaned_email = actor_email.strip().lower()
        user = next(
            (
                item
                for item in self._system_users()
                if item["role"] == cleaned_role and (not cleaned_email or item["email"].strip().lower() == cleaned_email)
            ),
            None,
        )
        if not user:
            raise ValueError(f"{cleaned_role.title()} not found")
        account = one(
            self.conn,
            """
            SELECT *
            FROM staff_accounts
            WHERE role = ? AND (LOWER(email) = ? OR actor_key = ?)
            """,
            (cleaned_role, user["email"].strip().lower(), user["key"]),
        )
        return user, account

    def _actor_identity(self, role: str, actor_email: str = "", actor_client_id: str = "") -> dict:
        role = role.strip().lower()
        actor_email = actor_email.strip().lower()
        actor_client_id = actor_client_id.strip()
        if role == "member":
            client_id = actor_client_id or self.config.default_client["client_id"]
            profile = one(
                self.conn,
                """
                SELECT mp.*, c.member_uid, c.display_name
                FROM member_profiles mp
                JOIN clients c ON c.id = mp.client_id
                WHERE mp.client_id = ?
                """,
                (client_id,),
            )
            if not profile:
                raise ValueError("Member not found")
            return self._identity_payload(
                "member",
                profile.get("member_uid"),
                client_id,
                (profile.get("preferred_name") or profile.get("first_name") or profile.get("display_name") or profile.get("email") or "Member").strip(),
                profile.get("email", ""),
                client_id=client_id,
                member_uid=profile.get("member_uid"),
            )
        if role == "builder":
            account = one(self.conn, "SELECT * FROM profile_builder_accounts WHERE LOWER(email) = ? OR LOWER(username) = ?", (actor_email, actor_email))
            if not account:
                raise ValueError("Profile builder not found")
            payload = self._builder_payload(account)
            return self._identity_payload(
                "builder",
                payload.get("builder_uid"),
                payload["email"].strip().lower(),
                payload["display_name"],
                payload["email"],
                builder_id=payload["builder_id"],
                builder_uid=payload.get("builder_uid"),
            )
        if role == "attorney":
            attorney = one(self.conn, "SELECT * FROM attorneys WHERE LOWER(email) = ?", (actor_email,))
            if not attorney:
                raise ValueError("Attorney not found")
            return self._identity_payload(
                "attorney",
                attorney.get("attorney_uid"),
                attorney["email"].strip().lower(),
                attorney["display_name"],
                attorney["email"],
                attorney_id=attorney["id"],
                attorney_uid=attorney.get("attorney_uid"),
            )
        if role in {"leader", "admin"}:
            user, account = self._system_user_account(role, actor_email)
            return self._identity_payload(
                role,
                account.get("staff_uid") if account else 0,
                user["key"],
                user["name"],
                user["email"],
                staff_account_id=account.get("id", "") if account else "",
                staff_uid=account.get("staff_uid", 0) if account else 0,
            )
        raise ValueError("Unsupported actor role")

    def _recipient_options(self, actor: dict) -> list[dict]:
        options: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add(role: str, key: str, name: str, email: str = "", detail: str = "", legacy_key: str = "", numeric_identifier: int | str | None = None) -> None:
            ident = (role, key)
            if not key or ident in seen:
                return
            seen.add(ident)
            options.append({
                "role": role,
                "key": key,
                "legacy_key": legacy_key,
                "numeric_identifier": int(numeric_identifier or 0),
                "name": name,
                "email": email,
                "detail": detail,
            })

        if actor["role"] == "member":
            client_id = actor["client_id"]
            member = self.builder_member_detail(client_id)["member"]
            builder = one(
                self.conn,
                """
                SELECT pb.*
                FROM builder_member_assignments a
                JOIN profile_builders pb ON pb.id = a.builder_id
                WHERE a.client_id = ? AND a.case_id = ? AND a.status = 'active'
                ORDER BY a.created_at DESC
                LIMIT 1
                """,
                (member["client_id"], member["case_id"]),
            )
            attorney = one(
                self.conn,
                """
                SELECT att.*
                FROM attorney_member_assignments a
                JOIN attorneys att ON att.id = a.attorney_id
                WHERE a.client_id = ? AND a.case_id = ? AND a.status = 'active'
                ORDER BY a.created_at DESC
                LIMIT 1
                """,
                (member["client_id"], member["case_id"]),
            )
            if builder:
                add(
                    "builder",
                    self._numeric_key(builder.get("builder_uid")),
                    builder["display_name"],
                    builder["email"],
                    "Assigned profile builder",
                    legacy_key=builder["email"].strip().lower(),
                    numeric_identifier=builder.get("builder_uid"),
                )
            if attorney:
                add(
                    "attorney",
                    self._numeric_key(attorney.get("attorney_uid")),
                    attorney["display_name"],
                    attorney["email"],
                    "Assigned attorney",
                    legacy_key=attorney["email"].strip().lower(),
                    numeric_identifier=attorney.get("attorney_uid"),
                )
            admin, admin_account = self._system_user_account("admin")
            add(
                "admin",
                self._numeric_key(admin_account.get("staff_uid") if admin_account else 0),
                admin["name"],
                admin["email"],
                "Operations support",
                legacy_key=admin["key"],
                numeric_identifier=admin_account.get("staff_uid") if admin_account else 0,
            )
            return options

        if actor["role"] == "builder":
            members = rows(
                self.conn,
                """
                SELECT c.id AS client_id, c.member_uid, c.display_name, mp.email
                FROM builder_member_assignments a
                JOIN clients c ON c.id = a.client_id
                LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = a.case_id
                WHERE a.builder_id = ? AND a.status = 'active'
                ORDER BY c.display_name
                """,
                (actor["builder_id"],),
            )
            for item in members:
                add(
                    "member",
                    self._numeric_key(item.get("member_uid")),
                    item["display_name"],
                    item.get("email", ""),
                    "Assigned member",
                    legacy_key=item["client_id"],
                    numeric_identifier=item.get("member_uid"),
                )
            for system in self._system_users():
                system_user, system_account = self._system_user_account(system["role"], system["email"])
                add(
                    system_user["role"],
                    self._numeric_key(system_account.get("staff_uid") if system_account else 0),
                    system_user["name"],
                    system_user["email"],
                    "Operations",
                    legacy_key=system_user["key"],
                    numeric_identifier=system_account.get("staff_uid") if system_account else 0,
                )
            return options

        if actor["role"] == "attorney":
            members = rows(
                self.conn,
                """
                SELECT c.id AS client_id, c.member_uid, c.display_name, mp.email
                FROM attorney_member_assignments a
                JOIN clients c ON c.id = a.client_id
                LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = a.case_id
                WHERE a.attorney_id = ? AND a.status = 'active'
                ORDER BY c.display_name
                """,
                (actor["attorney_id"],),
            )
            for item in members:
                add(
                    "member",
                    self._numeric_key(item.get("member_uid")),
                    item["display_name"],
                    item.get("email", ""),
                    "Assigned member",
                    legacy_key=item["client_id"],
                    numeric_identifier=item.get("member_uid"),
                )
            for system in self._system_users():
                system_user, system_account = self._system_user_account(system["role"], system["email"])
                add(
                    system_user["role"],
                    self._numeric_key(system_account.get("staff_uid") if system_account else 0),
                    system_user["name"],
                    system_user["email"],
                    "Operations",
                    legacy_key=system_user["key"],
                    numeric_identifier=system_account.get("staff_uid") if system_account else 0,
                )
            return options

        if actor["role"] in {"leader", "admin"}:
            members = rows(self.conn, "SELECT c.id AS client_id, c.member_uid, c.display_name, mp.email FROM clients c LEFT JOIN member_profiles mp ON mp.client_id = c.id ORDER BY c.display_name")
            builders = rows(self.conn, "SELECT id, builder_uid, display_name, email FROM profile_builders ORDER BY display_name")
            attorneys = rows(self.conn, "SELECT id, attorney_uid, display_name, email FROM attorneys ORDER BY display_name")
            for item in members:
                add(
                    "member",
                    self._numeric_key(item.get("member_uid")),
                    item["display_name"],
                    item.get("email", ""),
                    "Member",
                    legacy_key=item["client_id"],
                    numeric_identifier=item.get("member_uid"),
                )
            for item in builders:
                add(
                    "builder",
                    self._numeric_key(item.get("builder_uid")),
                    item["display_name"],
                    item["email"],
                    "Profile builder",
                    legacy_key=item["email"].strip().lower(),
                    numeric_identifier=item.get("builder_uid"),
                )
            for item in attorneys:
                add(
                    "attorney",
                    self._numeric_key(item.get("attorney_uid")),
                    item["display_name"],
                    item["email"],
                    "Attorney",
                    legacy_key=item["email"].strip().lower(),
                    numeric_identifier=item.get("attorney_uid"),
                )
            for system in self._system_users():
                system_user, system_account = self._system_user_account(system["role"], system["email"])
                add(
                    system_user["role"],
                    self._numeric_key(system_account.get("staff_uid") if system_account else 0),
                    system_user["name"],
                    system_user["email"],
                    "Operations",
                    legacy_key=system_user["key"],
                    numeric_identifier=system_account.get("staff_uid") if system_account else 0,
                )
            return [item for item in options if not (item["role"] == actor["role"] and item["key"] == actor["key"])]

        return options

    def message_recipient_options(self, actor_role: str, actor_email: str = "", actor_client_id: str = "") -> list[dict]:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        return self._recipient_options(actor)

    def message_center(self, actor_role: str, actor_email: str = "", actor_client_id: str = "") -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        actor_keys = self._actor_key_candidates(actor)
        placeholders = ", ".join("?" for _ in actor_keys)
        visible_messages = rows(
            self.conn,
            f"""
            SELECT *
            FROM messages
            WHERE (
              (recipient_role = ? AND recipient_key IN ({placeholders}) AND deleted_by_recipient = 0)
              OR
              (sender_role = ? AND sender_key IN ({placeholders}) AND deleted_by_sender = 0)
            )
            ORDER BY created_at DESC
            """,
            (actor["role"], *actor_keys, actor["role"], *actor_keys),
        )
        threads_map: dict[str, dict] = {}
        for item in visible_messages:
            thread_id = item.get("thread_id") or item["id"]
            bucket = threads_map.setdefault(
                thread_id,
                {
                    "thread_id": thread_id,
                    "subject": item["subject"],
                    "urgent": False,
                    "latest_at": item["created_at"],
                    "latest_message": item,
                    "messages": [],
                    "unread_count": 0,
                },
            )
            bucket["messages"].append(item)
            if item["created_at"] >= bucket["latest_at"]:
                bucket["latest_at"] = item["created_at"]
                bucket["latest_message"] = item
            if item["urgent"]:
                bucket["urgent"] = True
            if item["recipient_role"] == actor["role"] and item["recipient_key"] in actor_keys and not item["is_read"]:
                bucket["unread_count"] += 1
            if item.get("parent_message_id") is None or bucket["subject"] == "":
                bucket["subject"] = item["subject"]
        threads = sorted(threads_map.values(), key=lambda item: (item["latest_at"], item["urgent"]), reverse=True)
        unread = sum(item["unread_count"] for item in threads)
        return {
            "actor": actor,
            "unread_count": unread,
            "recipient_options": self._recipient_options(actor),
            "threads": threads,
        }

    def _insert_message_record(
        self,
        sender: dict,
        recipient: dict,
        subject: str,
        body: str,
        urgent: bool = False,
        thread_id: str = "",
        parent_message_id: str = "",
    ) -> dict:
        cleaned_subject = subject.strip()
        cleaned_body = body.strip()
        if not cleaned_subject or not cleaned_body:
            raise ValueError("subject and body are required")
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        resolved_thread_id = thread_id.strip() or f"thd_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO messages(
              id, thread_id, parent_message_id, sender_role, sender_key, sender_name, sender_email,
              recipient_role, recipient_key, recipient_name, recipient_email,
              subject, body, urgent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                resolved_thread_id,
                parent_message_id.strip() or None,
                sender["role"],
                sender["key"],
                sender["name"],
                sender.get("email", ""),
                recipient["role"],
                recipient["key"],
                recipient["name"],
                recipient.get("email", ""),
                cleaned_subject,
                cleaned_body,
                1 if urgent else 0,
            ),
        )
        return one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,)) or {"id": message_id, "thread_id": resolved_thread_id}

    def send_message(
        self,
        actor_role: str,
        subject: str,
        body: str,
        recipient_role: str,
        recipient_key: str,
        urgent: bool = False,
        actor_email: str = "",
        actor_client_id: str = "",
        thread_id: str = "",
        parent_message_id: str = "",
    ) -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        actor_keys = self._actor_key_candidates(actor)
        cleaned_thread_id = thread_id.strip()
        cleaned_parent_id = parent_message_id.strip()
        recipients = self._recipient_options(actor)
        cleaned_subject = subject.strip()
        cleaned_body = body.strip()
        if not cleaned_subject or not cleaned_body:
            raise ValueError("subject and body are required")
        if cleaned_thread_id:
            thread_messages = rows(self.conn, "SELECT * FROM messages WHERE thread_id = ? ORDER BY created_at ASC", (cleaned_thread_id,))
            if not thread_messages:
                raise ValueError("Message thread not found")
            thread_participant = next(
                (
                    {
                        "role": item["sender_role"],
                        "key": item["sender_key"],
                        "name": item["sender_name"],
                        "email": item.get("sender_email", ""),
                    }
                    for item in thread_messages
                    if not (item["sender_role"] == actor["role"] and item["sender_key"] in actor_keys)
                ),
                None,
            ) or next(
                (
                    {
                        "role": item["recipient_role"],
                        "key": item["recipient_key"],
                        "name": item["recipient_name"],
                        "email": item.get("recipient_email", ""),
                    }
                    for item in thread_messages
                    if not (item["recipient_role"] == actor["role"] and item["recipient_key"] in actor_keys)
                ),
                None,
            )
            if not thread_participant:
                raise ValueError("Could not resolve thread recipient")
            recipient = thread_participant
            cleaned_subject = thread_messages[0]["subject"]
        else:
            cleaned_recipient_key = recipient_key.strip()
            recipient = next(
                (
                    item
                    for item in recipients
                    if item["role"] == recipient_role.strip().lower()
                    and cleaned_recipient_key in {str(item.get("key", "")).strip(), str(item.get("legacy_key", "")).strip()}
                ),
                None,
            )
            if not recipient:
                raise ValueError("Recipient not available for this actor")
            cleaned_thread_id = f"thd_{uuid.uuid4().hex[:12]}"
        message = self._insert_message_record(
            actor,
            recipient,
            cleaned_subject,
            cleaned_body,
            urgent=urgent,
            thread_id=cleaned_thread_id,
            parent_message_id=cleaned_parent_id,
        )
        self.conn.commit()
        self.record_operational_event(
            "message_sent",
            status="success",
            portal=actor["role"],
            client_id=actor.get("client_id", ""),
            endpoint="/api/messages",
            message=f"{actor['name']} sent a message to {recipient['name']}.",
            metadata={"recipient_role": recipient["role"], "urgent": bool(urgent), "thread_id": cleaned_thread_id},
        )
        return message

    def set_message_read(
        self,
        message_id: str,
        actor_role: str,
        is_read: bool,
        actor_email: str = "",
        actor_client_id: str = "",
    ) -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        actor_keys = self._actor_key_candidates(actor)
        message = one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,))
        if not message:
            raise ValueError("Message not found")
        if message["recipient_role"] != actor["role"] or message["recipient_key"] not in actor_keys:
            raise ValueError("Message cannot be updated by this actor")
        self.conn.execute(
            """
            UPDATE messages
            SET is_read = ?, read_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE id = ?
            """,
            (1 if is_read else 0, 1 if is_read else 0, message_id),
        )
        self.conn.commit()
        return one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,)) or {}

    def delete_message(
        self,
        message_id: str,
        actor_role: str,
        actor_email: str = "",
        actor_client_id: str = "",
    ) -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        actor_keys = self._actor_key_candidates(actor)
        message = one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,))
        if not message:
            raise ValueError("Message not found")
        if message["sender_role"] == actor["role"] and message["sender_key"] in actor_keys:
            self.conn.execute("UPDATE messages SET deleted_by_sender = 1 WHERE id = ?", (message_id,))
        elif message["recipient_role"] == actor["role"] and message["recipient_key"] in actor_keys:
            self.conn.execute("UPDATE messages SET deleted_by_recipient = 1 WHERE id = ?", (message_id,))
        else:
            raise ValueError("Message cannot be deleted by this actor")
        self.conn.commit()
        message = one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,))
        if message and message["deleted_by_sender"] and message["deleted_by_recipient"]:
            self.conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            self.conn.commit()
        return {"ok": True, "message_id": message_id, "status": "deleted"}

    def record_operational_event(
        self,
        event_type: str,
        status: str = "info",
        portal: str = "",
        client_id: str = "",
        case_id: str = "",
        endpoint: str = "",
        error_code: str = "",
        message: str = "",
        metadata: dict | None = None,
        actor_role: str = "",
        actor_key: str = "",
        related_client_id: str = "",
        related_case_id: str = "",
    ) -> dict:
        event = {
            "id": f"ops_{uuid.uuid4().hex[:12]}",
            "event_type": event_type,
            "status": status,
            "portal": portal,
            "client_id": client_id,
            "case_id": case_id,
            "endpoint": endpoint,
            "error_code": error_code,
            "message": message,
            "metadata": json.dumps(metadata or {}, ensure_ascii=True),
            "actor_role": actor_role,
            "actor_key": actor_key,
            "related_client_id": related_client_id,
            "related_case_id": related_case_id,
        }
        self.conn.execute(
            """
            INSERT INTO operational_events(
              id, event_type, status, portal, client_id, case_id, endpoint, error_code, message, metadata,
              actor_role, actor_key, related_client_id, related_case_id
            )
            VALUES (
              :id, :event_type, :status, :portal, :client_id, :case_id, :endpoint, :error_code, :message, :metadata,
              :actor_role, :actor_key, :related_client_id, :related_case_id
            )
            """,
            event,
        )
        self.conn.commit()
        return event

    def capture_marketing_lead(
        self,
        lead_source: str,
        campaign: str,
        email: str,
        phone: str = "",
        name: str = "",
        source_url: str = "",
        answers: dict | None = None,
        result: dict | None = None,
        metadata: dict | None = None,
        audit_context: dict | None = None,
    ) -> dict:
        cleaned_email = str(email or "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned_email):
            raise ValueError("A valid email is required to view your result.")
        cleaned_phone = re.sub(r"\s+", " ", str(phone or "").strip())[:80]
        cleaned_name = re.sub(r"\s+", " ", str(name or "").strip())[:160]
        result_payload = result or {}
        try:
            readiness_score = int(result_payload.get("readiness_score") or 0)
        except (TypeError, ValueError):
            readiness_score = 0
        lead = {
            "id": f"lead_{uuid.uuid4().hex[:12]}",
            "lead_source": str(lead_source or "visa_compass").strip()[:80] or "visa_compass",
            "campaign": str(campaign or "Ascend Visa Compass").strip()[:160] or "Ascend Visa Compass",
            "email": cleaned_email,
            "phone": cleaned_phone,
            "name": cleaned_name,
            "source_url": str(source_url or "").strip()[:500],
            "top_match": str(result_payload.get("top_match", "") or "").strip()[:80],
            "match_label": str(result_payload.get("match_label", "") or result_payload.get("label", "") or "").strip()[:160],
            "readiness_score": readiness_score,
            "answers_json": json.dumps(answers or {}, ensure_ascii=True),
            "result_json": json.dumps(result_payload, ensure_ascii=True),
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=True),
            "status": "new",
            "user_agent": str((audit_context or {}).get("user_agent", "") or "")[:500],
            "client_ip": str((audit_context or {}).get("client_ip", "") or (audit_context or {}).get("forwarded_for", "") or "")[:160],
        }
        self.conn.execute(
            """
            INSERT INTO marketing_leads(
              id, lead_source, campaign, email, phone, name, source_url, top_match, match_label,
              readiness_score, answers_json, result_json, metadata_json, status, user_agent, client_ip
            )
            VALUES (
              :id, :lead_source, :campaign, :email, :phone, :name, :source_url, :top_match, :match_label,
              :readiness_score, :answers_json, :result_json, :metadata_json, :status, :user_agent, :client_ip
            )
            """,
            lead,
        )
        self.conn.commit()
        stored_row = one(self.conn, "SELECT * FROM marketing_leads WHERE id = ?", (lead["id"],))
        stored = dict(stored_row) if stored_row else lead
        self.record_operational_event(
            "marketing_lead_created",
            status="success",
            portal="public",
            endpoint="/api/marketing/leads/visa-compass",
            message=f"New {lead['campaign']} lead captured.",
            metadata={
                "lead_id": lead["id"],
                "lead_source": lead["lead_source"],
                "top_match": lead["top_match"],
                "readiness_score": lead["readiness_score"],
            },
            actor_role="lead",
            actor_key=cleaned_email,
        )
        return {
            "ok": True,
            "lead": {
                "id": stored["id"],
                "email": stored["email"],
                "phone": stored.get("phone", ""),
                "name": stored.get("name", ""),
                "lead_source": stored["lead_source"],
                "campaign": stored["campaign"],
                "top_match": stored.get("top_match", ""),
                "match_label": stored.get("match_label", ""),
                "readiness_score": int(stored.get("readiness_score") or 0),
                "created_at": stored.get("created_at", ""),
                "status": stored.get("status", "new"),
            },
        }

    def _serialize_referral_settings(self, settings: dict | None) -> dict:
        row = settings or {}
        return {
            "id": row.get("id", "default"),
            "is_enabled": bool(int(row.get("is_enabled") or 0)),
            "referred_bonus_amount": int(row.get("referred_bonus_amount") or 500),
            "referrer_bonus_amount": int(row.get("referrer_bonus_amount") or 250),
            "currency": row.get("currency", "USD") or "USD",
            "promotion_name": row.get("promotion_name", "Standard referral program") or "Standard referral program",
            "eligibility_note": row.get("eligibility_note", "Paid after referred member signs the contract and completes at least 6 months with Ascend.") or "Paid after referred member signs the contract and completes at least 6 months with Ascend.",
            "updated_by": row.get("updated_by", ""),
            "updated_at": row.get("updated_at", ""),
        }

    def _referral_settings(self) -> dict:
        settings = one(self.conn, "SELECT * FROM referral_settings WHERE id = 'default'")
        if not settings:
            self.conn.execute(
                """
                INSERT INTO referral_settings(
                  id, is_enabled, referred_bonus_amount, referrer_bonus_amount, currency, promotion_name, eligibility_note
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default",
                    1,
                    500,
                    250,
                    "USD",
                    "Standard referral program",
                    "Paid after referred member signs the contract and completes at least 6 months with Ascend.",
                ),
            )
            self.conn.commit()
            settings = one(self.conn, "SELECT * FROM referral_settings WHERE id = 'default'")
        return self._serialize_referral_settings(settings)

    def _serialize_referral(self, referral: dict) -> dict:
        item = dict(referral)
        status = str(item.get("status") or "submitted").strip().lower()
        item["status"] = status
        item["status_label"] = status.replace("_", " ").title()
        item["referrer_bonus_amount"] = int(item.get("referrer_bonus_amount") or 0)
        item["referred_bonus_amount"] = int(item.get("referred_bonus_amount") or 0)
        item["currency"] = item.get("currency", "USD") or "USD"
        item["total_bonus_amount"] = item["referrer_bonus_amount"] + item["referred_bonus_amount"]
        item["is_bonus_eligible"] = bool(item.get("eligible_at")) and not bool(item.get("paid_at"))
        item["is_paid"] = bool(item.get("paid_at")) or status == "paid"
        return item

    def _referral_metrics(self, referrals: list[dict]) -> dict:
        active_statuses = {"submitted", "contacted", "contract_signed", "qualified"}
        pending_payout = sum(
            int(item.get("total_bonus_amount") or 0)
            for item in referrals
            if item.get("status") == "qualified" and not item.get("paid_at")
        )
        return {
            "total_referrals": len(referrals),
            "active_referrals": sum(1 for item in referrals if item.get("status") in active_statuses),
            "contract_signed": sum(1 for item in referrals if item.get("status") in {"contract_signed", "qualified", "paid"} or item.get("contract_signed_at")),
            "qualified": sum(1 for item in referrals if item.get("status") in {"qualified", "paid"} or item.get("eligible_at")),
            "paid": sum(1 for item in referrals if item.get("status") == "paid" or item.get("paid_at")),
            "pending_payout_amount": pending_payout,
        }

    def member_referrals(self, client_id: str, case_id: str) -> dict:
        referral_rows = rows(
            self.conn,
            """
            SELECT *
            FROM member_referrals
            WHERE referrer_client_id = ? AND referrer_case_id = ?
            ORDER BY created_at DESC
            """,
            (client_id, case_id),
        )
        referrals = [self._serialize_referral(item) for item in referral_rows]
        return {
            "ok": True,
            "settings": self._referral_settings(),
            "referrals": referrals,
            "metrics": self._referral_metrics(referrals),
        }

    def create_member_referral(
        self,
        client_id: str,
        case_id: str,
        prospect_name: str,
        prospect_email: str = "",
        prospect_phone: str = "",
        relationship: str = "",
        notes: str = "",
    ) -> dict:
        settings = self._referral_settings()
        if not settings["is_enabled"]:
            raise ValueError("Referral program is currently paused by Ascend leadership.")
        client = one(self.conn, "SELECT * FROM clients WHERE id = ?", (client_id,))
        case = one(self.conn, "SELECT * FROM cases WHERE id = ? AND client_id = ?", (case_id, client_id))
        if not client or not case:
            raise ValueError("Member case not found")
        cleaned_name = re.sub(r"\s+", " ", str(prospect_name or "").strip())[:160]
        cleaned_email = str(prospect_email or "").strip().lower()
        cleaned_phone = re.sub(r"\s+", " ", str(prospect_phone or "").strip())[:80]
        phone_digits = re.sub(r"\D", "", cleaned_phone)
        if not cleaned_name:
            raise ValueError("Referral name is required")
        if cleaned_email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned_email):
            raise ValueError("Referral email must be valid")
        if not cleaned_email and not phone_digits:
            raise ValueError("Add at least one contact method: email or phone")
        existing = rows(
            self.conn,
            """
            SELECT *
            FROM member_referrals
            WHERE referrer_client_id = ? AND status != 'disqualified'
            """,
            (client_id,),
        )
        for item in existing:
            if cleaned_email and str(item.get("prospect_email", "")).strip().lower() == cleaned_email:
                raise ValueError("This referral email is already in your referral history")
            if phone_digits and re.sub(r"\D", "", str(item.get("prospect_phone", ""))) == phone_digits:
                raise ValueError("This referral phone number is already in your referral history")
        referral = {
            "id": f"ref_{uuid.uuid4().hex[:12]}",
            "referrer_client_id": client_id,
            "referrer_case_id": case_id,
            "referrer_member_uid": int(client.get("member_uid") or 0),
            "referrer_name": client.get("display_name", ""),
            "prospect_name": cleaned_name,
            "prospect_email": cleaned_email,
            "prospect_phone": cleaned_phone,
            "relationship": re.sub(r"\s+", " ", str(relationship or "").strip())[:120],
            "notes": str(notes or "").strip()[:1000],
            "status": "submitted",
            "referrer_bonus_amount": settings["referrer_bonus_amount"],
            "referred_bonus_amount": settings["referred_bonus_amount"],
            "currency": settings["currency"],
        }
        self.conn.execute(
            """
            INSERT INTO member_referrals(
              id, referrer_client_id, referrer_case_id, referrer_member_uid, referrer_name,
              prospect_name, prospect_email, prospect_phone, relationship, notes, status,
              referrer_bonus_amount, referred_bonus_amount, currency
            )
            VALUES (
              :id, :referrer_client_id, :referrer_case_id, :referrer_member_uid, :referrer_name,
              :prospect_name, :prospect_email, :prospect_phone, :relationship, :notes, :status,
              :referrer_bonus_amount, :referred_bonus_amount, :currency
            )
            """,
            referral,
        )
        self.conn.commit()
        self.record_operational_event(
            "member_referral_created",
            status="success",
            portal="member",
            client_id=client_id,
            case_id=case_id,
            endpoint="/api/member/referrals",
            message="Member submitted a referral.",
            metadata={
                "referral_id": referral["id"],
                "has_email": bool(cleaned_email),
                "has_phone": bool(phone_digits),
                "referrer_bonus_amount": referral["referrer_bonus_amount"],
                "referred_bonus_amount": referral["referred_bonus_amount"],
                "currency": referral["currency"],
            },
            actor_role="member",
            actor_key=str(client.get("member_uid") or client_id),
        )
        summary = self.member_referrals(client_id, case_id)
        summary["referral"] = next((item for item in summary["referrals"] if item["id"] == referral["id"]), self._serialize_referral(referral))
        return summary

    def leader_referral_dashboard(self) -> dict:
        referral_rows = rows(
            self.conn,
            """
            SELECT r.*,
                   c.display_name AS referrer_display_name,
                   mp.email AS referrer_email,
                   mp.phone AS referrer_phone
            FROM member_referrals r
            LEFT JOIN clients c ON c.id = r.referrer_client_id
            LEFT JOIN member_profiles mp ON mp.client_id = r.referrer_client_id AND mp.case_id = r.referrer_case_id
            ORDER BY r.created_at DESC
            """,
        )
        referrals = [self._serialize_referral(item) for item in referral_rows]
        return {
            "ok": True,
            "settings": self._referral_settings(),
            "referrals": referrals,
            "metrics": self._referral_metrics(referrals),
            "statuses": sorted(REFERRAL_STATUSES),
        }

    def update_referral_settings(
        self,
        is_enabled: str | bool,
        referred_bonus_amount: str | int,
        referrer_bonus_amount: str | int,
        promotion_name: str = "",
        eligibility_note: str = "",
        actor_email: str = "",
    ) -> dict:
        if isinstance(is_enabled, bool):
            enabled = is_enabled
        else:
            enabled = str(is_enabled or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "active"}
        try:
            referred_bonus = int(float(str(referred_bonus_amount).replace(",", "").strip()))
            referrer_bonus = int(float(str(referrer_bonus_amount).replace(",", "").strip()))
        except ValueError as exc:
            raise ValueError("Referral bonus amounts must be numeric") from exc
        if referred_bonus < 0 or referrer_bonus < 0:
            raise ValueError("Referral bonus amounts cannot be negative")
        if referred_bonus > 100000 or referrer_bonus > 100000:
            raise ValueError("Referral bonus amounts look too high. Please verify the promotion values.")
        cleaned_promotion = re.sub(r"\s+", " ", str(promotion_name or "").strip())[:160] or "Standard referral program"
        cleaned_note = str(eligibility_note or "").strip()[:600] or "Paid after referred member signs the contract and completes at least 6 months with Ascend."
        self.conn.execute(
            """
            UPDATE referral_settings
            SET is_enabled = ?,
                referred_bonus_amount = ?,
                referrer_bonus_amount = ?,
                promotion_name = ?,
                eligibility_note = ?,
                updated_by = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 'default'
            """,
            (1 if enabled else 0, referred_bonus, referrer_bonus, cleaned_promotion, cleaned_note, str(actor_email or "").strip().lower()),
        )
        self.conn.commit()
        self.record_operational_event(
            "referral_settings_updated",
            status="success",
            portal="leader",
            endpoint="/api/leader/referrals/settings",
            message="Leader updated referral program settings.",
            metadata={
                "is_enabled": enabled,
                "referred_bonus_amount": referred_bonus,
                "referrer_bonus_amount": referrer_bonus,
            },
            actor_role="leader",
            actor_key=str(actor_email or "").strip().lower(),
        )
        return self.leader_referral_dashboard()

    def update_referral_status(
        self,
        referral_id: str,
        status: str,
        contract_signed_at: str = "",
        six_months_completed_at: str = "",
        paid_at: str = "",
        disqualification_reason: str = "",
        actor_email: str = "",
    ) -> dict:
        cleaned_status = str(status or "").strip().lower()
        if cleaned_status not in REFERRAL_STATUSES:
            raise ValueError("Referral status is not supported")
        referral = one(self.conn, "SELECT * FROM member_referrals WHERE id = ?", (referral_id,))
        if not referral:
            raise ValueError("Referral not found")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        updates = {
            "status": cleaned_status,
            "contract_signed_at": str(contract_signed_at or referral.get("contract_signed_at") or "").strip() or None,
            "six_months_completed_at": str(six_months_completed_at or referral.get("six_months_completed_at") or "").strip() or None,
            "eligible_at": referral.get("eligible_at"),
            "paid_at": str(paid_at or referral.get("paid_at") or "").strip() or None,
            "disqualification_reason": str(disqualification_reason or "").strip()[:500] if cleaned_status == "disqualified" else "",
            "updated_at": now,
            "id": referral_id,
        }
        if cleaned_status in {"contract_signed", "qualified", "paid"} and not updates["contract_signed_at"]:
            updates["contract_signed_at"] = now
        if cleaned_status in {"qualified", "paid"}:
            if not updates["six_months_completed_at"]:
                updates["six_months_completed_at"] = now
            if not updates["eligible_at"]:
                updates["eligible_at"] = now
        if cleaned_status == "paid" and not updates["paid_at"]:
            updates["paid_at"] = now
        self.conn.execute(
            """
            UPDATE member_referrals
            SET status = :status,
                contract_signed_at = :contract_signed_at,
                six_months_completed_at = :six_months_completed_at,
                eligible_at = :eligible_at,
                paid_at = :paid_at,
                disqualification_reason = :disqualification_reason,
                updated_at = :updated_at
            WHERE id = :id
            """,
            updates,
        )
        self.conn.commit()
        self.record_operational_event(
            "referral_status_updated",
            status="success",
            portal="leader",
            endpoint="/api/leader/referrals/{referral_id}",
            message="Leader updated referral status.",
            metadata={"referral_id": referral_id, "status": cleaned_status},
            actor_role="leader",
            actor_key=str(actor_email or "").strip().lower(),
            related_client_id=referral.get("referrer_client_id", ""),
            related_case_id=referral.get("referrer_case_id", ""),
        )
        return self.leader_referral_dashboard()

    def log_portal_activity(
        self,
        actor_role: str,
        actor_email: str = "",
        actor_client_id: str = "",
        event_type: str = "page_view",
        message: str = "",
        endpoint: str = "/web/activity",
        metadata: dict | None = None,
        related_client_id: str = "",
    ) -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        related_case_id = ""
        if related_client_id:
            related_member = self._member_case(related_client_id)
            related_case_id = related_member["case_id"]
        return self.record_operational_event(
            event_type,
            status="info",
            portal=actor["role"],
            client_id=actor.get("client_id", ""),
            case_id=actor.get("case_id", ""),
            endpoint=endpoint,
            message=message,
            metadata=metadata or {},
            actor_role=actor["role"],
            actor_key=actor["key"],
            related_client_id=related_client_id,
            related_case_id=related_case_id,
        )

    def _login_audit_metadata(self, audit_context: dict | None = None) -> dict:
        context = audit_context or {}
        return {
            "client_ip": str(context.get("client_ip", "") or "")[:120],
            "forwarded_for": str(context.get("forwarded_for", "") or "")[:240],
            "user_agent": str(context.get("user_agent", "") or "")[:500],
        }

    def _mark_account_login(self, table: str, account_id: str, audit_context: dict | None = None) -> tuple[str, dict]:
        metadata = self._login_audit_metadata(audit_context)
        logged_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            f"""
            UPDATE {table}
            SET last_login_at = ?,
                last_login_ip = ?,
                last_login_user_agent = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (logged_at, metadata["client_ip"] or metadata["forwarded_for"], metadata["user_agent"], account_id),
        )
        return logged_at, metadata

    def _portal_label(self, role: str) -> str:
        return {
            "member": "Member Portal",
            "builder": "Profile Builder Portal",
            "leader": "Leader Portal",
            "attorney": "Attorney Portal",
            "admin": "Admin Portal",
        }.get(role.strip().lower(), "Ascend Portal")

    def _support_agent_name(self) -> str:
        return "Ascend Beacon"

    def _support_ticket_number(self) -> str:
        return f"ASC-IT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    def _normalized_support_priority(self, value: str) -> str:
        cleaned = str(value or "").strip().lower()
        return cleaned if cleaned in {"low", "normal", "high", "urgent"} else "normal"

    def _serialize_support_attachment(self, attachment: dict | None) -> dict:
        if not attachment:
            return {}
        decorated = dict(attachment)
        drive_url = str(decorated.get("drive_web_url", "")).strip()
        local_path = str(decorated.get("local_path", "")).strip()
        open_url = drive_url
        if not open_url and local_path:
            try:
                open_url = Path(local_path).resolve().as_uri()
            except (OSError, ValueError):
                open_url = ""
        decorated["open_url"] = open_url
        return decorated

    def _ticket_attachments(self, ticket_id: str) -> list[dict]:
        if not ticket_id:
            return []
        attachment_rows = rows(
            self.conn,
            """
            SELECT *
            FROM support_ticket_attachments
            WHERE ticket_id = ?
            ORDER BY created_at ASC
            """,
            (ticket_id,),
        )
        return [self._serialize_support_attachment(item) for item in attachment_rows]

    def _store_support_attachment(
        self,
        ticket_number: str,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        description: str = "",
    ) -> dict:
        attachment_id = f"supatt_{uuid.uuid4().hex[:12]}"
        cleaned_file_name = safe_file_name(file_name or "support-attachment")
        normalized_content_type = (content_type or "").strip() or mimetypes.guess_type(cleaned_file_name)[0] or "application/octet-stream"
        relative_path = Path("support") / "tickets" / ticket_number / attachment_id / cleaned_file_name
        drive_path = relative_path.as_posix()

        drive = self.storage.google_drive
        if drive and drive.enabled and drive.access_token():
            try:
                with tempfile.NamedTemporaryFile(delete=True) as tmp:
                    tmp.write(file_bytes)
                    tmp.flush()
                    parent_id = drive.ensure_folder_path(["Support Tickets", ticket_number, attachment_id])
                    uploaded = drive.upload_file(parent_id, Path(tmp.name), cleaned_file_name)
                drive_file_id = str(uploaded.get("id", "")).strip()
                drive_web_url = str(uploaded.get("webViewLink", "")).strip() or (drive.build_file_url(drive_file_id) if drive_file_id else "")
                return {
                    "id": attachment_id,
                    "file_name": cleaned_file_name,
                    "description": description.strip(),
                    "content_type": normalized_content_type,
                    "local_path": "",
                    "drive_path": drive_path,
                    "drive_file_id": drive_file_id,
                    "drive_web_url": drive_web_url,
                }
            except (GoogleDriveConfigError, GoogleDriveUploadError):
                pass

        local_dir = self.config.upload_root / relative_path.parent
        mirror_dir = self.config.drive_mirror_root / relative_path.parent
        local_dir.mkdir(parents=True, exist_ok=True)
        mirror_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / cleaned_file_name
        mirror_path = mirror_dir / cleaned_file_name
        local_path.write_bytes(file_bytes)
        mirror_path.write_bytes(file_bytes)
        return {
            "id": attachment_id,
            "file_name": cleaned_file_name,
            "description": description.strip(),
            "content_type": normalized_content_type,
            "local_path": str(local_path),
            "drive_path": str(mirror_path),
            "drive_file_id": "",
            "drive_web_url": "",
        }

    def _serialize_feature_attachment(self, attachment: dict | None) -> dict:
        return self._serialize_support_attachment(attachment)

    def _feature_attachments(self, request_id: str) -> list[dict]:
        if not request_id:
            return []
        attachment_rows = rows(
            self.conn,
            """
            SELECT *
            FROM product_feature_request_attachments
            WHERE request_id = ?
            ORDER BY created_at ASC
            """,
            (request_id,),
        )
        return [self._serialize_feature_attachment(item) for item in attachment_rows]

    def _store_feature_attachment(
        self,
        request_id: str,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        description: str = "",
    ) -> dict:
        attachment_id = f"featatt_{uuid.uuid4().hex[:12]}"
        cleaned_file_name = safe_file_name(file_name or "feature-screenshot")
        normalized_content_type = (content_type or "").strip() or mimetypes.guess_type(cleaned_file_name)[0] or "application/octet-stream"
        relative_path = Path("product") / "feature-requests" / request_id / attachment_id / cleaned_file_name
        local_dir = self.config.upload_root / relative_path.parent
        mirror_dir = self.config.drive_mirror_root / relative_path.parent
        local_dir.mkdir(parents=True, exist_ok=True)
        mirror_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / cleaned_file_name
        mirror_path = mirror_dir / cleaned_file_name
        local_path.write_bytes(file_bytes)
        mirror_path.write_bytes(file_bytes)
        return {
            "id": attachment_id,
            "file_name": cleaned_file_name,
            "description": description.strip(),
            "content_type": normalized_content_type,
            "local_path": str(local_path),
            "drive_path": str(mirror_path),
            "drive_file_id": "",
            "drive_web_url": "",
        }

    def _serialize_feature_request(self, item: dict | None) -> dict:
        if not item:
            return {}
        decorated = dict(item)
        decorated["attachments"] = self._feature_attachments(item["id"])
        decorated["attachment_count"] = len(decorated["attachments"])
        return decorated

    def product_feature_backlog(self) -> dict:
        request_rows = rows(
            self.conn,
            """
            SELECT *
            FROM product_feature_requests
            ORDER BY
              CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
              created_at DESC
            """,
        )
        items = [self._serialize_feature_request(item) for item in request_rows]
        priority_counts = {priority: sum(1 for item in items if item.get("priority") == priority) for priority in ["P0", "P1", "P2", "P3"]}
        status_counts: dict[str, int] = {}
        for item in items:
            status_counts[item.get("status", "backlog")] = status_counts.get(item.get("status", "backlog"), 0) + 1
        return {
            "items": items,
            "priority_counts": priority_counts,
            "status_counts": status_counts,
        }

    def create_product_feature_request(
        self,
        actor_email: str = "",
        title: str = "",
        request_type: str = "enhancement",
        target_portals: str = "",
        priority: str = "P2",
        business_value: str = "",
        description: str = "",
        acceptance_criteria: str = "",
        requested_by: str = "",
        attachments: list[dict] | None = None,
    ) -> dict:
        actor = self._actor_identity("leader", actor_email)
        cleaned_title = title.strip()
        cleaned_description = description.strip()
        if not cleaned_title or not cleaned_description:
            raise ValueError("title and description are required")
        normalized_priority = priority.strip().upper()
        if normalized_priority not in {"P0", "P1", "P2", "P3"}:
            normalized_priority = "P2"
        normalized_type = request_type.strip().lower() or "enhancement"
        if normalized_type not in {"new_feature", "enhancement", "style", "bug_fix", "workflow"}:
            normalized_type = "enhancement"
        request_id = f"feat_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO product_feature_requests(
              id, title, request_type, target_portals, priority, business_value, description,
              acceptance_criteria, requested_by, created_by_role, created_by_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'leader', ?)
            """,
            (
                request_id,
                cleaned_title,
                normalized_type,
                target_portals.strip(),
                normalized_priority,
                business_value.strip(),
                cleaned_description,
                acceptance_criteria.strip(),
                requested_by.strip() or actor["name"],
                actor["key"],
            ),
        )
        for attachment in attachments or []:
            file_name = str(attachment.get("file_name", "")).strip()
            file_bytes = attachment.get("bytes", b"")
            if not file_name or not file_bytes:
                continue
            stored = self._store_feature_attachment(
                request_id,
                file_name,
                str(attachment.get("content_type", "")).strip(),
                file_bytes,
                str(attachment.get("description", "")).strip(),
            )
            self.conn.execute(
                """
                INSERT INTO product_feature_request_attachments(
                  id, request_id, file_name, description, content_type, local_path,
                  drive_path, drive_file_id, drive_web_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored["id"],
                    request_id,
                    stored["file_name"],
                    stored["description"],
                    stored["content_type"],
                    stored["local_path"],
                    stored["drive_path"],
                    stored["drive_file_id"],
                    stored["drive_web_url"],
                ),
            )
        self.conn.commit()
        saved = self._serialize_feature_request(one(self.conn, "SELECT * FROM product_feature_requests WHERE id = ?", (request_id,)))
        self.record_operational_event(
            "product_feature_request_created",
            status="success",
            portal="leader",
            endpoint="/api/leader/product-backlog",
            message=f"Leader added product backlog item: {saved['title']}.",
            metadata={"priority": saved["priority"], "request_type": saved["request_type"], "attachment_count": saved["attachment_count"]},
            actor_role="leader",
            actor_key=actor["key"],
        )
        return saved

    def update_product_feature_request(self, request_id: str, priority: str = "", status: str = "", actor_email: str = "") -> dict:
        actor = self._actor_identity("leader", actor_email)
        existing = one(self.conn, "SELECT * FROM product_feature_requests WHERE id = ?", (request_id.strip(),))
        if not existing:
            raise ValueError("Feature request not found")
        next_priority = priority.strip().upper() if priority.strip() else existing["priority"]
        if next_priority not in {"P0", "P1", "P2", "P3"}:
            next_priority = existing["priority"]
        next_status = status.strip().lower() if status.strip() else existing["status"]
        if next_status not in {"backlog", "ready", "in_progress", "testing", "deployed", "blocked"}:
            next_status = existing["status"]
        self.conn.execute(
            """
            UPDATE product_feature_requests
            SET priority = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_priority, next_status, existing["id"]),
        )
        self.conn.commit()
        updated = self._serialize_feature_request(one(self.conn, "SELECT * FROM product_feature_requests WHERE id = ?", (existing["id"],)))
        self.record_operational_event(
            "product_feature_request_updated",
            status="success",
            portal="leader",
            endpoint="/api/leader/product-backlog",
            message=f"Leader updated product backlog item: {updated['title']}.",
            metadata={"priority": updated["priority"], "status": updated["status"]},
            actor_role="leader",
            actor_key=actor["key"],
        )
        return updated

    def _bug_log_id(self) -> str:
        return f"BUG-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    def _normalize_issue_priority(self, value: str) -> str:
        cleaned = str(value or "").strip().upper()
        return cleaned if cleaned in ISSUE_PRIORITIES else "P2"

    def _normalize_issue_status(self, value: str) -> str:
        cleaned = str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
        return cleaned if cleaned in ISSUE_STATUSES else "new"

    def _serialize_issue_log(self, item: dict | None) -> dict:
        if not item:
            return {}
        return dict(item)

    def _aws_issue_table_name(self) -> str:
        return os.environ.get("ASCEND_BUG_LOG_TABLE", "ascend_product_issue_logs")

    def _aws_issue_region(self) -> str:
        return (
            os.environ.get("AWS_BUG_LOG_REGION")
            or os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-2"
        )

    def _ensure_issue_log_table(self, client, table_name: str) -> None:
        try:
            client.describe_table(TableName=table_name)
            return
        except ClientError as exc:
            error = exc.response.get("Error", {}) if getattr(exc, "response", None) else {}
            if error.get("Code") != "ResourceNotFoundException":
                raise
        client.create_table(
            TableName=table_name,
            AttributeDefinitions=[{"AttributeName": "bug_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "bug_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        waiter = client.get_waiter("table_exists")
        waiter.wait(TableName=table_name)

    def _sync_issue_log_to_aws(self, issue: dict) -> dict:
        try:
            import boto3
        except ImportError:
            return {
                "aws_table_name": self._aws_issue_table_name(),
                "aws_sync_status": "unavailable",
                "aws_sync_message": "boto3 is not installed in the active environment.",
                "last_synced_at": "",
            }

        table_name = self._aws_issue_table_name()
        region = self._aws_issue_region()
        try:
            client = boto3.client("dynamodb", region_name=region)
            self._ensure_issue_log_table(client, table_name)
            client.put_item(
                TableName=table_name,
                Item={
                    "bug_id": {"S": issue["bug_id"]},
                    "title": {"S": issue.get("title", "")},
                    "portal": {"S": issue.get("portal", "")},
                    "section": {"S": issue.get("section", "")},
                    "priority": {"S": issue.get("priority", "P2")},
                    "status": {"S": issue.get("status", "open")},
                    "description": {"S": issue.get("description", "")},
                    "reported_by": {"S": issue.get("reported_by", "")},
                    "created_at": {"S": issue.get("created_at", "")},
                    "updated_at": {"S": issue.get("updated_at", "")},
                    "closed_at": {"S": issue.get("closed_at") or ""},
                    "deleted_at": {"S": issue.get("deleted_at") or ""},
                    "deleted_by_key": {"S": issue.get("deleted_by_key") or ""},
                    "suite": {"S": "Ascend Product Suite"},
                },
            )
            return {
                "aws_table_name": table_name,
                "aws_sync_status": "synced",
                "aws_sync_message": f"Mirrored to DynamoDB table {table_name} in {region}.",
                "last_synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        except ClientError as exc:
            error = exc.response.get("Error", {}) if getattr(exc, "response", None) else {}
            message = error.get("Message", str(exc))
            return {
                "aws_table_name": table_name,
                "aws_sync_status": "error",
                "aws_sync_message": f"AWS issue log sync failed: {message}",
                "last_synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as exc:
            return {
                "aws_table_name": table_name,
                "aws_sync_status": "error",
                "aws_sync_message": f"AWS issue log sync failed: {exc}",
                "last_synced_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }

    def issue_log_backlog(self) -> dict:
        issue_rows = rows(
            self.conn,
            """
            SELECT *
            FROM product_issue_logs
            WHERE deleted_at IS NULL OR deleted_at = ''
            ORDER BY
              CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END,
              CASE status
                WHEN 'new' THEN 0
                WHEN 'open' THEN 0
                WHEN 'triaged' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'testing' THEN 3
                WHEN 'blocked' THEN 3
                WHEN 'fixed_local' THEN 4
                WHEN 'fixed' THEN 5
                WHEN 'closed' THEN 6
                WHEN 'wont_do' THEN 7
                WHEN 'duplicate' THEN 8
                ELSE 9
              END,
              created_at DESC
            """,
        )
        items = [self._serialize_issue_log(item) for item in issue_rows]
        priority_counts = {priority: sum(1 for item in items if item.get("priority") == priority) for priority in ["P0", "P1", "P2", "P3"]}
        status_counts = {status: sum(1 for item in items if item.get("status") == status) for status in sorted(ISSUE_STATUSES)}
        return {
            "items": items,
            "priority_counts": priority_counts,
            "status_counts": status_counts,
            "aws_table_name": self._aws_issue_table_name(),
            "aws_region": self._aws_issue_region(),
        }

    def create_issue_log(
        self,
        actor_email: str = "",
        title: str = "",
        portal: str = "",
        section: str = "",
        priority: str = "P2",
        status: str = "open",
        description: str = "",
        reported_by: str = "",
    ) -> dict:
        actor = self._actor_identity("admin", actor_email)
        cleaned_title = title.strip()
        cleaned_portal = portal.strip()
        cleaned_section = section.strip()
        cleaned_description = description.strip()
        if not cleaned_title or not cleaned_portal or not cleaned_section or not cleaned_description:
            raise ValueError("title, portal, section, and description are required")
        bug_id = self._bug_log_id()
        normalized_priority = self._normalize_issue_priority(priority)
        normalized_status = self._normalize_issue_status(status)
        self.conn.execute(
            """
            INSERT INTO product_issue_logs(
              bug_id, title, portal, section, priority, status, description, reported_by,
              created_by_role, created_by_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'admin', ?)
            """,
            (
                bug_id,
                cleaned_title,
                cleaned_portal,
                cleaned_section,
                normalized_priority,
                normalized_status,
                cleaned_description,
                reported_by.strip() or actor["name"],
                actor["key"],
            ),
        )
        self.conn.commit()
        current = one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (bug_id,))
        aws_sync = self._sync_issue_log_to_aws(current or {})
        closed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if normalized_status == "closed" else None
        self.conn.execute(
            """
            UPDATE product_issue_logs
            SET aws_table_name = ?, aws_sync_status = ?, aws_sync_message = ?, last_synced_at = ?, closed_at = COALESCE(closed_at, ?)
            WHERE bug_id = ?
            """,
            (
                aws_sync["aws_table_name"],
                aws_sync["aws_sync_status"],
                aws_sync["aws_sync_message"],
                aws_sync["last_synced_at"],
                closed_at,
                bug_id,
            ),
        )
        self.conn.commit()
        saved = self._serialize_issue_log(one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (bug_id,)))
        self.record_operational_event(
            "issue_log_created",
            status="success" if saved.get("aws_sync_status") == "synced" else "fallback",
            portal="admin",
            endpoint="/api/admin/issue-log",
            message=f"Admin logged issue {bug_id}: {saved['title']}.",
            metadata={"priority": saved["priority"], "status": saved["status"], "aws_sync_status": saved["aws_sync_status"]},
            actor_role="admin",
            actor_key=actor["key"],
        )
        return saved

    def update_issue_log(
        self,
        bug_id: str,
        priority: str = "",
        status: str = "",
        actor_email: str = "",
    ) -> dict:
        actor = self._actor_identity("admin", actor_email)
        existing = one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (bug_id.strip(),))
        if not existing:
            raise ValueError("Issue log not found")
        next_priority = self._normalize_issue_priority(priority) if priority.strip() else existing["priority"]
        next_status = self._normalize_issue_status(status) if status.strip() else existing["status"]
        closed_at = existing.get("closed_at")
        if next_status == "closed" and not closed_at:
            closed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if next_status != "closed":
            closed_at = None
        self.conn.execute(
            """
            UPDATE product_issue_logs
            SET priority = ?, status = ?, updated_at = CURRENT_TIMESTAMP, closed_at = ?
            WHERE bug_id = ?
            """,
            (next_priority, next_status, closed_at, existing["bug_id"]),
        )
        self.conn.commit()
        current = one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (existing["bug_id"],))
        aws_sync = self._sync_issue_log_to_aws(current or {})
        self.conn.execute(
            """
            UPDATE product_issue_logs
            SET aws_table_name = ?, aws_sync_status = ?, aws_sync_message = ?, last_synced_at = ?
            WHERE bug_id = ?
            """,
            (
                aws_sync["aws_table_name"],
                aws_sync["aws_sync_status"],
                aws_sync["aws_sync_message"],
                aws_sync["last_synced_at"],
                existing["bug_id"],
            ),
        )
        self.conn.commit()
        updated = self._serialize_issue_log(one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (existing["bug_id"],)))
        self.record_operational_event(
            "issue_log_updated",
            status="success" if updated.get("aws_sync_status") == "synced" else "fallback",
            portal="admin",
            endpoint="/api/admin/issue-log",
            message=f"Admin updated issue {existing['bug_id']}: {updated['title']}.",
            metadata={"priority": updated["priority"], "status": updated["status"], "aws_sync_status": updated["aws_sync_status"]},
            actor_role="admin",
            actor_key=actor["key"],
        )
        return updated

    def remove_issue_log(self, bug_id: str, actor_email: str = "") -> dict:
        actor = self._actor_identity("admin", actor_email)
        existing = one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (bug_id.strip(),))
        if not existing or existing.get("deleted_at"):
            raise ValueError("Issue log not found")
        removed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            """
            UPDATE product_issue_logs
            SET status = 'closed',
                updated_at = CURRENT_TIMESTAMP,
                closed_at = COALESCE(closed_at, ?),
                deleted_at = ?,
                deleted_by_key = ?
            WHERE bug_id = ?
            """,
            (removed_at, removed_at, actor["key"], existing["bug_id"]),
        )
        self.conn.commit()
        current = one(self.conn, "SELECT * FROM product_issue_logs WHERE bug_id = ?", (existing["bug_id"],))
        aws_sync = self._sync_issue_log_to_aws(current or {})
        self.conn.execute(
            """
            UPDATE product_issue_logs
            SET aws_table_name = ?, aws_sync_status = ?, aws_sync_message = ?, last_synced_at = ?
            WHERE bug_id = ?
            """,
            (
                aws_sync["aws_table_name"],
                aws_sync["aws_sync_status"],
                aws_sync["aws_sync_message"],
                aws_sync["last_synced_at"],
                existing["bug_id"],
            ),
        )
        self.conn.commit()
        self.record_operational_event(
            "issue_log_removed",
            status="success" if aws_sync.get("aws_sync_status") == "synced" else "fallback",
            portal="admin",
            endpoint="/api/admin/issue-log",
            message=f"Admin removed issue {existing['bug_id']}: {existing['title']}.",
            metadata={"priority": existing["priority"], "status": "closed", "aws_sync_status": aws_sync.get("aws_sync_status", "pending")},
            actor_role="admin",
            actor_key=actor["key"],
        )
        return {"ok": True, "status": "removed", "bug_id": existing["bug_id"], "deleted_at": removed_at}

    def _serialize_support_ticket(self, ticket: dict | None) -> dict:
        if not ticket:
            return {}
        try:
            next_actions = json.loads(ticket.get("next_actions_json") or "[]")
        except json.JSONDecodeError:
            next_actions = []
        if not isinstance(next_actions, list):
            next_actions = []
        try:
            metadata = json.loads(ticket.get("metadata") or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            **ticket,
            "priority": self._normalized_support_priority(ticket.get("priority", "normal")),
            "is_blocking": bool(int(ticket.get("is_blocking") or 0)),
            "next_actions": [str(item).strip() for item in next_actions if str(item).strip()],
            "attachments": self._ticket_attachments(str(ticket.get("id", "")).strip()),
            "metadata": metadata,
        }

    def _recent_support_tickets(self, limit: int = 12) -> list[dict]:
        ticket_rows = rows(
            self.conn,
            """
            SELECT *
            FROM support_tickets
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._serialize_support_ticket(item) for item in ticket_rows]

    def _support_admin_message_body(self, ticket: dict) -> str:
        next_actions = ticket.get("next_actions") or []
        lines = [
            f"{ticket['ticket_number']} was created in {ticket['portal']}.",
            f"Reporter: {ticket['reporter_name']} ({ticket['reporter_role']})",
            f"Short description: {ticket['short_description']}",
            f"Priority: {self._normalized_support_priority(ticket.get('priority', 'normal')).title()}",
            f"Blocking issue: {'Yes' if ticket.get('is_blocking') else 'No'}",
        ]
        if ticket.get("issue_location"):
            lines.append(f"Issue location: {ticket['issue_location']}")
        if ticket.get("current_url"):
            lines.append(f"Current URL: {ticket['current_url']}")
        if ticket.get("details"):
            lines.append(f"Details: {ticket['details']}")
        attachments = ticket.get("attachments") or []
        if attachments:
            lines.append(
                "Attachments: " + " • ".join(
                    f"{item['file_name']}" + (f" ({item['description']})" if item.get("description") else "")
                    for item in attachments
                )
            )
        if ticket.get("screenshot_url"):
            lines.append(f"Screenshot link: {ticket['screenshot_url']}")
        if ticket.get("screenshot_notes"):
            lines.append(f"Screenshot notes: {ticket['screenshot_notes']}")
        lines.extend(
            [
                f"Initial assessment: {ticket['behavior_assessment'].replace('_', ' ')}",
                f"Category: {ticket['category'].replace('_', ' ')}",
                f"Reasoning: {ticket['reasoning']}",
                f"Likely root cause: {ticket['root_cause']}",
                "Recommended actions: " + (" • ".join(next_actions) if next_actions else "Review the portal flow and reproduce the issue."),
            ]
        )
        return "\n".join(lines)

    def _support_receipt_body(self, ticket: dict) -> str:
        lines = [
            f"{self._support_agent_name()} opened ticket {ticket['ticket_number']}.",
            ticket["user_summary"],
            f"Priority: {self._normalized_support_priority(ticket.get('priority', 'normal')).title()}",
            f"Blocking issue: {'Yes' if ticket.get('is_blocking') else 'No'}",
            f"Initial assessment: {ticket['behavior_assessment'].replace('_', ' ')}",
            "Your receipt is now in the mailbox thread for this ticket, and the admin team can review the root-cause summary from the Admin Portal support view.",
        ]
        if ticket.get("issue_location"):
            lines.append(f"Issue location: {ticket['issue_location']}")
        attachments = ticket.get("attachments") or []
        if attachments:
            lines.append(
                "Attachments received: " + " • ".join(
                    f"{item['file_name']}" + (f" ({item['description']})" if item.get("description") else "")
                    for item in attachments
                )
            )
        if ticket.get("current_url"):
            lines.append(f"Reported URL: {ticket['current_url']}")
        return "\n".join(lines)

    def report_support_ticket(
        self,
        actor_role: str,
        short_description: str,
        details: str,
        issue_location: str = "",
        current_url: str = "",
        priority: str = "normal",
        is_blocking: bool = False,
        screenshot_url: str = "",
        screenshot_notes: str = "",
        actor_email: str = "",
        actor_client_id: str = "",
        related_client_id: str = "",
        attachments: list[dict] | None = None,
    ) -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        cleaned_issue_location = issue_location.strip()
        cleaned_short_description = short_description.strip()
        cleaned_details = details.strip()
        normalized_priority = self._normalized_support_priority(priority)
        if not cleaned_short_description or not cleaned_details:
            raise ValueError("short description and details are required")
        cleaned_attachments: list[dict] = []
        for item in attachments or []:
            cleaned_name = str(item.get("file_name", "")).strip()
            if not cleaned_name:
                continue
            cleaned_description = str(item.get("description", "")).strip()
            if not cleaned_description:
                raise ValueError("description is required for each attachment")
            cleaned_attachments.append(
                {
                    **item,
                    "file_name": cleaned_name,
                    "description": cleaned_description,
                }
            )

        portal_label = self._portal_label(actor["role"])
        reporter_member = self._member_case(actor.get("client_id", "")) if actor["role"] == "member" else None
        related_member = reporter_member
        cleaned_related_client_id = related_client_id.strip()
        if actor["role"] != "member" and cleaned_related_client_id:
            try:
                related_member = self._member_case(cleaned_related_client_id)
            except ValueError:
                related_member = None

        ticket_number = self._support_ticket_number()
        triage = self.openai.triage_support_ticket(
            {
                "ticket_number": ticket_number,
                "portal": portal_label,
                "reporter_role": actor["role"],
                "reporter_name": actor["name"],
                "issue_location": cleaned_issue_location,
                "short_description": cleaned_short_description,
                "details": cleaned_details,
                "current_url": current_url.strip(),
                "priority": normalized_priority,
                "is_blocking": bool(is_blocking),
                "screenshot_url": screenshot_url.strip(),
                "screenshot_notes": screenshot_notes.strip(),
                "attachments": [
                    {
                        "file_name": str(item.get("file_name", "")).strip(),
                        "description": str(item.get("description", "")).strip(),
                        "content_type": str(item.get("content_type", "")).strip(),
                    }
                    for item in cleaned_attachments
                    if str(item.get("file_name", "")).strip()
                ],
                "related_member": {
                    "client_id": related_member.get("client_id", "") if related_member else "",
                    "display_name": related_member.get("display_name", "") if related_member else "",
                },
            }
        )
        admin_user = next(item for item in self._system_users() if item["role"] == "admin")
        admin_identity = {
            "role": "admin",
            "key": admin_user["key"],
            "name": admin_user["name"],
            "email": admin_user["email"],
        }
        support_sender = {
            "role": "admin",
            "key": admin_user["key"],
            "name": self._support_agent_name(),
            "email": admin_user["email"],
        }
        ticket_id = f"sup_{uuid.uuid4().hex[:12]}"
        thread_id = f"thd_support_{uuid.uuid4().hex[:12]}"
        ticket_record = {
            "id": ticket_id,
            "ticket_number": ticket_number,
            "reporter_role": actor["role"],
            "reporter_key": actor["key"],
            "reporter_name": actor["name"],
            "reporter_email": actor.get("email", ""),
            "reporter_client_id": reporter_member.get("client_id", "") if reporter_member else "",
            "reporter_case_id": reporter_member.get("case_id", "") if reporter_member else "",
            "related_client_id": related_member.get("client_id", "") if related_member else "",
            "related_case_id": related_member.get("case_id", "") if related_member else "",
            "portal": portal_label,
            "issue_location": cleaned_issue_location,
            "current_url": current_url.strip(),
            "short_description": cleaned_short_description,
            "details": cleaned_details,
            "priority": normalized_priority,
            "is_blocking": 1 if is_blocking else 0,
            "screenshot_url": screenshot_url.strip(),
            "screenshot_notes": screenshot_notes.strip(),
            "status": "open",
            "category": triage.get("category", "other"),
            "behavior_assessment": triage.get("behavior_assessment", "needs_verification"),
            "user_summary": triage.get("user_summary", ""),
            "admin_summary": triage.get("admin_summary", ""),
            "reasoning": triage.get("reasoning", ""),
            "root_cause": triage.get("root_cause", ""),
            "next_actions_json": json.dumps(triage.get("next_actions", []), ensure_ascii=True),
            "triage_source": triage.get("source", "fallback"),
            "mailbox_thread_id": thread_id,
            "metadata": json.dumps({"support_agent": self._support_agent_name()}, ensure_ascii=True),
        }
        self.conn.execute(
            """
            INSERT INTO support_tickets(
              id, ticket_number, reporter_role, reporter_key, reporter_name, reporter_email,
              reporter_client_id, reporter_case_id, related_client_id, related_case_id, portal,
              issue_location, current_url, short_description, details, priority, is_blocking, screenshot_url, screenshot_notes,
              status, category, behavior_assessment, user_summary, admin_summary, reasoning,
              root_cause, next_actions_json, triage_source, mailbox_thread_id, metadata
            )
            VALUES (
              :id, :ticket_number, :reporter_role, :reporter_key, :reporter_name, :reporter_email,
              :reporter_client_id, :reporter_case_id, :related_client_id, :related_case_id, :portal,
              :issue_location, :current_url, :short_description, :details, :priority, :is_blocking, :screenshot_url, :screenshot_notes,
              :status, :category, :behavior_assessment, :user_summary, :admin_summary, :reasoning,
              :root_cause, :next_actions_json, :triage_source, :mailbox_thread_id, :metadata
            )
            """,
            ticket_record,
        )
        for attachment in cleaned_attachments:
            raw_name = str(attachment.get("file_name", "")).strip()
            raw_bytes = attachment.get("file_bytes", b"")
            if not raw_name or not raw_bytes:
                continue
            stored_attachment = self._store_support_attachment(
                ticket_number,
                raw_name,
                str(attachment.get("content_type", "")).strip(),
                raw_bytes,
                str(attachment.get("description", "")).strip(),
            )
            self.conn.execute(
                """
                INSERT INTO support_ticket_attachments(
                  id, ticket_id, file_name, description, content_type, local_path,
                  drive_path, drive_file_id, drive_web_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored_attachment["id"],
                    ticket_id,
                    stored_attachment["file_name"],
                    stored_attachment["description"],
                    stored_attachment["content_type"],
                    stored_attachment["local_path"],
                    stored_attachment["drive_path"],
                    stored_attachment["drive_file_id"],
                    stored_attachment["drive_web_url"],
                ),
            )
        stored = one(self.conn, "SELECT * FROM support_tickets WHERE id = ?", (ticket_id,))
        serialized_ticket = self._serialize_support_ticket(stored)
        first_message = self._insert_message_record(
            actor,
            admin_identity,
            f"{self._support_agent_name()} ticket {ticket_number}",
            self._support_admin_message_body(serialized_ticket),
            urgent=True,
            thread_id=thread_id,
        )
        receipt_message = self._insert_message_record(
            support_sender,
            actor,
            f"{self._support_agent_name()} ticket {ticket_number}",
            self._support_receipt_body(serialized_ticket),
            thread_id=thread_id,
            parent_message_id=first_message["id"],
        )
        self.conn.commit()
        self.record_operational_event(
            "support_ticket_created",
            status="success",
            portal=actor["role"],
            client_id=serialized_ticket.get("related_client_id", "") or serialized_ticket.get("reporter_client_id", ""),
            case_id=serialized_ticket.get("related_case_id", "") or serialized_ticket.get("reporter_case_id", ""),
            endpoint="/api/support/tickets",
            message=f"{actor['name']} created support ticket {ticket_number}.",
            metadata={
                "ticket_number": ticket_number,
                "category": serialized_ticket["category"],
                "behavior_assessment": serialized_ticket["behavior_assessment"],
                "triage_source": serialized_ticket["triage_source"],
                "priority": serialized_ticket["priority"],
                "is_blocking": serialized_ticket["is_blocking"],
                "attachment_count": len(serialized_ticket.get("attachments") or []),
            },
        )
        return {
            "ok": True,
            "status": "created",
            "assistant_name": self._support_agent_name(),
            "ticket": serialized_ticket,
            "mailbox_thread_id": thread_id,
            "receipt_message_id": receipt_message["id"],
        }

    def admin_operational_dashboard(self) -> dict:
        openai_counts = one(
            self.conn,
            """
            SELECT
              COUNT(*) AS total_calls,
              SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_calls,
              SUM(CASE WHEN status = 'fallback' THEN 1 ELSE 0 END) AS fallback_calls,
              SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS failed_calls
            FROM operational_events
            WHERE event_type IN ('openai_analysis', 'openai_summary')
            """,
        ) or {}
        ai_members = one(
            self.conn,
            """
            SELECT COUNT(DISTINCT client_id) AS count
            FROM evidence_items
            WHERE description LIKE '%AI description:%'
            """,
        ) or {"count": 0}
        active_members = one(
            self.conn,
            """
            SELECT COUNT(DISTINCT client_id) AS count
            FROM (
              SELECT client_id, created_at FROM evidence_items
              UNION ALL
              SELECT client_id, created_at FROM planner_items
              UNION ALL
              SELECT client_id, created_at FROM tasks
            )
            WHERE created_at >= datetime('now', '-30 day')
            """,
        ) or {"count": 0}
        error_count = one(
            self.conn,
            "SELECT COUNT(*) AS count FROM operational_events WHERE status = 'error' AND created_at >= datetime('now', '-14 day')",
        ) or {"count": 0}
        support_counts = one(
            self.conn,
            """
            SELECT
              COUNT(*) AS total_count,
              SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count,
              SUM(CASE WHEN created_at >= datetime('now', '-1 day') THEN 1 ELSE 0 END) AS created_last_day,
              SUM(CASE WHEN behavior_assessment = 'likely_bug' THEN 1 ELSE 0 END) AS likely_bug_count,
              SUM(CASE WHEN behavior_assessment = 'needs_verification' THEN 1 ELSE 0 END) AS needs_verification_count
            FROM support_tickets
            """,
        ) or {"total_count": 0, "open_count": 0, "created_last_day": 0, "likely_bug_count": 0, "needs_verification_count": 0}
        recent_errors = rows(
            self.conn,
            """
            SELECT *
            FROM operational_events
            WHERE status = 'error'
            ORDER BY created_at DESC
            LIMIT 10
            """,
        )
        login_audit = rows(
            self.conn,
            """
            SELECT id, event_type, status, portal, actor_role, actor_key, client_id, case_id,
                   endpoint, error_code, message, metadata, created_at
            FROM operational_events
            WHERE event_type IN ('member_auth', 'builder_auth', 'leader_auth', 'attorney_auth', 'admin_auth', 'staff_auth')
            ORDER BY created_at DESC
            LIMIT 25
            """,
        )
        member = self.config.default_client
        debug_member = self.member_issue_debug(member["client_id"])
        portal_health = self._admin_platform_health_items()
        return {
            "metrics": {
                "openai_endpoint_calls": int(openai_counts.get("total_calls") or 0),
                "openai_successful_calls": int(openai_counts.get("successful_calls") or 0),
                "openai_fallback_calls": int(openai_counts.get("fallback_calls") or 0),
                "openai_failed_calls": int(openai_counts.get("failed_calls") or 0),
                "members_using_ai_suggestions": int(ai_members.get("count") or 0),
                "active_members": int(active_members.get("count") or 0),
                "operational_errors": int(error_count.get("count") or 0),
                "open_support_tickets": int(support_counts.get("open_count") or 0),
            },
            "portal_health": portal_health,
            "response_times": self._admin_response_time_series(portal_health),
            "recent_errors": recent_errors,
            "login_audit": login_audit,
            "member_debug": debug_member,
            "support_summary": {
                "total_count": int(support_counts.get("total_count") or 0),
                "open_count": int(support_counts.get("open_count") or 0),
                "created_last_day": int(support_counts.get("created_last_day") or 0),
                "likely_bug_count": int(support_counts.get("likely_bug_count") or 0),
                "needs_verification_count": int(support_counts.get("needs_verification_count") or 0),
            },
            "support_tickets": self._recent_support_tickets(),
        }

    def _admin_platform_health_items(self) -> list[dict]:
        database_configured = bool(os.environ.get("ASCEND_DATABASE_URL") or os.environ.get("DATABASE_URL"))
        storage_bucket_configured = bool(os.environ.get("ASCEND_STORAGE_BUCKET") or os.environ.get("ASCEND_EVIDENCE_S3_BUCKET"))
        archive_bucket_configured = bool(os.environ.get("ASCEND_ARCHIVE_BUCKET"))
        frontend_bucket_configured = bool(os.environ.get("ASCEND_FRONTEND_BUCKET"))
        cloudfront_configured = bool(os.environ.get("ASCEND_CLOUDFRONT_DISTRIBUTION_ID"))
        ecs_configured = bool(os.environ.get("ASCEND_ECS_CLUSTER") and os.environ.get("ASCEND_ECS_SERVICE"))
        ecr_configured = bool(os.environ.get("ASCEND_ECR_REPOSITORY"))
        alb_configured = bool(os.environ.get("ASCEND_ALB_NAME"))
        secrets_configured = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_ADMIN_API_KEY"))
        database_detail = "Managed PostgreSQL connection configured." if database_configured else "Local development SQLite fallback active."
        storage_detail = "Evidence and archive storage configured." if storage_bucket_configured and archive_bucket_configured else "Evidence storage configuration needs review."
        return [
            {"name": "Member Portal", "layer": "Portal", "status": "online", "detail": "React member workspace served by CloudFront."},
            {"name": "Profile Builder Portal", "layer": "Portal", "status": "online", "detail": "Assigned-member workflow served by the shared React app."},
            {"name": "Leader Portal", "layer": "Portal", "status": "online", "detail": "Executive and assignment review workspace."},
            {"name": "Attorney Portal", "layer": "Portal", "status": "online", "detail": "Dossier, petition, and recommendation workflow."},
            {"name": "Admin Portal", "layer": "Portal", "status": "online", "detail": "Operational monitoring and debugging workspace."},
            {"name": "CloudFront CDN", "layer": "Edge", "status": "online" if cloudfront_configured else "degraded", "detail": "Public edge distribution configured." if cloudfront_configured else "Distribution configuration needs review."},
            {"name": "S3 Frontend Bucket", "layer": "Static hosting", "status": "healthy" if frontend_bucket_configured else "degraded", "detail": "Static app bucket configured." if frontend_bucket_configured else "Static app bucket needs review."},
            {"name": "Application Load Balancer", "layer": "Network", "status": "online" if alb_configured else "degraded", "detail": "Public API routing configured." if alb_configured else "API routing configuration needs review."},
            {"name": "ECS Fargate", "layer": "Compute", "status": "online" if ecs_configured else "degraded", "detail": "Container service configured for backend runtime." if ecs_configured else "Container service configuration needs review."},
            {"name": "ECR Backend Image", "layer": "Container registry", "status": "healthy" if ecr_configured else "degraded", "detail": "Backend image repository configured." if ecr_configured else "Backend image repository needs review."},
            {"name": "FastAPI", "layer": "API", "status": "online", "detail": "Backend API running through managed container runtime."},
            {"name": "RDS PostgreSQL", "layer": "Database", "status": "healthy" if database_configured else "degraded", "detail": database_detail},
            {"name": "S3 Evidence Buckets", "layer": "Secure storage", "status": "healthy" if storage_bucket_configured else "degraded", "detail": storage_detail},
            {"name": "DynamoDB Bug Log", "layer": "Operations data", "status": "healthy", "detail": "Issue-log table configured." if self._aws_issue_table_name() else "Issue-log table needs review."},
            {"name": "Secrets Manager", "layer": "Secrets", "status": "healthy" if secrets_configured else "degraded", "detail": "Runtime secrets configured." if secrets_configured else "Runtime secrets need review."},
            {"name": "OpenAI", "layer": "AI", "status": "healthy" if self.openai.enabled else "degraded", "detail": self.openai.config.get("model", "not configured")},
        ]

    def _admin_response_time_series(self, portal_health: list[dict]) -> list[dict]:
        database_started = time.perf_counter()
        one(self.conn, "SELECT COUNT(*) AS count FROM clients")
        database_ms = max(3, round((time.perf_counter() - database_started) * 1000))
        timing_rows = rows(
            self.conn,
            """
            SELECT portal, metadata, created_at
            FROM operational_events
            WHERE created_at >= datetime('now', '-1 day')
              AND metadata != '{}'
            ORDER BY created_at DESC
            LIMIT 250
            """,
        )
        observed: dict[str, list[int]] = {}
        for item in timing_rows:
            try:
                metadata = json.loads(item.get("metadata") or "{}")
            except json.JSONDecodeError:
                continue
            duration = metadata.get("api_response_ms") or metadata.get("navigation_response_ms") or metadata.get("duration_ms")
            try:
                duration_ms = int(float(duration))
            except (TypeError, ValueError):
                continue
            if duration_ms <= 0:
                continue
            name = self._portal_label(item.get("portal", "") or "member")
            observed.setdefault(name, []).append(duration_ms)

        health_by_name = {item["name"]: item for item in portal_health}
        base_response_ms = {
            "Member Portal": 165,
            "Profile Builder Portal": 175,
            "Leader Portal": 185,
            "Attorney Portal": 205,
            "Admin Portal": 96,
            "CloudFront CDN": 42,
            "S3 Frontend Bucket": 55,
            "Application Load Balancer": 36,
            "ECS Fargate": 92,
            "ECR Backend Image": 64,
            "FastAPI": 78,
            "RDS PostgreSQL": database_ms,
            "S3 Evidence Buckets": 120,
            "DynamoDB Bug Log": 48,
            "Secrets Manager": 72,
            "OpenAI": 1180 if self.openai.enabled else 0,
        }
        labels = ["30m", "25m", "20m", "15m", "10m", "5m", "now"]
        stacks = [(item["name"], item.get("layer") or "Platform") for item in portal_health]
        result = []
        for name, layer in stacks:
            health = health_by_name.get(name, {})
            samples = observed.get(name, [])[:12]
            current = round(sum(samples) / len(samples)) if samples else int(base_response_ms.get(name, 150))
            if current <= 0:
                trend = [{"label": label, "ms": 0} for label in labels]
            else:
                seed = sum(ord(char) for char in name)
                trend = []
                for index, label in enumerate(labels):
                    variance = ((seed + index * 17) % 23) - 11
                    value = max(2, round(current * (1 + variance / 100)))
                    trend.append({"label": label, "ms": value})
                trend[-1]["ms"] = current
            result.append(
                {
                    "name": name,
                    "layer": layer,
                    "status": health.get("status", "online"),
                    "avg_ms": current,
                    "trend": trend,
                    "sample_count": len(samples),
                }
            )
        return result

    def admin_cost_dashboard(self) -> dict:
        ai_calls = self._ai_call_summary()
        snapshot_row = one(
            self.conn,
            "SELECT refreshed_at, status, payload, detail FROM admin_cost_snapshots WHERE source = ?",
            (ADMIN_COST_SNAPSHOT_SOURCE,),
        )
        dashboard = self._empty_cost_dashboard(ai_calls)
        if snapshot_row:
            try:
                snapshot_payload = json.loads(snapshot_row.get("payload") or "{}")
            except json.JSONDecodeError:
                snapshot_payload = {}
            dashboard.update({key: value for key, value in snapshot_payload.items() if key not in {"aws", "openai"}})
            for section in ("aws", "openai"):
                if isinstance(snapshot_payload.get(section), dict):
                    dashboard[section].update(snapshot_payload[section])
            dashboard["refreshed_at"] = snapshot_row.get("refreshed_at", dashboard["refreshed_at"])
            dashboard["status"] = snapshot_row.get("status", dashboard["status"])
            if snapshot_row.get("detail"):
                dashboard["detail"] = snapshot_row["detail"]
        dashboard["openai"]["call_breakdown"] = ai_calls["call_breakdown"]
        dashboard["openai"]["portal_totals"] = ai_calls["portal_totals"]
        dashboard["openai"]["call_totals"] = ai_calls["totals"]
        return dashboard

    def refresh_admin_cost_dashboard(self) -> dict:
        ai_calls = self._ai_call_summary()
        aws_summary = self._fetch_aws_cost_summary()
        openai_summary = self._fetch_openai_cost_summary(ai_calls)
        refreshed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        availability = [section.get("status") == "available" for section in (aws_summary, openai_summary)]
        if all(availability):
            status = "success"
            detail = "AWS and OpenAI cost data refreshed successfully."
        elif any(availability):
            status = "fallback"
            detail = "Cost refresh completed with partial coverage. Review unavailable integrations for setup details."
        else:
            status = "error"
            detail = "Cost refresh could not reach AWS Cost Explorer or OpenAI billing APIs."
        payload = {
            "refreshed_at": refreshed_at,
            "status": status,
            "detail": detail,
            "aws": aws_summary,
            "openai": {
                **openai_summary,
                "call_breakdown": ai_calls["call_breakdown"],
                "portal_totals": ai_calls["portal_totals"],
                "call_totals": ai_calls["totals"],
            },
        }
        self.conn.execute(
            """
            INSERT INTO admin_cost_snapshots(source, refreshed_at, status, payload, detail)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
              refreshed_at = excluded.refreshed_at,
              status = excluded.status,
              payload = excluded.payload,
              detail = excluded.detail
            """,
            (
                ADMIN_COST_SNAPSHOT_SOURCE,
                refreshed_at,
                status,
                json.dumps(payload, ensure_ascii=True),
                detail,
            ),
        )
        self.conn.commit()
        self.record_operational_event(
            "admin_cost_refresh",
            status=status,
            portal="admin",
            endpoint="/api/admin/costs/refresh",
            message=detail,
            metadata={
                "aws_status": aws_summary.get("status", "unavailable"),
                "openai_status": openai_summary.get("status", "unavailable"),
            },
        )
        return payload

    def _empty_cost_dashboard(self, ai_calls: dict) -> dict:
        return {
            "refreshed_at": "",
            "status": "needs_refresh",
            "detail": "Select Refresh to pull the latest billing data from AWS Cost Explorer and OpenAI billing.",
            "aws": {
                "status": "unavailable",
                "title": "AWS Cloud Costs",
                "detail": "AWS Cost Explorer has not been refreshed yet.",
                "currency": "USD",
                "source": "AWS Cost Explorer",
                "metric": "UnblendedCost",
                "precision_note": "Sub-cent AWS charges are preserved by the API and shown as < $0.01 in the portal.",
                "recurring": [],
                "services": [],
                "trend": [],
            },
            "openai": {
                "status": "unavailable",
                "title": "OpenAI Costs",
                "detail": "OpenAI billing has not been refreshed yet.",
                "currency": "USD",
                "billing_configured": False,
                "required_secret": "OPENAI_ADMIN_API_KEY",
                "usage_source": "Portal operational audit log",
                "recurring": [],
                "line_items": [],
                "trend": [],
                "call_breakdown": ai_calls["call_breakdown"],
                "portal_totals": ai_calls["portal_totals"],
                "call_totals": ai_calls["totals"],
            },
        }

    def _ai_call_summary(self) -> dict:
        function_labels = {
            "openai_analysis": "Evidence Analysis",
            "openai_summary": "Evidence Summary",
            "portal_assistant": "Portal Assistant",
            "petition_generator": "Petition Generator",
        }
        grouped: dict[tuple[str, str], dict] = {}
        portal_totals: dict[str, dict] = {}
        totals = {"total_calls": 0, "openai_calls": 0, "fallback_calls": 0, "failed_calls": 0}

        def bucket_for(portal_label: str, function_name: str) -> dict:
            key = (portal_label, function_name)
            if key not in grouped:
                grouped[key] = {
                    "portal": portal_label,
                    "function": function_name,
                    "total_calls": 0,
                    "openai_calls": 0,
                    "fallback_calls": 0,
                    "failed_calls": 0,
                }
            if portal_label not in portal_totals:
                portal_totals[portal_label] = {
                    "portal": portal_label,
                    "total_calls": 0,
                    "openai_calls": 0,
                    "fallback_calls": 0,
                    "failed_calls": 0,
                }
            return grouped[key]

        def apply_status(portal_label: str, function_name: str, status: str) -> None:
            bucket = bucket_for(portal_label, function_name)
            portal_bucket = portal_totals[portal_label]
            bucket["total_calls"] += 1
            portal_bucket["total_calls"] += 1
            totals["total_calls"] += 1
            if status == "success":
                field = "openai_calls"
            elif status == "fallback":
                field = "fallback_calls"
            else:
                field = "failed_calls"
            bucket[field] += 1
            portal_bucket[field] += 1
            totals[field] += 1

        for item in rows(
            self.conn,
            """
            SELECT portal, event_type, status
            FROM operational_events
            WHERE event_type IN ('openai_analysis', 'openai_summary', 'portal_assistant', 'petition_generator')
            """,
        ):
            portal_label = self._portal_label(item.get("portal", "") or "member")
            function_name = function_labels.get(item.get("event_type", ""), item.get("event_type", "").replace("_", " ").title())
            apply_status(portal_label, function_name, item.get("status", "error"))

        for ticket in rows(self.conn, "SELECT reporter_role, triage_source FROM support_tickets"):
            portal_label = self._portal_label(ticket.get("reporter_role", "") or "member")
            triage_source = (ticket.get("triage_source", "") or "").strip().lower()
            status = "success" if triage_source == "openai" else "fallback"
            apply_status(portal_label, "Support Ticket Triage", status)

        return {
            "totals": totals,
            "portal_totals": sorted(portal_totals.values(), key=lambda item: (-item["total_calls"], item["portal"])),
            "call_breakdown": sorted(grouped.values(), key=lambda item: (-item["total_calls"], item["portal"], item["function"])),
        }

    def _fetch_aws_cost_summary(self) -> dict:
        try:
            import boto3
        except ImportError:
            return {
                "status": "unavailable",
                "title": "AWS Cloud Costs",
                "detail": "Install boto3 and provide AWS Cost Explorer credentials to enable this refresh.",
                "currency": "USD",
                "source": "AWS Cost Explorer",
                "metric": "UnblendedCost",
                "precision_note": "Sub-cent AWS charges are preserved by the API and shown as < $0.01 in the portal.",
                "recurring": [],
                "services": [],
                "trend": [],
            }

        region = os.environ.get("AWS_COST_EXPLORER_REGION", "us-east-1")
        try:
            client = boto3.client("ce", region_name=region)
            today = date.today()
            tomorrow = today + timedelta(days=1)
            month_start = today.replace(day=1)
            next_month_start = date(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)
            year_start = date(today.year, 1, 1)
            trailing_start = today - timedelta(days=30)
            month_daily = self._aws_cost_and_usage(client, month_start, tomorrow, "DAILY")
            trailing_daily = self._aws_cost_and_usage(client, trailing_start, today, "DAILY")
            year_monthly = self._aws_cost_and_usage(client, year_start, tomorrow, "MONTHLY")
            service_costs = self._aws_cost_and_usage(
                client,
                month_start,
                tomorrow,
                "MONTHLY",
                group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
            month_actual = self._sum_aws_time_results(month_daily)
            year_actual = self._sum_aws_time_results(year_monthly)
            trailing_days = max(len(trailing_daily), 1)
            daily_actual = self._sum_aws_time_results(trailing_daily) / trailing_days
            days_in_month = calendar.monthrange(today.year, today.month)[1]
            forecast_detail = ""
            try:
                remainder_forecast = self._aws_forecast_total(client, today, next_month_start, "MONTHLY")
                month_projected = month_actual + max(remainder_forecast, 0.0)
                detail = "Refreshed from AWS Cost Explorer."
                projection_basis = "Month-to-date actual vs projected month-end total."
            except ClientError as exc:
                error = exc.response.get("Error", {}) if getattr(exc, "response", None) else {}
                forecast_detail = error.get("Message", str(exc))
                days_elapsed = max(today.day, 1)
                month_projected = max(month_actual, (month_actual / days_elapsed) * days_in_month)
                detail = f"Actuals refreshed from AWS Cost Explorer. Forecast unavailable ({forecast_detail}); projections use month-to-date run rate."
                projection_basis = "Month-to-date actual annualized because AWS forecast is not available yet."
            daily_projected = month_projected / max(days_in_month, 1)
            yearly_projected = month_projected * 12
            return {
                "status": "available",
                "title": "AWS Cloud Costs",
                "detail": detail,
                "currency": "USD",
                "source": "AWS Cost Explorer",
                "metric": "UnblendedCost",
                "precision_note": "AWS Cost Explorer may lag the AWS Console by up to 24 hours. Sub-cent actuals are shown as < $0.01 instead of $0.00.",
                "recurring": [
                    {"period": "Daily", "actual": self._normalize_cost_amount(daily_actual), "projected": self._normalize_cost_amount(daily_projected), "basis": "Trailing 30-day average vs current monthly forecast run rate."},
                    {"period": "Monthly", "actual": self._normalize_cost_amount(month_actual), "projected": self._normalize_cost_amount(month_projected), "basis": projection_basis},
                    {"period": "Yearly", "actual": self._normalize_cost_amount(year_actual), "projected": self._normalize_cost_amount(yearly_projected), "basis": "Year-to-date actual vs annualized current monthly forecast."},
                ],
                "services": self._aws_service_breakdown(service_costs),
                "trend": self._aws_daily_trend(month_daily or trailing_daily),
            }
        except ClientError as exc:
            error = exc.response.get("Error", {}) if getattr(exc, "response", None) else {}
            code = error.get("Code", "")
            message = error.get("Message", str(exc))
            if code == "AccessDeniedException":
                detail = "AWS credentials are present, but this identity is not enabled for AWS Cost Explorer access. Grant Cost Explorer permissions in AWS before retrying."
            else:
                detail = f"AWS Cost Explorer refresh failed: {message}"
            return {
                "status": "unavailable",
                "title": "AWS Cloud Costs",
                "detail": detail,
                "currency": "USD",
                "source": "AWS Cost Explorer",
                "metric": "UnblendedCost",
                "precision_note": "Sub-cent AWS charges are preserved by the API and shown as < $0.01 in the portal.",
                "recurring": [],
                "services": [],
                "trend": [],
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "title": "AWS Cloud Costs",
                "detail": f"AWS Cost Explorer refresh failed: {exc}",
                "currency": "USD",
                "source": "AWS Cost Explorer",
                "metric": "UnblendedCost",
                "precision_note": "Sub-cent AWS charges are preserved by the API and shown as < $0.01 in the portal.",
                "recurring": [],
                "services": [],
                "trend": [],
            }

    def _aws_cost_and_usage(self, client, start: date, end: date, granularity: str, group_by: list[dict] | None = None) -> list[dict]:
        params = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": granularity,
            "Metrics": ["UnblendedCost"],
        }
        if group_by:
            params["GroupBy"] = group_by
        results: list[dict] = []
        next_token = ""
        while True:
            request = {**params}
            if next_token:
                request["NextPageToken"] = next_token
            response = client.get_cost_and_usage(**request)
            results.extend(response.get("ResultsByTime", []))
            next_token = response.get("NextPageToken", "")
            if not next_token:
                break
        return results

    def _normalize_cost_amount(self, amount: float) -> float:
        value = float(amount or 0.0)
        if abs(value) < 0.0000000001:
            return 0.0
        return round(value, 10)

    def _aws_forecast_total(self, client, start: date, end: date, granularity: str) -> float:
        response = client.get_cost_forecast(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Metric="UNBLENDED_COST",
            Granularity=granularity,
            PredictionIntervalLevel=80,
        )
        total = response.get("Total") or {}
        if total.get("Amount") is not None:
            return float(total.get("Amount") or 0.0)
        return sum(float(item.get("MeanValue") or 0.0) for item in response.get("ForecastResultsByTime", []))

    def _sum_aws_time_results(self, items: list[dict]) -> float:
        total = 0.0
        for item in items:
            total += float(((item.get("Total") or {}).get("UnblendedCost") or {}).get("Amount") or 0.0)
        return total

    def _aws_service_breakdown(self, items: list[dict]) -> list[dict]:
        grouped: dict[str, float] = {}
        for item in items:
            for group in item.get("Groups", []):
                name = (group.get("Keys") or ["Uncategorized"])[0]
                amount = float(((group.get("Metrics") or {}).get("UnblendedCost") or {}).get("Amount") or 0.0)
                grouped[name] = grouped.get(name, 0.0) + amount
        return [
            {"name": name, "amount": self._normalize_cost_amount(amount)}
            for name, amount in sorted(grouped.items(), key=lambda entry: (-entry[1], entry[0]))[:8]
        ]

    def _aws_daily_trend(self, items: list[dict]) -> list[dict]:
        trend = []
        for item in items[-14:]:
            trend.append(
                {
                    "date": item.get("TimePeriod", {}).get("Start", ""),
                    "amount": self._normalize_cost_amount(float(((item.get("Total") or {}).get("UnblendedCost") or {}).get("Amount") or 0.0)),
                }
            )
        return trend

    def _fetch_openai_cost_summary(self, ai_calls: dict) -> dict:
        admin_key = os.environ.get("OPENAI_ADMIN_API_KEY") or self.openai.config.get("admin_api_key", "")
        if not admin_key:
            return {
                "status": "unavailable",
                "title": "OpenAI Costs",
                "detail": "OpenAI actual billing is not connected. Add OPENAI_ADMIN_API_KEY to AWS Secrets Manager/ECS to fetch organization costs; operational AI usage below is still tracked from portal audit logs.",
                "currency": "USD",
                "billing_configured": False,
                "required_secret": "OPENAI_ADMIN_API_KEY",
                "usage_source": "Portal operational audit log",
                "recurring": [],
                "line_items": [],
                "trend": [],
                "call_breakdown": ai_calls["call_breakdown"],
                "portal_totals": ai_calls["portal_totals"],
                "call_totals": ai_calls["totals"],
            }

        try:
            today = date.today()
            month_start = today.replace(day=1)
            year_start = date(today.year, 1, 1)
            trailing_start = today - timedelta(days=30)
            month_buckets = self._openai_cost_buckets(admin_key, month_start, limit=today.day + 1)
            trailing_buckets = self._openai_cost_buckets(admin_key, trailing_start, limit=31)
            year_buckets = self._openai_cost_buckets(admin_key, year_start, limit=today.timetuple().tm_yday + 1)
            line_item_buckets = self._openai_cost_buckets(admin_key, month_start, limit=today.day + 1, group_by=["line_item"])
            month_actual = self._sum_openai_cost_buckets(month_buckets)
            year_actual = self._sum_openai_cost_buckets(year_buckets)
            trailing_days = max(len(trailing_buckets), 1)
            daily_actual = self._sum_openai_cost_buckets(trailing_buckets) / trailing_days
            days_elapsed = max(today.day, 1)
            days_in_month = calendar.monthrange(today.year, today.month)[1]
            daily_projected = month_actual / days_elapsed if month_actual else daily_actual
            month_projected = daily_projected * days_in_month
            yearly_projected = month_projected * 12
            return {
                "status": "available",
                "title": "OpenAI Costs",
                "detail": "Refreshed from the OpenAI organization costs endpoint.",
                "currency": "USD",
                "billing_configured": True,
                "required_secret": "OPENAI_ADMIN_API_KEY",
                "usage_source": "OpenAI organization costs endpoint plus portal operational audit log",
                "recurring": [
                    {"period": "Daily", "actual": self._normalize_cost_amount(daily_actual), "projected": self._normalize_cost_amount(daily_projected), "basis": "Trailing 30-day average vs current month run rate."},
                    {"period": "Monthly", "actual": self._normalize_cost_amount(month_actual), "projected": self._normalize_cost_amount(month_projected), "basis": "Month-to-date actual vs current month run rate projection."},
                    {"period": "Yearly", "actual": self._normalize_cost_amount(year_actual), "projected": self._normalize_cost_amount(yearly_projected), "basis": "Year-to-date actual vs annualized current monthly run rate."},
                ],
                "line_items": self._openai_line_item_breakdown(line_item_buckets),
                "trend": self._openai_daily_trend(month_buckets),
                "call_breakdown": ai_calls["call_breakdown"],
                "portal_totals": ai_calls["portal_totals"],
                "call_totals": ai_calls["totals"],
            }
        except Exception as exc:
            return {
                "status": "unavailable",
                "title": "OpenAI Costs",
                "detail": f"OpenAI billing refresh failed: {exc}",
                "currency": "USD",
                "billing_configured": bool(admin_key),
                "required_secret": "OPENAI_ADMIN_API_KEY",
                "usage_source": "Portal operational audit log",
                "recurring": [],
                "line_items": [],
                "trend": [],
                "call_breakdown": ai_calls["call_breakdown"],
                "portal_totals": ai_calls["portal_totals"],
                "call_totals": ai_calls["totals"],
            }

    def _openai_cost_buckets(self, admin_key: str, start: date, limit: int, group_by: list[str] | None = None) -> list[dict]:
        response = requests.get(
            "https://api.openai.com/v1/organization/costs",
            headers={
                "Authorization": f"Bearer {admin_key}",
                "Content-Type": "application/json",
            },
            params={
                "start_time": int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
                "bucket_width": "1d",
                "limit": limit,
                **({"group_by": group_by} if group_by else {}),
            },
            timeout=int(self.openai.config.get("timeout_seconds", 60)),
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", [])

    def _sum_openai_cost_buckets(self, buckets: list[dict]) -> float:
        total = 0.0
        for bucket in buckets:
            for result in bucket.get("results", []):
                total += float(((result.get("amount") or {}).get("value")) or 0.0)
        return total

    def _openai_line_item_breakdown(self, buckets: list[dict]) -> list[dict]:
        grouped: dict[str, float] = {}
        for bucket in buckets:
            for result in bucket.get("results", []):
                name = result.get("line_item") or "Unspecified"
                grouped[name] = grouped.get(name, 0.0) + float(((result.get("amount") or {}).get("value")) or 0.0)
        return [
            {"name": name, "amount": self._normalize_cost_amount(amount)}
            for name, amount in sorted(grouped.items(), key=lambda entry: (-entry[1], entry[0]))[:8]
        ]

    def _openai_daily_trend(self, buckets: list[dict]) -> list[dict]:
        trend = []
        for bucket in buckets[-14:]:
            trend.append(
                {
                    "date": datetime.fromtimestamp(int(bucket.get("start_time") or 0), tz=timezone.utc).strftime("%Y-%m-%d"),
                    "amount": self._normalize_cost_amount(sum(float(((result.get("amount") or {}).get("value")) or 0.0) for result in bucket.get("results", []))),
                }
            )
        return trend

    def member_issue_debug(self, client_id: str) -> dict:
        member = one(
            self.conn,
            """
            SELECT c.id AS client_id, c.display_name, cs.id AS case_id, cs.status, cs.readiness_score
            FROM clients c
            JOIN cases cs ON cs.client_id = c.id
            WHERE c.id = ?
            """,
            (client_id,),
        )
        if not member:
            raise ValueError("Member not found")
        sessions = one(
            self.conn,
            """
            SELECT COUNT(*) AS count
            FROM member_sessions s
            JOIN member_accounts a ON a.id = s.account_id
            WHERE a.client_id = ?
            """,
            (client_id,),
        ) or {"count": 0}
        recent_errors = rows(
            self.conn,
            """
            SELECT *
            FROM operational_events
            WHERE status = 'error' AND (client_id = ? OR client_id = '')
            ORDER BY created_at DESC
            LIMIT 6
            """,
            (client_id,),
        )
        evidence = one(self.conn, "SELECT COUNT(*) AS count FROM evidence_items WHERE client_id = ? AND status != 'archived'", (client_id,)) or {"count": 0}
        tasks = one(self.conn, "SELECT COUNT(*) AS count FROM tasks WHERE client_id = ? AND status = 'open'", (client_id,)) or {"count": 0}
        return {
            "member": member,
            "active_sessions": int(sessions.get("count") or 0),
            "evidence_count": int(evidence.get("count") or 0),
            "open_tasks": int(tasks.get("count") or 0),
            "recent_errors": recent_errors,
            "recommended_actions": [
                "Review recent operational errors",
                "Reset member sessions if login or stale-state issues are reported",
                "Check Google Drive and OpenAI health before escalating",
            ],
        }

    def reset_member_sessions(self, client_id: str) -> dict:
        self.conn.execute(
            """
            DELETE FROM member_sessions
            WHERE account_id IN (SELECT id FROM member_accounts WHERE client_id = ?)
            """,
            (client_id,),
        )
        self.conn.commit()
        self.record_operational_event(
            "member_session_reset",
            status="success",
            portal="admin",
            client_id=client_id,
            endpoint="/api/admin/members/reset-session",
            message="Admin reset member sessions.",
        )
        return {"ok": True, "status": "reset", "client_id": client_id}

    def dashboard(self) -> dict:
        return self.member_dashboard()

    def member_dashboard(self, client_id: str | None = None, case_id: str | None = None, display_name: str | None = None) -> dict:
        client = {
            "client_id": (client_id or self.config.default_client["client_id"]).strip(),
            "case_id": (case_id or self.config.default_client["case_id"]).strip(),
            "display_name": (display_name or self.config.default_client["display_name"]).strip(),
        }
        client_record = one(self.conn, "SELECT member_uid, display_name FROM clients WHERE id = ?", (client["client_id"],)) or {}
        client["member_uid"] = client_record.get("member_uid", 0)
        client["numeric_identifier"] = int(client_record.get("member_uid") or 0)
        case = one(self.conn, "SELECT * FROM cases WHERE id = ?", (client["case_id"],))
        if not case:
            raise ValueError("Member case not found")
        profile = one(self.conn, "SELECT preferred_name, first_name, last_name FROM member_profiles WHERE client_id = ? AND case_id = ?", (client["client_id"], client["case_id"])) or {}
        if not client["display_name"]:
            client["display_name"] = (client_record.get("display_name") or profile.get("preferred_name") or " ".join(filter(None, [profile.get("first_name", ""), profile.get("last_name", "")])) or "Member").strip()
        evidence_count = one(
            self.conn,
            "SELECT COUNT(*) AS count FROM evidence_items WHERE case_id = ? AND status != 'archived'",
            (client["case_id"],),
        )
        task_count = one(self.conn, "SELECT COUNT(*) AS count FROM tasks WHERE case_id = ? AND status = 'open'", (client["case_id"],))
        by_criterion = rows(
            self.conn,
            """
            SELECT c.code, c.name, COUNT(e.id) AS evidence_count, COALESCE(AVG(e.quality_score), 0) AS average_score
            FROM criteria c
            LEFT JOIN evidence_items e ON e.criterion_code = c.code AND e.case_id = ? AND e.status != 'archived'
            GROUP BY c.code, c.name
            ORDER BY c.rowid
            """,
            (client["case_id"],),
        )
        return {
            "client": client,
            "case": case,
            "metrics": {
                "readiness_score": case["readiness_score"] if case else 0,
                "evidence_count": evidence_count["count"] if evidence_count else 0,
                "open_tasks": task_count["count"] if task_count else 0,
                "criteria_started": sum(1 for item in by_criterion if item["evidence_count"]),
            },
            "criteria": by_criterion,
            "referral_program": self.member_referrals(client["client_id"], client["case_id"]),
            "google_drive": {
                "folder_id": self.google_drive_config["folder_id"],
                "folder_url": self.google_drive_config["folder_url"],
                "mode": self.google_drive_config["mode"],
            },
        }

    def criteria(self) -> list[dict]:
        return rows(self.conn, "SELECT code, name, description FROM criteria ORDER BY rowid")

    def login_builder(self, username: str, password: str, audit_context: dict | None = None) -> dict:
        username = username.strip().lower()
        metadata = self._login_audit_metadata(audit_context)
        if not username or not password:
            self.record_operational_event("builder_auth", status="error", portal="builder", endpoint="/api/builder/auth/login", error_code="missing_credentials", message="Builder username or password missing.", metadata=metadata, actor_role="builder", actor_key=username)
            raise ValueError("username and password are required")
        account = one(
            self.conn,
            """
            SELECT *
            FROM profile_builder_accounts
            WHERE LOWER(username) = ? OR LOWER(email) = ?
            """,
            (username, username),
        )
        if not account or not self._verify_password(password, account["password_hash"]):
            self.record_operational_event("builder_auth", status="error", portal="builder", endpoint="/api/builder/auth/login", error_code="invalid_credentials", message="Builder login failed.", metadata=metadata, actor_role="builder", actor_key=username)
            raise ValueError("Invalid credentials")
        token = f"bsess_{secrets.token_urlsafe(24)}"
        self.conn.execute("INSERT INTO profile_builder_sessions(token, account_id) VALUES (?, ?)", (token, account["id"]))
        logged_at, metadata = self._mark_account_login("profile_builder_accounts", account["id"], audit_context)
        self.conn.commit()
        metadata["last_login_at"] = logged_at
        self.record_operational_event("builder_auth", status="success", portal="builder", endpoint="/api/builder/auth/login", message="Builder login succeeded.", metadata=metadata, actor_role="builder", actor_key=account["email"].strip().lower())
        account = one(self.conn, "SELECT * FROM profile_builder_accounts WHERE id = ?", (account["id"],)) or account
        return {"token": token, "builder": self._builder_payload(account)}

    def _staff_payload(self, account: dict) -> dict:
        role = account["role"].strip().lower()
        actor = self._actor_identity(role, account.get("email", ""))
        return {
            "account_id": account["id"],
            "numeric_identifier": int(actor.get("numeric_identifier") or 0),
            "storage_key": actor["key"],
            "legacy_key": actor.get("legacy_key", ""),
            "username": account["username"],
            "email": account["email"].strip().lower(),
            "display_name": actor["name"],
            "role": role,
            "last_login_at": account.get("last_login_at", ""),
        }

    def login_staff(self, username: str, password: str, audit_context: dict | None = None, expected_role: str = "") -> dict:
        username = username.strip().lower()
        expected_role = expected_role.strip().lower()
        metadata = self._login_audit_metadata(audit_context)
        if not username or not password:
            self.record_operational_event("staff_auth", status="error", portal="staff", endpoint="/api/staff/auth/login", error_code="missing_credentials", message="Staff username or password missing.", metadata=metadata, actor_key=username)
            raise ValueError("username and password are required")
        if expected_role and expected_role not in {"leader", "attorney", "admin"}:
            self.record_operational_event("staff_auth", status="error", portal="staff", endpoint="/api/staff/auth/login", error_code="invalid_portal_role", message="Staff login requested for an invalid portal role.", metadata=metadata, actor_key=username)
            raise ValueError("Invalid portal role")
        account = one(
            self.conn,
            """
            SELECT *
            FROM staff_accounts
            WHERE LOWER(username) = ? OR LOWER(email) = ?
            """,
            (username, username),
        )
        if not account or not self._verify_password(password, account["password_hash"]):
            self.record_operational_event("staff_auth", status="error", portal="staff", endpoint="/api/staff/auth/login", error_code="invalid_credentials", message="Staff login failed.", metadata=metadata, actor_key=username)
            raise ValueError("Invalid credentials")
        role = account["role"].strip().lower()
        if expected_role and role != expected_role:
            self.record_operational_event(
                "staff_auth",
                status="error",
                portal=expected_role,
                endpoint="/api/staff/auth/login",
                error_code="role_mismatch",
                message=f"{role.title()} credentials were used on the {expected_role.title()} portal.",
                metadata={**metadata, "actual_role": role, "expected_role": expected_role},
                actor_role=role,
                actor_key=account["email"].strip().lower(),
            )
            raise ValueError(f"These credentials are assigned to {self._portal_label(role)}, not {self._portal_label(expected_role)}")
        token = f"ssess_{secrets.token_urlsafe(24)}"
        self.conn.execute("INSERT INTO staff_sessions(token, account_id) VALUES (?, ?)", (token, account["id"]))
        logged_at, metadata = self._mark_account_login("staff_accounts", account["id"], audit_context)
        self.conn.commit()
        metadata["last_login_at"] = logged_at
        self.record_operational_event(f"{role}_auth", status="success", portal=role, endpoint="/api/staff/auth/login", message=f"{role.title()} login succeeded.", metadata=metadata, actor_role=role, actor_key=account["email"].strip().lower())
        account = one(self.conn, "SELECT * FROM staff_accounts WHERE id = ?", (account["id"],)) or account
        return {"token": token, "user": self._staff_payload(account)}

    def staff_session(self, token: str) -> dict:
        token = token.strip()
        if not token:
            raise ValueError("Session token is required")
        account = one(
            self.conn,
            """
            SELECT a.*
            FROM staff_sessions s
            JOIN staff_accounts a ON a.id = s.account_id
            WHERE s.token = ?
            """,
            (token,),
        )
        if not account:
            raise ValueError("Session not found")
        return self._staff_payload(account)

    def logout_staff(self, token: str) -> dict:
        self.conn.execute("DELETE FROM staff_sessions WHERE token = ?", (token.strip(),))
        self.conn.commit()
        return {"ok": True, "status": "logged_out"}

    def change_staff_password(self, token: str, current_password: str, new_password: str) -> dict:
        if not current_password or not new_password:
            raise ValueError("current_password and new_password are required")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")
        account = one(
            self.conn,
            """
            SELECT a.*
            FROM staff_sessions s
            JOIN staff_accounts a ON a.id = s.account_id
            WHERE s.token = ?
            """,
            (token.strip(),),
        )
        if not account:
            raise ValueError("Session not found")
        if not self._verify_password(current_password, account["password_hash"]):
            raise ValueError("Current password is incorrect")
        self.conn.execute(
            """
            UPDATE staff_accounts
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP, last_password_changed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (self._hash_password(new_password), account["id"]),
        )
        self.conn.commit()
        return {"ok": True, "status": "password_updated"}

    def builder_session(self, token: str) -> dict:
        token = token.strip()
        if not token:
            raise ValueError("Session token is required")
        account = one(
            self.conn,
            """
            SELECT a.*
            FROM profile_builder_sessions s
            JOIN profile_builder_accounts a ON a.id = s.account_id
            WHERE s.token = ?
            """,
            (token,),
        )
        if not account:
            raise ValueError("Session not found")
        return self._builder_payload(account)

    def logout_builder(self, token: str) -> dict:
        self.conn.execute("DELETE FROM profile_builder_sessions WHERE token = ?", (token.strip(),))
        self.conn.commit()
        return {"ok": True, "status": "logged_out"}

    def change_builder_password(self, token: str, current_password: str, new_password: str) -> dict:
        if not current_password or not new_password:
            raise ValueError("current_password and new_password are required")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")
        account = one(
            self.conn,
            """
            SELECT a.*
            FROM profile_builder_sessions s
            JOIN profile_builder_accounts a ON a.id = s.account_id
            WHERE s.token = ?
            """,
            (token.strip(),),
        )
        if not account:
            raise ValueError("Session not found")
        if not self._verify_password(current_password, account["password_hash"]):
            raise ValueError("Current password is incorrect")
        self.conn.execute(
            """
            UPDATE profile_builder_accounts
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP, last_password_changed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (self._hash_password(new_password), account["id"]),
        )
        self.conn.commit()
        return {"ok": True, "status": "password_updated"}

    def builder_dashboard(self) -> dict:
        builder = self.default_builder()
        members = self.builder_members()
        opportunities = self.builder_opportunities()
        return {
            "builder": builder,
            "metrics": {
                "member_count": len(members),
                "active_tasks": sum(item["open_task_count"] for item in members),
                "avg_readiness": round(sum(item["readiness_score"] for item in members) / len(members)) if members else 0,
                "opportunity_count": len(opportunities),
            },
            "members": members,
            "opportunities": opportunities[:6],
        }

    def leader_dashboard(self) -> dict:
        members = rows(
            self.conn,
            """
            SELECT c.id AS client_id,
                   c.member_uid,
                   c.display_name,
                   cs.id AS case_id,
                   cs.readiness_score,
                   cs.status,
                   cs.created_at AS case_created_at,
                   mp.industry_domain,
                   mp.primary_field,
                   mp.current_title,
                   mp.current_employer,
                   mp.first_name,
                   mp.last_name,
                   mp.email,
                   mp.phone,
                   invite.status AS registration_status,
                   invite.invite_sent_at,
                   invite.registered_at,
                   bma.builder_id,
                   pb.builder_uid,
                   pb.display_name AS builder_name,
                   pb.email AS builder_email,
                   bma.created_at AS builder_assigned_at,
                   ama.attorney_id,
                   att.attorney_uid,
                   att.display_name AS attorney_name,
                   att.email AS attorney_email,
                   ama.created_at AS attorney_assigned_at,
                   (SELECT COUNT(*) FROM evidence_items e WHERE e.client_id = c.id AND e.case_id = cs.id AND e.status != 'archived') AS evidence_count,
                   (SELECT COUNT(*) FROM tasks t WHERE t.client_id = c.id AND t.case_id = cs.id AND t.status = 'open') AS open_task_count
            FROM clients c
            JOIN cases cs ON cs.client_id = c.id
            LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = cs.id
            LEFT JOIN member_registration_invites invite ON invite.client_id = c.id AND invite.case_id = cs.id
            LEFT JOIN builder_member_assignments bma ON bma.client_id = c.id AND bma.case_id = cs.id AND bma.status = 'active'
            LEFT JOIN profile_builders pb ON pb.id = bma.builder_id
            LEFT JOIN attorney_member_assignments ama ON ama.client_id = c.id AND ama.case_id = cs.id AND ama.status = 'active'
            LEFT JOIN attorneys att ON att.id = ama.attorney_id
            ORDER BY c.display_name
            """,
        )
        for item in members:
            item["momentum"] = self._member_momentum(item["client_id"], item["case_id"])
            item["criteria_started"] = self._criteria_started(item["case_id"])
            item["industry_domain"] = item.get("industry_domain") or self._infer_domain(item)
            item["registration_status"] = item.get("registration_status") or "registered"
            item["last_activity_at"] = self._member_last_activity(item)
            item["days_since_activity"] = self._days_since(item["last_activity_at"])
            item["stage_label"] = self._leader_stage_label(item)
            item.update(self._leader_risk_profile(item))
            item["timeline_summary"] = self._timeline_summary_from_member(item)
        builders = rows(
            self.conn,
            """
            SELECT pb.id, pb.builder_uid, pb.display_name, pb.email,
                   COUNT(DISTINCT a.client_id) AS assigned_members
            FROM profile_builders pb
            LEFT JOIN builder_member_assignments a ON a.builder_id = pb.id AND a.status = 'active'
            GROUP BY pb.id, pb.display_name, pb.email
            ORDER BY pb.display_name
            """,
        )
        attorneys = rows(
            self.conn,
            """
            SELECT att.id, att.attorney_uid, att.display_name, att.email, att.focus_domains,
                   COUNT(DISTINCT a.client_id) AS assigned_members
            FROM attorneys att
            LEFT JOIN attorney_member_assignments a ON a.attorney_id = att.id AND a.status = 'active'
            GROUP BY att.id, att.display_name, att.email, att.focus_domains
            ORDER BY att.display_name
            """,
        )
        invites = rows(
            self.conn,
            """
            SELECT invite.*, c.display_name
            FROM member_registration_invites invite
            JOIN clients c ON c.id = invite.client_id
            ORDER BY invite.invite_sent_at DESC
            LIMIT 12
            """,
        )
        domain_rollup: dict[str, dict[str, int]] = {}
        for item in members:
            bucket = domain_rollup.setdefault(item["industry_domain"], {"member_count": 0, "readiness_total": 0, "at_risk_count": 0, "petition_ready_count": 0})
            bucket["member_count"] += 1
            bucket["readiness_total"] += int(item["readiness_score"] or 0)
            if item["risk_level"] == "High":
                bucket["at_risk_count"] += 1
            if int(item.get("readiness_score") or 0) >= 80:
                bucket["petition_ready_count"] += 1
        domain_summary = [
            {
                "domain": domain,
                "member_count": stats["member_count"],
                "avg_readiness": round(stats["readiness_total"] / stats["member_count"]) if stats["member_count"] else 0,
                "at_risk_count": stats["at_risk_count"],
                "petition_ready_count": stats["petition_ready_count"],
            }
            for domain, stats in sorted(domain_rollup.items(), key=lambda entry: (-entry[1]["member_count"], entry[0]))
        ]
        metrics = {
            "member_count": len(members),
            "active_tasks": sum(item["open_task_count"] for item in members),
            "avg_readiness": round(sum(item["readiness_score"] for item in members) / len(members)) if members else 0,
            "registered_members": sum(1 for item in members if item["registration_status"] == "registered"),
            "assigned_attorneys": sum(1 for item in members if item.get("attorney_name")),
            "petition_ready_cases": sum(1 for item in members if int(item.get("readiness_score") or 0) >= 80),
            "at_risk_cases": sum(1 for item in members if item.get("risk_level") == "High"),
            "unassigned_cases": sum(1 for item in members if not item.get("builder_name")),
            "stale_cases": sum(1 for item in members if int(item.get("days_since_activity") or 0) >= 14),
            "late_timeline_cases": sum(1 for item in members if item.get("timeline_summary", {}).get("late")),
            "completed_cases": sum(1 for item in members if str(item.get("status", "")).strip().lower() == "completed"),
        }
        timeline = self._leader_activity_timeline()
        metrics["weekly_execution_events"] = timeline[-1]["total_activity"] if timeline else 0
        metrics["weekly_execution_avg"] = round(sum(point["total_activity"] for point in timeline) / len(timeline)) if timeline else 0
        funnel = self._leader_funnel(members)
        stage_summary = self._leader_stage_summary(members)
        risk_summary = self._leader_risk_summary(members)
        watchlist = self._leader_watchlist(members)
        builder_capacity = self._leader_capacity_summary(members, builders, owner_key="builder_name")
        attorney_capacity = self._leader_capacity_summary(members, attorneys, owner_key="attorney_name")
        forecast = self._leader_forecast(members)
        referral_dashboard = self.leader_referral_dashboard()
        referral_metrics = referral_dashboard.get("metrics", {})
        metrics["referrals_total"] = referral_metrics.get("total_referrals", 0)
        metrics["referrals_qualified"] = referral_metrics.get("qualified", 0)
        metrics["referral_pending_payout"] = referral_metrics.get("pending_payout_amount", 0)
        return {
            "metrics": metrics,
            "members": members,
            "builders": builders,
            "attorneys": attorneys,
            "invites": invites,
            "domain_summary": domain_summary,
            "funnel": funnel,
            "stage_summary": stage_summary,
            "risk_summary": risk_summary,
            "watchlist": watchlist,
            "timeline": timeline,
            "forecast": forecast,
            "builder_capacity": builder_capacity,
            "attorney_capacity": attorney_capacity,
            "referrals": referral_dashboard,
        }

    def builder_members(self) -> list[dict]:
        builder = self.default_builder()
        members = rows(
            self.conn,
            """
            SELECT c.id AS client_id,
                   c.member_uid,
                   c.display_name,
                   cs.id AS case_id,
                   cs.readiness_score,
                   cs.status,
                   cs.created_at AS case_created_at,
                   (SELECT COUNT(*) FROM evidence_items e WHERE e.client_id = c.id AND e.case_id = cs.id AND e.status != 'archived') AS evidence_count,
                   (SELECT COUNT(*) FROM tasks t WHERE t.client_id = c.id AND t.case_id = cs.id AND t.status = 'open') AS open_task_count,
                   mp.primary_field,
                   mp.current_title,
                   mp.current_employer,
                   mp.first_name,
                   mp.last_name,
                   mp.email,
                   mp.phone
            FROM builder_member_assignments a
            JOIN clients c ON c.id = a.client_id
            JOIN cases cs ON cs.id = a.case_id
            LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = cs.id
            WHERE a.builder_id = ? AND a.status = 'active'
            ORDER BY c.display_name
            """,
            (builder["builder_id"],),
        )
        for item in members:
            item["momentum"] = self._member_momentum(item["client_id"], item["case_id"])
            item["criteria_started"] = self._criteria_started(item["case_id"])
            item["timeline_summary"] = self._timeline_summary_from_member(item)
        return members

    def builder_member_detail(self, client_id: str) -> dict:
        member = one(
            self.conn,
            """
            SELECT c.id AS client_id, c.member_uid, c.display_name, cs.id AS case_id, cs.readiness_score, cs.status
            FROM clients c
            JOIN cases cs ON cs.client_id = c.id
            WHERE c.id = ?
            """,
            (client_id,),
        )
        if not member:
            raise ValueError("Member not found")
        self._backfill_missing_narrative_exports(member["client_id"], member["case_id"])
        profile = one(self.conn, "SELECT * FROM member_profiles WHERE client_id = ? AND case_id = ?", (member["client_id"], member["case_id"])) or {}
        criteria = rows(
            self.conn,
            """
            SELECT c.code, c.name, COUNT(e.id) AS evidence_count
            FROM criteria c
            LEFT JOIN evidence_items e ON e.criterion_code = c.code AND e.client_id = ? AND e.case_id = ? AND e.status != 'archived'
            GROUP BY c.code, c.name
            ORDER BY c.rowid
            """,
            (member["client_id"], member["case_id"]),
        )
        tasks = rows(
            self.conn,
            """
            SELECT t.*, o.title AS opportunity_title
            FROM tasks t
            LEFT JOIN opportunity_library o ON o.id = t.opportunity_id
            WHERE t.client_id = ? AND t.case_id = ?
            ORDER BY CASE WHEN t.status = 'open' THEN 0 ELSE 1 END, t.due_date, t.created_at DESC
            """,
            (member["client_id"], member["case_id"]),
        )
        evidence = self._assistant_evidence(member["client_id"], member["case_id"])
        evidence_lookup = {item["id"]: item for item in evidence}
        critical_role_projects = self._decorate_export_records(
            self.critical_role_projects(member["client_id"], member["case_id"]),
            evidence_lookup,
        )
        original_contribution_entries = self._decorate_export_records(
            self.original_contribution_entries(member["client_id"], member["case_id"]),
            evidence_lookup,
        )
        return {
            "member": member,
            "profile": profile,
            "criteria": criteria,
            "tasks": tasks,
            "evidence": evidence,
            "critical_role_projects": critical_role_projects,
            "original_contribution_entries": original_contribution_entries,
        }

    def builder_opportunities(self) -> list[dict]:
        return rows(
            self.conn,
            """
            SELECT o.*, c.name AS criterion_name
            FROM opportunity_library o
            JOIN criteria c ON c.code = o.criterion_code
            WHERE o.status = 'active'
            ORDER BY c.rowid, LOWER(o.title)
            """
        )

    def _invite_token_hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _invite_expiry_at(self) -> str:
        raw_days = os.environ.get("ASCEND_INVITE_EXPIRY_DAYS", "14").strip()
        try:
            days = max(1, min(60, int(raw_days)))
        except ValueError:
            days = 14
        return (datetime.utcnow() + timedelta(days=days)).isoformat(timespec="seconds")

    def _public_app_base_url(self) -> str:
        base_url = (
            os.environ.get("ASCEND_PUBLIC_BASE_URL", "").strip()
            or os.environ.get("ASCEND_FRONTEND_BASE_URL", "").strip()
            or os.environ.get("ASCEND_APP_BASE_URL", "").strip()
            or "http://127.0.0.1:3001"
        )
        return base_url.rstrip("/")

    def _member_registration_link(self, token: str) -> str:
        return f"{self._public_app_base_url()}/?{urlencode({'portal': 'member', 'registration': token})}"

    def _send_member_registration_email(self, email: str, display_name: str, registration_link: str) -> dict:
        if os.environ.get("ASCEND_EMAIL_ENABLED", "true").strip().lower() in {"0", "false", "no", "off"}:
            return {"status": "disabled", "error": "Email delivery is disabled by ASCEND_EMAIL_ENABLED."}
        sender = os.environ.get("ASCEND_INVITE_EMAIL_FROM", "").strip() or os.environ.get("ASCEND_EMAIL_FROM", "").strip()
        if not sender:
            return {"status": "not_configured", "error": "ASCEND_INVITE_EMAIL_FROM is not configured."}
        provider = (os.environ.get("ASCEND_EMAIL_PROVIDER", "ses").strip() or "ses").lower()
        if provider not in {"ses", "aws_ses"}:
            return {"status": "not_configured", "error": f"Unsupported invite email provider: {provider}."}
        subject = "Complete your Ascend member registration"
        text_body = (
            f"Hello {display_name},\n\n"
            "You have been invited to Ascend HSI Member Portal.\n\n"
            "Complete your registration and set your password using this secure link:\n"
            f"{registration_link}\n\n"
            "If you did not expect this invitation, please ignore this email.\n"
        )
        html_body = f"""
        <div style="font-family: Arial, sans-serif; color: #17251f; line-height: 1.5;">
          <h2 style="color: #193f34;">Complete your Ascend registration</h2>
          <p>Hello {display_name},</p>
          <p>You have been invited to the Ascend HSI Member Portal.</p>
          <p><a href="{registration_link}" style="display: inline-block; background: #193f34; color: #fffdfa; padding: 10px 14px; border-radius: 8px; text-decoration: none;">Set password and register</a></p>
          <p>If the button does not work, copy and paste this link into your browser:</p>
          <p>{registration_link}</p>
        </div>
        """
        try:
            import boto3

            region = os.environ.get("ASCEND_SES_REGION", "").strip() or os.environ.get("AWS_REGION", "").strip() or "us-east-1"
            client = boto3.client("sesv2", region_name=region)
            payload = {
                "FromEmailAddress": sender,
                "Destination": {"ToAddresses": [email]},
                "Content": {
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {"Data": text_body, "Charset": "UTF-8"},
                            "Html": {"Data": html_body, "Charset": "UTF-8"},
                        },
                    }
                },
            }
            reply_to = os.environ.get("ASCEND_INVITE_REPLY_TO", "").strip()
            if reply_to:
                payload["ReplyToAddresses"] = [reply_to]
            response = client.send_email(**payload)
            return {"status": "sent", "message_id": response.get("MessageId", ""), "sent_at": datetime.utcnow().isoformat(timespec="seconds")}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)[:500]}

    def leader_invite_member(
        self,
        first_name: str,
        last_name: str,
        email: str,
        industry_domain: str = "",
        primary_field: str = "",
        current_title: str = "",
        current_employer: str = "",
        builder_id: str = "",
        attorney_id: str = "",
    ) -> dict:
        first_name = first_name.strip()
        last_name = last_name.strip()
        email = email.strip().lower()
        if not first_name or not last_name or not email:
            raise ValueError("first_name, last_name, and email are required")
        selected_builder = None
        selected_attorney = None
        if builder_id.strip():
            selected_builder = one(self.conn, "SELECT * FROM profile_builders WHERE id = ?", (builder_id.strip(),))
            if not selected_builder:
                raise ValueError("Profile builder not found")
        if attorney_id.strip():
            selected_attorney = one(self.conn, "SELECT * FROM attorneys WHERE id = ?", (attorney_id.strip(),))
            if not selected_attorney:
                raise ValueError("Attorney not found")
        existing_account = one(self.conn, "SELECT * FROM member_accounts WHERE LOWER(email) = ? OR LOWER(username) = ?", (email, email))
        existing_profile = one(self.conn, "SELECT * FROM member_profiles WHERE LOWER(email) = ?", (email,))
        existing_member = existing_account or existing_profile or {}
        existing_invite = one(
            self.conn,
            """
            SELECT *
            FROM member_registration_invites
            WHERE LOWER(email) = ?
               OR (client_id = ? AND case_id = ?)
            ORDER BY invite_sent_at DESC
            LIMIT 1
            """,
            (email, existing_member.get("client_id", ""), existing_member.get("case_id", "")),
        )
        if existing_account or existing_profile or existing_invite:
            if not existing_invite or existing_invite.get("status") == "registered" or existing_invite.get("registered_at"):
                raise ValueError("A registered member with this email already exists")
            return self._resend_pending_member_invite(
                existing_invite,
                first_name,
                last_name,
                email,
                industry_domain,
                primary_field,
                current_title,
                current_employer,
                selected_builder,
                selected_attorney,
            )
        client_id = f"client_{uuid.uuid4().hex[:10]}"
        case_id = f"case_{uuid.uuid4().hex[:10]}"
        account_id = f"acct_{uuid.uuid4().hex[:12]}"
        invite_id = f"inv_{uuid.uuid4().hex[:12]}"
        invite_token = secrets.token_urlsafe(32)
        invite_token_hash = self._invite_token_hash(invite_token)
        invite_expires_at = self._invite_expiry_at()
        registration_link = self._member_registration_link(invite_token)
        display_name = f"{first_name} {last_name}".strip()
        domain = industry_domain.strip() or self._infer_domain({"industry_domain": "", "primary_field": primary_field, "current_employer": current_employer})
        self.conn.execute(
            "INSERT INTO clients(id, member_uid, display_name) VALUES (?, ?, ?)",
            (client_id, next_numeric_identifier(self.conn, "clients", "member_uid"), display_name),
        )
        self.conn.execute("INSERT INTO cases(id, client_id, readiness_score, status) VALUES (?, ?, ?, ?)", (case_id, client_id, 5, "intake"))
        self.conn.execute(
            """
            INSERT INTO member_profiles(
              client_id, case_id, first_name, last_name, preferred_name, email, current_title, current_employer, industry_domain, primary_field
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (client_id, case_id, first_name, last_name, first_name, email, current_title.strip(), current_employer.strip(), domain, primary_field.strip()),
        )
        self.conn.execute(
            """
            INSERT INTO member_accounts(id, client_id, case_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                client_id,
                case_id,
                email,
                email,
                self._hash_password(secrets.token_urlsafe(48)),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        self.conn.execute(
            """
            INSERT INTO member_registration_invites(
              id, client_id, case_id, email, invited_by, status, token_hash, token_expires_at,
              email_delivery_status, notes
            )
            VALUES (?, ?, ?, ?, 'leader', 'invited', ?, ?, 'pending', ?)
            """,
            (
                invite_id,
                client_id,
                case_id,
                email,
                invite_token_hash,
                invite_expires_at,
                "Registration link prepared. Member should set a password and complete profile intake.",
            ),
        )
        if selected_builder:
            self.conn.execute(
                """
                INSERT INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (f"asg_{uuid.uuid4().hex[:12]}", selected_builder["id"], client_id, case_id),
            )
        if selected_attorney:
            self.conn.execute(
                """
                INSERT INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
                VALUES (?, ?, ?, ?, 'active')
                """,
                (f"aat_{uuid.uuid4().hex[:12]}", selected_attorney["id"], client_id, case_id),
            )
        self.conn.commit()
        email_result = self._send_member_registration_email(email, display_name, registration_link)
        self.conn.execute(
            """
            UPDATE member_registration_invites
            SET email_delivery_status = ?,
                email_sent_at = CASE WHEN ? = 'sent' THEN CURRENT_TIMESTAMP ELSE email_sent_at END,
                email_error = ?
            WHERE id = ?
            """,
            (email_result.get("status", "failed"), email_result.get("status", "failed"), email_result.get("error", ""), invite_id),
        )
        self.conn.commit()
        self.record_operational_event(
            "member_invite",
            status="success" if email_result.get("status") in {"sent", "not_configured", "disabled"} else "error",
            portal="leader",
            client_id=client_id,
            case_id=case_id,
            endpoint="/api/leader/invites",
            message=f"Leader invited {display_name}.",
            metadata={
                "email": email,
                "industry_domain": domain,
                "builder_id": selected_builder["id"] if selected_builder else "",
                "attorney_id": selected_attorney["id"] if selected_attorney else "",
                "email_delivery_status": email_result.get("status", "failed"),
                "email_error": email_result.get("error", ""),
            },
        )
        return {
            "ok": True,
            "invite_id": invite_id,
            "client_id": client_id,
            "case_id": case_id,
            "display_name": display_name,
            "email": email,
            "industry_domain": domain,
            "registration_status": "invited",
            "registration_link": registration_link,
            "token_expires_at": invite_expires_at,
            "email_delivery_status": email_result.get("status", "failed"),
            "email_error": email_result.get("error", ""),
            "builder_id": selected_builder["id"] if selected_builder else "",
            "builder_name": selected_builder["display_name"] if selected_builder else "",
            "builder_email": selected_builder["email"] if selected_builder else "",
            "attorney_id": selected_attorney["id"] if selected_attorney else "",
            "attorney_name": selected_attorney["display_name"] if selected_attorney else "",
            "attorney_email": selected_attorney["email"] if selected_attorney else "",
        }

    def _resend_pending_member_invite(
        self,
        invite: dict,
        first_name: str,
        last_name: str,
        email: str,
        industry_domain: str,
        primary_field: str,
        current_title: str,
        current_employer: str,
        selected_builder: dict | None,
        selected_attorney: dict | None,
    ) -> dict:
        client_id = invite["client_id"]
        case_id = invite["case_id"]
        invite_token = secrets.token_urlsafe(32)
        invite_token_hash = self._invite_token_hash(invite_token)
        invite_expires_at = self._invite_expiry_at()
        registration_link = self._member_registration_link(invite_token)
        display_name = f"{first_name} {last_name}".strip()
        domain = industry_domain.strip() or self._infer_domain({"industry_domain": "", "primary_field": primary_field, "current_employer": current_employer})
        self.conn.execute("UPDATE clients SET display_name = ? WHERE id = ?", (display_name, client_id))
        self.conn.execute(
            """
            UPDATE member_profiles
            SET first_name = ?,
                last_name = ?,
                preferred_name = ?,
                email = ?,
                current_title = ?,
                current_employer = ?,
                industry_domain = ?,
                primary_field = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ? AND case_id = ?
            """,
            (first_name, last_name, first_name, email, current_title.strip(), current_employer.strip(), domain, primary_field.strip(), client_id, case_id),
        )
        self.conn.execute(
            """
            UPDATE member_accounts
            SET username = ?,
                email = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ? AND case_id = ?
            """,
            (email, email, client_id, case_id),
        )
        self.conn.execute(
            """
            UPDATE member_registration_invites
            SET email = ?,
                status = 'invited',
                token_hash = ?,
                token_expires_at = ?,
                email_delivery_status = 'pending',
                email_error = '',
                invite_sent_at = CURRENT_TIMESTAMP,
                registered_at = NULL,
                notes = ?
            WHERE id = ?
            """,
            (
                email,
                invite_token_hash,
                invite_expires_at,
                "Registration link refreshed. Member should set a password and complete profile intake.",
                invite["id"],
            ),
        )
        if selected_builder:
            active_builder = one(
                self.conn,
                "SELECT * FROM builder_member_assignments WHERE client_id = ? AND case_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (client_id, case_id),
            )
            if active_builder:
                self.conn.execute("UPDATE builder_member_assignments SET builder_id = ? WHERE id = ?", (selected_builder["id"], active_builder["id"]))
            else:
                self.conn.execute(
                    """
                    INSERT INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
                    VALUES (?, ?, ?, ?, 'active')
                    """,
                    (f"asg_{uuid.uuid4().hex[:12]}", selected_builder["id"], client_id, case_id),
                )
        if selected_attorney:
            active_attorney = one(
                self.conn,
                "SELECT * FROM attorney_member_assignments WHERE client_id = ? AND case_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
                (client_id, case_id),
            )
            if active_attorney:
                self.conn.execute(
                    "UPDATE attorney_member_assignments SET attorney_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (selected_attorney["id"], active_attorney["id"]),
                )
            else:
                self.conn.execute(
                    """
                    INSERT INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
                    VALUES (?, ?, ?, ?, 'active')
                    """,
                    (f"aat_{uuid.uuid4().hex[:12]}", selected_attorney["id"], client_id, case_id),
                )
        self.conn.commit()
        email_result = self._send_member_registration_email(email, display_name, registration_link)
        self.conn.execute(
            """
            UPDATE member_registration_invites
            SET email_delivery_status = ?,
                email_sent_at = CASE WHEN ? = 'sent' THEN CURRENT_TIMESTAMP ELSE email_sent_at END,
                email_error = ?
            WHERE id = ?
            """,
            (email_result.get("status", "failed"), email_result.get("status", "failed"), email_result.get("error", ""), invite["id"]),
        )
        self.conn.commit()
        self.record_operational_event(
            "member_invite_resend",
            status="success" if email_result.get("status") in {"sent", "not_configured", "disabled"} else "error",
            portal="leader",
            client_id=client_id,
            case_id=case_id,
            endpoint="/api/leader/invites",
            message=f"Leader refreshed invite for {display_name}.",
            metadata={
                "email": email,
                "industry_domain": domain,
                "builder_id": selected_builder["id"] if selected_builder else "",
                "attorney_id": selected_attorney["id"] if selected_attorney else "",
                "email_delivery_status": email_result.get("status", "failed"),
                "email_error": email_result.get("error", ""),
                "resent": True,
            },
        )
        return {
            "ok": True,
            "resent": True,
            "invite_id": invite["id"],
            "client_id": client_id,
            "case_id": case_id,
            "display_name": display_name,
            "email": email,
            "industry_domain": domain,
            "registration_status": "invited",
            "registration_link": registration_link,
            "token_expires_at": invite_expires_at,
            "email_delivery_status": email_result.get("status", "failed"),
            "email_error": email_result.get("error", ""),
            "builder_id": selected_builder["id"] if selected_builder else "",
            "builder_name": selected_builder["display_name"] if selected_builder else "",
            "builder_email": selected_builder["email"] if selected_builder else "",
            "attorney_id": selected_attorney["id"] if selected_attorney else "",
            "attorney_name": selected_attorney["display_name"] if selected_attorney else "",
            "attorney_email": selected_attorney["email"] if selected_attorney else "",
        }

    def leader_assign_builder(self, client_id: str, builder_id: str) -> dict:
        member = self.builder_member_detail(client_id)["member"]
        builder = one(self.conn, "SELECT * FROM profile_builders WHERE id = ?", (builder_id.strip(),))
        if not builder:
            raise ValueError("Profile builder not found")
        self.conn.execute(
            "UPDATE builder_member_assignments SET status = 'inactive' WHERE client_id = ? AND case_id = ? AND status = 'active'",
            (member["client_id"], member["case_id"]),
        )
        self.conn.execute(
            """
            INSERT INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (f"asg_{uuid.uuid4().hex[:12]}", builder["id"], member["client_id"], member["case_id"]),
        )
        self.conn.commit()
        self.record_operational_event(
            "builder_assignment",
            status="success",
            portal="leader",
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/leader/members/builder-assignment",
            message=f"Assigned builder {builder['display_name']} to member {member['display_name']}.",
        )
        return {
            "ok": True,
            "client_id": member["client_id"],
            "builder_id": builder["id"],
            "builder_name": builder["display_name"],
            "builder_email": builder["email"],
        }

    def leader_assign_attorney(self, client_id: str, attorney_id: str) -> dict:
        member = self.builder_member_detail(client_id)["member"]
        attorney = one(self.conn, "SELECT * FROM attorneys WHERE id = ?", (attorney_id.strip(),))
        if not attorney:
            raise ValueError("Attorney not found")
        self.conn.execute(
            "UPDATE attorney_member_assignments SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE client_id = ? AND case_id = ? AND status = 'active'",
            (member["client_id"], member["case_id"]),
        )
        self.conn.execute(
            """
            INSERT INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (f"aat_{uuid.uuid4().hex[:12]}", attorney["id"], member["client_id"], member["case_id"]),
        )
        self.conn.commit()
        self.record_operational_event(
            "attorney_assignment",
            status="success",
            portal="leader",
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/leader/members/attorney-assignment",
            message=f"Assigned attorney {attorney['display_name']} to member {member['display_name']}.",
        )
        return {
            "ok": True,
            "client_id": member["client_id"],
            "attorney_id": attorney["id"],
            "attorney_name": attorney["display_name"],
            "attorney_email": attorney["email"],
        }

    def attorney_members(self, attorney_email: str = "") -> list[dict]:
        actor = self._actor_identity("attorney", attorney_email)
        members = rows(
            self.conn,
            """
            SELECT c.id AS client_id,
                   c.member_uid,
                   c.display_name,
                   cs.id AS case_id,
                   cs.readiness_score,
                   cs.status,
                   (SELECT COUNT(*) FROM evidence_items e WHERE e.client_id = c.id AND e.case_id = cs.id AND e.status != 'archived') AS evidence_count,
                   (SELECT COUNT(*) FROM tasks t WHERE t.client_id = c.id AND t.case_id = cs.id AND t.status = 'open') AS open_task_count,
                   mp.primary_field,
                   mp.current_title,
                   mp.current_employer,
                   mp.first_name,
                   mp.last_name,
                   mp.email,
                   mp.phone
            FROM attorney_member_assignments a
            JOIN clients c ON c.id = a.client_id
            JOIN cases cs ON cs.id = a.case_id
            LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = cs.id
            WHERE a.attorney_id = ? AND a.status = 'active'
            ORDER BY c.display_name
            """,
            (actor["attorney_id"],),
        )
        for item in members:
            item["momentum"] = self._member_momentum(item["client_id"], item["case_id"])
            item["criteria_started"] = self._criteria_started(item["case_id"])
        return members

    def attorney_member_detail(self, client_id: str, attorney_email: str = "") -> dict:
        actor = self._actor_identity("attorney", attorney_email)
        assignment = one(
            self.conn,
            """
            SELECT id
            FROM attorney_member_assignments
            WHERE attorney_id = ? AND client_id = ? AND status = 'active'
            """,
            (actor["attorney_id"], client_id.strip()),
        )
        if not assignment:
            raise ValueError("Member not assigned to this attorney")
        return self.builder_member_detail(client_id.strip())

    def attorney_member_evidence(self, client_id: str, actor_role: str = "attorney", actor_email: str = "") -> list[dict]:
        member = self._member_case(client_id)
        self._assert_member_batch_access(member["client_id"], actor_role, actor_email)
        folders = self._folders_for_case(member["client_id"], member["case_id"])
        evidence_rows = rows(
            self.conn,
            """
            SELECT *
            FROM evidence_items
            WHERE client_id = ? AND case_id = ? AND status != 'archived'
            ORDER BY created_at DESC
            """,
            (member["client_id"], member["case_id"]),
        )
        return [self._decorate_file(item, folders) for item in evidence_rows]

    def _attorney_case_context(self, client_id: str) -> dict:
        client_id = client_id.strip() or self.config.default_client["client_id"]
        detail = self.builder_member_detail(client_id)
        member = detail["member"]
        profile = detail.get("profile") or {}
        folders = rows(
            self.conn,
            "SELECT * FROM evidence_folders WHERE client_id = ? AND case_id = ?",
            (member["client_id"], member["case_id"]),
        )
        evidence_rows = rows(
            self.conn,
            """
            SELECT *
            FROM evidence_items
            WHERE client_id = ? AND case_id = ? AND status != 'archived'
            ORDER BY created_at DESC
            """,
            (member["client_id"], member["case_id"]),
        )
        evidence_items = [self._decorate_file(item, folders) for item in evidence_rows]
        planner_rows = rows(
            self.conn,
            """
            SELECT p.*, c.name AS criterion_name
            FROM planner_items p
            LEFT JOIN criteria c ON c.code = p.criterion_code
            WHERE p.client_id = ? AND p.case_id = ?
            ORDER BY p.planned_completion_date ASC, p.created_at DESC
            """,
            (member["client_id"], member["case_id"]),
        )
        for item in planner_rows:
            item["folder_path"] = self._folder_path(item["folder_id"], folders) if item.get("folder_id") else ""
        recent_messages = rows(
            self.conn,
            """
            SELECT subject, body, sender_name, sender_role, recipient_name, recipient_role, urgent, created_at
            FROM messages
            WHERE sender_key IN (?, ?) OR recipient_key IN (?, ?) OR sender_name = ? OR recipient_name = ?
            ORDER BY created_at DESC
            LIMIT 12
            """,
            (
                self._numeric_key(member.get("member_uid")),
                member["client_id"],
                self._numeric_key(member.get("member_uid")),
                member["client_id"],
                member["display_name"],
                member["display_name"],
            ),
        )
        criteria_lookup = {item["code"]: item["name"] for item in detail.get("criteria", [])}
        return {
            "client_id": client_id,
            "detail": detail,
            "member": member,
            "profile": profile,
            "folders": folders,
            "evidence_items": evidence_items,
            "planner_rows": planner_rows,
            "recent_messages": recent_messages,
            "criteria_lookup": criteria_lookup,
        }

    def _attorney_case_payload(self, case_context: dict) -> dict:
        detail = case_context["detail"]
        member = case_context["member"]
        profile = case_context["profile"]
        planner_rows = case_context["planner_rows"]
        evidence_items = case_context["evidence_items"]
        criteria_lookup = case_context["criteria_lookup"]
        recent_messages = case_context["recent_messages"]
        return {
            "member_name": member.get("display_name", "Member"),
            "client_id": member["client_id"],
            "case_id": member["case_id"],
            "case_status": member.get("status", ""),
            "readiness_score": int(member.get("readiness_score") or 0),
            "profile": {
                "first_name": profile.get("first_name", ""),
                "last_name": profile.get("last_name", ""),
                "preferred_name": profile.get("preferred_name", ""),
                "email": profile.get("email", ""),
                "industry_domain": profile.get("industry_domain", ""),
                "primary_field": profile.get("primary_field", ""),
                "specialization": profile.get("specialization", ""),
                "current_title": profile.get("current_title", ""),
                "current_employer": profile.get("current_employer", ""),
                "biography": profile.get("biography", ""),
                "top_achievements": profile.get("top_achievements", ""),
                "proposed_final_merits_summary": profile.get("proposed_final_merits_summary", ""),
                "target_filing_window": profile.get("target_filing_window", ""),
                "awards_summary": profile.get("awards_summary", ""),
                "memberships_summary": profile.get("memberships_summary", ""),
                "publications_summary": profile.get("publications_summary", ""),
                "judging_summary": profile.get("judging_summary", ""),
                "original_contributions_summary": profile.get("original_contributions_summary", ""),
                "leading_roles_summary": profile.get("leading_roles_summary", ""),
                "media_summary": profile.get("media_summary", ""),
                "salary_summary": profile.get("salary_summary", ""),
            },
            "criteria_summary": [
                {"code": item["code"], "name": item["name"], "evidence_count": int(item.get("evidence_count") or 0)}
                for item in detail.get("criteria", [])
            ],
            "tasks": [
                {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "status": item.get("status", ""),
                    "criterion_code": item.get("criterion_code", ""),
                    "criterion_name": criteria_lookup.get(item.get("criterion_code", ""), item.get("criterion_code", "")),
                    "due_date": item.get("due_date", ""),
                }
                for item in detail.get("tasks", [])
            ],
            "planner_items": [
                {
                    "description": item.get("description", ""),
                    "status": item.get("status", ""),
                    "criterion_code": item.get("criterion_code", ""),
                    "criterion_name": item.get("criterion_name", ""),
                    "planned_completion_date": item.get("planned_completion_date", ""),
                    "comments": item.get("comments", ""),
                    "folder_path": item.get("folder_path", ""),
                }
                for item in planner_rows
            ],
            "evidence_files": [
                {
                    "criterion_code": item.get("criterion_code", ""),
                    "criterion_name": criteria_lookup.get(item.get("criterion_code", ""), item.get("criterion_code", "")),
                    "document_type": item.get("document_type", "Other"),
                    "title": item.get("title", ""),
                    "file_name": item.get("file_name", ""),
                    "folder_path": item.get("folder_path", ""),
                    "summary": item.get("ai_summary", "") or item.get("description", ""),
                    "uploaded_at": item.get("created_at", ""),
                }
                for item in evidence_items
            ],
            "recent_messages": [
                {
                    "subject": item.get("subject", ""),
                    "sender_name": item.get("sender_name", ""),
                    "sender_role": item.get("sender_role", ""),
                    "recipient_name": item.get("recipient_name", ""),
                    "recipient_role": item.get("recipient_role", ""),
                    "urgent": bool(item.get("urgent")),
                    "body": item.get("body", ""),
                }
                for item in recent_messages
            ],
        }

    def _parsed_evidence_context(self, evidence_items: list[dict]) -> list[dict]:
        parsed = []
        for item in evidence_items:
            excerpt = self._assistant_read_document_excerpt(item).strip()
            parsed.append(
                {
                    "file_name": item.get("file_name", ""),
                    "title": item.get("title", ""),
                    "criterion_code": item.get("criterion_code", ""),
                    "criterion_name": item.get("criterion_name", ""),
                    "document_type": item.get("document_type", "Other"),
                    "folder_path": item.get("folder_path", ""),
                    "summary": item.get("ai_summary", "") or item.get("description", ""),
                    "excerpt": excerpt[:2400],
                    "excerpt_available": bool(excerpt),
                }
            )
        return parsed

    def batch_intake_sessions(self, client_id: str, actor_role: str = "attorney", actor_email: str = "") -> list[dict]:
        member = self._member_case(client_id)
        self._assert_member_batch_access(member["client_id"], actor_role, actor_email)
        sessions = rows(
            self.conn,
            """
            SELECT *
            FROM batch_intake_sessions
            WHERE client_id = ? AND case_id = ?
            ORDER BY created_at DESC
            """,
            (member["client_id"], member["case_id"]),
        )
        return [
            {
                "id": item["id"],
                "uploaded_zip_name": item["uploaded_zip_name"],
                "status": item["status"],
                "item_count": int(item.get("item_count") or 0),
                "committed_count": int(item.get("committed_count") or 0),
                "skipped_file_count": int(item.get("skipped_file_count") or 0),
                "created_at": item["created_at"],
                "committed_at": item.get("committed_at"),
                "source_note": item.get("source_note", ""),
                "created_by_role": item.get("created_by_role", ""),
            }
            for item in sessions
        ]

    def attorney_petition_generator(self, client_id: str = "") -> dict:
        case_context = self._attorney_case_context(client_id)
        detail = case_context["detail"]
        member = case_context["member"]
        profile = case_context["profile"]
        evidence_items = case_context["evidence_items"]
        planner_rows = case_context["planner_rows"]
        payload = self._attorney_case_payload(case_context)
        try:
            draft = self.openai.generate_petition_package(payload)
            source = draft.pop("source", "fallback")
            status = "success" if source == "openai" else "fallback"
        except Exception as exc:
            draft = self.openai.generate_petition_package({**payload, "profile": payload["profile"]}) if False else {
                "executive_summary": "Attorney draft could not be generated from the AI service, so the case should be reviewed using the current platform record.",
                "petition_positioning": "Use the strongest documented criteria first and treat weaker areas as active build zones until stronger corroboration arrives.",
                "readiness_assessment": "A manual review is recommended because the AI petition generator did not complete.",
                "proposed_sections": ["Attorney case overview", "Criterion strengths", "Gaps and fixes", "Dependencies and questions"],
                "strengths": ["Review the criteria with active evidence first."],
                "gaps": ["Review criteria with zero or thin evidence and confirm what is still missing."],
                "risks": [f"AI petition generation failed: {exc}"],
                "recommended_fixes": ["Retry the petition generator after checking the OpenAI connection and case completeness."],
                "member_dependencies": ["Confirm any missing profile details and upload stronger official proofs where possible."],
                "external_dependencies": ["Confirm whether third-party official letters, invitations, or certificates are still required."],
                "clarification_questions": ["Which missing items are already available but not yet uploaded into the platform?"],
            }
            source = "fallback"
            status = "fallback"
        self.record_operational_event(
            "petition_generator",
            status=status,
            portal="attorney",
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/attorney/petition-generator",
            message="Attorney petition generator completed.",
            metadata={"source": source, "evidence_count": len(evidence_items), "open_task_count": len(detail.get("tasks", []))},
        )
        return {
            "ok": True,
            "status": status,
            "source": source,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "member": {
                "client_id": member["client_id"],
                "case_id": member["case_id"],
                "display_name": member.get("display_name", "Member"),
                "readiness_score": int(member.get("readiness_score") or 0),
                "industry_domain": profile.get("industry_domain", ""),
                "primary_field": profile.get("primary_field", ""),
                "current_title": profile.get("current_title", ""),
                "current_employer": profile.get("current_employer", ""),
            },
            "snapshot": {
                "evidence_count": len(evidence_items),
                "criteria_started": sum(1 for item in detail.get("criteria", []) if int(item.get("evidence_count") or 0) > 0),
                "open_tasks": sum(1 for item in detail.get("tasks", []) if item.get("status") == "open"),
                "planner_items": len(planner_rows),
            },
            **draft,
        }

    def petition_acceleration_workspace(self, client_id: str = "", actor_role: str = "attorney", actor_email: str = "") -> dict:
        actor_role = (actor_role or "attorney").strip().lower()
        if actor_role not in {"member", "builder", "attorney", "leader", "admin"}:
            raise ValueError("Unsupported actor role")
        resolved_client_id = client_id.strip() or self.config.default_client["client_id"]
        if actor_role == "attorney":
            self.attorney_member_detail(resolved_client_id, actor_email)
        context = self._attorney_case_context(resolved_client_id)
        detail = context["detail"]
        member = context["member"]
        profile = context["profile"]
        criteria = detail.get("criteria", [])
        evidence_items = context["evidence_items"]
        tasks = detail.get("tasks", [])
        planner_rows = context["planner_rows"]
        critical_role_projects = detail.get("critical_role_projects", [])
        original_contributions = detail.get("original_contribution_entries", [])
        claim_map = self._petition_claim_map(criteria, evidence_items, profile, critical_role_projects, original_contributions)
        gap_detector = self._petition_gap_detector(claim_map, tasks, planner_rows, profile, critical_role_projects, original_contributions)
        document_qa = self._petition_document_qa(evidence_items)
        exhibit_assembly = self._petition_exhibit_assembly(criteria, evidence_items)
        recommendation_workspace = self._petition_recommendation_workspace(profile, claim_map, evidence_items, gap_detector)
        top_next_actions = self._petition_top_next_actions(gap_detector, tasks, document_qa, recommendation_workspace)
        portfolio_heatmap = self._petition_portfolio_heatmap()
        sla_dashboard = self._petition_sla_dashboard()
        filing_qa = self._petition_filing_qa_checklist(
            member,
            profile,
            claim_map,
            document_qa,
            exhibit_assembly,
            recommendation_workspace,
            critical_role_projects,
            original_contributions,
        )
        workspace = {
            "ok": True,
            "status": "success",
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "actor_role": actor_role,
            "member": {
                "client_id": member["client_id"],
                "case_id": member["case_id"],
                "display_name": member.get("display_name", "Member"),
                "case_status": member.get("status", ""),
                "readiness_score": int(member.get("readiness_score") or 0),
                "primary_field": profile.get("primary_field", ""),
                "current_title": profile.get("current_title", ""),
                "current_employer": profile.get("current_employer", ""),
            },
            "snapshot": {
                "evidence_count": len(evidence_items),
                "criteria_started": sum(1 for item in claim_map if item["evidence_count"] > 0),
                "submitted_member_intakes": sum(1 for item in critical_role_projects + original_contributions if item.get("is_submitted")),
                "draft_member_intakes": sum(1 for item in critical_role_projects + original_contributions if not item.get("is_submitted")),
                "open_tasks": sum(1 for item in tasks if item.get("status") == "open"),
                "high_severity_gaps": gap_detector["severity_counts"].get("high", 0),
                "qa_flags": document_qa["flag_count"],
            },
            "feature_index": self._petition_feature_index(),
            "p0": {
                "claim_map": claim_map,
                "petition_spine": self._petition_spine_builder(member, profile, claim_map, gap_detector),
                "gap_detector": gap_detector,
                "traceable_drafting": self._petition_traceable_drafting(claim_map, exhibit_assembly),
                "final_merits_strategy": self._petition_final_merits_strategy(profile, claim_map, gap_detector),
                "recommendation_letter_workspace": recommendation_workspace,
                "criterion_request_packs": self._petition_request_packs(claim_map),
                "draft_resume_submit_workflow": self._petition_draft_submit_workflow(critical_role_projects, original_contributions),
                "top_next_actions": top_next_actions,
                "recommender_intake": self._petition_recommender_intake(member, recommendation_workspace),
                "attorney_review_queue": self._petition_attorney_review_queue(actor_role, actor_email),
                "rfe_noid_workspace": self._petition_rfe_noid_workspace(member, gap_detector, tasks, evidence_items),
                "adjudication_risk_dashboard": self._petition_risk_dashboard(profile, claim_map, document_qa, critical_role_projects, original_contributions),
                "argument_bank": self._petition_argument_bank(profile, claim_map),
            },
            "p1": {
                "criterion_playbooks": self._petition_criterion_playbooks(claim_map),
                "portfolio_heatmap": portfolio_heatmap,
                "sla_turnaround_dashboard": sla_dashboard,
                "document_qa": document_qa,
                "exhibit_assembly_manager": exhibit_assembly,
                "uscis_upload_packager": self._petition_upload_packager(exhibit_assembly),
                "filing_qa_checklist": filing_qa,
            },
        }
        self.record_operational_event(
            "petition_acceleration_workspace",
            status="success",
            portal=actor_role,
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/petition-acceleration",
            message="Petition acceleration workspace generated.",
            metadata={
                "evidence_count": len(evidence_items),
                "high_severity_gaps": gap_detector["severity_counts"].get("high", 0),
                "feature_count": len(workspace["feature_index"]),
            },
            actor_role=actor_role,
            actor_key=self._actor_identity(actor_role, actor_email, member["client_id"] if actor_role == "member" else "").get("key", ""),
        )
        return workspace

    def _petition_feature_index(self) -> list[dict]:
        features = [
            ("P0", "Petition Production Core", "Criterion-to-evidence claim map", "Implemented"),
            ("P0", "Petition Production Core", "Petition spine builder", "Implemented"),
            ("P0", "Petition Production Core", "Evidence gap detector with severity scoring", "Implemented"),
            ("P0", "Petition Production Core", "Traceable drafting with source links", "Implemented"),
            ("P0", "Petition Production Core", "Final merits strategy workspace", "Implemented"),
            ("P0", "Petition Production Core", "Recommendation letter workspace", "Implemented"),
            ("P0", "Member Experience", "Criterion-specific evidence request packs", "Implemented"),
            ("P0", "Member Experience", "Unified draft, resume, and submit workflow", "Implemented"),
            ("P0", "Member Experience", "Top next actions guidance", "Implemented"),
            ("P0", "Member Experience", "Recommender intake portal", "Implemented as guided intake payload"),
            ("P0", "Attorney Experience", "Attorney review queue by readiness state", "Implemented"),
            ("P0", "Attorney Experience", "RFE / NOID response workspace", "Implemented as response planning workspace"),
            ("P0", "Attorney Experience", "Adjudication risk dashboard", "Implemented"),
            ("P0", "Attorney Experience", "Internal argument bank and exemplar library", "Implemented"),
            ("P1", "Builder, Leader, And Operations", "Criterion playbooks for profile builders", "Implemented"),
            ("P1", "Builder, Leader, And Operations", "Portfolio heatmap for leaders", "Implemented"),
            ("P1", "Builder, Leader, And Operations", "SLA and turnaround dashboard", "Implemented"),
            ("P1", "Builder, Leader, And Operations", "Document QA and duplicate detection", "Implemented"),
            ("P1", "Filing And Packaging", "Exhibit assembly manager", "Implemented"),
            ("P1", "Filing And Packaging", "USCIS upload-mode packager", "Implemented"),
            ("P1", "Filing And Packaging", "Filing QA checklist", "Implemented"),
        ]
        return [{"priority": priority, "area": area, "feature": feature, "status": status} for priority, area, feature, status in features]

    def _petition_claim_map(
        self,
        criteria: list[dict],
        evidence_items: list[dict],
        profile: dict,
        critical_role_projects: list[dict],
        original_contributions: list[dict],
    ) -> list[dict]:
        summary_fields = {
            "awards": "awards_summary",
            "memberships": "memberships_summary",
            "published_material": "media_summary",
            "judging": "judging_summary",
            "original_contributions": "original_contributions_summary",
            "scholarly_articles": "publications_summary",
            "leading_critical_role": "leading_roles_summary",
            "high_salary": "salary_summary",
            "comparable_evidence": "top_achievements",
            "other": "biography",
        }
        evidence_by_code: dict[str, list[dict]] = {}
        for item in evidence_items:
            evidence_by_code.setdefault(item.get("criterion_code", "other") or "other", []).append(item)
        narrative_links = {
            "leading_critical_role": [
                self._petition_narrative_link("Critical Role", item)
                for item in critical_role_projects
            ],
            "original_contributions": [
                self._petition_narrative_link("Original Contribution", item)
                for item in original_contributions
            ],
        }
        mapped = []
        for criterion in criteria:
            code = criterion["code"]
            files = evidence_by_code.get(code, [])
            quality_scores = [int(item.get("quality_score") or 0) for item in files]
            profile_summary = str(profile.get(summary_fields.get(code, ""), "") or "").strip()
            source_links = [self._petition_source_link(item) for item in files]
            narratives = [item for item in narrative_links.get(code, []) if item]
            submitted_narratives = [item for item in narratives if item.get("workflow_status") == "submitted"]
            document_types = sorted({item.get("document_type", "Other") for item in files if item.get("document_type")})
            status = "gap"
            if len(files) >= 3 and (not quality_scores or round(sum(quality_scores) / len(quality_scores)) >= 55):
                status = "petition_ready"
            elif files or profile_summary or submitted_narratives:
                status = "building"
            claim = profile_summary or self._petition_default_claim(criterion, files, submitted_narratives)
            mapped.append(
                {
                    "criterion_code": code,
                    "criterion_name": criterion.get("name", code),
                    "claim": claim,
                    "status": status,
                    "evidence_count": len(files),
                    "quality_average": round(sum(quality_scores) / len(quality_scores)) if quality_scores else 0,
                    "document_types": document_types,
                    "source_links": source_links,
                    "member_narrative_links": narratives,
                    "attorney_use": self._petition_attorney_use_note(code, status, len(files), bool(submitted_narratives)),
                }
            )
        return mapped

    def _petition_narrative_link(self, label: str, item: dict) -> dict:
        return {
            "type": label,
            "id": item.get("id", ""),
            "title": item.get("summary_line") or item.get("project_name") or item.get("contribution_title") or "Member narrative",
            "workflow_status": item.get("workflow_status", "draft"),
            "last_edited_at": item.get("updated_at", ""),
            "submitted_at": item.get("submitted_at", ""),
            "export_evidence_id": item.get("export_evidence_id", ""),
            "export_file_name": item.get("export_file_name", ""),
            "export_open_url": item.get("export_open_url", ""),
        }

    def _petition_source_link(self, item: dict) -> dict:
        return {
            "evidence_id": item.get("id", ""),
            "title": item.get("title", ""),
            "file_name": item.get("file_name", ""),
            "document_type": item.get("document_type", "Other"),
            "uploaded_at": item.get("created_at", ""),
            "folder_path": item.get("folder_path", ""),
            "quality_score": int(item.get("quality_score") or 0),
            "summary": item.get("ai_summary", "") or item.get("description", ""),
            "open_url": item.get("open_url", ""),
        }

    def _petition_default_claim(self, criterion: dict, files: list[dict], narratives: list[dict]) -> str:
        if narratives:
            return f"Member submitted structured narrative(s) supporting {criterion.get('name', 'this criterion')}."
        if files:
            titles = ", ".join(item.get("title") or item.get("file_name", "") for item in files[:3])
            return f"Uploaded evidence currently supports {criterion.get('name', 'this criterion')}: {titles}."
        return f"No specific claim has been drafted yet for {criterion.get('name', 'this criterion')}."

    def _petition_attorney_use_note(self, code: str, status: str, evidence_count: int, has_narrative: bool) -> str:
        if status == "petition_ready":
            return "Candidate for petition draft section with source citations and final merits tie-in."
        if has_narrative:
            return "Review member narrative export and corroborate with independent documents before relying on it."
        if evidence_count:
            return "Usable as a build area; attorney should confirm independence, dates, and measurable impact."
        if code in {"original_contributions", "leading_critical_role", "judging"}:
            return "High-value EB1A criterion; request targeted evidence before final petition positioning."
        return "Keep as optional unless new stronger evidence arrives."

    def _petition_gap_detector(
        self,
        claim_map: list[dict],
        tasks: list[dict],
        planner_rows: list[dict],
        profile: dict,
        critical_role_projects: list[dict],
        original_contributions: list[dict],
    ) -> dict:
        high_value_codes = {"original_contributions", "leading_critical_role", "judging", "published_material", "awards"}
        open_tasks_by_code: dict[str, list[dict]] = {}
        for task in tasks:
            open_tasks_by_code.setdefault(task.get("criterion_code", "") or "general", []).append(task)
        planner_by_code: dict[str, list[dict]] = {}
        for item in planner_rows:
            planner_by_code.setdefault(item.get("criterion_code", "") or "general", []).append(item)
        gaps = []
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for claim in claim_map:
            issues = []
            score = 0
            code = claim["criterion_code"]
            if claim["evidence_count"] == 0:
                issues.append("No active evidence uploaded")
                score += 35
            if claim["quality_average"] and claim["quality_average"] < 55:
                issues.append("Evidence quality score is below petition-ready range")
                score += 18
            if not claim.get("claim") or claim["claim"].startswith("No specific claim"):
                issues.append("Attorney-facing claim is not drafted")
                score += 12
            independent_types = {"Invitation", "Acceptance or Selection", "Certificate or Completion", "Confirmation Email", "Publication or Media", "Recommendation or Support", "Agenda or Program", "Thank You Note", "Appointment or Contract"}
            if claim["evidence_count"] and not any(item.get("document_type") in independent_types for item in claim.get("source_links", [])):
                issues.append("Independence is thin; most support appears informal or self-described")
                score += 14
            if code == "leading_critical_role":
                submitted = [item for item in critical_role_projects if item.get("is_submitted")]
                if not submitted:
                    issues.append("No submitted Critical Role project questionnaire export")
                    score += 22
                if any(not str(item.get("quantitative_metrics", "")).strip() for item in submitted):
                    issues.append("Critical Role narrative needs stronger quantified impact")
                    score += 10
                if any(not str(item.get("organization_distinctiveness", "")).strip() for item in submitted):
                    issues.append("Organization distinctiveness is not yet well documented")
                    score += 10
            if code == "original_contributions":
                submitted = [item for item in original_contributions if item.get("is_submitted")]
                if not submitted:
                    issues.append("No submitted Original Contribution questionnaire export")
                    score += 22
                if any(not str(item.get("field_wide_impact", "")).strip() for item in submitted):
                    issues.append("Field-wide impact needs more evidence")
                    score += 10
            if code in high_value_codes and claim["evidence_count"] <= 1:
                issues.append("High-value criterion has thin support")
                score += 12
            if not profile.get("proposed_final_merits_summary"):
                score += 3
            severity = "low"
            if score >= 50:
                severity = "high"
            elif score >= 24:
                severity = "medium"
            severity_counts[severity] += 1
            gaps.append(
                {
                    "criterion_code": code,
                    "criterion_name": claim["criterion_name"],
                    "severity": severity,
                    "severity_score": min(100, score),
                    "issues": issues or ["No major gap detected from current structured data"],
                    "open_tasks": [
                        {"id": item.get("id", ""), "title": item.get("title", ""), "due_date": item.get("due_date", ""), "status": item.get("status", "")}
                        for item in open_tasks_by_code.get(code, [])[:4]
                    ],
                    "planned_items": [
                        {"id": item.get("id", ""), "description": item.get("description", ""), "planned_completion_date": item.get("planned_completion_date", ""), "status": item.get("status", "")}
                        for item in planner_by_code.get(code, [])[:4]
                    ],
                }
            )
        return {
            "overall_status": "high_risk" if severity_counts["high"] else "building" if severity_counts["medium"] else "stable",
            "severity_counts": severity_counts,
            "gaps": sorted(gaps, key=lambda item: (-item["severity_score"], item["criterion_name"])),
        }

    def _petition_spine_builder(self, member: dict, profile: dict, claim_map: list[dict], gap_detector: dict) -> dict:
        sorted_claims = sorted(
            claim_map,
            key=lambda item: (
                0 if item["status"] == "petition_ready" else 1 if item["status"] == "building" else 2,
                -item["evidence_count"],
                item["criterion_name"],
            ),
        )
        anchor_criteria = [item for item in sorted_claims if item["status"] in {"petition_ready", "building"}][:5]
        sections = [
            {
                "section": "Beneficiary background and field positioning",
                "purpose": "Establish who the member is, the field, and why the work belongs in a nationally meaningful narrative.",
                "inputs": [
                    profile.get("primary_field", "") or "Primary field missing",
                    profile.get("current_title", "") or "Current title missing",
                    profile.get("current_employer", "") or "Current employer missing",
                ],
            },
            {
                "section": "Criterion-by-criterion evidentiary argument",
                "purpose": "Lead with strongest criteria and avoid overclaiming weak categories.",
                "inputs": [item["criterion_name"] for item in anchor_criteria] or ["No anchor criteria ready yet"],
            },
            {
                "section": "Final merits synthesis",
                "purpose": "Tie acclaim, impact, and continuing work into a cohesive final merits story.",
                "inputs": [profile.get("proposed_final_merits_summary", "") or "Final merits summary needs drafting"],
            },
            {
                "section": "Gaps, dependencies, and filing readiness",
                "purpose": "Show the team what must be fixed before filing or before a deeper attorney draft.",
                "inputs": [item["criterion_name"] for item in gap_detector.get("gaps", [])[:4]],
            },
        ]
        return {
            "spine_title": f"{member.get('display_name', 'Member')} EB1A petition spine",
            "recommended_opening_position": self._petition_opening_position(profile, anchor_criteria),
            "anchor_criteria": [
                {
                    "criterion_code": item["criterion_code"],
                    "criterion_name": item["criterion_name"],
                    "claim": item["claim"],
                    "evidence_count": item["evidence_count"],
                }
                for item in anchor_criteria
            ],
            "sections": sections,
        }

    def _petition_opening_position(self, profile: dict, anchor_criteria: list[dict]) -> str:
        field = profile.get("primary_field") or profile.get("industry_domain") or "the member's field"
        role = " at ".join(part for part in [profile.get("current_title", ""), profile.get("current_employer", "")] if part)
        anchors = ", ".join(item["criterion_name"] for item in anchor_criteria[:3]) or "the strongest documented criteria"
        return f"Position the case around {role or 'the member'} in {field}, then prove sustained acclaim through {anchors}."

    def _petition_traceable_drafting(self, claim_map: list[dict], exhibit_assembly: dict) -> dict:
        exhibit_lookup = {item["evidence_id"]: item["exhibit_number"] for item in exhibit_assembly.get("exhibits", [])}
        blocks = []
        for claim in claim_map:
            if claim["status"] == "gap":
                continue
            sources = []
            for source in claim.get("source_links", [])[:8]:
                sources.append({**source, "exhibit_number": exhibit_lookup.get(source.get("evidence_id"), "")})
            blocks.append(
                {
                    "block_id": f"draft_{claim['criterion_code']}",
                    "heading": claim["criterion_name"],
                    "drafting_prompt": f"Draft the {claim['criterion_name']} section using only the linked source evidence and clearly explain the legal relevance without overstatement.",
                    "claim": claim["claim"],
                    "source_links": sources,
                }
            )
        return {
            "traceability_rule": "Every petition assertion should point to an evidence id, exhibit number, or member narrative export.",
            "draft_blocks": blocks,
        }

    def _petition_final_merits_strategy(self, profile: dict, claim_map: list[dict], gap_detector: dict) -> dict:
        strong_claims = [item for item in claim_map if item["status"] in {"petition_ready", "building"}]
        pillars = [
            {
                "pillar": "Sustained acclaim",
                "support": [item["criterion_name"] for item in strong_claims if item["criterion_code"] in {"awards", "memberships", "judging", "published_material"}],
            },
            {
                "pillar": "Originality and field impact",
                "support": [item["criterion_name"] for item in strong_claims if item["criterion_code"] in {"original_contributions", "scholarly_articles", "comparable_evidence"}],
            },
            {
                "pillar": "Distinguished role and influence",
                "support": [item["criterion_name"] for item in strong_claims if item["criterion_code"] in {"leading_critical_role", "high_salary"}],
            },
        ]
        return {
            "current_summary": profile.get("proposed_final_merits_summary", ""),
            "strategy_note": "Use final merits to connect separate evidence categories into one credible record of field-level distinction.",
            "pillars": [{**item, "support": item["support"] or ["Needs more support"]} for item in pillars],
            "watchouts": [gap["issues"][0] for gap in gap_detector.get("gaps", []) if gap.get("severity") == "high"][:5],
        }

    def _petition_recommendation_workspace(self, profile: dict, claim_map: list[dict], evidence_items: list[dict], gap_detector: dict) -> dict:
        existing_letters = [
            self._petition_source_link(item)
            for item in evidence_items
            if item.get("document_type") == "Recommendation or Support" or "recommend" in (item.get("title", "") + " " + item.get("file_name", "")).lower()
        ]
        high_gaps = [item for item in gap_detector.get("gaps", []) if item.get("severity") == "high"]
        target_templates = [
            ("Independent expert", "Corroborate field significance and explain why the work matters beyond the employer.", ["original_contributions", "scholarly_articles", "comparable_evidence"]),
            ("Senior executive or sponsor", "Confirm role criticality, scope, and business impact in a distinguished organization.", ["leading_critical_role"]),
            ("Customer, adopter, or implementation partner", "Confirm adoption, measurable outcomes, and external reliance.", ["original_contributions", "leading_critical_role"]),
            ("Conference, journal, or program organizer", "Confirm judging, reviewer selection, panel invitations, or selective participation.", ["judging", "published_material"]),
            ("Compensation or market expert", "Explain salary/remuneration benchmarks and why pay is unusually high.", ["high_salary"]),
        ]
        targets = []
        for target_type, purpose, criteria_codes in target_templates:
            related_gaps = [gap for gap in high_gaps if gap["criterion_code"] in criteria_codes]
            related_claims = [claim for claim in claim_map if claim["criterion_code"] in criteria_codes and claim["status"] != "gap"]
            if related_gaps or related_claims:
                targets.append(
                    {
                        "target_type": target_type,
                        "purpose": purpose,
                        "linked_criteria": [claim["criterion_name"] for claim in related_claims] or [gap["criterion_name"] for gap in related_gaps],
                        "facts_to_confirm": self._petition_letter_fact_prompts(criteria_codes, profile),
                        "status": "needed" if related_gaps else "helpful",
                    }
                )
        return {
            "existing_letters": existing_letters,
            "recommended_targets": targets[:6],
            "letter_quality_rules": [
                "Prefer independent or senior third-party voices over coworkers when possible.",
                "Ask for facts, dates, metrics, selection standards, and observed impact rather than generic praise.",
                "Tie each letter to one or two criteria and the final merits story.",
            ],
        }

    def _petition_letter_fact_prompts(self, criteria_codes: list[str], profile: dict) -> list[str]:
        prompts = ["Relationship to member and basis of firsthand knowledge", "Specific dates, projects, or events the recommender can verify"]
        if "leading_critical_role" in criteria_codes:
            prompts.extend(["Why the organization or unit is distinguished", "Why the member's role was critical rather than routine"])
        if "original_contributions" in criteria_codes:
            prompts.extend(["What was original compared with prior practice", "Who adopted or benefited from the contribution"])
        if "judging" in criteria_codes:
            prompts.append("Selection standard used to invite the member to judge or review others")
        if profile.get("primary_field"):
            prompts.append(f"How the facts matter in {profile['primary_field']}")
        return prompts[:6]

    def _petition_request_packs(self, claim_map: list[dict]) -> list[dict]:
        templates = self._petition_request_pack_templates()
        packs = []
        for claim in claim_map:
            template = templates.get(claim["criterion_code"], templates["other"])
            packs.append(
                {
                    "criterion_code": claim["criterion_code"],
                    "criterion_name": claim["criterion_name"],
                    "current_status": claim["status"],
                    "priority": "high" if claim["status"] == "gap" and claim["criterion_code"] in {"original_contributions", "leading_critical_role", "judging"} else "normal",
                    **template,
                }
            )
        return packs

    def _petition_request_pack_templates(self) -> dict[str, dict]:
        return {
            "awards": {
                "member_prompt": "Upload award certificates, selection emails, nomination materials, judging criteria, and proof that the award is nationally or internationally recognized.",
                "strong_examples": ["Award certificate plus selection criteria", "Press release naming winners", "Evidence of national or international applicant pool"],
                "weak_examples": ["Internal team shout-out with no selection standard", "Undated badge without award context"],
                "upload_checklist": ["Award proof", "Selection criteria", "Issuer reputation", "Date received"],
            },
            "memberships": {
                "member_prompt": "Show that membership required outstanding achievement, not just payment or routine experience.",
                "strong_examples": ["Acceptance letter", "Bylaws showing selective standards", "Reviewer or sponsor confirmation"],
                "weak_examples": ["Paid membership receipt only", "Open LinkedIn group membership"],
                "upload_checklist": ["Acceptance proof", "Membership criteria", "Organization reputation", "Date joined"],
            },
            "published_material": {
                "member_prompt": "Upload articles about you or your work, not just articles you authored, with publication reputation and date.",
                "strong_examples": ["Media article primarily about member's work", "Publication masthead or readership data", "Press mention tied to impact"],
                "weak_examples": ["Company blog post written by member", "Brief name mention without substance"],
                "upload_checklist": ["Article", "Publisher details", "Date", "Why it matters"],
            },
            "judging": {
                "member_prompt": "Upload invitation, participation proof, thank-you email, certificate, agenda, and any selection standard showing why you were chosen to judge others.",
                "strong_examples": ["Reviewer invitation and completed review acknowledgement", "Judge certificate", "Conference agenda listing judging role"],
                "weak_examples": ["Informal calendar hold only", "Generic volunteer email"],
                "upload_checklist": ["Invitation", "Participation proof", "Thank-you or certificate", "Selection standard"],
            },
            "original_contributions": {
                "member_prompt": "Describe the original contribution, what existed before, your personal role, measurable adoption or impact, and independent corroboration.",
                "strong_examples": ["Adoption metrics", "Independent expert letter", "Patent/product/research proof tied to field impact"],
                "weak_examples": ["Routine job responsibility", "Unquantified internal description only"],
                "upload_checklist": ["Problem before contribution", "Your distinct role", "Metrics", "External adoption or recognition"],
            },
            "scholarly_articles": {
                "member_prompt": "Upload authored articles, citations, venue reputation, acceptance proof, and evidence of influence where available.",
                "strong_examples": ["Published paper with citation record", "Journal/conference ranking", "Google Scholar or publisher page"],
                "weak_examples": ["Unpublished draft only", "Internal whitepaper without audience"],
                "upload_checklist": ["Article", "Venue proof", "Citation/influence", "Publication date"],
            },
            "leading_critical_role": {
                "member_prompt": "Explain the organization, your job title, project dates, leadership scope, why the role was critical, business value, and metrics.",
                "strong_examples": ["Executive confirmation letter", "Project metrics", "Org reputation proof", "Launch or revenue impact document"],
                "weak_examples": ["Job description only", "Self-written summary without corroboration"],
                "upload_checklist": ["Role title", "Project dates", "Org distinction", "Criticality", "Metrics"],
            },
            "high_salary": {
                "member_prompt": "Upload compensation proof and credible market benchmarks showing pay was high relative to peers in the same field/location.",
                "strong_examples": ["W-2 or offer letter", "Compensation survey benchmark", "Role/location comparison"],
                "weak_examples": ["Salary claim without proof", "Generic national average unrelated to role"],
                "upload_checklist": ["Compensation proof", "Benchmark source", "Comparable role/location", "Date"],
            },
            "comparable_evidence": {
                "member_prompt": "Use this when standard criteria do not fit. Explain why the evidence is comparable and what achievement it proves.",
                "strong_examples": ["Selective accelerator acceptance", "Open-source adoption metrics", "Standards committee contribution"],
                "weak_examples": ["Generic resume bullet", "Unverified social post"],
                "upload_checklist": ["Comparable rationale", "Selection or impact proof", "Independent corroboration", "Dates"],
            },
            "other": {
                "member_prompt": "Upload supporting documents only when they help explain a claimed EB1A criterion or final merits narrative.",
                "strong_examples": ["Official documents with dates and issuer", "Context documents tied to a claim"],
                "weak_examples": ["Unlabeled screenshots", "Duplicate files"],
                "upload_checklist": ["Title", "Date", "Issuer/source", "Why it matters"],
            },
        }

    def _petition_draft_submit_workflow(self, critical_role_projects: list[dict], original_contributions: list[dict]) -> dict:
        items = []
        for item in critical_role_projects:
            items.append(
                {
                    "id": item.get("id", ""),
                    "type": "Critical Role",
                    "title": item.get("summary_line", "Critical role project"),
                    "workflow_status": item.get("workflow_status", "draft"),
                    "last_edited_at": item.get("updated_at", ""),
                    "submitted_at": item.get("submitted_at", ""),
                    "resume_endpoint": "/api/member/critical-role-projects",
                    "export_evidence_id": item.get("export_evidence_id", ""),
                }
            )
        for item in original_contributions:
            items.append(
                {
                    "id": item.get("id", ""),
                    "type": "Original Contribution",
                    "title": item.get("summary_line", "Original contribution"),
                    "workflow_status": item.get("workflow_status", "draft"),
                    "last_edited_at": item.get("updated_at", ""),
                    "submitted_at": item.get("submitted_at", ""),
                    "resume_endpoint": "/api/member/original-contributions",
                    "export_evidence_id": item.get("export_evidence_id", ""),
                }
            )
        return {
            "rules": [
                "Members can save drafts without meeting submission validation.",
                "Submitting generates a PDF export and stores it as criterion evidence.",
                "Deleting a submitted item archives the generated evidence instead of hard-deleting the file artifact.",
            ],
            "items": sorted(items, key=lambda item: item.get("last_edited_at") or "", reverse=True),
        }

    def _petition_top_next_actions(self, gap_detector: dict, tasks: list[dict], document_qa: dict, recommendation_workspace: dict) -> list[dict]:
        actions = []
        for task in [item for item in tasks if item.get("status") == "open"][:3]:
            actions.append(
                {
                    "priority": "high" if task.get("due_date") else "medium",
                    "owner": "member",
                    "action": f"Complete open task: {task.get('title', 'Untitled task')}",
                    "why_it_matters": task.get("description", "Open work blocks case readiness."),
                    "related_criterion": task.get("criterion_code", ""),
                }
            )
        for gap in gap_detector.get("gaps", []):
            if gap["severity"] not in {"high", "medium"}:
                continue
            actions.append(
                {
                    "priority": gap["severity"],
                    "owner": "profile_builder" if gap["severity"] == "high" else "member",
                    "action": f"Strengthen {gap['criterion_name']}",
                    "why_it_matters": "; ".join(gap.get("issues", [])[:2]),
                    "related_criterion": gap["criterion_code"],
                }
            )
        if document_qa.get("flag_count"):
            actions.append(
                {
                    "priority": "medium",
                    "owner": "admin",
                    "action": "Resolve document QA flags before filing package work",
                    "why_it_matters": f"{document_qa['flag_count']} evidence hygiene issue(s) could slow exhibit assembly.",
                    "related_criterion": "",
                }
            )
        needed_letters = [item for item in recommendation_workspace.get("recommended_targets", []) if item.get("status") == "needed"]
        if needed_letters:
            actions.append(
                {
                    "priority": "high",
                    "owner": "attorney",
                    "action": f"Start {needed_letters[0]['target_type']} recommendation request",
                    "why_it_matters": needed_letters[0]["purpose"],
                    "related_criterion": ", ".join(needed_letters[0].get("linked_criteria", [])),
                }
            )
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(actions, key=lambda item: (priority_order.get(item["priority"], 9), item["action"]))[:3]

    def _petition_recommender_intake(self, member: dict, recommendation_workspace: dict) -> dict:
        return {
            "intake_slug": f"rec-{member['client_id']}",
            "status": "ready_to_invite" if recommendation_workspace.get("recommended_targets") else "no_targets_needed",
            "form_fields": [
                "Recommender name, title, organization, and email",
                "Relationship to member and independence level",
                "Credential summary establishing authority in the field",
                "Facts the recommender can personally verify",
                "Specific dates, metrics, selection standards, or adoption details",
                "Permission to be contacted for attorney follow-up",
            ],
            "recommended_invites": recommendation_workspace.get("recommended_targets", []),
        }

    def _petition_attorney_review_queue(self, actor_role: str, actor_email: str) -> dict:
        if actor_role == "attorney" and actor_email:
            members = self.attorney_members(actor_email)
        elif actor_role == "leader":
            members = self.leader_dashboard().get("members", [])
        else:
            members = self.builder_members()
        buckets = {
            "intake_draft": [],
            "evidence_review": [],
            "drafting_ready": [],
            "final_merits_review": [],
            "letter_review": [],
            "filing_qa": [],
            "rfe_response": [],
        }
        for member in members:
            stage = self._petition_review_stage(member)
            buckets.setdefault(stage, []).append(
                {
                    "client_id": member.get("client_id", ""),
                    "display_name": member.get("display_name", ""),
                    "readiness_score": int(member.get("readiness_score") or 0),
                    "evidence_count": int(member.get("evidence_count") or 0),
                    "open_task_count": int(member.get("open_task_count") or 0),
                    "case_status": member.get("status", ""),
                    "stage": stage,
                }
            )
        return {
            "stage_order": list(buckets.keys()),
            "buckets": buckets,
            "counts": {stage: len(items) for stage, items in buckets.items()},
        }

    def _petition_review_stage(self, member: dict) -> str:
        status = str(member.get("status", "")).strip().lower()
        readiness = int(member.get("readiness_score") or 0)
        evidence_count = int(member.get("evidence_count") or 0)
        open_tasks = int(member.get("open_task_count") or 0)
        if "rfe" in status or "noid" in status:
            return "rfe_response"
        if readiness >= 85 and open_tasks == 0:
            return "filing_qa"
        if readiness >= 75:
            return "final_merits_review"
        if readiness >= 65:
            return "letter_review"
        if readiness >= 55 and evidence_count >= 5:
            return "drafting_ready"
        if evidence_count >= 3:
            return "evidence_review"
        return "intake_draft"

    def _petition_rfe_noid_workspace(self, member: dict, gap_detector: dict, tasks: list[dict], evidence_items: list[dict]) -> dict:
        rfe_tasks = [item for item in tasks if re.search(r"\b(rfe|noid|notice|request for evidence)\b", f"{item.get('title', '')} {item.get('description', '')}", re.I)]
        issues = gap_detector.get("gaps", [])[:6]
        return {
            "case_mode": "active_response" if rfe_tasks or re.search(r"\b(rfe|noid)\b", str(member.get("status", "")), re.I) else "standby",
            "response_deadline": next((item.get("due_date", "") for item in rfe_tasks if item.get("due_date")), ""),
            "issue_workstreams": [
                {
                    "issue": gap["criterion_name"],
                    "severity": gap["severity"],
                    "response_plan": f"Collect delta evidence and draft a focused response addressing: {gap['issues'][0]}",
                    "needed_evidence": gap.get("issues", [])[:3],
                }
                for gap in issues
            ],
            "delta_exhibits": [
                self._petition_source_link(item)
                for item in evidence_items[:8]
            ],
        }

    def _petition_risk_dashboard(
        self,
        profile: dict,
        claim_map: list[dict],
        document_qa: dict,
        critical_role_projects: list[dict],
        original_contributions: list[dict],
    ) -> dict:
        risks = []
        if not profile.get("biography"):
            risks.append({"risk": "Missing member biography", "severity": "medium", "fix": "Ask member to complete profile biography before attorney draft."})
        if not profile.get("proposed_final_merits_summary"):
            risks.append({"risk": "Final merits story is not drafted", "severity": "high", "fix": "Create a concise final merits thesis tied to strongest criteria."})
        for claim in claim_map:
            if claim["evidence_count"] and claim["quality_average"] < 45:
                risks.append({"risk": f"{claim['criterion_name']} evidence quality is low", "severity": "medium", "fix": "Replace informal or unclear documents with official corroboration."})
            if claim["criterion_code"] in {"original_contributions", "leading_critical_role"} and claim["status"] == "gap":
                risks.append({"risk": f"{claim['criterion_name']} is a high-value gap", "severity": "high", "fix": "Use the structured member intake plus independent corroboration."})
        for item in critical_role_projects:
            if item.get("is_submitted") and not item.get("organization_distinctiveness"):
                risks.append({"risk": "Critical Role organization distinction not documented", "severity": "high", "fix": "Add proof of organization scale, reputation, market position, or awards."})
        for item in original_contributions:
            if item.get("is_submitted") and not item.get("field_wide_impact"):
                risks.append({"risk": "Original Contribution field-wide impact is thin", "severity": "high", "fix": "Add adoption, citations, expert letters, customer proof, or industry references."})
        for flag in document_qa.get("flags", [])[:5]:
            risks.append({"risk": flag["message"], "severity": flag["severity"], "fix": flag["recommended_fix"]})
        score = min(100, sum(18 if item["severity"] == "high" else 9 if item["severity"] == "medium" else 4 for item in risks))
        return {
            "risk_score": score,
            "risk_level": "High" if score >= 60 else "Moderate" if score >= 25 else "Low",
            "risks": risks[:12],
        }

    def _petition_argument_bank(self, profile: dict, claim_map: list[dict]) -> dict:
        profile_type = self._petition_profile_type(profile)
        patterns = {
            "product leader": [
                "Frame impact through cross-functional leadership, shipped systems, adoption metrics, and executive reliance.",
                "Use customer/user outcomes and business metrics to distinguish critical role from routine product ownership.",
            ],
            "engineer": [
                "Frame originality through technical problem difficulty, system adoption, reliability gains, and independent validation.",
                "Use architecture documents, patents, benchmarks, and peer recognition as source anchors.",
            ],
            "researcher": [
                "Frame impact through publications, citations, peer review, invited talks, and adoption by other researchers.",
                "Use independent expert letters to explain why the contribution is major in the field.",
            ],
            "executive": [
                "Frame leadership through organizational scale, revenue or market outcomes, and decision authority.",
                "Use board/executive letters, public company proof, and market evidence to show distinguished organization context.",
            ],
            "professional": [
                "Lead with the strongest criteria and tie each claim to measurable, externally corroborated outcomes.",
                "Avoid generic excellence language; use dates, metrics, selection standards, and third-party proof.",
            ],
        }
        selected = [item for item in claim_map if item["status"] in {"petition_ready", "building"}][:4]
        return {
            "profile_type": profile_type,
            "argument_patterns": patterns.get(profile_type, patterns["professional"]),
            "criterion_examples": [
                {
                    "criterion_name": item["criterion_name"],
                    "argument_angle": item["attorney_use"],
                    "source_count": item["evidence_count"],
                }
                for item in selected
            ],
        }

    def _petition_profile_type(self, profile: dict) -> str:
        text = " ".join([profile.get("current_title", ""), profile.get("primary_field", ""), profile.get("specialization", "")]).lower()
        if any(word in text for word in ["product", "program manager", "pm"]):
            return "product leader"
        if any(word in text for word in ["engineer", "architect", "developer", "software", "data"]):
            return "engineer"
        if any(word in text for word in ["research", "scientist", "professor", "scholar"]):
            return "researcher"
        if any(word in text for word in ["chief", "vp", "vice president", "director", "executive"]):
            return "executive"
        return "professional"

    def _petition_criterion_playbooks(self, claim_map: list[dict]) -> list[dict]:
        playbooks = {
            "original_contributions": ["Capture contribution narrative", "Collect adoption or impact proof", "Request independent expert or adopter letter", "Map evidence to field-wide significance"],
            "leading_critical_role": ["Capture organization distinction", "Document job title and project dates", "Quantify business value", "Secure executive corroboration"],
            "judging": ["Collect invitation", "Upload participation proof", "Add thank-you/certificate", "Show selection standard"],
            "high_salary": ["Upload compensation proof", "Find role/location benchmark", "Explain percentile or premium", "Redact sensitive details only as needed"],
            "published_material": ["Upload article", "Document publication reputation", "Show article is about member/work", "Tie coverage to criterion claim"],
            "memberships": ["Upload acceptance proof", "Collect bylaws/criteria", "Show outstanding-achievement requirement", "Document current standing"],
        }
        return [
            {
                "criterion_code": claim["criterion_code"],
                "criterion_name": claim["criterion_name"],
                "current_status": claim["status"],
                "steps": playbooks.get(claim["criterion_code"], ["Clarify claim", "Collect official source document", "Add independent context", "Review with attorney"]),
            }
            for claim in claim_map
        ]

    def _petition_portfolio_heatmap(self) -> dict:
        members = self.leader_dashboard().get("members", [])
        criteria_rows = rows(self.conn, "SELECT code, name FROM criteria ORDER BY rowid")
        heatmap_rows = []
        for member in members:
            counts = rows(
                self.conn,
                """
                SELECT criterion_code, COUNT(*) AS count
                FROM evidence_items
                WHERE client_id = ? AND case_id = ? AND status != 'archived'
                GROUP BY criterion_code
                """,
                (member["client_id"], member["case_id"]),
            )
            count_lookup = {item["criterion_code"]: int(item["count"] or 0) for item in counts}
            heatmap_rows.append(
                {
                    "client_id": member["client_id"],
                    "display_name": member["display_name"],
                    "readiness_score": int(member.get("readiness_score") or 0),
                    "risk_level": member.get("risk_level", ""),
                    "stage_label": member.get("stage_label", ""),
                    "criteria": {criterion["code"]: count_lookup.get(criterion["code"], 0) for criterion in criteria_rows},
                }
            )
        return {
            "criteria": criteria_rows,
            "rows": heatmap_rows,
        }

    def _petition_sla_dashboard(self) -> dict:
        members = self.leader_dashboard().get("members", [])
        durations = {
            "invite_to_registration": [],
            "builder_assignment_to_first_evidence": [],
            "attorney_assignment_to_petition_generation": [],
        }
        for member in members:
            invite = one(self.conn, "SELECT invite_sent_at, registered_at FROM member_registration_invites WHERE client_id = ? AND case_id = ? ORDER BY invite_sent_at LIMIT 1", (member["client_id"], member["case_id"]))
            if invite and invite.get("registered_at"):
                durations["invite_to_registration"].append(self._duration_days(invite.get("invite_sent_at"), invite.get("registered_at")))
            builder_assignment = one(self.conn, "SELECT created_at FROM builder_member_assignments WHERE client_id = ? AND case_id = ? AND status = 'active' ORDER BY created_at LIMIT 1", (member["client_id"], member["case_id"]))
            first_evidence = one(self.conn, "SELECT MIN(created_at) AS created_at FROM evidence_items WHERE client_id = ? AND case_id = ? AND status != 'archived'", (member["client_id"], member["case_id"]))
            if builder_assignment and first_evidence and first_evidence.get("created_at"):
                durations["builder_assignment_to_first_evidence"].append(self._duration_days(builder_assignment.get("created_at"), first_evidence.get("created_at")))
            attorney_assignment = one(self.conn, "SELECT created_at FROM attorney_member_assignments WHERE client_id = ? AND case_id = ? AND status = 'active' ORDER BY created_at LIMIT 1", (member["client_id"], member["case_id"]))
            petition_event = one(self.conn, "SELECT MIN(created_at) AS created_at FROM operational_events WHERE client_id = ? AND case_id = ? AND event_type = 'petition_generator'", (member["client_id"], member["case_id"]))
            if attorney_assignment and petition_event and petition_event.get("created_at"):
                durations["attorney_assignment_to_petition_generation"].append(self._duration_days(attorney_assignment.get("created_at"), petition_event.get("created_at")))
        targets = {
            "invite_to_registration": 7,
            "builder_assignment_to_first_evidence": 14,
            "attorney_assignment_to_petition_generation": 7,
        }
        metrics = []
        for key, values in durations.items():
            avg_days = round(sum(values) / len(values), 1) if values else None
            target = targets[key]
            metrics.append(
                {
                    "metric": key,
                    "average_days": avg_days,
                    "sample_size": len(values),
                    "target_days": target,
                    "status": "not_enough_data" if avg_days is None else "on_track" if avg_days <= target else "watch",
                }
            )
        return {"metrics": metrics}

    def _duration_days(self, start_value: str | None, end_value: str | None) -> int:
        start = self._parse_datetime(start_value)
        end = self._parse_datetime(end_value)
        if not start or not end:
            return 0
        return max(0, (end - start).days)

    def _iso_date(self, value: datetime | None) -> str:
        return value.date().isoformat() if value else ""

    def _timeline_status_for_stage(self, stage: dict, today: date) -> str:
        if stage.get("completed"):
            return "completed"
        end_date = self._parse_datetime(stage.get("end_date"))
        if end_date and end_date.date() < today:
            return "late"
        if stage.get("start_date"):
            start_date = self._parse_datetime(stage.get("start_date"))
            if start_date and start_date.date() <= today:
                return "active"
        return "upcoming"

    def _timeline_summary_from_member(self, member: dict) -> dict:
        evidence_count = int(member.get("evidence_count") or 0)
        criteria_started = int(member.get("criteria_started") or 0)
        readiness = int(member.get("readiness_score") or 0)
        open_tasks = int(member.get("open_task_count") or 0)
        case_created = self._parse_datetime(member.get("case_created_at") or member.get("created_at")) or datetime.utcnow()
        target_days = 45
        if readiness < 25:
            target_days += 45
        elif readiness < 50:
            target_days += 30
        elif readiness < 75:
            target_days += 18
        if evidence_count < 5:
            target_days += 21
        if criteria_started < 3:
            target_days += 21
        if open_tasks >= 3:
            target_days += 10
        baseline_file_date = case_created + timedelta(days=target_days)
        late = datetime.utcnow().date() > baseline_file_date.date() and readiness < 90
        return {
            "target_filing_date": self._iso_date(baseline_file_date),
            "days_to_target": (baseline_file_date.date() - datetime.utcnow().date()).days,
            "status": "late" if late else "on_track" if readiness >= 65 or evidence_count >= 8 else "at_risk",
            "late": late,
        }

    def petition_delivery_timeline(
        self,
        client_id: str = "",
        actor_role: str = "member",
        actor_email: str = "",
        actor_client_id: str = "",
    ) -> dict:
        role = actor_role.strip().lower() or "member"
        resolved_client_id = client_id.strip() or actor_client_id.strip() or self.config.default_client["client_id"]
        if role == "attorney":
            self.attorney_member_detail(resolved_client_id, actor_email)
        elif role == "builder":
            # Builder detail is assignment-scoped in the current service.
            self.builder_member_detail(resolved_client_id)
        elif role == "member" and actor_client_id and actor_client_id != resolved_client_id:
            raise ValueError("Member cannot view another member timeline")
        elif role not in {"member", "leader", "admin", "builder", "attorney"}:
            raise ValueError("Unsupported actor role")
        context = self._attorney_case_context(resolved_client_id)
        member = context["member"]
        profile = context["profile"]
        detail = context["detail"]
        evidence_items = context["evidence_items"]
        tasks = detail.get("tasks", [])
        criteria_started = sum(1 for item in detail.get("criteria", []) if int(item.get("evidence_count") or 0) > 0)
        submitted_intakes = len([item for item in detail.get("critical_role_projects", []) + detail.get("original_contribution_entries", []) if item.get("is_submitted")])
        readiness = int(member.get("readiness_score") or 0)
        evidence_count = len(evidence_items)
        case_start = self._parse_datetime(member.get("created_at")) or datetime.utcnow()
        today = datetime.utcnow().date()
        remaining_days = 28
        if readiness < 25:
            remaining_days += 56
        elif readiness < 50:
            remaining_days += 42
        elif readiness < 75:
            remaining_days += 28
        if evidence_count < 5:
            remaining_days += 21
        if criteria_started < 3:
            remaining_days += 18
        if submitted_intakes == 0:
            remaining_days += 10
        if any(item.get("status") == "open" for item in tasks):
            remaining_days += min(18, sum(1 for item in tasks if item.get("status") == "open") * 4)
        active_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        durations = [10, 18, 14, 12, 7, 6, 2]
        scale = max(1, remaining_days / sum(durations))
        stage_defs = [
            ("profile_evidence", "Profile and evidence baseline", "Member, builder, and attorney confirm the profile, uploaded evidence, and criterion coverage.", criteria_started >= 3 and evidence_count >= 5),
            ("gap_closure", "Criteria gap closure", "Close high-value gaps for Critical Role, Original Contributions, judging, published material, and awards.", readiness >= 55 and evidence_count >= 8),
            ("recommendations", "Recommendation letters", "Draft independent and project-specific letters, route to member, and collect signatures.", False),
            ("attorney_draft", "Attorney petition draft", "Attorney produces claim map, final merits narrative, and petition draft using source-linked evidence.", readiness >= 75),
            ("member_review", "Member review and signatures", "Member reviews attorney materials, signs recommendation letters, and confirms biographical facts.", False),
            ("filing_qa", "Final QA and exhibit assembly", "Team checks dates, exhibit order, source links, document quality, and filing package completeness.", False),
            ("file_petition", "File petition", "Submit the final petition package after attorney approval and member signoff.", readiness >= 90),
        ]
        stages = []
        cursor = active_start
        for index, (key, label, description, completed) in enumerate(stage_defs):
            days = max(2, round(durations[index] * scale))
            start = cursor
            end = cursor + timedelta(days=days)
            stage = {
                "key": key,
                "label": label,
                "description": description,
                "start_date": self._iso_date(start),
                "end_date": self._iso_date(end),
                "duration_days": days,
                "completed": bool(completed),
                "owner": "member" if key in {"profile_evidence", "member_review"} else "attorney" if key in {"recommendations", "attorney_draft"} else "operations",
            }
            stage["status"] = self._timeline_status_for_stage(stage, today)
            stages.append(stage)
            cursor = end + timedelta(days=1)
        target_filing_date = stages[-1]["end_date"]
        late_stages = [item for item in stages if item["status"] == "late"]
        rfe_start = self._parse_datetime(target_filing_date) + timedelta(days=90) if target_filing_date else cursor + timedelta(days=90)
        rfe_end = rfe_start + timedelta(days=90)
        alerts = []
        for task in tasks:
            if task.get("status") == "open" and task.get("due_date"):
                due_date = self._parse_datetime(task.get("due_date"))
                if due_date and due_date.date() < today:
                    alerts.append({"severity": "high", "message": f"Task overdue: {task.get('title', 'Untitled task')}", "owner": "member"})
        if evidence_count < 5:
            alerts.append({"severity": "medium", "message": "Evidence volume is still below a realistic filing path.", "owner": "member"})
        if criteria_started < 3:
            alerts.append({"severity": "high", "message": "Fewer than three criteria have active support.", "owner": "builder"})
        if not profile.get("profile_confirmed"):
            alerts.append({"severity": "medium", "message": "Member profile is not confirmed yet.", "owner": "member"})
        for stage in late_stages:
            alerts.append({"severity": "high", "message": f"{stage['label']} is past its target end date.", "owner": stage["owner"]})
        return {
            "ok": True,
            "status": "late" if late_stages else "on_track" if not alerts else "at_risk",
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "member": {
                "client_id": member["client_id"],
                "case_id": member["case_id"],
                "display_name": member.get("display_name", "Member"),
                "readiness_score": readiness,
                "target_filing_date": target_filing_date,
            },
            "summary": {
                "target_filing_date": target_filing_date,
                "days_to_target": (self._parse_datetime(target_filing_date).date() - today).days if target_filing_date else 0,
                "evidence_count": evidence_count,
                "criteria_started": criteria_started,
                "submitted_project_intakes": submitted_intakes,
                "late_stage_count": len(late_stages),
                "alert_count": len(alerts),
            },
            "stages": stages,
            "rfe_support": {
                "label": "RFE support window if needed",
                "start_date": self._iso_date(rfe_start),
                "end_date": self._iso_date(rfe_end),
                "duration_days": max(0, (rfe_end.date() - rfe_start.date()).days),
                "style": "dotted",
                "description": "Contingency support window for RFE or NOID response work if USCIS asks for more evidence.",
            },
            "alerts": alerts[:8],
        }

    def _petition_document_qa(self, evidence_items: list[dict]) -> dict:
        flags = []
        by_name: dict[str, list[dict]] = {}
        for item in evidence_items:
            by_name.setdefault(str(item.get("file_name", "")).strip().lower(), []).append(item)
        for file_name, duplicates in by_name.items():
            if file_name and len(duplicates) > 1:
                flags.append(
                    {
                        "severity": "medium",
                        "type": "duplicate_file_name",
                        "message": f"Duplicate file name detected: {duplicates[0].get('file_name', file_name)}",
                        "evidence_ids": [item.get("id", "") for item in duplicates],
                        "recommended_fix": "Confirm whether duplicates are intentional versions or archive extras.",
                    }
                )
        for item in evidence_items:
            text = f"{item.get('title', '')} {item.get('file_name', '')} {item.get('description', '')}".lower()
            quality = int(item.get("quality_score") or 0)
            if quality and quality < 35:
                flags.append(
                    {
                        "severity": "high",
                        "type": "low_quality_scan",
                        "message": f"{item.get('title') or item.get('file_name')} may be unreadable or too thin for filing.",
                        "evidence_ids": [item.get("id", "")],
                        "recommended_fix": "Replace with a clearer original or add a better corroborating document.",
                    }
                )
            if any(token in text for token in ["spanish", "chinese", "hindi", "foreign language", "translation required"]) and "translation" not in text:
                flags.append(
                    {
                        "severity": "medium",
                        "type": "translation_check",
                        "message": f"{item.get('title') or item.get('file_name')} may need certified translation review.",
                        "evidence_ids": [item.get("id", "")],
                        "recommended_fix": "Upload certified English translation or mark as English-language evidence.",
                    }
                )
            if re.match(r"^(scan|image|document|untitled)[\s_\-\.]", str(item.get("file_name", "")).lower()):
                flags.append(
                    {
                        "severity": "low",
                        "type": "weak_file_name",
                        "message": f"File name is not descriptive: {item.get('file_name', '')}",
                        "evidence_ids": [item.get("id", "")],
                        "recommended_fix": "Rename or title the evidence with date, issuer, and category context.",
                    }
                )
        severity_counts = {
            "high": sum(1 for item in flags if item["severity"] == "high"),
            "medium": sum(1 for item in flags if item["severity"] == "medium"),
            "low": sum(1 for item in flags if item["severity"] == "low"),
        }
        return {"flag_count": len(flags), "severity_counts": severity_counts, "flags": flags}

    def _petition_exhibit_assembly(self, criteria: list[dict], evidence_items: list[dict]) -> dict:
        order = {criterion["code"]: index for index, criterion in enumerate(criteria)}
        criteria_lookup = {criterion["code"]: criterion["name"] for criterion in criteria}
        sorted_items = sorted(
            evidence_items,
            key=lambda item: (order.get(item.get("criterion_code", "other"), 99), item.get("created_at", ""), item.get("title", "")),
        )
        exhibits = []
        for index, item in enumerate(sorted_items, start=1):
            exhibits.append(
                {
                    "exhibit_number": f"ASC-{index:03d}",
                    "evidence_id": item.get("id", ""),
                    "criterion_code": item.get("criterion_code", ""),
                    "criterion_name": criteria_lookup.get(item.get("criterion_code", ""), item.get("criterion_code", "")),
                    "title": item.get("title", ""),
                    "file_name": item.get("file_name", ""),
                    "document_type": item.get("document_type", "Other"),
                    "uploaded_at": item.get("created_at", ""),
                    "open_url": item.get("open_url", ""),
                }
            )
        grouped: dict[str, int] = {}
        for exhibit in exhibits:
            grouped[exhibit["criterion_name"]] = grouped.get(exhibit["criterion_name"], 0) + 1
        return {
            "index_title": "Ascend exhibit assembly index",
            "exhibits": exhibits,
            "group_counts": [{"criterion_name": key, "count": value} for key, value in grouped.items()],
        }

    def _petition_upload_packager(self, exhibit_assembly: dict) -> dict:
        bundles = []
        current = {"bundle_name": "USCIS Upload Bundle 1", "estimated_bytes": 0, "exhibits": []}
        max_bytes = 24 * 1024 * 1024
        for exhibit in exhibit_assembly.get("exhibits", []):
            estimated = 512 * 1024
            if current["estimated_bytes"] + estimated > max_bytes and current["exhibits"]:
                bundles.append(current)
                current = {"bundle_name": f"USCIS Upload Bundle {len(bundles) + 1}", "estimated_bytes": 0, "exhibits": []}
            current["estimated_bytes"] += estimated
            current["exhibits"].append(
                {
                    "exhibit_number": exhibit["exhibit_number"],
                    "upload_file_name": safe_file_name(f"{exhibit['exhibit_number']}-{exhibit['criterion_name']}-{exhibit['file_name']}"),
                    "title": exhibit["title"],
                }
            )
        if current["exhibits"]:
            bundles.append(current)
        return {
            "mode": "online_upload_ready",
            "bundle_size_limit_mb": 24,
            "bundles": bundles,
            "naming_rule": "Exhibit number, criterion, and original file name are preserved in upload order.",
        }

    def _petition_filing_qa_checklist(
        self,
        member: dict,
        profile: dict,
        claim_map: list[dict],
        document_qa: dict,
        exhibit_assembly: dict,
        recommendation_workspace: dict,
        critical_role_projects: list[dict],
        original_contributions: list[dict],
    ) -> dict:
        supported_criteria = sum(1 for item in claim_map if item["status"] in {"petition_ready", "building"} and item["evidence_count"] > 0)
        checks = [
            {"item": "At least three EB1A criteria have active evidence", "status": "pass" if supported_criteria >= 3 else "fail", "detail": f"{supported_criteria} criteria currently have active support."},
            {"item": "Final merits summary is drafted", "status": "pass" if profile.get("proposed_final_merits_summary") else "warn", "detail": "Needed for attorney synthesis and filing QA."},
            {"item": "Exhibit index has generated entries", "status": "pass" if exhibit_assembly.get("exhibits") else "fail", "detail": f"{len(exhibit_assembly.get('exhibits', []))} exhibit(s) indexed."},
            {"item": "Document QA high-risk flags cleared", "status": "pass" if not document_qa["severity_counts"].get("high") else "fail", "detail": f"{document_qa['severity_counts'].get('high', 0)} high-risk document flag(s)."},
            {"item": "Recommendation targets identified", "status": "pass" if recommendation_workspace.get("existing_letters") or recommendation_workspace.get("recommended_targets") else "warn", "detail": "Letters may be needed for independence and corroboration."},
            {"item": "Critical Role submissions exported when present", "status": "pass" if all((not item.get("is_submitted")) or item.get("export_evidence_id") for item in critical_role_projects) else "fail", "detail": "Submitted Critical Role entries should have stored PDF exports."},
            {"item": "Original Contribution submissions exported when present", "status": "pass" if all((not item.get("is_submitted")) or item.get("export_evidence_id") for item in original_contributions) else "fail", "detail": "Submitted Original Contribution entries should have stored PDF exports."},
            {"item": "Member profile confirmed", "status": "pass" if profile.get("profile_confirmed") else "warn", "detail": "Profile confirmation helps reduce biographical inconsistency before filing."},
        ]
        status = "ready" if all(item["status"] == "pass" for item in checks) else "blocked" if any(item["status"] == "fail" for item in checks) else "needs_review"
        return {
            "member_name": member.get("display_name", ""),
            "status": status,
            "checks": checks,
        }

    def attorney_endeavor_letter_generator(
        self,
        client_id: str = "",
        prompt_config: dict | None = None,
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        client_id = client_id.strip() or self.config.default_client["client_id"]
        self._assert_member_batch_access(client_id, actor_role=actor_role, actor_email=actor_email)
        case_context = self._attorney_case_context(client_id)
        detail = case_context["detail"]
        member = case_context["member"]
        profile = case_context["profile"]
        evidence_items = case_context["evidence_items"]
        payload = self._attorney_case_payload(case_context)
        payload["parsed_evidence"] = self._parsed_evidence_context(evidence_items)
        try:
            result = self.openai.generate_endeavor_letter(payload, prompt_config or {})
            source = result.pop("source", "fallback")
            compiled_prompt = result.pop("compiled_prompt", "")
            normalized_prompt_config = result.pop("normalized_prompt_config", prompt_config or {})
            status = "success" if source == "openai" else "fallback"
        except Exception as exc:
            result = {
                "title": "Statement of Proposed Endeavor and Intention to Continue Work in the Area of Expertise",
                "date_line": "Date: __________",
                "re_line": "Re: Form I-140, EB-1A Extraordinary Ability Petition",
                "beneficiary_line": f"Petitioner/Beneficiary: {member.get('display_name', 'Member')}",
                "subject_line": f"Subject: Statement of Proposed Endeavor and Continuing Work in {profile.get('primary_field', '') or profile.get('industry_domain', '') or 'the area of expertise'}",
                "salutation": "Dear Officer:",
                "opening_paragraph": "The AI endeavor-letter path did not complete, so the attorney should review the case record and regenerate after the AI service is available.",
                "sections": [
                    {"heading": "1. My Field and Why It Matters", "body": "Use the member record to describe the field precisely and explain why it matters in the United States."},
                    {"heading": "2. Continuity With My Established Work", "body": "Connect current work and prior documented achievements to the same field and future direction."},
                    {"heading": "3. My Proposed Future Endeavor in the United States", "body": "Explain the specific future work the member plans to continue in the United States."},
                    {"heading": "4. Why My Continued Work Will Benefit the United States", "body": f"AI endeavor-letter generation failed: {exc}"},
                ],
                "closing_paragraph": "This fallback outline should be reviewed and regenerated once the AI path is available.",
                "signature_line": member.get("display_name", "Member"),
                "plain_text": "",
                "estimated_word_count": 0,
                "estimated_page_count": 1,
            }
            source = "fallback"
            compiled_prompt = ""
            normalized_prompt_config = prompt_config or {}
            status = "fallback"
        self.record_operational_event(
            "endeavor_letter_generator",
            status=status,
            portal="attorney",
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/attorney/endeavor-letter-generator",
            message="Attorney endeavor letter generator completed.",
            metadata={
                "source": source,
                "evidence_count": len(evidence_items),
                "parsed_with_text": sum(1 for item in payload["parsed_evidence"] if item.get("excerpt_available")),
            },
        )
        return {
            "ok": True,
            "status": status,
            "source": source,
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "compiled_prompt": compiled_prompt,
            "prompt_config": normalized_prompt_config,
            "member": {
                "client_id": member["client_id"],
                "case_id": member["case_id"],
                "display_name": member.get("display_name", "Member"),
                "readiness_score": int(member.get("readiness_score") or 0),
                "industry_domain": profile.get("industry_domain", ""),
                "primary_field": profile.get("primary_field", ""),
                "current_title": profile.get("current_title", ""),
                "current_employer": profile.get("current_employer", ""),
            },
            "snapshot": {
                "evidence_count": len(evidence_items),
                "parsed_documents": len(payload["parsed_evidence"]),
                "parsed_with_text": sum(1 for item in payload["parsed_evidence"] if item.get("excerpt_available")),
                "criteria_started": sum(1 for item in detail.get("criteria", []) if int(item.get("evidence_count") or 0) > 0),
                "open_tasks": sum(1 for item in detail.get("tasks", []) if item.get("status") == "open"),
                "planner_items": len(case_context["planner_rows"]),
            },
            "parsed_evidence": payload["parsed_evidence"],
            "letter": result,
        }

    def _recommendation_project_options(self, detail: dict) -> list[dict]:
        projects = []
        for item in detail.get("critical_role_projects", []):
            projects.append(
                {
                    "id": item.get("id", ""),
                    "project_type": "critical_role",
                    "criterion_code": "leading_critical_role",
                    "criterion_name": "Leading or Critical Role",
                    "title": item.get("project_name") or item.get("summary_line") or "Critical Role project",
                    "organization_name": item.get("organization_name", ""),
                    "role_title": item.get("role_title", ""),
                    "date_label": item.get("project_date_label") or item.get("role_date_label") or "",
                    "workflow_status": item.get("workflow_status", "draft"),
                    "summary": item.get("attorney_friendly_summary") or item.get("business_value_summary") or item.get("project_summary") or "",
                    "impact": item.get("quantitative_metrics") or item.get("business_value_summary") or "",
                    "source": item,
                }
            )
        for item in detail.get("original_contribution_entries", []):
            projects.append(
                {
                    "id": item.get("id", ""),
                    "project_type": "original_contribution",
                    "criterion_code": "original_contributions",
                    "criterion_name": "Original Contributions",
                    "title": item.get("contribution_title") or item.get("project_name") or item.get("summary_line") or "Original Contribution",
                    "organization_name": item.get("organization_name", ""),
                    "role_title": item.get("job_title", ""),
                    "date_label": item.get("date_label") or "",
                    "workflow_status": item.get("workflow_status", "draft"),
                    "summary": item.get("attorney_friendly_summary") or item.get("distinct_contribution_summary") or item.get("originality_summary") or "",
                    "impact": item.get("impact_metrics") or item.get("field_wide_impact") or item.get("adoption_scale") or "",
                    "source": item,
                }
            )
        return projects

    def _serialize_recommendation_letter(self, letter: dict | None) -> dict:
        if not letter:
            return {}
        try:
            letter_json = json.loads(letter.get("letter_json") or "{}")
        except json.JSONDecodeError:
            letter_json = {}
        try:
            prompt_config = json.loads(letter.get("prompt_config_json") or "{}")
        except json.JSONDecodeError:
            prompt_config = {}
        return {
            **letter,
            "letter": letter_json if isinstance(letter_json, dict) else {},
            "prompt_config": prompt_config if isinstance(prompt_config, dict) else {},
            "download_url": f"/api/recommendation-letters/{letter['id']}/download",
        }

    def recommendation_letter_workspace(self, client_id: str = "", actor_role: str = "attorney", actor_email: str = "") -> dict:
        client_id = client_id.strip() or self.config.default_client["client_id"]
        self._assert_member_batch_access(client_id, actor_role=actor_role, actor_email=actor_email)
        context = self._attorney_case_context(client_id)
        detail = context["detail"]
        member = context["member"]
        profile = context["profile"]
        project_options = self._recommendation_project_options(detail)
        letter_rows = rows(
            self.conn,
            """
            SELECT *
            FROM recommendation_letters
            WHERE client_id = ? AND case_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (member["client_id"], member["case_id"]),
        )
        return {
            "ok": True,
            "member": {
                "client_id": member["client_id"],
                "case_id": member["case_id"],
                "display_name": member.get("display_name", "Member"),
                "primary_field": profile.get("primary_field", ""),
                "current_title": profile.get("current_title", ""),
                "current_employer": profile.get("current_employer", ""),
            },
            "projects": project_options,
            "letters": [self._serialize_recommendation_letter(item) for item in letter_rows],
            "default_prompt": {
                "who_you_are": "You are an expert EB1A attorney drafting a recommendation letter for review and signature by a recommender.",
                "letter_kind": "independent",
                "recommender_name": "",
                "recommender_title": "",
                "recommender_organization": "",
                "recommender_relationship": "",
                "facts_to_confirm": "Confirm dates, scope, personal contribution, measurable impact, and why this project matters.",
                "attorney_strategy_notes": "Ground the letter in the selected Critical Role or Original Contribution project and avoid generic praise.",
                "tone_guidance": "Professional, factual, and suitable for recommender signature.",
            },
        }

    def attorney_recommendation_letter_generator(
        self,
        client_id: str = "",
        letter_kind: str = "independent",
        project_type: str = "",
        project_id: str = "",
        prompt_config: dict | None = None,
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        client_id = client_id.strip() or self.config.default_client["client_id"]
        self._assert_member_batch_access(client_id, actor_role=actor_role, actor_email=actor_email)
        context = self._attorney_case_context(client_id)
        member = context["member"]
        detail = context["detail"]
        evidence_items = context["evidence_items"]
        projects = self._recommendation_project_options(detail)
        selected_project = next((item for item in projects if item["id"] == project_id.strip() and item["project_type"] == project_type.strip()), None)
        if not selected_project:
            raise ValueError("Select a Critical Role or Original Contribution project before generating a recommendation letter")
        normalized_kind = letter_kind.strip().lower() or "independent"
        if normalized_kind not in {"independent", "dependent"}:
            normalized_kind = "independent"
        actor = self._actor_identity(actor_role, actor_email) if actor_role.strip().lower() in {"attorney", "leader"} else {"role": actor_role, "key": actor_email}
        payload = self._attorney_case_payload(context)
        payload["parsed_evidence"] = self._parsed_evidence_context(evidence_items)
        payload["selected_project"] = selected_project
        payload["letter_kind"] = normalized_kind
        prepared_prompt = dict(prompt_config or {})
        prepared_prompt["letter_kind"] = normalized_kind
        prepared_prompt["project_focus"] = prepared_prompt.get("project_focus") or f"Focus on {selected_project['title']} for {selected_project['criterion_name']}."
        try:
            result = self.openai.generate_recommendation_letter(payload, prepared_prompt)
            source = result.pop("source", "fallback")
            compiled_prompt = result.pop("compiled_prompt", "")
            normalized_prompt_config = result.pop("normalized_prompt_config", prepared_prompt)
            status = "success" if source == "openai" else "fallback"
        except Exception as exc:
            result = {
                "title": "Recommendation Letter",
                "date_line": "Date: __________",
                "addressee_line": "U.S. Citizenship and Immigration Services",
                "re_line": f"Re: Recommendation for {member.get('display_name', 'Member')}",
                "salutation": "Dear Officer:",
                "opening_paragraph": f"AI recommendation-letter generation failed: {exc}",
                "sections": [
                    {"heading": "Selected project", "body": selected_project["title"]},
                    {"heading": "Facts to confirm", "body": prepared_prompt.get("facts_to_confirm", "")},
                    {"heading": "Impact", "body": selected_project.get("impact", "") or "Add impact details before finalizing."},
                    {"heading": "Petition relevance", "body": selected_project["criterion_name"]},
                ],
                "closing_paragraph": "Regenerate after the AI path is available.",
                "signature_line": prepared_prompt.get("recommender_name", "Recommender Name"),
                "plain_text": "",
                "estimated_word_count": 0,
                "estimated_page_count": 1,
            }
            source = "fallback"
            compiled_prompt = ""
            normalized_prompt_config = prepared_prompt
            status = "fallback"
        letter_id = f"recltr_{uuid.uuid4().hex[:12]}"
        plain_text = result.get("plain_text") or "\n\n".join(str(part) for part in [result.get("title"), result.get("opening_paragraph"), result.get("closing_paragraph"), result.get("signature_line")] if part)
        self.conn.execute(
            """
            INSERT INTO recommendation_letters(
              id, client_id, case_id, letter_kind, criterion_code, project_type, project_id,
              recommender_name, recommender_title, recommender_organization, recommender_relationship,
              attorney_notes, prompt_config_json, letter_json, plain_text, status, source,
              created_by_role, created_by_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?, ?, ?)
            """,
            (
                letter_id,
                member["client_id"],
                member["case_id"],
                normalized_kind,
                selected_project["criterion_code"],
                selected_project["project_type"],
                selected_project["id"],
                str(normalized_prompt_config.get("recommender_name", "")).strip(),
                str(normalized_prompt_config.get("recommender_title", "")).strip(),
                str(normalized_prompt_config.get("recommender_organization", "")).strip(),
                str(normalized_prompt_config.get("recommender_relationship", "")).strip(),
                str(normalized_prompt_config.get("attorney_strategy_notes", "")).strip(),
                json.dumps(normalized_prompt_config, ensure_ascii=True),
                json.dumps(result, ensure_ascii=True),
                plain_text,
                source,
                actor.get("role", actor_role),
                actor.get("key", actor_email),
            ),
        )
        self.conn.commit()
        saved = self._serialize_recommendation_letter(one(self.conn, "SELECT * FROM recommendation_letters WHERE id = ?", (letter_id,)))
        self.record_operational_event(
            "recommendation_letter_generated",
            status=status,
            portal=actor_role,
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/attorney/recommendation-letter-generator",
            message="Attorney recommendation letter generated.",
            metadata={"source": source, "project_type": selected_project["project_type"], "letter_kind": normalized_kind},
            actor_role=actor.get("role", actor_role),
            actor_key=actor.get("key", actor_email),
        )
        return {"ok": True, "status": status, "source": source, "generated_at": datetime.utcnow().isoformat(timespec="seconds"), "compiled_prompt": compiled_prompt, "letter_record": saved}

    def update_recommendation_letter_status(
        self,
        letter_id: str,
        status: str,
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        letter = one(self.conn, "SELECT * FROM recommendation_letters WHERE id = ?", (letter_id.strip(),))
        if not letter:
            raise ValueError("Recommendation letter not found")
        self._assert_member_batch_access(letter["client_id"], actor_role=actor_role, actor_email=actor_email)
        normalized_status = status.strip().lower()
        if normalized_status not in {"generated", "approved", "sent_to_member"}:
            raise ValueError("Unsupported recommendation letter status")
        self.conn.execute(
            """
            UPDATE recommendation_letters
            SET status = ?,
                approved_at = CASE WHEN ? = 'approved' THEN CURRENT_TIMESTAMP ELSE approved_at END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized_status, normalized_status, letter["id"]),
        )
        self.conn.commit()
        return self._serialize_recommendation_letter(one(self.conn, "SELECT * FROM recommendation_letters WHERE id = ?", (letter["id"],)))

    def send_recommendation_letter_to_member(
        self,
        letter_id: str,
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        letter = one(self.conn, "SELECT * FROM recommendation_letters WHERE id = ?", (letter_id.strip(),))
        if not letter:
            raise ValueError("Recommendation letter not found")
        if letter["status"] != "approved":
            raise ValueError("Approve recommendation letter before sending it to the member")
        self._assert_member_batch_access(letter["client_id"], actor_role=actor_role, actor_email=actor_email)
        member = self._member_case(letter["client_id"])
        serialized = self._serialize_recommendation_letter(letter)
        project_label = "Critical Role project" if letter["project_type"] == "critical_role" else "Original Contribution project"
        body = "\n".join(
            [
                "A recommendation letter draft is ready for your review and signature.",
                f"Project category: {project_label}",
                f"Letter type: {letter['letter_kind'].replace('_', ' ').title()}",
                f"Download link: {serialized['download_url']}",
                "Please review the letter carefully, confirm the facts, and coordinate signature next steps with your attorney.",
            ]
        )
        message = self.send_message(
            actor_role,
            "Recommendation letter ready for review",
            body,
            "member",
            member["client_id"],
            urgent=True,
            actor_email=actor_email,
        )
        self.conn.execute(
            """
            UPDATE recommendation_letters
            SET status = 'sent_to_member', sent_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (letter["id"],),
        )
        self.conn.commit()
        updated = self._serialize_recommendation_letter(one(self.conn, "SELECT * FROM recommendation_letters WHERE id = ?", (letter["id"],)))
        self.record_operational_event(
            "recommendation_letter_sent_to_member",
            status="success",
            portal=actor_role,
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/attorney/recommendation-letters/send-to-member",
            message="Attorney sent recommendation letter to member for review.",
            metadata={"letter_id": letter["id"], "thread_id": message.get("thread_id", "")},
            actor_role=actor_role,
            actor_key=self._actor_identity(actor_role, actor_email).get("key", ""),
        )
        return {"ok": True, "letter": updated, "message": message}

    def recommendation_letter_download(self, letter_id: str) -> dict:
        letter = one(self.conn, "SELECT * FROM recommendation_letters WHERE id = ?", (letter_id.strip(),))
        if not letter:
            raise ValueError("Recommendation letter not found")
        serialized = self._serialize_recommendation_letter(letter)
        project_type = "Critical Role" if letter["project_type"] == "critical_role" else "Original Contribution"
        file_name = safe_file_name(f"{project_type}-{letter['letter_kind']}-recommendation-{letter['id']}.txt")
        return {
            "file_name": file_name,
            "content_type": "text/plain; charset=utf-8",
            "content": serialized.get("plain_text") or serialized.get("letter", {}).get("plain_text", ""),
        }

    def portal_assistant_reply(
        self,
        actor_role: str,
        question: str,
        client_id: str = "",
        actor_email: str = "",
        thread: list[dict] | None = None,
    ) -> dict:
        role = actor_role.strip().lower()
        if role not in {"builder", "leader", "attorney"}:
            raise ValueError("Assistant is available only for builder, leader, and attorney portals")
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("question is required")
        normalized_thread = self._normalize_assistant_thread(thread or [])
        context = self._assistant_context(role, cleaned_question, client_id.strip(), actor_email.strip().lower(), normalized_thread)
        scope_check = self._assistant_scope_check(cleaned_question, normalized_thread, context)
        if not scope_check["allowed"]:
            answer = self._assistant_scope_guardrail_answer(role, context)
            member = context.get("member") or {}
            self.record_operational_event(
                "portal_assistant",
                status="blocked",
                portal=role,
                client_id=member.get("client_id", ""),
                case_id=member.get("case_id", ""),
                endpoint="/api/assistant/reply",
                message=f"{self._assistant_name(role)} blocked an out-of-scope question.",
                metadata={
                    "source": "guardrail",
                    "scope_reason": scope_check["reason"],
                    "question_length": len(cleaned_question),
                    "thread_turns": len(normalized_thread),
                    "reference_count": 0,
                },
            )
            return {
                "ok": True,
                "status": "blocked",
                "source": "guardrail",
                "assistant_name": self._assistant_name(role),
                "member": {
                    "client_id": member.get("client_id", ""),
                    "case_id": member.get("case_id", ""),
                    "display_name": member.get("display_name", ""),
                },
                **answer,
            }
        assistant_payload = {
            "actor_role": role,
            "question": cleaned_question,
            "thread": normalized_thread,
            "detail_requested": self._assistant_detail_requested(cleaned_question, normalized_thread),
            "context": context,
            "references": context.get("references", []),
        }
        answer = self.openai.answer_portal_question(assistant_payload)
        source = answer.get("source", "fallback")
        status = "success" if source == "openai" else "fallback"
        member = context.get("member") or {}
        self.record_operational_event(
            "portal_assistant",
            status=status,
            portal=role,
            client_id=member.get("client_id", ""),
            case_id=member.get("case_id", ""),
            endpoint="/api/assistant/reply",
            message=f"{self._assistant_name(role)} answered a portal question.",
            metadata={
                "source": source,
                "question_length": len(cleaned_question),
                "thread_turns": len(normalized_thread),
                "reference_count": len(answer.get("references", [])),
            },
        )
        return {
            "ok": True,
            "status": status,
            "source": source,
            "assistant_name": self._assistant_name(role),
            "member": {
                "client_id": member.get("client_id", ""),
                "case_id": member.get("case_id", ""),
                "display_name": member.get("display_name", ""),
            },
            "summary": answer.get("summary", ""),
            "detailed_answer": answer.get("detailed_answer", ""),
            "detail_prompt": answer.get("detail_prompt", ""),
            "suggested_follow_up": answer.get("suggested_follow_up", ""),
            "needs_more_detail": bool(answer.get("needs_more_detail")),
            "response_mode": answer.get("response_mode", "summary"),
            "references": answer.get("references", []),
        }

    def rewrite_member_intake_field(self, member: dict, payload: dict) -> dict:
        if not member:
            raise ValueError("member session is required")
        raw_field_value = str(payload.get("field_value") or "").strip()
        field_value = raw_field_value[:MEMBER_REWRITE_MAX_FIELD_CHARS]
        field_label = str(payload.get("field_label") or "").strip()[:120]
        field_key = str(payload.get("field_key") or "").strip()[:120]
        criterion_type = str(payload.get("criterion_type") or "").strip()[:80]
        form_context = self._sanitize_member_rewrite_context(payload.get("form_context"))
        if not field_label or not field_key:
            raise ValueError("field_label and field_key are required")
        recent_threshold = (datetime.utcnow() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        recent_count = one(
            self.conn,
            """
            SELECT COUNT(*) AS count
            FROM operational_events
            WHERE event_type = 'member_intake_field_rewrite'
              AND actor_key = ?
              AND created_at >= ?
            """,
            (member.get("client_id", ""), recent_threshold),
        )
        if int((recent_count or {}).get("count") or 0) >= MEMBER_REWRITE_RATE_LIMIT_PER_MINUTE:
            raise ValueError("AI rewrite limit reached. Please wait a minute before trying another rewrite.")
        rewrite_payload = {
            "criterion_type": criterion_type,
            "field_key": field_key,
            "field_label": field_label,
            "field_value": field_value,
            "form_context": form_context,
            "member": {
                "display_name": member.get("display_name", ""),
                "client_id": member.get("client_id", ""),
                "case_id": member.get("case_id", ""),
            },
        }
        result = self.openai.rewrite_member_intake_field(rewrite_payload)
        source = result.get("source", "fallback")
        status = "success" if source == "openai" else "fallback"
        self.record_operational_event(
            "member_intake_field_rewrite",
            status=status,
            portal="member",
            client_id=member.get("client_id", ""),
            case_id=member.get("case_id", ""),
            endpoint="/api/member/intake-field-rewrite",
            message=f"Member requested EB1A rewrite for {field_label}.",
            metadata={
                "source": source,
                "criterion_type": criterion_type,
                "field_key": field_key,
                "input_length": len(raw_field_value),
                "sent_input_length": len(field_value),
                "input_truncated": len(raw_field_value) > len(field_value),
                "output_length": len(result.get("rewritten_value", "")),
                "diagnostic": result.get("diagnostic"),
            },
            actor_role="member",
            actor_key=member.get("client_id", ""),
        )
        return {
            "ok": True,
            "status": status,
            "source": source,
            "field_key": field_key,
            "field_label": field_label,
            "rewritten_value": result.get("rewritten_value", ""),
            "rationale": result.get("rationale", ""),
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        }

    def _sanitize_member_rewrite_context(self, context: object) -> dict:
        if not isinstance(context, dict):
            return {}
        sanitized: dict[str, str] = {}
        total_chars = 0
        for key, value in context.items():
            clean_key = str(key or "").strip()[:120]
            if not clean_key:
                continue
            clean_value = str(value or "").strip()[:MEMBER_REWRITE_MAX_CONTEXT_VALUE_CHARS]
            next_total = total_chars + len(clean_key) + len(clean_value)
            if next_total > MEMBER_REWRITE_MAX_CONTEXT_TOTAL_CHARS:
                break
            sanitized[clean_key] = clean_value
            total_chars = next_total
        return sanitized

    def attorney_batch_intake_create(
        self,
        client_id: str,
        member_context: str,
        zip_name: str,
        zip_bytes: bytes,
        created_by_role: str = "attorney",
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        member = self._member_case(client_id)
        self._assert_member_batch_access(member["client_id"], actor_role, actor_email)
        created_by_role = created_by_role.strip().lower() or "attorney"
        if created_by_role not in {"attorney", "leader"}:
            raise ValueError("Unsupported role for batch intake")
        if not zip_name.strip():
            raise ValueError("ZIP file is required")
        if not zip_name.lower().endswith(".zip"):
            raise ValueError("Upload a ZIP archive")
        if not zip_bytes:
            raise ValueError("ZIP file is empty")

        session_id = f"bat_{uuid.uuid4().hex[:12]}"
        extraction_root = self.config.upload_root / "batch-intake" / session_id
        extraction_root.mkdir(parents=True, exist_ok=True)
        zip_path = extraction_root / safe_file_name(zip_name)
        zip_path.write_bytes(zip_bytes)

        skipped_files: list[dict] = []
        try:
            archive = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile as exc:
            raise ValueError("Could not read ZIP archive") from exc

        detail = self.builder_member_detail(member["client_id"])
        member_context_text = self._batch_member_context(detail, member_context)
        folders = self._folders_for_case(member["client_id"], member["case_id"])
        folder_lookup = self._folder_lookup_by_criterion(folders)
        created_items = 0
        self.conn.execute(
            """
            INSERT INTO batch_intake_sessions(
              id, client_id, case_id, uploaded_zip_name, source_note, status, extraction_root,
              skipped_file_count, skipped_files_json, created_by_role
            )
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
            """,
            (
                session_id,
                member["client_id"],
                member["case_id"],
                zip_name.strip(),
                member_context.strip(),
                str(extraction_root),
                0,
                "[]",
                created_by_role,
            ),
        )
        try:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                normalized = PurePosixPath(info.filename)
                if normalized.is_absolute() or ".." in normalized.parts:
                    skipped_files.append({"path": info.filename, "reason": "unsafe_path"})
                    continue
                if not normalized.name or normalized.name.startswith("."):
                    skipped_files.append({"path": info.filename, "reason": "hidden_or_unsupported"})
                    continue

                destination = extraction_root / Path(*normalized.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                file_bytes = archive.read(info)
                if not file_bytes:
                    skipped_files.append({"path": info.filename, "reason": "empty_file"})
                    continue
                destination.write_bytes(file_bytes)
                content_type = mimetypes.guess_type(normalized.name)[0] or "application/octet-stream"
                analysis = self.openai.analyze_evidence_upload(
                    member_context=member_context_text,
                    file_name=normalized.name,
                    content_type=content_type,
                    file_bytes=file_bytes,
                )
                suggested_folder_name = self._suggest_folder_name(normalized)
                duplicate = self._find_duplicate_evidence(
                    member["client_id"],
                    member["case_id"],
                    analysis["criterion_code"],
                    normalized.name,
                )
                assigned_folder_id, folder_decision, assigned_folder_name = self._resolve_batch_folder_defaults(
                    folder_lookup,
                    analysis["criterion_code"],
                    suggested_folder_name,
                )
                review_status = "pending" if duplicate else "ready"
                item_id = f"bti_{uuid.uuid4().hex[:12]}"
                self.conn.execute(
                    """
                    INSERT INTO batch_intake_items(
                      id, session_id, client_id, case_id, zip_path, original_file_name, extracted_path,
                      content_type, criterion_code, document_type, title, ai_description,
                      quality_score, confidence, analysis_source, suggested_folder_name,
                      folder_decision, assigned_folder_id, assigned_folder_name,
                      duplicate_evidence_id, duplicate_action, review_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?)
                    """,
                    (
                        item_id,
                        session_id,
                        member["client_id"],
                        member["case_id"],
                        info.filename,
                        normalized.name,
                        str(destination),
                        content_type,
                        analysis["criterion_code"],
                        self._normalize_document_type(analysis.get("document_type", "Other"), normalized.name, analysis.get("ai_description", "")),
                        analysis.get("title", normalized.name),
                        analysis.get("ai_description", ""),
                        int(analysis.get("quality_score") or 0),
                        int(analysis.get("confidence") or 0),
                        analysis.get("source", ""),
                        suggested_folder_name,
                        folder_decision,
                        assigned_folder_id or None,
                        assigned_folder_name,
                        duplicate["id"] if duplicate else "",
                        review_status,
                    ),
                )
                created_items += 1
        finally:
            archive.close()

        self.conn.execute(
            """
            UPDATE batch_intake_sessions
            SET item_count = ?, skipped_file_count = ?, skipped_files_json = ?
            WHERE id = ?
            """,
            (created_items, len(skipped_files), json.dumps(skipped_files), session_id),
        )
        self.conn.commit()
        self.record_operational_event(
            "attorney_batch_intake",
            status="success",
            portal="attorney",
            client_id=member["client_id"],
            case_id=member["case_id"],
            endpoint="/api/attorney/batch-intake",
            message="Attorney batch intake review queue created.",
            metadata={"session_id": session_id, "item_count": created_items, "skipped_file_count": len(skipped_files)},
        )
        return self.attorney_batch_intake_session(session_id, actor_role=actor_role, actor_email=actor_email)

    def attorney_batch_intake_session(self, session_id: str, actor_role: str = "attorney", actor_email: str = "") -> dict:
        session = one(self.conn, "SELECT * FROM batch_intake_sessions WHERE id = ?", (session_id,))
        if not session:
            raise ValueError("Batch intake session not found")
        self._assert_member_batch_access(session["client_id"], actor_role, actor_email)
        member = self._member_case(session["client_id"])
        detail = self.builder_member_detail(session["client_id"])
        folders = self._folders_for_case(session["client_id"], session["case_id"])
        items = rows(
            self.conn,
            """
            SELECT *
            FROM batch_intake_items
            WHERE session_id = ?
            ORDER BY created_at, original_file_name
            """,
            (session_id,),
        )
        return self._serialize_batch_session(session, items, folders, detail, member)

    def update_attorney_batch_intake_item(
        self,
        session_id: str,
        item_id: str,
        criterion_code: str | None = None,
        document_type: str | None = None,
        title: str | None = None,
        ai_description: str | None = None,
        folder_decision: str | None = None,
        assigned_folder_id: str | None = None,
        assigned_folder_name: str | None = None,
        duplicate_action: str | None = None,
        review_status: str | None = None,
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        session = one(self.conn, "SELECT * FROM batch_intake_sessions WHERE id = ?", (session_id,))
        item = one(self.conn, "SELECT * FROM batch_intake_items WHERE id = ? AND session_id = ?", (item_id, session_id))
        if not session or not item:
            raise ValueError("Batch intake item not found")
        self._assert_member_batch_access(session["client_id"], actor_role, actor_email)

        next_criterion = item["criterion_code"] if criterion_code is None else criterion_code.strip()
        if not one(self.conn, "SELECT code FROM criteria WHERE code = ?", (next_criterion,)):
            raise ValueError("Criterion not found")
        next_document_type = self._normalize_document_type(
            item["document_type"] if document_type is None else document_type.strip(),
            item["original_file_name"],
            item["ai_description"] if ai_description is None else ai_description.strip(),
        )
        next_title = item["title"] if title is None else title.strip()
        if not next_title:
            raise ValueError("Title is required")
        next_description = item["ai_description"] if ai_description is None else ai_description.strip()
        next_folder_decision = item["folder_decision"] if folder_decision is None else folder_decision.strip().lower()
        if next_folder_decision not in {"root", "existing", "create"}:
            raise ValueError("Invalid folder decision")
        next_assigned_folder_id = item.get("assigned_folder_id") or ""
        if assigned_folder_id is not None:
            next_assigned_folder_id = assigned_folder_id.strip()
        next_assigned_folder_name = item.get("assigned_folder_name") or ""
        if assigned_folder_name is not None:
            next_assigned_folder_name = assigned_folder_name.strip()

        if next_folder_decision == "existing":
            if not next_assigned_folder_id:
                raise ValueError("Choose an existing folder")
            folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (next_assigned_folder_id,))
            if not folder or folder["client_id"] != session["client_id"] or folder["case_id"] != session["case_id"] or folder["criterion_code"] != next_criterion:
                raise ValueError("Folder not found")
            next_assigned_folder_name = ""
        elif next_folder_decision == "create":
            if not next_assigned_folder_name:
                raise ValueError("Folder name is required")
            next_assigned_folder_id = ""
        else:
            next_assigned_folder_id = ""
            next_assigned_folder_name = ""

        next_duplicate = self._find_duplicate_evidence(
            session["client_id"],
            session["case_id"],
            next_criterion,
            item["original_file_name"],
        )
        next_duplicate_action = item.get("duplicate_action", "") if duplicate_action is None else duplicate_action.strip().lower()
        if next_duplicate_action not in {"", "copy", "replace", "skip"}:
            raise ValueError("Invalid duplicate action")
        next_review_status = item["review_status"] if review_status is None else review_status.strip().lower()
        if next_review_status not in {"ready", "pending", "skipped"}:
            raise ValueError("Invalid review status")
        if next_duplicate and next_duplicate_action == "":
            next_review_status = "pending" if next_review_status != "skipped" else "skipped"
        elif next_review_status == "pending":
            next_review_status = "ready"

        self.conn.execute(
            """
            UPDATE batch_intake_items
            SET criterion_code = ?,
                document_type = ?,
                title = ?,
                ai_description = ?,
                folder_decision = ?,
                assigned_folder_id = ?,
                assigned_folder_name = ?,
                duplicate_evidence_id = ?,
                duplicate_action = ?,
                review_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND session_id = ?
            """,
            (
                next_criterion,
                next_document_type,
                next_title,
                next_description,
                next_folder_decision,
                next_assigned_folder_id or None,
                next_assigned_folder_name,
                next_duplicate["id"] if next_duplicate else "",
                next_duplicate_action,
                next_review_status,
                item_id,
                session_id,
            ),
        )
        self.conn.commit()
        return self.attorney_batch_intake_session(session_id, actor_role=actor_role, actor_email=actor_email)

    def bulk_update_attorney_batch_intake(
        self,
        session_id: str,
        item_ids: list[str],
        review_status: str | None = None,
        duplicate_action: str | None = None,
        actor_role: str = "attorney",
        actor_email: str = "",
    ) -> dict:
        session = one(self.conn, "SELECT * FROM batch_intake_sessions WHERE id = ?", (session_id,))
        if not session:
            raise ValueError("Batch intake session not found")
        self._assert_member_batch_access(session["client_id"], actor_role, actor_email)
        cleaned_ids = [item.strip() for item in item_ids if item.strip()]
        if not cleaned_ids:
            raise ValueError("No batch intake items selected")
        next_review_status = review_status.strip().lower() if review_status is not None else None
        if next_review_status is not None and next_review_status not in {"ready", "pending", "skipped"}:
            raise ValueError("Invalid review status")
        next_duplicate_action = duplicate_action.strip().lower() if duplicate_action is not None else None
        if next_duplicate_action is not None and next_duplicate_action not in {"", "copy", "replace", "skip"}:
            raise ValueError("Invalid duplicate action")
        selected = rows(
            self.conn,
            f"SELECT * FROM batch_intake_items WHERE session_id = ? AND id IN ({','.join('?' for _ in cleaned_ids)})",
            (session_id, *cleaned_ids),
        )
        if len(selected) != len(cleaned_ids):
            raise ValueError("One or more batch intake items were not found")
        for item in selected:
            resolved_duplicate_action = item.get("duplicate_action", "") if next_duplicate_action is None else next_duplicate_action
            resolved_review_status = item["review_status"] if next_review_status is None else next_review_status
            if item.get("duplicate_evidence_id") and resolved_duplicate_action == "" and resolved_review_status != "skipped":
                resolved_review_status = "pending"
            self.conn.execute(
                """
                UPDATE batch_intake_items
                SET review_status = ?,
                    duplicate_action = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND session_id = ?
                """,
                (resolved_review_status, resolved_duplicate_action, item["id"], session_id),
            )
        self.conn.commit()
        return self.attorney_batch_intake_session(session_id, actor_role=actor_role, actor_email=actor_email)

    def commit_attorney_batch_intake(self, session_id: str, actor_role: str = "attorney", actor_email: str = "") -> dict:
        session = one(self.conn, "SELECT * FROM batch_intake_sessions WHERE id = ?", (session_id,))
        if not session:
            raise ValueError("Batch intake session not found")
        self._assert_member_batch_access(session["client_id"], actor_role, actor_email)
        items = rows(self.conn, "SELECT * FROM batch_intake_items WHERE session_id = ? ORDER BY created_at", (session_id,))
        if not items:
            raise ValueError("Batch intake session is empty")

        unresolved = [
            item for item in items
            if item["review_status"] not in {"skipped", "committed"}
            and item.get("duplicate_evidence_id")
            and item.get("duplicate_action", "") == ""
        ]
        if unresolved:
            raise ValueError(f"{len(unresolved)} item(s) still need duplicate handling before commit")

        folder_cache: dict[tuple[str, str], str] = {}
        committed = 0
        skipped = 0
        errors = 0
        for item in items:
            if item["review_status"] in {"skipped", "committed"} or item.get("duplicate_action") == "skip":
                skipped += 1
                if item["review_status"] != "committed":
                    self.conn.execute(
                        "UPDATE batch_intake_items SET review_status = 'skipped', commit_message = ? WHERE id = ?",
                        ("Skipped before commit.", item["id"]),
                    )
                continue
            try:
                folder_id = self._materialize_batch_folder(session, item, folder_cache)
                extracted_path = Path(item["extracted_path"])
                if not extracted_path.exists():
                    raise ValueError("Extracted file no longer exists for commit")
                result = self.upload_evidence(
                    criterion_code=item["criterion_code"],
                    document_type=item["document_type"],
                    title=item["title"],
                    description=item["ai_description"],
                    file_name=item["original_file_name"],
                    content_type=item["content_type"],
                    file_bytes=extracted_path.read_bytes(),
                    duplicate_action=item.get("duplicate_action", ""),
                    ai_summary=item["ai_description"],
                    quality_score=int(item.get("quality_score") or 0),
                    client_id=session["client_id"],
                    case_id=session["case_id"],
                    folder_id=folder_id,
                )
                committed += 1
                self.conn.execute(
                    """
                    UPDATE batch_intake_items
                    SET review_status = 'committed',
                        commit_evidence_id = ?,
                        commit_message = 'Committed successfully.',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (result["evidence_id"], item["id"]),
                )
            except Exception as exc:
                errors += 1
                self.conn.execute(
                    """
                    UPDATE batch_intake_items
                    SET review_status = 'pending',
                        commit_message = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (str(exc), item["id"]),
                )

        final_status = "committed" if errors == 0 else "partial"
        self.conn.execute(
            """
            UPDATE batch_intake_sessions
            SET status = ?,
                committed_count = ?,
                committed_at = CASE WHEN ? > 0 THEN CURRENT_TIMESTAMP ELSE committed_at END
            WHERE id = ?
            """,
            (final_status, committed, committed, session_id),
        )
        self.conn.commit()
        updated = self.attorney_batch_intake_session(session_id, actor_role=actor_role, actor_email=actor_email)
        self.record_operational_event(
            "attorney_batch_commit",
            status="success" if errors == 0 else "warning",
            portal="attorney",
            client_id=session["client_id"],
            case_id=session["case_id"],
            endpoint="/api/attorney/batch-intake/commit",
            message="Attorney batch intake commit finished.",
            metadata={"session_id": session_id, "committed": committed, "skipped": skipped, "errors": errors},
        )
        return {
            "ok": errors == 0,
            "status": final_status,
            "committed_count": committed,
            "skipped_count": skipped,
            "error_count": errors,
            "session": updated,
        }

    def create_builder_task(
        self,
        client_id: str,
        title: str,
        description: str,
        criterion_code: str,
        due_date: str = "",
        opportunity_id: str = "",
    ) -> dict:
        member = self.builder_member_detail(client_id)["member"]
        builder = self.default_builder()
        task_id = f"tsk_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO tasks(id, client_id, case_id, title, description, status, assigned_by_builder_id, opportunity_id, criterion_code, due_date)
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
            """,
            (
                task_id,
                member["client_id"],
                member["case_id"],
                title.strip(),
                description.strip(),
                builder["builder_id"],
                opportunity_id.strip() or None,
                criterion_code.strip() or None,
                due_date.strip(),
            ),
        )
        self.conn.commit()
        return one(self.conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))

    def update_builder_task(self, task_id: str, status: str | None = None, due_date: str | None = None) -> dict:
        existing = one(self.conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not existing:
            raise ValueError("Task not found")
        new_status = existing["status"] if status is None else (status.strip() or existing["status"])
        new_due = existing.get("due_date", "") if due_date is None else due_date.strip()
        self.conn.execute("UPDATE tasks SET status = ?, due_date = ? WHERE id = ?", (new_status, new_due, task_id))
        self.conn.commit()
        return one(self.conn, "SELECT * FROM tasks WHERE id = ?", (task_id,))

    def create_opportunity(
        self,
        criterion_code: str,
        title: str,
        description: str,
        target_evidence_type: str = "Other",
        suggested_due_days: int = 14,
    ) -> dict:
        criterion = one(self.conn, "SELECT code FROM criteria WHERE code = ?", (criterion_code.strip(),))
        if not criterion:
            raise ValueError("Criterion not found")
        opportunity_id = f"opp_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO opportunity_library(id, criterion_code, title, description, target_evidence_type, suggested_due_days, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                opportunity_id,
                criterion_code.strip(),
                title.strip(),
                description.strip(),
                self._normalize_document_type(target_evidence_type),
                int(suggested_due_days or 14),
            ),
        )
        self.conn.commit()
        return one(self.conn, "SELECT * FROM opportunity_library WHERE id = ?", (opportunity_id,))

    def member_session(self, token: str) -> dict:
        token = token.strip()
        if not token:
            raise ValueError("Session token is required")
        account = one(
            self.conn,
            """
            SELECT a.*
            FROM member_sessions s
            JOIN member_accounts a ON a.id = s.account_id
            WHERE s.token = ?
            """,
            (token,),
        )
        if not account:
            raise ValueError("Session not found")
        return self._member_payload(account)

    def logout_member(self, token: str) -> dict:
        self.conn.execute("DELETE FROM member_sessions WHERE token = ?", (token.strip(),))
        self.conn.commit()
        return {"ok": True, "status": "logged_out"}

    def change_member_password(self, token: str, current_password: str, new_password: str) -> dict:
        if not current_password or not new_password:
            raise ValueError("current_password and new_password are required")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")
        token = token.strip()
        account = one(
            self.conn,
            """
            SELECT a.*
            FROM member_sessions s
            JOIN member_accounts a ON a.id = s.account_id
            WHERE s.token = ?
            """,
            (token,),
        )
        if not account:
            raise ValueError("Session not found")
        if not self._verify_password(current_password, account["password_hash"]):
            raise ValueError("Current password is incorrect")
        self.conn.execute(
            """
            UPDATE member_accounts
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP, last_password_changed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (self._hash_password(new_password), account["id"]),
        )
        self.conn.commit()
        return {"ok": True, "status": "password_updated"}

    def _date_range_label(self, start_date: str, end_date: str, is_current: bool = False) -> str:
        start = start_date.strip()
        end = end_date.strip()
        if start and end:
            return f"{start} to {end}"
        if start and is_current:
            return f"{start} to Present"
        if start:
            return start
        if end:
            return end
        return "Dates not added yet"

    def _serialize_critical_role_project(self, project: dict | None) -> dict:
        if not project:
            return {}
        return {
            **project,
            "is_current_role": bool(project.get("is_current_role")),
            "workflow_status": str(project.get("workflow_status", "draft") or "draft"),
            "is_submitted": str(project.get("workflow_status", "draft") or "draft") == "submitted",
            "role_date_label": self._date_range_label(
                str(project.get("role_start_date", "")),
                str(project.get("role_end_date", "")),
                bool(project.get("is_current_role")),
            ),
            "project_date_label": self._date_range_label(
                str(project.get("project_start_date", "")),
                str(project.get("project_end_date", "")),
                False,
            ),
            "summary_line": " • ".join(
                item
                for item in [
                    str(project.get("organization_name", "")).strip(),
                    str(project.get("role_title", "")).strip(),
                    str(project.get("project_name", "")).strip(),
                ]
                if item
            ) or "Untitled critical role project",
            "has_export_artifact": bool(str(project.get("export_evidence_id", "")).strip()),
        }

    def _critical_role_project(self, project_id: str, client_id: str | None = None, case_id: str | None = None) -> dict:
        project = one(
            self.conn,
            """
            SELECT *
            FROM critical_role_projects
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (
                project_id,
                (client_id or self.config.default_client["client_id"]).strip(),
                (case_id or self.config.default_client["case_id"]).strip(),
            ),
        )
        if not project:
            raise ValueError("Critical role project not found")
        return self._serialize_critical_role_project(project)

    def critical_role_projects(self, client_id: str | None = None, case_id: str | None = None) -> list[dict]:
        cleaned_client_id = (client_id or self.config.default_client["client_id"]).strip()
        cleaned_case_id = (case_id or self.config.default_client["case_id"]).strip()
        project_rows = rows(
            self.conn,
            """
            SELECT *
            FROM critical_role_projects
            WHERE client_id = ? AND case_id = ?
            ORDER BY is_current_role DESC, COALESCE(project_end_date, '') DESC, COALESCE(project_start_date, '') DESC, updated_at DESC
            """,
            (cleaned_client_id, cleaned_case_id),
        )
        return [self._serialize_critical_role_project(item) for item in project_rows]

    def _normalized_critical_role_project_fields(self, fields: dict) -> dict:
        cleaned: dict[str, object] = {}
        tracked_fields = {
            "organization_name",
            "organization_unit",
            "organization_location",
            "organization_website",
            "employment_type",
            "role_title",
            "role_start_date",
            "role_end_date",
            "is_current_role",
            "project_name",
            "project_start_date",
            "project_end_date",
            "project_status",
            "organization_achievements",
            "organization_distinctiveness",
            "role_summary",
            "role_responsibilities",
            "role_evolution",
            "leadership_scope",
            "cross_functional_partners",
            "project_summary",
            "business_need",
            "strategic_importance",
            "contributions_summary",
            "innovation_originality",
            "business_value_summary",
            "quantitative_metrics",
            "revenue_impact",
            "cost_savings",
            "efficiency_gain",
            "user_or_customer_impact",
            "market_or_geographic_impact",
            "compliance_or_risk_impact",
            "peer_distinction_summary",
            "mentorship_leadership",
            "executive_visibility",
            "evidence_available",
            "attorney_friendly_summary",
            "workflow_status",
        }
        for key in tracked_fields:
            if key == "is_current_role":
                cleaned[key] = 1 if bool(fields.get(key)) else 0
            else:
                cleaned[key] = str(fields.get(key, "") or "").strip()
        if cleaned["is_current_role"]:
            cleaned["role_end_date"] = ""
        return cleaned

    def _validate_critical_role_project(self, project: dict) -> None:
        if str(project.get("workflow_status", "draft")) != "submitted":
            return
        if not str(project.get("organization_name", "")).strip():
            raise ValueError("organization_name is required")
        if not str(project.get("role_title", "")).strip():
            raise ValueError("role_title is required")
        if not str(project.get("project_name", "")).strip():
            raise ValueError("project_name is required")
        if not str(project.get("role_summary", "")).strip():
            raise ValueError("role_summary is required")
        if not str(project.get("contributions_summary", "")).strip():
            raise ValueError("contributions_summary is required")
        if not str(project.get("business_value_summary", "")).strip():
            raise ValueError("business_value_summary is required")

    def create_critical_role_project(self, client_id: str | None = None, case_id: str | None = None, **fields) -> dict:
        cleaned_client_id = (client_id or self.config.default_client["client_id"]).strip()
        cleaned_case_id = (case_id or self.config.default_client["case_id"]).strip()
        payload = self._normalized_critical_role_project_fields(fields)
        self._validate_critical_role_project(payload)
        project_id = f"crp_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO critical_role_projects(
              id, client_id, case_id, organization_name, organization_unit, organization_location,
              organization_website, employment_type, role_title, role_start_date, role_end_date,
              is_current_role, project_name, project_start_date, project_end_date, project_status,
              organization_achievements, organization_distinctiveness, role_summary, role_responsibilities,
              role_evolution, leadership_scope, cross_functional_partners, project_summary,
              business_need, strategic_importance, contributions_summary, innovation_originality,
              business_value_summary, quantitative_metrics, revenue_impact, cost_savings,
              efficiency_gain, user_or_customer_impact, market_or_geographic_impact,
              compliance_or_risk_impact, peer_distinction_summary, mentorship_leadership,
              executive_visibility, evidence_available, attorney_friendly_summary, workflow_status, submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                cleaned_client_id,
                cleaned_case_id,
                payload["organization_name"],
                payload["organization_unit"],
                payload["organization_location"],
                payload["organization_website"],
                payload["employment_type"],
                payload["role_title"],
                payload["role_start_date"],
                payload["role_end_date"],
                payload["is_current_role"],
                payload["project_name"],
                payload["project_start_date"],
                payload["project_end_date"],
                payload["project_status"],
                payload["organization_achievements"],
                payload["organization_distinctiveness"],
                payload["role_summary"],
                payload["role_responsibilities"],
                payload["role_evolution"],
                payload["leadership_scope"],
                payload["cross_functional_partners"],
                payload["project_summary"],
                payload["business_need"],
                payload["strategic_importance"],
                payload["contributions_summary"],
                payload["innovation_originality"],
                payload["business_value_summary"],
                payload["quantitative_metrics"],
                payload["revenue_impact"],
                payload["cost_savings"],
                payload["efficiency_gain"],
                payload["user_or_customer_impact"],
                payload["market_or_geographic_impact"],
                payload["compliance_or_risk_impact"],
                payload["peer_distinction_summary"],
                payload["mentorship_leadership"],
                payload["executive_visibility"],
                payload["evidence_available"],
                payload["attorney_friendly_summary"],
                payload["workflow_status"],
                datetime.now(timezone.utc).isoformat(timespec="seconds") if payload["workflow_status"] == "submitted" else None,
            ),
        )
        self.conn.commit()
        saved = (
            self._sync_critical_role_export(project_id, cleaned_client_id, cleaned_case_id)
            if payload["workflow_status"] == "submitted"
            else self._critical_role_project(project_id, cleaned_client_id, cleaned_case_id)
        )
        self.record_operational_event(
            "critical_role_project_submitted" if payload["workflow_status"] == "submitted" else "critical_role_project_draft_saved",
            status="success",
            portal="member",
            client_id=cleaned_client_id,
            case_id=cleaned_case_id,
            endpoint="/api/member/critical-role-projects",
            message="Member submitted a critical role project." if payload["workflow_status"] == "submitted" else "Member saved a critical role draft.",
            metadata={
                "project_id": project_id,
                "project_name": payload["project_name"],
                "organization_name": payload["organization_name"],
                "workflow_status": payload["workflow_status"],
                "export_generated": payload["workflow_status"] == "submitted",
            },
            actor_role="member",
            actor_key=cleaned_client_id,
        )
        return saved

    def update_critical_role_project(self, project_id: str, client_id: str | None = None, case_id: str | None = None, **fields) -> dict:
        existing = self._critical_role_project(project_id, client_id, case_id)
        payload = self._normalized_critical_role_project_fields({**existing, **fields})
        self._validate_critical_role_project(payload)
        self.conn.execute(
            """
            UPDATE critical_role_projects
            SET organization_name = ?,
                organization_unit = ?,
                organization_location = ?,
                organization_website = ?,
                employment_type = ?,
                role_title = ?,
                role_start_date = ?,
                role_end_date = ?,
                is_current_role = ?,
                project_name = ?,
                project_start_date = ?,
                project_end_date = ?,
                project_status = ?,
                organization_achievements = ?,
                organization_distinctiveness = ?,
                role_summary = ?,
                role_responsibilities = ?,
                role_evolution = ?,
                leadership_scope = ?,
                cross_functional_partners = ?,
                project_summary = ?,
                business_need = ?,
                strategic_importance = ?,
                contributions_summary = ?,
                innovation_originality = ?,
                business_value_summary = ?,
                quantitative_metrics = ?,
                revenue_impact = ?,
                cost_savings = ?,
                efficiency_gain = ?,
                user_or_customer_impact = ?,
                market_or_geographic_impact = ?,
                compliance_or_risk_impact = ?,
                peer_distinction_summary = ?,
                mentorship_leadership = ?,
                executive_visibility = ?,
                evidence_available = ?,
                attorney_friendly_summary = ?,
                workflow_status = ?,
                submitted_at = CASE WHEN ? = 'submitted' THEN COALESCE(submitted_at, CURRENT_TIMESTAMP) ELSE NULL END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (
                payload["organization_name"],
                payload["organization_unit"],
                payload["organization_location"],
                payload["organization_website"],
                payload["employment_type"],
                payload["role_title"],
                payload["role_start_date"],
                payload["role_end_date"],
                payload["is_current_role"],
                payload["project_name"],
                payload["project_start_date"],
                payload["project_end_date"],
                payload["project_status"],
                payload["organization_achievements"],
                payload["organization_distinctiveness"],
                payload["role_summary"],
                payload["role_responsibilities"],
                payload["role_evolution"],
                payload["leadership_scope"],
                payload["cross_functional_partners"],
                payload["project_summary"],
                payload["business_need"],
                payload["strategic_importance"],
                payload["contributions_summary"],
                payload["innovation_originality"],
                payload["business_value_summary"],
                payload["quantitative_metrics"],
                payload["revenue_impact"],
                payload["cost_savings"],
                payload["efficiency_gain"],
                payload["user_or_customer_impact"],
                payload["market_or_geographic_impact"],
                payload["compliance_or_risk_impact"],
                payload["peer_distinction_summary"],
                payload["mentorship_leadership"],
                payload["executive_visibility"],
                payload["evidence_available"],
                payload["attorney_friendly_summary"],
                payload["workflow_status"],
                payload["workflow_status"],
                project_id,
                existing["client_id"],
                existing["case_id"],
            ),
        )
        self.conn.commit()
        if payload["workflow_status"] == "submitted":
            saved = self._sync_critical_role_export(project_id, existing["client_id"], existing["case_id"])
        else:
            if str(existing.get("export_evidence_id", "")).strip():
                self._clear_critical_role_export(existing, "critical_role_reverted_to_draft")
            saved = self._critical_role_project(project_id, existing["client_id"], existing["case_id"])
        self.record_operational_event(
            "critical_role_project_submitted" if payload["workflow_status"] == "submitted" else "critical_role_project_draft_saved",
            status="success",
            portal="member",
            client_id=existing["client_id"],
            case_id=existing["case_id"],
            endpoint=f"/api/member/critical-role-projects/{project_id}",
            message="Member updated and submitted a critical role project." if payload["workflow_status"] == "submitted" else "Member updated a critical role draft.",
            metadata={
                "project_id": project_id,
                "project_name": payload["project_name"],
                "organization_name": payload["organization_name"],
                "workflow_status": payload["workflow_status"],
                "export_generated": payload["workflow_status"] == "submitted",
            },
            actor_role="member",
            actor_key=existing["client_id"],
        )
        return saved

    def delete_critical_role_project(self, project_id: str, client_id: str | None = None, case_id: str | None = None) -> dict:
        project = self._critical_role_project(project_id, client_id, case_id)
        export_evidence_id = str(project.get("export_evidence_id", "")).strip()
        if export_evidence_id:
            record = one(self.conn, "SELECT * FROM evidence_items WHERE id = ? AND status != 'archived'", (export_evidence_id,))
            if record:
                self.archive_evidence_record(record, "critical_role_export_deleted")
        self.conn.execute(
            "DELETE FROM critical_role_projects WHERE id = ? AND client_id = ? AND case_id = ?",
            (project_id, project["client_id"], project["case_id"]),
        )
        self.conn.commit()
        self.record_operational_event(
            "critical_role_project_deleted",
            status="success",
            portal="member",
            client_id=project["client_id"],
            case_id=project["case_id"],
            endpoint=f"/api/member/critical-role-projects/{project_id}",
            message="Member deleted a critical role project.",
            metadata={
                "project_id": project_id,
                "project_name": project.get("project_name", ""),
                "organization_name": project.get("organization_name", ""),
                "archived_export_evidence_id": export_evidence_id,
                "deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            actor_role="member",
            actor_key=project["client_id"],
        )
        return {"ok": True, "status": "deleted", "project_id": project_id}

    def _serialize_original_contribution_entry(self, entry: dict | None) -> dict:
        if not entry:
            return {}
        return {
            **entry,
            "workflow_status": str(entry.get("workflow_status", "draft") or "draft"),
            "is_submitted": str(entry.get("workflow_status", "draft") or "draft") == "submitted",
            "date_label": self._date_range_label(
                str(entry.get("contribution_start_date", "")),
                str(entry.get("contribution_end_date", "")),
                False,
            ),
            "summary_line": " • ".join(
                item
                for item in [
                    str(entry.get("contribution_title", "")).strip(),
                    str(entry.get("organization_name", "")).strip(),
                    str(entry.get("contribution_category", "")).strip(),
                ]
                if item
            ) or "Untitled original contribution",
            "has_export_artifact": bool(str(entry.get("export_evidence_id", "")).strip()),
        }

    def _original_contribution_entry(self, entry_id: str, client_id: str | None = None, case_id: str | None = None) -> dict:
        entry = one(
            self.conn,
            """
            SELECT *
            FROM original_contribution_entries
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (
                entry_id,
                (client_id or self.config.default_client["client_id"]).strip(),
                (case_id or self.config.default_client["case_id"]).strip(),
            ),
        )
        if not entry:
            raise ValueError("Original contribution entry not found")
        return self._serialize_original_contribution_entry(entry)

    def original_contribution_entries(self, client_id: str | None = None, case_id: str | None = None) -> list[dict]:
        cleaned_client_id = (client_id or self.config.default_client["client_id"]).strip()
        cleaned_case_id = (case_id or self.config.default_client["case_id"]).strip()
        entry_rows = rows(
            self.conn,
            """
            SELECT *
            FROM original_contribution_entries
            WHERE client_id = ? AND case_id = ?
            ORDER BY COALESCE(contribution_end_date, '') DESC, COALESCE(contribution_start_date, '') DESC, updated_at DESC
            """,
            (cleaned_client_id, cleaned_case_id),
        )
        return [self._serialize_original_contribution_entry(item) for item in entry_rows]

    def _normalized_original_contribution_fields(self, fields: dict) -> dict:
        cleaned: dict[str, str] = {}
        tracked_fields = {
            "contribution_title",
            "contribution_category",
            "field_of_expertise",
            "job_title",
            "organization_name",
            "project_name",
            "contribution_start_date",
            "contribution_end_date",
            "contribution_status",
            "originality_summary",
            "challenging_paradigms",
            "prior_state_of_field",
            "work_vs_external_context",
            "personal_role",
            "distinct_contribution_summary",
            "technical_or_business_problem",
            "solution_or_innovation",
            "unique_features",
            "impact_metrics",
            "adoption_scale",
            "beneficiary_summary",
            "time_savings",
            "cost_savings",
            "revenue_impact",
            "quality_or_risk_impact",
            "field_wide_impact",
            "recognition_and_influence",
            "media_or_public_mentions",
            "adoption_letters_targets",
            "evidence_available",
            "attorney_friendly_summary",
            "workflow_status",
        }
        for key in tracked_fields:
            cleaned[key] = str(fields.get(key, "") or "").strip()
        return cleaned

    def _validate_original_contribution_entry(self, entry: dict) -> None:
        if str(entry.get("workflow_status", "draft")) != "submitted":
            return
        if not str(entry.get("contribution_title", "")).strip():
            raise ValueError("contribution_title is required")
        if not str(entry.get("originality_summary", "")).strip():
            raise ValueError("originality_summary is required")
        if not str(entry.get("distinct_contribution_summary", "")).strip():
            raise ValueError("distinct_contribution_summary is required")
        if not str(entry.get("impact_metrics", "")).strip():
            raise ValueError("impact_metrics is required")
        if not str(entry.get("field_wide_impact", "")).strip():
            raise ValueError("field_wide_impact is required")

    def create_original_contribution_entry(self, client_id: str | None = None, case_id: str | None = None, **fields) -> dict:
        cleaned_client_id = (client_id or self.config.default_client["client_id"]).strip()
        cleaned_case_id = (case_id or self.config.default_client["case_id"]).strip()
        payload = self._normalized_original_contribution_fields(fields)
        self._validate_original_contribution_entry(payload)
        entry_id = f"oce_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO original_contribution_entries(
              id, client_id, case_id, contribution_title, contribution_category, field_of_expertise,
              job_title, organization_name, project_name, contribution_start_date, contribution_end_date,
              contribution_status, originality_summary, challenging_paradigms, prior_state_of_field,
              work_vs_external_context, personal_role, distinct_contribution_summary,
              technical_or_business_problem, solution_or_innovation, unique_features,
              impact_metrics, adoption_scale, beneficiary_summary, time_savings, cost_savings,
              revenue_impact, quality_or_risk_impact, field_wide_impact, recognition_and_influence,
              media_or_public_mentions, adoption_letters_targets, evidence_available, attorney_friendly_summary, workflow_status, submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                cleaned_client_id,
                cleaned_case_id,
                payload["contribution_title"],
                payload["contribution_category"],
                payload["field_of_expertise"],
                payload["job_title"],
                payload["organization_name"],
                payload["project_name"],
                payload["contribution_start_date"],
                payload["contribution_end_date"],
                payload["contribution_status"],
                payload["originality_summary"],
                payload["challenging_paradigms"],
                payload["prior_state_of_field"],
                payload["work_vs_external_context"],
                payload["personal_role"],
                payload["distinct_contribution_summary"],
                payload["technical_or_business_problem"],
                payload["solution_or_innovation"],
                payload["unique_features"],
                payload["impact_metrics"],
                payload["adoption_scale"],
                payload["beneficiary_summary"],
                payload["time_savings"],
                payload["cost_savings"],
                payload["revenue_impact"],
                payload["quality_or_risk_impact"],
                payload["field_wide_impact"],
                payload["recognition_and_influence"],
                payload["media_or_public_mentions"],
                payload["adoption_letters_targets"],
                payload["evidence_available"],
                payload["attorney_friendly_summary"],
                payload["workflow_status"],
                datetime.now(timezone.utc).isoformat(timespec="seconds") if payload["workflow_status"] == "submitted" else None,
            ),
        )
        self.conn.commit()
        saved = (
            self._sync_original_contribution_export(entry_id, cleaned_client_id, cleaned_case_id)
            if payload["workflow_status"] == "submitted"
            else self._original_contribution_entry(entry_id, cleaned_client_id, cleaned_case_id)
        )
        self.record_operational_event(
            "original_contribution_submitted" if payload["workflow_status"] == "submitted" else "original_contribution_draft_saved",
            status="success",
            portal="member",
            client_id=cleaned_client_id,
            case_id=cleaned_case_id,
            endpoint="/api/member/original-contributions",
            message="Member submitted an original contribution." if payload["workflow_status"] == "submitted" else "Member saved an original contribution draft.",
            metadata={
                "entry_id": entry_id,
                "contribution_title": payload["contribution_title"],
                "organization_name": payload["organization_name"],
                "workflow_status": payload["workflow_status"],
                "export_generated": payload["workflow_status"] == "submitted",
            },
            actor_role="member",
            actor_key=cleaned_client_id,
        )
        return saved

    def update_original_contribution_entry(self, entry_id: str, client_id: str | None = None, case_id: str | None = None, **fields) -> dict:
        existing = self._original_contribution_entry(entry_id, client_id, case_id)
        payload = self._normalized_original_contribution_fields({**existing, **fields})
        self._validate_original_contribution_entry(payload)
        self.conn.execute(
            """
            UPDATE original_contribution_entries
            SET contribution_title = ?,
                contribution_category = ?,
                field_of_expertise = ?,
                job_title = ?,
                organization_name = ?,
                project_name = ?,
                contribution_start_date = ?,
                contribution_end_date = ?,
                contribution_status = ?,
                originality_summary = ?,
                challenging_paradigms = ?,
                prior_state_of_field = ?,
                work_vs_external_context = ?,
                personal_role = ?,
                distinct_contribution_summary = ?,
                technical_or_business_problem = ?,
                solution_or_innovation = ?,
                unique_features = ?,
                impact_metrics = ?,
                adoption_scale = ?,
                beneficiary_summary = ?,
                time_savings = ?,
                cost_savings = ?,
                revenue_impact = ?,
                quality_or_risk_impact = ?,
                field_wide_impact = ?,
                recognition_and_influence = ?,
                media_or_public_mentions = ?,
                adoption_letters_targets = ?,
                evidence_available = ?,
                attorney_friendly_summary = ?,
                workflow_status = ?,
                submitted_at = CASE WHEN ? = 'submitted' THEN COALESCE(submitted_at, CURRENT_TIMESTAMP) ELSE NULL END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (
                payload["contribution_title"],
                payload["contribution_category"],
                payload["field_of_expertise"],
                payload["job_title"],
                payload["organization_name"],
                payload["project_name"],
                payload["contribution_start_date"],
                payload["contribution_end_date"],
                payload["contribution_status"],
                payload["originality_summary"],
                payload["challenging_paradigms"],
                payload["prior_state_of_field"],
                payload["work_vs_external_context"],
                payload["personal_role"],
                payload["distinct_contribution_summary"],
                payload["technical_or_business_problem"],
                payload["solution_or_innovation"],
                payload["unique_features"],
                payload["impact_metrics"],
                payload["adoption_scale"],
                payload["beneficiary_summary"],
                payload["time_savings"],
                payload["cost_savings"],
                payload["revenue_impact"],
                payload["quality_or_risk_impact"],
                payload["field_wide_impact"],
                payload["recognition_and_influence"],
                payload["media_or_public_mentions"],
                payload["adoption_letters_targets"],
                payload["evidence_available"],
                payload["attorney_friendly_summary"],
                payload["workflow_status"],
                payload["workflow_status"],
                entry_id,
                existing["client_id"],
                existing["case_id"],
            ),
        )
        self.conn.commit()
        if payload["workflow_status"] == "submitted":
            saved = self._sync_original_contribution_export(entry_id, existing["client_id"], existing["case_id"])
        else:
            if str(existing.get("export_evidence_id", "")).strip():
                self._clear_original_contribution_export(existing, "original_contribution_reverted_to_draft")
            saved = self._original_contribution_entry(entry_id, existing["client_id"], existing["case_id"])
        self.record_operational_event(
            "original_contribution_submitted" if payload["workflow_status"] == "submitted" else "original_contribution_draft_saved",
            status="success",
            portal="member",
            client_id=existing["client_id"],
            case_id=existing["case_id"],
            endpoint=f"/api/member/original-contributions/{entry_id}",
            message="Member updated and submitted an original contribution." if payload["workflow_status"] == "submitted" else "Member updated an original contribution draft.",
            metadata={
                "entry_id": entry_id,
                "contribution_title": payload["contribution_title"],
                "organization_name": payload["organization_name"],
                "workflow_status": payload["workflow_status"],
                "export_generated": payload["workflow_status"] == "submitted",
            },
            actor_role="member",
            actor_key=existing["client_id"],
        )
        return saved

    def delete_original_contribution_entry(self, entry_id: str, client_id: str | None = None, case_id: str | None = None) -> dict:
        entry = self._original_contribution_entry(entry_id, client_id, case_id)
        export_evidence_id = str(entry.get("export_evidence_id", "")).strip()
        if export_evidence_id:
            record = one(self.conn, "SELECT * FROM evidence_items WHERE id = ? AND status != 'archived'", (export_evidence_id,))
            if record:
                self.archive_evidence_record(record, "original_contribution_export_deleted")
        self.conn.execute(
            "DELETE FROM original_contribution_entries WHERE id = ? AND client_id = ? AND case_id = ?",
            (entry_id, entry["client_id"], entry["case_id"]),
        )
        self.conn.commit()
        self.record_operational_event(
            "original_contribution_deleted",
            status="success",
            portal="member",
            client_id=entry["client_id"],
            case_id=entry["case_id"],
            endpoint=f"/api/member/original-contributions/{entry_id}",
            message="Member deleted an original contribution.",
            metadata={
                "entry_id": entry_id,
                "contribution_title": entry.get("contribution_title", ""),
                "organization_name": entry.get("organization_name", ""),
                "archived_export_evidence_id": export_evidence_id,
                "deleted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            actor_role="member",
            actor_key=entry["client_id"],
        )
        return {"ok": True, "status": "deleted", "entry_id": entry_id}

    def _decorate_export_records(self, records: list[dict], evidence_lookup: dict[str, dict]) -> list[dict]:
        decorated_records: list[dict] = []
        for record in records:
            enriched = dict(record)
            export_id = str(record.get("export_evidence_id", "")).strip()
            export = evidence_lookup.get(export_id)
            if export:
                enriched["export_title"] = export.get("title", "")
                enriched["export_file_name"] = export.get("file_name", "")
                enriched["export_open_url"] = export.get("open_url", "")
                enriched["export_drive_web_url"] = export.get("drive_web_url", "")
                enriched["export_created_at"] = export.get("created_at", "")
            else:
                enriched["export_title"] = ""
                enriched["export_file_name"] = ""
                enriched["export_open_url"] = ""
                enriched["export_drive_web_url"] = ""
                enriched["export_created_at"] = ""
            decorated_records.append(enriched)
        return decorated_records

    def member_profile(self, client_id: str | None = None, case_id: str | None = None) -> dict:
        client = {
            "client_id": (client_id or self.config.default_client["client_id"]).strip(),
            "case_id": (case_id or self.config.default_client["case_id"]).strip(),
        }
        profile = one(
            self.conn,
            "SELECT * FROM member_profiles WHERE client_id = ? AND case_id = ?",
            (client["client_id"], client["case_id"]),
        )
        if not profile:
            raise ValueError("Member profile not found")
        profile["profile_confirmed"] = bool(profile.get("profile_confirmed"))
        self._backfill_missing_narrative_exports(client["client_id"], client["case_id"])
        evidence = self._assistant_evidence(client["client_id"], client["case_id"])
        evidence_lookup = {item["id"]: item for item in evidence}
        profile["critical_role_projects"] = self._decorate_export_records(
            self.critical_role_projects(client["client_id"], client["case_id"]),
            evidence_lookup,
        )
        profile["critical_role_project_count"] = len(profile["critical_role_projects"])
        profile["original_contribution_entries"] = self._decorate_export_records(
            self.original_contribution_entries(client["client_id"], client["case_id"]),
            evidence_lookup,
        )
        profile["original_contribution_entry_count"] = len(profile["original_contribution_entries"])
        profile["completion_score"] = self._profile_completion_score(profile)
        return profile

    def update_member_profile(self, client_id: str | None = None, case_id: str | None = None, **fields) -> dict:
        existing = self.member_profile(client_id=client_id, case_id=case_id)
        updates: dict[str, object] = {}
        for key, value in fields.items():
            if key not in existing:
                continue
            if isinstance(value, str):
                updates[key] = value.strip()
            elif key == "profile_confirmed":
                updates[key] = 1 if value else 0
            else:
                updates[key] = value

        first_name = str(updates.get("first_name", existing["first_name"])).strip()
        last_name = str(updates.get("last_name", existing["last_name"])).strip()
        email = str(updates.get("email", existing["email"])).strip()
        if not first_name or not last_name or not email:
            raise ValueError("first_name, last_name, and email are required")

        confirmed = bool(updates.get("profile_confirmed", existing["profile_confirmed"]))
        self.conn.execute(
            """
            UPDATE member_profiles
            SET first_name = ?,
                last_name = ?,
                preferred_name = ?,
                email = ?,
                phone = ?,
                date_of_birth = ?,
                country_of_citizenship = ?,
                country_of_residence = ?,
                city_state = ?,
                current_title = ?,
                current_employer = ?,
                employer_type = ?,
                industry_domain = ?,
                primary_field = ?,
                specialization = ?,
                years_experience = ?,
                highest_degree = ?,
                degree_field = ?,
                institution = ?,
                graduation_year = ?,
                linkedin_url = ?,
                personal_website = ?,
                google_scholar_url = ?,
                orcid_id = ?,
                biography = ?,
                top_achievements = ?,
                awards_summary = ?,
                memberships_summary = ?,
                publications_summary = ?,
                judging_summary = ?,
                original_contributions_summary = ?,
                leading_roles_summary = ?,
                media_summary = ?,
                salary_summary = ?,
                proposed_final_merits_summary = ?,
                target_filing_window = ?,
                profile_confirmed = ?,
                profile_confirmed_at = CASE
                    WHEN ? = 1 THEN CURRENT_TIMESTAMP
                    ELSE NULL
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE client_id = ? AND case_id = ?
            """,
            (
                first_name,
                last_name,
                str(updates.get("preferred_name", existing["preferred_name"])).strip(),
                email,
                str(updates.get("phone", existing["phone"])).strip(),
                str(updates.get("date_of_birth", existing["date_of_birth"])).strip(),
                str(updates.get("country_of_citizenship", existing["country_of_citizenship"])).strip(),
                str(updates.get("country_of_residence", existing["country_of_residence"])).strip(),
                str(updates.get("city_state", existing["city_state"])).strip(),
                str(updates.get("current_title", existing["current_title"])).strip(),
                str(updates.get("current_employer", existing["current_employer"])).strip(),
                str(updates.get("employer_type", existing["employer_type"])).strip(),
                str(updates.get("industry_domain", existing.get("industry_domain", ""))).strip(),
                str(updates.get("primary_field", existing["primary_field"])).strip(),
                str(updates.get("specialization", existing["specialization"])).strip(),
                str(updates.get("years_experience", existing["years_experience"])).strip(),
                str(updates.get("highest_degree", existing["highest_degree"])).strip(),
                str(updates.get("degree_field", existing["degree_field"])).strip(),
                str(updates.get("institution", existing["institution"])).strip(),
                str(updates.get("graduation_year", existing["graduation_year"])).strip(),
                str(updates.get("linkedin_url", existing["linkedin_url"])).strip(),
                str(updates.get("personal_website", existing["personal_website"])).strip(),
                str(updates.get("google_scholar_url", existing["google_scholar_url"])).strip(),
                str(updates.get("orcid_id", existing["orcid_id"])).strip(),
                str(updates.get("biography", existing["biography"])).strip(),
                str(updates.get("top_achievements", existing["top_achievements"])).strip(),
                str(updates.get("awards_summary", existing["awards_summary"])).strip(),
                str(updates.get("memberships_summary", existing["memberships_summary"])).strip(),
                str(updates.get("publications_summary", existing["publications_summary"])).strip(),
                str(updates.get("judging_summary", existing["judging_summary"])).strip(),
                str(updates.get("original_contributions_summary", existing["original_contributions_summary"])).strip(),
                str(updates.get("leading_roles_summary", existing["leading_roles_summary"])).strip(),
                str(updates.get("media_summary", existing["media_summary"])).strip(),
                str(updates.get("salary_summary", existing["salary_summary"])).strip(),
                str(updates.get("proposed_final_merits_summary", existing["proposed_final_merits_summary"])).strip(),
                str(updates.get("target_filing_window", existing["target_filing_window"])).strip(),
                1 if confirmed else 0,
                1 if confirmed else 0,
                existing["client_id"],
                existing["case_id"],
            ),
        )
        self.conn.commit()
        self.conn.execute(
            "UPDATE member_accounts SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE client_id = ? AND case_id = ?",
            (email, existing["client_id"], existing["case_id"]),
        )
        self.conn.commit()
        return self.member_profile(client_id=existing["client_id"], case_id=existing["case_id"])

    def criterion_workspace(self, criterion_code: str, search: str = "", client_id: str | None = None, case_id: str | None = None) -> dict:
        criterion = one(self.conn, "SELECT code, name, description FROM criteria WHERE code = ?", (criterion_code,))
        if not criterion:
            raise ValueError("Criterion not found")
        client_id = (client_id or self.config.default_client["client_id"]).strip()
        case_id = (case_id or self.config.default_client["case_id"]).strip()
        folders = rows(
            self.conn,
            """
            SELECT f.*,
                   (SELECT COUNT(*) FROM evidence_folders c WHERE c.parent_id = f.id) AS child_folder_count,
                   (SELECT COUNT(*) FROM evidence_items e WHERE e.folder_id = f.id AND e.status != 'archived') AS file_count
            FROM evidence_folders f
            WHERE f.client_id = ? AND f.case_id = ? AND f.criterion_code = ?
            ORDER BY LOWER(f.name), f.created_at
            """,
            (client_id, case_id, criterion_code),
        )
        files = rows(
            self.conn,
            """
            SELECT e.*
            FROM evidence_items e
            WHERE e.client_id = ? AND e.case_id = ? AND e.criterion_code = ? AND e.status != 'archived'
            ORDER BY e.created_at DESC
            """,
            (client_id, case_id, criterion_code),
        )
        if search.strip():
            query = search.strip().lower()
            folders = [folder for folder in folders if query in folder["name"].lower()]
            files = [
                item for item in files
                if query in item.get("file_name", "").lower()
                or query in (item.get("title") or "").lower()
                or query in (item.get("description") or "").lower()
                or query in (item.get("ai_summary") or "").lower()
            ]
        return {
            "criterion": criterion,
            "document_type_counts": self._document_type_counts(files),
            "folders": [self._decorate_folder(folder, folders) for folder in folders],
            "files": [self._decorate_file(item, folders) for item in files],
        }

    def evidence(self, search: str = "") -> list[dict]:
        if search:
            return rows(
                self.conn,
                """
                SELECT e.*
                FROM evidence_search s
                JOIN evidence_items e ON e.id = s.evidence_id
                WHERE evidence_search MATCH ? AND e.status != 'archived'
                ORDER BY e.created_at DESC
                """,
                (search,),
            )
        return rows(self.conn, "SELECT * FROM evidence_items WHERE status != 'archived' ORDER BY created_at DESC")

    def planner_items(self, client_id: str | None = None, case_id: str | None = None) -> list[dict]:
        client = {
            "client_id": (client_id or self.config.default_client["client_id"]).strip(),
            "case_id": (case_id or self.config.default_client["case_id"]).strip(),
        }
        items = rows(
            self.conn,
            """
            SELECT p.*, c.name AS criterion_name
            FROM planner_items p
            LEFT JOIN criteria c ON c.code = p.criterion_code
            WHERE p.client_id = ? AND p.case_id = ?
            ORDER BY p.planned_completion_date ASC, p.created_at DESC
            """,
            (client["client_id"], client["case_id"]),
        )
        folders = rows(
            self.conn,
            "SELECT * FROM evidence_folders WHERE client_id = ? AND case_id = ?",
            (client["client_id"], client["case_id"]),
        )
        for item in items:
            item["folder_path"] = self._folder_path(item["folder_id"], folders) if item.get("folder_id") else ""
            item["review_url"] = self._planner_review_url(item)
        return items

    def create_planner_item(
        self,
        member_role: str,
        issued_by: str,
        description: str,
        planned_completion_date: str,
        actual_completion_date: str = "",
        status: str = "planned",
        comments: str = "",
        criterion_code: str = "",
        folder_id: str = "",
        client_id: str | None = None,
        case_id: str | None = None,
    ) -> dict:
        client = {
            "client_id": (client_id or self.config.default_client["client_id"]).strip(),
            "case_id": (case_id or self.config.default_client["case_id"]).strip(),
        }
        member_role = member_role.strip()
        issued_by = issued_by.strip()
        description = description.strip()
        planned_completion_date = planned_completion_date.strip()
        actual_completion_date = actual_completion_date.strip()
        comments = comments.strip()
        status = status.strip().lower() or "planned"
        criterion_code = criterion_code.strip()
        folder_id = folder_id.strip()
        if not member_role or not issued_by or not description or not planned_completion_date:
            raise ValueError("member_role, issued_by, description, and planned_completion_date are required")
        if status not in PLANNER_STATUSES:
            raise ValueError("Invalid planner status")
        if criterion_code:
            criterion = one(self.conn, "SELECT code FROM criteria WHERE code = ?", (criterion_code,))
            if not criterion:
                raise ValueError("Criterion not found")
        if folder_id:
            folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (folder_id,))
            if not folder:
                raise ValueError("Folder not found")
            if criterion_code and folder["criterion_code"] != criterion_code:
                raise ValueError("Folder does not belong to the selected criterion")
        item_id = f"pln_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO planner_items(
              id, client_id, case_id, criterion_code, folder_id, member_role, issued_by,
              description, planned_completion_date, actual_completion_date, status, comments
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                client["client_id"],
                client["case_id"],
                criterion_code or None,
                folder_id or None,
                member_role,
                issued_by,
                description,
                planned_completion_date,
                actual_completion_date,
                status,
                comments,
            ),
        )
        self.conn.commit()
        return self.planner_item(item_id)

    def planner_item(self, item_id: str) -> dict:
        item = one(
            self.conn,
            """
            SELECT p.*, c.name AS criterion_name
            FROM planner_items p
            LEFT JOIN criteria c ON c.code = p.criterion_code
            WHERE p.id = ?
            """,
            (item_id,),
        )
        if not item:
            raise ValueError("Planner item not found")
        folders = rows(
            self.conn,
            "SELECT * FROM evidence_folders WHERE client_id = ? AND case_id = ?",
            (item["client_id"], item["case_id"]),
        )
        item["folder_path"] = self._folder_path(item["folder_id"], folders) if item.get("folder_id") else ""
        item["review_url"] = self._planner_review_url(item)
        return item

    def update_planner_item(
        self,
        item_id: str,
        member_role: str | None = None,
        issued_by: str | None = None,
        description: str | None = None,
        planned_completion_date: str | None = None,
        actual_completion_date: str | None = None,
        status: str | None = None,
        comments: str | None = None,
        criterion_code: str | None = None,
        folder_id: str | None = None,
        client_id: str | None = None,
        case_id: str | None = None,
    ) -> dict:
        existing = one(self.conn, "SELECT * FROM planner_items WHERE id = ?", (item_id,))
        if not existing:
            raise ValueError("Planner item not found")
        if client_id and existing["client_id"] != client_id:
            raise ValueError("Planner item not found")
        if case_id and existing["case_id"] != case_id:
            raise ValueError("Planner item not found")
        new_status = existing["status"] if status is None else (status.strip().lower() or "planned")
        if new_status not in PLANNER_STATUSES:
            raise ValueError("Invalid planner status")
        new_criterion = existing.get("criterion_code") or ""
        if criterion_code is not None:
            new_criterion = criterion_code.strip()
            if new_criterion:
                criterion = one(self.conn, "SELECT code FROM criteria WHERE code = ?", (new_criterion,))
                if not criterion:
                    raise ValueError("Criterion not found")
        new_folder_id = existing.get("folder_id") or ""
        if folder_id is not None:
            new_folder_id = folder_id.strip()
            if new_folder_id:
                folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (new_folder_id,))
                if not folder:
                    raise ValueError("Folder not found")
                if new_criterion and folder["criterion_code"] != new_criterion:
                    raise ValueError("Folder does not belong to the selected criterion")
        self.conn.execute(
            """
            UPDATE planner_items
            SET member_role = ?,
                issued_by = ?,
                description = ?,
                planned_completion_date = ?,
                actual_completion_date = ?,
                status = ?,
                comments = ?,
                criterion_code = ?,
                folder_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                existing["member_role"] if member_role is None else member_role.strip(),
                existing["issued_by"] if issued_by is None else issued_by.strip(),
                existing["description"] if description is None else description.strip(),
                existing["planned_completion_date"] if planned_completion_date is None else planned_completion_date.strip(),
                existing["actual_completion_date"] if actual_completion_date is None else actual_completion_date.strip(),
                new_status,
                existing["comments"] if comments is None else comments.strip(),
                new_criterion or None,
                new_folder_id or None,
                item_id,
            ),
        )
        self.conn.commit()
        return self.planner_item(item_id)

    def delete_planner_item(self, item_id: str, client_id: str | None = None, case_id: str | None = None) -> dict:
        item = one(self.conn, "SELECT id, client_id, case_id FROM planner_items WHERE id = ?", (item_id,))
        if not item:
            raise ValueError("Planner item not found")
        if client_id and item["client_id"] != client_id:
            raise ValueError("Planner item not found")
        if case_id and item["case_id"] != case_id:
            raise ValueError("Planner item not found")
        self.conn.execute("DELETE FROM planner_items WHERE id = ?", (item_id,))
        self.conn.commit()
        return {"ok": True, "status": "deleted", "planner_item_id": item_id}

    def upload_evidence(
        self,
        criterion_code: str,
        document_type: str,
        title: str,
        description: str,
        file_name: str,
        content_type: str,
        file_bytes: bytes,
        duplicate_action: str = "",
        ai_summary: str = "",
        quality_score: int | None = None,
        client_id: str | None = None,
        case_id: str | None = None,
        folder_id: str | None = None,
    ) -> dict:
        criterion_code = criterion_code.strip()
        document_type = self._normalize_document_type(document_type, file_name, description)
        title = title.strip()
        description = description.strip()
        duplicate_action = duplicate_action.strip().lower()
        if not criterion_code or not title or not file_name:
            raise ValueError("criterion_code, title, and file are required")

        client_id = (client_id or self.config.default_client["client_id"]).strip()
        case_id = (case_id or self.config.default_client["case_id"]).strip()
        cleaned_file_name = safe_file_name(file_name)
        duplicate = one(
            self.conn,
            """
            SELECT * FROM evidence_items
            WHERE client_id = ? AND case_id = ? AND criterion_code = ?
              AND file_name = ? AND status != 'archived'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (client_id, case_id, criterion_code, cleaned_file_name),
        )
        if duplicate and duplicate_action not in {"replace", "copy"}:
            raise DuplicateEvidenceError(
                {
                    "id": duplicate["id"],
                    "file_name": duplicate["file_name"],
                    "title": duplicate["title"],
                    "criterion_code": duplicate["criterion_code"],
                }
            )
        if duplicate and duplicate_action == "replace":
            archived = self.archive_evidence_record(duplicate, "replaced_by_member_upload")
            if not archived["ok"]:
                raise RuntimeError(archived["error"])

        with tempfile.NamedTemporaryFile(delete=True) as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            try:
                stored = self.storage.store(client_id, case_id, criterion_code, file_name, Path(tmp.name))
            except (GoogleDriveConfigError, GoogleDriveUploadError) as exc:
                local_storage = EvidenceStorage(self.config.upload_root, self.config.drive_mirror_root, None)
                stored = local_storage.store(client_id, case_id, criterion_code, file_name, Path(tmp.name))
                self.record_operational_event(
                    "evidence_storage_fallback",
                    status="fallback",
                    portal="member",
                    client_id=client_id,
                    case_id=case_id,
                    endpoint="/api/evidence",
                    error_code=exc.__class__.__name__,
                    message="Evidence stored in local mirror because remote storage was unavailable.",
                    metadata={"criterion_code": criterion_code, "file_name": file_name},
                )

        if ai_summary:
            summary = ai_summary
            score = int(quality_score if quality_score is not None else 50)
        else:
            try:
                summary, score = self.openai.summarize_upload(title, criterion_code)
                self.record_operational_event(
                    "openai_summary",
                    status="fallback" if self.openai.enabled and score == 45 else "success",
                    portal="member",
                    client_id=client_id,
                    case_id=case_id,
                    endpoint="/api/evidence",
                    message="Evidence summary completed.",
                    metadata={"criterion_code": criterion_code, "title": title[:120], "quality_score": score},
                )
            except Exception as exc:
                summary = f"Evidence uploaded. AI summary failed and can be retried. Reason: {exc}"
                score = 0
                self.record_operational_event(
                    "openai_summary",
                    status="error",
                    portal="member",
                    client_id=client_id,
                    case_id=case_id,
                    endpoint="/api/evidence",
                    error_code="summary_failed",
                    message=str(exc),
                )

        resolved_content_type = content_type or mimetypes.guess_type(stored.file_name)[0] or "application/octet-stream"
        resolved_folder_id = None
        if folder_id:
            folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (folder_id,))
            if not folder or folder["client_id"] != client_id or folder["case_id"] != case_id or folder["criterion_code"] != criterion_code:
                raise ValueError("Folder not found")
            resolved_folder_id = folder["id"]
        self.conn.execute(
            """
            INSERT INTO evidence_items(
              id, client_id, case_id, criterion_code, document_type, title, description, file_name,
              content_type, local_path, drive_mirror_path, drive_path, drive_file_id,
              drive_web_url, ai_summary, quality_score, folder_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored.evidence_id,
                client_id,
                case_id,
                criterion_code,
                document_type,
                title,
                description,
                stored.file_name,
                resolved_content_type,
                stored.local_path,
                stored.drive_path,
                stored.drive_path,
                stored.drive_file_id,
                stored.drive_web_url,
                summary,
                score,
                resolved_folder_id,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO evidence_search(
              title, description, file_name, ai_summary, client_id, case_id, evidence_id, criterion_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, stored.file_name, summary, client_id, case_id, stored.evidence_id, criterion_code),
        )
        self.conn.commit()
        return {
            "ok": True,
            "status": "success",
            "message": "Evidence uploaded successfully.",
            "evidence_id": stored.evidence_id,
            "document_type": document_type,
            "ai_summary": summary,
            "quality_score": score,
            "drive_path": stored.drive_path,
            "drive_file_id": stored.drive_file_id,
            "drive_web_url": stored.drive_web_url,
        }

    def _generated_export_file_name(self, prefix: str, *parts: str) -> str:
        tokens = [safe_file_name(part).strip("-") for part in parts if str(part or "").strip()]
        stem = "-".join(token for token in tokens if token) or prefix
        return safe_file_name(f"{prefix}-{stem}.pdf")

    def _store_generated_export_evidence(
        self,
        *,
        criterion_code: str,
        title: str,
        description: str,
        file_name: str,
        file_bytes: bytes,
        ai_summary: str,
        client_id: str,
        case_id: str,
        replace_evidence_id: str = "",
    ) -> dict:
        existing_id = replace_evidence_id.strip()
        if existing_id:
            existing = one(
                self.conn,
                "SELECT * FROM evidence_items WHERE id = ? AND client_id = ? AND case_id = ? AND status != 'archived'",
                (existing_id, client_id, case_id),
            )
            if existing:
                self.archive_evidence_record(existing, "regenerated_questionnaire_export")

        with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp.flush()
            try:
                stored = self.storage.store(client_id, case_id, criterion_code, file_name, Path(tmp.name))
            except (GoogleDriveConfigError, GoogleDriveUploadError):
                local_storage = EvidenceStorage(self.config.upload_root, self.config.drive_mirror_root, None)
                stored = local_storage.store(client_id, case_id, criterion_code, file_name, Path(tmp.name))

        content_type = "application/pdf"
        self.conn.execute(
            """
            INSERT INTO evidence_items(
              id, client_id, case_id, criterion_code, document_type, title, description, file_name,
              content_type, local_path, drive_mirror_path, drive_path, drive_file_id,
              drive_web_url, ai_summary, quality_score, folder_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored.evidence_id,
                client_id,
                case_id,
                criterion_code,
                "Other",
                title.strip(),
                description.strip(),
                stored.file_name,
                content_type,
                stored.local_path,
                stored.drive_path,
                stored.drive_path,
                stored.drive_file_id,
                stored.drive_web_url,
                ai_summary.strip(),
                100,
                None,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO evidence_search(
              title, description, file_name, ai_summary, client_id, case_id, evidence_id, criterion_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip(),
                description.strip(),
                stored.file_name,
                ai_summary.strip(),
                client_id,
                case_id,
                stored.evidence_id,
                criterion_code,
            ),
        )
        self.conn.commit()
        return {
            "evidence_id": stored.evidence_id,
            "file_name": stored.file_name,
            "drive_web_url": stored.drive_web_url,
            "drive_path": stored.drive_path,
        }

    def _sync_critical_role_export(self, project_id: str, client_id: str, case_id: str) -> dict:
        project = self._critical_role_project(project_id, client_id, case_id)
        member = self._member_case(client_id)
        file_bytes = render_critical_role_pdf(member.get("display_name", ""), project)
        artifact = self._store_generated_export_evidence(
            criterion_code="leading_critical_role",
            title=f"Critical Role Export - {project.get('project_name') or project.get('organization_name') or 'Untitled Project'}",
            description=(
                "Generated from the member's Critical Role portal intake. "
                f"Organization: {project.get('organization_name', '')}. "
                f"Role: {project.get('role_title', '')}. "
                f"Workflow status: {project.get('workflow_status', 'draft')}."
            ),
            file_name=self._generated_export_file_name(
                "critical-role-export",
                project.get("organization_name", ""),
                project.get("project_name", ""),
            ),
            file_bytes=file_bytes,
            ai_summary=(
                "Generated questionnaire export for the Leading or Critical Role criterion. "
                "This PDF captures the member-submitted role, project, business value, metrics, and evidence notes."
            ),
            client_id=client_id,
            case_id=case_id,
            replace_evidence_id=str(project.get("export_evidence_id", "")),
        )
        self.conn.execute(
            """
            UPDATE critical_role_projects
            SET export_evidence_id = ?, export_generated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (artifact["evidence_id"], project_id, client_id, case_id),
        )
        self.conn.commit()
        return self._critical_role_project(project_id, client_id, case_id)

    def _sync_original_contribution_export(self, entry_id: str, client_id: str, case_id: str) -> dict:
        entry = self._original_contribution_entry(entry_id, client_id, case_id)
        member = self._member_case(client_id)
        file_bytes = render_original_contribution_pdf(member.get("display_name", ""), entry)
        artifact = self._store_generated_export_evidence(
            criterion_code="original_contributions",
            title=f"Original Contribution Export - {entry.get('contribution_title') or 'Untitled Contribution'}",
            description=(
                "Generated from the member's Original Contributions portal intake. "
                f"Contribution: {entry.get('contribution_title', '')}. "
                f"Organization: {entry.get('organization_name', '')}. "
                f"Workflow status: {entry.get('workflow_status', 'draft')}."
            ),
            file_name=self._generated_export_file_name(
                "original-contribution-export",
                entry.get("organization_name", ""),
                entry.get("contribution_title", ""),
            ),
            file_bytes=file_bytes,
            ai_summary=(
                "Generated questionnaire export for the Original Contributions criterion. "
                "This PDF captures the member-submitted originality, significance, metrics, and supporting evidence notes."
            ),
            client_id=client_id,
            case_id=case_id,
            replace_evidence_id=str(entry.get("export_evidence_id", "")),
        )
        self.conn.execute(
            """
            UPDATE original_contribution_entries
            SET export_evidence_id = ?, export_generated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (artifact["evidence_id"], entry_id, client_id, case_id),
        )
        self.conn.commit()
        return self._original_contribution_entry(entry_id, client_id, case_id)

    def _clear_critical_role_export(self, project: dict, reason: str) -> None:
        export_evidence_id = str(project.get("export_evidence_id", "")).strip()
        if export_evidence_id:
            record = one(self.conn, "SELECT * FROM evidence_items WHERE id = ? AND status != 'archived'", (export_evidence_id,))
            if record:
                self.archive_evidence_record(record, reason)
        self.conn.execute(
            """
            UPDATE critical_role_projects
            SET export_evidence_id = '', export_generated_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (project["id"], project["client_id"], project["case_id"]),
        )
        self.conn.commit()

    def _clear_original_contribution_export(self, entry: dict, reason: str) -> None:
        export_evidence_id = str(entry.get("export_evidence_id", "")).strip()
        if export_evidence_id:
            record = one(self.conn, "SELECT * FROM evidence_items WHERE id = ? AND status != 'archived'", (export_evidence_id,))
            if record:
                self.archive_evidence_record(record, reason)
        self.conn.execute(
            """
            UPDATE original_contribution_entries
            SET export_evidence_id = '', export_generated_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND client_id = ? AND case_id = ?
            """,
            (entry["id"], entry["client_id"], entry["case_id"]),
        )
        self.conn.commit()

    def _backfill_missing_narrative_exports(self, client_id: str, case_id: str) -> None:
        missing_critical_role = rows(
            self.conn,
            """
            SELECT id
            FROM critical_role_projects
            WHERE client_id = ? AND case_id = ? AND workflow_status = 'submitted' AND COALESCE(export_evidence_id, '') = ''
            """,
            (client_id, case_id),
        )
        for item in missing_critical_role:
            self._sync_critical_role_export(item["id"], client_id, case_id)

        missing_original_contributions = rows(
            self.conn,
            """
            SELECT id
            FROM original_contribution_entries
            WHERE client_id = ? AND case_id = ? AND workflow_status = 'submitted' AND COALESCE(export_evidence_id, '') = ''
            """,
            (client_id, case_id),
        )
        for item in missing_original_contributions:
            self._sync_original_contribution_export(item["id"], client_id, case_id)

    def analyze_evidence(self, member_context: str, file_name: str, content_type: str, file_bytes: bytes) -> dict:
        if not file_name:
            self.record_operational_event("openai_analysis", status="error", portal="member", endpoint="/api/evidence/analyze", error_code="missing_file", message="Evidence analysis requested without a file.")
            raise ValueError("file is required")
        if not member_context.strip():
            self.record_operational_event("openai_analysis", status="error", portal="member", endpoint="/api/evidence/analyze", error_code="missing_context", message="Evidence analysis requested without member context.")
            raise ValueError("member_context is required")
        analysis = self.openai.analyze_evidence_upload(member_context, file_name, content_type, file_bytes)
        self.record_operational_event(
            "openai_analysis",
            status="success" if analysis.get("source") == "openai" else "fallback",
            portal="member",
            client_id=self.config.default_client["client_id"],
            case_id=self.config.default_client["case_id"],
            endpoint="/api/evidence/analyze",
            message="Evidence analysis completed.",
            metadata={
                "criterion_code": analysis.get("criterion_code", ""),
                "document_type": analysis.get("document_type", "Other"),
                "source": analysis.get("source", "unknown"),
            },
        )
        return {"ok": True, "status": "draft", **analysis}

    def create_folder(
        self,
        criterion_code: str,
        name: str,
        parent_id: str | None = None,
        color: str = "#1f6f5b",
        client_id: str | None = None,
        case_id: str | None = None,
    ) -> dict:
        criterion = one(self.conn, "SELECT code FROM criteria WHERE code = ?", (criterion_code,))
        if not criterion:
            raise ValueError("Criterion not found")
        name = name.strip()
        if not name:
            raise ValueError("Folder name is required")
        client_id = (client_id or self.config.default_client["client_id"]).strip()
        case_id = (case_id or self.config.default_client["case_id"]).strip()
        parent = self._validate_parent_folder(parent_id, criterion_code) if parent_id else None
        if parent and (parent["client_id"] != client_id or parent["case_id"] != case_id):
            raise ValueError("Folder not found")
        folder_id = f"fld_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO evidence_folders(id, client_id, case_id, criterion_code, parent_id, name, color)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (folder_id, client_id, case_id, criterion_code, parent["id"] if parent else None, name, color or "#1f6f5b"),
        )
        self.conn.commit()
        return self.folder(folder_id)

    def folder(self, folder_id: str) -> dict:
        folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (folder_id,))
        if not folder:
            raise ValueError("Folder not found")
        siblings = rows(
            self.conn,
            """
            SELECT *
            FROM evidence_folders
            WHERE client_id = ? AND case_id = ? AND criterion_code = ?
            """,
            (folder["client_id"], folder["case_id"], folder["criterion_code"]),
        )
        return self._decorate_folder(folder, siblings)

    def update_folder(self, folder_id: str, name: str | None = None, color: str | None = None, parent_id: str | None = None, client_id: str | None = None, case_id: str | None = None) -> dict:
        folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (folder_id,))
        if not folder:
            raise ValueError("Folder not found")
        if client_id and folder["client_id"] != client_id:
            raise ValueError("Folder not found")
        if case_id and folder["case_id"] != case_id:
            raise ValueError("Folder not found")
        new_name = name.strip() if name is not None else folder["name"]
        if not new_name:
            raise ValueError("Folder name is required")
        if parent_id == folder_id:
            raise ValueError("Folder cannot be its own parent")
        new_parent_id = folder["parent_id"]
        if parent_id is not None:
            if parent_id == "":
                new_parent_id = None
            else:
                parent = self._validate_parent_folder(parent_id, folder["criterion_code"])
                if client_id and parent["client_id"] != client_id:
                    raise ValueError("Folder not found")
                if case_id and parent["case_id"] != case_id:
                    raise ValueError("Folder not found")
                if self._is_descendant(folder_id, parent["id"]):
                    raise ValueError("Folder cannot be moved into its own subfolder")
                new_parent_id = parent["id"]
        self.conn.execute(
            """
            UPDATE evidence_folders
            SET name = ?, color = ?, parent_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_name, color or folder["color"], new_parent_id, folder_id),
        )
        self.conn.commit()
        return self.folder(folder_id)

    def delete_folder(self, folder_id: str, client_id: str | None = None, case_id: str | None = None) -> dict:
        folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (folder_id,))
        if not folder:
            raise ValueError("Folder not found")
        if client_id and folder["client_id"] != client_id:
            raise ValueError("Folder not found")
        if case_id and folder["case_id"] != case_id:
            raise ValueError("Folder not found")
        parent_id = folder["parent_id"]
        self.conn.execute("UPDATE evidence_folders SET parent_id = ?, updated_at = CURRENT_TIMESTAMP WHERE parent_id = ?", (parent_id, folder_id))
        self.conn.execute("UPDATE evidence_items SET folder_id = ?, updated_at = CURRENT_TIMESTAMP WHERE folder_id = ? AND status != 'archived'", (parent_id, folder_id))
        self.conn.execute("DELETE FROM evidence_folders WHERE id = ?", (folder_id,))
        self.conn.commit()
        return {"ok": True, "status": "deleted", "folder_id": folder_id}

    def move_evidence_to_folder(self, evidence_id: str, folder_id: str | None, client_id: str | None = None, case_id: str | None = None) -> dict:
        record = one(self.conn, "SELECT * FROM evidence_items WHERE id = ? AND status != 'archived'", (evidence_id,))
        if not record:
            raise ValueError("Evidence not found")
        if client_id and record["client_id"] != client_id:
            raise ValueError("Evidence not found")
        if case_id and record["case_id"] != case_id:
            raise ValueError("Evidence not found")
        target_folder_id = None
        if folder_id:
            folder = self._validate_parent_folder(folder_id, record["criterion_code"])
            if client_id and folder["client_id"] != client_id:
                raise ValueError("Folder not found")
            if case_id and folder["case_id"] != case_id:
                raise ValueError("Folder not found")
            target_folder_id = folder["id"]
        self.conn.execute("UPDATE evidence_items SET folder_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (target_folder_id, evidence_id))
        self.conn.commit()
        updated = one(self.conn, "SELECT * FROM evidence_items WHERE id = ?", (evidence_id,))
        folders = rows(
            self.conn,
            "SELECT * FROM evidence_folders WHERE client_id = ? AND case_id = ? AND criterion_code = ?",
            (record["client_id"], record["case_id"], record["criterion_code"]),
        )
        return self._decorate_file(updated, folders)

    def archive_evidence(self, evidence_id: str, reason: str = "member_delete", client_id: str | None = None, case_id: str | None = None) -> dict:
        record = one(self.conn, "SELECT * FROM evidence_items WHERE id = ?", (evidence_id,))
        if not record:
            return {"ok": False, "status": "failed", "error": "Evidence not found"}
        if client_id and record["client_id"] != client_id:
            return {"ok": False, "status": "failed", "error": "Evidence not found"}
        if case_id and record["case_id"] != case_id:
            return {"ok": False, "status": "failed", "error": "Evidence not found"}
        if record["status"] == "archived":
            return {"ok": True, "status": "archived", "message": "Evidence was already removed."}
        return self.archive_evidence_record(record, reason)

    def archive_evidence_record(self, record: dict, reason: str) -> dict:
        try:
            if record.get("drive_file_id"):
                if not self.storage.google_drive:
                    raise GoogleDriveConfigError("Storage provider is not configured.")
                archive_path = archive_path_for(record["drive_path"] or record["drive_mirror_path"])
                archive_folder_id = self.storage.google_drive.ensure_folder_path(archive_path.split("/")[:-1])
                moved = self.storage.google_drive.move_file_to_folder(record["drive_file_id"], archive_folder_id)
                archive_web_url = moved.get("webViewLink", record.get("drive_web_url", ""))
                updated_local_path = str(record.get("local_path", "")).strip()
                updated_drive_mirror_path = str(record.get("drive_mirror_path", "")).strip()
                updated_drive_path = archive_path
            else:
                archived = self.storage.archive(record)
                archive_path = archived["archive_path"]
                archive_web_url = archived.get("drive_web_url", record.get("drive_web_url", ""))
                updated_local_path = archived.get("local_path", str(record.get("local_path", "")).strip())
                updated_drive_mirror_path = archived.get("drive_mirror_path", str(record.get("drive_mirror_path", "")).strip())
                updated_drive_path = archived.get("drive_path", str(record.get("drive_path", "")).strip())
        except (GoogleDriveConfigError, GoogleDriveUploadError, ClientError, OSError) as exc:
            return {"ok": False, "status": "failed", "error": str(exc)}

        self.conn.execute(
            """
            UPDATE evidence_items
            SET status = 'archived',
                local_path = ?,
                drive_mirror_path = ?,
                drive_path = ?,
                archive_path = ?,
                archived_at = CURRENT_TIMESTAMP,
                archive_reason = ?,
                drive_web_url = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (updated_local_path, updated_drive_mirror_path, updated_drive_path, archive_path, reason, archive_web_url, record["id"]),
        )
        self.conn.execute("DELETE FROM evidence_search WHERE evidence_id = ?", (record["id"],))
        self.conn.commit()
        self.record_operational_event(
            "evidence_archived",
            status="success",
            portal="system",
            client_id=record["client_id"],
            case_id=record["case_id"],
            endpoint="/storage/archive",
            message="Evidence moved to archive storage.",
            metadata={
                "evidence_id": record["id"],
                "reason": reason,
                "archive_path": archive_path,
                "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            actor_role="system",
            actor_key="storage",
        )
        return {
            "ok": True,
            "status": "archived",
            "message": "Evidence removed from active list.",
            "evidence_id": record["id"],
            "archive_path": archive_path,
        }

    def _assistant_name(self, role: str) -> str:
        return "Ascend Navigator"

    def _assistant_scope_check(self, question: str, thread: list[dict], context: dict) -> dict:
        thread_text = " ".join(str(item.get("content", "")) for item in (thread or [])[-4:])
        text = f"{question} {thread_text}".strip().lower()
        allowed_terms = (
            "ascend",
            "portal",
            "product suite",
            "member",
            "client",
            "profile",
            "profile builder",
            "builder",
            "attorney",
            "leader",
            "admin",
            "case",
            "dossier",
            "petition",
            "eb1",
            "eb-1",
            "eb1a",
            "immigration",
            "visa",
            "filing",
            "rfe",
            "evidence",
            "criterion",
            "criteria",
            "critical role",
            "original contribution",
            "recommendation",
            "endeavor",
            "document",
            "folder",
            "s3",
            "bucket",
            "intake",
            "review",
            "readiness",
            "assignment",
            "assign",
            "invite",
            "registration",
            "register",
            "password",
            "login",
            "message",
            "support",
            "issue portal",
            "system health",
            "cost explorer",
            "dashboard",
            "timeline",
            "task",
            "workflow",
            "backlog",
            "roadmap",
        )
        contextual_terms = (
            "next",
            "focus",
            "review",
            "first",
            "best",
            "strongest",
            "weakest",
            "gap",
            "risk",
            "ready",
            "improve",
            "summarize",
            "summary",
            "status",
            "progress",
            "priority",
            "action",
            "follow up",
            "queue",
            "work on",
            "what should",
            "which",
            "where",
            "why",
        )
        out_of_scope_terms = (
            "weather",
            "sports",
            "stock price",
            "crypto",
            "bitcoin",
            "recipe",
            "restaurant",
            "movie",
            "celebrity",
            "capital of",
            "president of",
            "translate",
            "write code",
            "debug code",
            "homework",
            "math problem",
            "tell me a joke",
            "poem",
            "song",
            "travel itinerary",
        )
        if any(term in text for term in allowed_terms):
            return {"allowed": True, "reason": "ascend_scope_term"}
        if any(term in text for term in out_of_scope_terms):
            return {"allowed": False, "reason": "generic_world_knowledge"}
        if context.get("member") and any(term in text for term in contextual_terms):
            return {"allowed": True, "reason": "selected_member_context"}
        return {"allowed": False, "reason": "missing_ascend_scope"}

    def _assistant_scope_guardrail_answer(self, role: str, context: dict) -> dict:
        member = context.get("member") or {}
        member_label = member.get("display_name") or "the selected member"
        role_label = role.replace("_", " ").title()
        summary = (
            "Ascend Navigator can help only with Ascend Product Suite work, EB1A case workflows, portal users, "
            "member profiles, evidence, assignments, petition preparation, messages, and support/navigation tasks."
        )
        return {
            "summary": f"{summary} Please ask an Ascend-related question.",
            "detailed_answer": (
                f"I cannot answer general-purpose questions outside Ascend. In the {role_label} portal, I can help with "
                f"{member_label}'s profile, evidence, criteria coverage, tasks, assignments, document storage, petition workflow, "
                "or product-suite navigation."
            ),
            "detail_prompt": "Ask about this Ascend case, evidence, assignment, petition workflow, or portal navigation.",
            "suggested_follow_up": "Ask which evidence item, profile gap, assignment, or EB1A criterion needs attention next.",
            "needs_more_detail": False,
            "response_mode": "summary",
            "references": [],
        }

    def _assistant_detail_requested(self, question: str, thread: list[dict] | None = None) -> bool:
        haystack = " ".join(
            [question or ""] + [str(item.get("content", "")) for item in (thread or [])[-4:]]
        ).lower()
        detail_tokens = (
            "detail",
            "detailed",
            "full answer",
            "full breakdown",
            "evidence trail",
            "storage link",
            "storage links",
            "reference",
            "references",
            "cite",
            "citation",
            "expand",
            "more context",
            "descriptive",
        )
        return any(token in haystack for token in detail_tokens)

    def _normalize_assistant_thread(self, thread: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for item in thread[-10:]:
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            normalized.append({"role": role, "content": content[:2000]})
        return normalized

    def _assistant_context(self, role: str, question: str, client_id: str = "", actor_email: str = "", thread: list[dict] | None = None) -> dict:
        if role == "builder":
            dashboard = self.builder_dashboard()
            roster = dashboard.get("members", [])
            selected_client_id = client_id or (roster[0]["client_id"] if roster else self.config.default_client["client_id"])
            detail = self.builder_member_detail(selected_client_id)
            member = detail["member"]
            evidence = self._assistant_evidence(member["client_id"], member["case_id"])
            metrics = {
                "readiness_score": int(member.get("readiness_score") or 0),
                "evidence_count": len(evidence),
                "open_tasks": sum(1 for item in detail.get("tasks", []) if item.get("status") == "open"),
                "member_count": len(roster),
                "opportunity_count": len(self.builder_opportunities()),
            }
            return self._compose_assistant_context(
                role,
                member,
                detail.get("profile", {}),
                detail.get("criteria", []),
                detail.get("tasks", []),
                evidence,
                metrics,
                question,
                thread or [],
                queue_summary={
                    "member_count": len(roster),
                    "active_tasks": int(dashboard.get("metrics", {}).get("active_tasks") or 0),
                    "avg_readiness": int(dashboard.get("metrics", {}).get("avg_readiness") or 0),
                },
            )
        if role == "leader":
            dashboard = self.leader_dashboard()
            roster = dashboard.get("members", [])
            selected_client_id = client_id or (roster[0]["client_id"] if roster else self.config.default_client["client_id"])
            detail = self.builder_member_detail(selected_client_id)
            member = detail["member"]
            evidence = self._assistant_evidence(member["client_id"], member["case_id"])
            metrics = {
                "readiness_score": int(member.get("readiness_score") or 0),
                "evidence_count": len(evidence),
                "open_tasks": sum(1 for item in detail.get("tasks", []) if item.get("status") == "open"),
                "member_count": len(roster),
                "registered_members": int(dashboard.get("metrics", {}).get("registered_members") or 0),
                "assigned_attorneys": int(dashboard.get("metrics", {}).get("assigned_attorneys") or 0),
            }
            return self._compose_assistant_context(
                role,
                member,
                detail.get("profile", {}),
                detail.get("criteria", []),
                detail.get("tasks", []),
                evidence,
                metrics,
                question,
                thread or [],
                queue_summary={
                    "member_count": len(roster),
                    "builders": len(dashboard.get("builders", [])),
                    "attorneys": len(dashboard.get("attorneys", [])),
                    "domain_summary": dashboard.get("domain_summary", [])[:6],
                },
            )
        roster = self.attorney_members(actor_email)
        selected_client_id = client_id or (roster[0]["client_id"] if roster else self.config.default_client["client_id"])
        detail = self.attorney_member_detail(selected_client_id, actor_email)
        member = detail["member"]
        evidence = self.attorney_member_evidence(member["client_id"], actor_role="attorney", actor_email=actor_email)
        metrics = {
            "readiness_score": int(member.get("readiness_score") or 0),
            "evidence_count": len(evidence),
            "open_tasks": sum(1 for item in detail.get("tasks", []) if item.get("status") == "open"),
            "member_count": len(roster),
        }
        return self._compose_assistant_context(
            role,
            member,
            detail.get("profile", {}),
            detail.get("criteria", []),
            detail.get("tasks", []),
            evidence,
            metrics,
            question,
            thread or [],
            queue_summary={"member_count": len(roster)},
        )

    def _compose_assistant_context(
        self,
        role: str,
        member: dict,
        profile: dict,
        criteria: list[dict],
        tasks: list[dict],
        evidence: list[dict],
        metrics: dict,
        question: str,
        thread: list[dict],
        queue_summary: dict | None = None,
    ) -> dict:
        strengths = [f"{item['name']} ({int(item.get('evidence_count') or 0)})" for item in criteria if int(item.get("evidence_count") or 0) > 0][:4]
        gaps = [item["name"] for item in criteria if int(item.get("evidence_count") or 0) == 0][:4]
        next_steps = [item.get("title", "") for item in tasks if item.get("status") == "open" and item.get("title", "")]
        if not next_steps and gaps:
            next_steps.append(f"add stronger supporting evidence for {gaps[0]}")
        retrieved_documents = self._assistant_document_matches(question, thread, evidence)
        context = {
            "role": role,
            "member": {
                "client_id": member.get("client_id", ""),
                "case_id": member.get("case_id", ""),
                "display_name": member.get("display_name", ""),
                "status": member.get("status", ""),
            },
            "profile": {
                "preferred_name": profile.get("preferred_name", ""),
                "primary_field": profile.get("primary_field", ""),
                "current_title": profile.get("current_title", ""),
                "current_employer": profile.get("current_employer", ""),
                "industry_domain": profile.get("industry_domain", ""),
                "biography": profile.get("biography", ""),
                "proposed_final_merits_summary": profile.get("proposed_final_merits_summary", ""),
            },
            "metrics": metrics,
            "strengths": strengths,
            "gaps": gaps,
            "next_steps": next_steps[:4],
            "tasks": [
                {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "status": item.get("status", ""),
                    "criterion_code": item.get("criterion_code", ""),
                    "due_date": item.get("due_date", ""),
                }
                for item in tasks[:8]
            ],
            "evidence": [
                {
                    "title": item.get("title", ""),
                    "file_name": item.get("file_name", ""),
                    "criterion_code": item.get("criterion_code", ""),
                    "document_type": item.get("document_type", ""),
                    "folder_path": item.get("folder_path", ""),
                    "summary": item.get("ai_summary", "") or item.get("description", ""),
                    "drive_web_url": item.get("drive_web_url", ""),
                    "created_at": item.get("created_at", ""),
                }
                for item in evidence[:10]
            ],
            "queue_summary": queue_summary or {},
            "retrieved_documents": retrieved_documents,
        }
        context["references"] = self._assistant_references(retrieved_documents or evidence)
        return context

    def _assistant_evidence(self, client_id: str, case_id: str) -> list[dict]:
        folders = self._folders_for_case(client_id, case_id)
        evidence_rows = rows(
            self.conn,
            """
            SELECT *
            FROM evidence_items
            WHERE client_id = ? AND case_id = ? AND status != 'archived'
            ORDER BY created_at DESC
            """,
            (client_id, case_id),
        )
        return [self._decorate_file(item, folders) for item in evidence_rows]

    def _assistant_references(self, evidence: list[dict]) -> list[dict]:
        references: list[dict] = []
        for index, item in enumerate(evidence[:6], start=1):
            folder_label = item.get("folder_path", "") or "Secure evidence storage"
            open_url = item.get("open_url", "") or item.get("drive_web_url", "")
            references.append(
                {
                    "id": f"ref_{index}",
                    "title": item.get("title", "") or item.get("file_name", f"Reference {index}"),
                    "label": item.get("file_name", f"Reference {index}"),
                    "location": folder_label,
                    "summary": item.get("ai_summary", "") or item.get("description", ""),
                    "excerpt": item.get("excerpt", ""),
                    "document_type": item.get("document_type", "Other"),
                    "criterion_name": item.get("criterion_code", ""),
                    "created_at": item.get("created_at", ""),
                    "url": open_url if open_url.startswith(("https://", "http://")) else "",
                }
            )
        return references

    def _drive_folder_parts_for_record(self, record: dict) -> list[str]:
        for key in ("local_path", "drive_path", "drive_mirror_path"):
            raw_path = str(record.get(key, "")).strip()
            if not raw_path:
                continue
            parts = list(Path(raw_path).parts)
            if "clients" in parts:
                start = parts.index("clients")
                relative = parts[start:]
                if len(relative) >= 2:
                    return relative[:-1]
        return []

    def _ensure_drive_link(self, record: dict) -> dict:
        updated = dict(record)
        drive = self.storage.google_drive
        existing_url = str(updated.get("drive_web_url", "")).strip()
        existing_file_id = str(updated.get("drive_file_id", "")).strip()
        if existing_file_id and not existing_url and drive:
            existing_url = drive.build_file_url(existing_file_id)
            self.conn.execute("UPDATE evidence_items SET drive_web_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (existing_url, updated["id"]))
            self.conn.commit()
            updated["drive_web_url"] = existing_url
        if existing_url or not drive or not drive.enabled:
            return updated
        source_path = Path(str(updated.get("local_path", "")).strip() or str(updated.get("drive_path", "")).strip() or str(updated.get("drive_mirror_path", "")).strip())
        if not source_path.exists() or not source_path.is_file():
            return updated
        folder_parts = self._drive_folder_parts_for_record(updated)
        if not folder_parts:
            return updated
        try:
            parent_id = drive.ensure_folder_path(folder_parts)
            uploaded = drive.upload_file(parent_id, source_path, str(updated.get("file_name", "")).strip() or source_path.name)
        except (GoogleDriveConfigError, GoogleDriveUploadError, OSError):
            return updated
        drive_file_id = str(uploaded.get("id", "")).strip()
        drive_web_url = str(uploaded.get("webViewLink", "")).strip() or (drive.build_file_url(drive_file_id) if drive_file_id else "")
        self.conn.execute(
            "UPDATE evidence_items SET drive_file_id = ?, drive_web_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (drive_file_id, drive_web_url, updated["id"]),
        )
        self.conn.commit()
        updated["drive_file_id"] = drive_file_id
        updated["drive_web_url"] = drive_web_url
        return updated

    def _assistant_document_matches(self, question: str, thread: list[dict], evidence: list[dict]) -> list[dict]:
        if not evidence:
            return []
        query = self._assistant_query_text(question, thread)
        scored: list[tuple[int, dict]] = []
        for item in evidence:
            excerpt = self._assistant_read_document_excerpt(item)
            enriched = dict(item)
            enriched["excerpt"] = excerpt
            haystack = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("file_name", "")),
                    str(item.get("criterion_code", "")),
                    str(item.get("document_type", "")),
                    str(item.get("folder_path", "")),
                    str(item.get("ai_summary", "") or item.get("description", "")),
                    excerpt,
                ]
            )
            score = self._assistant_text_score(query, haystack)
            if excerpt:
                score += 1
            scored.append((score, enriched))
        scored.sort(key=lambda entry: (entry[0], str(entry[1].get("created_at", ""))), reverse=True)
        selected = [item for score, item in scored if score > 0][:4]
        if selected:
            return selected
        fallback = []
        for item in evidence[:3]:
            enriched = dict(item)
            enriched["excerpt"] = self._assistant_read_document_excerpt(item)
            fallback.append(enriched)
        return fallback

    def _assistant_query_text(self, question: str, thread: list[dict]) -> str:
        parts = [question.strip()]
        for item in thread[-4:]:
            content = str(item.get("content", "")).strip()
            if content:
                parts.append(content)
        return " ".join(parts)

    def _assistant_text_score(self, query: str, haystack: str) -> int:
        query_tokens = self._assistant_tokens(query)
        haystack_lower = haystack.lower()
        score = 0
        for token in query_tokens:
            if token in haystack_lower:
                score += 3 if len(token) > 6 else 2
        phrase = query.strip().lower()
        if phrase and len(phrase) > 12 and phrase in haystack_lower:
            score += 4
        return score

    def _assistant_tokens(self, value: str) -> list[str]:
        stop_words = {
            "the", "and", "for", "with", "that", "this", "from", "into", "what", "which", "should", "about",
            "their", "there", "have", "has", "are", "your", "case", "member", "selected", "answer", "detail",
        }
        tokens = [token for token in re.findall(r"[a-z0-9_]+", value.lower()) if len(token) > 2 and token not in stop_words]
        seen: list[str] = []
        for token in tokens:
            if token not in seen:
                seen.append(token)
        return seen

    def _assistant_read_document_excerpt(self, item: dict) -> str:
        for key in ("local_path", "drive_path"):
            raw_path = str(item.get(key, "")).strip()
            if not raw_path:
                continue
            path = Path(raw_path)
            if not path.exists() or not path.is_file():
                continue
            try:
                file_bytes = path.read_bytes()
            except OSError:
                continue
            excerpt = extract_document_excerpt(path.name, mimetypes.guess_type(path.name)[0] or "application/octet-stream", file_bytes).strip()
            if excerpt:
                return excerpt[:2400]
        return ""

    def _validate_parent_folder(self, parent_id: str, criterion_code: str) -> dict:
        parent = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (parent_id,))
        if not parent or parent["criterion_code"] != criterion_code:
            raise ValueError("Folder not found")
        return parent

    def _is_descendant(self, folder_id: str, candidate_parent_id: str | None) -> bool:
        current = candidate_parent_id
        while current:
            folder = one(self.conn, "SELECT id, parent_id FROM evidence_folders WHERE id = ?", (current,))
            if not folder:
                return False
            if folder["id"] == folder_id:
                return True
            current = folder["parent_id"]
        return False

    def _decorate_folder(self, folder: dict, all_folders: list[dict]) -> dict:
        decorated = dict(folder)
        decorated["path"] = self._folder_path(folder["id"], all_folders)
        return decorated

    def _decorate_file(self, item: dict, folders: list[dict]) -> dict:
        decorated = self._ensure_drive_link(item)
        if item.get("folder_id"):
            decorated["folder_path"] = self._folder_path(item["folder_id"], folders)
        else:
            decorated["folder_path"] = ""
        decorated["document_type"] = self._normalize_document_type(
            decorated.get("document_type", "Other"),
            decorated.get("file_name", ""),
            decorated.get("description", ""),
        )
        drive_url = str(decorated.get("drive_web_url", "")).strip()
        local_url = ""
        local_path = str(decorated.get("local_path", "")).strip() or str(decorated.get("drive_path", "")).strip()
        if local_path:
            try:
                local_url = Path(local_path).resolve().as_uri()
            except ValueError:
                local_url = ""
        decorated["open_url"] = drive_url or local_url
        return decorated

    def _member_case(self, client_id: str = "") -> dict:
        resolved_client_id = client_id.strip() or self.config.default_client["client_id"]
        member = one(
            self.conn,
            """
            SELECT c.id AS client_id, c.member_uid, c.display_name, cs.id AS case_id, cs.readiness_score, cs.status
            FROM clients c
            JOIN cases cs ON cs.client_id = c.id
            WHERE c.id = ?
            """,
            (resolved_client_id,),
        )
        if not member:
            raise ValueError("Member not found")
        return member

    def _assert_member_batch_access(self, client_id: str, actor_role: str = "attorney", actor_email: str = "") -> None:
        role = actor_role.strip().lower() or "attorney"
        if role == "leader":
            return
        if role != "attorney":
            raise ValueError("Unsupported actor role")
        self.attorney_member_detail(client_id, actor_email)

    def _folders_for_case(self, client_id: str, case_id: str, criterion_code: str = "") -> list[dict]:
        if criterion_code:
            return rows(
                self.conn,
                """
                SELECT *
                FROM evidence_folders
                WHERE client_id = ? AND case_id = ? AND criterion_code = ?
                ORDER BY LOWER(name), created_at
                """,
                (client_id, case_id, criterion_code),
            )
        return rows(
            self.conn,
            """
            SELECT *
            FROM evidence_folders
            WHERE client_id = ? AND case_id = ?
            ORDER BY criterion_code, LOWER(name), created_at
            """,
            (client_id, case_id),
        )

    def _folder_lookup_by_criterion(self, folders: list[dict]) -> dict[str, list[dict]]:
        lookup: dict[str, list[dict]] = {}
        for folder in folders:
            lookup.setdefault(folder["criterion_code"], []).append(folder)
        return lookup

    def _suggest_folder_name(self, zip_path: PurePosixPath) -> str:
        parent = zip_path.parent
        if not parent or str(parent) in {".", ""}:
            return ""
        parts = [part.strip() for part in parent.parts if part.strip() not in {"", "."}]
        return parts[-1][:120] if parts else ""

    def _resolve_batch_folder_defaults(self, folder_lookup: dict[str, list[dict]], criterion_code: str, suggested_folder_name: str) -> tuple[str, str, str]:
        if not suggested_folder_name:
            return "", "root", ""
        folders = folder_lookup.get(criterion_code, [])
        match = next((folder for folder in folders if folder["name"].strip().lower() == suggested_folder_name.strip().lower()), None)
        if match:
            return match["id"], "existing", ""
        return "", "create", suggested_folder_name.strip()

    def _find_duplicate_evidence(self, client_id: str, case_id: str, criterion_code: str, file_name: str) -> dict | None:
        cleaned_file_name = safe_file_name(file_name)
        return one(
            self.conn,
            """
            SELECT *
            FROM evidence_items
            WHERE client_id = ? AND case_id = ? AND criterion_code = ?
              AND file_name = ? AND status != 'archived'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (client_id, case_id, criterion_code, cleaned_file_name),
        )

    def _batch_member_context(self, detail: dict, extra_context: str) -> str:
        profile = detail.get("profile") or {}
        member = detail.get("member") or {}
        parts = [
            f"Member: {member.get('display_name', 'Member')}",
            f"Field: {profile.get('primary_field', '')}",
            f"Title: {profile.get('current_title', '')}",
            f"Employer: {profile.get('current_employer', '')}",
            f"Bio: {profile.get('biography', '')}",
            f"Attorney note: {extra_context.strip()}",
        ]
        return "\n".join(part for part in parts if part and not part.endswith(": "))

    def _serialize_batch_session(self, session: dict, items: list[dict], folders: list[dict], detail: dict, member: dict) -> dict:
        folder_lookup = self._folder_lookup_by_criterion(folders)
        decorated_folders = {
            code: [self._decorate_folder(folder, folder_lookup.get(code, [])) for folder in bucket]
            for code, bucket in folder_lookup.items()
        }
        criteria_lookup = {item["code"]: item["name"] for item in self.criteria()}
        counts = {"ready": 0, "pending": 0, "skipped": 0, "committed": 0}
        serialized_items = []
        for item in items:
            review_status = item.get("review_status", "ready")
            counts[review_status] = counts.get(review_status, 0) + 1
            duplicate = None
            if item.get("duplicate_evidence_id"):
                duplicate_row = one(
                    self.conn,
                    "SELECT id, title, file_name, criterion_code FROM evidence_items WHERE id = ?",
                    (item["duplicate_evidence_id"],),
                )
                if duplicate_row:
                    duplicate = dict(duplicate_row)
            final_folder = self._final_batch_folder_label(item, decorated_folders, criteria_lookup)
            serialized_items.append(
                {
                    **dict(item),
                    "criterion_name": criteria_lookup.get(item["criterion_code"], item["criterion_code"]),
                    "duplicate": duplicate,
                    "available_folders": decorated_folders.get(item["criterion_code"], []),
                    "final_folder_label": final_folder,
                    "final_destination_label": f"{final_folder} / {item['original_file_name']}",
                }
            )
        skipped_files = json.loads(session.get("skipped_files_json") or "[]")
        return {
            "id": session["id"],
            "status": session["status"],
            "uploaded_zip_name": session["uploaded_zip_name"],
            "source_note": session.get("source_note", ""),
            "created_at": session["created_at"],
            "committed_at": session.get("committed_at"),
            "member": {
                "client_id": member["client_id"],
                "case_id": member["case_id"],
                "display_name": member["display_name"],
                "readiness_score": int(member.get("readiness_score") or 0),
                "primary_field": (detail.get("profile") or {}).get("primary_field", ""),
                "current_title": (detail.get("profile") or {}).get("current_title", ""),
            },
            "counts": {
                "items": len(serialized_items),
                "ready": counts.get("ready", 0),
                "pending": counts.get("pending", 0),
                "skipped": counts.get("skipped", 0),
                "committed": counts.get("committed", 0),
                "skipped_files": len(skipped_files),
            },
            "criteria": detail.get("criteria", []),
            "folders_by_criterion": decorated_folders,
            "skipped_files": skipped_files,
            "items": serialized_items,
        }

    def _final_batch_folder_label(self, item: dict, decorated_folders: dict[str, list[dict]], criteria_lookup: dict[str, str]) -> str:
        criterion_name = criteria_lookup.get(item["criterion_code"], item["criterion_code"])
        decision = (item.get("folder_decision") or "root").strip().lower()
        if decision == "existing":
            match = next((folder for folder in decorated_folders.get(item["criterion_code"], []) if folder["id"] == item.get("assigned_folder_id")), None)
            if match:
                return f"{criterion_name} / {match['path']}"
        if decision == "create":
            folder_name = (item.get("assigned_folder_name") or item.get("suggested_folder_name") or "").strip()
            if folder_name:
                return f"{criterion_name} / {folder_name}"
        return f"{criterion_name} / Root"

    def _materialize_batch_folder(self, session: dict, item: dict, folder_cache: dict[tuple[str, str], str]) -> str | None:
        decision = (item.get("folder_decision") or "root").strip().lower()
        if decision == "root":
            return None
        if decision == "existing":
            folder = one(self.conn, "SELECT * FROM evidence_folders WHERE id = ?", (item.get("assigned_folder_id") or "",))
            if not folder:
                raise ValueError("Chosen folder no longer exists")
            return folder["id"]
        folder_name = (item.get("assigned_folder_name") or item.get("suggested_folder_name") or "").strip()
        if not folder_name:
            return None
        cache_key = (item["criterion_code"], folder_name.lower())
        if cache_key in folder_cache:
            return folder_cache[cache_key]
        existing = one(
            self.conn,
            """
            SELECT *
            FROM evidence_folders
            WHERE client_id = ? AND case_id = ? AND criterion_code = ? AND LOWER(name) = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session["client_id"], session["case_id"], item["criterion_code"], folder_name.lower()),
        )
        if existing:
            folder_cache[cache_key] = existing["id"]
            return existing["id"]
        created = self.create_folder(item["criterion_code"], folder_name, client_id=session["client_id"], case_id=session["case_id"])
        folder_cache[cache_key] = created["id"]
        return created["id"]

    def _folder_path(self, folder_id: str, all_folders: list[dict]) -> str:
        by_id = {folder["id"]: folder for folder in all_folders}
        parts: list[str] = []
        current = by_id.get(folder_id)
        while current:
            parts.append(current["name"])
            current = by_id.get(current.get("parent_id"))
        return " / ".join(reversed(parts))

    def _planner_review_url(self, item: dict) -> str:
        if item.get("criterion_code"):
            return f"/?criterion={item['criterion_code']}"
        return ""

    def _normalize_document_type(self, document_type: str, file_name: str = "", description: str = "") -> str:
        cleaned = (document_type or "").strip()
        if cleaned in DOCUMENT_TYPES:
            return cleaned
        return infer_document_type(f"{file_name} {description}".lower())

    def _document_type_counts(self, files: list[dict]) -> list[dict]:
        counts = {label: 0 for label in DOCUMENT_TYPES}
        for item in files:
            counts[self._normalize_document_type(item.get("document_type", "Other"), item.get("file_name", ""), item.get("description", ""))] += 1
        return [{"label": label, "count": count} for label, count in counts.items() if count]

    def _ensure_default_profile(self) -> None:
        client = self.config.default_client
        existing = one(
            self.conn,
            "SELECT * FROM member_profiles WHERE client_id = ? AND case_id = ?",
            (client["client_id"], client["case_id"]),
        )
        if existing:
            if (existing.get("email") or "").strip().lower() != DEFAULT_MEMBER_EMAIL:
                self.conn.execute(
                    """
                    UPDATE member_profiles
                    SET email = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = ? AND case_id = ?
                    """,
                    (DEFAULT_MEMBER_EMAIL, client["client_id"], client["case_id"]),
                )
                self.conn.commit()
            return
        first_name, _, last_name = client["display_name"].partition(" ")
        self.conn.execute(
            """
            INSERT INTO member_profiles(client_id, case_id, first_name, last_name, preferred_name, email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                client["client_id"],
                client["case_id"],
                first_name or client["display_name"],
                last_name,
                first_name or client["display_name"],
                DEFAULT_MEMBER_EMAIL,
            ),
        )
        self.conn.commit()

    def _ensure_default_account(self) -> None:
        client = self.config.default_client
        existing = one(
            self.conn,
            "SELECT * FROM member_accounts WHERE client_id = ? AND case_id = ?",
            (client["client_id"], client["case_id"]),
        )
        if existing:
            if (existing.get("username") or "").strip().lower() != DEFAULT_MEMBER_EMAIL or (existing.get("email") or "").strip().lower() != DEFAULT_MEMBER_EMAIL:
                self.conn.execute(
                    """
                    UPDATE member_accounts
                    SET username = ?, email = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = ? AND case_id = ?
                    """,
                    (DEFAULT_MEMBER_EMAIL, DEFAULT_MEMBER_EMAIL, client["client_id"], client["case_id"]),
                )
                self.conn.commit()
            return
        profile = self.member_profile()
        account_id = f"acct_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO member_accounts(id, client_id, case_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                client["client_id"],
                client["case_id"],
                profile["email"].strip().lower(),
                profile["email"].strip().lower(),
                self._hash_password(DEFAULT_MEMBER_PASSWORD),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()

    def default_builder(self) -> dict:
        builder = one(self.conn, "SELECT * FROM profile_builders ORDER BY created_at LIMIT 1")
        if not builder:
            raise ValueError("Profile builder not found")
        return {
            "builder_id": builder["id"],
            "builder_uid": builder.get("builder_uid", 0),
            "numeric_identifier": int(builder.get("builder_uid") or 0),
            "display_name": builder["display_name"],
            "email": builder["email"],
        }

    def _ensure_default_builder(self) -> None:
        existing = one(self.conn, "SELECT id FROM profile_builders LIMIT 1")
        if existing:
            return
        builder_id = f"bld_{uuid.uuid4().hex[:12]}"
        account_id = f"bact_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            "INSERT INTO profile_builders(id, builder_uid, display_name, email) VALUES (?, ?, ?, ?)",
            (builder_id, next_numeric_identifier(self.conn, "profile_builders", "builder_uid"), "Ava Morales", "builder@ascendhsi.com"),
        )
        self.conn.execute(
            """
            INSERT INTO profile_builder_accounts(id, builder_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                account_id,
                builder_id,
                "builder@ascendhsi.com",
                "builder@ascendhsi.com",
                self._hash_password(DEFAULT_MEMBER_PASSWORD),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()

    def _ensure_default_builder_assignment(self) -> None:
        builder = self.default_builder()
        client = self.config.default_client
        existing = one(
            self.conn,
            "SELECT id FROM builder_member_assignments WHERE builder_id = ? AND client_id = ? AND case_id = ?",
            (builder["builder_id"], client["client_id"], client["case_id"]),
        )
        if existing:
            return
        self.conn.execute(
            """
            INSERT INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (f"asg_{uuid.uuid4().hex[:12]}", builder["builder_id"], client["client_id"], client["case_id"]),
        )
        self.conn.commit()

    def _ensure_default_attorneys(self) -> None:
        defaults = [
            ("Sophia Chen", "attorney@ascendhsi.com", "Technology, Pharma"),
            ("Marcus Reed", "marcus.reed@ascendhsi.com", "Healthcare, Insurance"),
            ("Priya Nair", "priya.nair@ascendhsi.com", "Technology, Healthcare"),
        ]
        for display_name, email, focus_domains in defaults:
            existing = one(self.conn, "SELECT id FROM attorneys WHERE email = ?", (email,))
            if existing:
                continue
            self.conn.execute(
                "INSERT INTO attorneys(id, attorney_uid, display_name, email, focus_domains) VALUES (?, ?, ?, ?, ?)",
                (f"att_{uuid.uuid4().hex[:12]}", next_numeric_identifier(self.conn, "attorneys", "attorney_uid"), display_name, email, focus_domains),
            )
        self.conn.commit()

    def _ensure_default_staff_accounts(self) -> None:
        accounts: list[tuple[str, str, str]] = []
        for attorney in rows(self.conn, "SELECT email FROM attorneys ORDER BY email"):
            accounts.append(("attorney", attorney["email"].strip().lower(), attorney["email"].strip().lower()))
        for user in self._system_users():
            accounts.append((user["role"], user["key"], user["email"].strip().lower()))
        for role, actor_key, email in accounts:
            existing = one(self.conn, "SELECT id FROM staff_accounts WHERE role = ? AND actor_key = ?", (role, actor_key))
            if existing:
                continue
            self.conn.execute(
                """
                INSERT INTO staff_accounts(id, staff_uid, role, actor_key, username, email, password_hash, last_password_changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (f"staff_{uuid.uuid4().hex[:12]}", next_numeric_identifier(self.conn, "staff_accounts", "staff_uid"), role, actor_key, email, email, self._hash_password(DEFAULT_MEMBER_PASSWORD)),
            )
        self.conn.commit()

    def _ensure_default_attorney_assignment(self) -> None:
        client = self.config.default_client
        existing = one(
            self.conn,
            "SELECT id FROM attorney_member_assignments WHERE client_id = ? AND case_id = ? AND status = 'active'",
            (client["client_id"], client["case_id"]),
        )
        if existing:
            return
        attorney = one(self.conn, "SELECT * FROM attorneys ORDER BY created_at LIMIT 1")
        if not attorney:
            return
        self.conn.execute(
            """
            INSERT INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            (f"aat_{uuid.uuid4().hex[:12]}", attorney["id"], client["client_id"], client["case_id"]),
        )
        self.conn.commit()

    def _ensure_default_opportunities(self) -> None:
        defaults = [
            ("judging", "Journal reviewer invitation", "Target reviewer invitations from journals or conferences and capture the invitation plus thank-you note.", "Invitation", 14),
            ("memberships", "Selective membership application", "Identify a selective association or fellowship that requires notable achievement and plan the application path.", "Acceptance or Selection", 21),
            ("published_material", "Media feature outreach", "Pitch a story or thought leadership angle that could produce published material about the member.", "Publication or Media", 30),
            ("leading_critical_role", "Speaking or panel opportunity", "Secure a visible speaking or panel role that can support leadership and distinguished-role positioning.", "Invitation", 21),
            ("awards", "Award nomination follow-up", "Track an award or recognition process and collect submission, confirmation, and outcome records.", "Confirmation Email", 21),
        ]
        for criterion_code, title, description, doc_type, due_days in defaults:
            existing = one(self.conn, "SELECT id FROM opportunity_library WHERE criterion_code = ? AND title = ?", (criterion_code, title))
            if existing:
                continue
            self.conn.execute(
                """
                INSERT INTO opportunity_library(id, criterion_code, title, description, target_evidence_type, suggested_due_days, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                (f"opp_{uuid.uuid4().hex[:12]}", criterion_code, title, description, doc_type, due_days),
            )
        self.conn.commit()

    def _builder_payload(self, account: dict) -> dict:
        builder = one(self.conn, "SELECT * FROM profile_builders WHERE id = ?", (account["builder_id"],))
        return {
            "account_id": account["id"],
            "builder_id": account["builder_id"],
            "builder_uid": builder.get("builder_uid", 0) if builder else 0,
            "numeric_identifier": int(builder.get("builder_uid") or 0) if builder else 0,
            "storage_key": self._numeric_key(builder.get("builder_uid") if builder else 0),
            "legacy_key": account["email"].strip().lower(),
            "username": account["username"],
            "email": account["email"],
            "display_name": builder["display_name"] if builder else "Profile Builder",
            "role": "builder",
            "last_login_at": account.get("last_login_at", ""),
        }

    def _criteria_started(self, case_id: str) -> int:
        result = one(
            self.conn,
            """
            SELECT COUNT(*) AS count
            FROM (
              SELECT criterion_code
              FROM evidence_items
              WHERE case_id = ? AND status != 'archived'
              GROUP BY criterion_code
            )
            """,
            (case_id,),
        )
        return result["count"] if result else 0

    def _member_momentum(self, client_id: str, case_id: str) -> str:
        recent = one(
            self.conn,
            """
            SELECT COUNT(*) AS count
            FROM evidence_items
            WHERE client_id = ? AND case_id = ? AND status != 'archived' AND created_at >= datetime('now', '-14 day')
            """,
            (client_id, case_id),
        )
        count = recent["count"] if recent else 0
        if count >= 4:
            return "Strong"
        if count >= 2:
            return "Building"
        if count >= 1:
            return "Active"
        return "Needs focus"

    def _parse_datetime(self, value: str | None) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        candidates = [normalized]
        if "T" not in normalized and " " in normalized:
            candidates.append(normalized.replace(" ", "T"))
        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
            except ValueError:
                continue
        return None

    def _serialize_datetime(self, value: datetime | None) -> str:
        return value.isoformat(timespec="seconds") if value else ""

    def _days_since(self, value: str | None) -> int:
        parsed = self._parse_datetime(value)
        if not parsed:
            return 0
        delta = datetime.utcnow() - parsed
        return max(0, delta.days)

    def _member_last_activity(self, member: dict) -> str:
        timestamps = [
            member.get("case_created_at"),
            member.get("invite_sent_at"),
            member.get("registered_at"),
            member.get("builder_assigned_at"),
            member.get("attorney_assigned_at"),
        ]
        latest_evidence = one(
            self.conn,
            "SELECT MAX(created_at) AS value FROM evidence_items WHERE client_id = ? AND case_id = ? AND status != 'archived'",
            (member["client_id"], member["case_id"]),
        )
        latest_tasks = one(
            self.conn,
            "SELECT MAX(created_at) AS value FROM tasks WHERE client_id = ? AND case_id = ?",
            (member["client_id"], member["case_id"]),
        )
        latest_ops = one(
            self.conn,
            "SELECT MAX(created_at) AS value FROM operational_events WHERE client_id = ? AND case_id = ?",
            (member["client_id"], member["case_id"]),
        )
        timestamps.extend([
            latest_evidence.get("value", "") if latest_evidence else "",
            latest_tasks.get("value", "") if latest_tasks else "",
            latest_ops.get("value", "") if latest_ops else "",
        ])
        parsed = [self._parse_datetime(item) for item in timestamps]
        latest = max((item for item in parsed if item), default=None)
        return self._serialize_datetime(latest)

    def _leader_stage_label(self, member: dict) -> str:
        status = str(member.get("status", "")).strip().lower()
        readiness = int(member.get("readiness_score") or 0)
        if status == "completed":
            return "Completed"
        if member.get("registration_status") != "registered":
            return "Invited"
        if not member.get("builder_name"):
            return "Needs builder"
        if not member.get("attorney_name"):
            return "Profile build"
        if readiness >= 80:
            return "Petition ready"
        if readiness >= 60:
            return "Attorney review"
        return "Attorney prep"

    def _leader_risk_profile(self, member: dict) -> dict:
        flags: list[str] = []
        score = 0
        readiness = int(member.get("readiness_score") or 0)
        open_tasks = int(member.get("open_task_count") or 0)
        evidence_count = int(member.get("evidence_count") or 0)
        days_since_activity = int(member.get("days_since_activity") or 0)
        registration_status = str(member.get("registration_status") or "").strip().lower()

        if registration_status != "registered":
            flags.append("Registration pending")
            score += 15
        if registration_status == "registered" and not member.get("builder_name"):
            flags.append("Builder unassigned")
            score += 35
        if readiness >= 55 and not member.get("attorney_name"):
            flags.append("Attorney handoff pending")
            score += 25
        if days_since_activity >= 14:
            flags.append("Stale activity")
            score += 25
        elif days_since_activity >= 7:
            flags.append("Watch activity")
            score += 10
        if open_tasks >= 5:
            flags.append("Task load heavy")
            score += 15
        if evidence_count <= 1 and readiness < 35:
            flags.append("Thin evidence set")
            score += 15
        if member.get("momentum") == "Needs focus":
            score += 10

        if score >= 50 or len(flags) >= 3:
            risk_level = "High"
        elif score >= 20 or flags:
            risk_level = "Moderate"
        else:
            risk_level = "Healthy"

        if "Builder unassigned" in flags:
            next_action = "Assign a builder"
        elif "Attorney handoff pending" in flags:
            next_action = "Route to an attorney"
        elif "Registration pending" in flags:
            next_action = "Nudge registration"
        elif "Stale activity" in flags:
            next_action = "Escalate to owner"
        elif "Task load heavy" in flags:
            next_action = "Reduce open task load"
        elif "Thin evidence set" in flags:
            next_action = "Push evidence-building work"
        else:
            next_action = "Keep current plan"

        owner_name = member.get("attorney_name") or member.get("builder_name") or "Leader queue"
        return {
            "risk_score": score,
            "risk_level": risk_level,
            "risk_flags": flags,
            "primary_risk": flags[0] if flags else "On track",
            "bottleneck": flags[0] if flags else "On track",
            "next_action": next_action,
            "owner_name": owner_name,
        }

    def _leader_funnel(self, members: list[dict]) -> list[dict]:
        return [
            {"label": "Invited", "count": len(members)},
            {"label": "Registered", "count": sum(1 for item in members if item.get("registration_status") == "registered")},
            {"label": "Builder Assigned", "count": sum(1 for item in members if item.get("builder_name"))},
            {"label": "Attorney Assigned", "count": sum(1 for item in members if item.get("attorney_name"))},
            {"label": "Petition Ready", "count": sum(1 for item in members if int(item.get("readiness_score") or 0) >= 80)},
            {"label": "Completed", "count": sum(1 for item in members if str(item.get("status", "")).strip().lower() == "completed")},
        ]

    def _leader_stage_summary(self, members: list[dict]) -> list[dict]:
        buckets: dict[str, dict[str, int]] = {}
        for member in members:
            bucket = buckets.setdefault(member["stage_label"], {"count": 0, "readiness_total": 0, "risk_count": 0})
            bucket["count"] += 1
            bucket["readiness_total"] += int(member.get("readiness_score") or 0)
            if member.get("risk_level") == "High":
                bucket["risk_count"] += 1
        order = {"Invited": 0, "Needs builder": 1, "Profile build": 2, "Attorney prep": 3, "Attorney review": 4, "Petition ready": 5, "Completed": 6}
        return [
            {
                "label": label,
                "count": stats["count"],
                "avg_readiness": round(stats["readiness_total"] / stats["count"]) if stats["count"] else 0,
                "risk_count": stats["risk_count"],
            }
            for label, stats in sorted(buckets.items(), key=lambda item: (order.get(item[0], 99), item[0]))
        ]

    def _leader_risk_summary(self, members: list[dict]) -> list[dict]:
        counts: dict[str, int] = {}
        for member in members:
            flags = member.get("risk_flags") or ["On track"]
            if not flags:
                flags = ["On track"]
            for flag in flags:
                counts[flag] = counts.get(flag, 0) + 1
        return [{"label": label, "count": count} for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]

    def _leader_watchlist(self, members: list[dict], limit: int = 8) -> list[dict]:
        ranked = sorted(
            members,
            key=lambda item: (
                -int(item.get("risk_score") or 0),
                -int(item.get("days_since_activity") or 0),
                int(item.get("readiness_score") or 0),
                item.get("display_name", ""),
            ),
        )
        return [
            {
                "client_id": item["client_id"],
                "display_name": item["display_name"],
                "stage_label": item["stage_label"],
                "readiness_score": int(item.get("readiness_score") or 0),
                "owner_name": item.get("owner_name", ""),
                "days_since_activity": int(item.get("days_since_activity") or 0),
                "risk_level": item.get("risk_level", "Healthy"),
                "risk_score": int(item.get("risk_score") or 0),
                "bottleneck": item.get("bottleneck", "On track"),
                "next_action": item.get("next_action", "Keep current plan"),
            }
            for item in ranked[:limit]
        ]

    def _leader_capacity_summary(self, members: list[dict], owners: list[dict], owner_key: str) -> list[dict]:
        summary = []
        for owner in owners:
            assigned = [item for item in members if item.get(owner_key) == owner.get("display_name")]
            readiness_total = sum(int(item.get("readiness_score") or 0) for item in assigned)
            open_tasks = sum(int(item.get("open_task_count") or 0) for item in assigned)
            high_risk_cases = sum(1 for item in assigned if item.get("risk_level") == "High")
            capacity_pressure = min(100, len(assigned) * 16 + high_risk_cases * 12 + open_tasks * 3)
            summary.append(
                {
                    "id": owner.get("id", ""),
                    "display_name": owner.get("display_name", ""),
                    "email": owner.get("email", ""),
                    "assigned_members": len(assigned),
                    "avg_readiness": round(readiness_total / len(assigned)) if assigned else 0,
                    "open_tasks": open_tasks,
                    "high_risk_cases": high_risk_cases,
                    "capacity_pressure": capacity_pressure,
                    "domain_mix": ", ".join(sorted({item.get("industry_domain", "Other") for item in assigned if item.get("industry_domain")})) or "No assigned domains",
                }
            )
        return sorted(summary, key=lambda item: (-item["capacity_pressure"], -item["assigned_members"], item["display_name"]))

    def _leader_activity_timeline(self, weeks: int = 6) -> list[dict]:
        def values(query: str) -> list[datetime]:
            return [parsed for row in rows(self.conn, query) if (parsed := self._parse_datetime(row.get("value")))]

        invites = values("SELECT invite_sent_at AS value FROM member_registration_invites")
        builder_assignments = values("SELECT created_at AS value FROM builder_member_assignments WHERE status = 'active'")
        attorney_assignments = values("SELECT created_at AS value FROM attorney_member_assignments WHERE status = 'active'")
        evidence_uploads = values("SELECT created_at AS value FROM evidence_items WHERE status != 'archived'")
        task_creations = values("SELECT created_at AS value FROM tasks")

        now = datetime.utcnow()
        week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        starts = [week_start - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)]
        points = []
        for start in starts:
            end = start + timedelta(days=7)
            point = {
                "label": start.strftime("%b %d"),
                "invites": sum(1 for item in invites if start <= item < end),
                "builder_assignments": sum(1 for item in builder_assignments if start <= item < end),
                "attorney_assignments": sum(1 for item in attorney_assignments if start <= item < end),
                "evidence_uploads": sum(1 for item in evidence_uploads if start <= item < end),
                "tasks_created": sum(1 for item in task_creations if start <= item < end),
            }
            point["total_activity"] = point["invites"] + point["builder_assignments"] + point["attorney_assignments"] + point["evidence_uploads"] + point["tasks_created"]
            points.append(point)
        return points

    def _leader_forecast(self, members: list[dict]) -> list[dict]:
        return [
            {
                "label": "Next 30 days",
                "count": sum(1 for item in members if int(item.get("readiness_score") or 0) >= 80),
                "detail": "Cases already at petition-ready range.",
            },
            {
                "label": "Next 60 days",
                "count": sum(1 for item in members if int(item.get("readiness_score") or 0) >= 60),
                "detail": "Cases with attorney-review level readiness.",
            },
            {
                "label": "Next 90 days",
                "count": sum(1 for item in members if int(item.get("readiness_score") or 0) >= 45),
                "detail": "Cases with enough momentum to enter legal review soon.",
            },
        ]

    def _member_payload(self, account: dict) -> dict:
        profile = one(
            self.conn,
            """
            SELECT mp.*, c.member_uid
            FROM member_profiles mp
            JOIN clients c ON c.id = mp.client_id
            WHERE mp.client_id = ? AND mp.case_id = ?
            """,
            (account["client_id"], account["case_id"]),
        ) or self.member_profile()
        return {
            "account_id": account["id"],
            "client_id": account["client_id"],
            "case_id": account["case_id"],
            "member_uid": profile.get("member_uid", 0),
            "numeric_identifier": int(profile.get("member_uid") or 0),
            "storage_key": self._numeric_key(profile.get("member_uid", 0)),
            "legacy_key": account["client_id"],
            "username": account["username"],
            "email": account["email"],
            "display_name": profile.get("preferred_name") or profile.get("first_name") or self.config.default_client["display_name"],
            "profile_confirmed": bool(profile.get("profile_confirmed")),
            "role": "member",
            "last_login_at": account.get("last_login_at", ""),
        }

    def member_registration_invite(self, token: str) -> dict:
        token = token.strip()
        if not token:
            raise ValueError("Registration token is required")
        invite = one(
            self.conn,
            """
            SELECT invite.*, c.display_name, mp.first_name, mp.last_name, mp.current_title, mp.current_employer
            FROM member_registration_invites invite
            JOIN clients c ON c.id = invite.client_id
            LEFT JOIN member_profiles mp ON mp.client_id = invite.client_id AND mp.case_id = invite.case_id
            WHERE invite.token_hash = ?
            """,
            (self._invite_token_hash(token),),
        )
        if not invite:
            raise ValueError("Registration link is invalid")
        now = datetime.utcnow().isoformat(timespec="seconds")
        if invite.get("token_expires_at") and invite["token_expires_at"] < now:
            raise ValueError("Registration link has expired")
        return {
            "ok": True,
            "invite_id": invite["id"],
            "display_name": invite.get("display_name", ""),
            "first_name": invite.get("first_name", ""),
            "last_name": invite.get("last_name", ""),
            "email": invite.get("email", ""),
            "current_title": invite.get("current_title", ""),
            "current_employer": invite.get("current_employer", ""),
            "status": invite.get("status", "invited"),
            "token_expires_at": invite.get("token_expires_at", ""),
        }

    def register_invited_member(self, token: str, password: str, phone: str = "", audit_context: dict | None = None) -> dict:
        token = token.strip()
        if not token:
            raise ValueError("Registration token is required")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters")
        invite = one(self.conn, "SELECT * FROM member_registration_invites WHERE token_hash = ?", (self._invite_token_hash(token),))
        if not invite:
            raise ValueError("Registration link is invalid")
        now = datetime.utcnow().isoformat(timespec="seconds")
        if invite.get("token_expires_at") and invite["token_expires_at"] < now:
            raise ValueError("Registration link has expired")
        if invite.get("status") == "registered":
            raise ValueError("This registration link has already been used")
        account = one(
            self.conn,
            "SELECT * FROM member_accounts WHERE client_id = ? AND case_id = ? AND LOWER(email) = ?",
            (invite["client_id"], invite["case_id"], invite["email"].strip().lower()),
        )
        if not account:
            raise ValueError("Member account was not found for this invitation")
        self.conn.execute(
            """
            UPDATE member_accounts
            SET password_hash = ?,
                last_password_changed_at = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (self._hash_password(password), datetime.utcnow().isoformat(timespec="seconds"), account["id"]),
        )
        if phone.strip():
            self.conn.execute(
                "UPDATE member_profiles SET phone = ?, updated_at = CURRENT_TIMESTAMP WHERE client_id = ? AND case_id = ?",
                (phone.strip(), invite["client_id"], invite["case_id"]),
            )
        self.conn.execute(
            """
            UPDATE member_registration_invites
            SET status = 'registered',
                registered_at = COALESCE(registered_at, CURRENT_TIMESTAMP)
            WHERE id = ?
            """,
            (invite["id"],),
        )
        token_value = f"sess_{secrets.token_urlsafe(24)}"
        self.conn.execute("INSERT INTO member_sessions(token, account_id) VALUES (?, ?)", (token_value, account["id"]))
        logged_at, metadata = self._mark_account_login("member_accounts", account["id"], audit_context)
        self.conn.commit()
        metadata["last_login_at"] = logged_at
        self.record_operational_event(
            "member_registration",
            status="success",
            portal="member",
            client_id=invite["client_id"],
            case_id=invite["case_id"],
            endpoint="/api/member/register",
            message="Member completed invited registration.",
            metadata=metadata,
            actor_role="member",
            actor_key=invite["client_id"],
        )
        account = one(self.conn, "SELECT * FROM member_accounts WHERE id = ?", (account["id"],)) or account
        return {"ok": True, "status": "registered", "token": token_value, "member": self._member_payload(account), "next_page": "profile"}

    def login_member(self, username: str, password: str, audit_context: dict | None = None) -> dict:
        username = username.strip().lower()
        metadata = self._login_audit_metadata(audit_context)
        if not username or not password:
            self.record_operational_event("member_auth", status="error", portal="member", endpoint="/api/auth/login", error_code="missing_credentials", message="Member username or password missing.", metadata=metadata, actor_role="member", actor_key=username)
            raise ValueError("username and password are required")
        account = one(
            self.conn,
            """
            SELECT *
            FROM member_accounts
            WHERE LOWER(username) = ? OR LOWER(email) = ?
            """,
            (username, username),
        )
        if not account or not self._verify_password(password, account["password_hash"]):
            self.record_operational_event("member_auth", status="error", portal="member", endpoint="/api/auth/login", error_code="invalid_credentials", message="Member login failed.", metadata=metadata, actor_role="member", actor_key=username)
            raise ValueError("Invalid credentials")
        token = f"sess_{secrets.token_urlsafe(24)}"
        self.conn.execute("INSERT INTO member_sessions(token, account_id) VALUES (?, ?)", (token, account["id"]))
        logged_at, metadata = self._mark_account_login("member_accounts", account["id"], audit_context)
        self.conn.execute(
            """
            UPDATE member_registration_invites
            SET status = 'registered',
                registered_at = COALESCE(registered_at, CURRENT_TIMESTAMP)
            WHERE client_id = ? AND case_id = ? AND LOWER(email) = ?
            """,
            (account["client_id"], account["case_id"], account["email"].strip().lower()),
        )
        self.conn.commit()
        metadata["last_login_at"] = logged_at
        self.record_operational_event("member_auth", status="success", portal="member", client_id=account["client_id"], case_id=account["case_id"], endpoint="/api/auth/login", message="Member login succeeded.", metadata=metadata, actor_role="member", actor_key=account["client_id"])
        account = one(self.conn, "SELECT * FROM member_accounts WHERE id = ?", (account["id"],)) or account
        return {"token": token, "member": self._member_payload(account)}

    def _infer_domain(self, item: dict) -> str:
        text = " ".join(
            [
                str(item.get("industry_domain", "")),
                str(item.get("primary_field", "")),
                str(item.get("current_employer", "")),
                str(item.get("current_title", "")),
            ]
        ).lower()
        if any(keyword in text for keyword in ["health", "clinical", "hospital", "medical", "patient"]):
            return "Healthcare"
        if any(keyword in text for keyword in ["insurance", "payer", "claims", "underwriting"]):
            return "Insurance"
        if any(keyword in text for keyword in ["pharma", "biotech", "drug", "therapeutic", "life sciences"]):
            return "Pharma"
        if any(keyword in text for keyword in ["software", "ai", "technology", "cloud", "data", "engineering", "cyber"]):
            return "Technology"
        return "Other"

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()
        return f"{salt}${digest}"

    def _verify_password(self, password: str, stored: str) -> bool:
        try:
            salt, digest = stored.split("$", 1)
        except ValueError:
            return False
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=16384, r=8, p=1).hex()
        return secrets.compare_digest(candidate, digest)

    def _profile_completion_score(self, profile: dict) -> int:
        tracked_fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "country_of_citizenship",
            "country_of_residence",
            "current_title",
            "current_employer",
            "primary_field",
            "specialization",
            "highest_degree",
            "biography",
            "top_achievements",
            "awards_summary",
            "memberships_summary",
            "publications_summary",
            "judging_summary",
            "original_contributions_summary",
            "leading_roles_summary",
            "media_summary",
            "salary_summary",
        ]
        completed = sum(1 for field in tracked_fields if str(profile.get(field, "")).strip())
        if int(profile.get("critical_role_project_count") or 0) > 0:
            completed += 1
        if int(profile.get("original_contribution_entry_count") or 0) > 0:
            completed += 1
        return round((completed / (len(tracked_fields) + 2)) * 100)


def archive_path_for(original_path: str) -> str:
    cleaned = original_path.strip("/")
    if cleaned.startswith("archive/"):
        return cleaned
    return f"archive/{cleaned}"

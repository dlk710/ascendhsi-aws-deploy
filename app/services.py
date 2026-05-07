import mimetypes
import hashlib
import json
import re
import secrets
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
import uuid

PLANNER_STATUSES = {"planned", "in_progress", "completed", "blocked"}
DEFAULT_MEMBER_PASSWORD = "Ascend123!"
DEFAULT_MEMBER_EMAIL = "vas@ascendhsi.com"

from app.config import load_app_config, load_openai_config, load_storage_config
from app.db import connect, initialize, one, rows, seed_default_case
from app.openai_client import DOCUMENT_TYPES, OpenAIService, extract_document_excerpt, infer_document_type
from app.s3_storage import S3ConfigError, S3StorageClient, S3StorageError
from app.storage import EvidenceStorage, safe_file_name


class DuplicateEvidenceError(RuntimeError):
    def __init__(self, duplicate: dict):
        super().__init__("A file with this name already exists in this category.")
        self.duplicate = duplicate


class EvidenceService:
    def __init__(self):
        self.config = load_app_config()
        self.storage_config = load_storage_config()
        self.openai = OpenAIService(load_openai_config())
        self.storage = EvidenceStorage(
            self.config.upload_root,
            self.config.drive_mirror_root,
            S3StorageClient(self.storage_config),
        )
        self.conn = connect(self.config)
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

    def _database_driver(self) -> str:
        return getattr(self.conn, "driver", "sqlite")

    def _insert_ignore(self, sqlite_sql: str, postgres_sql: str, params: tuple) -> None:
        self.conn.execute(postgres_sql if self._database_driver() == "postgres" else sqlite_sql, params)

    def _stable_id(self, prefix: str, value: str) -> str:
        return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"

    def _actor_identity(self, role: str, actor_email: str = "", actor_client_id: str = "") -> dict:
        role = role.strip().lower()
        actor_email = actor_email.strip().lower()
        actor_client_id = actor_client_id.strip()
        if role == "member":
            client_id = actor_client_id or self.config.default_client["client_id"]
            profile = one(self.conn, "SELECT * FROM member_profiles WHERE client_id = ?", (client_id,))
            if not profile:
                raise ValueError("Member not found")
            return {
                "role": "member",
                "key": client_id,
                "client_id": client_id,
                "name": (profile.get("preferred_name") or profile.get("first_name") or profile.get("email") or "Member").strip(),
                "email": profile.get("email", "").strip().lower(),
            }
        if role == "builder":
            account = one(self.conn, "SELECT * FROM profile_builder_accounts WHERE LOWER(email) = ? OR LOWER(username) = ?", (actor_email, actor_email))
            if not account:
                raise ValueError("Profile builder not found")
            payload = self._builder_payload(account)
            return {
                "role": "builder",
                "key": payload["email"].strip().lower(),
                "builder_id": payload["builder_id"],
                "name": payload["display_name"],
                "email": payload["email"].strip().lower(),
            }
        if role == "attorney":
            attorney = one(self.conn, "SELECT * FROM attorneys WHERE LOWER(email) = ?", (actor_email,))
            if not attorney:
                raise ValueError("Attorney not found")
            return {
                "role": "attorney",
                "key": attorney["email"].strip().lower(),
                "attorney_id": attorney["id"],
                "name": attorney["display_name"],
                "email": attorney["email"].strip().lower(),
            }
        if role in {"leader", "admin"}:
            user = next((item for item in self._system_users() if item["role"] == role and (not actor_email or item["email"] == actor_email)), None)
            if not user:
                raise ValueError(f"{role.title()} not found")
            return {
                "role": role,
                "key": user["key"],
                "name": user["name"],
                "email": user["email"],
            }
        raise ValueError("Unsupported actor role")

    def _recipient_options(self, actor: dict) -> list[dict]:
        options: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add(role: str, key: str, name: str, email: str = "", detail: str = "") -> None:
            ident = (role, key)
            if not key or ident in seen:
                return
            seen.add(ident)
            options.append({"role": role, "key": key, "name": name, "email": email, "detail": detail})

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
                add("builder", builder["email"].strip().lower(), builder["display_name"], builder["email"], "Assigned profile builder")
            if attorney:
                add("attorney", attorney["email"].strip().lower(), attorney["display_name"], attorney["email"], "Assigned attorney")
            admin = next(item for item in self._system_users() if item["role"] == "admin")
            add("admin", admin["key"], admin["name"], admin["email"], "Operations support")
            return options

        if actor["role"] == "builder":
            members = rows(
                self.conn,
                """
                SELECT c.id AS client_id, c.display_name, mp.email
                FROM builder_member_assignments a
                JOIN clients c ON c.id = a.client_id
                LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = a.case_id
                WHERE a.builder_id = ? AND a.status = 'active'
                ORDER BY c.display_name
                """,
                (actor["builder_id"],),
            )
            for item in members:
                add("member", item["client_id"], item["display_name"], item.get("email", ""), "Assigned member")
            for system in self._system_users():
                add(system["role"], system["key"], system["name"], system["email"], "Operations")
            return options

        if actor["role"] == "attorney":
            members = rows(
                self.conn,
                """
                SELECT c.id AS client_id, c.display_name, mp.email
                FROM attorney_member_assignments a
                JOIN clients c ON c.id = a.client_id
                LEFT JOIN member_profiles mp ON mp.client_id = c.id AND mp.case_id = a.case_id
                WHERE a.attorney_id = ? AND a.status = 'active'
                ORDER BY c.display_name
                """,
                (actor["attorney_id"],),
            )
            for item in members:
                add("member", item["client_id"], item["display_name"], item.get("email", ""), "Assigned member")
            for system in self._system_users():
                add(system["role"], system["key"], system["name"], system["email"], "Operations")
            return options

        if actor["role"] in {"leader", "admin"}:
            members = rows(self.conn, "SELECT c.id AS client_id, c.display_name, mp.email FROM clients c LEFT JOIN member_profiles mp ON mp.client_id = c.id ORDER BY c.display_name")
            builders = rows(self.conn, "SELECT display_name, email FROM profile_builders ORDER BY display_name")
            attorneys = rows(self.conn, "SELECT display_name, email FROM attorneys ORDER BY display_name")
            for item in members:
                add("member", item["client_id"], item["display_name"], item.get("email", ""), "Member")
            for item in builders:
                add("builder", item["email"].strip().lower(), item["display_name"], item["email"], "Profile builder")
            for item in attorneys:
                add("attorney", item["email"].strip().lower(), item["display_name"], item["email"], "Attorney")
            for system in self._system_users():
                add(system["role"], system["key"], system["name"], system["email"], "Operations")
            return [item for item in options if not (item["role"] == actor["role"] and item["key"] == actor["key"])]

        return options

    def message_recipient_options(self, actor_role: str, actor_email: str = "", actor_client_id: str = "") -> list[dict]:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        return self._recipient_options(actor)

    def message_center(self, actor_role: str, actor_email: str = "", actor_client_id: str = "") -> dict:
        actor = self._actor_identity(actor_role, actor_email, actor_client_id)
        visible_messages = rows(
            self.conn,
            """
            SELECT *
            FROM messages
            WHERE (
              (recipient_role = ? AND recipient_key = ? AND deleted_by_recipient = 0)
              OR
              (sender_role = ? AND sender_key = ? AND deleted_by_sender = 0)
            )
            ORDER BY created_at DESC
            """,
            (actor["role"], actor["key"], actor["role"], actor["key"]),
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
            if item["recipient_role"] == actor["role"] and item["recipient_key"] == actor["key"] and not item["is_read"]:
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
                    if not (item["sender_role"] == actor["role"] and item["sender_key"] == actor["key"])
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
                    if not (item["recipient_role"] == actor["role"] and item["recipient_key"] == actor["key"])
                ),
                None,
            )
            if not thread_participant:
                raise ValueError("Could not resolve thread recipient")
            recipient = thread_participant
            cleaned_subject = thread_messages[0]["subject"]
        else:
            recipient = next((item for item in recipients if item["role"] == recipient_role.strip().lower() and item["key"] == recipient_key.strip()), None)
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
        message = one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,))
        if not message:
            raise ValueError("Message not found")
        if message["recipient_role"] != actor["role"] or message["recipient_key"] != actor["key"]:
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
        message = one(self.conn, "SELECT * FROM messages WHERE id = ?", (message_id,))
        if not message:
            raise ValueError("Message not found")
        if message["sender_role"] == actor["role"] and message["sender_key"] == actor["key"]:
            self.conn.execute("UPDATE messages SET deleted_by_sender = 1 WHERE id = ?", (message_id,))
        elif message["recipient_role"] == actor["role"] and message["recipient_key"] == actor["key"]:
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

    def _login_audit_metadata(self, audit_context: dict | None = None) -> dict:
        context = audit_context or {}
        return {
            "client_ip": str(context.get("client_ip", "") or "")[:120],
            "forwarded_for": str(context.get("forwarded_for", "") or "")[:240],
            "user_agent": str(context.get("user_agent", "") or "")[:500],
        }

    def _mark_account_login(self, table: str, account_id: str, audit_context: dict | None = None) -> tuple[str, dict]:
        metadata = self._login_audit_metadata(audit_context)
        logged_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
        drive_file_id = str(decorated.get("drive_file_id", "")).strip()
        if drive_file_id and self.storage.object_storage and self.storage.object_storage.enabled:
            try:
                drive_url = self.storage.object_storage.build_file_url(drive_file_id)
                decorated["drive_web_url"] = drive_url
            except S3StorageError:
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

        object_storage = self.storage.object_storage
        if object_storage and object_storage.enabled:
            try:
                parent_id = object_storage.ensure_folder_path(["support", "tickets", ticket_number, attachment_id])
                uploaded = object_storage.upload_bytes(parent_id, cleaned_file_name, file_bytes, normalized_content_type)
                drive_file_id = str(uploaded.get("id", "")).strip()
                drive_web_url = str(uploaded.get("webViewLink", "")).strip() or (object_storage.build_file_url(drive_file_id) if drive_file_id else "")
                return {
                    "id": attachment_id,
                    "file_name": cleaned_file_name,
                    "description": description.strip(),
                    "content_type": normalized_content_type,
                    "local_path": "",
                    "drive_path": drive_path,
                    "drive_file_id": drive_file_id,
                    "drive_web_url": drive_web_url,
                    "storage_provider": "s3",
                    "storage_class": str(uploaded.get("storageClass", "")).strip(),
                }
            except (S3ConfigError, S3StorageError):
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
            "storage_provider": "local",
            "storage_class": "",
        }

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
        database_backend = self.config.database_backend
        if database_backend == "postgresql":
            database_name = "PostgreSQL"
            database_detail = "Configured through ASCEND_DATABASE_URL."
        elif database_backend == "external":
            database_name = "External Database"
            database_detail = "Configured through ASCEND_DATABASE_URL."
        else:
            database_name = "SQLite"
            database_detail = str(self.config.database_path)
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
            "portal_health": [
                {"name": "Member Portal", "status": "online", "detail": "React portal available on port 3001."},
                {"name": "Profile Builder Portal", "status": "online", "detail": "Assigned-member workflow available."},
                {"name": "Leader Portal", "status": "online", "detail": "Executive and assignment review available."},
                {"name": "Attorney Portal", "status": "online", "detail": "Full dossier preview available."},
                {"name": "Admin Portal", "status": "online", "detail": "Operational monitoring available."},
                {"name": "FastAPI", "status": "online", "detail": "Serving on port 8000."},
                {"name": database_name, "status": "healthy", "detail": database_detail},
                {
                    "name": "Amazon S3",
                    "status": "healthy" if self.storage.object_storage and self.storage.object_storage.enabled else "degraded",
                    "detail": self.storage.object_storage.bucket_name() if self.storage.object_storage else "not configured",
                },
                {"name": "OpenAI", "status": "healthy" if self.openai.enabled else "degraded", "detail": self.openai.config.get("model", "not configured")},
            ],
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
                "Check Amazon S3 and OpenAI health before escalating",
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
        case = one(self.conn, "SELECT * FROM cases WHERE id = ?", (client["case_id"],))
        if not case:
            raise ValueError("Member case not found")
        profile = one(self.conn, "SELECT preferred_name, first_name, last_name FROM member_profiles WHERE client_id = ? AND case_id = ?", (client["client_id"], client["case_id"])) or {}
        if not client["display_name"]:
            client["display_name"] = (profile.get("preferred_name") or " ".join(filter(None, [profile.get("first_name", ""), profile.get("last_name", "")])) or "Member").strip()
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
            GROUP BY c.code, c.name, c.display_order
            ORDER BY c.display_order, c.name
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
            "storage": {
                "provider": self.storage_config.get("provider", "s3"),
                "bucket": self.storage.object_storage.bucket_name() if self.storage.object_storage else "",
                "archive_bucket": self.storage.object_storage.archive_bucket_name() if self.storage.object_storage else "",
                "active_storage_class": self.storage_config.get("active_storage_class", ""),
                "archive_storage_class": self.storage_config.get("archive_storage_class", ""),
            },
        }

    def criteria(self) -> list[dict]:
        return rows(self.conn, "SELECT code, name, description FROM criteria ORDER BY display_order, name")

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
            "username": account["username"],
            "email": account["email"].strip().lower(),
            "display_name": actor["name"],
            "role": role,
            "last_login_at": account.get("last_login_at", ""),
        }

    def login_staff(self, username: str, password: str, audit_context: dict | None = None) -> dict:
        username = username.strip().lower()
        metadata = self._login_audit_metadata(audit_context)
        if not username or not password:
            self.record_operational_event("staff_auth", status="error", portal="staff", endpoint="/api/staff/auth/login", error_code="missing_credentials", message="Staff username or password missing.", metadata=metadata, actor_key=username)
            raise ValueError("username and password are required")
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
        token = f"ssess_{secrets.token_urlsafe(24)}"
        self.conn.execute("INSERT INTO staff_sessions(token, account_id) VALUES (?, ?)", (token, account["id"]))
        logged_at, metadata = self._mark_account_login("staff_accounts", account["id"], audit_context)
        self.conn.commit()
        metadata["last_login_at"] = logged_at
        role = account["role"].strip().lower()
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
                   c.display_name,
                   cs.id AS case_id,
                   cs.readiness_score,
                   cs.status,
                   cs.created_at AS case_created_at,
                   mp.industry_domain,
                   mp.primary_field,
                   mp.current_title,
                   mp.current_employer,
                   invite.status AS registration_status,
                   invite.invite_sent_at,
                   invite.registered_at,
                   pb.display_name AS builder_name,
                   pb.email AS builder_email,
                   bma.created_at AS builder_assigned_at,
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
        builders = rows(
            self.conn,
            """
            SELECT pb.id, pb.display_name, pb.email,
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
            SELECT att.id, att.display_name, att.email, att.focus_domains,
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
        }

    def builder_members(self) -> list[dict]:
        builder = self.default_builder()
        members = rows(
            self.conn,
            """
            SELECT c.id AS client_id,
                   c.display_name,
                   cs.id AS case_id,
                   cs.readiness_score,
                   cs.status,
                   (SELECT COUNT(*) FROM evidence_items e WHERE e.client_id = c.id AND e.case_id = cs.id AND e.status != 'archived') AS evidence_count,
                   (SELECT COUNT(*) FROM tasks t WHERE t.client_id = c.id AND t.case_id = cs.id AND t.status = 'open') AS open_task_count,
                   mp.primary_field,
                   mp.current_title,
                   mp.current_employer
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
        return members

    def builder_member_detail(self, client_id: str) -> dict:
        member = one(
            self.conn,
            """
            SELECT c.id AS client_id, c.display_name, cs.id AS case_id, cs.readiness_score, cs.status
            FROM clients c
            JOIN cases cs ON cs.client_id = c.id
            WHERE c.id = ?
            """,
            (client_id,),
        )
        if not member:
            raise ValueError("Member not found")
        profile = one(self.conn, "SELECT * FROM member_profiles WHERE client_id = ? AND case_id = ?", (member["client_id"], member["case_id"])) or {}
        criteria = rows(
            self.conn,
            """
            SELECT c.code, c.name, COUNT(e.id) AS evidence_count
            FROM criteria c
            LEFT JOIN evidence_items e ON e.criterion_code = c.code AND e.client_id = ? AND e.case_id = ? AND e.status != 'archived'
            GROUP BY c.code, c.name, c.display_order
            ORDER BY c.display_order, c.name
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
        return {"member": member, "profile": profile, "criteria": criteria, "tasks": tasks, "evidence": evidence}

    def builder_opportunities(self) -> list[dict]:
        return rows(
            self.conn,
            """
            SELECT o.*, c.name AS criterion_name
            FROM opportunity_library o
            JOIN criteria c ON c.code = o.criterion_code
            WHERE o.status = 'active'
            ORDER BY c.display_order, LOWER(o.title)
            """
        )

    def leader_invite_member(
        self,
        first_name: str,
        last_name: str,
        email: str,
        industry_domain: str = "",
        primary_field: str = "",
        current_title: str = "",
        current_employer: str = "",
    ) -> dict:
        first_name = first_name.strip()
        last_name = last_name.strip()
        email = email.strip().lower()
        if not first_name or not last_name or not email:
            raise ValueError("first_name, last_name, and email are required")
        existing_account = one(self.conn, "SELECT * FROM member_accounts WHERE LOWER(email) = ? OR LOWER(username) = ?", (email, email))
        existing_profile = one(self.conn, "SELECT * FROM member_profiles WHERE LOWER(email) = ?", (email,))
        if existing_account or existing_profile:
            raise ValueError("A member with this email already exists")
        client_id = f"client_{uuid.uuid4().hex[:10]}"
        case_id = f"case_{uuid.uuid4().hex[:10]}"
        account_id = f"acct_{uuid.uuid4().hex[:12]}"
        invite_id = f"inv_{uuid.uuid4().hex[:12]}"
        display_name = f"{first_name} {last_name}".strip()
        domain = industry_domain.strip() or self._infer_domain({"industry_domain": "", "primary_field": primary_field, "current_employer": current_employer})
        self.conn.execute("INSERT INTO clients(id, display_name) VALUES (?, ?)", (client_id, display_name))
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
                self._hash_password(DEFAULT_MEMBER_PASSWORD),
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        self.conn.execute(
            """
            INSERT INTO member_registration_invites(id, client_id, case_id, email, invited_by, status, notes)
            VALUES (?, ?, ?, ?, 'leader', 'invited', ?)
            """,
            (invite_id, client_id, case_id, email, "Invite created in local seed data. Email delivery can be connected later."),
        )
        self.conn.commit()
        self.record_operational_event(
            "member_invite",
            status="success",
            portal="leader",
            client_id=client_id,
            case_id=case_id,
            endpoint="/api/leader/invites",
            message=f"Leader invited {display_name}.",
            metadata={"email": email, "industry_domain": domain},
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
                   c.display_name,
                   cs.id AS case_id,
                   cs.readiness_score,
                   cs.status,
                   (SELECT COUNT(*) FROM evidence_items e WHERE e.client_id = c.id AND e.case_id = cs.id AND e.status != 'archived') AS evidence_count,
                   (SELECT COUNT(*) FROM tasks t WHERE t.client_id = c.id AND t.case_id = cs.id AND t.status = 'open') AS open_task_count,
                   mp.primary_field,
                   mp.current_title,
                   mp.current_employer
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
            WHERE sender_key = ? OR recipient_key = ? OR sender_name = ? OR recipient_name = ?
            ORDER BY created_at DESC
            LIMIT 12
            """,
            (member["client_id"], member["client_id"], member["display_name"], member["display_name"]),
        )
        criteria_lookup = {item["code"]: item["name"] for item in detail.get("criteria", [])}
        payload = {
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
                {
                    "code": item["code"],
                    "name": item["name"],
                    "evidence_count": int(item.get("evidence_count") or 0),
                }
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
            tokens = [token.strip().lower() for token in search.split() if token.strip()]
            if not tokens:
                return rows(self.conn, "SELECT * FROM evidence_items WHERE status != 'archived' ORDER BY created_at DESC")
            token_clause = " AND ".join(
                [
                    "("
                    "LOWER(COALESCE(s.title, '')) LIKE ? OR "
                    "LOWER(COALESCE(s.description, '')) LIKE ? OR "
                    "LOWER(COALESCE(s.file_name, '')) LIKE ? OR "
                    "LOWER(COALESCE(s.ai_summary, '')) LIKE ?"
                    ")"
                    for _ in tokens
                ]
            )
            params: list[str] = []
            for token in tokens:
                like = f"%{token}%"
                params.extend([like, like, like, like])
            return rows(
                self.conn,
                f"""
                SELECT e.*
                FROM evidence_search s
                JOIN evidence_items e ON e.id = s.evidence_id
                WHERE e.status != 'archived' AND {token_clause}
                ORDER BY e.created_at DESC
                """,
                tuple(params),
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
            stored = self.storage.store(client_id, case_id, criterion_code, file_name, Path(tmp.name))

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
        self.conn.execute("UPDATE evidence_items SET folder_id = ? WHERE folder_id = ? AND status != 'archived'", (parent_id, folder_id))
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
        self.conn.execute("UPDATE evidence_items SET folder_id = ? WHERE id = ?", (target_folder_id, evidence_id))
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
        archive_path = archive_path_for(record["drive_path"] or record["drive_mirror_path"])
        try:
            if record.get("drive_file_id"):
                if not self.storage.object_storage:
                    raise S3ConfigError("Storage provider is not configured.")
                archive_folder_id = self.storage.object_storage.ensure_folder_path(archive_path.split("/")[:-1])
                moved = self.storage.object_storage.move_file_to_folder(record["drive_file_id"], archive_folder_id)
                archive_web_url = moved.get("webViewLink", record.get("drive_web_url", ""))
            else:
                archive_web_url = record.get("drive_web_url", "")
        except (S3ConfigError, S3StorageError) as exc:
            return {"ok": False, "status": "failed", "error": str(exc)}

        self.conn.execute(
            """
            UPDATE evidence_items
            SET status = 'archived',
                archive_path = ?,
                archived_at = CURRENT_TIMESTAMP,
                archive_reason = ?,
                drive_web_url = ?
            WHERE id = ?
            """,
            (archive_path, reason, archive_web_url, record["id"]),
        )
        self.conn.execute("DELETE FROM evidence_search WHERE evidence_id = ?", (record["id"],))
        self.conn.commit()
        return {
            "ok": True,
            "status": "archived",
            "message": "Evidence removed from active list.",
            "evidence_id": record["id"],
            "archive_path": archive_path,
        }

    def _assistant_name(self, role: str) -> str:
        return "Ascend Navigator"

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
            local_path = item.get("drive_path", "") or item.get("local_path", "")
            local_url = ""
            if local_path:
                try:
                    local_url = Path(local_path).resolve().as_uri()
                except ValueError:
                    local_url = ""
            references.append(
                {
                    "id": f"ref_{index}",
                    "title": item.get("title", "") or item.get("file_name", f"Reference {index}"),
                    "label": item.get("file_name", f"Reference {index}"),
                    "location": item.get("folder_path", "") or item.get("drive_path", "") or "Root",
                    "summary": item.get("ai_summary", "") or item.get("description", ""),
                    "excerpt": item.get("excerpt", ""),
                    "document_type": item.get("document_type", "Other"),
                    "criterion_name": item.get("criterion_code", ""),
                    "created_at": item.get("created_at", ""),
                    "url": item.get("open_url", "") or item.get("drive_web_url", "") or local_url,
                }
            )
        return references

    def _storage_folder_parts_for_record(self, record: dict) -> list[str]:
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

    def _ensure_storage_link(self, record: dict) -> dict:
        updated = dict(record)
        object_storage = self.storage.object_storage
        existing_file_id = str(updated.get("drive_file_id", "")).strip()
        if existing_file_id and object_storage and object_storage.enabled:
            try:
                updated["drive_web_url"] = object_storage.build_file_url(existing_file_id)
            except S3StorageError:
                pass
            return updated
        existing_url = str(updated.get("drive_web_url", "")).strip()
        if existing_url or not object_storage or not object_storage.enabled:
            return updated
        source_path = Path(str(updated.get("local_path", "")).strip() or str(updated.get("drive_path", "")).strip() or str(updated.get("drive_mirror_path", "")).strip())
        if not source_path.exists() or not source_path.is_file():
            return updated
        folder_parts = self._storage_folder_parts_for_record(updated)
        if not folder_parts:
            return updated
        try:
            parent_id = object_storage.ensure_folder_path(folder_parts)
            uploaded = object_storage.upload_file(parent_id, source_path, str(updated.get("file_name", "")).strip() or source_path.name)
        except (S3ConfigError, S3StorageError, OSError):
            return updated
        drive_file_id = str(uploaded.get("id", "")).strip()
        drive_web_url = str(uploaded.get("webViewLink", "")).strip() or (object_storage.build_file_url(drive_file_id) if drive_file_id else "")
        self.conn.execute(
            "UPDATE evidence_items SET drive_file_id = ?, drive_web_url = ? WHERE id = ?",
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
        decorated = self._ensure_storage_link(item)
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
            SELECT c.id AS client_id, c.display_name, cs.id AS case_id, cs.readiness_score, cs.status
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
        self._insert_ignore(
            """
            INSERT OR IGNORE INTO member_profiles(client_id, case_id, first_name, last_name, preferred_name, email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            """
            INSERT INTO member_profiles(client_id, case_id, first_name, last_name, preferred_name, email)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
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
        account_id = self._stable_id("acct", f"{client['client_id']}:{client['case_id']}")
        self._insert_ignore(
            """
            INSERT OR IGNORE INTO member_accounts(id, client_id, case_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            """
            INSERT INTO member_accounts(id, client_id, case_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
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
            "display_name": builder["display_name"],
            "email": builder["email"],
        }

    def _ensure_default_builder(self) -> None:
        builder = one(self.conn, "SELECT * FROM profile_builders ORDER BY created_at LIMIT 1")
        if not builder:
            builder_id = self._stable_id("bld", "builder@ascendhsi.com")
            self._insert_ignore(
                "INSERT OR IGNORE INTO profile_builders(id, display_name, email) VALUES (?, ?, ?)",
                "INSERT INTO profile_builders(id, display_name, email) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                (builder_id, "Ava Morales", "builder@ascendhsi.com"),
            )
            builder = one(self.conn, "SELECT * FROM profile_builders WHERE id = ?", (builder_id,)) or self.default_builder()
        account = one(self.conn, "SELECT id FROM profile_builder_accounts WHERE username = ?", ("builder@ascendhsi.com",))
        if account:
            self.conn.commit()
            return
        account_id = self._stable_id("bact", "builder@ascendhsi.com")
        self._insert_ignore(
            """
            INSERT OR IGNORE INTO profile_builder_accounts(id, builder_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            """
            INSERT INTO profile_builder_accounts(id, builder_id, username, email, password_hash, last_password_changed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                account_id,
                builder["id"],
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
        assignment_id = self._stable_id("asg", f"{builder['builder_id']}:{client['client_id']}:{client['case_id']}")
        self._insert_ignore(
            """
            INSERT OR IGNORE INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            """
            INSERT INTO builder_member_assignments(id, builder_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT DO NOTHING
            """,
            (assignment_id, builder["builder_id"], client["client_id"], client["case_id"]),
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
            attorney_id = self._stable_id("att", email.strip().lower())
            self._insert_ignore(
                "INSERT OR IGNORE INTO attorneys(id, display_name, email, focus_domains) VALUES (?, ?, ?, ?)",
                "INSERT INTO attorneys(id, display_name, email, focus_domains) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (attorney_id, display_name, email, focus_domains),
            )
        self.conn.commit()

    def _ensure_default_staff_accounts(self) -> None:
        accounts: list[tuple[str, str, str]] = []
        for attorney in rows(self.conn, "SELECT email FROM attorneys ORDER BY email"):
            accounts.append(("attorney", attorney["email"].strip().lower(), attorney["email"].strip().lower()))
        for user in self._system_users():
            accounts.append((user["role"], user["key"], user["email"].strip().lower()))
        for role, actor_key, email in accounts:
            existing = one(
                self.conn,
                "SELECT id FROM staff_accounts WHERE username = ? OR (role = ? AND actor_key = ?)",
                (email, role, actor_key),
            )
            if existing:
                continue
            staff_id = self._stable_id("staff", f"{role}:{actor_key}")
            self._insert_ignore(
                """
                INSERT OR IGNORE INTO staff_accounts(id, role, actor_key, username, email, password_hash, last_password_changed_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                """
                INSERT INTO staff_accounts(id, role, actor_key, username, email, password_hash, last_password_changed_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT DO NOTHING
                """,
                (staff_id, role, actor_key, email, email, self._hash_password(DEFAULT_MEMBER_PASSWORD)),
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
        assignment_id = self._stable_id("aat", f"{attorney['id']}:{client['client_id']}:{client['case_id']}")
        self._insert_ignore(
            """
            INSERT OR IGNORE INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            """,
            """
            INSERT INTO attorney_member_assignments(id, attorney_id, client_id, case_id, status)
            VALUES (?, ?, ?, ?, 'active')
            ON CONFLICT DO NOTHING
            """,
            (assignment_id, attorney["id"], client["client_id"], client["case_id"]),
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
            opportunity_id = self._stable_id("opp", f"{criterion_code}:{title}")
            self._insert_ignore(
                """
                INSERT OR IGNORE INTO opportunity_library(id, criterion_code, title, description, target_evidence_type, suggested_due_days, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                """,
                """
                INSERT INTO opportunity_library(id, criterion_code, title, description, target_evidence_type, suggested_due_days, status)
                VALUES (?, ?, ?, ?, ?, ?, 'active')
                ON CONFLICT DO NOTHING
                """,
                (opportunity_id, criterion_code, title, description, doc_type, due_days),
            )
        self.conn.commit()

    def _builder_payload(self, account: dict) -> dict:
        builder = one(self.conn, "SELECT * FROM profile_builders WHERE id = ?", (account["builder_id"],))
        return {
            "account_id": account["id"],
            "builder_id": account["builder_id"],
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
            "SELECT * FROM member_profiles WHERE client_id = ? AND case_id = ?",
            (account["client_id"], account["case_id"]),
        ) or self.member_profile()
        return {
            "account_id": account["id"],
            "client_id": account["client_id"],
            "case_id": account["case_id"],
            "username": account["username"],
            "email": account["email"],
            "display_name": profile.get("preferred_name") or profile.get("first_name") or self.config.default_client["display_name"],
            "profile_confirmed": bool(profile.get("profile_confirmed")),
            "role": "member",
            "last_login_at": account.get("last_login_at", ""),
        }

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
        return round((completed / len(tracked_fields)) * 100)


def archive_path_for(original_path: str) -> str:
    cleaned = original_path.strip("/")
    if cleaned.startswith("archive/"):
        return cleaned
    return f"archive/{cleaned}"

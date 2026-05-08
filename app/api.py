import json

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_cors_origins
from app.s3_storage import S3ConfigError, S3StorageError
from app.services import DuplicateEvidenceError, EvidenceService


app = FastAPI(
    title="Ascend HSI CaseOS API",
    version="0.2.0",
    description="FastAPI service for the Ascend role-based EB1A product suite.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def service() -> EvidenceService:
    return EvidenceService()


@app.get("/")
def root() -> dict:
    return {
        "ok": True,
        "service": "ascend-suite-api",
        "message": "Ascend API is running. This endpoint is the backend API origin, not the product suite web UI.",
        "endpoints": {
            "health": "/health",
            "readiness": "/ready",
            "docs": "/docs",
            "openapi": "/openapi.json",
        },
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "ascend-suite-api"}


@app.get("/ready")
def ready() -> dict:
    try:
        dashboard = service().admin_operational_dashboard()
    except Exception as exc:  # pragma: no cover - defensive readiness guard
        raise HTTPException(status_code=503, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc
    storage_health = next((item for item in dashboard.get("portal_health", []) if item.get("name") == "Amazon S3"), {})
    return {
        "ok": True,
        "service": "ascend-suite-api",
        "storage": storage_health,
        "openai": next((item for item in dashboard.get("portal_health", []) if item.get("name") == "OpenAI"), {}),
    }


@app.post("/api/marketing/leads/visa-compass")
def capture_visa_compass_lead(request: Request, payload: dict = Body(...)) -> dict:
    try:
        return service().capture_marketing_lead(
            lead_source="visa_compass",
            campaign="Ascend Visa Compass",
            email=str(payload.get("email", "")),
            phone=str(payload.get("phone", "")),
            name=str(payload.get("name", "")),
            source_url=str(payload.get("source_url", "")),
            answers=payload.get("answers") if isinstance(payload.get("answers"), dict) else {},
            result=payload.get("result") if isinstance(payload.get("result"), dict) else {},
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            audit_context=_login_audit_context(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


def bearer_token(authorization: str | None = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": "Authorization required"})
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": "Invalid authorization header"})
    return token.strip()


def optional_bearer_token(authorization: str = Header(alias="Authorization", default="")) -> str:
    return authorization.removeprefix("Bearer ").strip()


def _auth_error(error: str, status_code: int = 401) -> None:
    raise HTTPException(status_code=status_code, detail={"ok": False, "status": "failed", "error": error})


def optional_member_user(token: str = "") -> dict | None:
    parsed = token.removeprefix("Bearer ").strip()
    if not parsed:
        return None
    try:
        return service().member_session(parsed)
    except ValueError as exc:
        _auth_error(str(exc))
    return None


def require_member_user(authorization: str | None = Header(None)) -> dict:
    parsed = bearer_token(authorization)
    try:
        return service().member_session(parsed)
    except ValueError as exc:
        _auth_error(str(exc))
    return {}


def require_builder_user(authorization: str | None = Header(None)) -> dict:
    parsed = bearer_token(authorization)
    try:
        return service().builder_session(parsed)
    except ValueError as exc:
        _auth_error(str(exc))
    return {}


def require_staff_role(expected_roles: set[str], authorization: str | None = Header(None)) -> dict:
    parsed = bearer_token(authorization)
    try:
        user = service().staff_session(parsed)
    except ValueError as exc:
        _auth_error(str(exc))
    role = str(user.get("role", "")).strip().lower()
    if role not in expected_roles:
        _auth_error("Insufficient permissions")
    return user


def require_leader_user(authorization: str | None = Header(None)) -> dict:
    return require_staff_role({"leader"}, authorization)


def require_attorney_user(authorization: str | None = Header(None)) -> dict:
    return require_staff_role({"attorney"}, authorization)


def require_legal_staff_user(authorization: str | None = Header(None)) -> dict:
    return require_staff_role({"attorney", "leader"}, authorization)


def require_admin_user(authorization: str | None = Header(None)) -> dict:
    return require_staff_role({"admin"}, authorization)


def _login_audit_context(request: Request) -> dict:
    return {
        "client_ip": request.client.host if request.client else "",
        "forwarded_for": request.headers.get("x-forwarded-for", ""),
        "user_agent": request.headers.get("user-agent", ""),
    }


@app.post("/api/auth/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)) -> dict:
    try:
        return service().login_member(username, password, _login_audit_context(request))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/builder/auth/login")
def builder_login(request: Request, username: str = Form(...), password: str = Form(...)) -> dict:
    try:
        return service().login_builder(username, password, _login_audit_context(request))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/staff/auth/login")
def staff_login(request: Request, username: str = Form(...), password: str = Form(...), portal_role: str = Form("")) -> dict:
    try:
        return service().login_staff(username, password, _login_audit_context(request), portal_role)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/auth/me")
def auth_me(token: str = Header(alias="Authorization", default="")) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().member_session(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/builder/auth/me")
def builder_auth_me(token: str = Header(alias="Authorization", default="")) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().builder_session(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/staff/auth/me")
def staff_auth_me(token: str = Header(alias="Authorization", default="")) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().staff_session(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/auth/change-password")
def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    token: str = Header(alias="Authorization", default=""),
) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().change_member_password(parsed, current_password, new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400 if "password" in str(exc).lower() else 401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/builder/auth/change-password")
def builder_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    token: str = Header(alias="Authorization", default=""),
) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().change_builder_password(parsed, current_password, new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400 if "password" in str(exc).lower() else 401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/staff/auth/change-password")
def staff_change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    token: str = Header(alias="Authorization", default=""),
) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().change_staff_password(parsed, current_password, new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400 if "password" in str(exc).lower() else 401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/auth/logout")
def logout(token: str = Header(alias="Authorization", default="")) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().logout_member(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/builder/auth/logout")
def builder_logout(token: str = Header(alias="Authorization", default="")) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().logout_builder(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/staff/auth/logout")
def staff_logout(token: str = Header(alias="Authorization", default="")) -> dict:
    parsed = token.removeprefix("Bearer ").strip()
    try:
        return service().logout_staff(parsed)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/builder/dashboard")
def builder_dashboard(_builder_user: dict = Depends(require_builder_user)) -> dict:
    return service().builder_dashboard()


@app.get("/api/leader/dashboard")
def leader_dashboard(_leader_user: dict = Depends(require_leader_user)) -> dict:
    return service().leader_dashboard()


@app.post("/api/leader/invites")
def leader_invite_member(
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    industry_domain: str = Form(""),
    primary_field: str = Form(""),
    current_title: str = Form(""),
    current_employer: str = Form(""),
    builder_id: str = Form(""),
    attorney_id: str = Form(""),
    _leader_user: dict = Depends(require_leader_user),
) -> dict:
    try:
        return service().leader_invite_member(first_name, last_name, email, industry_domain, primary_field, current_title, current_employer, builder_id, attorney_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/leader/members/{client_id}/builder-assignment")
def leader_assign_builder(client_id: str, builder_id: str = Form(...), _leader_user: dict = Depends(require_leader_user)) -> dict:
    try:
        return service().leader_assign_builder(client_id, builder_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/leader/members/{client_id}/attorney-assignment")
def leader_assign_attorney(client_id: str, attorney_id: str = Form(...), _leader_user: dict = Depends(require_leader_user)) -> dict:
    try:
        return service().leader_assign_attorney(client_id, attorney_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/leader/product-backlog")
def leader_product_backlog(_leader_user: dict = Depends(require_leader_user)) -> dict:
    return service().product_feature_backlog()


@app.post("/api/leader/product-backlog")
async def create_leader_product_backlog_item(
    title: str = Form(...),
    request_type: str = Form("enhancement"),
    target_portals: str = Form(""),
    priority: str = Form("P2"),
    business_value: str = Form(""),
    description: str = Form(...),
    acceptance_criteria: str = Form(""),
    requested_by: str = Form(""),
    actor_email: str = Form(""),
    screenshots: list[UploadFile] | None = File(None),
    _leader_user: dict = Depends(require_leader_user),
) -> dict:
    try:
        attachments = []
        for upload in screenshots or []:
            content = await upload.read()
            attachments.append({"file_name": upload.filename, "content_type": upload.content_type, "bytes": content})
        return service().create_product_feature_request(
            actor_email=actor_email or _leader_user.get("email", ""),
            title=title,
            request_type=request_type,
            target_portals=target_portals,
            priority=priority,
            business_value=business_value,
            description=description,
            acceptance_criteria=acceptance_criteria,
            requested_by=requested_by,
            attachments=attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/leader/product-backlog/{request_id}")
def update_leader_product_backlog_item(
    request_id: str,
    priority: str = Form(""),
    status: str = Form(""),
    actor_email: str = Form(""),
    _leader_user: dict = Depends(require_leader_user),
) -> dict:
    try:
        return service().update_product_feature_request(request_id, priority=priority, status=status, actor_email=actor_email or _leader_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/admin/operations")
def admin_operations(_admin_user: dict = Depends(require_admin_user)) -> dict:
    return service().admin_operational_dashboard()


@app.get("/api/admin/issue-log")
def admin_issue_log(_admin_user: dict = Depends(require_admin_user)) -> dict:
    return service().issue_log_backlog()


@app.post("/api/admin/issue-log")
def create_admin_issue_log(
    title: str = Form(...),
    portal: str = Form(...),
    section: str = Form(...),
    priority: str = Form("P2"),
    status: str = Form("open"),
    description: str = Form(...),
    reported_by: str = Form(""),
    actor_email: str = Form(""),
    _admin_user: dict = Depends(require_admin_user),
) -> dict:
    try:
        return service().create_issue_log(
            actor_email=actor_email,
            title=title,
            portal=portal,
            section=section,
            priority=priority,
            status=status,
            description=description,
            reported_by=reported_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/admin/issue-log/{bug_id}")
def update_admin_issue_log(
    bug_id: str,
    priority: str = Form(""),
    status: str = Form(""),
    actor_email: str = Form(""),
    _admin_user: dict = Depends(require_admin_user),
) -> dict:
    try:
        return service().update_issue_log(bug_id, priority=priority, status=status, actor_email=actor_email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/admin/issue-log/{bug_id}")
def remove_admin_issue_log(
    bug_id: str,
    actor_email: str = Form(""),
    _admin_user: dict = Depends(require_admin_user),
) -> dict:
    try:
        return service().remove_issue_log(bug_id, actor_email=actor_email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/admin/costs")
def admin_costs(_admin_user: dict = Depends(require_admin_user)) -> dict:
    return service().admin_cost_dashboard()


@app.post("/api/admin/costs/refresh")
def admin_costs_refresh(_admin_user: dict = Depends(require_admin_user)) -> dict:
    return service().refresh_admin_cost_dashboard()


@app.get("/api/attorney/petition-generator")
def attorney_petition_generator(client_id: str = "", _attorney_user: dict = Depends(require_attorney_user)) -> dict:
    try:
        return service().attorney_petition_generator(client_id, attorney_email=_attorney_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/petition-acceleration")
def petition_acceleration(client_id: str = "", actor_role: str = "attorney", actor_email: str = "", _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        role = _legal_user.get("role", actor_role)
        email = _legal_user.get("email", actor_email)
        return service().petition_acceleration_workspace(client_id, actor_role=role, actor_email=email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/member/petition-acceleration")
def member_petition_acceleration(_member_user: dict = Depends(require_member_user)) -> dict:
    try:
        return service().petition_acceleration_workspace(_member_user["client_id"], actor_role="member")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/builder/members/{client_id}/petition-acceleration")
def builder_petition_acceleration(client_id: str, _builder_user: dict = Depends(require_builder_user)) -> dict:
    try:
        return service().petition_acceleration_workspace(client_id, actor_role="builder", actor_email=_builder_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/attorney/members/{client_id}/petition-acceleration")
def attorney_petition_acceleration(client_id: str, _attorney_user: dict = Depends(require_attorney_user)) -> dict:
    try:
        return service().petition_acceleration_workspace(client_id, actor_role="attorney", actor_email=_attorney_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/leader/members/{client_id}/petition-acceleration")
def leader_petition_acceleration(client_id: str, _leader_user: dict = Depends(require_leader_user)) -> dict:
    try:
        return service().petition_acceleration_workspace(client_id, actor_role="leader", actor_email=_leader_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/admin/petition-acceleration")
def admin_petition_acceleration(client_id: str = "", _admin_user: dict = Depends(require_admin_user)) -> dict:
    try:
        return service().petition_acceleration_workspace(client_id, actor_role="admin", actor_email=_admin_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/members/{client_id}/filing-timeline")
def member_filing_timeline(client_id: str, actor_role: str = "member", actor_email: str = "", actor_client_id: str = "") -> dict:
    try:
        return service().petition_delivery_timeline(client_id, actor_role=actor_role, actor_email=actor_email, actor_client_id=actor_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/attorney/endeavor-letter-generator")
def attorney_endeavor_letter_generator(payload: dict = Body(...), _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        role = _legal_user.get("role", payload.get("actor_role", "attorney"))
        email = _legal_user.get("email", payload.get("actor_email", ""))
        return service().attorney_endeavor_letter_generator(
            payload.get("client_id", ""),
            prompt_config=payload.get("prompt_config", {}),
            actor_role=role,
            actor_email=email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/attorney/members/{client_id}/recommendation-letter-workspace")
def attorney_recommendation_letter_workspace(client_id: str, _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        return service().recommendation_letter_workspace(client_id, actor_role=_legal_user.get("role", "attorney"), actor_email=_legal_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/attorney/recommendation-letter-generator")
def attorney_recommendation_letter_generator(payload: dict = Body(...), _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        role = _legal_user.get("role", payload.get("actor_role", "attorney"))
        email = _legal_user.get("email", payload.get("actor_email", ""))
        return service().attorney_recommendation_letter_generator(
            payload.get("client_id", ""),
            letter_kind=payload.get("letter_kind", "independent"),
            project_type=payload.get("project_type", ""),
            project_id=payload.get("project_id", ""),
            prompt_config=payload.get("prompt_config", {}),
            actor_role=role,
            actor_email=email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/attorney/recommendation-letters/{letter_id}")
def update_recommendation_letter(letter_id: str, payload: dict = Body(...), _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        return service().update_recommendation_letter_status(
            letter_id,
            payload.get("status", ""),
            actor_role=_legal_user.get("role", "attorney"),
            actor_email=_legal_user.get("email", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/attorney/recommendation-letters/{letter_id}/send-to-member")
def send_recommendation_letter_to_member(letter_id: str, _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        return service().send_recommendation_letter_to_member(letter_id, actor_role=_legal_user.get("role", "attorney"), actor_email=_legal_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/recommendation-letters/{letter_id}/download")
def download_recommendation_letter(letter_id: str) -> Response:
    try:
        download = service().recommendation_letter_download(letter_id)
        return Response(
            content=download["content"],
            media_type=download["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{download["file_name"]}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/assistant/reply")
def assistant_reply(payload: dict = Body(...)) -> dict:
    try:
        return service().portal_assistant_reply(
            payload.get("actor_role", ""),
            payload.get("question", ""),
            client_id=payload.get("client_id", ""),
            actor_email=payload.get("actor_email", ""),
            thread=payload.get("thread", []),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/activity-events")
def activity_events(payload: dict = Body(...)) -> dict:
    try:
        return service().log_portal_activity(
            payload.get("actor_role", ""),
            actor_email=payload.get("actor_email", ""),
            actor_client_id=payload.get("actor_client_id", ""),
            event_type=payload.get("event_type", "page_view"),
            message=payload.get("message", ""),
            endpoint=payload.get("endpoint", "/web/activity"),
            metadata=payload.get("metadata", {}),
            related_client_id=payload.get("related_client_id", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/support/tickets")
async def create_support_ticket(
    actor_role: str = Form(...),
    short_description: str = Form(...),
    details: str = Form(...),
    issue_location: str = Form(""),
    current_url: str = Form(""),
    priority: str = Form("normal"),
    is_blocking: str = Form("false"),
    screenshot_url: str = Form(""),
    screenshot_notes: str = Form(""),
    actor_email: str = Form(""),
    actor_client_id: str = Form(""),
    related_client_id: str = Form(""),
    attachment_descriptions_json: str = Form("[]"),
    attachments: list[UploadFile] = File([]),
) -> dict:
    try:
        try:
            attachment_descriptions = json.loads(attachment_descriptions_json or "[]")
        except json.JSONDecodeError as exc:
            raise ValueError("attachment descriptions must be valid JSON") from exc
        if not isinstance(attachment_descriptions, list):
            attachment_descriptions = []
        attachment_payload = []
        for index, item in enumerate(attachments or []):
            file_name = (item.filename or "").strip()
            file_bytes = await item.read()
            if not file_name or not file_bytes:
                continue
            attachment_payload.append(
                {
                    "file_name": file_name,
                    "content_type": item.content_type or "application/octet-stream",
                    "description": str(attachment_descriptions[index]).strip() if index < len(attachment_descriptions) else "",
                    "file_bytes": file_bytes,
                }
            )
        return service().report_support_ticket(
            actor_role,
            short_description,
            details,
            issue_location=issue_location,
            current_url=current_url,
            priority=priority,
            is_blocking=str(is_blocking).strip().lower() in {"1", "true", "yes", "on"},
            screenshot_url=screenshot_url,
            screenshot_notes=screenshot_notes,
            actor_email=actor_email,
            actor_client_id=actor_client_id,
            related_client_id=related_client_id,
            attachments=attachment_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/attorney/members")
def attorney_members(_attorney_user: dict = Depends(require_attorney_user)) -> list[dict]:
    try:
        return service().attorney_members(_attorney_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/attorney/members/{client_id}")
def attorney_member_detail(client_id: str, _attorney_user: dict = Depends(require_attorney_user)) -> dict:
    try:
        return service().attorney_member_detail(client_id, _attorney_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/attorney/members/{client_id}/evidence")
def attorney_member_evidence(client_id: str, _legal_user: dict = Depends(require_legal_staff_user)) -> list[dict]:
    try:
        return service().attorney_member_evidence(client_id, actor_role=_legal_user.get("role", "attorney"), actor_email=_legal_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/batch-intake/sessions")
def batch_intake_sessions(client_id: str, _legal_user: dict = Depends(require_legal_staff_user)) -> list[dict]:
    try:
        return service().batch_intake_sessions(client_id, actor_role=_legal_user.get("role", "attorney"), actor_email=_legal_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/attorney/batch-intake")
async def attorney_batch_intake_create(
    client_id: str = Form(...),
    member_context: str = Form(""),
    actor_role: str = Form("attorney"),
    actor_email: str = Form(""),
    file: UploadFile = File(...),
    _legal_user: dict = Depends(require_legal_staff_user),
) -> dict:
    try:
        payload = await file.read()
        role = _legal_user.get("role", actor_role)
        email = _legal_user.get("email", actor_email)
        return service().attorney_batch_intake_create(
            client_id=client_id,
            member_context=member_context,
            zip_name=file.filename or "batch-intake.zip",
            zip_bytes=payload,
            created_by_role=role,
            actor_role=role,
            actor_email=email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/attorney/batch-intake/{session_id}")
def attorney_batch_intake_session(session_id: str, _legal_user: dict = Depends(require_legal_staff_user)) -> dict:
    try:
        return service().attorney_batch_intake_session(session_id, actor_role=_legal_user.get("role", "attorney"), actor_email=_legal_user.get("email", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/attorney/batch-intake/{session_id}/items/{item_id}")
def update_attorney_batch_intake_item(
    session_id: str,
    item_id: str,
    criterion_code: str = Form(""),
    document_type: str = Form(""),
    title: str = Form(""),
    ai_description: str = Form(""),
    folder_decision: str = Form(""),
    assigned_folder_id: str = Form(""),
    assigned_folder_name: str = Form(""),
    duplicate_action: str = Form(""),
    review_status: str = Form(""),
    actor_role: str = Form("attorney"),
    actor_email: str = Form(""),
    _legal_user: dict = Depends(require_legal_staff_user),
) -> dict:
    try:
        kwargs = {}
        for key, value in {
            "criterion_code": criterion_code,
            "document_type": document_type,
            "title": title,
            "ai_description": ai_description,
            "folder_decision": folder_decision,
            "assigned_folder_id": assigned_folder_id,
            "assigned_folder_name": assigned_folder_name,
            "duplicate_action": duplicate_action,
            "review_status": review_status,
            "actor_role": _legal_user.get("role", actor_role),
            "actor_email": _legal_user.get("email", actor_email),
        }.items():
            if value != "":
                kwargs[key] = value
        return {"ok": True, "status": "updated", "session": service().update_attorney_batch_intake_item(session_id, item_id, **kwargs)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/attorney/batch-intake/{session_id}/bulk-update")
def bulk_update_attorney_batch_intake(
    session_id: str,
    item_ids: str = Form(...),
    review_status: str = Form(""),
    duplicate_action: str = Form(""),
    actor_role: str = Form("attorney"),
    actor_email: str = Form(""),
    _legal_user: dict = Depends(require_legal_staff_user),
) -> dict:
    try:
        items = [item.strip() for item in item_ids.split(",") if item.strip()]
        kwargs = {"actor_role": _legal_user.get("role", actor_role), "actor_email": _legal_user.get("email", actor_email)}
        if review_status != "":
            kwargs["review_status"] = review_status
        if duplicate_action != "":
            kwargs["duplicate_action"] = duplicate_action
        return {"ok": True, "status": "updated", "session": service().bulk_update_attorney_batch_intake(session_id, items, **kwargs)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/attorney/batch-intake/{session_id}/commit")
def commit_attorney_batch_intake(
    session_id: str,
    actor_role: str = Form("attorney"),
    actor_email: str = Form(""),
    _legal_user: dict = Depends(require_legal_staff_user),
) -> dict:
    try:
        return service().commit_attorney_batch_intake(session_id, actor_role=_legal_user.get("role", actor_role), actor_email=_legal_user.get("email", actor_email))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/messages")
def message_center(actor_role: str, actor_email: str = "", actor_client_id: str = "") -> dict:
    try:
        return service().message_center(actor_role, actor_email, actor_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/messages/recipients")
def message_recipients(actor_role: str, actor_email: str = "", actor_client_id: str = "") -> list[dict]:
    try:
        return service().message_recipient_options(actor_role, actor_email, actor_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/messages")
def create_message(
    actor_role: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...),
    recipient_role: str = Form(""),
    recipient_key: str = Form(""),
    urgent: bool = Form(False),
    actor_email: str = Form(""),
    actor_client_id: str = Form(""),
    thread_id: str = Form(""),
    parent_message_id: str = Form(""),
) -> dict:
    try:
        return service().send_message(actor_role, subject, body, recipient_role, recipient_key, urgent, actor_email, actor_client_id, thread_id, parent_message_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/messages/{message_id}/read")
def set_message_read(
    message_id: str,
    actor_role: str = Form(...),
    is_read: bool = Form(True),
    actor_email: str = Form(""),
    actor_client_id: str = Form(""),
) -> dict:
    try:
        return service().set_message_read(message_id, actor_role, is_read, actor_email, actor_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/messages/{message_id}")
def delete_message(message_id: str, actor_role: str, actor_email: str = "", actor_client_id: str = "") -> dict:
    try:
        return service().delete_message(message_id, actor_role, actor_email, actor_client_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/admin/members/{client_id}/debug")
def admin_member_debug(client_id: str, _admin_user: dict = Depends(require_admin_user)) -> dict:
    try:
        return service().member_issue_debug(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/admin/members/{client_id}/reset-session")
def admin_reset_member_session(client_id: str, _admin_user: dict = Depends(require_admin_user)) -> dict:
    try:
        return service().reset_member_sessions(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/builder/members")
def builder_members() -> list[dict]:
    return service().builder_members()


@app.get("/api/builder/members/{client_id}")
def builder_member_detail(client_id: str) -> dict:
    try:
        return service().builder_member_detail(client_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/builder/opportunities")
def builder_opportunities() -> list[dict]:
    return service().builder_opportunities()


@app.post("/api/builder/opportunities")
def create_builder_opportunity(
    criterion_code: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    target_evidence_type: str = Form("Other"),
    suggested_due_days: int = Form(14),
) -> dict:
    try:
        return service().create_opportunity(criterion_code, title, description, target_evidence_type, suggested_due_days)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/builder/tasks")
def create_builder_task(
    client_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    criterion_code: str = Form(""),
    due_date: str = Form(""),
    opportunity_id: str = Form(""),
) -> dict:
    try:
        return service().create_builder_task(client_id, title, description, criterion_code, due_date, opportunity_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/builder/tasks/{task_id}")
def update_builder_task(task_id: str, status: str = Form(""), due_date: str = Form("")) -> dict:
    try:
        kwargs = {}
        if status != "":
            kwargs["status"] = status
        if due_date != "":
            kwargs["due_date"] = due_date
        return service().update_builder_task(task_id, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/member/dashboard")
def dashboard(member: dict = Depends(require_member_user)) -> dict:
    return service().member_dashboard(member["client_id"], member["case_id"], member.get("display_name", ""))


@app.get("/api/member/profile")
def member_profile(member: dict = Depends(require_member_user)) -> dict:
    return service().member_profile(member["client_id"], member["case_id"])


@app.put("/api/member/profile")
def update_member_profile(
    member: dict = Depends(require_member_user),
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    preferred_name: str = Form(""),
    phone: str = Form(""),
    date_of_birth: str = Form(""),
    country_of_citizenship: str = Form(""),
    country_of_residence: str = Form(""),
    city_state: str = Form(""),
    current_title: str = Form(""),
    current_employer: str = Form(""),
    employer_type: str = Form(""),
    industry_domain: str = Form(""),
    primary_field: str = Form(""),
    specialization: str = Form(""),
    years_experience: str = Form(""),
    highest_degree: str = Form(""),
    degree_field: str = Form(""),
    institution: str = Form(""),
    graduation_year: str = Form(""),
    linkedin_url: str = Form(""),
    personal_website: str = Form(""),
    google_scholar_url: str = Form(""),
    orcid_id: str = Form(""),
    biography: str = Form(""),
    top_achievements: str = Form(""),
    awards_summary: str = Form(""),
    memberships_summary: str = Form(""),
    publications_summary: str = Form(""),
    judging_summary: str = Form(""),
    original_contributions_summary: str = Form(""),
    leading_roles_summary: str = Form(""),
    media_summary: str = Form(""),
    salary_summary: str = Form(""),
    proposed_final_merits_summary: str = Form(""),
    target_filing_window: str = Form(""),
    profile_confirmed: bool = Form(False),
) -> dict:
    try:
        return service().update_member_profile(
            client_id=member["client_id"],
            case_id=member["case_id"],
            first_name=first_name,
            last_name=last_name,
            email=email,
            preferred_name=preferred_name,
            phone=phone,
            date_of_birth=date_of_birth,
            country_of_citizenship=country_of_citizenship,
            country_of_residence=country_of_residence,
            city_state=city_state,
            current_title=current_title,
            current_employer=current_employer,
            employer_type=employer_type,
            industry_domain=industry_domain,
            primary_field=primary_field,
            specialization=specialization,
            years_experience=years_experience,
            highest_degree=highest_degree,
            degree_field=degree_field,
            institution=institution,
            graduation_year=graduation_year,
            linkedin_url=linkedin_url,
            personal_website=personal_website,
            google_scholar_url=google_scholar_url,
            orcid_id=orcid_id,
            biography=biography,
            top_achievements=top_achievements,
            awards_summary=awards_summary,
            memberships_summary=memberships_summary,
            publications_summary=publications_summary,
            judging_summary=judging_summary,
            original_contributions_summary=original_contributions_summary,
            leading_roles_summary=leading_roles_summary,
            media_summary=media_summary,
            salary_summary=salary_summary,
            proposed_final_merits_summary=proposed_final_merits_summary,
            target_filing_window=target_filing_window,
            profile_confirmed=profile_confirmed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/member/critical-role-projects")
async def create_critical_role_project(request: Request, member: dict = Depends(require_member_user)) -> dict:
    try:
        form = await request.form()
        return service().save_critical_role_project(member["client_id"], member["case_id"], **dict(form))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/member/critical-role-projects/{project_id}")
async def update_critical_role_project(project_id: str, request: Request, member: dict = Depends(require_member_user)) -> dict:
    try:
        form = await request.form()
        return service().save_critical_role_project(member["client_id"], member["case_id"], project_id=project_id, **dict(form))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/member/critical-role-projects/{project_id}")
def remove_critical_role_project(project_id: str, member: dict = Depends(require_member_user)) -> dict:
    try:
        return service().delete_critical_role_project(member["client_id"], member["case_id"], project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/member/original-contributions")
async def create_original_contribution(request: Request, member: dict = Depends(require_member_user)) -> dict:
    try:
        form = await request.form()
        return service().save_original_contribution(member["client_id"], member["case_id"], **dict(form))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/member/original-contributions/{entry_id}")
async def update_original_contribution(entry_id: str, request: Request, member: dict = Depends(require_member_user)) -> dict:
    try:
        form = await request.form()
        return service().save_original_contribution(member["client_id"], member["case_id"], entry_id=entry_id, **dict(form))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/member/original-contributions/{entry_id}")
def remove_original_contribution(entry_id: str, member: dict = Depends(require_member_user)) -> dict:
    try:
        return service().delete_original_contribution(member["client_id"], member["case_id"], entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/criteria")
def criteria() -> list[dict]:
    return service().criteria()


@app.get("/api/evidence")
def evidence(q: str = "") -> list[dict]:
    return service().evidence(q.strip())


@app.get("/api/member/planner")
def planner_items(token: str = Header(alias="Authorization", default="")) -> list[dict]:
    member = optional_member_user(token)
    if not member:
        return service().planner_items()
    return service().planner_items(member["client_id"], member["case_id"])


@app.post("/api/member/planner")
def create_planner_item(
    token: str = Header(alias="Authorization", default=""),
    member_role: str = Form(...),
    issued_by: str = Form(...),
    description: str = Form(...),
    planned_completion_date: str = Form(...),
    actual_completion_date: str = Form(""),
    status: str = Form("planned"),
    comments: str = Form(""),
    criterion_code: str = Form(""),
    folder_id: str = Form(""),
) -> dict:
    try:
        member = optional_member_user(token)
        return service().create_planner_item(
            member_role=member_role,
            issued_by=issued_by,
            description=description,
            planned_completion_date=planned_completion_date,
            actual_completion_date=actual_completion_date,
            status=status,
            comments=comments,
            criterion_code=criterion_code,
            folder_id=folder_id,
            client_id=member["client_id"] if member else None,
            case_id=member["case_id"] if member else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/member/planner/{item_id}")
def update_planner_item(
    item_id: str,
    token: str = Header(alias="Authorization", default=""),
    member_role: str = Form(""),
    issued_by: str = Form(""),
    description: str = Form(""),
    planned_completion_date: str = Form(""),
    actual_completion_date: str = Form(""),
    status: str = Form(""),
    comments: str = Form(""),
    criterion_code: str = Form(""),
    folder_id: str = Form(""),
) -> dict:
    try:
        member = optional_member_user(token)
        kwargs = {}
        for key, value in {
            "member_role": member_role,
            "issued_by": issued_by,
            "description": description,
            "planned_completion_date": planned_completion_date,
            "actual_completion_date": actual_completion_date,
            "status": status,
            "comments": comments,
            "criterion_code": criterion_code,
            "folder_id": folder_id,
        }.items():
            if value != "":
                kwargs[key] = value
        return service().update_planner_item(
            item_id,
            client_id=member["client_id"] if member else None,
            case_id=member["case_id"] if member else None,
            **kwargs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/member/planner/{item_id}")
def delete_planner_item(item_id: str, token: str = Header(alias="Authorization", default="")) -> dict:
    try:
        member = optional_member_user(token)
        return service().delete_planner_item(item_id, member["client_id"] if member else None, member["case_id"] if member else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.get("/api/criteria/{criterion_code}/workspace")
def criterion_workspace(criterion_code: str, q: str = "", token: str = Header(alias="Authorization", default="")) -> dict:
    try:
        member = optional_member_user(token)
        return service().criterion_workspace(
            criterion_code,
            q.strip(),
            member["client_id"] if member else None,
            member["case_id"] if member else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/evidence/analyze")
async def analyze_evidence(
    member_context: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    try:
        payload = await file.read()
        return service().analyze_evidence(
            member_context=member_context,
            file_name=file.filename or "uploaded-file",
            content_type=file.content_type or "application/octet-stream",
            file_bytes=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/evidence")
async def upload_evidence(
    token: str = Header(alias="Authorization", default=""),
    criterion_code: str = Form(...),
    document_type: str = Form("Other"),
    title: str = Form(...),
    description: str = Form(""),
    duplicate_action: str = Form(""),
    ai_summary: str = Form(""),
    quality_score: int | None = Form(None),
    folder_id: str = Form(""),
    file: UploadFile = File(...),
) -> dict:
    try:
        payload = await file.read()
        member = optional_member_user(token)
        return service().upload_evidence(
            criterion_code=criterion_code,
            document_type=document_type,
            title=title,
            description=description,
            file_name=file.filename or "uploaded-file",
            content_type=file.content_type or "application/octet-stream",
            file_bytes=payload,
            duplicate_action=duplicate_action,
            ai_summary=ai_summary,
            quality_score=quality_score,
            client_id=member["client_id"] if member else None,
            case_id=member["case_id"] if member else None,
            folder_id=folder_id or None,
        )
    except DuplicateEvidenceError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "ok": False,
                "status": "duplicate",
                "message": "A file with this name already exists in this category.",
                "duplicate": exc.duplicate,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc
    except S3ConfigError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc
    except S3StorageError as exc:
        raise HTTPException(status_code=502, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.post("/api/criteria/{criterion_code}/folders")
def create_folder(criterion_code: str, name: str = Form(...), parent_id: str = Form(""), color: str = Form("#1f6f5b"), token: str = Header(alias="Authorization", default="")) -> dict:
    try:
        member = optional_member_user(token)
        return service().create_folder(
            criterion_code,
            name,
            parent_id or None,
            color,
            member["client_id"] if member else None,
            member["case_id"] if member else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/folders/{folder_id}")
def update_folder(folder_id: str, name: str = Form(""), color: str = Form(""), parent_id: str | None = Form(None), token: str = Header(alias="Authorization", default="")) -> dict:
    try:
        member = optional_member_user(token)
        kwargs = {}
        if name != "":
            kwargs["name"] = name
        if color != "":
            kwargs["color"] = color
        if parent_id is not None:
            kwargs["parent_id"] = parent_id
        return service().update_folder(
            folder_id,
            client_id=member["client_id"] if member else None,
            case_id=member["case_id"] if member else None,
            **kwargs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/folders/{folder_id}")
def delete_folder(folder_id: str, token: str = Header(alias="Authorization", default="")) -> dict:
    try:
        member = optional_member_user(token)
        return service().delete_folder(folder_id, member["client_id"] if member else None, member["case_id"] if member else None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.patch("/api/evidence/{evidence_id}/folder")
def move_evidence(evidence_id: str, folder_id: str = Form(""), token: str = Header(alias="Authorization", default="")) -> dict:
    try:
        member = optional_member_user(token)
        return service().move_evidence_to_folder(
            evidence_id,
            folder_id or None,
            member["client_id"] if member else None,
            member["case_id"] if member else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"ok": False, "status": "failed", "error": str(exc)}) from exc


@app.delete("/api/evidence/{evidence_id}")
def delete_evidence(evidence_id: str, token: str = Header(alias="Authorization", default="")) -> dict:
    member = optional_member_user(token)
    result = service().archive_evidence(
        evidence_id,
        "member_delete",
        member["client_id"] if member else None,
        member["case_id"] if member else None,
    )
    if not result["ok"]:
        raise HTTPException(status_code=404 if result["error"] == "Evidence not found" else 502, detail=result)
    return result

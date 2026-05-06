# Thread: API And Function Map

## Purpose

This is the quickest backend continuation map for the current Ascend suite.

## Primary API Routes

### Auth

- `POST /api/auth/login`
- `POST /api/builder/auth/login`
- `GET /api/auth/me`
- `GET /api/builder/auth/me`
- `POST /api/auth/change-password`
- `POST /api/builder/auth/change-password`
- `POST /api/auth/logout`
- `POST /api/builder/auth/logout`

### Builder / Leader / Admin / Attorney

- `GET /api/builder/dashboard`
- `GET /api/leader/dashboard`
- `POST /api/leader/invites`
- `PATCH /api/leader/members/{client_id}/builder-assignment`
- `PATCH /api/leader/members/{client_id}/attorney-assignment`
- `GET /api/admin/operations`
- `GET /api/attorney/petition-generator`

### Messaging

- `GET /api/messages`
- `GET /api/messages/recipients`
- `POST /api/messages`
- `PATCH /api/messages/{message_id}/read`
- `DELETE /api/messages/{message_id}`

### Admin support

- `GET /api/admin/members/{client_id}/debug`
- `POST /api/admin/members/{client_id}/reset-session`

### Builder member work

- `GET /api/builder/members`
- `GET /api/builder/members/{client_id}`
- `GET /api/builder/opportunities`
- `POST /api/builder/opportunities`
- `POST /api/builder/tasks`
- `PATCH /api/builder/tasks/{task_id}`

### Member

- `GET /api/member/dashboard`
- `GET /api/member/profile`
- `PUT /api/member/profile`
- `GET /api/member/planner`
- `POST /api/member/planner`
- `PATCH /api/member/planner/{item_id}`
- `DELETE /api/member/planner/{item_id}`

### Evidence

- `GET /api/criteria`
- `GET /api/evidence`
- `GET /api/criteria/{criterion_code}/workspace`
- `POST /api/evidence/analyze`
- `POST /api/evidence`
- `POST /api/criteria/{criterion_code}/folders`
- `PATCH /api/folders/{folder_id}`
- `DELETE /api/folders/{folder_id}`
- `PATCH /api/evidence/{evidence_id}/folder`
- `DELETE /api/evidence/{evidence_id}`

## Important Service Methods

### Messaging / ops

- `message_recipient_options`
- `message_center`
- `send_message`
- `set_message_read`
- `delete_message`
- `record_operational_event`
- `admin_operational_dashboard`
- `member_issue_debug`
- `reset_member_sessions`

### Builder / leader / attorney

- `builder_dashboard`
- `leader_dashboard`
- `builder_members`
- `builder_member_detail`
- `builder_opportunities`
- `leader_invite_member`
- `leader_assign_builder`
- `leader_assign_attorney`
- `attorney_petition_generator`
- `create_builder_task`
- `update_builder_task`
- `create_opportunity`

### Member / evidence

- `dashboard`
- `criteria`
- `member_profile`
- `update_member_profile`
- `criterion_workspace`
- `evidence`
- `planner_items`
- `create_planner_item`
- `planner_item`
- `update_planner_item`
- `delete_planner_item`
- `upload_evidence`
- `analyze_evidence`
- `create_folder`
- `folder`
- `update_folder`
- `delete_folder`
- `move_evidence_to_folder`
- `archive_evidence`

## Current Frontend Hub

The React frontend still centralizes much of the portal rendering in:

- `frontend-react/src/App.jsx`

That file currently contains:

- portal routing
- role-based page switching
- form state
- fetch orchestration
- messaging UI
- attorney petition generator UI

## Continuation Suggestion

If work gets larger, split `App.jsx` by portal or by major feature group:

- auth
- member
- builder
- leader
- attorney
- admin
- messaging

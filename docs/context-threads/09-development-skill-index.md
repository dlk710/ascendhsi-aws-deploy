# Thread: Development Skill Index

## Purpose

This thread maps the core skills required to continue developing Ascend as a production-grade role-based product suite.

Use this file at the start of a new development chat to choose the right continuation threads before changing code.

## Product Development Rule

Every feature should be treated as a role-aware workflow change, not an isolated screen or endpoint change.

Before implementation, identify:

- affected role portals
- affected API routes
- affected service methods
- data model impact
- AI or storage impact
- messaging or operations impact
- required tests

## Required Skill Threads

### React Portal Engineering

Read:

- `10-react-portal-engineering.md`
- affected portal thread, such as `01-member-portal.md` or `04-attorney-portal.md`

Use when changing:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- role navigation
- portal sections
- perspective switching
- forms, tables, cards, filters, evidence workspaces, dashboards

### FastAPI Backend Engineering

Read:

- `11-fastapi-backend-engineering.md`
- `08-api-and-function-map.md`

Use when changing:

- `app/api.py`
- `app/services.py`
- auth endpoints
- evidence endpoints
- messaging endpoints
- admin, builder, leader, attorney, or member service behavior

### Data Modeling And Migrations

Read:

- `12-data-modeling-and-migrations.md`
- `08-api-and-function-map.md`

Use when changing:

- `app/db.py`
- SQLite tables
- operational event fields
- assignments
- sessions
- evidence, planner, message, or profile schema

### Role-Based Product And EB1A Domain

Read:

- `13-role-based-product-and-eb1a-domain.md`
- affected portal thread

Use when changing:

- portal responsibilities
- evidence criteria workflows
- attorney review logic
- builder tasks
- leader assignment rules
- member next-step guidance

### Product Documentation And PRD Maintenance

Read:

- `00-suite-overview.md`
- affected portal thread
- `README.md`
- `docs/context-threads/README.md`

Use when changing:

- portal page maps
- role responsibilities
- PRD-style workflow expectations
- demo or QA guidance that changes how the product is explained

### AI Integration And Observability

Read:

- `14-ai-integration-and-observability.md`
- `07-integrations-and-ai.md`

Use when changing:

- `app/openai_client.py`
- evidence analysis
- petition generation
- AI fallbacks
- OpenAI usage tracking
- admin AI metrics

### Storage And Google Drive Integration

Read:

- `15-storage-and-google-drive.md`
- `07-integrations-and-ai.md`

Use when changing:

- `app/google_drive.py`
- `app/storage.py`
- evidence upload/archive behavior
- folder sync
- future production storage abstraction

### Messaging And Collaboration Systems

Read:

- `16-messaging-collaboration-systems.md`
- `06-messaging-and-collaboration.md`

Use when changing:

- threaded messages
- recipient rules
- unread or urgent behavior
- tasks created from messages
- message attachments

### Admin Operations And Production Readiness

Read:

- `17-admin-operations-and-production-readiness.md`
- `05-admin-operations-portal.md`

Use when changing:

- health checks
- operational events
- debug console
- session remediation
- alerts
- production deployment posture

### Testing, QA, And Release Discipline

Read:

- `18-testing-qa-and-release-discipline.md`

Use before merging or deploying any change.

## Recommended Chat Startup

For a new development chat, begin with:

```text
Use the Ascend context threads. Read 09-development-skill-index.md, then read the skill thread and product thread relevant to this feature before making changes.
```

Then name the target feature and role portal.

## Production-Grade Development Bar

A change is not production-grade until it has:

- clear role ownership
- explicit failure behavior
- backend validation
- persistent data behavior
- UI loading and error states
- operational visibility
- tests for expected and failure paths
- no regression to AI fallback behavior
- no leakage of implementation details to member-facing UI

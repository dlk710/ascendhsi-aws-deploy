# Thread: Development Skill Index

## Purpose

This thread maps the core skills required to continue developing Ascend as a production-grade role-based product suite.

Use this file at the start of a new development chat to choose the right continuation threads before changing code.

## Product Development Rule

Every feature should be treated as a role-aware workflow change, not an isolated screen or endpoint change.

## Current Dev Baseline

- Daily UX work should run the local React app with `cd frontend-react && pnpm run dev:aws`.
- That command proxies `/api`, `/ready`, `/health`, `/docs`, and `/openapi.json` to the shared AWS dev backend.
- Use `pnpm run dev:local` only when the backend is also running locally on `127.0.0.1:8000`.
- AWS dev is currently available at `https://dq5ab404dg57q.cloudfront.net`; the target branded endpoint is `https://dev-portal.ascendhsi.com` after DNS/ACM validation.
- Work in a personal branch and keep fabricated test data clearly prefixed by developer.

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
- `docs/aws-deployment.md` when changing cloud runtime behavior

Use when changing:

- `app/openai_client.py`
- evidence analysis
- petition generation
- AI fallbacks
- OpenAI usage tracking
- admin AI metrics
- OpenAI secrets and model configuration in cloud deployments

### Storage And AWS S3 Integration

Read:

- `15-storage-and-aws-s3.md`
- `07-integrations-and-ai.md`
- `docs/aws-deployment.md`

Use when changing:

- `app/storage.py`
- `app/s3_storage.py`
- evidence upload/archive behavior
- folder sync
- future production storage abstraction
- signed URL access to active or archived files

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
- `docs/aws-deployment.md`
- `deploy/aws/README.md`

Use when changing:

- health checks
- operational events
- debug console
- session remediation
- alerts
- production deployment posture
- Terraform modules, ECS, ALB, CloudFront, RDS, S3, Athena, IAM, or Secrets Manager

### Testing, QA, And Release Discipline

Read:

- `18-testing-qa-and-release-discipline.md`
- `docs/verification-notes.md`

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

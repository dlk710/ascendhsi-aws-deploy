# Ascend Product Suite

Ascend is a multi-portal EB1A operations suite for:

- Members
- Profile Builders
- Leaders
- Attorneys
- Admin / Operations

The active product uses a React frontend with a FastAPI backend, a configurable database layer that can run on SQLite or PostgreSQL-compatible databases, Amazon S3 for active document storage and archival routing, and OpenAI-backed analysis with fallback behavior.

This repository is intended to be understandable and extendable by any engineer, operator, or AI assistant without relying on prior chat history. The documentation in `docs/` is the source of truth for feature behavior, implementation boundaries, and remaining work.

## Active architecture

### Frontend

- `frontend-react/` - active React portal suite

### Backend

- `app/` - FastAPI routes, services, storage, data, AI integration

### Documentation

- `docs/feature-catalog.md` - portal-by-portal feature inventory
- `docs/aws-deployment.md` - AWS hosting shape, required services, and environment variables
- `docs/database-configuration.md` - database backends, switching rules, and deployment guidance
- `docs/solution-architecture.md` - current and scaled-world architecture with tech-stack guidance
- `docs/verification-notes.md` - live verification findings and known runtime caveats
- `docs/missing-features.md` - documented gaps, follow-up work, and production-hardening items
- `docs/handoff-guide.md` - continuation guide for new developers or AI assistants
- `docs/context-threads/` - continuation threads for each portal, integration, and engineering area
- `docs/repository-layout.md` - repository organization guide

### Tests

- `tests/` - API, AI, S3 storage, config, and database tests

## Current product capabilities

- role-based portal login
- multi-page role navigation across every portal
- member profile management
- event planner
- evidence intake review
- criterion-based evidence organization
- threaded messaging
- leader executive overview, risk, and capacity dashboards
- leader assignment oversight
- leader assume-as-builder and assume-as-attorney views
- builder opportunity library and task assignment
- attorney dossier review
- attorney batch intake and evidence review
- attorney AI petition generator
- admin operational monitoring, support tickets, and debug console

## Run locally

### Python backend

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/uvicorn app.api:app --host 127.0.0.1 --port 8000
```

### React frontend

```bash
cd frontend-react
pnpm install
pnpm run dev
```

Then open:

```text
http://127.0.0.1:3001
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## Configuration

Primary config files:

- `config/app.json`
- `config/openai.json`
- `config/storage.json`

### OpenAI

- keep `config/openai.json` checked in without secrets
- provide the actual key through the environment variable defined by `api_key_env`
- an example config is included at `config/openai.example.json`

### Storage

- S3 storage is configured in `config/storage.json`
- bucket, archive bucket, region, and optional public URL are supplied through environment variables
- uploads remain active in the configured active storage class, and archived records can move into colder storage classes

### Database

- local development defaults to SQLite
- cloud deployments can switch to PostgreSQL or Aurora PostgreSQL-compatible by setting `ASCEND_DATABASE_URL`
- the app keeps the same service layer and automatically selects the configured backend at startup

## Tests

```bash
python3 -m pytest -q
cd frontend-react && pnpm run build
```

If `pytest` is not available in the active Python environment, create a local virtual environment and install `requirements.txt` plus `pytest`. Do not install test dependencies globally on managed macOS/Python environments.

## Live AWS dev deployment

The current dev deployment runs in AWS account `027903151318`, region `us-east-2`.

- Frontend: CloudFront distribution `EV6WT9DUO1GQH` backed by S3 bucket `ascend-frontend-dev-027903151318`
- Backend: ECS Fargate service `ascend-dev-backend` in cluster `ascend-dev-cluster`
- API entry: Application Load Balancer `ascend-dev-api`
- Database: RDS PostgreSQL instance `ascend-dev-postgres`
- Active evidence storage: S3 bucket `client-data-dev-027903151318`
- Archive storage: S3 bucket `client-data-archive-dev-027903151318`
- Observability: ALB/CloudFront logs in S3 with Athena workgroup `ascend-dev-observability`
- Secrets: AWS Secrets Manager entries for database URL and OpenAI API key

The public dev URL is:

```text
https://dq5ab404dg57q.cloudfront.net
```

After frontend changes, build the React app, sync `frontend-react/dist/` to the frontend S3 bucket, and invalidate CloudFront.

## Continuation guidance

Start here when resuming work:

1. `docs/context-threads/README.md`
2. `docs/feature-catalog.md`
3. `docs/solution-architecture.md`
4. `docs/verification-notes.md`
5. `docs/missing-features.md`
6. `docs/context-threads/19-chat-change-inventory.md`
7. `docs/context-threads/20-thread-to-file-map.md`

## Demo helpers

For fast local portal switching during demos or QA:

- `frontend-react/public/auth-helper.html`
- `frontend-react/public/logout-helper.html`
- `docs/local-sample-credentials.md`

## AWS deployment

AWS deployment artifacts and environment examples are under:

- `deploy/aws/README.md`
- `deploy/aws/backend.Dockerfile`
- `deploy/aws/frontend.Dockerfile`
- `deploy/aws/terraform/`

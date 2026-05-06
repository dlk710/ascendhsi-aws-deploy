# Thread: Thread To File Map

## Purpose

This file maps each continuation thread to the code files that most directly support it.

Use it when you know the portal, integration, or deployment area you want to work on, but need the fastest jump from product context to implementation.

## Member Portal

Context thread:

- `01-member-portal.md`

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/db.py`

## Profile Builder Portal

Context thread:

- `02-profile-builder-portal.md`

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/db.py`

## Leader Portal

Context thread:

- `03-leader-portal.md`

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/db.py`

## Attorney Portal

Context thread:

- `04-attorney-portal.md`

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/openai_client.py`
- `app/db.py`

## Admin / Operations Portal

Context threads:

- `05-admin-operations-portal.md`
- `17-admin-operations-and-production-readiness.md`

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/db.py`
- `docs/aws-deployment.md`
- `deploy/aws/README.md`

## Messaging

Context threads:

- `06-messaging-and-collaboration.md`
- `16-messaging-collaboration-systems.md`

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/db.py`

## AI And OpenAI-Driven Flows

Context threads:

- `07-integrations-and-ai.md`
- `14-ai-integration-and-observability.md`

Primary files:

- `app/openai_client.py`
- `app/services.py`
- `app/api.py`
- `tests/test_openai_client.py`
- `tests/test_api.py`
- `docs/aws-deployment.md`

## Storage And AWS S3

Context thread:

- `15-storage-and-aws-s3.md`

Primary files:

- `app/storage.py`
- `app/s3_storage.py`
- `app/services.py`
- `tests/test_s3_storage.py`
- `tests/test_storage.py`
- `config/storage.json`
- `deploy/aws/terraform/s3.tf`

## AWS Cloud Deployment

Primary docs:

- `docs/aws-deployment.md`
- `deploy/aws/README.md`
- `docs/solution-architecture.md`
- `docs/verification-notes.md`

Primary files:

- `deploy/aws/terraform/`
- `deploy/aws/backend.Dockerfile`
- `deploy/aws/frontend.Dockerfile`
- `deploy/aws/backend.env.example`
- `deploy/aws/frontend.env.example`
- `frontend-react/public/runtime-config.js`

## Data Model And Migrations

Context thread:

- `12-data-modeling-and-migrations.md`

Primary files:

- `app/db.py`
- `app/services.py`
- `tests/test_db.py`
- `docs/database-configuration.md`

## Testing And Release Confidence

Context thread:

- `18-testing-qa-and-release-discipline.md`

Primary files:

- `tests/test_api.py`
- `tests/test_openai_client.py`
- `tests/test_db.py`
- `tests/test_s3_storage.py`
- `tests/test_storage.py`
- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `docs/verification-notes.md`

## Recommended Resume Order

1. Read `19-chat-change-inventory.md`.
2. Read the relevant portal or integration thread.
3. Read this file to jump into the right implementation files.
4. Read `08-api-and-function-map.md`.
5. For AWS work, read `docs/aws-deployment.md` and `deploy/aws/README.md`.

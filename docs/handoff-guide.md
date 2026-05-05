# Handoff Guide

This repository is intended to be continued by another engineer, product team, internal IT team, or AI assistant without relying on any hidden conversation history.

## Where to start

1. Read `README.md`
2. Read `docs/feature-catalog.md`
3. Read `docs/aws-deployment.md`
4. Read `docs/solution-architecture.md`
5. Read `docs/verification-notes.md`
6. Read `docs/missing-features.md`
7. Read `docs/repository-layout.md`
8. Read `docs/context-threads/README.md`
9. Review `docs/context-threads/19-chat-change-inventory.md`
10. Review `docs/context-threads/20-thread-to-file-map.md`

## Most important implementation files

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `app/api.py`
- `app/services.py`
- `app/db.py`
- `app/openai_client.py`

## Runtime expectations

- FastAPI backend
- React frontend
- SQLite database
- Amazon S3 bucket configuration for document storage and archive movement
- OpenAI API key for AI classification and petition generation

## Continuation rule

Documentation in this repository should stay understandable without requiring prior chats, oral handoff, or model-specific memory. New features should update:

- `docs/feature-catalog.md`
- `docs/solution-architecture.md` when architecture or scaling assumptions change
- `docs/verification-notes.md` when runtime verification reveals meaningful caveats
- `docs/missing-features.md`
- any affected portal or engineering context thread

## Key product areas already present

- Member Portal
- Profile Builder Portal
- Leader Portal
- Attorney Portal
- Admin / Operations Portal
- leader executive dashboard pages
- leader assume-as-builder and assume-as-attorney views
- threaded messaging
- evidence intake and organization
- AI petition generator
- admin support tickets and debug workflows

## Demo and QA helpers

- `docs/local-sample-credentials.md` lists active demo accounts
- `frontend-react/public/auth-helper.html` prepares role sessions quickly
- `frontend-react/public/logout-helper.html` clears local demo auth state

## Before production

- move from SQLite to a managed production database if scale or concurrency requires it
- rotate any local demo credentials
- add formal secret management
- establish CI for tests
- finalize RBAC hardening and audit logging

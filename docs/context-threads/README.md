# Ascend Product Context Threads

This folder preserves the working product context as portal-by-portal and integration-by-integration continuation threads.

These are not raw chat exports. They are structured product knowledge threads so future work can continue without losing product intent, workflow decisions, current live behavior, or the required functions behind each area.

They are written to be usable by both humans and AI assistants. A new contributor should be able to understand the suite from these files alone, without hidden chat context.

## Thread Index

1. [00-suite-overview.md](00-suite-overview.md)
2. [01-member-portal.md](01-member-portal.md)
3. [02-profile-builder-portal.md](02-profile-builder-portal.md)
4. [03-leader-portal.md](03-leader-portal.md)
5. [04-attorney-portal.md](04-attorney-portal.md)
6. [05-admin-operations-portal.md](05-admin-operations-portal.md)
7. [06-messaging-and-collaboration.md](06-messaging-and-collaboration.md)
8. [07-integrations-and-ai.md](07-integrations-and-ai.md)
9. [08-api-and-function-map.md](08-api-and-function-map.md)
10. [09-development-skill-index.md](09-development-skill-index.md)
11. [10-react-portal-engineering.md](10-react-portal-engineering.md)
12. [11-fastapi-backend-engineering.md](11-fastapi-backend-engineering.md)
13. [12-data-modeling-and-migrations.md](12-data-modeling-and-migrations.md)
14. [13-role-based-product-and-eb1a-domain.md](13-role-based-product-and-eb1a-domain.md)
15. [14-ai-integration-and-observability.md](14-ai-integration-and-observability.md)
16. [15-storage-and-aws-s3.md](15-storage-and-aws-s3.md)
17. [16-messaging-collaboration-systems.md](16-messaging-collaboration-systems.md)
18. [17-admin-operations-and-production-readiness.md](17-admin-operations-and-production-readiness.md)
19. [18-testing-qa-and-release-discipline.md](18-testing-qa-and-release-discipline.md)
20. [19-chat-change-inventory.md](19-chat-change-inventory.md)
21. [20-thread-to-file-map.md](20-thread-to-file-map.md)

## Current Product Shape

The suite currently operates as a multi-portal EB1A platform with:

- `Member Portal`
- `Profile Builder Portal`
- `Leader Portal`
- `Attorney Portal`
- `Admin / Operations Portal`

Shared capabilities include:

- AI evidence intake
- criterion-based evidence organization
- folder-based evidence review
- event planner
- role-based assignments
- threaded messaging
- leader perspective switching into builder and attorney views
- executive leader dashboards for overview, risk, and capacity
- attorney batch intake
- admin health and debug views
- admin support ticket management
- attorney AI petition generator

## Code Locations

Frontend:
- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `frontend-react/index.html`

Backend:
- `app/api.py`
- `app/services.py`
- `app/openai_client.py`
- `app/db.py`
- `app/storage.py`
- `app/s3_storage.py`

Tests:
- `tests/test_api.py`
- `tests/test_openai_client.py`
- `tests/test_db.py`
- `tests/test_storage.py`
- `tests/test_s3_storage.py`

## Continuation Guidance

When resuming work:

1. start with `09-development-skill-index.md`
2. read the portal thread you are changing
3. read the relevant skill thread for frontend, backend, data, AI, storage, messaging, operations, or testing
4. read the messaging and integrations threads if the work crosses roles or services
5. use the function map to find the current backend entry points
6. preserve role boundaries and child-page navigation
7. keep fallback behavior for AI and integration failures

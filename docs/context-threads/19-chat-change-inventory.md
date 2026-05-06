# Thread: Chat Change Inventory

## Purpose

This file captures the working inventory of files that were changed across the product-building chat, grouped by responsibility so development can continue without reconstructing the history from memory.

This is a curated continuation inventory for the active product and AWS deployment repositories. Use it together with git history for exact diffs.

## Primary Files Changed During This Build Cycle

### Frontend shell and shared UX

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `frontend-react/index.html`
- `frontend-react/src/main.jsx`

These files absorbed most of the portal UX work, including:

- login and portal switching
- left navigation and child-page routing
- member profile tabs
- event planner
- evidence intake and evidence-by-criterion views
- builder, leader, attorney, and admin page rendering
- threaded messaging
- attorney petition generator
- cache-buster updates for frontend refreshes
- non-blocking portal hydration after login

### Frontend branding assets

- `frontend-react/public/ascend-logo.webp`
- `frontend-react/public/favicon.png`
- `frontend-react/public/favicon.ico`

These support Ascend branding in the browser tab and UI shell.

### Backend API and application behavior

- `app/api.py`
- `app/services.py`
- `app/openai_client.py`
- `app/db.py`
- `app/storage.py`
- `app/s3_storage.py`
- `app/config.py`

These files carry the working backend for:

- role-based auth
- member profile and planner data
- evidence analysis and upload
- S3 storage and signed/private file access behavior
- foldering and archive behavior
- messaging and read/unread logic
- leader assignment flows
- admin monitoring and debug flows
- attorney AI petition generation

### Tests used to hold the suite together

- `tests/test_api.py`
- `tests/test_openai_client.py`
- `tests/test_db.py`
- `tests/test_s3_storage.py`
- `tests/test_storage.py`
- `tests/test_config.py`
- `tests/test_server.py`

These cover the highest-risk backend behaviors and were expanded as new features were introduced.

## High-Impact Feature Areas Reflected In These Files

### Member experience

- login, welcome salutation, profile tabs
- event planner
- evidence intake review
- AI/manual category routing
- document type classification
- evidence detail navigation
- folder organization

### Internal operations

- profile builder roster and opportunity workflows
- leader invite, assignment, and domain-aware staffing
- attorney dossier and petition generator
- admin operational monitoring and debug support

### Shared platform systems

- threaded messaging with reply and nested reply behavior
- S3 storage integration
- OpenAI evidence and petition generation
- operational fallback behavior when AI or integrations fail

## Best-Guess “Most Edited” Files

If someone needs to resume development quickly, start here first:

1. `frontend-react/src/App.jsx`
2. `frontend-react/src/styles.css`
3. `app/services.py`
4. `app/api.py`
5. `app/db.py`
6. `app/openai_client.py`
7. `deploy/aws/terraform/`
8. `docs/aws-deployment.md`

## Continuation Guidance

- use this file as the change inventory
- use `08-api-and-function-map.md` as the entry-point map
- use the portal threads for product intent and workflow behavior
- use the engineering threads for implementation direction

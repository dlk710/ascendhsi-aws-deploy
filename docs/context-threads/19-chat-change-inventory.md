# Thread: Chat Change Inventory

## Purpose

This file captures the working inventory of files that were changed across the product-building chat, grouped by responsibility so development can continue without reconstructing the history from memory.

Because `/Users/lohithdeshpande/Documents/Codex/ascend_mvp` is not currently a git repository, this is a curated continuation inventory rather than an exact commit diff.

## Primary Files Changed During This Build Cycle

### Frontend shell and shared UX

- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/src/App.jsx`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/src/styles.css`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/index.html`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/src/main.jsx`

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

### Frontend branding assets

- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/public/ascend-logo.webp`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/public/favicon.png`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/public/favicon.ico`

These support Ascend branding in the browser tab and UI shell.

### Backend API and application behavior

- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/api.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/services.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/openai_client.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/db.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/google_drive.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/storage.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/config.py`

These files carry the working backend for:

- role-based auth
- member profile and planner data
- evidence analysis and upload
- Google Drive storage behavior
- foldering and archive behavior
- messaging and read/unread logic
- leader assignment flows
- admin monitoring and debug flows
- attorney AI petition generation

### Tests used to hold the suite together

- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_api.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_openai_client.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_db.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_google_drive.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_storage.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_config.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/tests/test_server.py`

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
- Google Drive storage integration
- OpenAI evidence and petition generation
- operational fallback behavior when AI or integrations fail

## Best-Guess “Most Edited” Files

If someone needs to resume development quickly, start here first:

1. `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/src/App.jsx`
2. `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/frontend-react/src/styles.css`
3. `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/services.py`
4. `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/api.py`
5. `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/db.py`
6. `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/openai_client.py`

## Continuation Guidance

- use this file as the change inventory
- use `08-api-and-function-map.md` as the entry-point map
- use the portal threads for product intent and workflow behavior
- use the engineering threads for implementation direction

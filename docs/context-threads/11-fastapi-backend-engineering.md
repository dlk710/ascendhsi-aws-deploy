# Thread: FastAPI Backend Engineering

## Purpose

This thread defines the backend API and service skill required to continue Ascend.

The backend is the product contract between role portals, persistence, storage, AI, messaging, and operations.

## Current Code Ownership

Primary files:

- `app/api.py`
- `app/services.py`
- `app/config.py`

Current pressure point:

- `app/services.py` contains most business logic and should be decomposed carefully as features expand.

## Required Skill

Developers must be able to:

- design FastAPI route contracts
- validate user input and form data
- handle file uploads
- protect session-based role behavior
- preserve service-level fallback behavior
- map errors into stable API responses
- keep service methods testable
- separate API transport concerns from product workflow logic

## Formal Development Workflow

Before changing backend code:

1. Read `08-api-and-function-map.md`.
2. Identify the route, service method, and database tables involved.
3. Check whether the behavior crosses roles.
4. Add validation at the service boundary.
5. Record operational events for important success, fallback, and failure paths.
6. Update tests in `tests/`.

## Decomposition Direction

As the backend grows, split service logic by domain:

- auth and sessions
- member profile and planner
- evidence and folders
- messaging
- builder workflows
- leader assignments
- attorney petition workflows
- admin operations
- AI orchestration
- storage orchestration

Keep route names and response shapes stable while extracting internals.

## Production-Grade Expectations

Backend changes should include:

- explicit validation
- consistent errors
- durable persistence behavior
- authorization or actor checks for role-sensitive actions
- idempotent or safely retryable behavior where appropriate
- operational event tracking for critical workflows
- tests for happy path and failure path

## Chat Thread Starter

```text
Use the FastAPI Backend Engineering thread. Read 08-api-and-function-map.md before changing routes or services.
```

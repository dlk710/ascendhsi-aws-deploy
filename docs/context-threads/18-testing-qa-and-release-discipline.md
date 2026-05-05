# Thread: Testing, QA, And Release Discipline

## Purpose

This thread defines the testing and release skill required for formal Ascend development.

Tests protect the product contract across portals, API routes, storage, AI fallbacks, messaging, and admin operations.

## Current Code Ownership

Primary directory:

- `tests/`

Current test areas:

- API behavior
- config loading
- database initialization
- Google Drive integration
- OpenAI client fallback behavior
- server behavior
- storage behavior

## Required Skill

Developers must be able to:

- write focused unit and API tests
- cover role-sensitive behavior
- test failure and fallback paths
- keep tests independent of real external services
- verify frontend build when UI changes
- define release checks before deployment

## Formal Development Workflow

Before finishing a change:

1. Add or update tests for backend behavior.
2. Run the relevant Python test subset.
3. Run the React build for frontend changes.
4. Manually verify critical role flows when UI behavior changes.
5. Document any residual risk.

## Production-Grade Expectations

A production-ready change should have:

- backend tests for expected behavior
- backend tests for invalid or unauthorized behavior
- fallback tests for AI or storage changes
- schema tests for database changes
- frontend build verification for UI changes
- no dependency on live OpenAI or Google Drive in tests

## Release Checklist

Before production deployment:

- all tests pass
- frontend build passes
- config is environment-driven
- secrets are not committed
- AI fallback works
- storage failure behavior works
- admin health reflects integration status
- database backup and migration plan exists
- rollback path is known

## Chat Thread Starter

```text
Use the Testing, QA, And Release Discipline thread. Add tests before treating the feature as complete.
```


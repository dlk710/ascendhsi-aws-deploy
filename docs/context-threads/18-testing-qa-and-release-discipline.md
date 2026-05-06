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
- S3 storage integration
- OpenAI client fallback behavior
- server behavior
- storage behavior
- AWS deployment smoke checks

## Required Skill

Developers must be able to:

- write focused unit and API tests
- cover role-sensitive behavior
- test failure and fallback paths
- keep tests independent of real external services
- verify frontend build when UI changes
- define release checks before deployment
- validate live AWS role login and initial data APIs after deployment changes

## Formal Development Workflow

Before finishing a change:

1. Add or update tests for backend behavior.
2. Run the relevant Python test subset.
3. Run the React build for frontend changes.
4. Manually verify critical role flows when UI behavior changes.
5. Document any residual risk.
6. If deployed to AWS, verify CloudFront `/ready` and role-specific login/data APIs.

## Production-Grade Expectations

A production-ready change should have:

- backend tests for expected behavior
- backend tests for invalid or unauthorized behavior
- fallback tests for AI or storage changes
- schema tests for database changes
- frontend build verification for UI changes
- no dependency on live OpenAI or S3 in unit tests
- explicit live smoke checks for deployed AWS environments

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
- CloudFront serves the expected hashed frontend assets
- ECS service reaches the expected running task count after backend deployment
- S3 signed/private file access is verified for evidence links

## Chat Thread Starter

```text
Use the Testing, QA, And Release Discipline thread. Add tests before treating the feature as complete.
```

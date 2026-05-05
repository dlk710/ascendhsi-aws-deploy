# Thread: Admin Operations And Production Readiness

## Purpose

This thread defines the operational skill required to move Ascend toward production.

Admin and operations features are how the team detects, explains, and remediates system issues.

## Current Code Ownership

Primary files:

- `app/services.py`
- `app/api.py`
- `frontend-react/src/App.jsx`

Related docs:

- `docs/context-threads/05-admin-operations-portal.md`
- `docs/context-threads/07-integrations-and-ai.md`

## Required Skill

Developers must be able to:

- track operational events
- expose useful admin health views
- separate user errors from system errors
- provide remediation actions
- monitor OpenAI and storage health
- support production deployment readiness

## Formal Development Workflow

Before changing operations behavior:

1. Identify the operational signal required.
2. Decide whether it belongs in dashboard metrics, recent failures, member debug, or alerts.
3. Record events for success, fallback, and failure where useful.
4. Add admin UI only when it supports actual remediation or diagnosis.
5. Update tests for admin and event behavior.

## Production-Grade Expectations

Operations changes should include:

- health checks by integration
- clear error categories
- usage metrics by feature area
- session remediation
- per-member issue timeline
- no sensitive secrets in logs or UI
- environment-aware deployment settings

## Future Production Direction

Add:

- structured alerts
- issue timeline per member
- production logging provider
- metrics dashboard
- deployment runbook
- backup and restore process
- role-based admin permissions

## Chat Thread Starter

```text
Use the Admin Operations And Production Readiness thread. Add operational visibility for any feature that can fail in production.
```


# Thread: Data Modeling And Migrations

## Purpose

This thread defines the data modeling skill required to continue Ascend as the long-lived base product.

SQLite is the current persistence layer. Production evolution will require careful schema changes and migration discipline.

## Current Code Ownership

Primary file:

- `app/db.py`

Related files:

- `app/services.py`
- `tests/test_db.py`
- `data/db/ascend_suite.sqlite`

## Required Skill

Developers must be able to:

- evolve SQLite schemas without breaking existing local data
- model role assignments and case records clearly
- preserve relationships between clients, cases, evidence, folders, planner items, sessions, messages, and operational events
- add indexes for high-traffic workflows
- plan future migration from SQLite to production database infrastructure

## Formal Development Workflow

Before changing schema:

1. Identify all service methods that read or write the table.
2. Add fields with safe defaults when existing data may exist.
3. Update seed data only when needed for demo or local continuity.
4. Add or update database tests.
5. Verify API tests still pass.

## Production-Grade Expectations

Data changes should include:

- stable primary keys
- explicit timestamps
- clear ownership fields such as `client_id`, `case_id`, role, or account id
- indexes for common filters
- no silent data loss
- forward-compatible migration thinking

## Migration Direction

For production, prepare for:

- explicit migration files
- environment-specific database URLs
- backup and restore flow
- audit trails for sensitive role actions
- separation of demo seed data from production data

## Chat Thread Starter

```text
Use the Data Modeling And Migrations thread. Inspect app/db.py and affected service queries before changing persistence.
```

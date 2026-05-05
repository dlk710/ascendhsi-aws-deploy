# Thread: Messaging And Collaboration Systems

## Purpose

This thread defines the collaboration skill required for Ascend.

Messaging is a shared role-aware layer across the suite, not a side feature.

## Current Code Ownership

Primary files:

- `app/services.py`
- `app/api.py`
- `frontend-react/src/App.jsx`

Related docs:

- `docs/context-threads/06-messaging-and-collaboration.md`

## Required Skill

Developers must be able to:

- preserve role-aware recipient rules
- maintain thread grouping
- handle unread and urgent state
- support cross-role collaboration without breaking boundaries
- connect messages to tasks, evidence, or attorney questions when needed

## Formal Development Workflow

Before changing messaging:

1. Read `06-messaging-and-collaboration.md`.
2. Identify the actor role and allowed recipients.
3. Confirm thread, reply, unread, and delete behavior.
4. Update both service tests and UI state handling.
5. Confirm the change does not create unauthorized role visibility.

## Production-Grade Expectations

Messaging changes should include:

- actor validation
- recipient validation
- clear unread logic
- consistent deletion semantics
- auditability for sensitive messages
- optional attachment policy before adding files

## Future Production Direction

Add:

- attachments inside messages
- unread and urgent filters
- task creation from messages
- evidence links inside threads
- notification delivery
- message retention policy

## Chat Thread Starter

```text
Use the Messaging And Collaboration Systems thread. Preserve role-aware recipient rules before adding message features.
```


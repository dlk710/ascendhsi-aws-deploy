# Feature Catalog

This document is the repository-level inventory of what the Ascend product suite currently does.

Use it when you need to understand the product quickly without reading implementation code first.

## Product Scope

Ascend is a role-based EB1A operations platform with five active portal experiences:

- Member
- Profile Builder
- Leader
- Attorney
- Admin

All portals operate on the same underlying case record and share evidence, assignments, messaging, support, and operational visibility in role-appropriate ways.

## Shared Capabilities

- Portal-specific authentication with separate member, builder, and staff login flows
- Session-backed role context stored in the browser
- Threaded messaging across product roles
- Evidence upload, categorization, and organization
- S3-backed file storage with local metadata mirroring fallback
- Operational event logging for diagnostics and usage reporting
- Support-ticket submission from every portal
- AI-assisted workflows with fallback behavior when AI is unavailable

## Member Portal

Primary user: member / client

Current capabilities:

- View member home dashboard with readiness and evidence metrics
- Maintain structured profile information across identity, professional, credentials, narrative, and criterion tabs
- Plan future activities through the event planner
- Upload evidence with AI-suggested or manual routing
- Review criterion-based evidence organization
- Use folder-based evidence workspace
- Send and receive role-based messages
- Submit technical support tickets

Primary frontend areas:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`

Primary backend areas:

- `app/api.py`
- `app/services.py`

## Profile Builder Portal

Primary user: profile builder

Current capabilities:

- View builder dashboard and assigned-member summary
- Review assigned members and their evidence state
- Manage opportunity suggestions and next steps
- Create and review builder-side tasks
- Open evidence files through S3-backed links
- Use Ascend Navigator in builder context
- Send and receive messages
- Submit technical support tickets

## Leader Portal

Primary user: team lead / operations lead

Current capabilities:

- View executive overview metrics
- Review member progress and readiness
- Monitor domain mix, pipeline risk, and capacity signals
- Manage assignment oversight
- Invite and route members
- Assume builder or attorney perspective from leader workflows
- Use Ascend Navigator in leader context
- Send and receive messages
- Submit technical support tickets

## Attorney Portal

Primary user: attorney

Current capabilities:

- Open assigned case context through attorney home
- Review member dossier and attorney case detail
- Review evidence separately from profile detail
- Use petition generator support flows
- Review batch intake sessions
- Open S3-backed evidence links in a new tab
- Use Ascend Navigator in attorney context
- Send and receive messages
- Submit technical support tickets

## Admin Portal

Primary user: admin / operations

Current capabilities:

- Monitor operations snapshot metrics
- Review system health and dependency status
- Inspect debug console and operational events
- Review support-ticket queue with root-cause summaries and actions
- Access cross-suite messaging

## AI-Assisted Features

Current AI use cases:

- evidence intake classification and summarization
- attorney petition-generation support
- Ascend Navigator contextual Q&A
- IT support triage summarization

Current design rule:

- every AI-assisted flow must degrade gracefully when OpenAI is unavailable
- business workflows must remain operable through deterministic fallback behavior

## Storage And Evidence Model

- Evidence metadata is stored locally in SQLite
- Files are stored in Amazon S3 when cloud storage is enabled
- Evidence is grouped by EB1A criterion and may also be organized into workspace folders
- Portals use openable evidence links rather than raw storage identifiers

## Operational Support

- Every portal exposes the IT support entry point
- Support requests can include priority, blocking state, description, and attachments
- Admin receives summarized ticket context and recommended follow-up actions

## Primary Product References

- `README.md`
- `docs/aws-deployment.md`
- `docs/solution-architecture.md`
- `docs/verification-notes.md`
- `docs/missing-features.md`
- `docs/context-threads/README.md`
- `docs/context-threads/08-api-and-function-map.md`

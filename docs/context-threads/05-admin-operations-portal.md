# Thread: Admin / Operations Portal

## Purpose

Admin / Operations Portal keeps the platform supportable in live use.

It is responsible for operational visibility and issue support, not member-facing work.

## Current Pages

- `Admin Home`
- `System Health`
- `Support Tickets`
- `Debug Console`
- `Messages`

## Current Required Metrics

The user explicitly requested that admin see:

- how many calls were made to OpenAI endpoints
- how many members are using AI suggestions
- how many members are active
- whether there are operational errors
- health status of portals and connections

## Current Support Requirement

If a member has a problem, admin should be able to debug and help fix it.

## Admin Home

Current behavior:

- operational metrics
- high-level usage
- member movement summary
- workload and support visibility

## System Health

Current behavior:

- separate page from home
- keeps portal and integration health in its own surface
- includes platform and connected service status
- includes case movement and stage distribution

## Support Tickets

Current behavior:

- dedicated queue for inbound support work
- keeps support operations separate from systems health and debug actions
- complements messaging instead of replacing it

## Debug Console

Current behavior:

- dedicated troubleshooting area
- inspect member issues
- review recent errors
- reset member sessions if needed

## Messaging Rules

Admin can message anyone.

## Key Backend Dependencies

Important service methods:

- `admin_operational_dashboard`
- `member_issue_debug`
- `reset_member_sessions`
- `record_operational_event`
- `message_center`
- `send_message`

## Portal Health Model

Current health areas include:

- Member Portal
- Profile Builder Portal
- Leader Portal
- Attorney Portal
- Admin Portal
- FastAPI
- PostgreSQL / SQLite depending on environment
- Amazon S3
- ECS / ALB / CloudFront health through runtime checks and log review
- OpenAI

## Next Good Enhancements

- per-member issue timeline
- easier operational remediation actions
- structured alerts instead of passive dashboard-only visibility
- richer support analytics and escalation workflows

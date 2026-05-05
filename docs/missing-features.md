# Missing Features And Follow-Up Work

This document lists known product gaps, deferred engineering work, and production-hardening items for the Ascend product suite.

It should be updated whenever features are partially implemented, intentionally deferred, or blocked by environment constraints.

## Product Gaps

### Authentication And Identity

- No production-grade identity provider integration yet
- Seeded demo credentials are still present for local use
- Password-reset and account-recovery flows are not implemented
- Multi-factor authentication is not implemented

### Member And Staff Workflows

- No formal notifications system outside in-app messaging
- Email delivery for invites and support acknowledgements is not connected
- Some seeded role experiences still rely on sample/demo data rather than live workflow ingestion
- Workflow approvals, escalations, and service-level timers are not fully modeled

### AI Workflows

- Some AI-assisted flows still rely on fallback mode when `OPENAI_API_KEY` is not present
- No provider-agnostic AI abstraction exists yet; `app/openai_client.py` is still the only live provider client
- Prompt versioning and model-behavior evaluation are not formalized
- No structured human-review queue exists yet for low-confidence AI outputs
- No formal citation rendering model exists beyond current storage-backed references

### Data And Persistence

- SQLite is still the active persistence layer
- No migration framework is in place yet
- No backup, restore, or retention automation is configured
- Demo seed data and long-lived application data are still mixed in the same local database model
- Seed-data integrity still needs cleanup in some staff datasets, including duplicated role identities

### Storage

- No database migration to PostgreSQL has been completed yet; SQLite remains the current persistence engine
- No formal pluggable storage-provider abstraction exists beyond the new S3-first path
- No resumable upload or large-file scanning pipeline exists yet
- Retention and deletion policy enforcement is not fully implemented

### Frontend Architecture

- `frontend-react/src/App.jsx` is still a large orchestration file and should eventually be decomposed into portal-level modules
- Shared design tokens and UI primitives are not yet extracted into a reusable component system
- Accessibility review and keyboard-navigation hardening are still incomplete
- Shared login UX is still vulnerable to confusing cross-role browser autofill behavior during demos

### Backend Architecture

- Service logic is still concentrated heavily in `app/services.py`
- More domain-specific service modules would improve readability and ownership
- Background-job infrastructure is not present for long-running operations

### Testing And Delivery

- Full end-to-end browser regression automation is not yet in place
- CI/CD pipelines are not fully established in the repository
- No environment matrix exists yet for local, staging, and production behavior verification

## Engineering Hardening Priorities

Highest-value next steps:

1. Split large frontend and backend orchestration files into domain modules
2. Introduce formal migrations and environment-aware database configuration
3. Add production-safe secret handling and identity flows
4. Add CI coverage for backend tests and frontend build validation
5. Add end-to-end regression coverage for the five portal experiences

## Documentation Rule

Whenever a feature is added, changed, or deferred, update:

- `docs/feature-catalog.md` for implemented behavior
- this file for missing or deferred work
- the relevant context thread in `docs/context-threads/`

# Verification Notes

This document records recent live verification results for the Ascend product suite so future contributors can distinguish product behavior from environment-specific gaps.

## Verification Run: 2026-05-05

### Scope

- Live frontend at `http://127.0.0.1:3001`
- Live backend at `http://127.0.0.1:8000`
- Portal smoke tests across Member, Profile Builder, Leader, Attorney, and Admin
- Direct auth and health endpoint checks

### Overall Result

Status: pass with environment and seed-data caveats

The core product suite is functioning and the major portal surfaces match the intended design structure:

- shared role-based login entry point
- portal-specific left-rail navigation
- role-specific dashboards
- organized evidence groupings
- shared IT support entry point
- Ascend Navigator available in Builder, Leader, and Attorney contexts

### Manual Portal Verification

#### Member Portal

- Member home loaded successfully for `vas@ascendhsi.com`
- Left navigation showed `Member Home`, `Profile`, `Event Planner`, `Evidence Intake`, and `Messages`
- Evidence map rendered criterion-based organization and readiness metrics

#### Profile Builder Portal

- Builder dashboard loaded successfully for `builder@ascendhsi.com`
- `Assigned Members` rendered roster, selected-member detail, tasks, and evidence grouped by criterion
- S3-backed evidence links rendered in the member detail area
- Ascend Navigator launcher and IT support launcher were present

#### Leader Portal

- Executive overview loaded successfully for `leader@ascendhsi.com`
- `Member Review` rendered roster, selected-member detail, and evidence grouped by criterion
- Assume-view controls for CEO, Builder, and Attorney perspectives were present
- Ascend Navigator launcher and IT support launcher were present

#### Attorney Portal

- Attorney caseboard loaded successfully for `attorney@ascendhsi.com`
- `Evidence Review` rendered the selected member's evidence grouped the same way as the member workspace
- Evidence items rendered openable storage-backed links
- Ascend Navigator launcher and IT support launcher were present

#### Admin Portal

- Operations snapshot loaded successfully for `admin@ascendhsi.com`
- `System Health` rendered portal availability, backend availability, and dependency status
- Admin support surface rendered correctly

### Direct API Smoke Checks

The following runtime checks passed:

- `GET /health`
- `POST /api/auth/login`
- `POST /api/builder/auth/login`
- `POST /api/staff/auth/login`
- `GET /api/leader/dashboard`

These checks confirmed that authentication and core leader dashboard data were being served successfully by the active backend runtime.

### Caveats Found

#### External integrations were degraded in this runtime

Admin system health reported:

- `Amazon S3`: degraded when buckets are not configured in the runtime
- `OpenAI`: degraded

Interpretation:

- core UI flows still work
- deterministic fallback behavior remains important
- the full design intent for live S3-backed operations and live OpenAI-backed workflows depends on environment configuration being loaded correctly at backend startup

#### Shared login can be confusing after prior sessions

The shared login page can show stale browser-autofilled credentials from a different portal account after logout. This appears to be a browser-state or UX-isolation issue rather than a backend auth failure, but it is still confusing during demos.

#### Seed data contains a duplicate attorney identity

The live leader dashboard API returned duplicate attorney entries for `priya.nair@ascendhsi.com` in capacity data. This is a seed-data integrity issue and should be cleaned up before wider demos or analytics decisions rely on staff counts.

## Recommended Follow-Up

1. Ensure runtime environment loading is standardized so S3 and OpenAI health do not silently degrade after backend restarts.
2. Clean up duplicated seed staff records and re-run dashboard validation.
3. Isolate or suppress cross-role browser autofill on the shared login screen.
4. Add automated browser smoke coverage for the five portal helper-login flows.

## Related Documents

- `docs/solution-architecture.md`
- `docs/missing-features.md`
- `docs/feature-catalog.md`

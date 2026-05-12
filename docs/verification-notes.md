# Verification Notes

This document records recent live verification results for the Ascend product suite so future contributors can distinguish product behavior from environment-specific gaps.

## Verification Run: 2026-05-12 Release Readiness Guardrail

### Scope

- Product repo after AWS readiness endpoint restoration
- AWS deployment repo after matching readiness endpoint restoration and ECS failure diagnostics
- Backend readiness behavior for local and AWS-style deployments

### Overall Result

Status: pass locally, AWS frontend deployed, backend ECS stabilization fix in progress

The backend now exposes a lightweight `/ready` endpoint in the shared product code, matching the AWS deployment workflow and load-balancer smoke checks without running the full admin dashboard on every health probe. CORS origins can also be configured with `ASCEND_CORS_ORIGINS` while preserving local defaults. The AWS deployment path now also honors runtime path overrides, older and newer S3 evidence bucket environment names, and a 120-second ECS health-check grace period for safer Fargate rollouts.

### Automated Checks

- Product repo Python regression suite: `154 passed`
- Product repo React production build: pass
- AWS deployment repo Python regression suite: `159 passed`
- AWS deployment repo React production build: pass
- Direct local `GET /ready` through FastAPI TestClient: `200`
- `/ready` regression test confirms the health probe does not instantiate the full service layer.
- Runtime config regression tests confirm AWS container paths can be redirected to `/tmp/ascend`.
- Evidence S3 regression tests confirm AWS deployment env names map to the active and archive evidence buckets.

### Release Notes

- The AWS backend deployment workflow now prints recent ECS service events and stopped-task details if the service does not stabilize.
- ECS service updates now set `health-check-grace-period-seconds` to `120`; Terraform mirrors the same setting.
- Local runtime data under `data/` remains intentionally uncommitted.

## Verification Run: 2026-05-12

### Scope

- Product repo after referral-program implementation
- Local backend at `http://127.0.0.1:8000`
- Local React frontend at `http://127.0.0.1:3001`
- Portal bootstrap regression for Member, Profile Builder, Leader, Attorney, and Admin
- Targeted backend/API/service tests

### Overall Result

Status: pass locally, pending AWS deployment verification

The member portal loading hang was traced to local runtime URL handling. Local `runtime-config.js` intentionally sets `apiUrl` to an empty string so the Vite proxy can serve `/api/*`; the previous `getJson()` path built `new URL("/api/...")` without a base URL, throwing before dashboard calls were sent. The fix uses a shared URL builder with `window.location.origin` as the base for relative API paths.

### Functional Changes Verified

- Member portal loaded past `Loading Ascend portal...` and rendered `Member Home`.
- Protected member dashboard APIs returned live data with a valid session token.
- Profile Builder, Leader, Attorney, and Admin bootstrap API calls returned `200`.
- Referral program backend tables and APIs were added for member referrals and leader settings/status management.
- Member Portal now includes a configurable `Refer & Earn` section when the program is enabled.
- Leader Portal now includes referral incentive configuration, referral metrics, and referral status tracking.
- A portal bootstrap recovery panel now displays retry and sign-out actions if future hydration fails instead of leaving users on an indefinite spinner.

### Local API Smoke Checks

- Member: `/api/auth/me`, `/api/member/dashboard`, `/api/evidence`, `/api/member/planner`, `/api/member/profile`, `/api/criteria`, `/api/member/referrals`
- Profile Builder: `/api/builder/auth/me`, `/api/builder/dashboard`, `/api/builder/members`, `/api/builder/opportunities`, `/api/criteria`
- Leader: `/api/staff/auth/me`, `/api/leader/dashboard`, `/api/criteria`, `/api/builder/opportunities`, `/api/leader/referrals`
- Attorney: `/api/staff/auth/me`, `/api/attorney/members`, `/api/criteria`
- Admin: `/api/staff/auth/me`, `/api/admin/operations`, `/api/admin/issue-log`, `/api/admin/costs`, `/api/builder/members`, `/api/criteria`

### Automated Checks

- `python -m pytest tests/test_db.py tests/test_api.py tests/test_leader_service.py`: `97 passed`
- `cd frontend-react && vite build`: pass

### Notes

- Local runtime data under `data/` is not committed.
- AWS verification should be repeated after the deployment repo receives the same source updates and CloudFront invalidation completes.

## Verification Run: 2026-05-10

### Scope

- Product repo after the team-dev workflow update
- AWS deployment repo after the matching dev-environment update
- Shared AWS dev endpoint at `https://dq5ab404dg57q.cloudfront.net`
- Local React frontend using `pnpm run dev:aws`
- Backend and frontend regression checks

### Overall Result

Status: pass

The current baseline supports local UX review against the shared AWS dev backend. The local Vite server proxies relative API calls to AWS dev, while AWS continues to serve the deployed product through the CloudFront fallback URL until the branded dev endpoint is validated.

### Runtime Health

- `GET https://dq5ab404dg57q.cloudfront.net/ready` returned healthy dependency readiness.
- AWS dev backend reported RDS PostgreSQL, S3 storage, and OpenAI readiness.
- ECS was running task definition `ascend-dev-backend:36` after the latest deployment.
- Frontend runtime config was served through CloudFront after invalidation.

### Local UX Flow

- `cd frontend-react && pnpm run dev:aws` started the local Vite portal.
- Vite selected the next available port when `3001` was occupied.
- `GET /ready` through the local Vite server proxied successfully to AWS dev.
- The app shows the local-environment badge so developers can tell when they are reviewing local UI against AWS dev data.

### Automated Checks

- Product repo React build: pass
- Product repo Python regression suite: `145 passed`
- AWS deployment repo React build: pass
- AWS deployment repo Python regression suite: `111 passed`
- Diff whitespace validation: pass in both repos

### Environment Notes

- Target branded dev URL: `https://dev-portal.ascendhsi.com`
- Active fallback URL: `https://dq5ab404dg57q.cloudfront.net`
- ACM certificate for the branded dev URL is pending DNS validation because the AWS account does not currently host the `ascendhsi.com` Route 53 zone.
- Required DNS validation CNAME: `_fe0e9a32839d8195eb01703489086da3.dev-portal.ascendhsi.com` -> `_cb421196fe2de034e98a52b7cf429f70.jkddzztszm.acm-validations.aws`

## Verification Run: 2026-05-06

### Scope

- Live frontend at `http://127.0.0.1:3000`
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
- Storage-backed evidence links rendered in the member detail area
- Ascend Navigator launcher and IT support launcher were present

#### Leader Portal

- Executive overview loaded successfully for `leader@ascendhsi.com`
- `Member Review` rendered roster, selected-member detail, and evidence grouped by criterion
- Assume-view controls for CEO, Builder, and Attorney perspectives were present
- Ascend Navigator launcher and IT support launcher were present

#### Attorney Portal

- Attorney caseboard loaded successfully for `attorney@ascendhsi.com` and `marcus.reed@ascendhsi.com`
- Attorney Home stayed portfolio-level and no longer exposed member-specific detail cards
- Shared left sidebar resize handle worked in the live browser
- Endeavor Letter Generator rendered attorney-editable prompt fields including `Who you are`
- Endeavor letter review mode rendered as natural letter paragraphs instead of obvious numbered bullet-style sections
- `Evidence Review` rendered the selected member's evidence grouped the same way as the member workspace
- Evidence items rendered openable storage-backed links
- Ascend Navigator launcher and IT support launcher were present

#### Admin Portal

- Operations snapshot loaded successfully for `admin@ascendhsi.com`
- `System Health` rendered compact portal availability, backend availability, dependency status, and response-time trend rows
- Admin support surface rendered as a concise queue with compact, color-coded ticket line items

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

- `Storage provider`: degraded
- `OpenAI`: degraded

Interpretation:

- core UI flows still work
- deterministic fallback behavior remains important
- the full design intent for live storage-backed operations and live OpenAI-backed workflows depends on environment secrets being loaded correctly at backend startup

#### Shared login can be confusing after prior sessions

The shared login page can show stale browser-autofilled credentials from a different portal account after logout. This appears to be a browser-state or UX-isolation issue rather than a backend auth failure, but it is still confusing during demos.

#### Seed data contains a duplicate attorney identity

The live leader dashboard API returned duplicate attorney entries for `priya.nair@ascendhsi.com` in capacity data. This is a seed-data integrity issue and should be cleaned up before wider demos or analytics decisions rely on staff counts.

## Recommended Follow-Up

1. Ensure runtime secret loading is standardized so storage and OpenAI health do not silently degrade after backend restarts.
2. Clean up duplicated seed staff records and re-run dashboard validation.
3. Isolate or suppress cross-role browser autofill on the shared login screen.
4. Add automated browser smoke coverage for the five portal helper-login flows.

## Related Documents

- `docs/solution-architecture.md`
- `docs/missing-features.md`
- `docs/feature-catalog.md`

# Verification Notes

This document records recent live verification results for the Ascend product suite so future contributors can distinguish product behavior from environment-specific gaps.

## Verification Run: 2026-05-10

### Scope

- AWS deployment repo after the team-dev workflow update
- Shared AWS dev endpoint at `https://dq5ab404dg57q.cloudfront.net`
- Local React frontend using `pnpm run dev:aws`
- Frontend and backend GitHub Actions deployment runs
- Backend and frontend regression checks

### Overall Result

Status: pass

The AWS dev deployment is live through the CloudFront fallback URL. The deployment repo now documents the intended branded dev endpoint and keeps the local-to-AWS development loop explicit for multiple developers.

### Runtime Health

- `GET https://dq5ab404dg57q.cloudfront.net/ready` returned healthy dependency readiness.
- AWS dev backend reported RDS PostgreSQL, S3 storage, and OpenAI readiness.
- ECS was running task definition `ascend-dev-backend:36`.
- Frontend assets were deployed to S3 and served through CloudFront distribution `EV6WT9DUO1GQH`.

### Deployment Verification

- Frontend GitHub Actions run `25628949512`: success
- Backend GitHub Actions run `25628949513`: success
- Backend image tag deployed from commit `fd3d015`
- AWS deployment repo build: pass
- AWS deployment repo Python regression suite: `111 passed`

### Environment Notes

- Target branded dev URL: `https://dev-portal.ascendhsi.com`
- Active fallback URL: `https://dq5ab404dg57q.cloudfront.net`
- ACM certificate for the branded dev URL is pending DNS validation because the AWS account does not currently host the `ascendhsi.com` Route 53 zone.
- Certificate ARN: `arn:aws:acm:us-east-1:027903151318:certificate/126ffbc1-caf2-4098-a51a-42ea6fc1c425`
- Required DNS validation CNAME: `_fe0e9a32839d8195eb01703489086da3.dev-portal.ascendhsi.com` -> `_cb421196fe2de034e98a52b7cf429f70.jkddzztszm.acm-validations.aws`

## Verification Run: 2026-05-06

### Scope

- Live AWS frontend at `https://dq5ab404dg57q.cloudfront.net`
- CloudFront distribution `EV6WT9DUO1GQH`
- Frontend S3 bucket `ascend-frontend-dev-027903151318`
- Backend ECS Fargate service `ascend-dev-backend`
- RDS PostgreSQL database `ascend-dev-postgres`
- S3 active/archive storage buckets
- Portal login and initial data smoke checks across Member, Profile Builder, Leader, Attorney, and Admin

### Overall Result

Status: pass

The AWS-hosted product suite is functioning and the recent login performance change is live. The frontend now renders the portal shell immediately after authentication and hydrates role-specific data inside the portal instead of holding users on a full-screen loading state.

### Runtime Health

- `GET /ready` through CloudFront returned HTTP `200`
- S3 storage reported healthy for `client-data-dev-027903151318`
- OpenAI reported healthy with configured model detail
- CloudFront served the new hashed frontend assets after invalidation

### Portal Smoke Results

The following login and initial data checks returned HTTP `200`:

- Member: `POST /api/auth/login`, `/api/member/dashboard`, `/api/evidence`, `/api/member/planner`, `/api/member/profile`, `/api/criteria`, `/api/messages`
- Profile Builder: `POST /api/builder/auth/login`, `/api/builder/dashboard`, `/api/builder/members`, `/api/builder/opportunities`, `/api/criteria`
- Leader: `POST /api/staff/auth/login`, `/api/leader/dashboard`, `/api/criteria`, `/api/builder/opportunities`
- Attorney: `POST /api/staff/auth/login`, `/api/attorney/members`, `/api/criteria`
- Admin: `POST /api/staff/auth/login`, `/api/admin/operations`, `/api/builder/dashboard`, `/api/builder/members`, `/api/criteria`

Selected-member detail and evidence checks also passed for Builder, Leader, Attorney, and Admin contexts.

### Performance Observation

Login APIs completed in roughly `0.3s` to `0.5s` during the verification pass, and initial data APIs completed within sub-second timings. The frontend no longer blocks the whole portal on those data calls after authentication.

### Automated Checks

- React production build: pass
- Python regression suite: `77 passed`
- Diff whitespace validation: pass

### Notes

- Local macOS build shells can reject Rollup native optional binaries because of code signing. The repo includes `@rollup/wasm-node`; use the wasm Rollup path when this local environment issue appears.
- The active remotes for this work are GitHub repositories, not Bitbucket remotes.

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

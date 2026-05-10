# Ascend Team Development Workflow

This workflow is optimized for fast UX iteration while keeping backend data and AWS integrations realistic.

## Daily Local UX Flow

Run the React portal locally while forwarding API calls to the AWS dev backend:

```bash
cd frontend-react
pnpm run dev:aws
```

Open:

```text
http://127.0.0.1:3001
```

The browser calls local relative paths such as `/api/auth/login`; Vite proxies them to the AWS dev endpoint. This avoids CORS friction and keeps frontend changes reviewable before deployment.

## Local Backend Flow

Use this only when changing backend behavior locally:

```bash
cd frontend-react
pnpm run dev:local
```

This forwards API traffic to:

```text
http://127.0.0.1:8000
```

## Environment URLs

Target branded environment URLs:

```text
dev:     https://dev-portal.ascendhsi.com
test:    https://test-portal.ascendhsi.com
prod:    https://portal.ascendhsi.com
```

Until DNS and SSL validation are completed for the dev custom domain, AWS dev remains available through the CloudFront distribution URL:

```text
https://dq5ab404dg57q.cloudfront.net
```

## Multi-Developer Guardrails

- Work in a personal Git branch for every change.
- Use AWS dev for shared integration, not production data.
- Prefix fabricated test records with a developer identifier, for example `lohith-test-*`, `codex-test-*`, or `dev-alex-*`.
- Keep destructive testing in dev only, and rely on soft-delete/archive flows where available.
- Commit small, focused changes so AI and human reviews stay targeted.
- Run frontend build and backend tests before merge.
- Merge through PR review before deploying shared AWS dev.

## Deployment Path

Recommended promotion path:

```text
developer branch -> pull request -> main -> AWS dev -> test/staging -> production
```

AWS dev is the shared integration environment. Test/staging should be used for business review, and production should only receive stable release candidates.

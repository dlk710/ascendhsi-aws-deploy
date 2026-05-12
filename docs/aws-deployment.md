# AWS Deployment

This document describes the AWS shape for deploying the Ascend product suite after the S3 storage pivot.

## What Is In This Branch

- S3-first storage for active evidence and archive routing
- runtime-configurable frontend API host
- backend CORS and path configuration driven by environment
- readiness endpoint for load balancers and container health checks
- Athena-first operational analysis with logs routed to S3 instead of a CloudWatch-centric monitoring stack
- non-blocking portal hydration after login, so role shells render while live data refreshes
- relative frontend API URL handling for local Vite proxy, CloudFront, and future custom domains
- member and leader referral-program workflows with configurable incentives and payout tracking
- Dockerfiles and AWS deployment artifacts under `deploy/aws/`

## Current Dev Deployment

The active dev environment is deployed in AWS account `027903151318`, region `us-east-2`.

| Layer | AWS resource |
|---|---|
| Frontend CDN | CloudFront distribution `EV6WT9DUO1GQH` |
| Frontend origin | S3 bucket `ascend-frontend-dev-027903151318` |
| Backend compute | ECS Fargate service `ascend-dev-backend` on cluster `ascend-dev-cluster` |
| Backend image | ECR repository `027903151318.dkr.ecr.us-east-2.amazonaws.com/ascend-dev-backend` |
| API origin | ALB `ascend-dev-api` |
| Database | RDS PostgreSQL `ascend-dev-postgres` |
| Active files | S3 bucket `client-data-dev-027903151318` |
| Archive files | S3 bucket `client-data-archive-dev-027903151318` |
| Log storage | S3 bucket `ascend-observability-logs-dev-027903151318` |
| Athena results | S3 bucket `ascend-athena-results-dev-027903151318` |
| Observability queries | Athena workgroup `ascend-dev-observability`, database `ascend_dev_observability` |
| Secrets | `ascend-dev/backend/database-url`, `ascend-dev/backend/openai-api-key` |

The target branded dev endpoint is:

```text
https://dev-portal.ascendhsi.com
```

Until DNS and SSL validation are completed, the current public dev endpoint is:

```text
https://dq5ab404dg57q.cloudfront.net
```

The ALB DNS name is an API origin, not the product-suite user URL.

Human access to this dev account is documented in `docs/aws-human-access.md`. Daily work should use the IAM user `lohith-dev-admin` and switch into MFA-required roles instead of using root.

Current ACM certificate request for `dev-portal.ascendhsi.com`:

```text
arn:aws:acm:us-east-1:027903151318:certificate/126ffbc1-caf2-4098-a51a-42ea6fc1c425
```

DNS validation still needed:

```text
CNAME _fe0e9a32839d8195eb01703489086da3.dev-portal.ascendhsi.com
  -> _cb421196fe2de034e98a52b7cf429f70.jkddzztszm.acm-validations.aws
```

## Recommended AWS Services

### Required

- Amazon S3
  - one bucket for active uploads
  - one bucket for archived evidence, or one bucket with an archive prefix
- Amazon CloudFront
  - frontend CDN and HTTPS termination for the React app
- AWS Certificate Manager
  - TLS certificate for the frontend and API domains
- Amazon ECS on AWS Fargate
  - container runtime for the FastAPI backend
- Amazon Elastic Container Registry
  - stores the backend and optional frontend container images
- Application Load Balancer
  - routes HTTPS traffic to backend tasks and health checks `/health` and `/ready`
- AWS Secrets Manager
  - stores `OPENAI_API_KEY` and any private application secrets
- Amazon Athena
  - ad hoc and saved SQL analysis for ALB, CloudFront, and backend log data in S3

### Strongly Recommended

- AWS WAF
  - protects the frontend and API edge
- AWS IAM
  - task roles for backend access to S3 and Secrets Manager
- Amazon Route 53
  - DNS for frontend and API domains
- AWS Glue Data Catalog
  - catalog boundary for Athena log datasets

### Needed For True Horizontal Scale

- Amazon RDS for PostgreSQL or Amazon Aurora PostgreSQL-Compatible
  - the application now supports external database URLs, so cloud deployments can move off SQLite cleanly
- Amazon ElastiCache for Redis
  - recommended for future queueing, caching, and session coordination

## Storage Design

### Active Storage

- store active uploads in S3 with `INTELLIGENT_TIERING` or `STANDARD`
- keep evidence links as signed URLs unless a private distribution URL strategy is introduced

### Archive Storage

- archive evidence into a separate bucket or archive prefix
- default app-level archive move can use `GLACIER_IR`
- lifecycle rules can later transition older archive objects into `DEEP_ARCHIVE`

## Observability Shape For This Repo

This deployment repo intentionally avoids building a CloudWatch-centered monitoring layer for now.

### What Gets Logged

- Application Load Balancer access logs
  - delivered directly into S3
- CloudFront access logs
  - delivered into S3

### What Athena Is Used For

- recent backend error review
- ALB `4xx` and `5xx` analysis
- CloudFront path, status, and cache-behavior review
- cost-aware historical troubleshooting without keeping long-lived log infrastructure

### Tradeoff

This is cheaper and simpler for historical analysis, but it is not real-time alerting. AWS still emits native service telemetry, but this repo does not currently add CloudWatch dashboards or alarms on top of it.

## Deployment Layout

### Frontend

- build React assets with Vite
- serve the compiled app through CloudFront
- inject `window.ASCEND_RUNTIME_CONFIG.apiUrl` at deploy time

### Backend

- package the FastAPI app into a container
- run on ECS Fargate behind an ALB
- expose `/health` and `/ready`
- pass config through environment variables and Secrets Manager
- keep a 120-second ECS health-check grace period so new tasks can start cleanly before ALB replacement decisions are made

### Data

- local development can use SQLite
- AWS dev uses RDS PostgreSQL through `ASCEND_DATABASE_URL`
- multi-task backend scaling should use PostgreSQL or Aurora PostgreSQL-compatible storage

## Release Procedure

### Frontend

1. Run `pnpm install --frozen-lockfile` if dependencies are not present.
2. Run `pnpm run build` from `frontend-react/`.
3. Sync `frontend-react/dist/` to `s3://ascend-frontend-dev-027903151318/`.
4. Create a CloudFront invalidation for distribution `EV6WT9DUO1GQH`.
5. Verify the live `index.html` references the new hashed assets.

### Backend

1. Build the backend image from `deploy/aws/backend.Dockerfile`.
2. Push the image to ECR repository `ascend-dev-backend`.
3. Apply Terraform with the image digest, not a mutable tag, when possible.
4. Confirm ECS service `ascend-dev-backend` reaches the expected running task count.
5. Verify `/health`, `/ready`, and role login APIs through CloudFront.

### Verification Commands

```bash
python3 -m pytest -q
cd frontend-react && pnpm run build
curl -sS https://dq5ab404dg57q.cloudfront.net/ready
```

For portal smoke tests, validate login and initial data APIs for Member, Profile Builder, Leader, Attorney, and Admin.

The May 12, 2026 referral release should also validate:

- `GET /api/member/referrals`
- `POST /api/member/referrals`
- `GET /api/leader/referrals`
- `PATCH /api/leader/referrals/settings`
- `PATCH /api/leader/referrals/{referral_id}`
- Member and Leader portal hydration should move past `Loading Ascend portal...` or show the retry panel if a dependency fails.

## Environment Variables

### Backend

- `ASCEND_APP_NAME`
- `ASCEND_DATABASE_URL`
- `ASCEND_DATABASE_PATH`
- `ASCEND_UPLOAD_ROOT`
- `ASCEND_MIRROR_ROOT`
- `ASCEND_CORS_ORIGINS`
- `ASCEND_STORAGE_BUCKET`
- `ASCEND_ARCHIVE_BUCKET`
- `ASCEND_EVIDENCE_S3_BUCKET` and `ASCEND_EVIDENCE_S3_ARCHIVE_BUCKET` are also supported as forward-compatible aliases for the same evidence storage flow.
- `AWS_REGION`
- `ASCEND_STORAGE_PUBLIC_BASE_URL`
- `ASCEND_S3_SERVER_SIDE_ENCRYPTION`
- `ASCEND_S3_KMS_KEY_ID`
- `OPENAI_API_KEY`

### Frontend

- `ASCEND_API_URL`

## Related Files

- `deploy/aws/README.md`
- `deploy/aws/backend.Dockerfile`
- `deploy/aws/frontend.Dockerfile`

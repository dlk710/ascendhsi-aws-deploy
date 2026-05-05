# AWS Deployment

This document describes the AWS shape for deploying the Ascend product suite after the S3 storage pivot.

## What Is In This Branch

- S3-first storage instead of Google Drive
- runtime-configurable frontend API host
- backend CORS and path configuration driven by environment
- readiness endpoint for load balancers and container health checks
- Athena-first operational analysis with logs routed to S3 instead of a CloudWatch-centric monitoring stack
- Dockerfiles and AWS deployment artifacts under `deploy/aws/`

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
- Amazon Data Firehose
  - receives backend container logs from ECS FireLens and stores them in S3

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

- backend container logs
  - routed from ECS through FireLens into Amazon Data Firehose
  - delivered into S3 for Athena queries
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

### Data

- short-term deployment can mount SQLite on persistent storage for non-production demos
- scaled production deployment should move to PostgreSQL before multi-task backend scaling

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

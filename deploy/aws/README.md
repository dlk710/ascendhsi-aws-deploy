# AWS Deployment Artifacts

This folder contains deployment-ready scaffolding for running the Ascend product suite on AWS.

## Files

- `backend.Dockerfile`
  - backend container for FastAPI and Uvicorn
- `frontend.Dockerfile`
  - frontend container that serves the built React app with Nginx
- `nginx.conf`
  - SPA routing and cache behavior for the frontend container
- `frontend-entrypoint.sh`
  - renders `runtime-config.js` from environment at container start
- `backend.env.example`
  - example backend environment variables
- `frontend.env.example`
  - example frontend environment variables
- `terraform/`
  - AWS infrastructure as code for ECS, RDS PostgreSQL, S3, Athena, ALB, CloudFront, ECR, and Secrets Manager

## Target AWS Shape

- Frontend:
  - S3 + CloudFront, or the provided frontend container on ECS/App Runner if preferred
- Backend:
  - ECS Fargate behind an Application Load Balancer
- Container registry:
  - Amazon ECR
- Storage:
  - Amazon S3 active bucket plus archive bucket or archive prefix
- Secrets:
  - AWS Secrets Manager
- Monitoring:
  - Athena-first log analysis over S3, starting with ALB and CloudFront logs

## Current Dev Environment

The current dev deployment is live in AWS account `027903151318`, region `us-east-2`.

- CloudFront distribution: `EV6WT9DUO1GQH`
- Frontend bucket: `ascend-frontend-dev-027903151318`
- ECS cluster: `ascend-dev-cluster`
- ECS service: `ascend-dev-backend`
- ECR repository: `ascend-dev-backend`
- ALB: `ascend-dev-api`
- RDS instance: `ascend-dev-postgres`
- Active files bucket: `client-data-dev-027903151318`
- Archive files bucket: `client-data-archive-dev-027903151318`
- Observability logs bucket: `ascend-observability-logs-dev-027903151318`
- Athena workgroup: `ascend-dev-observability`
- Athena database: `ascend_dev_observability`

Current user-facing dev URL:

```text
https://dq5ab404dg57q.cloudfront.net
```

The ALB DNS name should be treated as an internal API origin for troubleshooting, not as the user-facing product-suite URL.

## Frontend Release Steps

```bash
cd frontend-react
pnpm install --frozen-lockfile
pnpm run build
cd ..
aws s3 sync frontend-react/dist/ s3://ascend-frontend-dev-027903151318/ --delete
aws cloudfront create-invalidation --distribution-id EV6WT9DUO1GQH --paths '/*'
```

After invalidation completes, verify:

```bash
curl -sS https://dq5ab404dg57q.cloudfront.net/ready
```

## Notes

- The application can run on SQLite locally or switch to PostgreSQL-compatible databases through `ASCEND_DATABASE_URL`.
- The Terraform scaffolding under `deploy/aws/terraform/` is designed around S3 + Athena log analysis instead of a CloudWatch-first monitoring stack.
- The frontend runtime config pattern means the same built artifact can point at different API hosts per environment.
- The React portal shell uses non-blocking hydration after login; keep this behavior when changing portal bootstrapping so perceived login performance stays fast.

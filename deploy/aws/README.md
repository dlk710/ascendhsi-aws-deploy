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
  - AWS infrastructure as code for ECS, RDS PostgreSQL, S3, Athena, Firehose, ALB, CloudFront, ECR, and Secrets Manager

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
  - Athena-first log analysis over S3, with backend logs routed by FireLens + Firehose

## Notes

- The application can run on SQLite locally or switch to PostgreSQL-compatible databases through `ASCEND_DATABASE_URL`.
- The Terraform scaffolding under `deploy/aws/terraform/` is designed around S3 + Athena log analysis instead of a CloudWatch-first monitoring stack.
- The frontend runtime config pattern means the same built artifact can point at different API hosts per environment.

# Terraform Deployment

This Terraform stack is the AWS deployment baseline for the separate `ascend-aws-deploy` repo.

## What It Creates

- VPC with public and private subnets
- ECS Fargate backend service behind an Application Load Balancer
- Amazon RDS for PostgreSQL
- Amazon ECR repository for the backend image
- Amazon S3 buckets for:
  - frontend assets
  - active client uploads
  - archived uploads
  - operational logs
  - Athena query results
- Amazon Data Firehose for backend log delivery into S3
- Amazon Athena workgroup, database, and starter named queries
- AWS Secrets Manager secrets for:
  - `ASCEND_DATABASE_URL`
  - `OPENAI_API_KEY`
- optional ACM + Route53 wiring when certificate and DNS creation are enabled

## Intentional Monitoring Choice

This stack is Athena-first for cost control:

- backend logs land in S3 through FireLens + Firehose
- ALB logs land in S3 directly
- CloudFront logs land in S3 directly
- Athena is used for analysis and saved queries

This means the stack is optimized for low-cost investigation rather than real-time alerting.

## Quick Start

1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Fill in certificate and image values
3. Run:

```bash
terraform init
terraform plan
terraform apply
```

## Frontend Deployment

The Terraform stack creates the frontend bucket and CloudFront distribution, but it does not upload the compiled React assets by itself.

After building the frontend, sync the build output into the frontend bucket that Terraform outputs:

```bash
aws s3 sync frontend-react/dist/ s3://<frontend-bucket-name>/ --delete
```

## Database Switching

The backend is configured to prefer `ASCEND_DATABASE_URL` when it is present.

- local development can keep using SQLite
- AWS runtime uses the RDS-backed PostgreSQL URL from Secrets Manager

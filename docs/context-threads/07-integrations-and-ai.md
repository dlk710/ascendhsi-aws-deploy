# Thread: Integrations And AI

## Purpose

This thread preserves the external integrations and AI behavior required for the Ascend suite to function.

## Amazon S3 Storage

The current AWS suite uses Amazon S3 for active evidence storage and archive routing.

### Current behavior

- evidence uploads go to a private active S3 bucket
- archive flows move or route records toward archive storage
- object-key structure is organized by client, case, criterion, and evidence id
- delete behavior should archive rather than physically remove the file
- archive must preserve retrievable evidence identity and folder context

### Product rule

Member-facing UI should not talk about S3, archive storage classes, signed URL mechanics, or backend implementation details.

## OpenAI

Current AI use cases:

- evidence analysis before save
- evidence summarization
- attorney petition generation

### Evidence AI behaviors

- classify into EB1A criterion
- classify document type
- generate clear summary
- allow member override

### Petition AI behaviors

- synthesize dossier-level legal planning draft
- identify strengths, gaps, risks, fixes, dependencies, and member questions

### Fallback rule

Fallback behavior is required whenever AI is unavailable, slow, or rate-limited.

## React + FastAPI

Current app model:

- React frontend builds to static assets served by CloudFront/S3 in AWS
- FastAPI backend runs on ECS Fargate behind an ALB in AWS
- local development may still use a dev server and local backend ports

## Database

SQLite is the local persistence layer. AWS dev uses RDS PostgreSQL through `ASCEND_DATABASE_URL`.

It stores:

- profiles
- evidence records
- folders
- tasks
- planner rows
- invites
- assignments
- messages
- operational events

## Operational Event Tracking

Operational events are used for:

- OpenAI usage counts
- error visibility
- health dashboard support
- administrative debugging

## Key Files

- `app/openai_client.py`
- `app/storage.py`
- `app/s3_storage.py`
- `app/config.py`
- `deploy/aws/terraform/`
- `docs/aws-deployment.md`

## Next Good Enhancements

- large-file upload hardening
- object scan and retention workflows
- stronger signed URL auditability
- stronger AI observability by feature area

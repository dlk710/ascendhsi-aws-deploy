# Thread: Storage And AWS S3 Integration

## Purpose

This thread defines the storage integration skill required for Ascend.

The current suite stores evidence through Amazon S3 while preserving product-facing abstractions around evidence, folders, active files, and archive files.

## Current Code Ownership

Primary files:

- `app/storage.py`
- `app/s3_storage.py`
- `config/storage.json`

Related files:

- `app/services.py`
- `tests/test_storage.py`
- `tests/test_s3_storage.py`
- `docs/aws-deployment.md`
- `docs/context-threads/07-integrations-and-ai.md`

## Required Skill

Developers must be able to:

- handle S3 upload and archive flows
- preserve local evidence metadata
- isolate storage provider details from product UI
- design folder and object-key behavior
- prepare for production storage abstraction
- handle IAM, signed URLs, encryption, lifecycle, and retention safely

## Product Rule

Member-facing UI should talk about evidence and case files, not S3, object storage, archive providers, or backend implementation details.

## Formal Development Workflow

Before changing storage behavior:

1. Identify whether the feature affects upload, archive, folder movement, or evidence display.
2. Inspect `app/storage.py`, `app/s3_storage.py`, and the current `config/storage.json` behavior.
3. Preserve behavior when S3 is unavailable or credentials are missing.
4. Record operational events for upload/archive failures.
5. Update storage and S3 tests.
6. Confirm evidence links use signed/private access unless an explicitly approved public distribution strategy is introduced.

## Production-Grade Expectations

Storage changes should include:

- provider abstraction
- IAM role and credential safety
- signed private URLs
- server-side encryption
- lifecycle behavior for active and archive buckets
- clear retry or failure behavior
- file identity mapping
- auditability for upload, archive, and deletion
- no hard-coded production credentials

## Future Production Direction

Add:

- storage provider interface
- environment-specific providers
- resumable uploads for large files
- malware or file-type scanning hooks
- signed access URLs or controlled download flow
- retention and deletion policy
- object lock or stronger retention policy if compliance requirements demand it

## Chat Thread Starter

```text
Use the Storage And AWS S3 Integration thread. Keep storage provider details out of member-facing UI and preserve private signed access.
```

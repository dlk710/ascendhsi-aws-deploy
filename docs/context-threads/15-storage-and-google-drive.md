# Thread: Storage And Google Drive Integration

## Purpose

This thread defines the storage integration skill required for Ascend.

The current suite stores evidence through Google Drive while mirroring local metadata and maintaining user-facing abstraction.

## Current Code Ownership

Primary files:

- `app/google_drive.py`
- `app/storage.py`
- `config/google_drive.json`

Related files:

- `app/services.py`
- `tests/test_google_drive.py`
- `tests/test_storage.py`
- `docs/context-threads/07-integrations-and-ai.md`

## Required Skill

Developers must be able to:

- handle Drive upload and archive flows
- preserve local evidence metadata
- isolate storage provider details from product UI
- design folder synchronization behavior
- prepare for production storage abstraction
- handle credentials and token refresh safely

## Product Rule

Member-facing UI should talk about evidence and case files, not Google Drive, object storage, archive providers, or backend implementation details.

## Formal Development Workflow

Before changing storage behavior:

1. Identify whether the feature affects upload, archive, folder movement, or evidence display.
2. Inspect `app/storage.py` and `app/google_drive.py`.
3. Preserve behavior when Drive is unavailable.
4. Record operational events for upload/archive failures.
5. Update storage and Google Drive tests.

## Production-Grade Expectations

Storage changes should include:

- provider abstraction
- credential safety
- refresh-token support
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

## Chat Thread Starter

```text
Use the Storage And Google Drive Integration thread. Keep storage provider details out of member-facing UI.
```

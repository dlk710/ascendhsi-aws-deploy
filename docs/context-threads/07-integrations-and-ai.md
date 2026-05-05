# Thread: Integrations And AI

## Purpose

This thread preserves the external integrations and AI behavior required for the Ascend suite to function.

## Google Drive

The current suite uses Google Drive instead of local-only storage or production cloud object storage.

### Current behavior

- evidence uploads go to Google Drive
- evidence path structure is organized by client, case, criterion, and evidence id
- delete behavior should archive rather than physically remove the file
- archive must preserve directory structure

### Product rule

Member-facing UI should not talk about Google Drive, archive storage, or backend implementation details.

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

- React frontend on `3000`
- FastAPI backend on `8000`

## SQLite

SQLite is the current persistence layer in the suite.

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

- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/openai_client.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/google_drive.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/storage.py`
- `/Users/lohithdeshpande/Documents/Codex/ascend_mvp/app/config.py`

## Next Good Enhancements

- refresh-token handling for Google Drive
- production storage abstraction for future non-Drive deployments
- stronger AI observability by feature area

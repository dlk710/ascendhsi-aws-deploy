# Configuration Notes

This folder contains checked-in configuration templates for the Ascend product suite.

## Files

- `app.json`
  - local application paths
  - default client seed values

- `storage.json`
  - Amazon S3 storage and archive configuration
  - bucket, archive bucket, storage class, and URL environment variable names

- `openai.json`
  - OpenAI model settings
  - environment variable name for the API key
  - checked in without a live secret

- `openai.example.json`
  - same structure as `openai.json`
  - safe reference for new environments

## Secret handling

Do not commit live credentials into this folder.

Use environment variables for:

- `OPENAI_API_KEY`
- `ASCEND_STORAGE_BUCKET`
- `ASCEND_ARCHIVE_BUCKET`
- `AWS_REGION`

If a local-only override is needed, create a `*.local.json` file and keep it out of version control.

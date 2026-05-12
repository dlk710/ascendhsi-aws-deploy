# Configuration Notes

This folder contains checked-in configuration templates for the Ascend product suite.

## Files

- `app.json`
  - local application paths
  - default client seed values

- `google_drive.json`
  - Google Drive folder routing
  - token environment variable name

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
- `GOOGLE_DRIVE_ACCESS_TOKEN`

If a local-only override is needed, create a `*.local.json` file and keep it out of version control.

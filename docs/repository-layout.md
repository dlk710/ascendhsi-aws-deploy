# Repository Layout

This repository is organized as a single product-suite codebase with clear separation between application layers, configuration, tests, and continuation context.

The documentation is intentionally repository-first and AI-agnostic: contributors should be able to understand the product from the checked-in files alone.

## Primary folders

- `app/`
  - FastAPI routes
  - business services
  - SQLite access
  - Amazon S3 integration
  - OpenAI integration

- `frontend-react/`
  - React portal UI
  - shared styling
  - public branding assets

- `config/`
  - JSON application configuration
  - integration settings
  - environment-backed OpenAI and S3 configuration

- `deploy/aws/`
  - container build files
  - frontend runtime-config injection
  - environment examples for AWS deployment

- `tests/`
  - API tests
  - data-model tests
  - S3 storage tests
  - OpenAI integration fallback tests

- `docs/context-threads/`
  - portal-by-portal continuation threads
  - integration and engineering notes
  - change inventory and file map

- `docs/feature-catalog.md`
  - implemented product behavior by portal
  - shared workflows and major system capabilities

- `docs/solution-architecture.md`
  - current architecture
  - scaled-world target architecture
  - tech-stack decisions and migration guidance

- `docs/verification-notes.md`
  - live verification findings
  - environment caveats
  - known runtime issues discovered during QA

- `docs/missing-features.md`
  - known gaps
  - production hardening work
  - deferred engineering tasks

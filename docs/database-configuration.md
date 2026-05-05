# Database Configuration

Ascend is wired so the application layer can run against different databases without changing portal code.

## Supported Backends

- SQLite
  - default for local development and lightweight demos
  - configured with `ASCEND_DATABASE_PATH`
- PostgreSQL-compatible databases
  - recommended for AWS environments
  - works with Amazon RDS for PostgreSQL and Amazon Aurora PostgreSQL-Compatible
  - configured with `ASCEND_DATABASE_URL`

## How Backend Selection Works

- if `ASCEND_DATABASE_URL` is set, Ascend uses that external database
- if `ASCEND_DATABASE_URL` is not set, Ascend falls back to SQLite using `ASCEND_DATABASE_PATH`
- the service layer and API routes do not change between backends

## Environment Variables

- `ASCEND_DATABASE_URL`
  - example: `postgresql://ascend_app:password@db-host:5432/ascend`
- `ASCEND_DATABASE_PATH`
  - local file path used only when no database URL is provided

## Current Portability Scope

The AWS deployment repo removes the main SQLite-only assumptions from the app layer:

- criteria ordering uses explicit `display_order`
- evidence search uses portable `LIKE` matching instead of SQLite full-text search syntax
- the connection wrapper normalizes parameter placeholders so the same queries can run on SQLite and PostgreSQL-compatible drivers

## AWS Recommendation

For AWS environments:

- use Amazon RDS for PostgreSQL or Aurora PostgreSQL-Compatible
- keep SQLite only for local development or disposable single-user demos
- store the database URL in AWS Secrets Manager and inject it as `ASCEND_DATABASE_URL`

## Future Follow-Up

The application is now backend-configurable, but production-grade scale should still add:

- formal schema migrations
- connection pooling tuned for ECS
- backup and restore runbooks
- read replica strategy only if analytics or reporting load grows materially

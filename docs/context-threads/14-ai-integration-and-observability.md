# Thread: AI Integration And Observability

## Purpose

This thread defines the AI engineering skill required for Ascend.

AI is used to support evidence analysis and attorney petition generation. It must remain structured, reviewable, observable, and resilient.

## Current Code Ownership

Primary file:

- `app/openai_client.py`

Related files:

- `app/services.py`
- `config/openai.json`
- `tests/test_openai_client.py`
- `docs/aws-deployment.md`
- `docs/context-threads/07-integrations-and-ai.md`

## Required Skill

Developers must be able to:

- design structured AI prompts and responses
- validate AI outputs before presenting them
- maintain deterministic fallback behavior
- track OpenAI usage by feature area
- separate evidence analysis from petition drafting
- make AI behavior transparent to Admin without burdening Members
- use official OpenAI documentation when changing API usage
- keep cloud secrets in AWS Secrets Manager and inject them at runtime

## Formal Development Workflow

Before changing AI behavior:

1. Read `07-integrations-and-ai.md`.
2. Inspect `app/openai_client.py`.
3. Preserve fallback output shape.
4. Add operational event tracking for success, fallback, and errors.
5. Update OpenAI client tests.
6. Confirm member-facing UI does not expose raw AI errors.
7. For AWS changes, confirm `OPENAI_API_KEY` remains sourced from Secrets Manager and is never committed to config or logs.

## Production-Grade Expectations

AI features should include:

- structured response schema
- timeout behavior
- fallback behavior
- usage and error logging
- prompt version awareness
- no final legal claims without attorney review framing
- safe degradation when OpenAI is unavailable
- cloud-secret rotation without code changes

## Future Production Direction

Add:

- feature-level AI usage metrics
- prompt version labels
- model configuration by environment
- retry and rate-limit handling
- eval datasets for evidence and petition quality
- redaction strategy for sensitive documents
- environment-level model selection and budget controls

## Chat Thread Starter

```text
Use the AI Integration And Observability thread. Preserve fallback behavior and consult official OpenAI docs before API changes.
```

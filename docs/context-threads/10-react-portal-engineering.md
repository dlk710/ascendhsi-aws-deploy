# Thread: React Portal Engineering

## Purpose

This thread defines the frontend skill required to continue the Ascend React product suite.

The React frontend is the primary user experience for all role portals.

## Current Code Ownership

Primary files:

- `frontend-react/src/App.jsx`
- `frontend-react/src/styles.css`
- `frontend-react/src/main.jsx`

Current pressure point:

- `App.jsx` contains portal routing, auth state, role rendering, form state, fetch orchestration, messaging UI, and attorney petition UI.
- it also currently contains leader perspective switching, admin support views, and demo auth-aware portal branching

## Required Skill

Developers must be able to:

- build role-aware React workflows
- manage form and loading state cleanly
- preserve portal-specific responsibilities
- design dense operational interfaces without turning them into marketing pages
- split large components without changing behavior
- keep member-facing UI simple and non-technical
- keep builder, leader, attorney, admin, and member views visually related but purpose-built

## Current Local Frontend Workflow

- Run `pnpm run dev:aws` from `frontend-react/` for daily UX and design review.
- The local Vite server proxies API calls to AWS dev, so browser back/forward, role routing, and live data can be reviewed locally without redeploying every visual change.
- Run `pnpm run dev:local` only when testing against a local FastAPI backend.
- Keep API calls relative to the app origin; do not hardcode CloudFront, ALB, localhost, or future custom-domain URLs into components.

## Formal Development Workflow

Before changing frontend code:

1. Identify the role portal and child page.
2. Read the matching portal thread.
3. Locate the existing state, fetch calls, and render branch in `App.jsx`.
4. Add or modify API calls only through the established helper pattern.
5. Confirm loading, empty, success, and error states.
6. Add CSS using existing design tokens and layout patterns.
7. If the change affects demos or portal switching, check `frontend-react/public/auth-helper.html` and `frontend-react/public/logout-helper.html`.

## Decomposition Direction

As the product grows, split `App.jsx` by capability:

- `auth`
- `member`
- `builder`
- `leader`
- `attorney`
- `admin`
- `messaging`
- shared API helpers
- shared layout components

Do this incrementally. Avoid a large rewrite unless the immediate feature requires it.

## Production-Grade Expectations

Frontend changes should include:

- role-correct navigation
- no broken preview roles
- stable layouts on desktop and mobile
- no text overflow in buttons, cards, tables, or sidebars
- visible but restrained error states
- clear disabled/loading states for async actions
- no member-facing references to S3, backend internals, signed URL mechanics, or fallback mechanics

## Chat Thread Starter

```text
Use the React Portal Engineering thread. Read the affected portal thread and inspect App.jsx before changing the UI.
```

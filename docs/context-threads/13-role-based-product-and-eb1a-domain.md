# Thread: Role-Based Product And EB1A Domain

## Purpose

This thread defines the product and domain skill required to build Ascend as a role-based EB1A operating system.

The product should not drift into a generic upload portal or generic CRM.

## Required Skill

Developers must understand:

- EB1A evidence criteria
- evidence strength and gap workflows
- member intake and profile building
- builder momentum management
- leader assignment oversight
- attorney legal review and petition strategy
- admin operations and support needs

## Role Boundaries

### Member

Owns profile completion, evidence upload, planner progress, and direct communication.

### Profile Builder

Owns member momentum, task guidance, opportunity creation, and gap identification.

### Leader

Owns assignments, routing, workload balance, and executive oversight.

### Attorney

Owns legal sufficiency, evidence review, petition strategy, and draft generation.

### Admin

Owns system health, operational troubleshooting, usage visibility, and support actions.

## Product Guardrails

- Do not give Builder the Leader's assignment authority.
- Do not expose operational storage details to Members.
- Do not make Attorney output look final when it is an AI-assisted draft.
- Do not hide fallback or failure behavior from Admin.
- Do not merge all role experiences into one generic dashboard.

## Formal Development Workflow

Before implementing a product feature:

1. Name the role owner.
2. Name the user decision or action being improved.
3. Identify cross-role effects.
4. Define the backend source of truth.
5. Define the operational event or audit signal if the action is important.

## Production-Grade Expectations

Product changes should include:

- clear role ownership
- trustworthy AI language
- no legal overclaiming
- useful next actions
- auditability for sensitive decisions
- consistent case record behavior across portals

## Chat Thread Starter

```text
Use the Role-Based Product And EB1A Domain thread. Confirm the role owner and EB1A workflow before changing product behavior.
```


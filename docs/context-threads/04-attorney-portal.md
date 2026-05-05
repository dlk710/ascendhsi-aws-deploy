# Thread: Attorney Portal

## Purpose

Attorney Portal is where the full case record becomes usable for petition strategy.

The attorney needs full dossier access, not just uploaded files.

## Current Pages

- `Attorney Home`
- `Member Dossier`
- `Petition Generator`
- `Batch Intake`
- `Evidence Review`
- `Messages`

## Attorney Home

Current behavior:

- portfolio-first caseboard
- case-stage triage across the assigned docket
- selected member summary that anchors the next legal action

## Member Dossier

Current behavior:

- profile summary
- current positioning
- filing posture
- strengths and gaps
- builder notes / tasks in motion

This page should remain the narrative overview page.

## Evidence Review

Current behavior:

- separate page from dossier
- lets attorney scan evidence files and summaries without losing case context

This page should remain evidence-centric, not strategy-centric.

## Batch Intake

Current behavior:

- dedicated child page for document intake sessions
- keeps batch processing separate from dossier and petition drafting
- preserves case context while letting attorneys work through evidence packets

## Petition Generator

Current behavior:

- dedicated child page
- attorney-facing AI draft generator
- synthesizes:
  - member profile
  - criteria summary
  - uploaded evidence
  - folder organization
  - builder tasks
  - planner history
  - recent messages

### Current output sections

- executive summary
- petition positioning
- readiness assessment
- proposed petition sections
- strengths
- gaps
- risks / challenges
- recommended fixes
- member dependencies
- external dependencies
- clarification questions

### Current runtime behavior

- AI path is attempted first
- fallback draft is returned if OpenAI is unavailable or fails
- endpoint currently verified to return a structured fallback response successfully

## Messaging Rules

Attorney can message:

- member
- builder
- leader
- admin

Leader can also inspect the attorney workspace through `Attorney View` without leaving leader auth.

## Key Backend Dependencies

Important service methods:

- `builder_member_detail`
- `attorney_petition_generator`
- `message_center`
- `send_message`

Important API endpoint:

- `/api/attorney/petition-generator`

## Next Good Enhancements

- petition letter / strategy export
- create tasks or messages directly from clarification questions
- criterion-by-criterion legal sufficiency scoring
- stronger intake-to-petition handoff visibility

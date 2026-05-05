# Thread: Member Portal

## Purpose

The Member Portal is the cleanest experience in the suite. It should feel guided, simple, and low-friction for a member who may not understand EB1A operations deeply.

## Current Pages

- `Member Home`
- `Profile`
- `Event Planner`
- `Evidence Intake`
- `Messages`

Deeper workspaces that branch from those pages:

- criterion-specific evidence workspace
- profile section tabs

## Current UX Decisions

- welcome salutation is preserved
- member must not see internal portal options
- long-scroll home page was reduced in favor of child pages
- evidence intake moved off the landing page as a dedicated area
- messages moved to their own page
- member-facing copy avoids internal operational language

## Member Profile

Current profile behavior:

- tabbed child page
- mandatory fields:
  - first name
  - last name
  - email
- additional profile fields support builder and attorney review later
- member must confirm profile accuracy before save is considered complete

## Event Planner

Current planner behavior:

- renamed from evidence planner to event planner
- simplified into row-based planning
- intended for self-maintained future activities
- row can track:
  - activity
  - organization
  - category
  - target date
  - status
  - notes
- rows can be added and removed

## Evidence Intake

Current intake behavior:

- heading changed away from explicit AI framing
- member can choose:
  - AI suggestion route
  - manual route
- if AI route:
  - upload + note
  - AI suggests criterion, document type, summary
  - member can accept or reject suggestion
  - manual override becomes available on rejection
- if manual route:
  - member chooses category directly
  - no AI draft section appears afterward

## Evidence Display

Current display behavior:

- evidence is shown by criterion
- category cards are clickable
- member goes into separate detail/workspace pages instead of staying on one long screen
- files show:
  - hyperlink filename
  - uploaded date/time
  - summary
  - delete action

Home page remains summary-first, while actual evidence work moves into the criterion workspace.

## Evidence Organization

Current organization behavior:

- each criterion has a dedicated workspace
- folders and subfolders exist in app metadata
- members can organize evidence cleanly
- folder colors are available
- drag/drop intent was explored, but actual UX should remain simple and obvious

## Messaging Rules

Member can message:

- assigned profile builder
- assigned attorney
- admin

Member should not message arbitrary internal users outside the role rules.

## Key Backend Dependencies

Important service methods:

- `dashboard`
- `member_profile`
- `update_member_profile`
- `planner_items`
- `create_planner_item`
- `update_planner_item`
- `delete_planner_item`
- `analyze_evidence`
- `upload_evidence`
- `criterion_workspace`
- `move_evidence_to_folder`
- `archive_evidence`
- `message_center`
- `send_message`

## Next Good Enhancements

- stronger folder organization sync to external storage
- better member-facing next-step guidance from builder tasks
- direct links from planner items into the right evidence workspace
- clearer progress nudges tied to attorney or builder requests

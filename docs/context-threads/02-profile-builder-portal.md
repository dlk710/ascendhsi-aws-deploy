# Thread: Profile Builder Portal

## Purpose

The Profile Builder Portal is the operational workbench for advancing each member's EB1A profile.

## Current Pages

- `Builder Home`
- `Assigned Members`
- `Opportunities`
- `Messages`

## Current Responsibilities

- review assigned roster
- inspect readiness and momentum
- identify strengths and weak criteria
- assign tasks
- push reusable opportunities
- communicate with members
- operate as the day-to-day execution workbench, distinct from leader routing

## Builder Home

Home page currently serves as:

- summary of assigned members
- summary of tasks in flight
- opportunity count
- overall progress signal
- selected member quick summary with next action context

## Assigned Members

Current behavior:

- separate page from home
- shows roster cards
- selected member shows:
  - current profile position
  - criterion coverage
  - tasks in flight
  - readiness and evidence momentum

## Opportunities

Current behavior:

- dedicated opportunity pool page
- reusable opportunity templates
- builder can turn an opportunity into a member task
- builder can also create custom opportunities for the shared library
- leader can review this same workspace through `Builder View` without leaving the leader account

## Builder Tasks

Task flow should remain:

- explicit
- due-date aware
- tied to a category when possible
- visible to both member and internal reviewers

## Messaging Rules

Builder should mainly message:

- assigned members
- leader
- admin
- attorney when needed for coordination

## Key Backend Dependencies

Important service methods:

- `builder_dashboard`
- `builder_members`
- `builder_member_detail`
- `builder_opportunities`
- `create_builder_task`
- `update_builder_task`
- `create_opportunity`
- `message_center`
- `send_message`

## Design Intention

This portal should feel like a workbench, not a member-facing showcase:

- denser information is acceptable
- progress and action clarity matter more than polish alone
- avoid mixing assignment oversight into this portal, because that belongs to Leader

## Next Good Enhancements

- richer momentum trends
- stronger task completion workflow
- opportunity analytics across builders
- clearer completion feedback loops back into leader oversight

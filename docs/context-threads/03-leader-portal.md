# Thread: Leader Portal

## Purpose

Leader Portal is the oversight and routing control surface for the entire Ascend profile-building operation.

Its current form is now a CEO-grade operations cockpit that answers five questions quickly:

1. Are cases moving fast enough?
2. Where is execution slowing down?
3. Which risks will cause misses unless leadership intervenes?
4. Which teams or domains are strongest or overloaded?
5. What will likely complete in the next 30, 60, and 90 days?

## Current Portal Responsibilities

Leader currently owns:

1. inviting a member
2. monitoring registration
3. assigning a profile builder
4. later assigning an attorney
5. reviewing member progress
6. understanding domain mix and routing quality

This ownership boundary should remain intact. Builder should not absorb routing decisions.

## Current Pages

- `Executive Overview`
- `Member Review`
- `Risk & Bottlenecks`
- `Team Capacity`
- `Batch Intake`
- `Opportunities`
- `Assignment Oversight`
- `Messages`

## Current Perspective Modes

Leader can now stay inside leader authentication while switching between:

- `CEO View`
- `Builder View`
- `Attorney View`

This is important for leadership review because it allows portal inspection without separate logins or role switching side effects.

## Current Backend Dependencies

Important service methods already present:

- `leader_dashboard`
- `leader_invite_member`
- `leader_assign_builder`
- `leader_assign_attorney`
- `builder_member_detail`
- `message_center`
- `send_message`

## Current Data Already Available

The existing FastAPI and SQLite stack can already support these operational views:

- member count
- readiness score
- case status
- registration status
- builder assignment
- attorney assignment
- evidence count
- open task count
- domain mix
- invite timestamps
- assignment timestamps
- operational events
- message activity

Important current sources:

- `cases`
- `member_profiles`
- `member_registration_invites`
- `builder_member_assignments`
- `attorney_member_assignments`
- `tasks`
- `evidence_items`
- `operational_events`
- `messages`

## CEO-Grade Target Experience

The portal has already moved beyond a single dashboard into a multi-page executive workspace with clean drilldown and drill-up. The remaining work is to deepen forecasting, cohort analysis, and case-level drill paths.

Recommended navigation:

1. `Executive Overview`
2. `Risk & Bottlenecks`
3. `Team Capacity`
4. `Member Review`
5. `Assignment Oversight`
6. `Batch Intake`
7. `Opportunities`
8. `Messages`
9. future: `Pipeline & Velocity`
10. future: `Domains & Cohorts`
11. future: `Case Drilldown`

The first page should feel like a calm command center, not a crowded admin console. It should emphasize signal over controls.

## Page Architecture

### 1. Executive Overview

Primary purpose:

- give the CEO one screen for portfolio health, speed, risk, and near-term forecast

Top KPI cards:

- `Active Cases`
- `Petition-Ready Cases`
- `Completed This Month`
- `Median Time To Petition-Ready`
- `Weekly Completion Velocity`
- `At-Risk Cases`
- `Unassigned Cases`
- `Forecast Confidence`

Recommended charts:

- `Executive funnel`
  - stages: `Invited -> Registered -> Builder Assigned -> Active Build -> Attorney Review -> Petition Ready -> Completed`
- `Velocity trend line`
  - weekly petition-ready completions and completed cases
- `Cycle time trend`
  - median days from intake to petition-ready by week
- `Portfolio stage mix`
  - stacked bar of cases by stage and risk color
- `Risk watchlist`
  - ranked table of top cases needing intervention
- `30/60/90 day forecast strip`
  - expected completions vs target

CEO actions from this page:

- drill into stalled stage
- drill into risky owner
- drill into weak domain cohort
- jump to assignment correction

### 2. Pipeline & Velocity

Primary purpose:

- show exactly where throughput slows and how fast cases convert through the pipeline

Core metrics:

- invite-to-registration conversion
- registration-to-builder-assignment lag
- builder-assignment-to-attorney-handoff lag
- attorney-handoff-to-petition-ready lag
- overall intake-to-completion cycle time
- median and P75 days per stage

Recommended charts:

- `Funnel conversion chart`
- `Stage aging histogram`
- `Weekly throughput bar + line overlay`
- `Cohort progression table`
  - rows by intake month
  - columns by milestone reached
- `Readiness progression line`
  - average readiness at day 0, 30, 60, 90

Key drilldown paths:

- by domain
- by builder
- by attorney
- by intake cohort

### 3. Risk & Bottlenecks

Primary purpose:

- isolate the exact work that requires leadership attention

Risk categories:

- no builder assigned after registration
- no attorney assigned after readiness threshold
- no member activity in X days
- no evidence added in X days
- no task completed in X days
- too many open tasks
- stage age beyond threshold
- repeated reassignment
- domain-expertise mismatch

Recommended charts:

- `Risk heatmap`
  - rows by owner
  - columns by risk type
- `Blocked reasons bar chart`
- `Aging by stage`
  - 0-7, 8-14, 15-30, 30+ days
- `Red case trend`
  - number of high-risk cases over time
- `Intervention queue table`
  - case, owner, stage, blocker, last activity, next action owner

Mandatory table columns:

- member
- stage
- readiness
- owner
- days in stage
- last activity
- blocker reason
- next milestone
- predicted miss risk

### 4. Team Capacity

Primary purpose:

- show whether builders and attorneys are balanced, overloaded, or underutilized

Builder and attorney KPIs:

- active caseload
- new cases assigned this month
- cases completed this month
- average readiness gain per 30 days
- average days to handoff
- average response lag
- percentage of high-risk cases
- portfolio domain mix

Recommended charts:

- `Caseload vs throughput scatter plot`
- `Owner workload ranked bars`
- `Owner stage-aging heatmap`
- `Domain mix stacked bars by owner`
- `Handoff turnaround leaderboard`

Leadership decisions supported:

- rebalance cases
- identify stars carrying too much load
- identify coaching gaps
- detect domain specialization bottlenecks

### 5. Domains & Cohorts

Primary purpose:

- help leadership understand which segments of the business move fastest and where complexity is concentrated

Breakdowns:

- by industry domain
- by intake month
- by current stage
- by builder
- by attorney
- by readiness band

Recommended charts:

- `Domain portfolio mix area chart`
- `Velocity by domain line chart`
- `Cycle-time spread by domain`
- `Cohort survival table`
- `Readiness band distribution`

Important use cases:

- compare healthcare vs pharma vs insurance vs technology
- identify domains with slower attorney conversion
- detect intake cohorts degrading over time

### 6. Case Drilldown

Primary purpose:

- convert every executive chart into a case-level explanation

Each case drilldown should show:

- current stage
- readiness score trend
- evidence count trend
- open task trend
- builder and attorney assignment history
- registration history
- recent messages and escalations
- bottleneck flags
- predicted petition-ready date
- recommended leadership action

Timeline modules:

- intake created
- invite sent
- registration completed
- builder assigned
- attorney assigned
- readiness milestones crossed
- major evidence uploads
- task completions
- operational exceptions

### 7. Assignment Oversight

Keep and upgrade the existing page rather than removing it.

New additions:

- workload-aware assignment suggestions
- domain-fit recommendations
- unowned case alerts
- aging-based assignment urgency
- bulk review queue for recently registered members

Recommended decision aids:

- `Suggested Builder`
- `Suggested Attorney`
- `Current Capacity Pressure`
- `Domain Match`
- `Case Complexity`

### 8. Messages

Leader can already message anyone. For executive operations this page should also surface:

- urgent unread threads
- case-linked escalations
- support/admin escalations affecting delivery
- owner follow-up lag

## Drilldown And Drill-Up Model

Every visual should support a predictable drill path:

1. portfolio
2. cohort or segment
3. owner or stage
4. case list
5. individual case timeline

Every detail page should support drill-up back to:

- source metric
- source cohort
- source owner
- source date range

This is essential for CEO usability. If drill state feels lossy or confusing, the portal will feel analytical but not operational.

## Metric Definitions

Use explicit business definitions, not loose labels.

### Core executive metrics

- `Active Cases`
  - all non-completed cases
- `Petition-Ready Cases`
  - cases at or above the readiness threshold defined by product policy
- `Weekly Completion Velocity`
  - count of cases entering petition-ready or completed state per trailing 7 days
- `Median Time To Petition-Ready`
  - days from case creation to petition-ready milestone
- `At-Risk Cases`
  - cases with red risk score based on aging, inactivity, and missing assignments
- `Forecast Confidence`
  - confidence score for expected completions in target window

### Derived operational scores

- `Velocity Score`
  - readiness gained over recent period, adjusted for stage
- `Execution Health Score`
  - combines task completion, evidence growth, member activity, and assignment stability
- `Risk Score`
  - combines inactivity, aging, assignment gaps, blocker count, and missed milestone thresholds
- `Capacity Pressure Score`
  - caseload adjusted by stage mix, risk mix, and domain complexity

## What Can Be Built Now Versus Next

### Available now with current schema

- current portfolio counts
- readiness averages
- domain mix
- assignment coverage
- invite funnel snapshots
- evidence counts
- open task counts
- simple case risk rules
- owner caseload tables
- recent operational exceptions

### Requires new derived milestones or richer event logging

- true petition-ready timestamp history
- true completion milestone history
- stage transition history
- stage aging accuracy beyond current status snapshot
- forecast confidence model
- readiness change over time
- evidence growth trend over time
- assignment history trend lines

## Backend Expansion Plan

### Phase 1: Executive metrics API

Expand `leader_dashboard` or add dedicated endpoints:

- `/api/leader/dashboard/executive-overview`
- `/api/leader/dashboard/pipeline`
- `/api/leader/dashboard/risks`
- `/api/leader/dashboard/capacity`
- `/api/leader/dashboard/domains`
- `/api/leader/members/{client_id}/timeline`

Phase 1 payloads should include:

- current metrics
- grouped rollups
- top-risk case list
- owner summaries
- domain summaries
- lightweight trend arrays

### Phase 2: Milestone history

Add durable event capture for:

- case status change
- readiness threshold crossed
- builder assigned
- attorney assigned
- task completed
- evidence uploaded
- member became inactive or reactivated

This can be recorded in `operational_events` first, then normalized later if needed.

### Phase 3: Forecasting

Add derived forecast logic:

- projected petition-ready date
- projected completion date
- confidence band
- expected completions by week/month

## Frontend Implementation Plan

The current frontend has no charting dependency. Recommended path:

### Initial plotting implementation

- use CSS bars, heatmaps, and dense executive tables first
- use lightweight inline SVG for line and bar trends
- avoid heavy chart-library adoption until the executive information architecture stabilizes

### Optional later chart library

- add a single React chart library only after the data model settles
- keep visuals restrained and operational, not presentation-heavy

### Suggested React decomposition

Current pressure point:

- `frontend-react/src/App.jsx` holds all portal rendering and data orchestration

Recommended split for Leader work:

- `leader/LeaderOverviewPage.jsx`
- `leader/LeaderPipelinePage.jsx`
- `leader/LeaderRiskPage.jsx`
- `leader/LeaderCapacityPage.jsx`
- `leader/LeaderDomainsPage.jsx`
- `leader/LeaderCaseDrilldownPage.jsx`
- `leader/leaderApi.js`
- shared chart primitives
- shared filter bar

## Elegant CEO Presentation Rules

- default to a quiet executive surface, not a form-heavy workspace
- put filters in one top horizontal bar
- show `current`, `vs prior period`, and `trend direction` together
- use color only for status semantics
- keep red reserved for intervention cases
- let each chart click through to a filtered case list
- make tables compact but readable
- preserve mobile responsiveness without collapsing the page into meaningless cards

## Minimum Widget Inventory

If only one major CEO page is built first, it should contain:

1. `KPI Row`
2. `Executive Funnel`
3. `Velocity Trend`
4. `Cycle Time Trend`
5. `Risk Watchlist`
6. `Owner Capacity Snapshot`
7. `Domain Mix`
8. `30/60/90 Forecast Strip`

## Best First Release

If delivery needs to stay pragmatic, the strongest first release is:

1. redesign `Leader Home` into `Executive Overview`
2. keep `Assignment Oversight` as the action page
3. add a new `Risk & Bottlenecks` page
4. add simple `Team Capacity` views
5. postpone advanced forecasting until milestone history exists

This creates visible executive value quickly without pretending the current data model already supports perfect forecasting.

## Product Guardrail

Leader Portal should remain the control center for operational oversight, routing quality, and executive intervention.

It should not become a duplicate of Builder workflow screens. Its value is cross-portfolio visibility, bottleneck detection, and decision support.

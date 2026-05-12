# Feature Catalog

This document is the current portal-by-portal inventory of the Ascend Product Suite.

## Product Scope

Ascend is a role-based EB1A operations platform with five active portal experiences:

- Member Portal
- Profile Builder Portal
- Leader Portal
- Attorney Portal
- Admin / Operations Portal

All portals operate on the same underlying member, case, evidence, assignment, message, support, and activity data model.

## Shared Platform Features

- Role-specific login for members, profile builders, leaders, attorneys, and admins.
- Session restore, logout, and change-password flows.
- Numeric user identifiers for members, profile builders, attorneys, leaders, and admins, while preserving internal `client_id`, `case_id`, and assignment identifiers.
- Page-specific URL state for portal, section, member, criterion, and folder navigation so browser back/forward follows the user journey.
- Relative API URL support for local Vite proxy, AWS CloudFront routing, and custom-domain deployments without changing frontend code.
- Portal bootstrap recovery panel with retry and sign-out actions so failed hydration does not leave users on an infinite loading state.
- Shared left-rail navigation with resizable sidebar behavior.
- Shared case record across member, builder, leader, attorney, and admin views.
- Shared EB1A criterion model across evidence intake, workspaces, review pages, petition drafting, and reporting.
- Threaded messaging across portals with role-aware recipients, unread counts, replies, read state, and delete actions.
- Ascend Navigator AI assistant for builder, leader, and attorney workflows with contextual case/evidence grounding.
- Ascend Beacon support-ticket widget available across portals.
- Support tickets with description, location, URL context, priority, blocking state, screenshots, attachments, AI/admin summary, and recommended next actions.
- Activity logging for page views, evidence activity, AI flows, messages, support tickets, delete/archive actions, and operational diagnostics.
- OpenAI-backed features with deterministic fallback behavior when AI is unavailable.
- Evidence metadata stored in the configured database and files routed through the storage provider abstraction.
- SQLite is used for local-only development; AWS dev uses RDS PostgreSQL through `ASCEND_DATABASE_URL`.
- S3-backed evidence storage and archive routing in AWS dev, with local storage fallback for local development.
- Soft-delete/archive behavior for evidence, generated exports, and storage-backed files.
- Timestamped records for uploads, exports, archive events, support tickets, messages, activities, and generated artifacts.

## Member Portal

Primary user: member / client.

### Member Home

- Readiness score, evidence count, open task count, and criteria-started metrics.
- Compact filing timeline visibility.
- Evidence summary by EB1A criterion in a simple spreadsheet-like view.
- Vertical criterion drilldown for uploaded evidence by category.
- Color-coded category chips for fast recognition.
- One-line evidence history rows with uploaded date, category, type, and review link.
- Click-through from criterion summary into the criterion workspace.

### Member Profile

- Structured profile tabs for identity, professional background, credentials and links, narrative, and criterion highlights.
- Identity fields including name, preferred name, email, phone, date of birth, citizenship, residence, and city/state.
- Professional fields including current title, employer, employer type, industry domain, primary field, specialization, and years of experience.
- Credentials fields including degree, institution, graduation year, LinkedIn, personal website, Google Scholar, and ORCID.
- Narrative fields for biography, top achievements, final merits positioning, and target filing window.
- Criterion highlight fields for awards, memberships, publications, judging, original contributions, leading roles, media, and salary.
- Member confirmation checkbox before profile submission.
- Profile completion score and member-approved status.

### Evidence Intake

- Dedicated evidence intake page separate from member home.
- AI suggestion route that analyzes uploaded evidence, suggests EB1A category, evidence type, title, summary, and confidence score.
- Manual route for member-selected category and evidence type.
- Draft review before saving AI-suggested evidence.
- Accept or reject AI suggestions.
- Override category and evidence type when rejecting AI suggestion.
- Duplicate file detection by category.
- Duplicate handling including replace/archive behavior.
- Evidence upload history in compact Excel-style rows.
- Sortable evidence history columns for evidence, category, uploaded date, and type.
- Hyperlinks from history rows to the relevant criterion/category review.
- Category-specific color coding.

### Evidence By Criterion Workspace

- Evidence grouped by EB1A criterion.
- Criterion workspace pages for deeper review.
- Folder tree per criterion.
- Create, rename, recolor, and delete folders.
- Drag-and-drop files between folders and workspace columns.
- Search within criterion workspace.
- Document-type count chips.
- Evidence delete with confirmation and archive behavior.
- Openable evidence links from stored files.

### Event Planner

- Plan future evidence-building activities.
- Track event/activity, issuing organization, EB1A category, target date, status, notes, and actions.
- Save, update, and remove planner rows.
- Statuses include planned, in progress, completed, and blocked.
- Examples guide members toward useful evidence opportunities.

### Critical Role Projects

- Structured project-by-project intake for the leading or critical role criterion.
- Multiple projects per member.
- Summary list with company, project, dates, title, and status.
- Detailed project editor opened from summary cards.
- Save draft at any time.
- Submit project when ready for attorney review.
- Delete project with double confirmation.
- Organization fields for name, unit, location, website, employment type, distinctiveness, achievements, awards, and reputation signals.
- Role fields for job title, start/end dates, current-role marker, summary, responsibilities, role evolution, leadership scope, and cross-functional partners.
- Project fields for project name, status, dates, summary, business need, and strategic importance.
- Contribution/value fields for personal contributions, originality, business value, quantitative metrics, revenue impact, cost savings, efficiency gains, user/customer impact, market/geographic impact, and compliance/risk impact.
- Distinction fields for peer distinction, mentorship, leadership beyond title, executive visibility, and trusted advisor role.
- Evidence and attorney-friendly summary fields.
- Italicized guidance and examples for member education.
- Submitted projects generate PDF/template-style exports.
- Exported project PDF is stored back as evidence under the respective criterion.
- Deleted submitted projects archive the generated evidence artifact.

### Original Contributions

- Structured contribution-by-contribution intake for original contributions of major significance.
- Multiple contributions per member.
- Summary list with title, organization/project, dates, and status.
- Detailed contribution editor opened from summary cards.
- Save draft at any time.
- Submit contribution when ready for attorney review.
- Delete contribution with double confirmation.
- Overview fields for contribution title, category, field of expertise, job title, organization, project name, dates, and status.
- Originality fields for originality summary, challenged paradigms, and prior state of field/workflow.
- Role fields for work vs external context, personal role, and distinct contribution.
- Problem/solution fields for technical or business problem, solution/innovation, unique features, and use cases.
- Impact fields for metrics, adoption scale, beneficiaries, time savings, cost savings, revenue/funding impact, quality/risk impact, and field-wide impact.
- Recognition/evidence fields for recognition, influence, media/public mentions, adoption letter targets, evidence available, and attorney-friendly summary.
- Italicized guidance and examples for member education.
- Submitted contributions generate PDF/template-style exports.
- Exported contribution PDF is stored back as evidence under the respective criterion.
- Deleted submitted contributions archive the generated evidence artifact.

### Member Messages

- Dedicated member conversations page.
- Message assigned Profile Builder, Attorney, or Admin according to role rules.
- View threads, replies, timestamps, and unread state.
- Receive attorney-pushed recommendation letter messages with download links.

### Member Referrals

- Member-facing `Refer & Earn` area shown only when the referral program is enabled by leadership.
- Capture potential customer name plus email or phone, relationship, and optional notes.
- Store each referral in a dedicated referral table instead of mixing it with member profile data.
- Show configurable referred-member and referrer-member incentive amounts in the member experience.
- Explain eligibility clearly: payout is due only after the referred member signs the contract and completes at least six months with Ascend.
- Show member referral history with prospect contact, status, eligibility state, and bonus amount.
- Hide the submission form and show a soft pause message when leadership disables the program.

## Profile Builder Portal

Primary user: profile builder.

### Builder Home

- Assigned-member dashboard.
- Metrics for assigned members, active tasks, average readiness, and opportunity library size.
- Member focus cards showing title, employer, readiness, evidence count, open tasks, and momentum.
- Selected-member quick summary with profile position, criterion coverage, and next move.

### Assigned Members

- Roster of assigned members.
- Member selection and detail review.
- Readiness, evidence count, open tasks, criteria started, current title, employer, and momentum indicators.
- Filing timeline preview for the selected member.
- Current profile position and criterion coverage.
- Builder-issued task list with due dates and status.
- Evidence library grouped by EB1A criterion.
- Openable evidence links.
- Critical Role and Original Contribution export panels for generated member narrative PDFs.
- Petition Acceleration workspace in compact builder view.

### Opportunities

- Opportunity template library.
- Create new profile-building opportunities by category.
- Define opportunity title, description, target evidence type, and suggested due days.
- Use an opportunity template for the selected member.
- Assign custom tasks to members.
- Task fields include title, guidance, EB1A category, due date, and opportunity linkage.
- Update task status.

### Builder Messages

- Dedicated conversations page.
- Message assigned members and internal roles according to role rules.
- Threaded replies, unread counts, and delete/read actions.

### Builder Assistant And Support

- Ascend Navigator in builder context.
- Ask case/evidence/task questions about selected member.
- Submit support tickets with portal context and attachments.

## Leader Portal

Primary user: leader / operations lead.

### Executive Overview

- Portfolio-level metrics for active cases, petition-ready cases, high-risk cases, late cases, active tasks, and average readiness.
- Executive funnel across registration, assignments, active build, attorney review, petition ready, and completion.
- Execution timeline showing operating tempo.
- Domain mix by member background with readiness/risk details.
- 90-day completion outlook by readiness band.
- Leadership intervention watchlist with direct member drilldown.
- Member invite form for first name, last name, email, domain, primary field, current title, and employer.
- Capacity snapshot of builder pressure.

### Member Review

- Member roster with readiness, evidence, open tasks, current title, employer, target filing date, timeline status, and momentum.
- Selected-member profile position.
- Criterion coverage.
- Builder-issued tasks in flight.
- Filing timeline preview.
- Evidence library grouped by criterion.
- Generated Critical Role and Original Contribution export panels.
- Petition Acceleration compact workspace.

### Risk And Bottlenecks

- High-risk case metrics.
- Stale cases, unassigned cases, and attorney-routed counts.
- Risk mix summary.
- Stage pressure summary.
- Intervention queue for leadership review.

### Team Capacity

- Builder capacity dashboard.
- Attorney capacity dashboard.
- Capacity pressure score blending caseload, high-risk cases, and open tasks.
- Average readiness by assignee.

### Delivery Timeline

- Portfolio filing timeline view.
- Realistic member-specific Gantt-style path to filing.
- Stage details, target dates, status, and alerts.
- Timeline alerts for late and at-risk members.
- Dotted/conditional RFE support path in the filing timeline model.

### Product Backlog

- Feature intake form for enhancement, style change, or new feature.
- Capture title, request type, target portals, priority, business value, description, acceptance criteria, requester, and screenshots.
- Prioritized backlog table.
- Priority and status updates.
- Statuses include backlog, ready, in progress, testing, deployed, and blocked.
- Priority counts and status counts.

### Batch Intake

- Leader access to batch intake review where appropriate.
- ZIP-based evidence packet review workflow shared with attorney operations.

### Assignment Oversight

- Invitation status tracking.
- Registered-member tracking.
- Builder assignment dropdown.
- Attorney assignment dropdown.
- Current stage and action column.
- Recent member invites list with invited/registered timestamps.

### Referral Program

- Configure whether the referral program is enabled or paused.
- Configure referred-member and referrer-member incentive amounts for promotion seasons.
- Configure the promotion name and eligibility note displayed to members.
- Track all referrals across members with prospect contact, relationship, status, contract milestone, six-month milestone, eligibility, payout, and disqualification reason.
- Update referral statuses through leadership workflow: submitted, contacted, contract signed, qualified, paid, or disqualified.
- Show summary metrics for total referrals, active referrals, contracts signed, qualified referrals, paid referrals, and pending payout amount.

### Leader Perspective Switching

- Leader can assume Leader View, Builder View, or Attorney View without separate login.
- Builder and attorney workflows remain scoped inside leader auth.

### Leader Messages, Assistant, And Support

- Dedicated messages page.
- Ascend Navigator in leader context.
- Support-ticket submission with context.

## Attorney Portal

Primary user: attorney.

### Attorney Home

- Portfolio-level caseboard for assigned matters.
- Total cases, open tasks, evidence items, average readiness, criteria started, and needs-attention metrics.
- Case roster snapshot by member, stage, readiness, evidence count, criteria started, and open tasks.
- Portfolio signal summary by case stage, attention needs, and evidence depth.
- Topbar selected-member dropdown for member-specific attorney work.
- Filing timeline preview for selected member.

### Member Dossier

- Member profile summary.
- Identity, current positioning, and filing posture cards.
- Strengths and gaps by EB1A criterion.
- Builder notes/tasks in motion.
- Filing timeline preview.
- Critical Role and Original Contribution generated export panels.

### Petition Generator

- AI-backed attorney petition planning draft from current member record.
- Uses profile, evidence, folders, tasks, planner history, and member narrative exports.
- Executive summary.
- Petition positioning.
- Readiness assessment.
- Proposed petition sections.
- Strengths, gaps, risks, and recommended fixes.
- Member dependencies and external dependencies.
- Clarification questions for the member.
- Deterministic fallback draft if AI is unavailable.
- Petition Acceleration workspace embedded below the generator.

### Petition Acceleration Workspace

- P0/P1 petition acceleration workspace shared by attorney, leader, builder, member, and admin in role-appropriate form.
- Case snapshot with readiness, evidence count, criteria started, and open tasks.
- Top next actions.
- Claim map by EB1A criterion.
- Gap detector.
- Filing QA.
- Member request packs.
- Recommendation workspace.
- Review queue.
- Document QA.
- Exhibit assembly.
- USCIS packager.
- Petition spine, final merits strategy, traceable drafting support, criterion playbooks, argument bank, RFE/NOID workspace, SLA dashboard, and portfolio heatmap from backend services.

### Endeavor Letter Generator

- Compact attorney input workspace.
- Attorney-editable prompt sections for who the member is, field of expertise, proposed endeavor, current work continuity, future work plan, national importance, evidence emphasis, attorney strategy notes, tone guidance, and length constraints.
- Generate or regenerate endeavor letter.
- Review generated letter in document-style view.
- Estimated word count, page count, parsed document counts, and source/fallback details.

### Recommendation Letters

- Generate independent or dependent recommendation letters.
- Letters must be tied to a selected Critical Role or Original Contribution project.
- Project dropdown populated from submitted member projects/contributions.
- Recommender name, title, organization, relationship/credibility, facts to confirm, independence guidance, and attorney strategy notes.
- Generated draft list.
- Review generated letter in document-style view.
- Approve recommendation letter.
- Push approved letter to member messages.
- Member receives downloadable recommendation letter for review/signature.
- Download endpoint for generated letters.

### Batch Intake

- Upload ZIP files containing many evidence documents.
- Create batch review queue from ZIP contents.
- Per-file AI/default classification into criterion, evidence type, title, description, and folder decision.
- Per-item review and edit.
- Bulk update selected batch items.
- Commit reviewed batch items into evidence storage.
- Auto-materialize suggested folders when committing.
- Batch session history and committed/skipped status.

### Evidence Review

- Dedicated selected-member evidence review page.
- Evidence grouped by the same EB1A criterion structure as the member workspace.
- Recent evidence summaries and openable evidence links.
- Legal review without mixing evidence scanning into dossier or petition drafting.

### Attorney Messages, Assistant, And Support

- Dedicated attorney communications page.
- Ascend Navigator in attorney context.
- Support-ticket submission with selected member and portal context.

## Admin / Operations Portal

Primary user: admin / operations.

### Admin Home

- Operations snapshot across active members, AI usage, operational errors, and support load.
- Recent support ticket snapshot.
- Support root-cause mix.
- OpenAI call count and members using AI suggestions.

### System Health

- Portal and integration health cards.
- Health status for frontend, backend, database, S3 storage, OpenAI, Cost Explorer, and related AWS dependencies.
- Realtime average response times by tech stack.
- Response-time trend sparklines.
- Compact operational view for demos and support.

### Cost Explorer

- Refresh AWS and OpenAI cost data on demand.
- Last-refreshed timestamp.
- AWS actuals vs projections by daily, monthly, and yearly periods.
- AWS top-service breakdown.
- OpenAI actuals vs projections.
- OpenAI usage by portal and function.
- OpenAI tracked calls, OpenAI-sourced calls, fallback calls, and failed calls.
- OpenAI billing line items when available.
- Recent daily cost trend across AWS and OpenAI.

### Support Tickets

- Spreadsheet-style support queue.
- Metrics for open tickets, last 24 hours, likely bugs, and needs verification.
- Ticket rows with ticket number, category, portal, reporter, triage assessment, priority, created timestamp, and context link.
- Color-coded categories.
- AI/admin summary, root cause, and next actions in row hover/context.

### Debug Console

- Recent operational errors across auth, AI processing, evidence workflows, and system events.
- Member issue review.
- Member readiness, evidence count, open tasks, active sessions, and recent member-related errors.
- Recommended recovery actions.
- Reset member session action.
- Petition Acceleration compact diagnostic view.

### Admin Messages

- Dedicated operations communications page.
- Cross-suite messaging visibility according to admin role.

## AI-Assisted Features

- Evidence intake classification and summarization.
- Duplicate evidence handling guidance.
- Attorney petition draft generation.
- Endeavor letter generation.
- Recommendation letter generation.
- Ascend Navigator contextual Q&A for builder, leader, and attorney portals.
- Support-ticket triage summaries, likely root cause, and next actions.
- Petition acceleration claim mapping, gap detection, request packs, review queues, document QA, exhibit assembly, argument support, RFE/NOID support, and filing QA.
- Feature-level OpenAI usage metrics and fallback-call tracking.

## Storage, Evidence, And Archive Features

- Evidence files are attached to a member and case.
- Evidence is mapped to EB1A criterion and document type.
- Evidence may be organized into color-coded folders.
- Evidence metadata includes title, description, AI summary, quality score, timestamps, storage paths, and archive metadata.
- Generated Critical Role and Original Contribution PDFs are stored as evidence artifacts.
- Deleted evidence and deleted generated exports are soft-deleted by setting archived status and moving storage paths into archive locations.
- Storage supports AWS S3 active/archive buckets and local development paths.
- Member-facing UI abstracts away S3/local implementation details.

## EB1A Criteria Covered In Workflows

- Awards and prizes.
- Memberships.
- Published material / media.
- Judging.
- Original contributions.
- Scholarly articles / publications.
- Exhibitions / showcases.
- Leading or critical role.
- High salary / compensation.
- Commercial success.
- Recommendation or support evidence.
- Other supporting evidence.

## Primary Implementation References

- Frontend portal suite: `frontend-react/src/App.jsx`
- Frontend styling: `frontend-react/src/styles.css`
- FastAPI routes: `app/api.py`
- Core service layer: `app/services.py`
- Template exports: `app/template_exports.py`
- Storage abstraction: `app/storage.py`
- S3 integration: `app/s3_storage.py`
- Database and migrations: `app/db.py`

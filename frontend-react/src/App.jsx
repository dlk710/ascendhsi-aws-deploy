import React, { useEffect, useMemo, useRef, useState } from "react";

const runtimeApiUrl = window.ASCEND_RUNTIME_CONFIG?.apiUrl;
const API_URL = runtimeApiUrl !== undefined ? runtimeApiUrl : window.ASCEND_API_URL || import.meta.env.VITE_ASCEND_API_URL || "http://127.0.0.1:8000";
const LOGO_URL = "https://ascendhsi.com/wp-content/uploads/2024/08/Ascend-logo-no-bg.webp";
const AUTH_TOKEN_KEY = "ascend_member_token";
const AUTH_MEMBER_KEY = "ascend_member_info";
const ASSISTANT_SESSION_PREFIX = "ascend_assistant_thread_";
const DEFAULT_QUICK_LOGIN_PASSWORD = "Ascend123!";
const PORTAL_OPTIONS = [
  { value: "member", label: "Member Portal", intro: "Sign in to manage evidence, keep your profile current, and stay aligned with Ascend on what comes next.", username: "vas@ascendhsi.com" },
  { value: "builder", label: "Profile Builder Portal", intro: "Sign in to manage assigned members, push profile-building opportunities, and keep progress moving across your roster.", username: "builder@ascendhsi.com" },
  { value: "leader", label: "Leader Portal", intro: "Sign in to review member progress across builders, rebalance assignments, and keep the broader operation moving.", username: "leader@ascendhsi.com" },
  { value: "attorney", label: "Attorney Portal", intro: "Sign in to review the full client profile, assess gaps and strengths, and prepare petition strategy with complete context.", username: "attorney@ascendhsi.com" },
  { value: "admin", label: "Admin Portal", intro: "Sign in to monitor system health, operational flow, user activity, and case movement across the platform.", username: "admin@ascendhsi.com" },
];
const PORTAL_ROLE_VALUES = new Set(PORTAL_OPTIONS.map((item) => item.value));
const STAFF_ROLE_VALUES = new Set(["leader", "attorney", "admin"]);
const BUILDER_SECTIONS = new Set(["home", "members", "opportunities", "messages"]);
const ATTORNEY_SECTIONS = new Set(["home", "dossier", "petition", "batch", "evidence", "messages"]);
const LEADER_EXEC_SECTIONS = new Set(["home", "members", "risks", "capacity", "oversight", "opportunities", "batch", "messages"]);
const ADMIN_SECTIONS = new Set(["home", "health", "costs", "issues", "support", "debug", "messages"]);
const LOGIN_HELPERS_ENABLED = window.ASCEND_RUNTIME_CONFIG?.showDemoLogins !== false;
const PREVIEW_ROLES = [];
const PREVIEW_ACCOUNTS = {
  leader: [
    { username: "leader@ascendhsi.com", email: "leader@ascendhsi.com", display_name: "Ava Morales" },
    { username: "jonathan.price@ascendhsi.com", email: "jonathan.price@ascendhsi.com", display_name: "Jonathan Price" },
  ],
  attorney: [
    { username: "attorney@ascendhsi.com", email: "attorney@ascendhsi.com", display_name: "Sophia Chen" },
    { username: "marcus.reed@ascendhsi.com", email: "marcus.reed@ascendhsi.com", display_name: "Marcus Reed" },
  ],
  admin: [
    { username: "admin@ascendhsi.com", email: "admin@ascendhsi.com", display_name: "Maya Thompson" },
  ],
};
const DEV_LOGIN_ACCOUNTS = {
  member: [{ username: "vas@ascendhsi.com", email: "vas@ascendhsi.com", display_name: "Member", password: DEFAULT_QUICK_LOGIN_PASSWORD }],
  builder: [{ username: "builder@ascendhsi.com", email: "builder@ascendhsi.com", display_name: "Profile Builder", password: DEFAULT_QUICK_LOGIN_PASSWORD }],
  leader: PREVIEW_ACCOUNTS.leader.map((account) => ({ ...account, password: DEFAULT_QUICK_LOGIN_PASSWORD })),
  attorney: PREVIEW_ACCOUNTS.attorney.map((account) => ({ ...account, password: DEFAULT_QUICK_LOGIN_PASSWORD })),
  admin: PREVIEW_ACCOUNTS.admin.map((account) => ({ ...account, password: DEFAULT_QUICK_LOGIN_PASSWORD })),
};
const PLANNER_STATUS_OPTIONS = [
  { value: "planned", label: "Planned" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "blocked", label: "Blocked" },
];
const DOCUMENT_TYPE_OPTIONS = [
  "Invitation",
  "Attendance",
  "Thank You Note",
  "Acceptance or Selection",
  "Certificate or Completion",
  "Confirmation Email",
  "Agenda or Program",
  "Photo or Screenshot",
  "Receipt or Payment Proof",
  "Publication or Media",
  "Recommendation or Support",
  "Appointment or Contract",
  "Impact or Results",
  "Other",
];
const DOMAIN_OPTIONS = ["Healthcare", "Insurance", "Pharma", "Technology", "Other"];

const FOLDER_COLORS = {
  Emerald: "#2f7d67",
  Amber: "#c6a15b",
  Coral: "#c8674a",
  Plum: "#7a5ea8",
  Slate: "#51606f",
};

function authToken() {
  return window.localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

function authHeaders() {
  const token = authToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function persistAuth(token, member) {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  window.localStorage.setItem(AUTH_MEMBER_KEY, JSON.stringify(member));
}

function clearAuth() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem(AUTH_MEMBER_KEY);
}

function clearAssistantSessions() {
  Object.keys(window.sessionStorage).forEach((key) => {
    if (key.startsWith(ASSISTANT_SESSION_PREFIX)) {
      window.sessionStorage.removeItem(key);
    }
  });
}

function readStoredMember() {
  try {
    const raw = window.localStorage.getItem(AUTH_MEMBER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

function normalizePortalRole(role) {
  const cleaned = String(role || "").trim().toLowerCase();
  return PORTAL_ROLE_VALUES.has(cleaned) ? cleaned : "";
}

function roleConfig(role) {
  return role === "builder"
    ? {
        loginPath: "/api/builder/auth/login",
        mePath: "/api/builder/auth/me",
        logoutPath: "/api/builder/auth/logout",
        passwordPath: "/api/builder/auth/change-password",
      }
    : ["leader", "attorney", "admin"].includes(role)
    ? {
        loginPath: "/api/staff/auth/login",
        mePath: "/api/staff/auth/me",
        logoutPath: "/api/staff/auth/logout",
        passwordPath: "/api/staff/auth/change-password",
      }
    : {
        loginPath: "/api/auth/login",
        mePath: "/api/auth/me",
        logoutPath: "/api/auth/logout",
        passwordPath: "/api/auth/change-password",
      };
}

function portalMeta(role) {
  return PORTAL_OPTIONS.find((item) => item.value === role) || PORTAL_OPTIONS[0];
}

function requestedPortalSection(role, fallback = "home") {
  const requested = new URLSearchParams(window.location.search).get("section") || fallback;
  const allowed = {
    builder: BUILDER_SECTIONS,
    leader: LEADER_EXEC_SECTIONS,
    attorney: ATTORNEY_SECTIONS,
    admin: ADMIN_SECTIONS,
  };
  return allowed[role]?.has(requested) ? requested : fallback;
}

const MEMBER_PAGE_ALIASES = {
  home: "home",
  profile: "profile",
  planner: "planner",
  events: "planner",
  event_planner: "planner",
  "event-planner": "planner",
  intake: "intake",
  evidence_intake: "intake",
  "evidence-intake": "intake",
  messages: "messages",
};

function requestedMemberView(criteria = []) {
  const params = new URLSearchParams(window.location.search);
  const criterion = params.get("criterion") || "";
  const folder = params.get("folder") || "";
  const rawPage = (params.get("page") || "home").trim().toLowerCase();
  if (criterion) {
    const knownCriterion = !criteria.length || criteria.some((item) => item.code === criterion);
    return {
      view: knownCriterion ? { type: "workspace", criterionCode: criterion } : { type: "home", criterionCode: "" },
      folderId: knownCriterion ? folder : "",
      invalidPage: knownCriterion ? "" : criterion,
      invalidKind: knownCriterion ? "" : "criterion",
    };
  }
  const page = MEMBER_PAGE_ALIASES[rawPage];
  if (page) return { view: { type: page, criterionCode: "" }, folderId: "", invalidPage: "", invalidKind: "" };
  return { view: { type: "home", criterionCode: "" }, folderId: "", invalidPage: rawPage, invalidKind: "page" };
}

function readPortalRoute() {
  const params = new URLSearchParams(window.location.search);
  return {
    portal: normalizePortalRole(params.get("portal") || ""),
    page: params.get("page") || "",
    section: params.get("section") || "",
    memberId: params.get("member") || "",
  };
}

function isPreviewRole(role) {
  return PREVIEW_ROLES.includes(role);
}

function previewIdentity(role, username = "") {
  const account = (PREVIEW_ACCOUNTS[role] || []).find((item) => item.username === username) || (PREVIEW_ACCOUNTS[role] || [])[0];
  const meta = portalMeta(role);
  return {
    account_id: `preview_${role}_${(account?.username || meta.username).replace(/[^a-z0-9]+/gi, "_")}`,
    username: account?.username || meta.username,
    email: account?.email || meta.username,
    display_name: account?.display_name || (role === "leader" ? "Ava Morales" : role === "attorney" ? "Sophia Chen" : "Maya Thompson"),
    role,
  };
}

function previewLoginNote(role) {
  return `${portalMeta(role).label}: use your Ascend-issued credentials to continue.`;
}

function formatLastLogin(value) {
  if (!value) return "Not recorded yet";
  const normalized = String(value).includes("T") ? String(value) : String(value).replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized);
  const parsed = new Date(hasTimezone ? normalized : `${normalized}Z`);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString([], {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function LastLoginStamp({ user }) {
  return <span className="last-login-stamp">Last login: {formatLastLogin(user?.last_login_at)}</span>;
}

const HELP_MANUAL_SECTIONS = {
  common: [
    {
      title: "Navigate The Product Suite",
      summary: "Use the left navigation for portal sections, the Ascend logo to return home, and browser back/forward for page-specific navigation.",
      can: ["Open portal sections from the left menu.", "Return to the portal home page from the Ascend logo.", "Use page URLs to revisit a specific workflow."],
      cannot: ["Access another portal unless your login role allows it.", "Use Help Manual as a replacement for support when the system is broken."],
      steps: ["Click the Ascend logo for home.", "Use the left menu to open a section.", "Use browser back/forward to move through your recent portal journey."],
      keywords: ["navigation", "home", "back", "forward", "logo", "left menu", "page", "url"],
    },
    {
      title: "Account, Password, And Logout",
      summary: "The account menu in the top-right contains password actions, this Help Manual, and Logout.",
      can: ["Review last login time.", "Change your password.", "Log out when your work is complete."],
      cannot: ["See another user's password.", "Recover a forgotten password without the supported reset/admin process."],
      steps: ["Open the top-right account pill.", "Choose Change Password if needed.", "Use Help Manual for workflow questions.", "Click Logout only when finished."],
      keywords: ["account", "password", "logout", "last login", "menu", "security"],
    },
    {
      title: "Messages And Collaboration",
      summary: "Messages keep member, builder, attorney, leader, and admin communication tied to the product workflow.",
      can: ["Send portal-specific messages.", "Review conversation threads.", "Keep case communication separate from evidence and profile sections."],
      cannot: ["Use Messages as legal filing proof unless the attorney confirms it should be saved as evidence.", "Message users outside configured recipient options."],
      steps: ["Open Messages from the portal menu.", "Select or create a thread.", "Write a clear subject and action-oriented message.", "Mark urgent only when timing truly matters."],
      keywords: ["message", "messages", "thread", "communication", "urgent", "collaboration"],
    },
    {
      title: "Ascend Navigator And Help Manual",
      summary: "Help Manual explains how to use the product. Ascend Navigator answers Ascend case/workflow questions within strict guardrails.",
      can: ["Ask Help Manual how to use a portal feature.", "Ask Navigator about Ascend case context, evidence, assignments, and portal workflow.", "Use support when something appears broken."],
      cannot: ["Ask Navigator generic world questions.", "Treat Help Manual as legal advice.", "Assume AI answers replace attorney review."],
      steps: ["Use Help Manual for product instructions.", "Use Navigator for selected member/case workflow questions.", "Use Support or Issue Portal for bugs."],
      keywords: ["help", "manual", "navigator", "assistant", "ai", "guardrail", "support"],
    },
  ],
  member: [
    {
      title: "Complete Member Profile",
      summary: "The Profile section collects attorney-ready facts about identity, education, career, field, achievements, and final merits positioning.",
      can: ["Save profile updates.", "Fill identity, contact, professional background, and EB1A narrative fields.", "Return later to complete missing details."],
      cannot: ["Submit vague claims without evidence support.", "Edit staff-only assignments or legal review decisions."],
      steps: ["Open Profile.", "Complete identity and contact fields.", "Add current title, employer, field, specialization, education, biography, and achievement summaries.", "Save changes before leaving."],
      keywords: ["profile", "identity", "phone", "email", "title", "employer", "biography", "achievements", "save"],
    },
    {
      title: "Upload Evidence Intake",
      summary: "Evidence Intake is where members upload files, add a note, select or confirm category, and submit evidence into the organized storage path.",
      can: ["Upload evidence files.", "Use AI suggestion or choose a category manually.", "Review upload history with category, date, type, and links."],
      cannot: ["Upload unrelated files as EB1A evidence.", "Permanently delete submitted evidence without archive handling.", "Skip review before submitting important files."],
      steps: ["Open Evidence Intake.", "Write a short evidence note.", "Attach the file.", "Use AI suggestion or choose category manually.", "Review and submit.", "Check upload history."],
      keywords: ["upload", "evidence", "intake", "file", "category", "history", "submit", "ai suggestion"],
    },
    {
      title: "Evidence By Criterion",
      summary: "Evidence By Criterion shows EB1A categories and lets members drill into each category's uploaded items and guidance.",
      can: ["Review uploaded items by EB1A criterion.", "See where evidence is thin.", "Open category-specific workspaces."],
      cannot: ["Assume a category is satisfied only because a file exists.", "Change attorney legal conclusions from this page."],
      steps: ["Open Member Home.", "Review the evidence summary.", "Click a criterion.", "Review uploaded items and guidance.", "Upload missing support through Intake if needed."],
      keywords: ["criterion", "criteria", "evidence map", "category", "judging", "awards", "published material"],
    },
    {
      title: "Critical Role Projects",
      summary: "Critical Role Projects collect detailed project narratives showing role, organization distinction, business value, dates, and measurable impact.",
      can: ["Create multiple projects.", "Save drafts.", "Edit or delete entries with confirmation.", "Submit projects for export to evidence storage."],
      cannot: ["Use placeholder suggestions as real facts.", "Mix multiple companies into one unclear project when separation matters."],
      steps: ["Open the Critical Role criterion from Evidence By Criterion.", "Create or open a project.", "Add job title, company, dates, role, contributions, impact, and evidence notes.", "Save draft frequently.", "Submit when ready."],
      keywords: ["critical role", "leading role", "project", "job title", "company", "business value", "impact", "draft"],
    },
    {
      title: "Original Contributions",
      summary: "Original Contributions capture what you created, why it was original, who adopted it, and how it impacted the field or business.",
      can: ["Create multiple contribution entries.", "Save drafts.", "Edit entries before submission.", "Submit structured content into evidence storage."],
      cannot: ["Rely on general job duties alone.", "Claim originality without adoption, impact, references, or corroborating evidence."],
      steps: ["Open the Original Contributions criterion.", "Create a contribution.", "Explain the problem, your original solution, adoption, impact, metrics, and supporting documents.", "Save draft.", "Submit when attorney-ready."],
      keywords: ["original contribution", "innovation", "adoption", "impact", "field", "metrics", "draft"],
    },
    {
      title: "Event Planner",
      summary: "Event Planner helps members track future opportunities, target dates, evidence goals, and completion notes.",
      can: ["Plan upcoming opportunities.", "Link plans to criteria.", "Track planned and actual completion dates."],
      cannot: ["Guarantee that an opportunity will count for EB1A without review.", "Replace evidence uploads with planner notes."],
      steps: ["Open Event Planner.", "Add an event or opportunity.", "Choose the related criterion.", "Set target dates and notes.", "Update completion details after the event."],
      keywords: ["event planner", "event", "deadline", "opportunity", "planned", "completion"],
    },
  ],
  builder: [
    {
      title: "Review Assigned Members",
      summary: "Profile Builders use the member roster to search, triage readiness, review tasks, and identify the next best profile-building action.",
      can: ["Search by member name, phone, or email.", "Open member detail.", "Review readiness, evidence counts, gaps, and tasks."],
      cannot: ["Access members not assigned to your workspace unless leadership grants visibility.", "Override attorney legal strategy."],
      steps: ["Open Assigned Members.", "Search or select a member.", "Review readiness, criterion coverage, and tasks.", "Move to Opportunities or Messages for follow-up."],
      keywords: ["builder", "assigned members", "roster", "search", "readiness", "tasks"],
    },
    {
      title: "Assign Tasks And Opportunities",
      summary: "Builders can turn reusable opportunities or custom guidance into clear member tasks tied to EB1A criteria.",
      can: ["Create tasks for selected members.", "Use opportunity templates.", "Set evidence category and due date."],
      cannot: ["Submit evidence on behalf of a member without proper source/document handling.", "Assign legal conclusions as facts."],
      steps: ["Select a member.", "Open Opportunities.", "Choose a template or custom task.", "Add guidance, criterion, and due date.", "Assign the task."],
      keywords: ["opportunity", "task", "assign task", "due date", "guidance", "template"],
    },
    {
      title: "Review Evidence And Narrative Exports",
      summary: "Builders can review uploaded evidence, Critical Role exports, Original Contribution exports, and profile completeness before attorney review.",
      can: ["Open evidence groups.", "Review exported narrative submissions.", "Identify missing corroboration."],
      cannot: ["Edit submitted member facts without member confirmation.", "Treat unverified claims as final petition language."],
      steps: ["Open a member.", "Review Evidence Library.", "Check narrative exports.", "Message the member for missing details.", "Create tasks for gaps."],
      keywords: ["evidence review", "exports", "critical role export", "original contribution export", "library"],
    },
  ],
  attorney: [
    {
      title: "Select A Member For Legal Work",
      summary: "Attorney sections are member-specific, so select the member first before dossier, petition, letters, evidence, or batch work.",
      can: ["Search assigned cases.", "Select a member from the caseboard.", "Keep the selected member active across attorney sections."],
      cannot: ["Generate member-specific work without selecting a member.", "Access unassigned members unless leader/admin visibility allows it."],
      steps: ["Open Attorney Home.", "Search by name, phone, or email.", "Select the member.", "Move to Dossier, Petition, Recommendations, Batch Intake, or Evidence Review."],
      keywords: ["attorney", "select member", "caseboard", "search", "dossier", "petition"],
    },
    {
      title: "Member Dossier",
      summary: "The dossier summarizes profile facts, strengths, gaps, tasks, evidence, and narrative exports for attorney review.",
      can: ["Review identity and positioning.", "Inspect strengths and gaps.", "Review member-submitted narrative exports."],
      cannot: ["Assume every uploaded item is legally sufficient.", "Skip attorney judgment on final merits."],
      steps: ["Select a member.", "Open Member Dossier.", "Review profile summary.", "Check strengths, gaps, evidence, and exported narratives.", "Decide next legal follow-up."],
      keywords: ["dossier", "profile summary", "strengths", "gaps", "legal review"],
    },
    {
      title: "Petition And Endeavor Drafting",
      summary: "Attorney drafting tools generate working drafts from selected member context, evidence, tasks, and profile data.",
      can: ["Generate draft work product.", "Refresh drafts after new evidence.", "Use draft output for attorney review and editing."],
      cannot: ["File AI-generated content without attorney review.", "Invent facts not present in evidence or profile data."],
      steps: ["Select a member.", "Open Petition Generator or Endeavor Letter Generator.", "Review available context.", "Generate or refresh draft.", "Edit and validate before use."],
      keywords: ["petition", "endeavor", "draft", "generator", "legal work product"],
    },
    {
      title: "Recommendation Letters",
      summary: "Recommendation Letters help attorneys generate dependent or independent letters tied to member projects and evidence context.",
      can: ["Select project context.", "Generate draft letters.", "Review and approve before pushing to member."],
      cannot: ["Send unreviewed letters as final.", "Create letters for unsupported projects without enough facts."],
      steps: ["Select a member.", "Open Recommendation Letters.", "Choose project and letter type.", "Generate draft.", "Review, approve, and send to member for signature when ready."],
      keywords: ["recommendation", "letter", "dependent", "independent", "project", "signature"],
    },
    {
      title: "Batch Intake",
      summary: "Batch Intake stages ZIP uploads for human review before files are committed to organized evidence storage.",
      can: ["Upload ZIP files.", "Review AI-suggested categories.", "Approve files one by one or in bulk before commit."],
      cannot: ["Commit a batch without selecting the member.", "Treat AI routing as final without human review."],
      steps: ["Select a member.", "Open Batch Intake.", "Upload ZIP.", "Review suggested categories and folders.", "Approve or adjust.", "Commit reviewed files."],
      keywords: ["batch", "zip", "bulk upload", "queue", "commit", "folder"],
    },
  ],
  leader: [
    {
      title: "Invite Members And Route Assignments",
      summary: "Leaders invite members by email and can optionally assign a Profile Builder and Attorney at invite time or later.",
      can: ["Create member invites.", "Assign builder and attorney now or later.", "Track registration status."],
      cannot: ["Require assignments before invitation.", "Assume invitation email delivery is complete unless email integration is configured."],
      steps: ["Open Leader Home or Assignment Oversight.", "Enter member name, email, domain, title, and employer.", "Optionally choose builder and attorney.", "Create invite.", "Track registration and rebalance later."],
      keywords: ["leader", "invite", "registration", "assign builder", "assign attorney", "routing"],
    },
    {
      title: "Assignment Oversight",
      summary: "Assignment Oversight shows registration, builder assignment, attorney assignment, current stage, and quick actions.",
      can: ["Search member roster.", "Reassign builders and attorneys.", "Review unassigned or delayed cases."],
      cannot: ["Delete member work from this routing view.", "Replace attorney review with assignment status alone."],
      steps: ["Open Assignment Oversight.", "Search for a member.", "Review registration and stage.", "Select builder or attorney from dropdown.", "Open member review when needed."],
      keywords: ["assignment oversight", "routing", "builder assignment", "attorney assignment", "search roster"],
    },
    {
      title: "Timelines, Capacity, And Alerts",
      summary: "Leader dashboards show filing timelines, late cases, capacity pressure, risk, and portfolio movement.",
      can: ["Review who is running late.", "Inspect team capacity.", "Use watchlists to prioritize intervention."],
      cannot: ["Guarantee filing date without member readiness and attorney confirmation.", "Ignore RFE dotted-line planning when risk exists."],
      steps: ["Open Leader Home, Timelines, Risks, or Capacity.", "Review late/at-risk cases.", "Open the member.", "Reassign or message the responsible team as needed."],
      keywords: ["timeline", "gantt", "capacity", "late", "risk", "alert", "watchlist"],
    },
    {
      title: "Product Backlog",
      summary: "Leaders can capture enhancement requests, priorities, screenshots, and acceptance criteria as development backlog items.",
      can: ["Log feature requests.", "Set priority and portal impact.", "Add screenshots and acceptance criteria."],
      cannot: ["Deploy features directly from backlog.", "Skip testing/deployment workflow."],
      steps: ["Open Product Backlog.", "Enter title, request type, portals, priority, value, description, and acceptance criteria.", "Attach screenshots.", "Submit for review."],
      keywords: ["backlog", "feature request", "roadmap", "priority", "screenshot", "acceptance criteria"],
    },
  ],
  admin: [
    {
      title: "System Health",
      summary: "System Health shows portal status, tech stack health, response times, and operational signals.",
      can: ["Review portal and integration health.", "Check response times by stack layer.", "Monitor degraded services."],
      cannot: ["Fix infrastructure only from the UI.", "Ignore repeated degraded states without technical follow-up."],
      steps: ["Open Admin Portal.", "Go to Platform Health or System Health.", "Review status cards, response times, and degraded rows.", "Log or route issues when needed."],
      keywords: ["admin", "system health", "platform health", "response times", "tech stack", "degraded"],
    },
    {
      title: "Issue Portal And Debug Console",
      summary: "Issue Portal and Debug Console help admins log, track, prioritize, and investigate bugs in an excel-like table format.",
      can: ["Add issue rows.", "Update priority and status.", "Review debug context and affected members."],
      cannot: ["Use issue rows as a substitute for code fixes.", "Delete audit history without archive controls."],
      steps: ["Open Issue Portal or Debug Console.", "Review existing rows.", "Add or update issue details.", "Set status and priority.", "Use reproduction notes for fixes."],
      keywords: ["issue portal", "bug", "debug console", "status", "priority", "reproduce"],
    },
    {
      title: "Cost Explorer",
      summary: "Cost Explorer summarizes AWS and platform operating cost signals for review and planning.",
      can: ["Review current cost categories.", "Refresh cost data.", "Compare cost trends."],
      cannot: ["Guarantee final AWS invoice totals from estimates.", "Change AWS billing settings directly from the portal."],
      steps: ["Open Cost Explorer.", "Review service rows and trends.", "Refresh if needed.", "Investigate unusual increases with the deployment team."],
      keywords: ["cost explorer", "aws cost", "billing", "refresh", "cloud cost"],
    },
    {
      title: "Support Tickets And Activity Logs",
      summary: "Admins can review support tickets and product activity logs to understand user journeys and operational issues.",
      can: ["Review support ticket details.", "Inspect user activity signals.", "Use logs for debugging and audit support."],
      cannot: ["Expose sensitive data unnecessarily.", "Treat logs as user-facing legal evidence."],
      steps: ["Open Admin support or logs section.", "Filter by portal, member, issue, or timeframe.", "Review activity details.", "Escalate or close when resolved."],
      keywords: ["support", "ticket", "activity log", "audit", "journey", "operations"],
    },
  ],
};

function roleLabel(role) {
  return portalMeta(role || "member").label || "Ascend Portal";
}

function helpArticlesForRole(role) {
  const normalized = String(role || "member").toLowerCase();
  return [...HELP_MANUAL_SECTIONS.common, ...(HELP_MANUAL_SECTIONS[normalized] || [])];
}

function helpArticleScore(article, query) {
  const tokens = String(query || "").toLowerCase().split(/[^a-z0-9]+/).filter((token) => token.length > 1);
  if (!tokens.length) return 0;
  const haystack = [
    article.title,
    article.summary,
    ...(article.keywords || []),
    ...(article.can || []),
    ...(article.cannot || []),
    ...(article.steps || []),
  ].join(" ").toLowerCase();
  return tokens.reduce((score, token) => score + (haystack.includes(token) ? 1 : 0), 0);
}

function manualAnswerForQuery(role, query) {
  const articles = helpArticlesForRole(role);
  const trimmed = String(query || "").trim();
  if (!trimmed) {
    return {
      top: {
        title: `${roleLabel(role)} Help Manual`,
        summary: "Ask a usage question above, or review the manual sections below for step-by-step guidance.",
        can: ["Search product usage questions.", "Review what each portal can and cannot do.", "Follow clean workflow steps."],
        cannot: ["Provide legal advice.", "Fix bugs automatically.", "Answer non-Ascend general questions."],
        steps: ["Type a question such as 'How do I upload evidence?'", "Review the summarized answer.", "Open related manual sections for more detail."],
      },
      related: articles,
    };
  }
  const ranked = articles
    .map((article) => ({ article, score: helpArticleScore(article, trimmed) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .map((item) => item.article);
  if (!ranked.length) {
    return {
      top: {
        title: "No exact manual match",
        summary: "I could not find an exact help article for that question, but I can still guide you within Ascend Product Suite usage.",
        can: ["Ask about portal navigation, evidence, profile, assignments, messages, timelines, issue logging, or admin operations."],
        cannot: ["Answer general world knowledge questions.", "Provide immigration legal advice.", "Create or deploy code from this manual."],
        steps: ["Rephrase using the portal or feature name.", "Try words like evidence, profile, assignment, petition, messages, issue portal, or cost explorer.", "Use Support if the feature appears broken."],
      },
      related: articles.slice(0, 5),
    };
  }
  return { top: ranked[0], related: ranked.slice(1, 6) };
}

function HelpManualDialog({ open, role, portalTitle, query, onQueryChange, onClose }) {
  if (!open) return null;
  const answer = manualAnswerForQuery(role, query);
  const related = answer.related || [];
  return (
    <div className="help-manual-backdrop" onClick={onClose}>
      <section className="help-manual-panel" onClick={(event) => event.stopPropagation()}>
        <header className="help-manual-header">
          <div>
            <div className="section-kicker">Product Suite Help</div>
            <h3 className="section-title">{portalTitle || roleLabel(role)} Manual</h3>
            <p className="section-intro">Ask how to use Ascend. The manual returns a summarized answer, what users can do, what they cannot do, and clean steps.</p>
          </div>
          <button className="ghost compact-btn" type="button" onClick={onClose}>Close</button>
        </header>
        <label className="help-manual-search">
          Ask a product usage question
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Example: How do I upload evidence or assign an attorney?"
            autoFocus
          />
        </label>
        <article className="help-answer-card">
          <div className="section-kicker">Summarized Answer</div>
          <h4>{answer.top.title}</h4>
          <p>{answer.top.summary}</p>
          <div className="help-answer-grid">
            <div>
              <strong>Users can</strong>
              <ul>{(answer.top.can || []).map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
            <div>
              <strong>Users cannot</strong>
              <ul>{(answer.top.cannot || []).map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
          </div>
          <div className="help-steps">
            <strong>How to do it</strong>
            <ol>{(answer.top.steps || []).map((item) => <li key={item}>{item}</li>)}</ol>
          </div>
        </article>
        <div className="help-manual-library">
          <div className="section-kicker">Related Manual Sections</div>
          {related.map((article) => (
            <details key={article.title} className="help-manual-section">
              <summary>{article.title}</summary>
              <p>{article.summary}</p>
              <ol>{(article.steps || []).map((item) => <li key={item}>{item}</li>)}</ol>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}

function devLoginOptions(role) {
  if (!LOGIN_HELPERS_ENABLED) return [];
  const previewAccounts = isPreviewRole(role) ? PREVIEW_ACCOUNTS[role] || [] : [];
  if (previewAccounts.length) return previewAccounts;
  return DEV_LOGIN_ACCOUNTS[role] || [];
}

async function getJson(path, params) {
  const url = new URL(`${API_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }
  const response = await fetch(url, { headers: { ...authHeaders() } });
  const payload = await response.json();
  if (!response.ok) throw payload.detail || payload;
  return payload;
}

async function sendForm(path, formData, method = "POST") {
  const response = await fetch(`${API_URL}${path}`, { method, body: formData, headers: { ...authHeaders() } });
  const payload = await response.json();
  return { ok: response.ok, status: response.status, payload: payload.detail || payload };
}

async function sendJson(path, body, method = "POST") {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  return { ok: response.ok, status: response.status, payload: payload.detail || payload };
}

function formatUploadedAt(value) {
  if (!value) return "Uploaded date unavailable";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return `Uploaded ${value}`;
  return `Uploaded ${date.toLocaleString([], { month: "short", day: "2-digit", year: "numeric", hour: "numeric", minute: "2-digit" })}`;
}

function formatDateTime(value) {
  if (!value) return "Not refreshed yet";
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "2-digit", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatMoney(value, currency = "USD") {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency || "USD", maximumFractionDigits: 2 }).format(amount);
}

function formatCostAmount(value, currency = "USD") {
  if (value === null || value === undefined || value === "") return "N/A";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "N/A";
  if (amount !== 0 && Math.abs(amount) < 0.01) {
    const penny = new Intl.NumberFormat("en-US", { style: "currency", currency: currency || "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(0.01);
    return `${amount < 0 ? "-" : ""}< ${penny}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency: currency || "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
}

function formatResponseMs(value) {
  const amount = Number(value || 0);
  if (!amount) return "N/A";
  if (amount >= 1000) return `${(amount / 1000).toFixed(amount >= 2000 ? 1 : 2)}s`;
  return `${Math.round(amount)}ms`;
}

function healthStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (["healthy", "online", "success", "available", "configured", "synced"].includes(normalized)) return "completed";
  if (["degraded", "fallback", "needs_refresh", "warning"].includes(normalized)) return "planned";
  return "blocked";
}

function healthIcon(name) {
  const normalized = String(name || "").toLowerCase();
  if (normalized.includes("cloudfront")) return "CF";
  if (normalized.includes("load balancer")) return "ALB";
  if (normalized.includes("fargate") || normalized.includes("ecs")) return "ECS";
  if (normalized.includes("ecr")) return "ECR";
  if (normalized.includes("postgres") || normalized.includes("rds")) return "RDS";
  if (normalized.includes("dynamodb")) return "DDB";
  if (normalized.includes("secrets")) return "SM";
  if (normalized.includes("member")) return "M";
  if (normalized.includes("builder")) return "B";
  if (normalized.includes("leader")) return "L";
  if (normalized.includes("attorney")) return "A";
  if (normalized.includes("admin")) return "O";
  if (normalized.includes("api") || normalized.includes("fast")) return "API";
  if (normalized.includes("sqlite") || normalized.includes("database")) return "DB";
  if (normalized.includes("drive") || normalized.includes("s3") || normalized.includes("storage")) return "S";
  if (normalized.includes("openai") || normalized.includes("ai")) return "AI";
  return "OK";
}

function supportCategoryClass(category) {
  const normalized = String(category || "other").toLowerCase();
  if (normalized.includes("login") || normalized.includes("auth")) return "support-category-auth";
  if (normalized.includes("upload") || normalized.includes("evidence") || normalized.includes("storage")) return "support-category-evidence";
  if (normalized.includes("ai") || normalized.includes("assistant")) return "support-category-ai";
  if (normalized.includes("message") || normalized.includes("email")) return "support-category-message";
  if (normalized.includes("bug") || normalized.includes("error")) return "support-category-bug";
  return "support-category-other";
}

function cleanSummary(value) {
  if (!value) return "Evidence received and ready for Ascend review.";
  const lowered = value.toLowerCase();
  if (lowered.includes("google drive") || lowered.includes("archive") || lowered.includes("storage")) {
    return "Evidence received and ready for Ascend review.";
  }
  return value;
}

function folderColorName(value) {
  return Object.keys(FOLDER_COLORS).find((name) => FOLDER_COLORS[name] === value) || "Emerald";
}

function buildActionItems(criteria, evidenceItems) {
  const now = new Date();
  const due = (days) => {
    const date = new Date(now);
    date.setDate(date.getDate() + days);
    return date.toLocaleDateString([], { month: "short", day: "2-digit", year: "numeric" });
  };
  const items = [];
  criteria.filter((item) => !item.evidence_count).slice(0, 3).forEach((item, index) => {
    items.push({
      title: `Add evidence for ${item.name}`,
      detail: `Upload one strong document for ${item.name} so your file set is easier to progress in the next review cycle.`,
      due: due(index + 1),
    });
  });
  if (criteria.find((item) => item.code === "other" && item.evidence_count)) {
    items.push({
      title: "Review documents placed in Other",
      detail: "Check whether any unmatched files need better notes or should be moved into a stronger criterion.",
      due: due(2),
    });
  }
  if (evidenceItems.length) {
    items.push({
      title: "Review your latest upload",
      detail: `Confirm that ${evidenceItems[0].file_name} has the right context and supporting note for the member record.`,
      due: due(1),
    });
  }
  const strongest = [...criteria].sort((a, b) => b.evidence_count - a.evidence_count)[0];
  if (strongest && strongest.evidence_count) {
    items.push({
      title: `Strengthen ${strongest.name}`,
      detail: "Add one more high-signal file or supporting note so this criterion stays easy to work from.",
      due: due(4),
    });
  }
  return items.slice(0, 5);
}

function emptyPlannerForm() {
  return {
    member_role: "",
    issued_by: "",
    description: "",
    planned_completion_date: "",
    actual_completion_date: "",
    status: "planned",
    comments: "",
    criterion_code: "",
    folder_id: "",
  };
}

function emptyPlannerRow() {
  return {
    id: `draft_${Math.random().toString(36).slice(2, 10)}`,
    member_role: "",
    issued_by: "",
    description: "",
    planned_completion_date: "",
    actual_completion_date: "",
    status: "planned",
    comments: "",
    criterion_code: "",
    folder_id: "",
    isNew: true,
  };
}

function emptyProfileForm() {
  return {
    first_name: "",
    last_name: "",
    preferred_name: "",
    email: "",
    phone: "",
    date_of_birth: "",
    country_of_citizenship: "",
    country_of_residence: "",
    city_state: "",
    current_title: "",
    current_employer: "",
    employer_type: "",
    industry_domain: "",
    primary_field: "",
    specialization: "",
    years_experience: "",
    highest_degree: "",
    degree_field: "",
    institution: "",
    graduation_year: "",
    linkedin_url: "",
    personal_website: "",
    google_scholar_url: "",
    orcid_id: "",
    biography: "",
    top_achievements: "",
    awards_summary: "",
    memberships_summary: "",
    publications_summary: "",
    judging_summary: "",
    original_contributions_summary: "",
    leading_roles_summary: "",
    media_summary: "",
    salary_summary: "",
    proposed_final_merits_summary: "",
    target_filing_window: "",
    profile_confirmed: false,
  };
}

function groupBatchItems(session) {
  if (!session?.items?.length) return [];
  const groups = new Map();
  session.items.forEach((item) => {
    const key = item.final_folder_label || "Unassigned";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  return Array.from(groups.entries()).map(([label, items]) => ({ label, items }));
}

function caseStatusLabel(value) {
  return String(value || "unknown").replaceAll("_", " ");
}

function supportPriorityLabel(value) {
  const normalized = String(value || "normal").trim().toLowerCase();
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : "Normal";
}

function memberSearchText(member) {
  return [
    member?.first_name,
    member?.last_name,
    member?.display_name,
    member?.email,
    member?.phone,
  ].map((value) => String(value || "").toLowerCase()).join(" ");
}

function memberPhoneDigits(member) {
  return String(member?.phone || "").replace(/\D/g, "");
}

function filterMembersBySearch(members, query) {
  const normalized = String(query || "").trim().toLowerCase();
  if (!normalized) return members;
  const queryDigits = normalized.replace(/\D/g, "");
  return members.filter((member) => {
    const textMatch = memberSearchText(member).includes(normalized);
    const phoneMatch = queryDigits ? memberPhoneDigits(member).includes(queryDigits) : false;
    return textMatch || phoneMatch;
  });
}

function MemberSearchBox({ value, onChange, total, visible, label = "Search members" }) {
  return (
    <div className="member-search-box">
      <label>
        <span>{label}</span>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Search first name, last name, phone, or email"
        />
      </label>
      <small>Showing {visible} of {total} member(s)</small>
    </div>
  );
}

function AssignmentFlowGuide() {
  const steps = [
    ["Invite", "Leader sends the member registration link to the member email address."],
    ["Register", "Member opens the link, sets a password, and starts their profile."],
    ["Assign", "Profile Builder and Attorney are optional now and can be assigned later."],
    ["Build", "Member completes profile and evidence intake for team review."],
  ];
  return (
    <div className="assignment-flow-guide">
      {steps.map(([title, detail], index) => (
        <article key={title}>
          <span>{index + 1}</span>
          <strong>{title}</strong>
          <small>{detail}</small>
        </article>
      ))}
    </div>
  );
}

function emptyLeaderInviteForm() {
  return {
    first_name: "",
    last_name: "",
    email: "",
    industry_domain: "Technology",
    primary_field: "",
    current_title: "",
    current_employer: "",
    builder_id: "",
    attorney_id: "",
  };
}

function emptyIssueLogForm() {
  return {
    title: "",
    portal: "Admin Portal",
    section: "Issue Portal",
    priority: "P1",
    status: "open",
    description: "",
    reported_by: "",
  };
}

function emptySupportAttachment() {
  return {
    id: `support_file_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    file: null,
    description: "",
  };
}

function emptySupportForm(issueLocation = "") {
  return {
    issue_location: issueLocation,
    short_description: "",
    details: "",
    priority: "normal",
    is_blocking: "no",
    attachments: [emptySupportAttachment()],
  };
}

function inferDocumentType(text) {
  const combined = String(text || "").toLowerCase();
  const matches = [
    ["Invitation", ["invite", "invitation", "invited"]],
    ["Attendance", ["attendance", "attended", "participated", "participant"]],
    ["Thank You Note", ["thank you", "thanks", "appreciation"]],
    ["Acceptance or Selection", ["accepted", "selected", "selection"]],
    ["Certificate or Completion", ["certificate", "completion", "completed"]],
    ["Confirmation Email", ["confirmation", "confirmed", "registration"]],
    ["Agenda or Program", ["agenda", "program", "schedule"]],
    ["Photo or Screenshot", ["photo", "screenshot", ".png", ".jpg", ".jpeg"]],
    ["Receipt or Payment Proof", ["receipt", "invoice", "payment"]],
    ["Publication or Media", ["publication", "published", "media", "article"]],
    ["Recommendation or Support", ["recommendation", "endorsement", "support"]],
    ["Appointment or Contract", ["appointment", "contract", "agreement"]],
    ["Impact or Results", ["impact", "results", "outcome", "metrics"]],
  ];
  const found = matches.find(([, keywords]) => keywords.some((keyword) => combined.includes(keyword)));
  return found ? found[0] : "Other";
}

function FolderColorPicker({ value, onChange }) {
  return (
    <div className="color-picker" role="radiogroup" aria-label="Folder color">
      {Object.entries(FOLDER_COLORS).map(([name, color]) => (
        <button
          key={name}
          className={`swatch ${value === name ? "active" : ""}`}
          style={{ "--swatch": color }}
          title={name}
          type="button"
          onClick={() => onChange(name)}
        />
      ))}
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function roadmapStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (["complete", "completed", "active", "ready to generate", "available from organized evidence", "rfe-ready baseline", "exceptional", "strong"].includes(normalized)) return "completed";
  if (["in_progress", "developing", "needs_input", "needs_work", "build more evidence first", "needs packet hardening", "planned", "optional"].includes(normalized)) return "planned";
  return "blocked";
}

function RoadmapTimeline({ items = [] }) {
  if (!items.length) return <p className="empty-state">Timeline will appear once the case record loads.</p>;
  return (
    <div className="roadmap-timeline">
      {items.map((item) => (
        <article key={item.label} className={`roadmap-timeline-step ${item.optional ? "optional" : ""}`}>
          <span className={`status-dot ${roadmapStatusClass(item.status)}`} />
          <strong>{item.label}</strong>
          <small>{item.target_date}</small>
        </article>
      ))}
    </div>
  );
}

function MiniChecklist({ rows = [], emptyText = "No checklist rows available yet." }) {
  if (!rows.length) return <p className="empty-state">{emptyText}</p>;
  return (
    <div className="roadmap-row-table">
      {rows.map((row) => (
        <article key={row.label || row.area} className="roadmap-row">
          <div>
            <strong>{row.label || row.area}</strong>
            <small>{row.detail || row.next_step}</small>
          </div>
          <span className={`status-pill ${roadmapStatusClass(row.status)}`}>{String(row.status || "active").replaceAll("_", " ")}</span>
        </article>
      ))}
    </div>
  );
}

function CaseCommandCenter({ data, onOpenCriterion }) {
  if (!data) return null;
  const summary = data.summary || {};
  const tracker = data.criterion_tracker || [];
  return (
    <section className="panel roadmap-panel">
      <div className="panel-header">
        <div>
          <div className="section-kicker">EB1A Command Center</div>
          <h3 className="section-title">Criterion readiness, gaps, and next steps</h3>
          <p className="section-intro">A compact roadmap view that turns member-entered evidence into attorney-ready work queues.</p>
        </div>
        <span className="mini-note">{summary.target_state || "Evidence-building in progress"}</span>
      </div>
      <div className="roadmap-summary-grid">
        <MetricCard label="Strong Criteria" value={summary.strong_criteria || 0} />
        <MetricCard label="Started Criteria" value={summary.criteria_started || 0} />
        <MetricCard label="Evidence Items" value={summary.evidence_count || 0} />
        <MetricCard label="Readiness" value={`${summary.readiness_score || 0}%`} />
      </div>
      <div className="roadmap-grid">
        <article className="roadmap-card roadmap-card-wide">
          <div className="section-kicker">Filing Timeline</div>
          <RoadmapTimeline items={data.timeline || []} />
        </article>
        <article className="roadmap-card">
          <div className="section-kicker">Onboarding Intake</div>
          <MiniChecklist rows={data.onboarding || []} />
        </article>
        <article className="roadmap-card">
          <div className="section-kicker">Member Alerts</div>
          <MiniChecklist rows={(data.notifications || []).map((item) => ({ label: item.title, detail: item.detail, status: item.type === "task" ? "in_progress" : "needs_input" }))} emptyText="No open alerts." />
        </article>
      </div>
      <div className="roadmap-criterion-table">
        <div className="roadmap-criterion-head"><span>Criterion</span><span>Strength</span><span>Evidence</span><span>Score</span><span>Next action</span></div>
        {tracker.map((item) => (
          <button key={item.code} type="button" className="roadmap-criterion-row" onClick={() => onOpenCriterion?.(item.code)}>
            <strong>{item.name}</strong>
            <span className={`status-pill ${roadmapStatusClass(item.strength_label)}`}>{item.strength_label}</span>
            <span>{item.evidence_count}</span>
            <span>{item.average_score || 0}</span>
            <small>{item.next_prompt}</small>
          </button>
        ))}
      </div>
    </section>
  );
}

function BuilderWorkbenchPanel({ workbench }) {
  if (!workbench) return null;
  return (
    <section className="panel roadmap-panel panel-subsection">
      <div className="panel-header">
        <div>
          <div className="section-kicker">Builder EB1A Workbench</div>
          <h3 className="section-title">Narratives and evidence requests</h3>
          <p className="section-intro">Roadmap-aligned queues for AI narrative drafting, member requests, and criterion gap closure.</p>
        </div>
      </div>
      <div className="roadmap-grid">
        <article className="roadmap-card">
          <div className="section-kicker">AI Narrative Queue</div>
          <div className="task-mini-list">
            {(workbench.narrative_queue || []).map((item) => (
              <article key={`${item.criterion_code}_${item.criterion_name}`} className="task-mini-item">
                <strong>{item.criterion_name}</strong>
                <p>{item.draft_focus}</p>
                <div className="task-mini-meta"><span>{item.evidence_count} evidence</span><span>{item.strength_label}</span></div>
              </article>
            ))}
          </div>
        </article>
        <article className="roadmap-card">
          <div className="section-kicker">Evidence Request Queue</div>
          <div className="task-mini-list">
            {(workbench.evidence_request_queue || []).map((item) => (
              <article key={`${item.title}_${item.criterion_code}`} className="task-mini-item">
                <strong>{item.title}</strong>
                <p>{item.detail}</p>
                <div className="task-mini-meta"><span>{item.criterion_name}</span><span>{item.priority}</span><span>{item.due_date || "No due date"}</span></div>
              </article>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function LegalWorkbenchPanel({ workbench, onGeneratePetition }) {
  if (!workbench) return null;
  const caseManagement = workbench.case_management || {};
  return (
    <section className="panel roadmap-panel panel-subsection">
      <div className="panel-header">
        <div>
          <div className="section-kicker">Attorney Legal Workbench</div>
          <h3 className="section-title">Filing audit, RFE readiness, and letters</h3>
          <p className="section-intro">Keeps P1 legal workflow signals visible before the attorney commits to final petition drafting.</p>
        </div>
        {onGeneratePetition ? <button className="ghost compact-btn" type="button" onClick={onGeneratePetition}>Open petition draft</button> : null}
      </div>
      <div className="roadmap-summary-grid">
        <MetricCard label="Legal Stage" value={caseManagement.stage || "Evidence build"} />
        <MetricCard label="Strong Criteria" value={caseManagement.strong_criteria || 0} />
        <MetricCard label="Criteria Started" value={caseManagement.criteria_started || 0} />
        <MetricCard label="Est. Hours" value={workbench.time_tracking_summary?.estimated_review_hours || 0} />
      </div>
      <div className="roadmap-grid">
        <article className="roadmap-card">
          <div className="section-kicker">Pre-filing Checklist</div>
          <MiniChecklist rows={workbench.pre_filing_checklist || []} />
        </article>
        <article className="roadmap-card">
          <div className="section-kicker">RFE Contingency</div>
          <p className="section-intro">{workbench.rfe_response?.detail}</p>
          <RoadmapTimeline items={(workbench.rfe_response?.dotted_timeline || []).map((item) => ({ label: item.label, target_date: `${item.target_days} days`, status: "optional", optional: true }))} />
        </article>
        <article className="roadmap-card roadmap-card-wide">
          <div className="section-kicker">Dependent Recommendation Letters</div>
          <div className="roadmap-row-table">
            {(workbench.recommendation_letters?.project_options || []).map((item) => (
              <article key={`${item.id}_${item.criterion_code}`} className="roadmap-row">
                <div>
                  <strong>{item.title}</strong>
                  <small>{item.criterion_name}</small>
                </div>
                <span className="status-pill planned">project mapped</span>
              </article>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function LeaderBusinessPanel({ insights }) {
  const performance = insights?.attorney_performance || [];
  const revenueRows = insights?.revenue_analytics?.rows || [];
  if (!performance.length && !revenueRows.length) return null;
  return (
    <section className="panel roadmap-panel" style={{ marginTop: "18px" }}>
      <div className="panel-header">
        <div>
          <div className="section-kicker">Leader Product Intelligence</div>
          <h3 className="section-title">Attorney capacity and revenue planning</h3>
          <p className="section-intro">Portfolio-level signals for delivery speed, petition readiness, and operational exposure.</p>
        </div>
        <span className="mini-note">{insights?.revenue_analytics?.assumption || "Planning estimates only"}</span>
      </div>
      <div className="leader-business-grid">
        <div className="roadmap-criterion-table">
          <div className="leader-performance-head"><span>Attorney</span><span>Cases</span><span>Ready</span><span>Risk</span><span>Avg</span><span>Signal</span></div>
          {performance.map((item) => (
            <article key={item.id || item.display_name} className="leader-performance-row">
              <strong>{item.display_name}</strong>
              <span>{item.assigned_cases}</span>
              <span>{item.petition_ready_cases}</span>
              <span>{item.high_risk_cases}</span>
              <span>{item.avg_readiness}%</span>
              <span className={`status-pill ${item.capacity_signal === "Healthy" ? "completed" : item.capacity_signal === "Available" ? "planned" : "blocked"}`}>{item.capacity_signal}</span>
            </article>
          ))}
        </div>
        <div className="roadmap-row-table">
          {revenueRows.map((row) => (
            <article key={row.label} className="roadmap-row">
              <div>
                <strong>{row.label}</strong>
                <small>{row.detail}</small>
              </div>
              <span>{formatMoney(row.value, insights?.revenue_analytics?.currency || "USD")}</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function AdminProductOpsPanel({ dashboard }) {
  const productOps = dashboard?.product_ops;
  const userManagement = dashboard?.user_management;
  if (!productOps && !userManagement) return null;
  const roleRows = Object.entries(userManagement?.roles || {}).map(([role, count]) => ({
    label: role.replaceAll("_", " "),
    detail: `${count} account(s)`,
    status: count ? "active" : "planned",
  }));
  return (
    <section className="panel roadmap-panel" style={{ marginTop: "18px" }}>
      <div className="panel-header">
        <div>
          <div className="section-kicker">Product Ops Controls</div>
          <h3 className="section-title">Roadmap P0/P1 admin coverage</h3>
          <p className="section-intro">Issue Portal, Cost Explorer, System Health, user inventory, and audit logs in one admin control surface.</p>
        </div>
        <span className="mini-note">{userManagement?.total_accounts || 0} accounts tracked</span>
      </div>
      <div className="roadmap-grid">
        <article className="roadmap-card">
          <div className="section-kicker">Admin Readiness Rows</div>
          <MiniChecklist rows={productOps?.readiness_rows || []} />
        </article>
        <article className="roadmap-card">
          <div className="section-kicker">User Management Inventory</div>
          <MiniChecklist rows={roleRows} />
        </article>
        <article className="roadmap-card roadmap-card-wide">
          <div className="section-kicker">Recent Login Audit</div>
          <div className="roadmap-row-table">
            {(dashboard?.audit_log || []).slice(0, 5).map((item) => (
              <article key={item.id || `${item.actor_key}_${item.created_at}`} className="roadmap-row">
                <div>
                  <strong>{item.actor_key || item.actor_role}</strong>
                  <small>{item.portal || "system"} • {item.message || item.event_type}</small>
                </div>
                <span>{formatDateTime(item.created_at)}</span>
              </article>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function ResponseSparkline({ points = [] }) {
  const values = points.map((point) => Number(point.ms) || 0);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const spread = Math.max(maxValue - minValue, 1);
  const polyline = values.map((value, index) => {
    const x = values.length <= 1 ? 96 : Math.round((index / (values.length - 1)) * 96);
    const y = Math.round(32 - ((value - minValue) / spread) * 26);
    return `${x},${Math.max(4, Math.min(32, y))}`;
  }).join(" ");
  return (
    <svg className="response-sparkline" viewBox="0 0 96 36" role="img" aria-label="Response time trend">
      <polyline points={polyline} />
      {values.map((value, index) => {
        const x = values.length <= 1 ? 96 : Math.round((index / (values.length - 1)) * 96);
        const y = Math.round(32 - ((value - minValue) / spread) * 26);
        return <circle key={`${index}_${value}`} cx={x} cy={Math.max(4, Math.min(32, y))} r="2.2" />;
      })}
    </svg>
  );
}

function IssueLogPanel({ backlog, form, busy, onFormChange, onSubmit, onUpdate, onRemove }) {
  const items = backlog?.items || [];
  return (
    <section className="product-backlog-panel admin-ops-compact">
      <div className="panel admin-table-panel">
        <div className="panel-header">
          <div>
            <div className="section-kicker">Issue Portal</div>
            <h3 className="section-title">Bug log across the product suite</h3>
            <p className="section-intro">Add, update, and remove issue rows with priority, status, timestamps, and AWS DynamoDB sync state in one spreadsheet-style registry.</p>
          </div>
          <span className="mini-note">AWS mirror: {backlog?.aws_table_name || "ascend_product_issue_logs"} • {backlog?.aws_region || "us-east-2"}</span>
        </div>
        <div className="admin-count-strip">
          {["P0", "P1", "P2", "P3"].map((priority) => (
            <span key={priority}><strong>{priority}</strong>{backlog?.priority_counts?.[priority] || 0}</span>
          ))}
          {["open", "triaged", "in_progress", "blocked", "fixed", "closed"].map((status) => (
            <span key={status}><strong>{status.replaceAll("_", " ")}</strong>{backlog?.status_counts?.[status] || 0}</span>
          ))}
        </div>

        <form className="issue-entry-row" onSubmit={onSubmit}>
          <input value={form.title} onChange={(event) => onFormChange("title", event.target.value)} placeholder="Issue title" aria-label="Issue title" />
          <select value={form.portal} onChange={(event) => onFormChange("portal", event.target.value)} aria-label="Portal">
            {["Member Portal", "Profile Builder Portal", "Leader Portal", "Attorney Portal", "Admin Portal"].map((option) => <option key={option} value={option}>{option}</option>)}
          </select>
          <input value={form.section} onChange={(event) => onFormChange("section", event.target.value)} placeholder="Section" aria-label="Section" />
          <select value={form.priority} onChange={(event) => onFormChange("priority", event.target.value)} aria-label="Priority">
            <option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option>
          </select>
          <select value={form.status} onChange={(event) => onFormChange("status", event.target.value)} aria-label="Status">
            <option value="open">Open</option><option value="triaged">Triaged</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option><option value="fixed">Fixed</option><option value="closed">Closed</option>
          </select>
          <input value={form.reported_by} onChange={(event) => onFormChange("reported_by", event.target.value)} placeholder="Reporter" aria-label="Reported by" />
          <input value={form.description} onChange={(event) => onFormChange("description", event.target.value)} placeholder="Short reproduction notes" aria-label="Description" />
          <button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Saving" : "Add row"}</button>
        </form>

        <div className="issue-log-table">
          <div className="issue-log-row issue-log-head"><span>Bug ID</span><span>Issue</span><span>Portal / Section</span><span>Priority</span><span>Status</span><span>Reporter</span><span>Updated</span><span>AWS</span><span>Actions</span></div>
          {items.map((item) => (
            <article key={item.bug_id} className={`issue-log-row priority-${item.priority?.toLowerCase()}`}>
              <div>
                <strong>{item.bug_id}</strong>
                <small>{item.created_at}</small>
              </div>
              <div>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </div>
              <span>{item.portal} / {item.section}</span>
              <select value={item.priority} onChange={(event) => onUpdate(item, { priority: event.target.value })}>
                <option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option>
              </select>
              <select value={item.status} onChange={(event) => onUpdate(item, { status: event.target.value })}>
                <option value="open">Open</option><option value="triaged">Triaged</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option><option value="fixed">Fixed</option><option value="closed">Closed</option>
              </select>
              <span>{item.reported_by || "Admin"}</span>
              <span>{item.updated_at || item.created_at}</span>
              <span className={`status-pill ${item.aws_sync_status === "synced" ? "completed" : item.aws_sync_status === "pending" ? "planned" : "blocked"}`}>{item.aws_sync_status || "pending"}</span>
              <button className="danger compact-btn" type="button" onClick={() => onRemove(item)}>Remove</button>
            </article>
          ))}
          {!items.length ? <p className="empty-state">No bug logs captured yet. Use the add row above to start the registry.</p> : null}
        </div>
      </div>
    </section>
  );
}

function formatRelativeDays(days) {
  const count = Number(days || 0);
  if (count <= 0) return "Active today";
  if (count === 1) return "1 day ago";
  return `${count} days ago`;
}

function riskPillClass(level) {
  if (level === "High") return "blocked";
  if (level === "Moderate") return "planned";
  return "completed";
}

function percentWidth(value, max) {
  const safeMax = Math.max(Number(max) || 0, 1);
  const ratio = Math.max(0, Number(value) || 0) / safeMax;
  return `${Math.max(10, Math.round(ratio * 100))}%`;
}

function LeaderPerspectiveSwitch({ value, onChange }) {
  const options = [
    { value: "leader", label: "CEO View", detail: "Executive dashboards and routing control" },
    { value: "builder", label: "Builder View", detail: "See the profile builder workspace as leader" },
    { value: "attorney", label: "Attorney View", detail: "See the attorney workspace as leader" },
  ];
  return (
    <div className="perspective-switch" role="tablist" aria-label="Leader portal perspectives">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`perspective-chip ${value === option.value ? "active" : ""}`}
          onClick={() => onChange(option.value)}
        >
          <strong>{option.label}</strong>
          <span>{option.detail}</span>
        </button>
      ))}
    </div>
  );
}

function ExecutiveBarList({ items = [], valueKey = "count", labelKey = "label", metaKey = "", emptyText = "No data available yet." }) {
  const maxValue = items.length ? Math.max(...items.map((item) => Number(item[valueKey]) || 0), 1) : 1;
  if (!items.length) return <p className="empty-state">{emptyText}</p>;
  return (
    <div className="executive-bar-list">
      {items.map((item) => (
        <article key={`${item[labelKey]}_${item[valueKey]}`} className="executive-bar-row">
          <div className="executive-bar-copy">
            <strong>{item[labelKey]}</strong>
            {metaKey && item[metaKey] ? <span>{item[metaKey]}</span> : null}
          </div>
          <div className="executive-bar-track">
            <div className="executive-bar-fill" style={{ width: percentWidth(item[valueKey], maxValue) }} />
          </div>
          <strong className="executive-bar-value">{item[valueKey]}</strong>
        </article>
      ))}
    </div>
  );
}

function TimelinePlot({ points = [] }) {
  const maxValue = points.length ? Math.max(...points.map((item) => Number(item.total_activity) || 0), 1) : 1;
  if (!points.length) return <p className="empty-state">No recent execution data yet.</p>;
  return (
    <div className="timeline-plot">
      {points.map((point) => (
        <article key={point.label} className="timeline-column">
          <div className="timeline-column-rail">
            <div className="timeline-column-fill" style={{ height: percentWidth(point.total_activity, maxValue) }} />
          </div>
          <strong>{point.total_activity}</strong>
          <span>{point.label}</span>
          <small>{point.invites} invites • {point.builder_assignments} builders • {point.attorney_assignments} attorneys</small>
        </article>
      ))}
    </div>
  );
}

function WatchlistTable({ rows = [], onOpenMember }) {
  if (!rows.length) return <p className="empty-state">No intervention cases right now.</p>;
  return (
    <div className="watchlist-table">
      <div className="watchlist-head">
        <span>Case</span>
        <span>Stage</span>
        <span>Owner</span>
        <span>Risk</span>
        <span>Last activity</span>
        <span>Next action</span>
        <span>Open</span>
      </div>
      {rows.map((row) => (
        <div key={row.client_id} className="watchlist-row">
          <div>
            <strong>{row.display_name}</strong>
            <span>Readiness {row.readiness_score}% • {row.bottleneck}</span>
          </div>
          <span>{row.stage_label}</span>
          <span>{row.owner_name}</span>
          <span className={`status-pill ${riskPillClass(row.risk_level)}`}>{row.risk_level}</span>
          <span>{formatRelativeDays(row.days_since_activity)}</span>
          <span>{row.next_action}</span>
          <div className="event-row-actions">
            <button className="ghost compact-btn" type="button" onClick={() => onOpenMember(row.client_id)}>Review</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function NavIcon({ name }) {
  const commonProps = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };
  switch (name) {
    case "home":
      return <svg {...commonProps}><path d="M3 11.5 12 4l9 7.5" /><path d="M6.5 10.5V20h11V10.5" /></svg>;
    case "members":
      return <svg {...commonProps}><path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" /><path d="M16 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z" /><path d="M3.5 19a4.5 4.5 0 0 1 9 0" /><path d="M13.5 19a3.5 3.5 0 0 1 7 0" /></svg>;
    case "batch":
      return <svg {...commonProps}><rect x="4" y="5" width="16" height="4" rx="1.5" /><rect x="4" y="10" width="16" height="4" rx="1.5" /><rect x="4" y="15" width="16" height="4" rx="1.5" /></svg>;
    case "opportunities":
      return <svg {...commonProps}><path d="m12 4 1.8 4.4L18 10l-4.2 1.6L12 16l-1.8-4.4L6 10l4.2-1.6Z" /></svg>;
    case "oversight":
      return <svg {...commonProps}><circle cx="11" cy="11" r="6" /><path d="m20 20-4.2-4.2" /></svg>;
    case "risks":
      return <svg {...commonProps}><path d="M12 4.5 20 19.5H4z" /><path d="M12 9v4.5" /><path d="M12 17h.01" /></svg>;
    case "capacity":
      return <svg {...commonProps}><path d="M4.5 18.5h15" /><path d="M7 18.5V11" /><path d="M12 18.5V6.5" /><path d="M17 18.5V9" /></svg>;
    case "messages":
      return <svg {...commonProps}><path d="M4 6.5h16v11H4z" /><path d="m4.5 7 7.5 6 7.5-6" /></svg>;
    case "dossier":
      return <svg {...commonProps}><path d="M7 4.5h8l3 3V19.5H7z" /><path d="M15 4.5v3h3" /><path d="M10 12h5" /><path d="M10 15h5" /></svg>;
    case "petition":
      return <svg {...commonProps}><path d="M8 4.5h8l3 3V19.5H8z" /><path d="M16 4.5v3h3" /><path d="M10.5 11.5h5" /><path d="M10.5 14.5h5" /><path d="M10.5 17.5h3" /></svg>;
    case "evidence":
      return <svg {...commonProps}><rect x="5" y="5" width="14" height="16" rx="2" /><path d="M9 9h6" /><path d="M9 13h6" /><path d="M9 17h4" /></svg>;
    case "profile":
      return <svg {...commonProps}><circle cx="12" cy="8" r="3.2" /><path d="M5 19a7 7 0 0 1 14 0" /></svg>;
    case "planner":
      return <svg {...commonProps}><rect x="4" y="6" width="16" height="14" rx="2" /><path d="M8 4v4" /><path d="M16 4v4" /><path d="M4 10h16" /></svg>;
    case "intake":
      return <svg {...commonProps}><path d="M12 5v10" /><path d="m8 11 4 4 4-4" /><path d="M5 19h14" /></svg>;
    case "health":
      return <svg {...commonProps}><path d="M4 13h3l2-4 3 7 2-5h6" /></svg>;
    case "issues":
      return <svg {...commonProps}><path d="M7 4.5h10l2 2v13H5v-13z" /><path d="M9 10h6" /><path d="M9 13h6" /><path d="M9 16h3" /></svg>;
    case "debug":
      return <svg {...commonProps}><circle cx="6" cy="12" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="18" cy="12" r="1.3" /></svg>;
    default:
      return <svg {...commonProps}><circle cx="12" cy="12" r="7" /></svg>;
  }
}

function SupportIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 4.5a7.5 7.5 0 0 0-7.5 7.5v2.5a2 2 0 0 0 2 2H8" />
      <path d="M12 4.5a7.5 7.5 0 0 1 7.5 7.5v2.5a2 2 0 0 1-2 2H16" />
      <path d="M8 14.5a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2" />
      <path d="M12 18.5v1.5" />
    </svg>
  );
}

function SupportActionIcon({ name }) {
  const commonProps = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };
  switch (name) {
    case "plus":
      return <svg {...commonProps}><path d="M12 5v14" /><path d="M5 12h14" /></svg>;
    case "mail":
      return <svg {...commonProps}><path d="M4 6.5h16v11H4z" /><path d="m4.5 7 7.5 6 7.5-6" /></svg>;
    case "send":
      return <svg {...commonProps}><path d="m4.5 12 14-6-4 12-2.2-4.2z" /><path d="m10.3 13.8 3.8-3.8" /></svg>;
    case "reset":
      return <svg {...commonProps}><path d="M4 12a8 8 0 1 0 2.3-5.7" /><path d="M4 4.5v4.2h4.2" /></svg>;
    case "hide":
      return <svg {...commonProps}><path d="M6 9.5 12 15.5 18 9.5" /></svg>;
    case "remove":
      return <svg {...commonProps}><path d="m7 7 10 10" /><path d="M17 7 7 17" /></svg>;
    case "clip":
      return <svg {...commonProps}><path d="M9 12.5 15.3 6.2a3 3 0 1 1 4.2 4.2l-8.1 8.1a5 5 0 1 1-7.1-7.1l8.5-8.5" /></svg>;
    default:
      return <svg {...commonProps}><circle cx="12" cy="12" r="7" /></svg>;
  }
}

function SidebarNav({ items, value, onChange }) {
  function iconForItem(itemValue) {
    if (itemValue === "home") return "home";
    if (itemValue === "members") return "members";
    if (itemValue === "batch") return "batch";
    if (itemValue === "opportunities") return "opportunities";
    if (itemValue === "oversight") return "oversight";
    if (itemValue === "risks") return "risks";
    if (itemValue === "capacity") return "capacity";
    if (itemValue === "messages") return "messages";
    if (itemValue === "dossier") return "dossier";
    if (itemValue === "petition") return "petition";
    if (itemValue === "evidence") return "evidence";
    if (itemValue === "profile") return "profile";
    if (itemValue === "planner") return "planner";
    if (itemValue === "intake") return "intake";
    if (itemValue === "health") return "health";
    if (itemValue === "issues") return "issues";
    if (itemValue === "costs") return "health";
    if (itemValue === "debug") return "debug";
    return "home";
  }

  return (
    <div className="sidebar-nav" role="navigation" aria-label="Portal sections">
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          className={`sidebar-nav-btn ${value === item.value ? "active" : ""}`}
          onClick={() => onChange(item.value)}
        >
          <span className="nav-icon-wrap">
            <NavIcon name={iconForItem(item.value)} />
          </span>
          <span className="nav-label">{item.label}</span>
        </button>
      ))}
    </div>
  );
}

function PortalBrand({ onHome, label = "Go to portal home" }) {
  return (
    <button className="brand-home-button" type="button" onClick={onHome} aria-label={label}>
      <img className="brand-logo" src={LOGO_URL} alt="Ascend HSI logo" />
      <span className="brand">Ascend HSI</span>
    </button>
  );
}

function ThreadedMessageCenter({
  title,
  intro,
  threads,
  recipientOptions,
  composer,
  selectedThreadId,
  busy,
  onSelectThread,
  onComposerChange,
  onSend,
  onDeleteMessage,
  onToggleRead,
  actor,
}) {
  const [recipientQuery, setRecipientQuery] = useState("");
  const [threadExpanded, setThreadExpanded] = useState(true);
  const selectedThread = threads.find((item) => item.thread_id === selectedThreadId) || threads[0] || null;
  const replyMode = Boolean(selectedThread);
  const activeReplyId = composer.reply_to_id || "";
  const filteredRecipients = recipientOptions.filter((item) => {
    const query = recipientQuery.trim().toLowerCase();
    if (!query) return true;
    return [item.name, item.role, item.email, item.detail].some((value) => String(value || "").toLowerCase().includes(query));
  });
  const selectedRecipient = recipientOptions.find((item) => item.role === composer.recipient_role && item.key === composer.recipient_key);
  const activeReplyMessage = selectedThread?.messages?.find((item) => item.id === activeReplyId) || null;

  function formatMessageStamp(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }

  function conversationTree(messages) {
    const byId = new Map();
    const children = new Map();
    const ordered = [...messages].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    ordered.forEach((item) => {
      byId.set(item.id, item);
      children.set(item.id, []);
    });
    const roots = [];
    ordered.forEach((item) => {
      const parentId = item.parent_message_id;
      if (parentId && children.has(parentId)) {
        children.get(parentId).push(item);
      } else {
        roots.push(item);
      }
    });
    function buildNode(item, depth = 0) {
      return {
        ...item,
        depth,
        children: (children.get(item.id) || []).map((child) => buildNode(child, depth + 1)),
      };
    }
    return roots.map((item) => buildNode(item));
  }

  function renderConversationNode(item) {
    const received = item.recipient_role === actor.role && item.recipient_key === actor.key;
    const mine = item.sender_role === actor.role && item.sender_key === actor.key;
    const displayName = received ? item.sender_name : mine ? "You" : item.sender_name;
    const childCount = item.children?.length || 0;
    const replyingHere = activeReplyId === item.id;
    return (
      <article key={item.id} className={`message-bubble ${mine ? "mine" : "theirs"} ${threadExpanded ? "" : "collapsed"}`} style={{ "--depth": item.depth }}>
        <div className="message-bubble-head">
          <div className="message-bubble-author">
            <strong>{displayName}</strong>
            <span className={`recipient-role recipient-role-${received ? item.sender_role : item.recipient_role}`}>{received ? item.sender_role : mine ? actor.role : item.recipient_role}</span>
            {item.urgent ? <span className="status-pill blocked">Urgent</span> : null}
          </div>
          <span className="message-bubble-time">{formatMessageStamp(item.created_at)}</span>
        </div>
        {threadExpanded ? (
          <React.Fragment>
            <p>{item.body}</p>
            <div className="message-bubble-actions">
              <button className="ghost compact-btn" type="button" onClick={() => {
                onComposerChange("reply_to_id", item.id);
                onComposerChange("body", "");
                onComposerChange("urgent", false);
              }}>Reply</button>
              {received ? (
                <button className="ghost compact-btn" type="button" onClick={() => onToggleRead(item, !item.is_read)}>
                  {item.is_read ? "Mark unread" : "Mark read"}
                </button>
              ) : null}
              <button className="ghost compact-btn" type="button" onClick={() => onDeleteMessage(item.id)}>Delete</button>
            </div>
            {replyingHere ? (
              <form className="inline-reply-box" onSubmit={onSend}>
                <div className="inline-reply-header">
                  <strong>Reply to {displayName}</strong>
                  <button className="ghost compact-btn" type="button" onClick={() => {
                    onComposerChange("reply_to_id", "");
                    onComposerChange("body", "");
                    onComposerChange("urgent", false);
                  }}>Cancel</button>
                </div>
                <textarea value={composer.body} onChange={(event) => onComposerChange("body", event.target.value)} placeholder="Write your reply" />
                <div className="inline-reply-actions">
                  <label className="message-urgent-toggle">
                    <input type="checkbox" checked={Boolean(composer.urgent)} onChange={(event) => onComposerChange("urgent", event.target.checked)} />
                    <span>Urgent</span>
                  </label>
                  <button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Sending..." : "Send"}</button>
                </div>
              </form>
            ) : null}
            {childCount ? (
              <div className="message-children">
                {item.children.map((child) => renderConversationNode(child))}
              </div>
            ) : null}
          </React.Fragment>
        ) : (
          <div className="message-bubble-summary">
            <span>{item.body}</span>
            {childCount ? <span>{childCount} repl{childCount === 1 ? "y" : "ies"}</span> : null}
          </div>
        )}
      </article>
    );
  }

  React.useEffect(() => {
    setThreadExpanded(true);
  }, [selectedThreadId]);

  return (
    <section className="panel" style={{ marginTop: "18px" }}>
      <div className="section-kicker">Messages</div>
      <h3 className="section-title">{title}</h3>
      <p className="section-intro">{intro}</p>
      <div className="message-layout">
        <section className="message-threads">
          <div className="panel-header">
            <div>
              <strong>Inbox</strong>
              <span>Newest active conversations first.</span>
            </div>
            <button className="ghost compact-btn" type="button" onClick={() => onSelectThread("")}>New thread</button>
          </div>
          <div className="task-mini-list">
            {threads.length ? threads.map((thread) => (
              <button key={thread.thread_id} type="button" className={`thread-card ${selectedThread?.thread_id === thread.thread_id ? "active" : ""}`} onClick={() => onSelectThread(thread.thread_id)}>
                <div className="thread-card-top">
                  <strong>{thread.subject}</strong>
                  <span>{formatMessageStamp(thread.latest_message?.created_at || "")}</span>
                </div>
                <p>{thread.latest_message?.body || "No message body."}</p>
                <div className="thread-card-meta">
                  <span>{thread.messages?.length || 0} message{(thread.messages?.length || 0) === 1 ? "" : "s"}</span>
                  <span>{thread.latest_message?.sender_name || thread.latest_message?.recipient_name || ""}</span>
                </div>
                <div className="task-mini-meta">
                  <span className={`recipient-role recipient-role-${thread.latest_message?.sender_role || "member"}`}>{thread.latest_message?.sender_role || "thread"}</span>
                  {thread.urgent ? <span className="status-pill blocked">Urgent</span> : null}
                  {thread.unread_count ? <span className="status-pill in_progress">{thread.unread_count} unread</span> : <span className="status-pill completed">Read</span>}
                </div>
              </button>
            )) : <p className="empty-state">No message threads yet.</p>}
          </div>
        </section>

        <section className="message-thread-detail">
          {selectedThread ? (
            <React.Fragment>
              <div className="message-thread-shell">
                <div className="message-thread-header">
                  <div>
                    <strong>{selectedThread.subject}</strong>
                    <span>{selectedThread.messages?.length || 0} message{(selectedThread.messages?.length || 0) === 1 ? "" : "s"} in this thread</span>
                  </div>
                  <div className="task-mini-meta">
                    <button className="ghost compact-btn" type="button" onClick={() => setThreadExpanded((current) => !current)}>
                      {threadExpanded ? "Collapse thread" : "Expand thread"}
                    </button>
                    {selectedThread.urgent ? <span className="status-pill blocked">Urgent</span> : null}
                    <span>{selectedThread.unread_count ? `${selectedThread.unread_count} unread` : "All read"}</span>
                  </div>
                </div>

                <div className="message-thread-scroll">
                  {conversationTree(selectedThread.messages || []).map((item) => renderConversationNode(item))}
                </div>
                {!threadExpanded ? (
                  <div className="message-collapsed-note">Expand the thread to read the full conversation and reply inline beneath a message.</div>
                ) : !activeReplyMessage ? (
                  <div className="message-collapsed-note">Select `Reply` beneath any message to respond in place.</div>
                ) : null}
              </div>
            </React.Fragment>
          ) : (
            <div className="message-thread-shell empty">
              <div className="message-thread-header">
                <div>
                  <strong>Start a new conversation</strong>
                  <span>Pick a recipient, add a subject, and send the first message.</span>
                </div>
              </div>
              <form className="stacked-form message-new-thread" onSubmit={onSend}>
                <div className="message-recipient-picker">
                  <label>
                    Find recipient
                    <input value={recipientQuery} onChange={(event) => setRecipientQuery(event.target.value)} placeholder="Search by name, role, or email" />
                  </label>
                  {selectedRecipient ? (
                    <div className="selected-recipient">
                      <span className={`recipient-role recipient-role-${selectedRecipient.role}`}>{selectedRecipient.role}</span>
                      <strong>{selectedRecipient.name}</strong>
                      <span>{selectedRecipient.email || selectedRecipient.detail}</span>
                    </div>
                  ) : null}
                  <div className="recipient-list" role="listbox" aria-label="Message recipients">
                    {filteredRecipients.slice(0, 8).map((item) => (
                      <button
                        key={`${item.role}|${item.key}`}
                        type="button"
                        className={`recipient-card ${selectedRecipient?.role === item.role && selectedRecipient?.key === item.key ? "active" : ""}`}
                        onClick={() => onComposerChange("recipient", `${item.role}|${item.key}`)}
                      >
                        <span className={`recipient-avatar recipient-role-${item.role}`}>{item.name.slice(0, 1).toUpperCase()}</span>
                        <span className="recipient-copy">
                          <strong>{item.name}</strong>
                          <span>{item.email || item.detail}</span>
                        </span>
                        <span className={`recipient-role recipient-role-${item.role}`}>{item.role}</span>
                      </button>
                    ))}
                    {!filteredRecipients.length ? <p className="empty-state">No matching recipients found.</p> : null}
                  </div>
                </div>
                <label>
                  Subject
                  <input value={composer.subject} onChange={(event) => onComposerChange("subject", event.target.value)} />
                </label>
                <label>
                  Message
                  <textarea value={composer.body} onChange={(event) => onComposerChange("body", event.target.value)} placeholder="Write your message" />
                </label>
                <div className="message-reply-actions">
                  <label className="message-urgent-toggle">
                    <input type="checkbox" checked={Boolean(composer.urgent)} onChange={(event) => onComposerChange("urgent", event.target.checked)} />
                    <span>Mark as urgent</span>
                  </label>
                  <button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Sending..." : "Send message"}</button>
                </div>
              </form>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function CriterionCard({ item, onOpen }) {
  return (
    <button className="criterion-card" type="button" onClick={() => onOpen(item.code)}>
      <strong>{item.name}</strong>
      <span>{item.evidence_count} evidence item(s)</span>
    </button>
  );
}

function WorkspaceCard({ item, onDragStart, onOpenFolder, onDeleteFile }) {
  return (
    <article className={`board-item ${item.kind}`} draggable onDragStart={(event) => onDragStart(event, item)}>
      <button className="drag-handle" type="button" aria-label="Drag item">⋮⋮</button>
      <div className="board-item-body">
        {item.kind === "folder" ? (
          <button className="board-folder-link" type="button" onClick={() => onOpenFolder(item.entityId)}>{item.label}</button>
        ) : item.href ? (
          <a className="board-link" href={item.href} target="_blank" rel="noreferrer">{item.label}</a>
        ) : (
          <strong>{item.label}</strong>
        )}
        {item.documentType ? <span className="document-type-badge">{item.documentType}</span> : null}
        <span>{item.timestamp}</span>
        <p>{item.subtitle}</p>
      </div>
      {item.kind === "file" ? <button className="icon-action" type="button" onClick={() => onDeleteFile(item)}>Delete</button> : null}
    </article>
  );
}

function WorkspaceColumn({ container, active, onDropItem, onDragStart, onOpenFolder, onDeleteFile }) {
  function handleDrop(event) {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/json");
    if (!raw) return;
    try {
      onDropItem(JSON.parse(raw), container.id);
    } catch (_error) {
      return;
    }
  }
  return (
    <section className={`drop-container ${active ? "active" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={handleDrop}>
      <header>
        <span className="folder-dot" style={{ background: container.color }} />
        <strong>{container.label}</strong>
      </header>
      {container.items.length ? container.items.map((item) => (
        <WorkspaceCard key={item.id} item={item} onDragStart={onDragStart} onOpenFolder={onOpenFolder} onDeleteFile={onDeleteFile} />
      )) : <p className="empty-state">Drop files or folders here.</p>}
    </section>
  );
}

function buildBoard(workspace) {
  if (!workspace) return [];
  const containers = [{ id: null, label: "Root", color: "#51606f", items: [] }];
  workspace.folders.forEach((folder) => containers.push({ id: folder.id, label: folder.name, color: folder.color, items: [] }));
  const byId = new Map(containers.map((container) => [container.id, container]));
  workspace.folders.forEach((folder) => {
    const parent = byId.get(folder.parent_id || null) || byId.get(null);
    parent.items.push({
      id: `folder:${folder.id}`,
      kind: "folder",
      entityId: folder.id,
      label: folder.name,
      subtitle: `${folder.file_count} files • ${folder.child_folder_count} subfolders`,
      timestamp: folder.path || "Folder",
    });
  });
  workspace.files.forEach((file) => {
    const parent = byId.get(file.folder_id || null) || byId.get(null);
    parent.items.push({
      id: `file:${file.id}`,
      kind: "file",
      entityId: file.id,
      label: file.file_name,
      documentType: file.document_type || "Other",
      subtitle: cleanSummary(file.ai_summary || file.description),
      timestamp: formatUploadedAt(file.created_at),
      href: file.open_url || file.drive_web_url || null,
    });
  });
  return containers;
}

function buildAttorneyDashboard(detail) {
  const member = detail?.member || null;
  const criteria = detail?.criteria || [];
  const tasks = detail?.tasks || [];
  const evidence = detail?.evidence || [];
  return {
    member,
    criteria,
    metrics: {
      readiness_score: member?.readiness_score || 0,
      evidence_count: member?.evidence_count || evidence.length,
      open_tasks: tasks.filter((item) => item.status === "open").length,
      criteria_started: member?.criteria_started || criteria.filter((item) => item.evidence_count).length,
    },
  };
}

function groupEvidenceByCriterion(evidence = [], criteriaByCode = {}) {
  const groups = new Map();
  evidence.forEach((item) => {
    const code = item.criterion_code || "other";
    const label = criteriaByCode[code]?.name || code.replaceAll("_", " ") || "Other";
    if (!groups.has(code)) groups.set(code, { code, label, items: [] });
    groups.get(code).items.push(item);
  });
  return Array.from(groups.values()).sort((left, right) => left.label.localeCompare(right.label));
}

function EvidenceGroupPanel({ evidence = [], criteriaByCode = {}, emptyText = "No evidence files available yet." }) {
  const groups = groupEvidenceByCriterion(evidence, criteriaByCode);
  if (!groups.length) return <p className="empty-state">{emptyText}</p>;
  return (
    <div className="evidence-group-list">
      {groups.map((group) => (
        <section key={group.code} className="evidence-group">
          <div className="section-kicker">{group.label}</div>
          <div className="task-mini-list">
            {group.items.map((item) => (
              <article key={item.id} className="task-mini-item">
                <div>
                  <strong>{item.file_name}</strong>
                  <p>{cleanSummary(item.ai_summary || item.description)}</p>
                </div>
                <div className="task-mini-meta">
                  <span>{item.document_type || "Other"}</span>
                  <span>{item.folder_path || "Criterion root"}</span>
                  <span>{formatUploadedAt(item.created_at)}</span>
                  {item.open_url ? <a href={item.open_url} target="_blank" rel="noreferrer">Open evidence</a> : null}
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function assistantStorageKey(role, clientId = "") {
  return `${ASSISTANT_SESSION_PREFIX}${role || "unknown"}_${clientId || "global"}`;
}

function readAssistantThread(key) {
  if (!key) return [];
  try {
    const raw = window.sessionStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function assistantThreadPayload(thread) {
  return thread.map((item) => ({
    role: item.role,
    content: item.role === "assistant" ? (item.detailed_answer || item.summary || "") : (item.content || ""),
  }));
}

function AssistantPanel({
  open,
  onToggle,
  assistantName,
  portalLabel,
  thread,
  input,
  onInputChange,
  onSubmit,
  onUsePrompt,
  onClear,
  busy,
}) {
  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit(event);
    }
  }

  return (
    <section className={`assistant-pop ${open ? "open" : ""}`}>
      {open ? (
        <div className="assistant-shell">
          <header className="assistant-header">
            <div>
              <div className="assistant-kicker">{portalLabel}</div>
              <strong>{assistantName}</strong>
            </div>
            <div className="assistant-actions">
              <button type="button" className="ghost compact-btn" onClick={onClear}>Clear Session</button>
              <button type="button" className="ghost compact-btn" onClick={onToggle}>Hide</button>
            </div>
          </header>
          <div className="assistant-thread">
            {thread.length ? thread.map((item) => (
              <article key={item.id} className={`assistant-msg ${item.role}`}>
                {item.role === "user" ? (
                  <p>{item.content}</p>
                ) : (
                  <React.Fragment>
                    <strong>{item.summary}</strong>
                    {item.response_mode === "detailed" ? (
                      <p>{item.detailed_answer}</p>
                    ) : null}
                    <div className="assistant-msg-actions">
                      {item.needs_more_detail && item.detail_prompt ? (
                        <button type="button" className="ghost compact-btn" onClick={() => onUsePrompt(item.detail_prompt)}>
                          {item.detail_prompt}
                        </button>
                      ) : null}
                    </div>
                    {item.response_mode === "detailed" && item.references?.length ? (
                      <div className="assistant-reference-list">
                        {item.references.map((ref) => (
                          <div key={ref.id || `${item.id}_${ref.label}`} className="assistant-reference">
                            <strong>{ref.label || ref.title}</strong>
                            <span>{ref.location || "Root"}</span>
                            {ref.url ? <a href={ref.url} target="_blank" rel="noreferrer">Open in storage</a> : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </React.Fragment>
                )}
              </article>
            )) : (
              <article className="assistant-empty">
                <strong>Ask about Ascend portal work only.</strong>
                <p>Try member gaps, next actions, storage-backed evidence trails, assignment questions, dossier summaries, or portal workflow.</p>
              </article>
            )}
          </div>
          <form className="assistant-form" onSubmit={onSubmit}>
            <textarea
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about the current Ascend case, portal workflow, evidence, queue, or next move."
              rows={3}
            />
            <div className="assistant-actions">
              <button className="primary compact-btn" type="submit" disabled={busy || !input.trim()}>
                {busy ? "Thinking..." : "Send"}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <button type="button" className="assistant-launcher" onClick={onToggle}>
          <span>{assistantName}</span>
          <strong>Ask AI</strong>
        </button>
      )}
    </section>
  );
}

function SupportPanel({
  open,
  onToggle,
  agentName,
  portalLabel,
  form,
  busy,
  submission,
  onFieldChange,
  onSubmit,
  onReset,
  onOpenInbox,
  onAttachmentFileChange,
  onAttachmentDescriptionChange,
  onAddAttachment,
  onRemoveAttachment,
}) {
  return (
    <section className={`support-pop ${open ? "open" : ""}`}>
      {open ? (
        <div className="support-shell">
          <header className="support-header">
            <div className="support-header-copy">
              <span className="support-icon-wrap"><SupportIcon /></span>
              <div className="support-header-text">
                <strong>{agentName}</strong>
                <div className="support-kicker">{portalLabel}</div>
              </div>
            </div>
            <div className="support-header-tools">
              {submission ? (
                <button type="button" className="support-icon-btn" onClick={onOpenInbox} aria-label="Open mailbox receipt" title="Open mailbox receipt">
                  <SupportActionIcon name="mail" />
                </button>
              ) : null}
              <button type="button" className="support-icon-btn" onClick={onToggle} aria-label="Hide IT support" title="Hide IT support">
                <SupportActionIcon name="hide" />
              </button>
            </div>
          </header>
          <div className="support-body">
            {submission ? (
              <div className="support-success">
                <span className="support-success-pill">Ticket created</span>
                <strong>{submission.ticket?.ticket_number || "Ticket created"}</strong>
                <p>{submission.ticket?.user_summary || "Your issue is now queued for admin review."}</p>
                <div className="support-ticket-meta">
                  <span>{submission.ticket?.portal || portalLabel}</span>
                  <span>{supportPriorityLabel(submission.ticket?.priority || "normal")} priority</span>
                  <span>{submission.ticket?.is_blocking ? "Blocking" : "Not blocking"}</span>
                  <span>{submission.ticket?.behavior_assessment ? submission.ticket.behavior_assessment.replaceAll("_", " ") : "needs verification"}</span>
                </div>
                <div className="support-success-actions">
                  <button type="button" className="support-action-chip support-action-chip-primary" onClick={onOpenInbox}>
                    <SupportActionIcon name="mail" />
                    <span>Receipt</span>
                  </button>
                  <button type="button" className="support-action-chip support-action-chip-ghost" onClick={onReset}>
                    <SupportActionIcon name="reset" />
                    <span>New</span>
                  </button>
                </div>
              </div>
            ) : (
              <form className="support-form" onSubmit={onSubmit}>
                <p className="support-intro">Describe the issue, choose urgency, and add optional files. A receipt goes to your mailbox.</p>
                <div className="support-inline-grid">
                  <label>
                    Priority
                    <select value={form.priority} onChange={(event) => onFieldChange("priority", event.target.value)}>
                      <option value="low">Low</option>
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                      <option value="urgent">Urgent</option>
                    </select>
                  </label>
                  <label>
                    Blocking?
                    <select value={form.is_blocking} onChange={(event) => onFieldChange("is_blocking", event.target.value)}>
                      <option value="no">No</option>
                      <option value="yes">Yes</option>
                    </select>
                  </label>
                </div>
                <label>
                  Short description
                  <input value={form.short_description} onChange={(event) => onFieldChange("short_description", event.target.value)} placeholder="Evidence link opens the wrong file" />
                </label>
                <label>
                  What happened
                  <textarea value={form.details} onChange={(event) => onFieldChange("details", event.target.value)} placeholder="Describe the steps, expected behavior, and what happened instead." />
                </label>
                <div className="support-attachment-list">
                  <div className="support-attachment-head">
                    <strong>Optional files</strong>
                    <button type="button" className="support-icon-btn" onClick={onAddAttachment} aria-label="Add another file" title="Add another file">
                      <SupportActionIcon name="plus" />
                    </button>
                  </div>
                  {form.attachments.map((attachment, index) => (
                    <div key={attachment.id} className="support-attachment-row">
                      <div className="support-attachment-top">
                        <strong>Attachment {index + 1}</strong>
                        {form.attachments.length > 1 || attachment.file || attachment.description.trim() ? (
                          <button
                            type="button"
                            className="support-icon-btn"
                            onClick={() => onRemoveAttachment(attachment.id)}
                            aria-label={`Remove file ${index + 1}`}
                            title="Remove file"
                          >
                            <SupportActionIcon name="remove" />
                          </button>
                        ) : null}
                      </div>
                      <div className="support-attachment-content">
                        <label className="support-file-field">
                          File
                          <span className="support-file-picker">
                            <input className="support-file-input" type="file" onChange={(event) => onAttachmentFileChange(attachment.id, event.target.files?.[0] || null)} />
                            <span className="support-file-icon"><SupportActionIcon name="clip" /></span>
                            <span className={`support-file-name ${attachment.file?.name ? "" : "empty"}`}>
                              {attachment.file?.name || "Browse"}
                            </span>
                          </span>
                        </label>
                        <label className="support-attachment-note">
                          Description
                          <textarea
                            value={attachment.description}
                            onChange={(event) => onAttachmentDescriptionChange(attachment.id, event.target.value)}
                            placeholder="Description"
                            required={Boolean(attachment.file)}
                            aria-required={Boolean(attachment.file)}
                            rows={2}
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="support-actions support-form-actions">
                  <button type="button" className="support-icon-btn" onClick={onReset} aria-label="Reset support form" title="Reset support form">
                    <SupportActionIcon name="reset" />
                  </button>
                  <button className="support-submit-btn" type="submit" disabled={busy}>
                    <SupportActionIcon name="send" />
                    <span>{busy ? "Sending..." : "Send"}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      ) : (
        <button type="button" className="support-launcher" onClick={onToggle} aria-label="Open IT support">
          <span className="support-launcher-icon"><SupportIcon /></span>
          <strong>Support</strong>
        </button>
      )}
    </section>
  );
}

function PortalHydrationNotice({ title = "Loading latest portal data", detail = "The workspace is available while Ascend refreshes the live case data." }) {
  return (
    <section className="panel portal-hydration-panel" aria-live="polite">
      <div>
        <div className="section-kicker">Loading</div>
        <h3 className="section-title">{title}</h3>
        <p className="section-intro">{detail}</p>
      </div>
      <div className="portal-skeleton-lines" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </section>
  );
}

function emptyMemberDashboard(member, criteria = []) {
  return {
    client: { display_name: member?.display_name || "Member" },
    metrics: {
      readiness_score: 0,
      evidence_count: 0,
      open_tasks: 0,
      criteria_started: 0,
    },
    criteria,
  };
}

function App() {
  const initialStoredMember = readStoredMember();
  const initialRoute = readPortalRoute();
  const [authMode, setAuthMode] = useState(initialRoute.portal || normalizePortalRole(initialStoredMember?.role) || "member");
  const [authReady, setAuthReady] = useState(false);
  const [authMember, setAuthMember] = useState(initialStoredMember);
  const [builderDashboard, setBuilderDashboard] = useState(null);
  const [builderMembers, setBuilderMembers] = useState([]);
  const [memberSearchQuery, setMemberSearchQuery] = useState("");
  const [builderMemberDetail, setBuilderMemberDetail] = useState(null);
  const [memberDetailLoading, setMemberDetailLoading] = useState(false);
  const [builderOpportunities, setBuilderOpportunities] = useState([]);
  const [selectedBuilderMemberId, setSelectedBuilderMemberId] = useState("");
  const [builderTaskForm, setBuilderTaskForm] = useState({ opportunity_id: "", title: "", description: "", criterion_code: "", due_date: "" });
  const [builderOpportunityForm, setBuilderOpportunityForm] = useState({ criterion_code: "judging", title: "", description: "", target_evidence_type: "Invitation", suggested_due_days: "14" });
  const [builderBusy, setBuilderBusy] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "", password: "" });
  const [loginBusy, setLoginBusy] = useState(false);
  const [memberMenuOpen, setMemberMenuOpen] = useState(false);
  const [helpManualOpen, setHelpManualOpen] = useState(false);
  const [helpManualQuery, setHelpManualQuery] = useState("");
  const [passwordDialogOpen, setPasswordDialogOpen] = useState(false);
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [passwordBusy, setPasswordBusy] = useState(false);
  const [profileTab, setProfileTab] = useState("identity");
  const [dashboard, setDashboard] = useState(null);
  const [criteriaList, setCriteriaList] = useState([]);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [plannerItems, setPlannerItems] = useState([]);
  const [plannerRows, setPlannerRows] = useState([]);
  const [profile, setProfile] = useState(null);
  const [profileForm, setProfileForm] = useState(emptyProfileForm());
  const [profileBusy, setProfileBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState(null);
  const [view, setView] = useState({ type: "home", criterionCode: "" });
  const [portalSection, setPortalSection] = useState("home");
  const [workspace, setWorkspace] = useState(null);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [workspaceQuery, setWorkspaceQuery] = useState("");

  const [routeMode, setRouteMode] = useState("ai");
  const [memberContext, setMemberContext] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [manualCategory, setManualCategory] = useState("");
  const [manualDocumentType, setManualDocumentType] = useState("Other");
  const [draft, setDraft] = useState(null);
  const [aiFeedback, setAiFeedback] = useState("accept");
  const [overrideCategory, setOverrideCategory] = useState("");
  const [overrideDocumentType, setOverrideDocumentType] = useState("Other");
  const [consent, setConsent] = useState(false);
  const [draftApprovalError, setDraftApprovalError] = useState("");
  const [uploadBusy, setUploadBusy] = useState(false);
  const [duplicateState, setDuplicateState] = useState(null);

  const [newFolderName, setNewFolderName] = useState("");
  const [newFolderParent, setNewFolderParent] = useState("");
  const [newFolderColor, setNewFolderColor] = useState("Emerald");
  const [selectedFolderId, setSelectedFolderId] = useState("");
  const [folderForm, setFolderForm] = useState({ name: "", color: "Emerald" });
  const [plannerForm, setPlannerForm] = useState(emptyPlannerForm());
  const [editingPlannerId, setEditingPlannerId] = useState("");
  const [plannerBusy, setPlannerBusy] = useState(false);
  const [plannerSavingId, setPlannerSavingId] = useState("");
  const [plannerFolders, setPlannerFolders] = useState([]);
  const [leaderAssignments, setLeaderAssignments] = useState([]);
  const [leaderBuilders, setLeaderBuilders] = useState([]);
  const [leaderAttorneys, setLeaderAttorneys] = useState([]);
  const [leaderInvites, setLeaderInvites] = useState([]);
  const [leaderDomainSummary, setLeaderDomainSummary] = useState([]);
  const [leaderInsights, setLeaderInsights] = useState(null);
  const [leaderPerspective, setLeaderPerspective] = useState("leader");
  const [leaderInviteForm, setLeaderInviteForm] = useState(emptyLeaderInviteForm());
  const [messageCenter, setMessageCenter] = useState({ threads: [], recipient_options: [], unread_count: 0, actor: null });
  const [selectedThreadId, setSelectedThreadId] = useState("");
  const [messageComposer, setMessageComposer] = useState({ recipient_role: "", recipient_key: "", subject: "", body: "", urgent: false, reply_to_id: "" });
  const [messageBusy, setMessageBusy] = useState(false);
  const [adminDashboard, setAdminDashboard] = useState(null);
  const [adminIssueLog, setAdminIssueLog] = useState({ items: [], priority_counts: {}, status_counts: {} });
  const [issueLogForm, setIssueLogForm] = useState(emptyIssueLogForm());
  const [issueLogBusy, setIssueLogBusy] = useState(false);
  const [adminCosts, setAdminCosts] = useState(null);
  const [adminCostBusy, setAdminCostBusy] = useState(false);
  const [petitionDraft, setPetitionDraft] = useState(null);
  const [petitionBusy, setPetitionBusy] = useState(false);
  const [batchZipFile, setBatchZipFile] = useState(null);
  const [batchContext, setBatchContext] = useState("");
  const [batchSession, setBatchSession] = useState(null);
  const [batchSessions, setBatchSessions] = useState([]);
  const [batchBusy, setBatchBusy] = useState(false);
  const [batchCommitBusy, setBatchCommitBusy] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantThread, setAssistantThread] = useState([]);
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportBusy, setSupportBusy] = useState(false);
  const [supportForm, setSupportForm] = useState(emptySupportForm());
  const [supportSubmission, setSupportSubmission] = useState(null);
  const routeHistoryRef = useRef({ lastUrl: window.location.href, fromPopState: false });

  const criteriaByCode = useMemo(() => Object.fromEntries((criteriaList || dashboard?.criteria || []).map((item) => [item.code, item])), [criteriaList, dashboard]);
  const actionItems = useMemo(() => buildActionItems(dashboard?.criteria || [], evidenceItems), [dashboard, evidenceItems]);
  const folderOptions = useMemo(() => [{ value: "", label: "Root" }, ...((workspace?.folders || []).map((folder) => ({ value: folder.id, label: folder.path })))], [workspace]);
  const board = useMemo(() => buildBoard(workspace), [workspace]);
  const plannerFolderOptions = useMemo(
    () => [{ value: "", label: "No folder link" }, ...plannerFolders.map((folder) => ({ value: folder.id, label: folder.path }))],
    [plannerFolders],
  );
  const batchGroups = useMemo(() => groupBatchItems(batchSession), [batchSession]);
  const attorneyCaseStatusSummary = useMemo(() => {
    return builderMembers.reduce((acc, item) => {
      const key = caseStatusLabel(item.status);
      acc[key] = (acc[key] || 0) + 1;
      return acc;
    }, {});
  }, [builderMembers]);
  const selectedAttorneyMember = useMemo(
    () => builderMembers.find((item) => item.client_id === selectedBuilderMemberId) || null,
    [builderMembers, selectedBuilderMemberId],
  );
  const filteredBuilderMembers = useMemo(
    () => filterMembersBySearch(builderMembers, memberSearchQuery),
    [builderMembers, memberSearchQuery],
  );
  const memberSelectorOptions = useMemo(() => {
    if (!selectedAttorneyMember || filteredBuilderMembers.some((item) => item.client_id === selectedAttorneyMember.client_id)) {
      return filteredBuilderMembers;
    }
    return [selectedAttorneyMember, ...filteredBuilderMembers];
  }, [filteredBuilderMembers, selectedAttorneyMember]);
  const assistantMemberId = useMemo(() => (
    ["builder", "leader", "attorney"].includes(authMember?.role) ? (selectedBuilderMemberId || builderMemberDetail?.member?.client_id || "") : ""
  ), [authMember?.role, selectedBuilderMemberId, builderMemberDetail]);
  const assistantSessionStorageKey = useMemo(
    () => ["builder", "leader", "attorney"].includes(authMember?.role) ? assistantStorageKey(authMember.role, assistantMemberId) : "",
    [authMember?.role, assistantMemberId],
  );
  const assistantPortalLabel = useMemo(() => (
    authMember?.role === "leader"
      ? leaderPerspective === "attorney"
        ? "Leader Attorney View Assistant"
        : leaderPerspective === "builder"
        ? "Leader Builder View Assistant"
        : "Leader Workspace Assistant"
      : authMember?.role === "attorney"
      ? "Attorney Workspace Assistant"
      : "Profile Builder Assistant"
  ), [authMember?.role, leaderPerspective]);
  const currentCriterionName = useMemo(
    () => dashboard?.criteria?.find((item) => item.code === view.criterionCode)?.name || "",
    [dashboard, view.criterionCode],
  );
  const supportSelectedMemberName = useMemo(() => (
    ["builder", "leader", "attorney"].includes(authMember?.role) ? (builderMemberDetail?.member?.display_name || selectedAttorneyMember?.display_name || "") : ""
  ), [authMember?.role, builderMemberDetail, selectedAttorneyMember]);
  const supportSectionLabel = useMemo(() => {
    if (authMember?.role === "member") {
      if (view.type === "workspace") return currentCriterionName ? `${currentCriterionName} workspace` : "Evidence workspace";
      if (view.type === "profile") return "Profile";
      if (view.type === "planner") return "Event Planner";
      if (view.type === "intake") return "Evidence Intake";
      if (view.type === "messages") return "Messages";
      return "Member Home";
    }
    if (authMember?.role === "leader") {
      if (leaderPerspective === "attorney") {
        if (portalSection === "dossier") return "Member Dossier";
        if (portalSection === "petition") return "Petition Generator";
        if (portalSection === "batch") return "Batch Intake";
        if (portalSection === "evidence") return "Evidence Review";
        if (portalSection === "messages") return "Messages";
        return "Attorney Home";
      }
      if (leaderPerspective === "builder") {
        if (portalSection === "members") return "Assigned Members";
        if (portalSection === "opportunities") return "Opportunities";
        if (portalSection === "messages") return "Messages";
        return "Builder Home";
      }
      if (portalSection === "members") return "Member Review";
      if (portalSection === "risks") return "Risk & Bottlenecks";
      if (portalSection === "capacity") return "Team Capacity";
      if (portalSection === "oversight") return "Assignment Oversight";
      if (portalSection === "opportunities") return "Opportunities";
      if (portalSection === "batch") return "Batch Intake";
      if (portalSection === "messages") return "Messages";
      return "Executive Overview";
    }
    if (authMember?.role === "builder") {
      if (portalSection === "members") return "Assigned Members";
      if (portalSection === "opportunities") return "Opportunities";
      if (portalSection === "messages") return "Messages";
      return "Builder Home";
    }
    if (authMember?.role === "attorney") {
      if (portalSection === "dossier") return "Dossier";
      if (portalSection === "petition") return "Petition Generator";
      if (portalSection === "batch") return "Batch Intake";
      if (portalSection === "evidence") return "Evidence Review";
      if (portalSection === "messages") return "Messages";
      return "Attorney Home";
    }
    if (authMember?.role === "admin") {
      if (portalSection === "health") return "System Health";
      if (portalSection === "issues") return "Issue Portal";
      if (portalSection === "costs") return "Cost Explorer";
      if (portalSection === "debug") return "Debug Console";
      if (portalSection === "support") return "Support Tickets";
      if (portalSection === "messages") return "Messages";
      return "Admin Home";
    }
    return "Portal";
  }, [authMember?.role, currentCriterionName, leaderPerspective, portalSection, view.type]);
  const supportIssueLocation = useMemo(() => (
    [portalMeta(authMember?.role || "member").label, supportSectionLabel, supportSelectedMemberName].filter(Boolean).join(" / ")
  ), [authMember?.role, supportSectionLabel, supportSelectedMemberName]);
  const supportRelatedClientId = useMemo(() => (
    authMember?.role === "member"
      ? (authMember?.client_id || "")
      : ["builder", "leader", "attorney"].includes(authMember?.role)
      ? (selectedBuilderMemberId || builderMemberDetail?.member?.client_id || "")
      : ""
  ), [authMember?.role, authMember?.client_id, builderMemberDetail, selectedBuilderMemberId]);

  function actorParams(member = authMember) {
    if (!member) return {};
    return {
      actor_role: member.role,
      actor_email: member.role === "member" ? "" : (member.email || ""),
      actor_client_id: member.role === "member" ? (member.client_id || "") : "",
    };
  }

  function supportDefaults() {
    return emptySupportForm(supportIssueLocation);
  }

  function openSupportPanel() {
    setSupportSubmission(null);
    setSupportForm(supportDefaults());
    setSupportOpen(true);
  }

  function toggleSupportPanel() {
    if (supportOpen) {
      setSupportOpen(false);
      return;
    }
    openSupportPanel();
  }

  function setSupportField(field, value) {
    setSupportForm((current) => ({ ...current, [field]: value }));
  }

  function setSupportAttachmentFile(attachmentId, file) {
    setSupportForm((current) => ({
      ...current,
      attachments: current.attachments.map((item) => item.id === attachmentId ? { ...item, file } : item),
    }));
  }

  function setSupportAttachmentDescription(attachmentId, description) {
    setSupportForm((current) => ({
      ...current,
      attachments: current.attachments.map((item) => item.id === attachmentId ? { ...item, description } : item),
    }));
  }

  function addSupportAttachment() {
    setSupportForm((current) => ({
      ...current,
      attachments: [...current.attachments, emptySupportAttachment()],
    }));
  }

  function removeSupportAttachment(attachmentId) {
    setSupportForm((current) => {
      const nextAttachments = current.attachments.filter((item) => item.id !== attachmentId);
      return {
        ...current,
        attachments: nextAttachments.length ? nextAttachments : [emptySupportAttachment()],
      };
    });
  }

  function writePortalUrl(nextUrl, replace = false) {
    if (routeHistoryRef.current.lastUrl === nextUrl) return;
    if (replace) {
      window.history.replaceState({}, "", nextUrl);
    } else {
      window.history.pushState({}, "", nextUrl);
    }
    routeHistoryRef.current.lastUrl = nextUrl;
  }

  function syncMemberUrl(nextView) {
    const url = new URL(window.location.href);
    url.searchParams.set("portal", "member");
    if (nextView?.type === "workspace" && nextView.criterionCode) {
      url.searchParams.set("page", "workspace");
      url.searchParams.set("criterion", nextView.criterionCode);
    } else {
      url.searchParams.set("page", nextView?.type || "home");
      url.searchParams.delete("criterion");
      url.searchParams.delete("folder");
    }
    writePortalUrl(url.toString(), routeHistoryRef.current.fromPopState);
    routeHistoryRef.current.fromPopState = false;
  }

  function syncStaffUrl() {
    if (!authMember || authMember.role === "member") return;
    const url = new URL(window.location.href);
    ["portal", "page", "section", "member", "criterion", "folder"].forEach((key) => url.searchParams.delete(key));
    url.searchParams.set("portal", authMember.role);
    url.searchParams.set("section", portalSection || "home");
    if (["builder", "leader", "attorney", "admin"].includes(authMember.role) && selectedBuilderMemberId) {
      url.searchParams.set("member", selectedBuilderMemberId);
    }
    writePortalUrl(url.toString(), routeHistoryRef.current.fromPopState);
    routeHistoryRef.current.fromPopState = false;
  }

  function applyRouteFromBrowser() {
    const route = readPortalRoute();
    const authenticatedRole = normalizePortalRole(authMember?.role);
    routeHistoryRef.current.fromPopState = true;
    routeHistoryRef.current.lastUrl = window.location.href;
    if (authMember && route.portal && route.portal !== authenticatedRole) {
      clearAuth();
      clearAssistantSessions();
      setAuthMember(null);
      setAuthMode(route.portal);
      setLoading(false);
      setMessage({ type: "error", text: `Please sign in with ${portalMeta(route.portal).label} credentials to open that portal.` });
      return;
    }
    if (!authMember) {
      if (route.portal) setAuthMode(route.portal);
      return;
    }
    if (authenticatedRole === "member") {
      const memberRoute = requestedMemberView(criteriaList);
      setSelectedFolderId(memberRoute.folderId || "");
      setView(memberRoute.view);
      return;
    }
    const allowed = authenticatedRole === "builder"
      ? BUILDER_SECTIONS
      : authenticatedRole === "leader"
      ? LEADER_EXEC_SECTIONS
      : authenticatedRole === "attorney"
      ? ATTORNEY_SECTIONS
      : ADMIN_SECTIONS;
    setPortalSection(allowed.has(route.section) ? route.section : "home");
    setSelectedBuilderMemberId(route.memberId || "");
  }

  async function loadHome() {
    setLoading(true);
    setMessage(null);
    try {
      const [dashboardData, evidenceData, plannerData, profileData, criteriaData] = await Promise.all([
        getJson("/api/member/dashboard"),
        getJson("/api/evidence"),
        getJson("/api/member/planner"),
        getJson("/api/member/profile"),
        getJson("/api/criteria"),
      ]);
      setDashboard(dashboardData);
      setCriteriaList(criteriaData);
      setEvidenceItems(evidenceData);
      setPlannerItems(plannerData);
      setProfile(profileData);
      setProfileForm({
        ...emptyProfileForm(),
        ...profileData,
        profile_confirmed: Boolean(profileData.profile_confirmed),
      });
      if (!manualCategory && dashboardData.criteria.length) setManualCategory(dashboardData.criteria[0].code);
      if (!manualDocumentType) setManualDocumentType("Other");
      const route = requestedMemberView(dashboardData.criteria);
      setSelectedFolderId(route.folderId || "");
      setView(route.view);
      if (route.invalidPage) {
        const label = route.invalidKind === "criterion" ? "criterion" : "page";
        setMessage({ type: "error", text: `${label.charAt(0).toUpperCase()} "${route.invalidPage}" was not found, so we returned you to Member Home.` });
      }
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load member portal." });
    } finally {
      setLoading(false);
    }
  }

  async function submitAssistantQuestion(questionOverride = "") {
    const question = (questionOverride || assistantInput).trim();
    if (!question || !["builder", "leader", "attorney"].includes(authMember?.role)) return;
    const userEntry = { id: `user_${Date.now()}`, role: "user", content: question };
    const pendingThread = [...assistantThread, userEntry];
    setAssistantThread(pendingThread);
    setAssistantBusy(true);
    setAssistantOpen(true);
    setMessage(null);
    setAssistantInput("");
    try {
      const result = await sendJson("/api/assistant/reply", {
        actor_role: authMember.role,
        actor_email: authMember.email || "",
        client_id: assistantMemberId,
        question,
        thread: assistantThreadPayload(pendingThread),
      });
      if (result.ok) {
        setAssistantThread((current) => [
          ...current,
          {
            id: `assistant_${Date.now()}`,
            role: "assistant",
            summary: result.payload.summary,
            detailed_answer: result.payload.detailed_answer,
            detail_prompt: result.payload.detail_prompt,
            suggested_follow_up: result.payload.suggested_follow_up,
            needs_more_detail: Boolean(result.payload.needs_more_detail),
            response_mode: result.payload.response_mode || "summary",
            references: result.payload.references || [],
          },
        ]);
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not get an assistant answer." });
        setAssistantThread((current) => current.filter((item) => item.id !== userEntry.id));
      }
    } finally {
      setAssistantBusy(false);
    }
  }

  async function askAssistant(event) {
    event.preventDefault();
    await submitAssistantQuestion();
  }

  async function useAssistantPrompt(promptText) {
    setAssistantInput(promptText);
    await submitAssistantQuestion(promptText);
  }

  function clearAssistantThread() {
    setAssistantThread([]);
    if (assistantSessionStorageKey) window.sessionStorage.removeItem(assistantSessionStorageKey);
  }

  function resetSupportTicketForm() {
    setSupportSubmission(null);
    setSupportForm(supportDefaults());
  }

  function openSupportInbox() {
    if (supportSubmission?.mailbox_thread_id) {
      setSelectedThreadId(supportSubmission.mailbox_thread_id);
    }
    if (authMember?.role === "member") {
      setView({ type: "messages", criterionCode: "" });
    } else {
      setPortalSection("messages");
    }
    setSupportOpen(false);
  }

  async function handleSupportSubmit(event) {
    event.preventDefault();
    if (!authMember) return;
    setSupportBusy(true);
    setMessage(null);
    try {
      const attachmentRows = (supportForm.attachments || []).filter((item) => item.file);
      const formData = new FormData();
      formData.set("actor_role", authMember.role);
      formData.set("actor_email", authMember.role === "member" ? "" : (authMember.email || ""));
      formData.set("actor_client_id", authMember.role === "member" ? (authMember.client_id || "") : "");
      formData.set("related_client_id", supportRelatedClientId || "");
      formData.set("issue_location", supportForm.issue_location.trim() || supportIssueLocation);
      formData.set("short_description", supportForm.short_description.trim());
      formData.set("details", supportForm.details.trim());
      formData.set("priority", supportForm.priority || "normal");
      formData.set("is_blocking", supportForm.is_blocking === "yes" ? "true" : "false");
      formData.set("attachment_descriptions_json", JSON.stringify(attachmentRows.map((item) => item.description.trim())));
      attachmentRows.forEach((item) => {
        formData.append("attachments", item.file, item.file.name);
      });
      const result = await sendForm("/api/support/tickets", formData);
      if (result.ok) {
        setSupportSubmission(result.payload);
        setSelectedThreadId(result.payload.mailbox_thread_id || "");
        await loadMessageCenterData(authMember);
        if (authMember.role === "admin") {
          await loadAdminPortal(selectedBuilderMemberId);
        }
        setMessage({ type: "success", text: `Support ticket ${result.payload.ticket?.ticket_number || ""} created.`.trim() });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not submit the support ticket." });
      }
    } finally {
      setSupportBusy(false);
    }
  }

  async function loadBuilderDashboard(memberId = selectedBuilderMemberId) {
    setLoading(true);
    setMessage(null);
    try {
      const [dashboardData, membersData, opportunitiesData, criteriaData] = await Promise.all([
        getJson("/api/builder/dashboard"),
        getJson("/api/builder/members"),
        getJson("/api/builder/opportunities"),
        getJson("/api/criteria"),
      ]);
      const roster = membersData.length ? membersData : (dashboardData.members || []);
      setBuilderDashboard(dashboardData);
      setBuilderMembers(roster);
      setLeaderAssignments(roster.map((item) => ({ client_id: item.client_id, builder_name: "Ava Morales", builder_email: "builder@ascendhsi.com" })));
      setBuilderOpportunities(opportunitiesData);
      setCriteriaList(criteriaData);
      const activeMemberId = memberId || roster[0]?.client_id || "";
      setSelectedBuilderMemberId(activeMemberId);
      if (activeMemberId) {
        const detail = await getJson(`/api/builder/members/${activeMemberId}`);
        setBuilderMemberDetail(detail);
      } else {
        setBuilderMemberDetail(null);
      }
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load profile builder portal." });
    } finally {
      setLoading(false);
    }
  }

  async function loadReviewPortals(memberId = selectedBuilderMemberId, actorEmail = authMember?.email || "attorney@ascendhsi.com") {
    setLoading(true);
    setMessage(null);
    try {
      const [membersData, criteriaData] = await Promise.all([
        getJson("/api/attorney/members", { attorney_email: actorEmail }),
        getJson("/api/criteria"),
      ]);
      const roster = membersData || [];
      setBuilderDashboard({ metrics: { member_count: roster.length, active_tasks: roster.reduce((sum, item) => sum + (item.open_task_count || 0), 0) } });
      setBuilderMembers(roster);
      setCriteriaList(criteriaData);
      const activeMemberId = memberId || roster[0]?.client_id || "";
      setSelectedBuilderMemberId(activeMemberId);
      if (activeMemberId) {
        const detail = await getJson(`/api/attorney/members/${activeMemberId}`, { attorney_email: actorEmail });
        setBuilderMemberDetail(detail);
        setDashboard(buildAttorneyDashboard(detail));
        setProfile(detail.profile || null);
        const evidenceData = await getJson(`/api/attorney/members/${activeMemberId}/evidence`, {
          actor_role: "attorney",
          actor_email: actorEmail,
        });
        setEvidenceItems(evidenceData || []);
      } else {
        setDashboard({ member: null, criteria: criteriaData, metrics: { readiness_score: 0, evidence_count: 0, open_tasks: 0, criteria_started: 0 } });
        setBuilderMemberDetail(null);
        setProfile(null);
        setEvidenceItems([]);
      }
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load the selected portal." });
    } finally {
      setLoading(false);
    }
  }

  async function loadLeaderPortal(memberId = selectedBuilderMemberId) {
    setLoading(true);
    setMessage(null);
    try {
      const [leaderData, criteriaData, opportunitiesData] = await Promise.all([
        getJson("/api/leader/dashboard"),
        getJson("/api/criteria"),
        getJson("/api/builder/opportunities"),
      ]);
      setBuilderDashboard({ metrics: { ...leaderData.metrics, opportunity_count: opportunitiesData.length } });
      setBuilderMembers(leaderData.members || []);
      setLeaderBuilders(leaderData.builders || []);
      setLeaderAttorneys(leaderData.attorneys || []);
      setLeaderInvites(leaderData.invites || []);
      setLeaderDomainSummary(leaderData.domain_summary || []);
      setLeaderInsights(leaderData);
      setBuilderOpportunities(opportunitiesData || []);
      setCriteriaList(criteriaData);
      setLeaderAssignments(
        (leaderData.members || []).map((item) => ({
          client_id: item.client_id,
          builder_id: item.builder_id || leaderData.builders?.find((builder) => builder.display_name === item.builder_name)?.id || "",
          builder_name: item.builder_name || "",
          builder_email: item.builder_email || "",
          attorney_id: item.attorney_id || leaderData.attorneys?.find((attorney) => attorney.display_name === item.attorney_name)?.id || "",
          attorney_name: item.attorney_name || "",
          attorney_email: item.attorney_email || "",
        })),
      );
      const activeMemberId = memberId || leaderData.members?.[0]?.client_id || "";
      setSelectedBuilderMemberId(activeMemberId);
      if (activeMemberId) {
        const [detail, evidenceData] = await Promise.all([
          getJson(`/api/builder/members/${activeMemberId}`),
          getJson(`/api/attorney/members/${activeMemberId}/evidence`, { actor_role: "leader" }),
        ]);
        setBuilderMemberDetail(detail);
        setEvidenceItems(evidenceData);
        setProfile(detail.profile || null);
        setDashboard(buildAttorneyDashboard({ ...detail, evidence: evidenceData || detail.evidence || [] }));
      } else {
        setBuilderMemberDetail(null);
        setProfile(null);
        setEvidenceItems([]);
        setDashboard({ member: null, criteria: criteriaData, metrics: { readiness_score: 0, evidence_count: 0, open_tasks: 0, criteria_started: 0 } });
      }
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load the leader portal." });
    } finally {
      setLoading(false);
    }
  }

  async function reloadOperationalWorkspace(memberId = selectedBuilderMemberId) {
    if (authMember?.role === "leader") {
      await loadLeaderPortal(memberId);
      return;
    }
    if (authMember?.role === "builder") {
      await loadBuilderDashboard(memberId);
      return;
    }
    if (authMember?.role === "attorney") {
      await loadReviewPortals(memberId, authMember?.email || "");
    }
  }

  async function loadAdminPortal(memberId = selectedBuilderMemberId) {
    setLoading(true);
    setMessage(null);
    try {
      const [opsData, issueData, costData, builderData, membersData, criteriaData] = await Promise.all([
        getJson("/api/admin/operations"),
        getJson("/api/admin/issue-log"),
        getJson("/api/admin/costs"),
        getJson("/api/builder/dashboard"),
        getJson("/api/builder/members"),
        getJson("/api/criteria"),
      ]);
      const roster = membersData.length ? membersData : (builderData.members || []);
      setAdminDashboard(opsData);
      setAdminIssueLog(issueData);
      setAdminCosts(costData);
      setBuilderDashboard(builderData);
      setBuilderMembers(roster);
      setCriteriaList(criteriaData);
      setPortalSection(requestedPortalSection("admin", portalSection || "home"));
      const activeMemberId = memberId || roster[0]?.client_id || "";
      setSelectedBuilderMemberId(activeMemberId);
      if (activeMemberId) {
        const detail = await getJson(`/api/builder/members/${activeMemberId}`);
        setBuilderMemberDetail(detail);
      } else {
        setBuilderMemberDetail(null);
      }
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load the admin portal." });
    } finally {
      setLoading(false);
    }
  }

  async function refreshAdminCosts() {
    setAdminCostBusy(true);
    setMessage(null);
    try {
      const response = await sendJson("/api/admin/costs/refresh", {});
      if (!response.ok) throw response.payload;
      setAdminCosts(response.payload);
      setMessage({ type: "success", text: "Cost Explorer refreshed." });
    } catch (_error) {
      setMessage({ type: "error", text: "Could not refresh Cost Explorer data." });
    } finally {
      setAdminCostBusy(false);
    }
  }

  async function loadIssueLog() {
    try {
      const data = await getJson("/api/admin/issue-log");
      setAdminIssueLog(data);
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load the issue log." });
    }
  }

  async function submitIssueLog(event) {
    event.preventDefault();
    setIssueLogBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(issueLogForm).forEach(([key, value]) => formData.set(key, value || ""));
      formData.set("actor_email", authMember?.email || "");
      const result = await sendForm("/api/admin/issue-log", formData);
      if (result.ok) {
        setIssueLogForm(emptyIssueLogForm());
        await loadIssueLog();
        setMessage({ type: "success", text: `Bug ${result.payload.bug_id} logged.` });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not log the issue." });
      }
    } finally {
      setIssueLogBusy(false);
    }
  }

  async function updateIssueLog(item, updates) {
    const formData = new FormData();
    formData.set("actor_email", authMember?.email || "");
    if (updates.priority) formData.set("priority", updates.priority);
    if (updates.status) formData.set("status", updates.status);
    const result = await sendForm(`/api/admin/issue-log/${item.bug_id}`, formData, "PATCH");
    if (result.ok) {
      await loadIssueLog();
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not update the issue." });
    }
  }

  async function removeIssueLog(item) {
    if (!window.confirm(`Remove ${item.bug_id} from the issue registry?`)) return;
    const formData = new FormData();
    formData.set("actor_email", authMember?.email || "");
    const result = await sendForm(`/api/admin/issue-log/${item.bug_id}`, formData, "DELETE");
    if (result.ok) {
      await loadIssueLog();
      setMessage({ type: "success", text: `Removed ${item.bug_id} from the visible issue registry.` });
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not remove the issue." });
    }
  }

  async function bootstrapAuth() {
    const route = readPortalRoute();
    const token = authToken();
    if (!token) {
      if (route.portal) setAuthMode(route.portal);
      if (route.portal && route.portal !== "member") {
        setPortalSection(requestedPortalSection(route.portal, "home"));
        setSelectedBuilderMemberId(route.memberId || "");
      }
      setAuthReady(true);
      setLoading(false);
      return;
    }
    try {
      const stored = readStoredMember();
      const role = normalizePortalRole(stored?.role) || "member";
      if (route.portal && route.portal !== role) {
        clearAuth();
        clearAssistantSessions();
        setAuthMember(null);
        setAuthMode(route.portal);
        setMessage({ type: "error", text: `Please sign in with ${portalMeta(route.portal).label} credentials to open that portal.` });
        setLoading(false);
        return;
      }
      if (isPreviewRole(role)) {
        setAuthMember(stored);
        setAuthMode(role);
        if (role === "admin") {
          await loadAdminPortal(route.memberId);
        } else if (role === "leader") {
          setLeaderPerspective("leader");
          setPortalSection(requestedPortalSection("leader", "home"));
          await loadLeaderPortal(route.memberId);
        } else {
          await loadReviewPortals(route.memberId || selectedBuilderMemberId, stored?.email || "");
        }
        setAuthReady(true);
        return;
      }
      const identity = await getJson(roleConfig(role).mePath);
      setAuthMember(identity);
      setAuthMode(role);
      persistAuth(token, identity);
      if (role === "builder") {
        setPortalSection(requestedPortalSection("builder", "home"));
        await loadBuilderDashboard(route.memberId);
      } else if (role === "leader") {
        setLeaderPerspective("leader");
        setPortalSection(requestedPortalSection("leader", "home"));
        await loadLeaderPortal(route.memberId);
      } else if (role === "attorney") {
        setPortalSection(requestedPortalSection("attorney", "home"));
        await loadReviewPortals(route.memberId || selectedBuilderMemberId, identity.email || "");
      } else if (role === "admin") {
        await loadAdminPortal(route.memberId);
      } else {
        await loadHome();
      }
    } catch (_error) {
      try {
        const identity = await getJson("/api/builder/auth/me");
        setAuthMember(identity);
        setAuthMode("builder");
        persistAuth(token, identity);
        await loadBuilderDashboard();
      } catch (_secondary) {
        clearAuth();
        setAuthMember(null);
        setLoading(false);
      }
    } finally {
      setAuthReady(true);
    }
  }

  async function loadWorkspace(criterionCode, query = "") {
    if (!criterionCode) return;
    setWorkspaceBusy(true);
    try {
      const data = await getJson(`/api/criteria/${criterionCode}/workspace`, { q: query });
      setWorkspace(data);
      if (selectedFolderId && !data.folders.some((folder) => folder.id === selectedFolderId)) setSelectedFolderId("");
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load criterion workspace." });
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function loadPlannerFolders(criterionCode) {
    if (!criterionCode) {
      setPlannerFolders([]);
      return;
    }
    try {
      const data = await getJson(`/api/criteria/${criterionCode}/workspace`);
      setPlannerFolders(data.folders || []);
    } catch (_error) {
      setPlannerFolders([]);
    }
  }

  async function loadMessageCenterData(member = authMember) {
    if (!member) return;
    try {
      const data = await getJson("/api/messages", actorParams(member));
      setMessageCenter(data);
      setSelectedThreadId((current) => current || data.threads?.[0]?.thread_id || "");
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load messages." });
    }
  }


  async function loadAttorneyPetition(clientId = selectedBuilderMemberId) {
    if (!clientId) return;
    setPetitionBusy(true);
    try {
      const data = await getJson("/api/attorney/petition-generator", { client_id: clientId });
      setPetitionDraft(data);
    } catch (_error) {
      setMessage({ type: "error", text: "Could not generate attorney petition draft." });
    } finally {
      setPetitionBusy(false);
    }
  }

  async function loadAttorneyEvidence(clientId = selectedBuilderMemberId) {
    if (!clientId || !["attorney", "leader"].includes(authMember?.role)) return;
    try {
      const data = await getJson(`/api/attorney/members/${clientId}/evidence`, {
        actor_role: authMember.role === "leader" ? "leader" : "attorney",
        actor_email: authMember.role === "leader" ? "" : (authMember.email || ""),
      });
      setEvidenceItems(data || []);
    } catch (_error) {
      setEvidenceItems([]);
    }
  }

  async function loadBatchSessions(clientId = selectedBuilderMemberId, sessionId = "") {
    if (!clientId || !["attorney", "leader"].includes(authMember?.role)) return;
    const params = {
      client_id: clientId,
      actor_role: authMember.role,
      actor_email: authMember.email || "",
    };
    try {
      const sessions = await getJson("/api/batch-intake/sessions", params);
      setBatchSessions(sessions);
      if (sessionId) {
        const detail = await getJson(`/api/attorney/batch-intake/${sessionId}`, params);
        setBatchSession(detail);
      }
    } catch (_error) {
      setBatchSessions([]);
    }
  }

  function updateBatchSessionItem(itemId, updates) {
    setBatchSession((current) => {
      if (!current) return current;
      return {
        ...current,
        items: current.items.map((item) => item.id === itemId ? { ...item, ...updates } : item),
      };
    });
  }

  async function handleBatchAnalyze(event) {
    event.preventDefault();
    if (!selectedBuilderMemberId || !batchZipFile) {
      setMessage({ type: "error", text: "Choose a member and a ZIP file first." });
      return;
    }
    setBatchBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.set("client_id", selectedBuilderMemberId);
      formData.set("member_context", batchContext.trim());
      formData.set("actor_role", authMember.role);
      formData.set("actor_email", authMember.email || "");
      formData.set("file", batchZipFile);
      const result = await sendForm("/api/attorney/batch-intake", formData);
      if (result.ok) {
        setBatchSession(result.payload);
        await loadBatchSessions(selectedBuilderMemberId, result.payload.id);
        setMessage({ type: "success", text: `Batch review queue created for ${result.payload.counts?.items || 0} file(s).` });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not create batch review queue." });
      }
    } finally {
      setBatchBusy(false);
    }
  }

  async function saveBatchItem(item) {
    if (!batchSession) return;
    const formData = new FormData();
    formData.set("criterion_code", item.criterion_code || "other");
    formData.set("document_type", item.document_type || "Other");
    formData.set("title", item.title || item.original_file_name || "Uploaded evidence");
    formData.set("ai_description", item.ai_description || "");
    formData.set("folder_decision", item.folder_decision || "root");
    formData.set("duplicate_action", item.duplicate_action || "");
    formData.set("review_status", item.review_status || "ready");
    formData.set("actor_role", authMember.role);
    formData.set("actor_email", authMember.email || "");
    if (item.folder_decision === "existing") {
      formData.set("assigned_folder_id", item.assigned_folder_id || "");
    }
    if (item.folder_decision === "create") {
      formData.set("assigned_folder_name", item.assigned_folder_name || item.suggested_folder_name || "");
    }
    const result = await sendForm(`/api/attorney/batch-intake/${batchSession.id}/items/${item.id}`, formData, "PATCH");
    if (result.ok) {
      setBatchSession(result.payload.session);
      setMessage({ type: "success", text: `${item.original_file_name} updated in the review queue.` });
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not update this batch item." });
    }
  }

  async function handleBatchCommit() {
    if (!batchSession) return;
    setBatchCommitBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.set("actor_role", authMember.role);
      formData.set("actor_email", authMember.email || "");
      const result = await sendForm(`/api/attorney/batch-intake/${batchSession.id}/commit`, formData);
      if (result.ok) {
        setBatchSession(result.payload.session);
        await loadBatchSessions(selectedBuilderMemberId, batchSession.id);
        setMessage({ type: "success", text: `Committed ${result.payload.committed_count} file(s) from the batch queue.` });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not commit batch intake." });
      }
    } finally {
      setBatchCommitBusy(false);
    }
  }

  async function openBatchSession(sessionId) {
    try {
      const data = await getJson(`/api/attorney/batch-intake/${sessionId}`, {
        actor_role: authMember.role,
        actor_email: authMember.email || "",
      });
      setBatchSession(data);
    } catch (_error) {
      setMessage({ type: "error", text: "Could not load batch review session." });
    }
  }

  async function bulkUpdateBatchItems(itemIds, reviewStatus, duplicateAction = "") {
    if (!batchSession || !itemIds.length) return;
    const formData = new FormData();
    formData.set("item_ids", itemIds.join(","));
    formData.set("review_status", reviewStatus);
    formData.set("duplicate_action", duplicateAction);
    formData.set("actor_role", authMember.role);
    formData.set("actor_email", authMember.email || "");
    const result = await sendForm(`/api/attorney/batch-intake/${batchSession.id}/bulk-update`, formData);
    if (result.ok) {
      setBatchSession(result.payload.session);
      await loadBatchSessions(selectedBuilderMemberId, batchSession.id);
      setMessage({ type: "success", text: `Updated ${itemIds.length} file(s) in the review queue.` });
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not apply the bulk update." });
    }
  }

  useEffect(() => { bootstrapAuth(); }, []);
  useEffect(() => {
    const handlePopState = () => applyRouteFromBrowser();
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [authMember, criteriaList]);
  useEffect(() => {
    if (!authMember) return;
    loadMessageCenterData(authMember);
  }, [authMember]);
  useEffect(() => {
    if (["builder", "leader", "attorney", "admin"].includes(authMember?.role)) return;
    if (!authMember) return;
    if (view.type === "workspace" && view.criterionCode) {
      syncMemberUrl(view);
      loadWorkspace(view.criterionCode, workspaceQuery);
    } else {
      syncMemberUrl(view);
    }
  }, [view, workspaceQuery]);
  useEffect(() => {
    if (!["builder", "leader", "attorney", "admin"].includes(authMember?.role)) return;
    syncStaffUrl();
  }, [authMember?.role, portalSection, selectedBuilderMemberId]);
  useEffect(() => {
    if (!workspace || !selectedFolderId) return;
    const folder = workspace.folders.find((item) => item.id === selectedFolderId);
    if (folder) setFolderForm({ name: folder.name, color: folderColorName(folder.color) });
  }, [workspace, selectedFolderId]);
  useEffect(() => {
    loadPlannerFolders(plannerForm.criterion_code);
  }, [plannerForm.criterion_code]);
  useEffect(() => {
    setPlannerRows(plannerItems.map((item) => ({ ...emptyPlannerRow(), ...item, isNew: false })));
  }, [plannerItems]);
  useEffect(() => {
    if (!["builder", "leader", "attorney", "admin"].includes(authMember?.role) || !selectedBuilderMemberId) return;
    if (loading || builderMemberDetail?.member?.client_id === selectedBuilderMemberId) return;
    let active = true;
    const path = authMember?.role === "attorney" ? `/api/attorney/members/${selectedBuilderMemberId}` : `/api/builder/members/${selectedBuilderMemberId}`;
    const params = authMember?.role === "attorney" ? { attorney_email: authMember?.email || "" } : undefined;
    setMemberDetailLoading(true);
    getJson(path, params).then((detail) => {
      if (!active) return;
      setBuilderMemberDetail(detail);
      if (authMember?.role === "attorney") setProfile(detail.profile || null);
      if (["attorney", "leader"].includes(authMember?.role)) loadAttorneyEvidence(selectedBuilderMemberId);
    }).catch(() => {}).finally(() => {
      if (active) setMemberDetailLoading(false);
    });
    return () => { active = false; };
  }, [selectedBuilderMemberId, authMember?.role, authMember?.email, loading, builderMemberDetail?.member?.client_id]);
  useEffect(() => {
    if (authMember?.role !== "attorney" || portalSection !== "petition" || !selectedBuilderMemberId) return;
    loadAttorneyPetition(selectedBuilderMemberId);
  }, [authMember?.role, portalSection, selectedBuilderMemberId]);
  useEffect(() => {
    if (!["attorney", "leader"].includes(authMember?.role)) return;
    setBatchSession(null);
    setBatchSessions([]);
    setBatchZipFile(null);
    setBatchContext("");
  }, [selectedBuilderMemberId, authMember?.role]);
  useEffect(() => {
    if (!["attorney", "leader"].includes(authMember?.role) || portalSection !== "batch" || !selectedBuilderMemberId) return;
    loadBatchSessions(selectedBuilderMemberId);
  }, [authMember?.role, portalSection, selectedBuilderMemberId]);
  useEffect(() => {
    if (!assistantSessionStorageKey) {
      setAssistantThread([]);
      return;
    }
    setAssistantThread(readAssistantThread(assistantSessionStorageKey));
  }, [assistantSessionStorageKey]);
  useEffect(() => {
    if (!assistantSessionStorageKey) return;
    window.sessionStorage.setItem(assistantSessionStorageKey, JSON.stringify(assistantThread));
  }, [assistantSessionStorageKey, assistantThread]);

  async function handleLogin(event) {
    event.preventDefault();
    setLoginBusy(true);
    setMessage(null);
    try {
      if (isPreviewRole(authMode)) {
        const options = PREVIEW_ACCOUNTS[authMode] || [];
        const match = options.find((item) => item.username === loginForm.username.trim().toLowerCase());
        if (!match) {
          const examples = options.map((item) => item.username).join(" or ");
          setMessage({ type: "error", text: `Use an authorized ${portalMeta(authMode).label} account${examples ? ` such as ${examples}` : ""}.` });
          return;
        }
        const identity = previewIdentity(authMode, match.username);
        persistAuth(`preview:${authMode}`, identity);
        setAuthMember(identity);
        setLoginForm({ username: "", password: "" });
        setAuthReady(true);
        if (authMode === "admin") {
          await loadAdminPortal();
        } else if (authMode === "leader") {
          setLeaderPerspective("leader");
          await loadLeaderPortal();
        } else {
          await loadReviewPortals();
        }
        return;
      }
      const formData = new FormData();
      formData.set("username", loginForm.username);
      formData.set("password", loginForm.password);
      if (STAFF_ROLE_VALUES.has(authMode)) {
        formData.set("portal_role", authMode);
      }
      const result = await sendForm(roleConfig(authMode).loginPath, formData);
      if (result.ok) {
        const payloadUser = result.payload.member || result.payload.builder || result.payload.user;
        const expectedRole = normalizePortalRole(authMode) || "member";
        const actualRole = normalizePortalRole(payloadUser?.role);
        if (!actualRole || actualRole !== expectedRole) {
          clearAuth();
          setAuthMember(null);
          setMessage({ type: "error", text: `These credentials belong to ${actualRole ? portalMeta(actualRole).label : "another portal"}, not ${portalMeta(expectedRole).label}.` });
          return;
        }
        persistAuth(result.payload.token, payloadUser);
        setAuthMember(payloadUser);
        setLoginForm({ username: "", password: "" });
        setAuthReady(true);
        const route = readPortalRoute();
        if (expectedRole !== "member") {
          setPortalSection(requestedPortalSection(expectedRole, portalSection || "home"));
          if (route.memberId) setSelectedBuilderMemberId(route.memberId);
        }
        if (authMode === "builder") {
          await loadBuilderDashboard(route.memberId || selectedBuilderMemberId);
        } else if (authMode === "leader") {
          setLeaderPerspective("leader");
          await loadLeaderPortal(route.memberId || selectedBuilderMemberId);
        } else if (authMode === "attorney") {
          await loadReviewPortals(route.memberId || selectedBuilderMemberId, payloadUser.email || "");
        } else if (authMode === "admin") {
          await loadAdminPortal(route.memberId || selectedBuilderMemberId);
        } else {
          await loadHome();
        }
      } else {
        setMessage({ type: "error", text: result.payload.error || "Login failed." });
      }
    } finally {
      setLoginBusy(false);
    }
  }

  async function handleDevLogin(account) {
    const username = account.username || "";
    const password = account.password || DEFAULT_QUICK_LOGIN_PASSWORD;
    setLoginForm({ username, password });
    setLoginBusy(true);
    setMessage(null);
    try {
      if (isPreviewRole(authMode)) {
        const identity = previewIdentity(authMode, username);
        persistAuth(`preview:${authMode}`, identity);
        setAuthMember(identity);
        setLoginForm({ username: "", password: "" });
        setAuthReady(true);
        if (authMode === "admin") {
          await loadAdminPortal();
        } else if (authMode === "leader") {
          setLeaderPerspective("leader");
          await loadLeaderPortal();
        } else {
          await loadReviewPortals();
        }
        return;
      }
      const formData = new FormData();
      formData.set("username", username);
      formData.set("password", password);
      if (STAFF_ROLE_VALUES.has(authMode)) {
        formData.set("portal_role", authMode);
      }
      const result = await sendForm(roleConfig(authMode).loginPath, formData);
      if (result.ok) {
        const payloadUser = result.payload.member || result.payload.builder || result.payload.user;
        const expectedRole = normalizePortalRole(authMode) || "member";
        const actualRole = normalizePortalRole(payloadUser?.role);
        if (!actualRole || actualRole !== expectedRole) {
          clearAuth();
          setAuthMember(null);
          setMessage({ type: "error", text: `These saved credentials belong to ${actualRole ? portalMeta(actualRole).label : "another portal"}, not ${portalMeta(expectedRole).label}.` });
          return;
        }
        persistAuth(result.payload.token, payloadUser);
        setAuthMember(payloadUser);
        setLoginForm({ username: "", password: "" });
        setAuthReady(true);
        const route = readPortalRoute();
        if (expectedRole !== "member") {
          setPortalSection(requestedPortalSection(expectedRole, portalSection || "home"));
          if (route.memberId) setSelectedBuilderMemberId(route.memberId);
        }
        if (authMode === "builder") {
          await loadBuilderDashboard(route.memberId || selectedBuilderMemberId);
        } else if (authMode === "leader") {
          setLeaderPerspective("leader");
          await loadLeaderPortal(route.memberId || selectedBuilderMemberId);
        } else if (authMode === "attorney") {
          await loadReviewPortals(route.memberId || selectedBuilderMemberId, payloadUser.email || "");
        } else if (authMode === "admin") {
          await loadAdminPortal(route.memberId || selectedBuilderMemberId);
        } else {
          await loadHome();
        }
      } else {
        setMessage({ type: "error", text: result.payload.error || "Saved credential login failed." });
      }
    } finally {
      setLoginBusy(false);
    }
  }

  async function handleLogout() {
    if (isPreviewRole(authMember?.role)) {
      clearAuth();
      clearAssistantSessions();
      setAuthMember(null);
      setDashboard(null);
      setEvidenceItems([]);
      setPlannerItems([]);
      setProfile(null);
      setWorkspace(null);
      setBuilderDashboard(null);
      setBuilderMembers([]);
      setBuilderMemberDetail(null);
      setBuilderOpportunities([]);
      setLeaderAssignments([]);
      setLeaderBuilders([]);
      setLeaderAttorneys([]);
      setLeaderInvites([]);
      setLeaderDomainSummary([]);
      setLeaderInsights(null);
      setLeaderPerspective("leader");
      setMessageCenter({ threads: [], recipient_options: [], unread_count: 0, actor: null });
      setSelectedThreadId("");
      setMessageComposer({ recipient_role: "", recipient_key: "", subject: "", body: "", urgent: false, reply_to_id: "" });
      setAdminDashboard(null);
      setAdminIssueLog({ items: [], priority_counts: {}, status_counts: {} });
      setIssueLogForm(emptyIssueLogForm());
      setAdminCosts(null);
      setView({ type: "home", criterionCode: "" });
      setPortalSection("home");
      setMemberMenuOpen(false);
      setPasswordDialogOpen(false);
      setMessage(null);
      setAuthMode("member");
      setAssistantOpen(false);
      setAssistantThread([]);
      setSupportOpen(false);
      setSupportBusy(false);
      setSupportForm(emptySupportForm());
      setSupportSubmission(null);
      return;
    }
    try {
      await fetch(`${API_URL}${roleConfig(authMember?.role).logoutPath}`, { method: "POST", headers: { ...authHeaders() } });
    } catch (_error) {
      // noop for local logout
    }
    clearAuth();
    clearAssistantSessions();
    setAuthMember(null);
    setDashboard(null);
    setEvidenceItems([]);
    setPlannerItems([]);
    setProfile(null);
    setWorkspace(null);
    setBuilderDashboard(null);
    setBuilderMembers([]);
    setBuilderMemberDetail(null);
    setBuilderOpportunities([]);
    setLeaderAssignments([]);
    setLeaderBuilders([]);
    setLeaderAttorneys([]);
    setLeaderInvites([]);
    setLeaderDomainSummary([]);
    setLeaderInsights(null);
    setLeaderPerspective("leader");
    setMessageCenter({ threads: [], recipient_options: [], unread_count: 0, actor: null });
    setSelectedThreadId("");
    setMessageComposer({ recipient_role: "", recipient_key: "", subject: "", body: "", urgent: false, reply_to_id: "" });
    setAdminDashboard(null);
    setAdminIssueLog({ items: [], priority_counts: {}, status_counts: {} });
    setIssueLogForm(emptyIssueLogForm());
    setAdminCosts(null);
    setView({ type: "home", criterionCode: "" });
    setPortalSection("home");
    setMemberMenuOpen(false);
    setPasswordDialogOpen(false);
    setMessage(null);
    setAuthMode("member");
    setAssistantOpen(false);
    setAssistantThread([]);
    setSupportOpen(false);
    setSupportBusy(false);
    setSupportForm(emptySupportForm());
    setSupportSubmission(null);
  }

  function openHelpManual() {
    setHelpManualOpen(true);
    setMemberMenuOpen(false);
  }

  async function handlePasswordChange(event) {
    event.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setMessage({ type: "error", text: "New password and confirmation do not match." });
      return;
    }
    if (isPreviewRole(authMember?.role)) {
      setMessage({ type: "success", text: "Password updated for preview mode." });
      setPasswordDialogOpen(false);
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
      return;
    }
    setPasswordBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.set("current_password", passwordForm.current_password);
      formData.set("new_password", passwordForm.new_password);
      const result = await sendForm(roleConfig(authMember?.role).passwordPath, formData);
      if (result.ok) {
        setMessage({ type: "success", text: "Password updated." });
        setPasswordDialogOpen(false);
        setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not change password." });
      }
    } finally {
      setPasswordBusy(false);
    }
  }

  function resetIntake() {
    setMemberContext("");
    setSelectedFile(null);
    setDraft(null);
    setAiFeedback("accept");
    setOverrideCategory("");
    setOverrideDocumentType("Other");
    setManualDocumentType("Other");
    setConsent(false);
    setDraftApprovalError("");
    setDuplicateState(null);
    const picker = document.getElementById("member-file");
    if (picker) picker.value = "";
  }

  function buildUploadForm({ criterionCode, documentType, title, description, aiSummary, qualityScore, duplicateAction = "" }) {
    const formData = new FormData();
    formData.set("criterion_code", criterionCode);
    formData.set("document_type", documentType);
    formData.set("title", title);
    formData.set("description", description);
    formData.set("ai_summary", aiSummary);
    formData.set("quality_score", String(qualityScore));
    formData.set("duplicate_action", duplicateAction);
    formData.set("file", selectedFile);
    return formData;
  }

  async function refreshAfterSave() {
    await loadHome();
    if (view.type === "workspace" && view.criterionCode) await loadWorkspace(view.criterionCode, workspaceQuery);
  }

  function resetPlannerForm() {
    setPlannerForm(emptyPlannerForm());
    setEditingPlannerId("");
    setPlannerFolders([]);
  }

  function setPlannerField(field, value) {
    setPlannerForm((current) => {
      const next = { ...current, [field]: value };
      if (field === "criterion_code") next.folder_id = "";
      return next;
    });
  }

  function addPlannerRow() {
    setPlannerRows((current) => [...current, emptyPlannerRow()]);
  }

  function setPlannerRowField(rowId, field, value) {
    setPlannerRows((current) => current.map((row) => {
      if (row.id !== rowId) return row;
      const next = { ...row, [field]: value };
      if (field === "criterion_code") next.folder_id = "";
      return next;
    }));
  }

  function setLeaderInviteField(field, value) {
    setLeaderInviteForm((current) => ({ ...current, [field]: value }));
  }

  async function setLeaderPerspectiveMode(nextPerspective) {
    setLeaderPerspective(nextPerspective);
    setPortalSection("home");
    setMessage(null);
    if (authMember?.role === "leader") {
      await loadLeaderPortal(selectedBuilderMemberId);
    }
  }

  async function setLeaderBuilderAssignment(clientId, builderId) {
    if (!builderId) return;
    setMessage(null);
    const formData = new FormData();
    formData.set("builder_id", builderId);
    const result = await sendForm(`/api/leader/members/${clientId}/builder-assignment`, formData, "PATCH");
    if (result.ok) {
      const selected = leaderBuilders.find((item) => item.id === builderId);
      setLeaderAssignments((current) => current.map((item) => item.client_id === clientId ? {
        ...item,
        builder_id: builderId,
        builder_name: selected?.display_name || "",
        builder_email: selected?.email || "",
      } : item));
      setMessage({ type: "success", text: `Profile builder assigned to ${selected?.display_name || "member"}.` });
      await loadLeaderPortal(clientId);
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not assign profile builder." });
    }
  }

  async function setLeaderAttorneyAssignment(clientId, attorneyId) {
    if (!attorneyId) return;
    setMessage(null);
    const formData = new FormData();
    formData.set("attorney_id", attorneyId);
    const result = await sendForm(`/api/leader/members/${clientId}/attorney-assignment`, formData, "PATCH");
    if (result.ok) {
      const selected = leaderAttorneys.find((item) => item.id === attorneyId);
      setLeaderAssignments((current) => current.map((item) => item.client_id === clientId ? {
        ...item,
        attorney_id: attorneyId,
        attorney_name: selected?.display_name || "",
        attorney_email: selected?.email || "",
      } : item));
      setMessage({ type: "success", text: `Attorney assigned to ${selected?.display_name || "member"}.` });
      await loadLeaderPortal(clientId);
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not assign attorney." });
    }
  }

  async function submitLeaderInvite(event) {
    event.preventDefault();
    setMessage(null);
    setBuilderBusy(true);
    try {
      const formData = new FormData();
      Object.entries(leaderInviteForm).forEach(([key, value]) => formData.set(key, value));
      const result = await sendForm("/api/leader/invites", formData);
      if (result.ok) {
        const routed = [
          result.payload.builder_name ? `Builder: ${result.payload.builder_name}` : "",
          result.payload.attorney_name ? `Attorney: ${result.payload.attorney_name}` : "",
        ].filter(Boolean).join(" • ");
        setMessage({
          type: "success",
          text: `Invitation prepared for ${result.payload.display_name}. Registration link is ready for email delivery${routed ? `; ${routed}` : "; assignments can be completed later"}.`,
        });
        setLeaderInviteForm(emptyLeaderInviteForm());
        await loadLeaderPortal(result.payload.client_id);
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not create member invite." });
      }
    } finally {
      setBuilderBusy(false);
    }
  }

  function selectedThread() {
    return messageCenter.threads?.find((item) => item.thread_id === selectedThreadId) || messageCenter.threads?.[0] || null;
  }

  function setMessageComposerField(field, value) {
    if (field === "recipient") {
      const [recipient_role, recipient_key] = String(value || "").split("|");
      setMessageComposer((current) => ({ ...current, recipient_role: recipient_role || "", recipient_key: recipient_key || "" }));
      return;
    }
    setMessageComposer((current) => ({ ...current, [field]: value }));
  }

  async function openThread(threadId) {
    setSelectedThreadId(threadId);
    setMessageComposer((current) => ({ ...current, reply_to_id: "" }));
    if (!threadId) {
      setMessageComposer((current) => ({ ...current, body: "", urgent: false, subject: "", reply_to_id: "" }));
      return;
    }
    const thread = messageCenter.threads?.find((item) => item.thread_id === threadId);
    if (!thread || !authMember) return;
    const unreadItems = thread.messages.filter((item) => item.recipient_role === authMember.role && !item.is_read && item.recipient_key === (authMember.role === "member" ? authMember.client_id : authMember.email));
    for (const item of unreadItems) {
      const formData = new FormData();
      formData.set("actor_role", authMember.role);
      formData.set("actor_email", authMember.role === "member" ? "" : authMember.email || "");
      formData.set("actor_client_id", authMember.role === "member" ? authMember.client_id || "" : "");
      formData.set("is_read", "true");
      await sendForm(`/api/messages/${item.id}/read`, formData, "PATCH");
    }
    if (unreadItems.length) await loadMessageCenterData();
  }

  async function handleSendMessage(event) {
    event.preventDefault();
    if (!authMember) return;
    const activeThread = selectedThread();
    setMessageBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.set("actor_role", authMember.role);
      formData.set("actor_email", authMember.role === "member" ? "" : authMember.email || "");
      formData.set("actor_client_id", authMember.role === "member" ? authMember.client_id || "" : "");
      formData.set("subject", activeThread ? activeThread.subject : messageComposer.subject);
      formData.set("body", messageComposer.body);
      formData.set("urgent", String(Boolean(messageComposer.urgent)));
      if (activeThread) {
        formData.set("thread_id", activeThread.thread_id);
        formData.set("parent_message_id", messageComposer.reply_to_id || activeThread.latest_message?.id || "");
      } else {
        formData.set("recipient_role", messageComposer.recipient_role);
        formData.set("recipient_key", messageComposer.recipient_key);
      }
      const result = await sendForm("/api/messages", formData);
      if (result.ok) {
        setMessage({ type: "success", text: activeThread ? "Reply sent." : "Message thread started." });
        setMessageComposer((current) => ({ ...current, body: "", urgent: false, subject: activeThread ? current.subject : "", reply_to_id: "" }));
        await loadMessageCenterData();
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not send message." });
      }
    } finally {
      setMessageBusy(false);
    }
  }

  async function handleDeleteMessage(messageId) {
    if (!authMember) return;
    const response = await fetch(
      `${API_URL}/api/messages/${messageId}?${new URLSearchParams(actorParams(authMember)).toString()}`,
      { method: "DELETE", headers: { ...authHeaders() } },
    );
    const payload = await response.json();
    const body = payload.detail || payload;
    if (response.ok) {
      setMessage({ type: "success", text: "Message deleted." });
      await loadMessageCenterData();
    } else {
      setMessage({ type: "error", text: body.error || "Could not delete message." });
    }
  }

  async function handleToggleMessageRead(item, isRead) {
    if (!authMember) return;
    const formData = new FormData();
    formData.set("actor_role", authMember.role);
    formData.set("actor_email", authMember.role === "member" ? "" : authMember.email || "");
    formData.set("actor_client_id", authMember.role === "member" ? authMember.client_id || "" : "");
    formData.set("is_read", String(Boolean(isRead)));
    const result = await sendForm(`/api/messages/${item.id}/read`, formData, "PATCH");
    if (result.ok) {
      await loadMessageCenterData();
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not update message state." });
    }
  }

  async function resetMemberIssueSession(clientId) {
    setMessage(null);
    const response = await fetch(`${API_URL}/api/admin/members/${clientId}/reset-session`, { method: "POST", headers: { ...authHeaders() } });
    const body = await response.json();
    if (!response.ok) {
      setMessage({ type: "error", text: body.detail?.error || body.error || "Could not reset the member session." });
      return;
    }
    setMessage({ type: "success", text: "Member sessions reset. Ask the member to sign in again." });
    if (authMember?.role === "admin") await loadAdminPortal(clientId);
  }

  async function savePlannerRow(row) {
    setPlannerBusy(true);
    setPlannerSavingId(row.id);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.set("member_role", row.member_role);
      formData.set("issued_by", row.issued_by);
      formData.set("description", row.description);
      formData.set("planned_completion_date", row.planned_completion_date);
      formData.set("actual_completion_date", row.actual_completion_date || "");
      formData.set("status", row.status || "planned");
      formData.set("comments", row.comments || "");
      formData.set("criterion_code", row.criterion_code || "");
      formData.set("folder_id", row.folder_id || "");
      const path = row.isNew ? "/api/member/planner" : `/api/member/planner/${row.id}`;
      const method = row.isNew ? "POST" : "PATCH";
      const result = await sendForm(path, formData, method);
      if (result.ok) {
        setMessage({ type: "success", text: row.isNew ? "Event added." : "Event updated." });
        await loadHome();
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not save event." });
      }
    } finally {
      setPlannerBusy(false);
      setPlannerSavingId("");
    }
  }

  function setProfileField(field, value) {
    setProfileForm((current) => ({ ...current, [field]: value }));
  }

  async function handleProfileSubmit(event) {
    event.preventDefault();
    setProfileBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(profileForm).forEach(([key, value]) => {
        formData.set(key, typeof value === "boolean" ? String(value) : value);
      });
      const result = await sendForm("/api/member/profile", formData, "PUT");
      if (result.ok) {
        setProfile(result.payload);
        setProfileForm({ ...emptyProfileForm(), ...result.payload, profile_confirmed: Boolean(result.payload.profile_confirmed) });
        setMessage({ type: "success", text: "Member profile updated." });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not update member profile." });
      }
    } finally {
      setProfileBusy(false);
    }
  }

  async function handlePlannerSubmit(event) {
    event.preventDefault();
    setPlannerBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(plannerForm).forEach(([key, value]) => formData.set(key, value));
      const path = editingPlannerId ? `/api/member/planner/${editingPlannerId}` : "/api/member/planner";
      const method = editingPlannerId ? "PATCH" : "POST";
      const result = await sendForm(path, formData, method);
      if (result.ok) {
        setMessage({ type: "success", text: editingPlannerId ? "Planner item updated." : "Planner item added." });
        resetPlannerForm();
        await loadHome();
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not save planner item." });
      }
    } finally {
      setPlannerBusy(false);
    }
  }

  async function handleDeletePlanner(itemId) {
    if (String(itemId).startsWith("draft_")) {
      setPlannerRows((current) => current.filter((row) => row.id !== itemId));
      return;
    }
    if (!window.confirm("Delete this planner item?")) return;
    const response = await fetch(`${API_URL}/api/member/planner/${itemId}`, { method: "DELETE", headers: { ...authHeaders() } });
    const payload = await response.json();
    const body = payload.detail || payload;
    if (response.ok) {
      setMessage({ type: "success", text: "Planner item deleted." });
      if (editingPlannerId === itemId) resetPlannerForm();
      await loadHome();
    } else {
      setMessage({ type: "error", text: body.error || "Could not delete planner item." });
    }
  }

  function startEditPlanner(item) {
    setEditingPlannerId(item.id);
    setPlannerForm({
      member_role: item.member_role || "",
      issued_by: item.issued_by || "",
      description: item.description || "",
      planned_completion_date: item.planned_completion_date || "",
      actual_completion_date: item.actual_completion_date || "",
      status: item.status || "planned",
      comments: item.comments || "",
      criterion_code: item.criterion_code || "",
      folder_id: item.folder_id || "",
    });
  }

  async function handleAnalyzeOrSave(event) {
    event.preventDefault();
    if (!selectedFile || !memberContext.trim()) {
      setMessage({ type: "error", text: "Please add a short note and choose a file." });
      return;
    }
    setUploadBusy(true);
    setMessage(null);
    try {
      if (routeMode === "manual") {
        const title = selectedFile.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ").trim() || "Uploaded evidence";
        const result = await sendForm("/api/evidence", buildUploadForm({
          criterionCode: manualCategory,
          documentType: manualDocumentType,
          title,
          description: `Member note: ${memberContext.trim()}\n\nMember selected category: ${criteriaByCode[manualCategory]?.name || manualCategory}\n\nMember feedback on AI category: manual route chosen`,
          aiSummary: memberContext.trim(),
          qualityScore: 45,
        }));
        if (result.status === 409 && result.payload.status === "duplicate") {
          setDuplicateState({ mode: "manual", duplicate: result.payload.duplicate });
        } else if (result.ok) {
          setMessage({ type: "success", text: `Evidence saved. Evidence ID: ${result.payload.evidence_id}` });
          resetIntake();
          await refreshAfterSave();
        } else {
          setMessage({ type: "error", text: "Save failed. Please try again or contact Ascend support." });
        }
      } else {
        const formData = new FormData();
        formData.set("member_context", memberContext.trim());
        formData.set("file", selectedFile);
        const result = await sendForm("/api/evidence/analyze", formData);
        if (result.ok) {
          setDraft(result.payload);
          setOverrideCategory(result.payload.criterion_code);
          setOverrideDocumentType(result.payload.document_type || inferDocumentType(`${selectedFile?.name || ""} ${memberContext}`));
          setConsent(false);
          setDraftApprovalError("");
        } else {
          setMessage({ type: "error", text: "Evidence review failed. Please try again or contact Ascend support." });
        }
      }
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleSaveDraft(duplicateAction = "") {
    if (!selectedFile) return;
    let formData;
    if (routeMode === "manual") {
      const title = selectedFile.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ").trim() || "Uploaded evidence";
      formData = buildUploadForm({
        criterionCode: manualCategory,
        documentType: manualDocumentType,
        title,
        description: `Member note: ${memberContext.trim()}\n\nMember selected category: ${criteriaByCode[manualCategory]?.name || manualCategory}\n\nMember feedback on AI category: manual route chosen`,
        aiSummary: memberContext.trim(),
        qualityScore: 45,
        duplicateAction,
      });
    } else {
      if (!draft || !consent) {
        const approvalMessage = "Please approve the evidence draft before saving.";
        setDraftApprovalError(approvalMessage);
        setMessage({ type: "error", text: approvalMessage });
        return;
      }
      setDraftApprovalError("");
      formData = buildUploadForm({
        criterionCode: aiFeedback === "accept" ? draft.criterion_code : overrideCategory,
        documentType: aiFeedback === "accept" ? (draft.document_type || "Other") : overrideDocumentType,
        title: draft.title,
        description: `Member note: ${memberContext.trim()}\n\nAI description: ${draft.ai_description}\n\nMember feedback on AI category: ${aiFeedback === "accept" ? "accepted" : "rejected"}`,
        aiSummary: draft.ai_description,
        qualityScore: draft.quality_score,
        duplicateAction,
      });
    }
    setUploadBusy(true);
    setMessage(null);
    try {
      const result = await sendForm("/api/evidence", formData);
      if (result.status === 409 && result.payload.status === "duplicate") {
        setDuplicateState({ mode: routeMode, duplicate: result.payload.duplicate });
      } else if (result.ok) {
        setMessage({ type: "success", text: `Evidence saved. Evidence ID: ${result.payload.evidence_id}` });
        resetIntake();
        await refreshAfterSave();
      } else {
        setMessage({ type: "error", text: "Save failed. Please try again or contact Ascend support." });
      }
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleDuplicate(action) {
    setDuplicateState(null);
    await handleSaveDraft(action);
  }

  async function createFolder(event) {
    event.preventDefault();
    if (!view.criterionCode || !newFolderName.trim()) return;
    const formData = new FormData();
    formData.set("name", newFolderName.trim());
    formData.set("parent_id", newFolderParent);
    formData.set("color", FOLDER_COLORS[newFolderColor]);
    const result = await sendForm(`/api/criteria/${view.criterionCode}/folders`, formData);
    if (result.ok) {
      setMessage({ type: "success", text: "Folder created." });
      setNewFolderName("");
      setNewFolderParent("");
      setNewFolderColor("Emerald");
      loadWorkspace(view.criterionCode, workspaceQuery);
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not create folder." });
    }
  }

  async function updateFolder(event) {
    event.preventDefault();
    if (!selectedFolderId) return;
    const formData = new FormData();
    formData.set("name", folderForm.name.trim());
    formData.set("color", FOLDER_COLORS[folderForm.color]);
    formData.set("parent_id", "");
    const result = await sendForm(`/api/folders/${selectedFolderId}`, formData, "PATCH");
    if (result.ok) {
      setMessage({ type: "success", text: "Folder updated." });
      loadWorkspace(view.criterionCode, workspaceQuery);
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not update folder." });
    }
  }

  async function deleteFolder() {
    if (!selectedFolderId) return;
    if (!window.confirm("Delete this folder? Files and subfolders will stay available.")) return;
    const response = await fetch(`${API_URL}/api/folders/${selectedFolderId}`, { method: "DELETE", headers: { ...authHeaders() } });
    const payload = await response.json();
    const body = payload.detail || payload;
    if (response.ok) {
      setMessage({ type: "success", text: "Folder deleted. Files and subfolders were kept." });
      setSelectedFolderId("");
      loadWorkspace(view.criterionCode, workspaceQuery);
    } else {
      setMessage({ type: "error", text: body.error || "Could not delete folder." });
    }
  }

  async function deleteFile(item) {
    if (!window.confirm(`Remove ${item.label} from your active evidence list?`)) return;
    const response = await fetch(`${API_URL}/api/evidence/${item.entityId}`, { method: "DELETE", headers: { ...authHeaders() } });
    const payload = await response.json();
    const body = payload.detail || payload;
    if (response.ok) {
      setMessage({ type: "success", text: "File removed from active evidence." });
      await refreshAfterSave();
    } else {
      setMessage({ type: "error", text: body.error || "Could not remove file." });
    }
  }

  function handleDragStart(event, item) {
    event.dataTransfer.setData("application/json", JSON.stringify(item));
    event.dataTransfer.effectAllowed = "move";
  }

  async function moveDraggedItem(item, targetFolderId) {
    if (!view.criterionCode) return;
    if (item.kind === "file") {
      const formData = new FormData();
      formData.set("folder_id", targetFolderId || "");
      const result = await sendForm(`/api/evidence/${item.entityId}/folder`, formData, "PATCH");
      if (!result.ok) return setMessage({ type: "error", text: result.payload.error || "Could not move file." });
    } else {
      const formData = new FormData();
      formData.set("parent_id", targetFolderId || "");
      const result = await sendForm(`/api/folders/${item.entityId}`, formData, "PATCH");
      if (!result.ok) return setMessage({ type: "error", text: result.payload.error || "Could not move folder." });
    }
    setMessage({ type: "success", text: "Workspace updated." });
    loadWorkspace(view.criterionCode, workspaceQuery);
  }

  function setBuilderTaskField(field, value) {
    setBuilderTaskForm((current) => ({ ...current, [field]: value }));
  }

  function setBuilderOpportunityField(field, value) {
    setBuilderOpportunityForm((current) => ({ ...current, [field]: value }));
  }

  async function assignBuilderTask(event) {
    event.preventDefault();
    if (!selectedBuilderMemberId) return;
    setBuilderBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.set("client_id", selectedBuilderMemberId);
      formData.set("title", builderTaskForm.title);
      formData.set("description", builderTaskForm.description);
      formData.set("criterion_code", builderTaskForm.criterion_code);
      formData.set("due_date", builderTaskForm.due_date);
      formData.set("opportunity_id", builderTaskForm.opportunity_id);
      const result = await sendForm("/api/builder/tasks", formData);
      if (result.ok) {
        setMessage({ type: "success", text: "Task assigned to member." });
        setBuilderTaskForm({ opportunity_id: "", title: "", description: "", criterion_code: "", due_date: "" });
        await reloadOperationalWorkspace(selectedBuilderMemberId);
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not assign task." });
      }
    } finally {
      setBuilderBusy(false);
    }
  }

  function applyOpportunity(opportunityId) {
    const selected = builderOpportunities.find((item) => item.id === opportunityId);
    if (!selected) return;
    const due = new Date();
    due.setDate(due.getDate() + Number(selected.suggested_due_days || 14));
    setBuilderTaskForm({
      opportunity_id: selected.id,
      title: selected.title,
      description: selected.description,
      criterion_code: selected.criterion_code,
      due_date: due.toISOString().slice(0, 10),
    });
  }

  async function createBuilderOpportunity(event) {
    event.preventDefault();
    setBuilderBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(builderOpportunityForm).forEach(([key, value]) => formData.set(key, value));
      const result = await sendForm("/api/builder/opportunities", formData);
      if (result.ok) {
        setMessage({ type: "success", text: "Opportunity added to library." });
        setBuilderOpportunityForm({ criterion_code: "judging", title: "", description: "", target_evidence_type: "Invitation", suggested_due_days: "14" });
        await reloadOperationalWorkspace(selectedBuilderMemberId);
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not add opportunity." });
      }
    } finally {
      setBuilderBusy(false);
    }
  }

  if (!authReady) {
    return <main className="shell auth-shell"><div className="loading">Loading Ascend portal...</div></main>;
  }

  if (!authMember) {
    const selectedPortal = portalMeta(authMode);
    const loginChoices = devLoginOptions(authMode);
    return (
      <main className="login-page">
        <section className="login-hero">
          <img className="brand-logo login-logo" src={LOGO_URL} alt="Ascend HSI logo" />
          <p className="eyebrow">{selectedPortal.label}</p>
          <h1>Welcome back.</h1>
          <p>{selectedPortal.intro}</p>
          {message ? <div className={`banner ${message.type}`}>{message.text}</div> : null}
          <label className="portal-select-label">
            Portal
            <select value={authMode} onChange={(event) => setAuthMode(event.target.value)}>
              {PORTAL_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <form className="login-card" onSubmit={handleLogin}>
            <label>
              Email or username
              <input value={loginForm.username} onChange={(event) => setLoginForm((current) => ({ ...current, username: event.target.value }))} placeholder="member@example.com" />
            </label>
            <label>
              Password
              <input type="password" value={loginForm.password} onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))} placeholder="Enter your password" />
            </label>
            <button className="primary" type="submit" disabled={loginBusy}>{loginBusy ? "Signing in..." : "Sign In"}</button>
            <p className="login-note">{previewLoginNote(authMode)}</p>
          </form>
          {loginChoices.length ? (
            <div className="dev-login-panel">
              <div className="section-kicker">Quick Login Shortcuts</div>
              <div className="dev-login-grid">
                {loginChoices.map((account) => (
                  <button
                    key={account.username}
                    className="dev-login-btn"
                    type="button"
                    disabled={loginBusy}
                    onClick={() => handleDevLogin(account)}
                  >
                    <strong>{account.display_name || account.username}</strong>
                    <span>{account.username}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </main>
    );
  }

  const selectedCriterion = dashboard?.criteria?.find((item) => item.code === view.criterionCode);
  const memberDashboard = dashboard || emptyMemberDashboard(authMember, criteriaList);
  const portalHydrating = Boolean(authMember && loading);
  const selectedMemberHydrating = memberDetailLoading && Boolean(selectedBuilderMemberId);
  const memberInitials = `${(authMember.display_name || "M").slice(0, 1)}${(profile?.last_name || "").slice(0, 1)}`.toUpperCase();
  const portalTitle = authMember.role === "leader" ? "Leader Portal" : authMember.role === "attorney" ? "Attorney Portal" : authMember.role === "admin" ? "Admin Portal" : authMember.role === "builder" ? "Profile Builder Portal" : "Member Portal";
  const isLeaderExecutiveView = authMember.role === "leader" && leaderPerspective === "leader";
  const isLeaderBuilderView = authMember.role === "leader" && leaderPerspective === "builder";
  const isLeaderAttorneyView = authMember.role === "leader" && leaderPerspective === "attorney";
  const showingBuilderWorkspace = authMember.role === "builder" || isLeaderBuilderView;
  const builderLabel = showingBuilderWorkspace ? "Profile Builder" : "Leader";
  const memberSection = view.type === "messages" ? "messages" : view.type === "profile" ? "profile" : view.type === "planner" ? "planner" : view.type === "intake" ? "intake" : "home";
  function goToPortalHome() {
    setMessage(null);
    setMemberMenuOpen(false);
    if (authMember.role === "member") {
      setView({ type: "home", criterionCode: "" });
      setSelectedFolderId("");
      return;
    }
    setPortalSection("home");
  }
  const messagePanel = (
    <ThreadedMessageCenter
      title="Conversation Threads"
      intro="Keep conversations in one place. Start a new subject for a new thread, or reply inside an existing thread to keep the full history together."
      threads={messageCenter.threads || []}
      recipientOptions={messageCenter.recipient_options || []}
      composer={messageComposer}
      selectedThreadId={selectedThreadId}
      busy={messageBusy}
      onSelectThread={openThread}
      onComposerChange={setMessageComposerField}
      onSend={handleSendMessage}
      onDeleteMessage={handleDeleteMessage}
      onToggleRead={handleToggleMessageRead}
      actor={{
        role: authMember.role,
        key: authMember.role === "member" ? authMember.client_id : authMember.email,
      }}
    />
  );
  const batchReviewPanel = (
    <React.Fragment>
      <header className="hero">
        <p className="eyebrow">Batch Intake</p>
        <h1>Review a ZIP before anything lands in the case file.</h1>
        <p>Select the member first, upload the ZIP second, then approve file-by-file, by folder, or across the whole batch.</p>
      </header>

      <section className="panel" style={{ marginTop: "18px" }}>
        <div className="panel-header">
          <div>
            <div className="section-kicker">ZIP Review Queue</div>
            <h3 className="section-title">{isLeaderExecutiveView ? "Leader batch intake oversight" : "Attorney batch intake"}</h3>
            <p className="section-intro">Every file stays staged until a human approves where it will go.</p>
          </div>
          {batchSession ? (
            <div className="form-actions">
              <button className="ghost compact-btn" type="button" onClick={() => bulkUpdateBatchItems(batchSession.items.map((item) => item.id), "ready")}>Approve All</button>
              <button className="primary compact-btn" type="button" onClick={handleBatchCommit} disabled={batchCommitBusy}>
                {batchCommitBusy ? "Committing..." : "Commit Reviewed Files"}
              </button>
            </div>
          ) : null}
        </div>

        <form className="stacked-form" onSubmit={handleBatchAnalyze}>
          <label>
            Member
            <select value={selectedBuilderMemberId || ""} onChange={(event) => setSelectedBuilderMemberId(event.target.value)}>
              <option value="">Select member before upload</option>
              {builderMembers.map((member) => <option key={member.client_id} value={member.client_id}>{member.display_name}</option>)}
            </select>
          </label>
          <label>
            Attorney note
            <textarea value={batchContext} onChange={(event) => setBatchContext(event.target.value)} placeholder="Optional context for AI classification, expected criteria, or source of the batch." />
          </label>
          <label className="file-picker">
            ZIP file
            <input type="file" accept=".zip,application/zip" onChange={(event) => setBatchZipFile(event.target.files?.[0] || null)} />
          </label>
          <div className="form-actions">
            <button className="primary compact-btn" type="submit" disabled={batchBusy || !selectedBuilderMemberId}>
              {batchBusy ? "Preparing Queue..." : "Build Review Queue"}
            </button>
          </div>
        </form>

        {batchSessions.length ? (
          <section className="panel" style={{ marginTop: "18px" }}>
            <div className="section-kicker">Existing Sessions</div>
            <h3 className="section-title">Past and active batch reviews for this member</h3>
            <div className="task-mini-list">
              {batchSessions.map((session) => (
                <article key={session.id} className="task-mini-item">
                  <div>
                    <strong>{session.uploaded_zip_name}</strong>
                    <p>{session.item_count} file(s) • {session.status}</p>
                  </div>
                  <div className="task-mini-meta">
                    <span>{formatUploadedAt(session.created_at)}</span>
                    <button className="ghost compact-btn" type="button" onClick={() => openBatchSession(session.id)}>Open</button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {batchSession ? (
          <React.Fragment>
            <section className="metrics-grid" style={{ marginTop: "18px" }}>
              <MetricCard label="Files In Queue" value={batchSession.counts?.items || 0} />
              <MetricCard label="Ready" value={batchSession.counts?.ready || 0} />
              <MetricCard label="Needs Review" value={batchSession.counts?.pending || 0} />
              <MetricCard label="Committed" value={batchSession.counts?.committed || 0} />
            </section>

            {batchSession.skipped_files?.length ? (
              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Skipped During Extraction</div>
                <h3 className="section-title">Files not added to the queue</h3>
                <div className="task-mini-list">
                  {batchSession.skipped_files.map((item, index) => (
                    <article key={`skipped_${index}`} className="task-mini-item">
                      <strong>{item.path}</strong>
                      <p>{item.reason}</p>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            <div className="task-mini-list" style={{ marginTop: "18px" }}>
              {batchGroups.map((group) => (
                <article key={group.label} className="panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Folder Approval</div>
                      <h3 className="section-title">{group.label}</h3>
                      <p className="section-intro">{group.items.length} file(s) currently mapped here.</p>
                    </div>
                    <div className="form-actions">
                      <button className="ghost compact-btn" type="button" onClick={() => bulkUpdateBatchItems(group.items.map((item) => item.id), "ready")}>Approve Folder</button>
                      <button className="ghost compact-btn" type="button" onClick={() => bulkUpdateBatchItems(group.items.map((item) => item.id), "skipped", "skip")}>Skip Folder</button>
                    </div>
                  </div>
                  <div className="task-mini-list">
                    {group.items.map((item) => (
                      <article key={item.id} className="task-mini-item">
                        <div className="panel-header">
                          <div>
                            <strong>{item.original_file_name}</strong>
                            <p>Final destination: {item.final_destination_label}</p>
                          </div>
                          <div className="task-mini-meta">
                            <span>{item.review_status}</span>
                            <span>{item.criterion_name}</span>
                            <span>{item.document_type || "Other"}</span>
                          </div>
                        </div>

                        <label>
                          Title
                          <input value={item.title || ""} onChange={(event) => updateBatchSessionItem(item.id, { title: event.target.value })} />
                        </label>
                        <label>
                          Summary
                          <textarea value={item.ai_description || ""} onChange={(event) => updateBatchSessionItem(item.id, { ai_description: event.target.value })} />
                        </label>
                        <div className="profile-grid">
                          <label>
                            Category
                            <select value={item.criterion_code || "other"} onChange={(event) => updateBatchSessionItem(item.id, { criterion_code: event.target.value, assigned_folder_id: "", folder_decision: "root", assigned_folder_name: "" })}>
                              {(criteriaList || []).map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
                            </select>
                          </label>
                          <label>
                            Document type
                            <select value={item.document_type || "Other"} onChange={(event) => updateBatchSessionItem(item.id, { document_type: event.target.value })}>
                              {DOCUMENT_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                            </select>
                          </label>
                          <label>
                            Folder handling
                            <select value={item.folder_decision || "root"} onChange={(event) => updateBatchSessionItem(item.id, { folder_decision: event.target.value, assigned_folder_id: event.target.value === "existing" ? item.assigned_folder_id : "", assigned_folder_name: event.target.value === "create" ? (item.assigned_folder_name || item.suggested_folder_name || "") : "" })}>
                              <option value="root">Save at criterion root</option>
                              <option value="existing">Map to existing folder</option>
                              <option value="create">Create folder on commit</option>
                            </select>
                          </label>
                          <label>
                            Approval
                            <select value={item.review_status || "ready"} onChange={(event) => updateBatchSessionItem(item.id, { review_status: event.target.value })}>
                              <option value="ready">Approved</option>
                              <option value="pending">Needs review</option>
                              <option value="skipped">Skip</option>
                            </select>
                          </label>
                        </div>

                        {item.folder_decision === "existing" ? (
                          <label>
                            Existing folder
                            <select value={item.assigned_folder_id || ""} onChange={(event) => updateBatchSessionItem(item.id, { assigned_folder_id: event.target.value })}>
                              <option value="">Choose folder</option>
                              {(batchSession.folders_by_criterion?.[item.criterion_code] || []).map((folder) => (
                                <option key={folder.id} value={folder.id}>{folder.path}</option>
                              ))}
                            </select>
                          </label>
                        ) : null}

                        {item.folder_decision === "create" ? (
                          <label>
                            New folder name
                            <input value={item.assigned_folder_name || item.suggested_folder_name || ""} onChange={(event) => updateBatchSessionItem(item.id, { assigned_folder_name: event.target.value })} />
                          </label>
                        ) : null}

                        {item.duplicate ? (
                          <label>
                            Duplicate handling
                            <select value={item.duplicate_action || ""} onChange={(event) => updateBatchSessionItem(item.id, { duplicate_action: event.target.value })}>
                              <option value="">Resolve before commit</option>
                              <option value="copy">Keep another copy</option>
                              <option value="replace">Replace existing file</option>
                              <option value="skip">Skip this item</option>
                            </select>
                          </label>
                        ) : null}

                        {item.duplicate ? <p>Existing file found: <strong>{item.duplicate.file_name}</strong> in {criteriaByCode[item.duplicate.criterion_code]?.name || item.duplicate.criterion_code}.</p> : null}
                        {item.commit_message ? <p>{item.commit_message}</p> : null}
                        <div className="form-actions">
                          <button className="ghost compact-btn" type="button" onClick={() => saveBatchItem(item)}>Save File Review</button>
                        </div>
                      </article>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </React.Fragment>
        ) : null}
      </section>
    </React.Fragment>
  );
  const assistantPanel = ["builder", "leader", "attorney"].includes(authMember.role) ? (
    <AssistantPanel
      open={assistantOpen}
      onToggle={() => setAssistantOpen((current) => !current)}
      assistantName="Ascend Navigator"
      portalLabel={assistantPortalLabel}
      thread={assistantThread}
      input={assistantInput}
      onInputChange={setAssistantInput}
      onSubmit={askAssistant}
      onUsePrompt={useAssistantPrompt}
      onClear={clearAssistantThread}
      busy={assistantBusy}
    />
  ) : null;
  const supportPanel = authMember ? (
    <SupportPanel
      open={supportOpen}
      onToggle={toggleSupportPanel}
      agentName="Ascend Beacon"
      portalLabel={portalTitle}
      form={supportForm}
      busy={supportBusy}
      submission={supportSubmission}
      onFieldChange={setSupportField}
      onSubmit={handleSupportSubmit}
      onReset={resetSupportTicketForm}
      onOpenInbox={openSupportInbox}
      onAttachmentFileChange={setSupportAttachmentFile}
      onAttachmentDescriptionChange={setSupportAttachmentDescription}
      onAddAttachment={addSupportAttachment}
      onRemoveAttachment={removeSupportAttachment}
    />
  ) : null;
  const helpManualDialog = authMember ? (
    <HelpManualDialog
      open={helpManualOpen}
      role={authMember.role}
      portalTitle={portalTitle}
      query={helpManualQuery}
      onQueryChange={setHelpManualQuery}
      onClose={() => setHelpManualOpen(false)}
    />
  ) : null;

  if (authMember.role === "builder" || (authMember.role === "leader" && !isLeaderAttorneyView)) {
    const builderInitials = (authMember.display_name || "B").split(" ").map((part) => part.slice(0, 1)).join("").slice(0, 2).toUpperCase();
    const leaderMetrics = leaderInsights?.metrics || builderDashboard?.metrics || {};
    const builderSidebarItems = [
      { value: "home", label: "Builder Home" },
      { value: "members", label: "Assigned Members" },
      { value: "opportunities", label: "Opportunities" },
      { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}` },
    ];
    const leaderSidebarItems = [
      { value: "home", label: "Executive Overview" },
      { value: "members", label: "Member Review" },
      { value: "risks", label: "Risk & Bottlenecks" },
      { value: "capacity", label: "Team Capacity" },
      { value: "batch", label: "Batch Intake" },
      { value: "opportunities", label: "Opportunities" },
      { value: "oversight", label: "Assignment Oversight" },
      { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}` },
    ];
    return (
      <React.Fragment>
        <main className="shell attorney-shell">
          <aside className="sidebar attorney-sidebar">
          <PortalBrand onHome={goToPortalHome} label={isLeaderExecutiveView ? "Go to leader home" : "Go to builder home"} />
          <div className="brand-sub">{isLeaderExecutiveView ? "Leader Workspace" : isLeaderBuilderView ? "Leader Acting As Builder" : "Profile Builder Workspace"}</div>
          {authMember.role === "leader" ? (
            <div className="side-card perspective-side-card">
              <strong>Assume Portal View</strong>
              <p>Switch between the CEO dashboard, builder workspace, and attorney workspace without leaving the leader account.</p>
              <LeaderPerspectiveSwitch value={leaderPerspective} onChange={setLeaderPerspectiveMode} />
            </div>
          ) : null}
          <SidebarNav
            items={isLeaderExecutiveView ? leaderSidebarItems : builderSidebarItems}
            value={portalSection}
            onChange={setPortalSection}
          />
          <div className="side-card">
            <strong>Welcome {authMember.display_name}</strong>
            <p>{isLeaderExecutiveView ? "See the full profile-building operation, rebalance assignments, and keep each case moving toward a stronger EB1A file." : "Work through the builder workspace with leadership visibility still intact."}</p>
          </div>
          <div className="side-card">
            <strong>At a glance</strong>
            <p>Assigned members: {(isLeaderExecutiveView ? leaderMetrics.member_count : builderDashboard?.metrics.member_count) || 0}</p>
            <p>Active tasks: {(isLeaderExecutiveView ? leaderMetrics.active_tasks : builderDashboard?.metrics.active_tasks) || 0}</p>
            <p>Opportunity library: {builderDashboard?.metrics.opportunity_count || 0}</p>
          </div>
          <span className="side-note">{authMember.role === "leader" ? (isLeaderExecutiveView ? "Leader portal only" : "Leader operating in builder visibility mode") : "Profile builder portal only"}</span>
        </aside>
        <section className="main attorney-main">
          <div className="topbar">
            <div className="topbar-copy">
              <span className="topbar-label">{portalTitle}</span>
              <div className="topbar-welcome">Welcome {authMember.display_name}.</div>
              <strong>{isLeaderExecutiveView ? "See builder workloads, member momentum, and executive-level movement in one place." : "Guide each member toward the highest-value profile building work with leader-level visibility."}</strong>
            </div>
            <div className="member-menu-wrap">
              <button className="member-menu-trigger" type="button" onClick={() => setMemberMenuOpen((current) => !current)}>
                <span className="member-avatar">{builderInitials}</span>
                <span className="member-trigger-copy">
                  <strong>{authMember.display_name}</strong>
                  <span>{authMember.email}</span>
                  <LastLoginStamp user={authMember} />
                </span>
              </button>
              {memberMenuOpen ? (
                <div className="member-menu">
                  <button type="button" onClick={() => { setPasswordDialogOpen(true); setMemberMenuOpen(false); }}>Change Password</button>
                  <button type="button" onClick={openHelpManual}>Help Manual</button>
                  <button type="button" onClick={handleLogout}>Logout</button>
                </div>
              ) : null}
            </div>
          </div>

          {message ? <div className={`banner ${message.type}`}>{message.text}</div> : null}
          {passwordDialogOpen ? (
            <div className="modal-backdrop" onClick={() => setPasswordDialogOpen(false)}>
              <section className="modal-card" onClick={(event) => event.stopPropagation()}>
                <div className="panel-header">
                  <div><div className="section-kicker">Account</div><h3 className="section-title">Change Password</h3></div>
                  <button className="ghost compact-btn" type="button" onClick={() => setPasswordDialogOpen(false)}>Close</button>
                </div>
                <form className="stacked-form" onSubmit={handlePasswordChange}>
                  <label>Current Password<input type="password" value={passwordForm.current_password} onChange={(event) => setPasswordForm((current) => ({ ...current, current_password: event.target.value }))} /></label>
                  <label>New Password<input type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm((current) => ({ ...current, new_password: event.target.value }))} /></label>
                  <label>Confirm New Password<input type="password" value={passwordForm.confirm_password} onChange={(event) => setPasswordForm((current) => ({ ...current, confirm_password: event.target.value }))} /></label>
                  <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={passwordBusy}>{passwordBusy ? "Updating..." : "Update Password"}</button></div>
                </form>
              </section>
            </div>
          ) : null}

          {portalHydrating ? (
            <PortalHydrationNotice
              title={isLeaderExecutiveView ? "Loading leader workspace" : "Loading profile builder workspace"}
              detail="The portal shell is ready while roster, opportunity, criteria, and selected member data refresh."
            />
          ) : selectedMemberHydrating ? (
            <PortalHydrationNotice
              title="Refreshing selected member"
              detail="The current workspace stays available while Ascend loads the selected member detail."
            />
          ) : null}

          {portalSection === "messages" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Messages</p>
                <h1>Conversations, one place.</h1>
                <p>Open threads, reply in context, and start a new subject without mixing it into active work screens.</p>
              </header>
              {messagePanel}
            </React.Fragment>
          ) : isLeaderExecutiveView && portalSection === "risks" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Risk & Bottlenecks</p>
                <h1>Intervene where velocity is most exposed.</h1>
                <p>Focus on stale cases, assignment gaps, and the exact blockers most likely to slow execution across the portfolio.</p>
              </header>

              <section className="metrics-grid">
                <MetricCard label="High Risk" value={leaderMetrics.at_risk_cases || 0} />
                <MetricCard label="Stale Cases" value={leaderMetrics.stale_cases || 0} />
                <MetricCard label="Needs Builder" value={leaderMetrics.unassigned_cases || 0} />
                <MetricCard label="Attorney Routed" value={leaderMetrics.assigned_attorneys || 0} />
              </section>

              <section className="executive-grid" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Risk Mix</div>
                  <h3 className="section-title">Current bottlenecks</h3>
                  <p className="section-intro">What is driving intervention needs right now.</p>
                  <ExecutiveBarList items={leaderInsights?.risk_summary || []} />
                </section>

                <section className="panel">
                  <div className="section-kicker">Stage Pressure</div>
                  <h3 className="section-title">Where risk is concentrated</h3>
                  <p className="section-intro">Stage count plotted with risk-heavy pockets visible by volume.</p>
                  <ExecutiveBarList
                    items={(leaderInsights?.stage_summary || []).map((item) => ({
                      label: item.label,
                      count: item.count,
                      meta: `${item.risk_count} at risk • avg readiness ${item.avg_readiness}%`,
                    }))}
                    metaKey="meta"
                  />
                </section>
              </section>

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Intervention Queue</div>
                <h3 className="section-title">Cases that need leadership attention</h3>
                <p className="section-intro">Open the member record directly from the risk queue to drill down without losing context.</p>
                <WatchlistTable
                  rows={leaderInsights?.watchlist || []}
                  onOpenMember={(clientId) => {
                    setSelectedBuilderMemberId(clientId);
                    setPortalSection("members");
                  }}
                />
              </section>
            </React.Fragment>
          ) : isLeaderExecutiveView && portalSection === "capacity" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Team Capacity</p>
                <h1>Workload, throughput, and routing pressure.</h1>
                <p>See where builders and attorneys are overloaded, where capacity is available, and which parts of the team are carrying the highest-risk mix.</p>
              </header>

              <section className="executive-grid" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Builder Capacity</div>
                  <h3 className="section-title">Profile builder load</h3>
                  <p className="section-intro">Pressure score blends caseload, high-risk mix, and open task volume.</p>
                  <ExecutiveBarList
                    items={(leaderInsights?.builder_capacity || []).map((item) => ({
                      label: item.display_name,
                      count: item.capacity_pressure,
                      meta: `${item.assigned_members} cases • ${item.high_risk_cases} high risk • avg readiness ${item.avg_readiness}%`,
                    }))}
                    metaKey="meta"
                    emptyText="No builder capacity data yet."
                  />
                </section>

                <section className="panel">
                  <div className="section-kicker">Attorney Capacity</div>
                  <h3 className="section-title">Attorney load</h3>
                  <p className="section-intro">Pressure score helps surface handoff imbalance before petition work slows down.</p>
                  <ExecutiveBarList
                    items={(leaderInsights?.attorney_capacity || []).map((item) => ({
                      label: item.display_name,
                      count: item.capacity_pressure,
                      meta: `${item.assigned_members} cases • ${item.high_risk_cases} high risk • avg readiness ${item.avg_readiness}%`,
                    }))}
                    metaKey="meta"
                    emptyText="No attorney capacity data yet."
                  />
                </section>
              </section>
            </React.Fragment>
          ) : isLeaderExecutiveView && portalSection === "oversight" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Assignment Oversight</p>
                <h1>Routing and workload, one view.</h1>
                <p>Invite members, optionally route them to a Profile Builder or Attorney immediately, and rebalance assignments later without crowding the Leader home page.</p>
              </header>
              <AssignmentFlowGuide />

              <section className="metrics-grid">
                <MetricCard label="Invited Members" value={leaderInvites.filter((item) => item.status !== "registered").length} />
                <MetricCard label="Registered Members" value={builderMembers.filter((item) => item.registration_status === "registered").length} />
                <MetricCard label="Builder Assigned" value={builderMembers.filter((item) => item.builder_name).length} />
                <MetricCard label="Attorney Assigned" value={builderMembers.filter((item) => item.attorney_name).length} />
              </section>

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Assignment Oversight</div>
                <h3 className="section-title">Intake, Builder, And Attorney Routing</h3>
                <p className="section-intro">Track invitation status, assign the right profile builder or attorney during invite creation, or leave either assignment open until the case is ready.</p>
                <MemberSearchBox
                  value={memberSearchQuery}
                  onChange={setMemberSearchQuery}
                  total={builderMembers.length}
                  visible={filteredBuilderMembers.length}
                  label="Search roster"
                />
                <div className="assignment-oversight-table">
                  <div className="assignment-oversight-row assignment-oversight-head">
                    <span>Member</span>
                    <span>Domain</span>
                    <span>Registration</span>
                    <span>Profile builder</span>
                    <span>Attorney</span>
                    <span>Current stage</span>
                    <span>Action</span>
                  </div>
                  {filteredBuilderMembers.map((item) => {
                    const assignment = leaderAssignments.find((entry) => entry.client_id === item.client_id) || {};
                    const memberSummary = `${item.display_name} • ${item.readiness_score || 0}% readiness`;
                    const domain = item.industry_domain || "Other";
                    const registration = item.registration_status === "registered" ? "Registered" : "Invite sent";
                    const stage = item.status.replaceAll("_", " ");
                    return (
                      <article key={`asg_${item.client_id}`} className="assignment-oversight-row">
                        <div className="assignment-member-cell" title={memberSummary}>
                          <strong>{item.display_name}</strong>
                          <small>{item.readiness_score || 0}% readiness</small>
                        </div>
                        <span title={domain}>{domain}</span>
                        <span title={registration}>{registration}</span>
                        <select value={assignment.builder_id || ""} onChange={(event) => setLeaderBuilderAssignment(item.client_id, event.target.value)}>
                          <option value="">Select builder</option>
                          {leaderBuilders.map((builder) => <option key={builder.id} value={builder.id}>{builder.display_name}</option>)}
                        </select>
                        <select value={assignment.attorney_id || ""} onChange={(event) => setLeaderAttorneyAssignment(item.client_id, event.target.value)}>
                          <option value="">Select attorney</option>
                          {leaderAttorneys.map((attorney) => <option key={attorney.id} value={attorney.id}>{attorney.display_name}</option>)}
                        </select>
                        <span title={stage}>{stage}</span>
                        <button className="ghost compact-btn" type="button" onClick={() => { setSelectedBuilderMemberId(item.client_id); setPortalSection("home"); }}>Review</button>
                      </article>
                    );
                  })}
                  {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                </div>
              </section>

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Registration Flow</div>
                <h3 className="section-title">Recent Member Invites</h3>
                <p className="section-intro">Quick confirmation of who has been invited, who has registered, and where the next assignment handoff should happen.</p>
                <div className="task-mini-list">
                  {leaderInvites.length ? leaderInvites.map((item) => (
                    <article key={item.id} className="task-mini-item">
                      <strong>{item.display_name}</strong>
                      <p>{item.email}</p>
                      <div className="task-mini-meta">
                        <span>{item.status === "registered" ? "Registered" : "Invite sent"}</span>
                        <span>{item.invite_sent_at ? `Invited ${item.invite_sent_at}` : "Invite pending"}</span>
                        <span>{item.registered_at ? `Registered ${item.registered_at}` : "Awaiting registration"}</span>
                      </div>
                    </article>
                  )) : <p className="empty-state">No member invites yet.</p>}
                </div>
              </section>
            </React.Fragment>
          ) : portalSection === "members" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">{isLeaderExecutiveView ? "Member Review" : "Assigned Members"}</p>
                <h1>{isLeaderExecutiveView ? "Member progress, ready for review." : "Assigned members, easy to triage."}</h1>
                <p>{isLeaderExecutiveView ? "Open a member to review readiness, criterion movement, and builder-issued work without mixing this into intake routing." : "Open a member to review readiness, criterion coverage, and where your next profile-building push should go."}</p>
              </header>

              <section className="builder-layout">
                <section className="panel">
                  <div className="section-kicker">Assigned Members</div>
                  <h3 className="section-title">Member Roster</h3>
                  <p className="section-intro">See which members are trending well and where to focus next.</p>
                  <MemberSearchBox
                    value={memberSearchQuery}
                    onChange={setMemberSearchQuery}
                    total={builderMembers.length}
                    visible={filteredBuilderMembers.length}
                  />
                  <div className="builder-member-list attorney-member-list">
                    {filteredBuilderMembers.map((item) => (
                      <button key={item.client_id} type="button" className={`builder-member-card attorney-member-card ${selectedBuilderMemberId === item.client_id ? "active" : ""}`} onClick={() => setSelectedBuilderMemberId(item.client_id)}>
                        <strong>{item.display_name}</strong>
                        <span>{item.current_title || "Profile in progress"}{item.current_employer ? ` • ${item.current_employer}` : ""}</span>
                        <span>Readiness {item.readiness_score}% • {item.evidence_count} evidence • {item.open_task_count} open tasks</span>
                        <span className={`status-pill ${item.momentum === "Strong" ? "completed" : item.momentum === "Needs focus" ? "blocked" : "in_progress"}`}>{item.momentum}</span>
                      </button>
                    ))}
                    {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                  </div>
                </section>

                <section className="panel">
                  <div className="section-kicker">Member Detail</div>
                  <h3 className="section-title">{builderMemberDetail?.member?.display_name || "Select a member"}</h3>
                  <p className="section-intro">Clear view of profile position, criterion coverage, and tasks already in flight.</p>
                  {builderMemberDetail ? (
                    <React.Fragment>
                      <div className="builder-detail-grid">
                        <article className="action-row">
                          <strong>Current profile position</strong>
                          <p>{builderMemberDetail.profile.primary_field || "Primary field not yet captured"}{builderMemberDetail.profile.current_title ? ` • ${builderMemberDetail.profile.current_title}` : ""}</p>
                          <span>Readiness: {builderMemberDetail.member.readiness_score}%</span>
                        </article>
                        <article className="action-row">
                          <strong>Criterion coverage</strong>
                          <p>{builderMemberDetail.criteria.filter((item) => item.evidence_count).length} criteria started across the current evidence set.</p>
                          <span>{builderMemberDetail.criteria.map((item) => `${item.name}: ${item.evidence_count}`).join(" • ")}</span>
                        </article>
                        <article className="action-row">
                          <strong>{builderLabel}-issued tasks</strong>
                          <p>{builderMemberDetail.tasks.length ? builderMemberDetail.tasks.map((item) => item.title).slice(0, 3).join(" • ") : `No ${builderLabel.toLowerCase()} tasks assigned yet.`}</p>
                          <span>{builderMemberDetail.tasks.filter((item) => item.status === "open").length} open</span>
                        </article>
                      </div>
                      <BuilderWorkbenchPanel workbench={builderMemberDetail.builder_workbench} />
                      <div className="task-mini-list">
                        <div className="section-kicker">Tasks In Flight</div>
                        {builderMemberDetail.tasks.length ? (
                          builderMemberDetail.tasks.slice(0, 6).map((item) => (
                            <article key={item.id} className="task-mini-item">
                              <div>
                                <strong>{item.title}</strong>
                                <p>{item.description || "Builder guidance will appear here."}</p>
                              </div>
                              <div className="task-mini-meta">
                                <span>{criteriaByCode[item.criterion_code]?.name || "No category"}</span>
                                <span>{item.due_date ? `Due ${item.due_date}` : "No due date"}</span>
                                <span className={`status-pill ${item.status === "completed" ? "completed" : item.status === "blocked" ? "blocked" : "in_progress"}`}>{item.status === "open" ? "Open" : item.status}</span>
                              </div>
                            </article>
                          ))
                        ) : (
                          <p className="empty-state">No builder tasks assigned yet.</p>
                        )}
                      </div>
                      <section className="panel panel-subsection">
                        <div className="section-kicker">Evidence Library</div>
                        <h3 className="section-title">Evidence by criterion</h3>
                        <p className="section-intro">Review the selected member’s evidence in organized groups and open any file directly.</p>
                        <EvidenceGroupPanel
                          evidence={builderMemberDetail.evidence || []}
                          criteriaByCode={criteriaByCode}
                          emptyText="No evidence files available for this member yet."
                        />
                      </section>
                    </React.Fragment>
                  ) : <p className="empty-state">Choose a member to review their progress and assign work.</p>}
                </section>
              </section>
            </React.Fragment>
          ) : isLeaderExecutiveView && portalSection === "batch" ? (
            batchReviewPanel
          ) : portalSection === "opportunities" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Opportunities</p>
                <h1>Reusable work, ready to push.</h1>
                <p>Keep opportunity templates and member task assignment in one separate workspace so the home page stays focused on momentum and summary.</p>
              </header>

              <section className="builder-layout">
                <section className="panel">
                  <div className="section-kicker">Opportunity Pool</div>
                  <h3 className="section-title">Profile Building Opportunities</h3>
                  <p className="section-intro">Reusable opportunities you can push to one or more assigned members.</p>
                  <div className="builder-opportunity-list">
                    {builderOpportunities.map((item) => (
                      <article key={item.id} className="action-row">
                        <strong>{item.title}</strong>
                        <p>{item.description}</p>
                        <span>{item.criterion_name} • {item.target_evidence_type} • {item.suggested_due_days} day target</span>
                        <div className="form-actions">
                          <button className="ghost compact-btn" type="button" onClick={() => applyOpportunity(item.id)}>Use for selected member</button>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="panel">
                  <div className="section-kicker">Push Work</div>
                  <h3 className="section-title">Assign Tasks To Member</h3>
                  <p className="section-intro">Turn an opportunity or custom guidance into a clear next step for the assigned member.</p>
                  <form className="stacked-form" onSubmit={assignBuilderTask}>
                    <label>Opportunity template<select value={builderTaskForm.opportunity_id} onChange={(event) => { setBuilderTaskField("opportunity_id", event.target.value); applyOpportunity(event.target.value); }}><option value="">Custom task</option>{builderOpportunities.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
                    <label>Task title<input value={builderTaskForm.title} onChange={(event) => setBuilderTaskField("title", event.target.value)} /></label>
                    <label>Guidance for member<textarea value={builderTaskForm.description} onChange={(event) => setBuilderTaskField("description", event.target.value)} /></label>
                    <label>Evidence category<select value={builderTaskForm.criterion_code} onChange={(event) => setBuilderTaskField("criterion_code", event.target.value)}><option value="">Choose category</option>{criteriaList.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}</select></label>
                    <label>Due date<input type="date" value={builderTaskForm.due_date} onChange={(event) => setBuilderTaskField("due_date", event.target.value)} /></label>
                    <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={builderBusy || !selectedBuilderMemberId}>{builderBusy ? "Assigning..." : "Assign To Member"}</button></div>
                  </form>

                  <div className="panel-divider" />

                  <h3 className="section-title">Add Opportunity To Library</h3>
                  <form className="stacked-form" onSubmit={createBuilderOpportunity}>
                    <label>Category<select value={builderOpportunityForm.criterion_code} onChange={(event) => setBuilderOpportunityField("criterion_code", event.target.value)}>{criteriaList.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}</select></label>
                    <label>Opportunity title<input value={builderOpportunityForm.title} onChange={(event) => setBuilderOpportunityField("title", event.target.value)} placeholder="For example: Selective fellowship application" /></label>
                    <label>Description<textarea value={builderOpportunityForm.description} onChange={(event) => setBuilderOpportunityField("description", event.target.value)} placeholder="Explain why this opportunity matters and what the member should aim to collect." /></label>
                    <label>Target evidence type<select value={builderOpportunityForm.target_evidence_type} onChange={(event) => setBuilderOpportunityField("target_evidence_type", event.target.value)}>{DOCUMENT_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
                    <label>Suggested due days<input value={builderOpportunityForm.suggested_due_days} onChange={(event) => setBuilderOpportunityField("suggested_due_days", event.target.value)} /></label>
                    <div className="form-actions"><button className="ghost compact-btn" type="submit" disabled={builderBusy}>{builderBusy ? "Saving..." : "Add To Library"}</button></div>
                  </form>
                </section>
              </section>
            </React.Fragment>
          ) : (
            <React.Fragment>

              <header className="hero">
                <p className="eyebrow">{isLeaderExecutiveView ? "Executive Overview" : "Builder Dashboard"}</p>
                <h1>{isLeaderExecutiveView ? "Operations, one calm command center." : "Your members, one view."}</h1>
                <p>{isLeaderExecutiveView ? "Track portfolio health, execution velocity, bottlenecks, risk concentration, and near-term completion outlook without losing the ability to drill into a case." : "See how each assigned member is progressing, identify who needs attention, and push the right profile-building opportunities into their queue."}</p>
                <div className="hero-chips">
                  <span className="hero-chip">{isLeaderExecutiveView ? "Executive funnel" : "Assigned member roster"}</span>
                  <span className="hero-chip">{isLeaderExecutiveView ? "Timeline trends" : "Opportunity library"}</span>
                  <span className="hero-chip">{isLeaderExecutiveView ? "Drilldown watchlist" : `${builderLabel}-issued tasks`}</span>
                </div>
              </header>

              <section className="metrics-grid">
                <MetricCard label={isLeaderExecutiveView ? "Active Cases" : "Assigned Members"} value={builderDashboard?.metrics.member_count || 0} />
                <MetricCard label={isLeaderExecutiveView ? "Petition Ready" : "Active Tasks"} value={isLeaderExecutiveView ? (leaderMetrics.petition_ready_cases || 0) : (builderDashboard?.metrics.active_tasks || 0)} />
                <MetricCard label={isLeaderExecutiveView ? "High Risk" : "Average Readiness"} value={isLeaderExecutiveView ? (leaderMetrics.at_risk_cases || 0) : `${builderDashboard?.metrics.avg_readiness || 0}%`} />
                <MetricCard label={isLeaderExecutiveView ? "Weekly Execution" : "Opportunities"} value={isLeaderExecutiveView ? (leaderMetrics.weekly_execution_events || 0) : (builderDashboard?.metrics.opportunity_count || 0)} />
              </section>

          {isLeaderExecutiveView ? (
            <React.Fragment>
              <section className="executive-grid" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Executive Funnel</div>
                  <h3 className="section-title">Coverage through the pipeline</h3>
                  <p className="section-intro">Milestone coverage across registration, staffing, and petition readiness.</p>
                  <ExecutiveBarList items={leaderInsights?.funnel || []} />
                </section>

                <section className="panel">
                  <div className="section-kicker">Execution Timeline</div>
                  <h3 className="section-title">Recent operating tempo</h3>
                  <p className="section-intro">Weekly trend of invites, assignments, and execution movement.</p>
                  <TimelinePlot points={leaderInsights?.timeline || []} />
                </section>
              </section>

              <section className="executive-grid" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Domain Mix</div>
                  <h3 className="section-title">Portfolio by member background</h3>
                  <p className="section-intro">See where work is coming from and where risk or readiness is clustering.</p>
                  <ExecutiveBarList
                    items={(leaderDomainSummary || []).map((item) => ({
                      label: item.domain,
                      count: item.member_count,
                      meta: `Avg readiness ${item.avg_readiness}% • ${item.at_risk_count || 0} at risk`,
                    }))}
                    metaKey="meta"
                  />
                </section>

                <section className="panel">
                  <div className="section-kicker">90-Day Outlook</div>
                  <h3 className="section-title">Completion outlook by readiness band</h3>
                  <p className="section-intro">A pragmatic forecast based on current readiness and staffing posture.</p>
                  <ExecutiveBarList
                    items={(leaderInsights?.forecast || []).map((item) => ({
                      label: item.label,
                      count: item.count,
                      meta: item.detail,
                    }))}
                    metaKey="meta"
                  />
                </section>
              </section>

              <LeaderBusinessPanel insights={leaderInsights} />

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Intervention Watchlist</div>
                <h3 className="section-title">Cases most likely to need leadership action</h3>
                <p className="section-intro">Drill directly into the member record from here, then move to Member Review or Assignment Oversight.</p>
                <WatchlistTable
                  rows={leaderInsights?.watchlist || []}
                  onOpenMember={(clientId) => {
                    setSelectedBuilderMemberId(clientId);
                    setPortalSection("members");
                  }}
                />
              </section>

              <section className="builder-layout" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Member Intake</div>
                  <h3 className="section-title">Invite A New Member</h3>
                  <p className="section-intro">Send the member registration path by email, then optionally route the case to a Profile Builder and Attorney now or leave assignment open for later.</p>
                  <AssignmentFlowGuide />
                  <form className="stacked-form" onSubmit={submitLeaderInvite}>
                    <label>First name<input value={leaderInviteForm.first_name} onChange={(event) => setLeaderInviteField("first_name", event.target.value)} /></label>
                    <label>Last name<input value={leaderInviteForm.last_name} onChange={(event) => setLeaderInviteField("last_name", event.target.value)} /></label>
                    <label>Email<input type="email" value={leaderInviteForm.email} onChange={(event) => setLeaderInviteField("email", event.target.value)} /></label>
                    <label>Domain<select value={leaderInviteForm.industry_domain} onChange={(event) => setLeaderInviteField("industry_domain", event.target.value)}>{DOMAIN_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
                    <label>Primary field<input value={leaderInviteForm.primary_field} onChange={(event) => setLeaderInviteField("primary_field", event.target.value)} placeholder="For example: Clinical AI, Claims Analytics, Biotechnology" /></label>
                    <label>Current title<input value={leaderInviteForm.current_title} onChange={(event) => setLeaderInviteField("current_title", event.target.value)} /></label>
                    <label>Current employer<input value={leaderInviteForm.current_employer} onChange={(event) => setLeaderInviteField("current_employer", event.target.value)} /></label>
                    <label>Profile builder (optional)<select value={leaderInviteForm.builder_id} onChange={(event) => setLeaderInviteField("builder_id", event.target.value)}><option value="">Assign later</option>{leaderBuilders.map((builder) => <option key={builder.id} value={builder.id}>{builder.display_name}</option>)}</select></label>
                    <label>Attorney (optional)<select value={leaderInviteForm.attorney_id} onChange={(event) => setLeaderInviteField("attorney_id", event.target.value)}><option value="">Assign later</option>{leaderAttorneys.map((attorney) => <option key={attorney.id} value={attorney.id}>{attorney.display_name}</option>)}</select></label>
                    <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={builderBusy}>{builderBusy ? "Preparing..." : "Create Invite And Route"}</button></div>
                  </form>
                </section>

                <section className="panel">
                  <div className="section-kicker">Capacity Snapshot</div>
                  <h3 className="section-title">Who is carrying the most pressure</h3>
                  <p className="section-intro">Open Team Capacity for a fuller load review, or jump to Assignment Oversight to rebalance now.</p>
                  <ExecutiveBarList
                    items={(leaderInsights?.builder_capacity || []).slice(0, 5).map((item) => ({
                      label: item.display_name,
                      count: item.capacity_pressure,
                      meta: `${item.assigned_members} cases • ${item.high_risk_cases} high risk`,
                    }))}
                    metaKey="meta"
                    emptyText="No builder pressure data yet."
                  />
                </section>
              </section>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <section className="builder-layout" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Member Focus</div>
                  <h3 className="section-title">Who needs the next push</h3>
                  <p className="section-intro">Choose a member, review momentum quickly, then move into opportunities or assigned member review.</p>
                  <MemberSearchBox
                    value={memberSearchQuery}
                    onChange={setMemberSearchQuery}
                    total={builderMembers.length}
                    visible={filteredBuilderMembers.length}
                  />
                  <div className="builder-member-list attorney-member-list">
                    {filteredBuilderMembers.map((item) => (
                      <button key={item.client_id} type="button" className={`builder-member-card attorney-member-card ${selectedBuilderMemberId === item.client_id ? "active" : ""}`} onClick={() => setSelectedBuilderMemberId(item.client_id)}>
                        <strong>{item.display_name}</strong>
                        <span>{item.current_title || "Profile in progress"}{item.current_employer ? ` • ${item.current_employer}` : ""}</span>
                        <span>Readiness {item.readiness_score}% • {item.evidence_count} evidence • {item.open_task_count} open tasks</span>
                        <span className={`status-pill ${item.momentum === "Strong" ? "completed" : item.momentum === "Needs focus" ? "blocked" : "in_progress"}`}>{item.momentum}</span>
                      </button>
                    ))}
                    {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                  </div>
                </section>

                <section className="panel">
                  <div className="section-kicker">Selected Member</div>
                  <h3 className="section-title">{builderMemberDetail?.member?.display_name || "Select a member"}</h3>
                  <p className="section-intro">Quick builder-style summary of the selected case, with the strongest next actions visible at a glance.</p>
                  {builderMemberDetail ? (
                    <React.Fragment>
                      <div className="builder-detail-grid">
                        <article className="action-row">
                          <strong>Profile position</strong>
                          <p>{builderMemberDetail.profile.primary_field || "Primary field not yet captured"}{builderMemberDetail.profile.current_title ? ` • ${builderMemberDetail.profile.current_title}` : ""}</p>
                          <span>{builderMemberDetail.profile.current_employer || "Employer not yet captured"}</span>
                        </article>
                        <article className="action-row">
                          <strong>Coverage</strong>
                          <p>{builderMemberDetail.criteria.filter((item) => item.evidence_count).length} criteria started</p>
                          <span>{builderMemberDetail.member.readiness_score}% readiness • {builderMemberDetail.tasks.filter((item) => item.status === "open").length} open tasks</span>
                        </article>
                        <article className="action-row">
                          <strong>Next move</strong>
                          <p>{builderMemberDetail.tasks.length ? builderMemberDetail.tasks[0].title : "Push the next opportunity or task."}</p>
                          <span>{builderMemberDetail.tasks.length ? (builderMemberDetail.tasks[0].due_date ? `Due ${builderMemberDetail.tasks[0].due_date}` : "No due date") : "Use Opportunities to issue the next step."}</span>
                        </article>
                      </div>
                      <BuilderWorkbenchPanel workbench={builderMemberDetail.builder_workbench} />
                    </React.Fragment>
                  ) : <p className="empty-state">Choose a member to review their current builder view.</p>}
                </section>
              </section>
            </React.Fragment>
          )}

            </React.Fragment>
          )}
          </section>
        </main>
        {assistantPanel}
        {supportPanel}
        {helpManualDialog}
      </React.Fragment>
    );
  }

  if (authMember.role === "attorney" || isLeaderAttorneyView) {
    const strengths = (builderMemberDetail?.criteria || []).filter((item) => item.evidence_count > 0);
    const gaps = (builderMemberDetail?.criteria || []).filter((item) => !item.evidence_count);
    const selectedMemberRequired = ["dossier", "petition", "batch", "evidence"].includes(portalSection) && !selectedBuilderMemberId;
    const statusEntries = Object.entries(attorneyCaseStatusSummary);
    return (
      <React.Fragment>
        <main className="shell attorney-shell">
          <aside className="sidebar attorney-sidebar">
          <PortalBrand onHome={goToPortalHome} label="Go to attorney home" />
          <div className="brand-sub">{isLeaderAttorneyView ? "Leader Acting As Attorney" : "Attorney Workspace"}</div>
          {isLeaderAttorneyView ? (
            <div className="side-card perspective-side-card">
              <strong>Assume Portal View</strong>
              <p>Stay in the leader account while reviewing the attorney workspace exactly as leadership needs to inspect it.</p>
              <LeaderPerspectiveSwitch value={leaderPerspective} onChange={setLeaderPerspectiveMode} />
            </div>
          ) : null}
          <SidebarNav
            items={[
              { value: "home", label: "Attorney Home" },
              { value: "dossier", label: "Member Dossier" },
              { value: "petition", label: "Petition Generator" },
              { value: "batch", label: "Batch Intake" },
              { value: "evidence", label: "Evidence Review" },
              { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}` },
            ]}
            value={portalSection}
            onChange={setPortalSection}
          />
          <div className="side-card">
            <strong>Welcome {authMember.display_name}</strong>
            <p>{isLeaderAttorneyView ? "Review the attorney workspace with leader-level visibility while keeping the legal workflow context intact." : "Move from portfolio triage to member-specific legal work without losing the case context that matters day to day."}</p>
          </div>
          <div className="side-card">
            <strong>At a glance</strong>
            <p>Total cases: {builderMembers.length}</p>
            <p>Selected member: {selectedAttorneyMember?.display_name || "Choose from caseboard"}</p>
            <p>Open attorney work: {builderMembers.reduce((sum, item) => sum + (item.open_task_count || 0), 0)}</p>
          </div>
          <span className="side-note">{isLeaderAttorneyView ? "Leader operating in attorney visibility mode" : "Attorney portal only"}</span>
        </aside>
        <section className="main attorney-main">
          <div className="topbar">
            <div className="topbar-copy">
              <span className="topbar-label">{isLeaderAttorneyView ? "Leader Portal • Attorney View" : "Attorney Portal"}</span>
              <div className="topbar-welcome">Welcome {authMember.display_name}.</div>
              <strong>Petition strategy with the full member picture in view.</strong>
            </div>
            <div className="member-menu-wrap">
              <button className="member-menu-trigger" type="button" onClick={() => setMemberMenuOpen((current) => !current)}>
                <span className="member-avatar">{authMember.display_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</span>
                <span className="member-trigger-copy">
                  <strong>{authMember.display_name}</strong>
                  <span>{authMember.email}</span>
                  <LastLoginStamp user={authMember} />
                </span>
              </button>
              {memberMenuOpen ? (
                <div className="member-menu">
                  <button type="button" onClick={() => { setPasswordDialogOpen(true); setMemberMenuOpen(false); }}>Change Password</button>
                  <button type="button" onClick={openHelpManual}>Help Manual</button>
                  <button type="button" onClick={handleLogout}>Logout</button>
                </div>
              ) : null}
            </div>
          </div>

          {message ? <div className={`banner ${message.type}`}>{message.text}</div> : null}
          {passwordDialogOpen ? (
            <div className="modal-backdrop" onClick={() => setPasswordDialogOpen(false)}>
              <section className="modal-card" onClick={(event) => event.stopPropagation()}>
                <div className="panel-header">
                  <div><div className="section-kicker">Account</div><h3 className="section-title">Change Password</h3></div>
                  <button className="ghost compact-btn" type="button" onClick={() => setPasswordDialogOpen(false)}>Close</button>
                </div>
                <form className="stacked-form" onSubmit={handlePasswordChange}>
                  <label>Current Password<input type="password" value={passwordForm.current_password} onChange={(event) => setPasswordForm((current) => ({ ...current, current_password: event.target.value }))} /></label>
                  <label>New Password<input type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm((current) => ({ ...current, new_password: event.target.value }))} /></label>
                  <label>Confirm New Password<input type="password" value={passwordForm.confirm_password} onChange={(event) => setPasswordForm((current) => ({ ...current, confirm_password: event.target.value }))} /></label>
                  <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={passwordBusy}>{passwordBusy ? "Updating..." : "Update Password"}</button></div>
                </form>
              </section>
            </div>
          ) : null}

          {portalHydrating ? (
            <PortalHydrationNotice
              title="Loading attorney workspace"
              detail="Caseboard, criteria, selected member detail, and evidence are refreshing while the attorney shell stays usable."
            />
          ) : selectedMemberHydrating ? (
            <PortalHydrationNotice
              title="Refreshing selected case"
              detail="The member-specific legal workspace will update as soon as the selected case data returns."
            />
          ) : null}

          {portalSection === "messages" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Messages</p>
                <h1>Attorney communications.</h1>
                <p>Review threaded conversations separately from the member dossier so petition work stays focused.</p>
              </header>
              {messagePanel}
            </React.Fragment>
          ) : portalSection === "home" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Attorney Caseboard</p>
                <h1>Portfolio first, casework second.</h1>
                <p>Start with the full docket, spot which cases are in intake, active build, or deeper review, then open one member and move straight into petition, evidence, or batch intake work.</p>
                <div className="hero-chips">
                  <span className="hero-chip">Assigned case portfolio</span>
                  <span className="hero-chip">Status-based triage</span>
                  <span className="hero-chip">One-click deep dives</span>
                </div>
              </header>

              <section className="metrics-grid">
                <MetricCard label="Total Cases" value={builderMembers.length} />
                <MetricCard label="Open Tasks" value={builderMembers.reduce((sum, item) => sum + (item.open_task_count || 0), 0)} />
                <MetricCard label="Evidence Items" value={builderMembers.reduce((sum, item) => sum + (item.evidence_count || 0), 0)} />
                <MetricCard label="Avg Readiness" value={`${builderMembers.length ? Math.round(builderMembers.reduce((sum, item) => sum + (item.readiness_score || 0), 0) / builderMembers.length) : 0}%`} />
              </section>

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">Start Here</div>
                    <h3 className="section-title">Select a member to work</h3>
                    <p className="section-intro">Pick the member first, then move into dossier review, petition drafting, evidence review, or batch intake with the right case in focus.</p>
                  </div>
                </div>
                <MemberSearchBox
                  value={memberSearchQuery}
                  onChange={setMemberSearchQuery}
                  total={builderMembers.length}
                  visible={filteredBuilderMembers.length}
                  label="Search cases"
                />
                <div className="builder-member-list attorney-member-list">
                  {filteredBuilderMembers.map((item) => (
                    <button
                      key={item.client_id}
                      type="button"
                      className={`builder-member-card attorney-member-card ${selectedBuilderMemberId === item.client_id ? "active" : ""}`}
                      onClick={() => setSelectedBuilderMemberId(item.client_id)}
                    >
                      <strong>{item.display_name}</strong>
                      <span>{caseStatusLabel(item.status)} • {item.primary_field || "Profile in progress"}</span>
                      <span>{item.current_title || "Title pending"}{item.current_employer ? ` • ${item.current_employer}` : ""}</span>
                      <span>Readiness {item.readiness_score}% • {item.evidence_count} evidence • {item.open_task_count} open tasks</span>
                      <span className={`status-pill ${item.momentum === "Strong" ? "completed" : item.momentum === "Needs focus" ? "blocked" : "in_progress"}`}>{item.momentum}</span>
                    </button>
                  ))}
                  {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                </div>
              </section>

              <section className="builder-layout" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Selected Case</div>
                  <h3 className="section-title">{selectedAttorneyMember?.display_name || "Select a member to begin"}</h3>
                  <p className="section-intro">This summary is your jump point into dossier, evidence review, petition drafting, and batch intake.</p>
                  {selectedAttorneyMember ? (
                    <div className="builder-detail-grid">
                      <article className="action-row">
                        <strong>Case stage</strong>
                        <p>{caseStatusLabel(selectedAttorneyMember.status)}</p>
                        <span>Readiness {selectedAttorneyMember.readiness_score}%</span>
                      </article>
                      <article className="action-row">
                        <strong>Current profile</strong>
                        <p>{selectedAttorneyMember.primary_field || "Field not yet captured"}{selectedAttorneyMember.current_title ? ` • ${selectedAttorneyMember.current_title}` : ""}</p>
                        <span>{selectedAttorneyMember.current_employer || "Employer not yet captured"}</span>
                      </article>
                      <article className="action-row">
                        <strong>Case volume</strong>
                        <p>{selectedAttorneyMember.evidence_count} evidence items • {selectedAttorneyMember.open_task_count} open tasks</p>
                        <span>{selectedAttorneyMember.criteria_started || 0} criteria started</span>
                      </article>
                    </div>
                  ) : (
                    <p className="empty-state">Select a member above to open their active legal workspace.</p>
                  )}
                </section>

                <section className="panel">
                  <div className="section-kicker">Case Statuses</div>
                  <h3 className="section-title">Portfolio by case stage</h3>
                  <p className="section-intro">Use case stage to decide where legal attention is needed today.</p>
                  <div className="task-mini-list">
                    {statusEntries.map(([status, count]) => (
                      <article key={status} className="task-mini-item">
                        <strong>{status}</strong>
                        <p>{count} case(s)</p>
                      </article>
                    ))}
                  </div>
                </section>
              </section>
              {builderMemberDetail ? (
                <LegalWorkbenchPanel
                  workbench={builderMemberDetail.legal_workbench}
                  onGeneratePetition={() => setPortalSection("petition")}
                />
              ) : null}
            </React.Fragment>
          ) : selectedMemberRequired ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Select A Member</p>
                <h1>Choose the case before opening the workspace.</h1>
                <p>Petition drafting, evidence review, dossier analysis, and batch intake are all member-specific. Pick a member from Attorney Home to continue.</p>
              </header>
              <section className="panel" style={{ marginTop: "18px" }}>
                <MemberSearchBox
                  value={memberSearchQuery}
                  onChange={setMemberSearchQuery}
                  total={builderMembers.length}
                  visible={filteredBuilderMembers.length}
                  label="Search cases"
                />
                <div className="builder-member-list attorney-member-list">
                  {filteredBuilderMembers.map((item) => (
                    <button
                      key={item.client_id}
                      type="button"
                      className={`builder-member-card attorney-member-card ${selectedBuilderMemberId === item.client_id ? "active" : ""}`}
                      onClick={() => { setSelectedBuilderMemberId(item.client_id); setPortalSection("home"); }}
                    >
                      <strong>{item.display_name}</strong>
                      <span>{caseStatusLabel(item.status)} • {item.primary_field || "Profile in progress"}</span>
                      <span>Readiness {item.readiness_score}% • {item.evidence_count} evidence • {item.open_task_count} open tasks</span>
                    </button>
                  ))}
                  {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                </div>
              </section>
            </React.Fragment>
          ) : portalSection === "dossier" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Member Dossier</p>
                <h1>{builderMemberDetail?.member?.display_name || "Member"} summary.</h1>
                <p>Review identity, professional positioning, and criterion-level strengths and gaps in one dedicated dossier page.</p>
              </header>

              <section className="builder-layout">
                <section className="panel">
                  <div className="section-kicker">Profile Summary</div>
                  <h3 className="section-title">Member Profile</h3>
                  <div className="builder-detail-grid">
                    <article className="action-row">
                      <strong>Identity</strong>
                      <p>{profile?.first_name} {profile?.last_name}</p>
                      <span>{profile?.email || "Email not yet captured"}</span>
                    </article>
                    <article className="action-row">
                      <strong>Current positioning</strong>
                      <p>{profile?.primary_field || "Primary field not yet captured"}{profile?.current_title ? ` • ${profile.current_title}` : ""}</p>
                      <span>{profile?.current_employer || "Employer not yet captured"}</span>
                    </article>
                    <article className="action-row">
                      <strong>Filing posture</strong>
                      <p>{profile?.target_filing_window || "Target filing window not yet defined"}</p>
                      <span>{profile?.proposed_final_merits_summary || "Final merits positioning not yet drafted"}</span>
                    </article>
                  </div>
                </section>

                <section className="panel">
                  <div className="section-kicker">Strengths And Gaps</div>
                  <h3 className="section-title">Criterion Review</h3>
                  <div className="task-mini-list">
                    <article className="task-mini-item">
                      <strong>Current strengths</strong>
                      <p>{strengths.length ? strengths.map((item) => `${item.name} (${item.evidence_count})`).join(" • ") : "No clear strengths surfaced yet."}</p>
                    </article>
                    <article className="task-mini-item">
                      <strong>Current gaps</strong>
                      <p>{gaps.length ? gaps.map((item) => item.name).join(" • ") : "No obvious criterion gaps."}</p>
                    </article>
                    <article className="task-mini-item">
                      <strong>Builder notes in motion</strong>
                      <p>{builderMemberDetail?.tasks?.length ? builderMemberDetail.tasks.map((item) => item.title).join(" • ") : "No builder tasks attached yet."}</p>
                    </article>
                  </div>
                </section>
              </section>
            </React.Fragment>
          ) : portalSection === "petition" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Petition Generator</p>
                <h1>{selectedAttorneyMember?.display_name || "Selected member"} petition strategy draft.</h1>
                <p>Generate a member-specific attorney draft using the selected case record, then move directly from risk review into legal follow-up.</p>
                <div className="hero-chips">
                  <span className="hero-chip">Full profile context</span>
                  <span className="hero-chip">Evidence + folders</span>
                  <span className="hero-chip">Tasks + planner history</span>
                </div>
              </header>

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">Attorney Draft</div>
                    <h3 className="section-title">Petition planning view</h3>
                    <p className="section-intro">Generate an attorney-facing draft from the current case record, then use it to guide legal review and follow-up with the member.</p>
                  </div>
                  <div className="form-actions">
                    <button className="primary compact-btn" type="button" onClick={() => loadAttorneyPetition(selectedBuilderMemberId)} disabled={petitionBusy}>
                      {petitionBusy ? "Generating..." : petitionDraft ? "Refresh Draft" : "Generate Draft"}
                    </button>
                  </div>
                </div>
                {petitionDraft ? (
                  <React.Fragment>
                    <div className="metrics-grid">
                      <MetricCard label="Readiness" value={`${petitionDraft.member?.readiness_score || 0}%`} />
                      <MetricCard label="Evidence Items" value={petitionDraft.snapshot?.evidence_count || 0} />
                      <MetricCard label="Criteria Started" value={petitionDraft.snapshot?.criteria_started || 0} />
                      <MetricCard label="Open Tasks" value={petitionDraft.snapshot?.open_tasks || 0} />
                    </div>

                    <LegalWorkbenchPanel workbench={petitionDraft.legal_workbench} />

                    <section className="petition-grid">
                      <article className="panel petition-panel">
                        <div className="section-kicker">Executive Summary</div>
                        <h3 className="section-title">Case positioning</h3>
                        <div className="action-row">
                          <strong>Executive summary</strong>
                          <p>{petitionDraft.executive_summary}</p>
                          <span>{petitionDraft.source === "openai" ? "AI generated from current case record" : "Fallback draft based on current structured data"}</span>
                        </div>
                        <div className="action-row">
                          <strong>Petition positioning</strong>
                          <p>{petitionDraft.petition_positioning}</p>
                        </div>
                        <div className="action-row">
                          <strong>Readiness assessment</strong>
                          <p>{petitionDraft.readiness_assessment}</p>
                        </div>
                      </article>

                      <article className="panel petition-panel">
                        <div className="section-kicker">Proposed Drafting Flow</div>
                        <h3 className="section-title">Suggested petition sections</h3>
                        <div className="task-mini-list">
                          {(petitionDraft.proposed_sections || []).map((item, index) => (
                            <article key={`sec_${index}`} className="task-mini-item">
                              <strong>{index + 1}. {item}</strong>
                            </article>
                          ))}
                        </div>
                      </article>
                    </section>

                    <section className="petition-grid">
                      <article className="panel petition-panel">
                        <div className="section-kicker">Strengths And Gaps</div>
                        <h3 className="section-title">What looks strong vs. what still needs work</h3>
                        <div className="task-mini-list">
                          <article className="task-mini-item">
                            <strong>Strengths</strong>
                            <ul className="petition-list">{(petitionDraft.strengths || []).map((item, index) => <li key={`str_${index}`}>{item}</li>)}</ul>
                          </article>
                          <article className="task-mini-item">
                            <strong>Gaps</strong>
                            <ul className="petition-list">{(petitionDraft.gaps || []).map((item, index) => <li key={`gap_${index}`}>{item}</li>)}</ul>
                          </article>
                        </div>
                      </article>

                      <article className="panel petition-panel">
                        <div className="section-kicker">Risks And Fixes</div>
                        <h3 className="section-title">Challenges and corrective actions</h3>
                        <div className="task-mini-list">
                          <article className="task-mini-item">
                            <strong>Risks / challenges</strong>
                            <ul className="petition-list">{(petitionDraft.risks || []).map((item, index) => <li key={`risk_${index}`}>{item}</li>)}</ul>
                          </article>
                          <article className="task-mini-item">
                            <strong>Recommended fixes</strong>
                            <ul className="petition-list">{(petitionDraft.recommended_fixes || []).map((item, index) => <li key={`fix_${index}`}>{item}</li>)}</ul>
                          </article>
                        </div>
                      </article>
                    </section>

                    <section className="petition-grid petition-grid-bottom">
                      <article className="panel petition-panel">
                        <div className="section-kicker">Dependencies</div>
                        <h3 className="section-title">What we still need</h3>
                        <div className="task-mini-list">
                          <article className="task-mini-item">
                            <strong>From member</strong>
                            <ul className="petition-list">{(petitionDraft.member_dependencies || []).map((item, index) => <li key={`mem_${index}`}>{item}</li>)}</ul>
                          </article>
                          <article className="task-mini-item">
                            <strong>From external parties</strong>
                            <ul className="petition-list">{(petitionDraft.external_dependencies || []).map((item, index) => <li key={`ext_${index}`}>{item}</li>)}</ul>
                          </article>
                        </div>
                      </article>

                      <article className="panel petition-panel">
                        <div className="section-kicker">Clarifications</div>
                        <h3 className="section-title">Questions for the member</h3>
                        <div className="task-mini-list">
                          {(petitionDraft.clarification_questions || []).map((item, index) => (
                            <article key={`q_${index}`} className="task-mini-item">
                              <strong>Question {index + 1}</strong>
                              <p>{item}</p>
                            </article>
                          ))}
                        </div>
                      </article>
                    </section>
                  </React.Fragment>
                ) : (
                  <p className="empty-state">Generate the petition draft to see AI-backed strengths, gaps, risks, dependencies, and attorney follow-up questions.</p>
                )}
              </section>
            </React.Fragment>
          ) : portalSection === "batch" ? (
            batchReviewPanel
          ) : portalSection === "evidence" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Evidence Review</p>
                <h1>{selectedAttorneyMember?.display_name || "Selected member"} evidence review.</h1>
                <p>Scan the selected member’s evidence only, with the latest files, summaries, and evidence types in one fast legal review surface.</p>
              </header>

              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Evidence File</div>
                <h3 className="section-title">Recent Evidence</h3>
                <p className="section-intro">Every item below belongs to the currently selected member and is grouped the same way the member workspace organizes evidence.</p>
                <EvidenceGroupPanel
                  evidence={evidenceItems}
                  criteriaByCode={criteriaByCode}
                  emptyText="No evidence files found for this member yet."
                />
              </section>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Attorney View</p>
                <h1>{builderMemberDetail?.member?.display_name || "Member"} dossier.</h1>
                <p>See the member profile, evidence coverage, strengths, and weaknesses in one place before petition drafting and merits strategy begin.</p>
              </header>

              <section className="metrics-grid">
                <MetricCard label="Readiness" value={`${builderMemberDetail?.member?.readiness_score || dashboard?.metrics?.readiness_score || 0}%`} />
                <MetricCard label="Strength areas" value={strengths.length} />
                <MetricCard label="Gap areas" value={gaps.length} />
                <MetricCard label="Open tasks" value={builderMemberDetail?.tasks?.filter((item) => item.status === "open").length || 0} />
              </section>

            </React.Fragment>
          )}
          </section>
        </main>
        {assistantPanel}
        {supportPanel}
        {helpManualDialog}
      </React.Fragment>
    );
  }

  if (authMember.role === "admin") {
    const stageCounts = builderMembers.reduce((acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    }, {});
    const ops = adminDashboard?.metrics || {};
    const costData = adminCosts || {};
    const awsCosts = costData.aws || {};
    const openaiCosts = costData.openai || {};
    const costTrendRows = [
      ...(awsCosts.trend || []).slice(-7).map((item) => ({ ...item, source: "AWS", currency: awsCosts.currency })),
      ...(openaiCosts.trend || []).slice(-7).map((item) => ({ ...item, source: "OpenAI", currency: openaiCosts.currency })),
    ];
    const debugMember = adminDashboard?.member_debug;
    const supportSummary = adminDashboard?.support_summary || {};
    const supportTickets = adminDashboard?.support_tickets || [];
    const portalHealth = adminDashboard?.portal_health || [];
    const responseTimes = adminDashboard?.response_times || [];
    return (
      <React.Fragment>
        <main className="shell admin-shell">
          <aside className="sidebar">
            <PortalBrand onHome={goToPortalHome} label="Go to admin home" />
            <div className="brand-sub">Admin Workspace</div>
            <SidebarNav
              items={[
                { value: "home", label: "Admin Home" },
                { value: "health", label: "System Health" },
                { value: "issues", label: `Issue Portal${adminIssueLog?.status_counts?.open ? ` (${adminIssueLog.status_counts.open})` : ""}` },
                { value: "costs", label: "Cost Explorer" },
                { value: "support", label: `Support Tickets${supportSummary.open_count ? ` (${supportSummary.open_count})` : ""}` },
                { value: "debug", label: "Debug Console" },
                { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}` },
              ]}
              value={portalSection}
              onChange={setPortalSection}
            />
            <div className="side-card">
              <strong>Welcome {authMember.display_name}</strong>
              <p>Monitor system health, case movement, portal usage, workload signals, and the support queue from one operations surface.</p>
            </div>
            <div className="side-card">
              <strong>At a glance</strong>
              <p>Members in system: {builderDashboard?.metrics?.member_count || 0}</p>
              <p>OpenAI calls: {ops.openai_endpoint_calls || 0}</p>
              <p>Operational errors: {ops.operational_errors || 0}</p>
              <p>Open support tickets: {supportSummary.open_count || 0}</p>
              <p>Open bugs: {adminIssueLog?.status_counts?.open || 0}</p>
            </div>
            <span className="side-note">Admin portal only</span>
          </aside>
          <section className="main admin-main">
            <div className="topbar">
              <div className="topbar-copy">
                <span className="topbar-label">Admin Portal</span>
                <div className="topbar-welcome">Welcome {authMember.display_name}.</div>
                <strong>Operational monitoring across clients, portals, workloads, and support issues.</strong>
              </div>
              <div className="member-menu-wrap">
                <button className="member-menu-trigger" type="button" onClick={() => setMemberMenuOpen((current) => !current)}>
                  <span className="member-avatar">{authMember.display_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</span>
                  <span className="member-trigger-copy">
                    <strong>{authMember.display_name}</strong>
                    <span>{authMember.email}</span>
                    <LastLoginStamp user={authMember} />
                  </span>
                </button>
                {memberMenuOpen ? (
                  <div className="member-menu">
                    <button type="button" onClick={() => { setPasswordDialogOpen(true); setMemberMenuOpen(false); }}>Change Password</button>
                    <button type="button" onClick={openHelpManual}>Help Manual</button>
                    <button type="button" onClick={handleLogout}>Logout</button>
                  </div>
                ) : null}
              </div>
            </div>

            {portalHydrating ? (
              <PortalHydrationNotice
                title="Loading admin workspace"
                detail="Operations metrics, support tickets, health data, and member diagnostics are refreshing while the admin shell stays available."
              />
            ) : null}

            {portalSection === "messages" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Messages</p>
                  <h1>Operations communications.</h1>
                  <p>Keep all inbound and outbound threads in one dedicated place so the operational dashboard stays focused on health and debugging.</p>
                </header>
                {messagePanel}
              </React.Fragment>
            ) : portalSection === "health" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">System Health</p>
                  <h1>Platform health, easy to scan.</h1>
                  <p>See every portal, integration, and response-time signal in one compact operational view.</p>
                </header>

                <section className="panel admin-health-panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Platform Health</div>
                      <h3 className="section-title">Portals and integrations</h3>
                    </div>
                    <span className="mini-note">Live operations payload</span>
                  </div>
                  <div className="admin-health-strip">
                    {portalHealth.map((item) => (
                      <article key={item.name} className={`admin-health-chip ${healthStatusClass(item.status)}`} title={item.detail}>
                        <span className="admin-health-icon">{healthIcon(item.name)}</span>
                        <span className="admin-health-copy">
                          <strong>{item.name}</strong>
                          <small>{item.status}</small>
                        </span>
                      </article>
                    ))}
                  </div>
                </section>

                <section className="panel admin-response-panel" style={{ marginTop: "18px" }}>
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Response Times</div>
                      <h3 className="section-title">Realtime average by tech stack</h3>
                    </div>
                    <span className="mini-note">Last 30 minutes</span>
                  </div>
                  <div className="response-time-table">
                    <div className="response-time-head">
                      <span>Stack</span>
                      <span>Layer</span>
                      <span>Avg</span>
                      <span>Trend</span>
                      <span>Status</span>
                    </div>
                    {responseTimes.length ? responseTimes.map((item) => (
                      <article key={item.name} className="response-time-row">
                        <div className="response-stack-name">
                          <span className="admin-health-icon">{healthIcon(item.name)}</span>
                          <strong>{item.name}</strong>
                        </div>
                        <span>{item.layer}</span>
                        <strong>{formatResponseMs(item.avg_ms)}</strong>
                        <ResponseSparkline points={item.trend || []} />
                        <span className={`status-pill ${healthStatusClass(item.status)}`}>{item.status}</span>
                      </article>
                    )) : <p className="empty-state">No response-time telemetry available yet.</p>}
                  </div>
                </section>
              </React.Fragment>
            ) : portalSection === "issues" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Issue Portal</p>
                  <h1>Product suite bugs, centralized.</h1>
                  <p>Track every bug with a bug ID, portal, section, priority, status, dates, and an AWS mirror so the team can diagnose and close issues without losing the thread.</p>
                </header>
                <IssueLogPanel
                  backlog={adminIssueLog}
                  form={issueLogForm}
                  busy={issueLogBusy}
                  onFormChange={(field, value) => setIssueLogForm((current) => ({ ...current, [field]: value }))}
                  onSubmit={submitIssueLog}
                  onUpdate={updateIssueLog}
                  onRemove={removeIssueLog}
                />
              </React.Fragment>
            ) : portalSection === "costs" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Cost Explorer</p>
                  <h1>Billing visibility for planning.</h1>
                  <p>Refresh AWS Cloud and OpenAI cost data on demand, keep the latest refresh timestamp visible, and compare actuals against projections for daily, monthly, and yearly planning.</p>
                </header>

                <section className="panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Refresh Controls</div>
                      <h3 className="section-title">Live cost sync</h3>
                      <p className="section-intro">{costData.detail || "Use Refresh to pull the latest cost data into the Admin Portal."}</p>
                    </div>
                    <div className="cost-toolbar">
                      <span className="mini-note">Last refreshed: {formatDateTime(costData.refreshed_at)}</span>
                      <button className="ghost compact-btn" type="button" onClick={refreshAdminCosts} disabled={adminCostBusy}>
                        {adminCostBusy ? "Refreshing..." : "Refresh"}
                      </button>
                    </div>
                  </div>
                </section>

                <section className="cost-explorer-grid">
                  <section className="panel cost-ledger-panel">
                    <div className="cost-section-head">
                      <div>
                        <div className="section-kicker">AWS Cloud</div>
                        <h3 className="section-title">Actuals vs projected</h3>
                      </div>
                      <span className={`status-pill ${healthStatusClass(awsCosts.status)}`}>{awsCosts.status || "unavailable"}</span>
                    </div>
                    <p className="section-intro">{awsCosts.detail || "AWS cost data is not available yet."}</p>
                    <div className="cost-ledger-table">
                      <div className="cost-ledger-row cost-ledger-head">
                        <span>Period</span>
                        <span>Actual</span>
                        <span>Projected</span>
                        <span>Basis</span>
                      </div>
                      {(awsCosts.recurring || []).length ? awsCosts.recurring.map((item) => (
                        <div key={item.period} className="cost-ledger-row">
                          <strong>{item.period}</strong>
                          <span>{formatCostAmount(item.actual, awsCosts.currency)}</span>
                          <span>{formatCostAmount(item.projected, awsCosts.currency)}</span>
                          <small>{item.basis}</small>
                        </div>
                      )) : (
                        <div className="cost-ledger-row cost-ledger-empty">
                          <span>No AWS cost data yet. Refresh after Cost Explorer credentials are available.</span>
                        </div>
                      )}
                    </div>
                    <p className="cost-source-note">{awsCosts.source || "AWS Cost Explorer"} • {awsCosts.metric || "UnblendedCost"} • {awsCosts.precision_note || "Sub-cent amounts are preserved."}</p>
                  </section>

                  <section className="panel cost-ledger-panel">
                    <div className="cost-section-head">
                      <div>
                        <div className="section-kicker">AWS Breakdown</div>
                        <h3 className="section-title">Current month by service</h3>
                      </div>
                    </div>
                    <p className="section-intro">Service-level month-to-date actuals from AWS Cost Explorer.</p>
                    <div className="cost-service-table">
                      <div className="cost-service-row cost-ledger-head">
                        <span>Service</span>
                        <span>MTD actual</span>
                      </div>
                      {(awsCosts.services || []).length ? awsCosts.services.map((item) => (
                        <div key={item.name} className="cost-service-row">
                          <strong>{item.name}</strong>
                          <span>{formatCostAmount(item.amount, awsCosts.currency)}</span>
                        </div>
                      )) : (
                        <div className="cost-service-row cost-ledger-empty">
                          <span>No AWS service breakdown available yet.</span>
                        </div>
                      )}
                    </div>
                  </section>
                </section>

                <section className="cost-explorer-grid">
                  <section className="panel cost-ledger-panel">
                    <div className="cost-section-head">
                      <div>
                        <div className="section-kicker">OpenAI Billing</div>
                        <h3 className="section-title">Actuals vs projected</h3>
                      </div>
                      <span className={`status-pill ${healthStatusClass(openaiCosts.status)}`}>{openaiCosts.status || "unavailable"}</span>
                    </div>
                    <p className="section-intro">{openaiCosts.detail || "OpenAI billing data is not available yet."}</p>
                    <div className="cost-ledger-table">
                      <div className="cost-ledger-row cost-ledger-head">
                        <span>Period</span>
                        <span>Actual</span>
                        <span>Projected</span>
                        <span>Basis</span>
                      </div>
                      {(openaiCosts.recurring || []).length ? openaiCosts.recurring.map((item) => (
                        <div key={item.period} className="cost-ledger-row">
                          <strong>{item.period}</strong>
                          <span>{formatCostAmount(item.actual, openaiCosts.currency)}</span>
                          <span>{formatCostAmount(item.projected, openaiCosts.currency)}</span>
                          <small>{item.basis}</small>
                        </div>
                      )) : (
                        <div className="cost-ledger-row cost-ledger-empty">
                          <span>Actual OpenAI billing is unavailable until {openaiCosts.required_secret || "OPENAI_ADMIN_API_KEY"} is configured.</span>
                        </div>
                      )}
                    </div>
                    <p className="cost-source-note">Usage source: {openaiCosts.usage_source || "Portal operational audit log"}</p>
                  </section>

                  <section className="panel cost-ledger-panel">
                    <div className="cost-section-head">
                      <div>
                        <div className="section-kicker">OpenAI Usage</div>
                        <h3 className="section-title">AI calls by portal</h3>
                      </div>
                    </div>
                    <div className="cost-usage-strip">
                      <span><strong>{openaiCosts.call_totals?.total_calls || 0}</strong> Total</span>
                      <span><strong>{openaiCosts.call_totals?.openai_calls || 0}</strong> OpenAI</span>
                      <span><strong>{openaiCosts.call_totals?.fallback_calls || 0}</strong> Fallback</span>
                      <span><strong>{openaiCosts.call_totals?.failed_calls || 0}</strong> Failed</span>
                    </div>
                    <div className="cost-usage-table">
                      <div className="cost-usage-row cost-ledger-head">
                        <span>Portal</span>
                        <span>Function</span>
                        <span>Total</span>
                        <span>OpenAI</span>
                        <span>Fallback</span>
                        <span>Failed</span>
                      </div>
                      {(openaiCosts.call_breakdown || []).length ? openaiCosts.call_breakdown.map((item) => (
                        <div key={`${item.portal}_${item.function}`} className="cost-usage-row">
                          <strong>{item.portal}</strong>
                          <span>{item.function}</span>
                          <span>{item.total_calls}</span>
                          <span>{item.openai_calls}</span>
                          <span>{item.fallback_calls}</span>
                          <span>{item.failed_calls}</span>
                        </div>
                      )) : (
                        <div className="cost-usage-row cost-ledger-empty">
                          <span>No tracked AI calls yet.</span>
                        </div>
                      )}
                    </div>
                  </section>
                </section>

                <section className="cost-explorer-grid">
                  <section className="panel cost-ledger-panel">
                    <div className="cost-section-head">
                      <div>
                        <div className="section-kicker">OpenAI Billing Breakdown</div>
                        <h3 className="section-title">Line items</h3>
                      </div>
                    </div>
                    <div className="cost-service-table">
                      <div className="cost-service-row cost-ledger-head">
                        <span>Line item</span>
                        <span>MTD actual</span>
                      </div>
                      {(openaiCosts.line_items || []).length ? openaiCosts.line_items.map((item) => (
                        <div key={item.name} className="cost-service-row">
                          <strong>{item.name}</strong>
                          <span>{formatCostAmount(item.amount, openaiCosts.currency)}</span>
                        </div>
                      )) : (
                        <div className="cost-service-row cost-ledger-empty">
                          <span>No OpenAI line-item breakdown available yet.</span>
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="panel cost-ledger-panel">
                    <div className="cost-section-head">
                      <div>
                        <div className="section-kicker">Recent Trend</div>
                        <h3 className="section-title">Daily cost trail</h3>
                      </div>
                    </div>
                    <div className="cost-service-table">
                      <div className="cost-service-row cost-ledger-head">
                        <span>Source and date</span>
                        <span>Amount</span>
                      </div>
                      {costTrendRows.length ? costTrendRows.map((item) => (
                        <div key={`${item.source}_${item.date}`} className="cost-service-row">
                          <strong>{item.source} • {item.date}</strong>
                          <span>{formatCostAmount(item.amount, item.currency)}</span>
                        </div>
                      )) : (
                        <div className="cost-service-row cost-ledger-empty">
                          <span>No daily trend points available yet.</span>
                        </div>
                      )}
                    </div>
                  </section>
                </section>
              </React.Fragment>
            ) : portalSection === "support" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Support Tickets</p>
                  <h1>Issue intake, triaged.</h1>
                  <p>Review user-reported technical issues with the first-pass assessment, likely root cause, and the next actions needed to verify or fix them.</p>
                </header>

                <section className="metrics-grid">
                  <MetricCard label="Open Tickets" value={supportSummary.open_count || 0} />
                  <MetricCard label="Last 24 Hours" value={supportSummary.created_last_day || 0} />
                  <MetricCard label="Likely Bugs" value={supportSummary.likely_bug_count || 0} />
                  <MetricCard label="Needs Verification" value={supportSummary.needs_verification_count || 0} />
                </section>

                <section className="panel support-queue-panel" style={{ marginTop: "18px" }}>
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Ticket Queue</div>
                      <h3 className="section-title">Recent support tickets</h3>
                    </div>
                    <span className="mini-note">{supportTickets.length} visible</span>
                  </div>
                  <div className="support-ticket-table">
                    <div className="support-ticket-head">
                      <span>Ticket</span>
                      <span>Category</span>
                      <span>Portal</span>
                      <span>Reporter</span>
                      <span>Triage</span>
                      <span>Priority</span>
                      <span>Created</span>
                      <span>Link</span>
                    </div>
                    {supportTickets.length ? supportTickets.map((ticket) => (
                      <article
                        key={ticket.id}
                        className={`support-ticket-row ${supportCategoryClass(ticket.category)}`}
                        title={`${ticket.admin_summary || ticket.short_description || ""}\nRoot cause: ${ticket.root_cause || "Needs review"}\nNext: ${(ticket.next_actions || []).join(" | ") || "Reproduce and inspect the matching flow."}`}
                      >
                        <div className="support-ticket-main">
                          <span className="support-ticket-icon">{ticket.is_blocking ? "!" : "#"}</span>
                          <span>
                            <strong>{ticket.ticket_number}</strong>
                            <small>{ticket.short_description}</small>
                          </span>
                        </div>
                        <span className="support-category-badge">{ticket.category?.replaceAll("_", " ") || "other"}</span>
                        <span>{ticket.portal}</span>
                        <span>{ticket.reporter_name}</span>
                        <span className={`status-pill ${ticket.behavior_assessment === "likely_bug" ? "blocked" : ticket.behavior_assessment === "expected_behavior" ? "planned" : "in_progress"}`}>{ticket.behavior_assessment?.replaceAll("_", " ") || "needs verification"}</span>
                        <span>{supportPriorityLabel(ticket.priority)}</span>
                        <span>{formatDateTime(ticket.created_at)}</span>
                        <span className="support-ticket-link">
                          {ticket.current_url ? <a href={ticket.current_url} target="_blank" rel="noreferrer">Open</a> : "Context"}
                        </span>
                      </article>
                    )) : <p className="empty-state">No support tickets submitted yet.</p>}
                  </div>
                </section>
              </React.Fragment>
            ) : portalSection === "debug" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Debug Console</p>
                  <h1>Operational issues, one workspace.</h1>
                  <p>Review recent failures and take the first recovery action for a member without crowding the main admin summary page.</p>
                </header>

                <section className="panel admin-table-panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Operational Errors</div>
                      <h3 className="section-title">Recent errors</h3>
                      <p className="section-intro">Recent failures across auth, AI processing, evidence workflows, and admin operations in a compact incident ledger.</p>
                    </div>
                    <span className="mini-note">{(adminDashboard?.recent_errors || []).length} visible</span>
                  </div>
                  <div className="debug-error-table">
                    <div className="debug-error-row debug-error-head"><span>Event</span><span>Portal</span><span>Endpoint</span><span>Status</span><span>Created</span><span>Message</span></div>
                    {(adminDashboard?.recent_errors || []).length ? (
                      adminDashboard.recent_errors.map((item) => (
                        <article key={item.id} className="debug-error-row">
                          <strong>{item.event_type}</strong>
                          <span>{item.portal || "system"}</span>
                          <span>{item.endpoint || "n/a"}</span>
                          <span className="status-pill blocked">{item.status || "error"}</span>
                          <span>{item.created_at}</span>
                          <small>{item.message || "No message captured."}</small>
                        </article>
                      ))
                    ) : (
                      <p className="empty-state">No recent operational errors.</p>
                    )}
                  </div>
                </section>

                <section className="panel admin-table-panel" style={{ marginTop: "18px" }}>
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Debug Console</div>
                      <h3 className="section-title">Member issue review</h3>
                      <p className="section-intro">Inspect a member issue quickly, see evidence/task/session counts, and take the first operational recovery action.</p>
                    </div>
                    {debugMember ? <button className="ghost compact-btn" type="button" onClick={() => resetMemberIssueSession(debugMember.member.client_id)}>Reset Session</button> : null}
                  </div>
                  {debugMember ? (
                    <div className="debug-member-table">
                      <div className="debug-member-row debug-member-head"><span>Member</span><span>Readiness</span><span>Evidence</span><span>Open tasks</span><span>Sessions</span><span>Recent errors</span><span>Recommended actions</span></div>
                      <article className="debug-member-row">
                        <strong>{debugMember.member.display_name}</strong>
                        <span>{debugMember.member.readiness_score}%</span>
                        <span>{debugMember.evidence_count}</span>
                        <span>{debugMember.open_tasks}</span>
                        <span className={`status-pill ${debugMember.active_sessions ? "planned" : "completed"}`}>{debugMember.active_sessions} active</span>
                        <small>{debugMember.recent_errors.length ? debugMember.recent_errors.map((item) => item.message || item.event_type).join(" | ") : "No recent member-specific errors captured."}</small>
                        <small>{debugMember.recommended_actions.join(" | ")}</small>
                      </article>
                    </div>
                  ) : (
                    <p className="empty-state">No member issue diagnostics available.</p>
                  )}
                </section>
              </React.Fragment>
            ) : (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Operational Monitoring</p>
                  <h1>Operations snapshot.</h1>
                  <p>Watch case movement, assignments, open work, platform stability, and support load so nothing gets stuck quietly in the background.</p>
                </header>

                <section className="metrics-grid">
                  <MetricCard label="OpenAI Calls" value={ops.openai_endpoint_calls || 0} />
                  <MetricCard label="Members Using AI" value={ops.members_using_ai_suggestions || 0} />
                  <MetricCard label="Active Members" value={ops.active_members || 0} />
                  <MetricCard label="Open Support" value={ops.open_support_tickets || 0} />
                </section>

                <AdminProductOpsPanel dashboard={adminDashboard} />

                <section className="builder-layout" style={{ marginTop: "18px" }}>
                  <section className="panel">
                    <div className="section-kicker">Recent Tickets</div>
                    <h3 className="section-title">Support queue snapshot</h3>
                    <p className="section-intro">Fresh issues reported from the live portals, with the initial admin summary already attached.</p>
                    <div className="task-mini-list">
                      {supportTickets.length ? supportTickets.slice(0, 4).map((ticket) => (
                        <article key={ticket.id} className="task-mini-item">
                          <strong>{ticket.ticket_number}</strong>
                          <p>{ticket.admin_summary}</p>
                          <div className="task-mini-meta">
                            <span>{ticket.reporter_name}</span>
                            <span>{ticket.portal}</span>
                            <span>{ticket.behavior_assessment?.replaceAll("_", " ") || "needs verification"}</span>
                          </div>
                        </article>
                      )) : <p className="empty-state">No support tickets yet.</p>}
                    </div>
                  </section>

                  <section className="panel">
                    <div className="section-kicker">Support Summary</div>
                    <h3 className="section-title">Root cause mix</h3>
                    <p className="section-intro">Keep the queue balanced between confirmed bugs and items that still need reproduction or product clarification.</p>
                    <div className="task-mini-list">
                      <article className="task-mini-item">
                        <strong>Open tickets</strong>
                        <p>{supportSummary.open_count || 0} support ticket(s) currently open in the system.</p>
                      </article>
                      <article className="task-mini-item">
                        <strong>Likely bugs</strong>
                        <p>{supportSummary.likely_bug_count || 0} ticket(s) are currently triaged as likely product issues.</p>
                      </article>
                      <article className="task-mini-item">
                        <strong>Needs verification</strong>
                        <p>{supportSummary.needs_verification_count || 0} ticket(s) still need direct reproduction or product review.</p>
                      </article>
                    </div>
                  </section>
                </section>
              </React.Fragment>
            )}
          </section>
        </main>
        {supportPanel}
        {helpManualDialog}
      </React.Fragment>
    );
  }

  return (
    <React.Fragment>
      <main className="shell">
        <aside className="sidebar">
        <PortalBrand onHome={goToPortalHome} label="Go to member home" />
        <div className="brand-sub">Member Workspace</div>
        <SidebarNav
          items={[
            { value: "home", label: "Member Home" },
            { value: "profile", label: "Profile" },
            { value: "planner", label: "Event Planner" },
            { value: "intake", label: "Evidence Intake" },
            { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}` },
          ]}
          value={memberSection}
          onChange={(next) => {
            if (next === "profile") {
              setView({ type: "profile", criterionCode: "" });
              setProfileTab("identity");
            } else if (next === "planner") {
              setView({ type: "planner", criterionCode: "" });
            } else if (next === "intake") {
              setView({ type: "intake", criterionCode: "" });
            } else if (next === "messages") {
              setView({ type: "messages", criterionCode: "" });
            } else {
              setView({ type: "home", criterionCode: "" });
            }
          }}
        />
        <div className="side-card">
          <strong>Welcome {memberDashboard.client.display_name}</strong>
          <p>Your portal is focused only on evidence intake, organization, and next steps.</p>
        </div>
        <div className="side-card">
          <strong>At a glance</strong>
          <p>Readiness: {memberDashboard.metrics.readiness_score}%</p>
          <p>Evidence items: {memberDashboard.metrics.evidence_count}</p>
          <p>Criteria started: {memberDashboard.metrics.criteria_started}</p>
        </div>
        {profile ? (
          <div className="side-card">
            <strong>Profile completion</strong>
            <p>{profile.completion_score}% complete</p>
            <p>{profile.profile_confirmed ? "Member-approved profile on file" : "Profile still needs member confirmation"}</p>
          </div>
        ) : null}
        <span className="side-note">Member portal only</span>
      </aside>

      <section className="main">
        <div className="topbar">
          <div className="topbar-copy">
            <span className="topbar-label">{view.type === "workspace" ? "Evidence Workspace" : view.type === "profile" ? "Member Profile" : view.type === "planner" ? "Event Planner" : view.type === "intake" ? "Evidence Intake" : view.type === "messages" ? "Messages" : "Member Home"}</span>
            <div className="topbar-welcome">Welcome {authMember.display_name}.</div>
            <strong>{view.type === "workspace" ? (selectedCriterion?.name || "Evidence By Criterion") : view.type === "profile" ? "Keep your attorney-ready profile current" : view.type === "planner" ? "Track upcoming opportunities and target dates in one clean planner" : view.type === "intake" ? "Upload and review evidence in its own focused intake page" : view.type === "messages" ? "Keep conversations in their own dedicated workspace" : "Evidence intake, planning, and organization"}</strong>
          </div>
          <div className="member-menu-wrap">
            <button className="member-menu-trigger" type="button" onClick={() => setMemberMenuOpen((current) => !current)}>
              <span className="member-avatar">{memberInitials}</span>
              <span className="member-trigger-copy">
                <strong>{authMember.display_name}</strong>
                <span>{authMember.email}</span>
                <LastLoginStamp user={authMember} />
              </span>
            </button>
            {memberMenuOpen ? (
              <div className="member-menu">
                <button type="button" onClick={() => { setView({ type: "profile", criterionCode: "" }); setProfileTab("identity"); setMemberMenuOpen(false); }}>Update Profile</button>
                <button type="button" onClick={() => { setView({ type: "planner", criterionCode: "" }); setMemberMenuOpen(false); }}>Event Planner</button>
                <button type="button" onClick={() => { setView({ type: "intake", criterionCode: "" }); setMemberMenuOpen(false); }}>Evidence Intake</button>
                <button type="button" onClick={() => { setView({ type: "messages", criterionCode: "" }); setMemberMenuOpen(false); }}>Messages</button>
                <button type="button" onClick={() => { setPasswordDialogOpen(true); setMemberMenuOpen(false); }}>Change Password</button>
                <button type="button" onClick={openHelpManual}>Help Manual</button>
                <button type="button" onClick={handleLogout}>Logout</button>
              </div>
            ) : null}
          </div>
        </div>

        {portalHydrating ? (
          <PortalHydrationNotice
            title="Loading member workspace"
            detail="Your member portal is open while evidence, planner, profile, and criteria data refresh in the background."
          />
        ) : null}

        {view.type === "home" ? (
          <React.Fragment>
            <header className="hero">
              <p className="eyebrow">Member Portal</p>
              <h1>Welcome {memberDashboard.client.display_name}.</h1>
              <p>Capture evidence, let AI help classify and summarize it, and keep every criterion organized for the next phase of your EB1A journey.</p>
              <div className="hero-chips">
                <span className="hero-chip">AI-assisted intake</span>
                <span className="hero-chip">Clean evidence organization</span>
                <span className="hero-chip">Action items with dates</span>
              </div>
            </header>

            <section className="metrics-grid">
              <MetricCard label="Readiness" value={`${memberDashboard.metrics.readiness_score}%`} />
              <MetricCard label="Evidence items" value={memberDashboard.metrics.evidence_count} />
              <MetricCard label="Open tasks" value={memberDashboard.metrics.open_tasks} />
              <MetricCard label="Criteria started" value={memberDashboard.metrics.criteria_started} />
            </section>

            <CaseCommandCenter
              data={memberDashboard.case_command_center}
              onOpenCriterion={(code) => setView({ type: "workspace", criterionCode: code })}
            />
          </React.Fragment>
        ) : null}

        {message ? <div className={`banner ${message.type}`}>{message.text}</div> : null}
        {passwordDialogOpen ? (
          <div className="modal-backdrop" onClick={() => setPasswordDialogOpen(false)}>
            <section className="modal-card" onClick={(event) => event.stopPropagation()}>
              <div className="panel-header">
                <div>
                  <div className="section-kicker">Account</div>
                  <h3 className="section-title">Change Password</h3>
                </div>
                <button className="ghost compact-btn" type="button" onClick={() => setPasswordDialogOpen(false)}>Close</button>
              </div>
              <form className="stacked-form" onSubmit={handlePasswordChange}>
                <label>
                  Current Password
                  <input type="password" value={passwordForm.current_password} onChange={(event) => setPasswordForm((current) => ({ ...current, current_password: event.target.value }))} />
                </label>
                <label>
                  New Password
                  <input type="password" value={passwordForm.new_password} onChange={(event) => setPasswordForm((current) => ({ ...current, new_password: event.target.value }))} />
                </label>
                <label>
                  Confirm New Password
                  <input type="password" value={passwordForm.confirm_password} onChange={(event) => setPasswordForm((current) => ({ ...current, confirm_password: event.target.value }))} />
                </label>
                <div className="form-actions">
                  <button className="primary compact-btn" type="submit" disabled={passwordBusy}>{passwordBusy ? "Updating..." : "Update Password"}</button>
                </div>
              </form>
            </section>
          </div>
        ) : null}

        {view.type === "home" ? (
          <React.Fragment>
            <section className="criteria-panel">
              <div className="section-kicker">Evidence Map</div>
              <h3 className="section-title">Evidence By Criterion</h3>
              <p className="section-intro">Open a category to organize files, review summaries, search folders, and keep evidence easy to retrieve.</p>
              <div className="criteria-grid">
                {memberDashboard.criteria.map((criterion) => <CriterionCard key={criterion.code} item={criterion} onOpen={(code) => setView({ type: "workspace", criterionCode: code })} />)}
              </div>
            </section>
          </React.Fragment>
        ) : view.type === "planner" ? (
          <section className="planner-panel">
            <div className="panel-header planner-header">
              <div>
                <div className="section-kicker">Planner</div>
                <h3 className="section-title">Event Planner</h3>
                <p className="section-intro">Track future events, invitations, and activities you want to turn into evidence later. Add a row, choose the category it supports, and remove anything you no longer need.</p>
              </div>
              <button className="primary compact-btn planner-add-btn" type="button" onClick={addPlannerRow}>+</button>
            </div>
            <div className="event-planner-tips">
              <span className="document-type-chip">Example: IEEE reviewer invitation for Judging</span>
              <span className="document-type-chip">Example: Conference speaker session for Leading or Critical Role</span>
              <span className="document-type-chip">Example: Award nomination follow-up for Awards and Prizes</span>
            </div>
            <div className="event-planner-list">
              <div className="event-planner-head">
                <span>Event or activity</span>
                <span>Organization</span>
                <span>Category</span>
                <span>Target date</span>
                <span>Status</span>
                <span>Notes</span>
                <span>Actions</span>
              </div>
              {plannerRows.length ? (
                plannerRows.map((row) => (
                  <div key={row.id} className="event-row">
                    <input value={row.member_role} onChange={(event) => setPlannerRowField(row.id, "member_role", event.target.value)} placeholder="Reviewer invitation, speaking panel, award submission" />
                    <input value={row.issued_by} onChange={(event) => setPlannerRowField(row.id, "issued_by", event.target.value)} placeholder="IEEE, conference, journal, university" />
                    <select value={row.criterion_code} onChange={(event) => setPlannerRowField(row.id, "criterion_code", event.target.value)}>
                      <option value="">Choose category</option>
                      {memberDashboard.criteria.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
                    </select>
                    <input type="date" value={row.planned_completion_date || ""} onChange={(event) => setPlannerRowField(row.id, "planned_completion_date", event.target.value)} />
                    <select value={row.status || "planned"} onChange={(event) => setPlannerRowField(row.id, "status", event.target.value)}>
                      {PLANNER_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                    <input value={row.comments || ""} onChange={(event) => setPlannerRowField(row.id, "comments", event.target.value)} placeholder="What to remember or collect" />
                    <div className="event-row-actions">
                      <button className="ghost compact-btn" type="button" disabled={plannerBusy && plannerSavingId === row.id} onClick={() => savePlannerRow(row)}>
                        {plannerBusy && plannerSavingId === row.id ? "Saving..." : "Save"}
                      </button>
                      <button className="danger compact-btn" type="button" onClick={() => handleDeletePlanner(row.id)}>Remove</button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="empty-state">No events planned yet. Use the + button to add one.</p>
              )}
            </div>
          </section>
        ) : view.type === "intake" ? (
          <section className="intake-card">
              <div className="section-kicker">Evidence Intake</div>
              <h3 className="section-title intake-title">Evidence Intake Review</h3>
              <p className="section-intro intake-intro">Add a short note, upload the document, and let the portal guide the next step without making the process feel heavy.</p>
              <span className="soft-badge">Review before saving</span>
              <p className="intake-helper">Choose the faster AI route or place the evidence yourself.</p>

              <div className="route-toggle" role="tablist" aria-label="Evidence route">
                <button type="button" className={routeMode === "ai" ? "active" : ""} onClick={() => { setRouteMode("ai"); setDraft(null); setConsent(false); }}>
                  Use AI suggestion
                </button>
                <button type="button" className={routeMode === "manual" ? "active" : ""} onClick={() => { setRouteMode("manual"); setDraft(null); setConsent(false); }}>
                  Choose category myself
                </button>
              </div>

              <form className="intake-form" onSubmit={handleAnalyzeOrSave}>
                <label>
                  Evidence note
                  <textarea value={memberContext} onChange={(event) => setMemberContext(event.target.value)} placeholder="Example: This is my IEEE reviewer invitation showing I judged work in my field." />
                </label>
                <label className="file-picker">
                  File
                  <input id="member-file" type="file" onChange={(event) => setSelectedFile(event.target.files?.[0] || null)} />
                </label>
                {routeMode === "manual" ? (
                  <React.Fragment>
                    <label>
                      Category
                      <select value={manualCategory} onChange={(event) => setManualCategory(event.target.value)}>
                        {memberDashboard.criteria.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
                      </select>
                    </label>
                    <label>
                      Evidence Type
                      <select value={manualDocumentType} onChange={(event) => setManualDocumentType(event.target.value)}>
                        {DOCUMENT_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    </label>
                    <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={uploadBusy}>{uploadBusy ? "Saving..." : "Save Evidence"}</button></div>
                  </React.Fragment>
                ) : (
                  <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={uploadBusy}>{uploadBusy ? "Reviewing..." : "Review Evidence"}</button></div>
                )}
              </form>

              {draft && routeMode === "ai" ? (
                <section className="draft-card">
                  <h3>Review Draft</h3>
                  <dl>
                    <div><dt>Suggested category</dt><dd>{criteriaByCode[draft.criterion_code]?.name || draft.criterion_code}</dd></div>
                    <div><dt>Suggested evidence type</dt><dd>{draft.document_type || "Other"}</dd></div>
                    <div><dt>Suggested title</dt><dd>{draft.title}</dd></div>
                    <div><dt>Summary</dt><dd>{draft.ai_description}</dd></div>
                    <div><dt>Confidence</dt><dd>{draft.quality_score}%</dd></div>
                  </dl>
                  <div className="route-toggle" role="tablist" aria-label="Draft feedback">
                    <button type="button" className={aiFeedback === "accept" ? "active" : ""} onClick={() => setAiFeedback("accept")}>Accept suggestion</button>
                    <button type="button" className={aiFeedback === "reject" ? "active" : ""} onClick={() => setAiFeedback("reject")}>Reject suggestion</button>
                  </div>
                  {aiFeedback === "reject" ? (
                    <React.Fragment>
                      <label>
                        Choose category
                        <select value={overrideCategory} onChange={(event) => setOverrideCategory(event.target.value)}>
                          {memberDashboard.criteria.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
                        </select>
                      </label>
                      <label>
                        Choose evidence type
                        <select value={overrideDocumentType} onChange={(event) => setOverrideDocumentType(event.target.value)}>
                          {DOCUMENT_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </label>
                    </React.Fragment>
                  ) : null}
                  <label className="consent-line">
                    <input
                      type="checkbox"
                      checked={consent}
                      onChange={(event) => {
                        setConsent(event.target.checked);
                        if (event.target.checked) setDraftApprovalError("");
                      }}
                    />
                    <span>I approve this evidence draft and want to save it.</span>
                  </label>
                  {draftApprovalError ? <p className="inline-error">{draftApprovalError}</p> : null}
                  <div className="form-actions">
                    <button className="primary compact-btn" type="button" disabled={uploadBusy} onClick={() => handleSaveDraft("")}>{uploadBusy ? "Saving..." : "Save Evidence"}</button>
                    <button className="ghost compact-btn" type="button" onClick={() => setDraft(null)}>Start over</button>
                  </div>
                </section>
              ) : null}

              {duplicateState ? (
                <section className="duplicate-card">
                  <h3>Matching filename found</h3>
                  <p>A file named <strong>{duplicateState.duplicate.file_name}</strong> already exists in this category.</p>
                  <div className="form-actions">
                    <button className="primary compact-btn" type="button" onClick={() => handleDuplicate("replace")}>Replace original</button>
                    <button className="ghost compact-btn" type="button" onClick={() => handleDuplicate("copy")}>Keep another copy</button>
                  </div>
                </section>
              ) : null}
            </section>
        ) : view.type === "messages" ? (
          <section className="profile-panel">
            <div className="panel-header profile-header">
              <div>
                <div className="section-kicker">Messages</div>
                <h3 className="section-title">Member Conversations</h3>
                <p className="section-intro">Reach your assigned Profile Builder, Attorney, or Admin from one dedicated thread view instead of mixing messages into your working pages.</p>
              </div>
            </div>
            {messagePanel}
          </section>
        ) : view.type === "profile" ? (
          <section className="profile-panel">
            <div className="panel-header profile-header">
              <div>
                <div className="section-kicker">Member Profile</div>
                <h3 className="section-title">Profile Details For EB1A Planning</h3>
                <p className="section-intro">Complete your profile in sections so Ascend and the attorney team can understand your background, signals, and filing narrative without chasing missing context.</p>
              </div>
              <div className="profile-summary">
                <strong>{profile?.completion_score || 0}% complete</strong>
                <span>{profile?.profile_confirmed ? "Member-approved" : "Awaiting member confirmation"}</span>
              </div>
            </div>

            <div className="profile-tabs" role="tablist" aria-label="Member profile sections">
              <button type="button" className={profileTab === "identity" ? "active" : ""} onClick={() => setProfileTab("identity")}>Identity</button>
              <button type="button" className={profileTab === "professional" ? "active" : ""} onClick={() => setProfileTab("professional")}>Professional</button>
              <button type="button" className={profileTab === "credentials" ? "active" : ""} onClick={() => setProfileTab("credentials")}>Credentials & Links</button>
              <button type="button" className={profileTab === "narrative" ? "active" : ""} onClick={() => setProfileTab("narrative")}>Narrative</button>
              <button type="button" className={profileTab === "criteria" ? "active" : ""} onClick={() => setProfileTab("criteria")}>Criterion Highlights</button>
            </div>

            <form className="profile-form" onSubmit={handleProfileSubmit}>
              {profileTab === "identity" ? (
                <div className="profile-grid">
                  <label>
                    First Name *
                    <input value={profileForm.first_name} onChange={(event) => setProfileField("first_name", event.target.value)} required />
                  </label>
                  <label>
                    Last Name *
                    <input value={profileForm.last_name} onChange={(event) => setProfileField("last_name", event.target.value)} required />
                  </label>
                  <label>
                    Preferred Name
                    <input value={profileForm.preferred_name} onChange={(event) => setProfileField("preferred_name", event.target.value)} />
                  </label>
                  <label>
                    Email Address *
                    <input type="email" value={profileForm.email} onChange={(event) => setProfileField("email", event.target.value)} required />
                  </label>
                  <label>
                    Phone
                    <input value={profileForm.phone} onChange={(event) => setProfileField("phone", event.target.value)} />
                  </label>
                  <label>
                    Date of Birth
                    <input type="date" value={profileForm.date_of_birth} onChange={(event) => setProfileField("date_of_birth", event.target.value)} />
                  </label>
                  <label>
                    Country of Citizenship
                    <input value={profileForm.country_of_citizenship} onChange={(event) => setProfileField("country_of_citizenship", event.target.value)} />
                  </label>
                  <label>
                    Country of Residence
                    <input value={profileForm.country_of_residence} onChange={(event) => setProfileField("country_of_residence", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    City / State
                    <input value={profileForm.city_state} onChange={(event) => setProfileField("city_state", event.target.value)} />
                  </label>
                </div>
              ) : null}

              {profileTab === "professional" ? (
                <div className="profile-grid">
                  <label>
                    Current Title
                    <input value={profileForm.current_title} onChange={(event) => setProfileField("current_title", event.target.value)} />
                  </label>
                  <label>
                    Current Employer / Organization
                    <input value={profileForm.current_employer} onChange={(event) => setProfileField("current_employer", event.target.value)} />
                  </label>
                  <label>
                    Employer Type
                    <input value={profileForm.employer_type} onChange={(event) => setProfileField("employer_type", event.target.value)} />
                  </label>
                  <label>
                    Industry Domain
                    <select value={profileForm.industry_domain} onChange={(event) => setProfileField("industry_domain", event.target.value)}>
                      <option value="">Choose domain</option>
                      {DOMAIN_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                    </select>
                  </label>
                  <label>
                    Primary Field
                    <input value={profileForm.primary_field} onChange={(event) => setProfileField("primary_field", event.target.value)} />
                  </label>
                  <label>
                    Specialization
                    <input value={profileForm.specialization} onChange={(event) => setProfileField("specialization", event.target.value)} />
                  </label>
                  <label>
                    Years of Experience
                    <input value={profileForm.years_experience} onChange={(event) => setProfileField("years_experience", event.target.value)} />
                  </label>
                </div>
              ) : null}

              {profileTab === "credentials" ? (
                <div className="profile-grid">
                  <label>
                    Highest Degree
                    <input value={profileForm.highest_degree} onChange={(event) => setProfileField("highest_degree", event.target.value)} />
                  </label>
                  <label>
                    Degree Field
                    <input value={profileForm.degree_field} onChange={(event) => setProfileField("degree_field", event.target.value)} />
                  </label>
                  <label>
                    Institution
                    <input value={profileForm.institution} onChange={(event) => setProfileField("institution", event.target.value)} />
                  </label>
                  <label>
                    Graduation Year
                    <input value={profileForm.graduation_year} onChange={(event) => setProfileField("graduation_year", event.target.value)} />
                  </label>
                  <label>
                    LinkedIn URL
                    <input value={profileForm.linkedin_url} onChange={(event) => setProfileField("linkedin_url", event.target.value)} />
                  </label>
                  <label>
                    Personal Website
                    <input value={profileForm.personal_website} onChange={(event) => setProfileField("personal_website", event.target.value)} />
                  </label>
                  <label>
                    Google Scholar URL
                    <input value={profileForm.google_scholar_url} onChange={(event) => setProfileField("google_scholar_url", event.target.value)} />
                  </label>
                  <label>
                    ORCID ID
                    <input value={profileForm.orcid_id} onChange={(event) => setProfileField("orcid_id", event.target.value)} />
                  </label>
                </div>
              ) : null}

              {profileTab === "narrative" ? (
                <div className="profile-grid">
                  <label className="profile-span-2">
                    Professional Biography
                    <textarea value={profileForm.biography} onChange={(event) => setProfileField("biography", event.target.value)} placeholder="Short attorney-friendly overview of your background and why your work matters." />
                  </label>
                  <label className="profile-span-2">
                    Top Achievements
                    <textarea value={profileForm.top_achievements} onChange={(event) => setProfileField("top_achievements", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Proposed Final Merits Positioning
                    <textarea value={profileForm.proposed_final_merits_summary} onChange={(event) => setProfileField("proposed_final_merits_summary", event.target.value)} />
                  </label>
                  <label>
                    Target Filing Window
                    <input value={profileForm.target_filing_window} onChange={(event) => setProfileField("target_filing_window", event.target.value)} />
                  </label>
                </div>
              ) : null}

              {profileTab === "criteria" ? (
                <div className="profile-grid">
                  <label className="profile-span-2">
                    Awards and Prizes Summary
                    <textarea value={profileForm.awards_summary} onChange={(event) => setProfileField("awards_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Memberships Summary
                    <textarea value={profileForm.memberships_summary} onChange={(event) => setProfileField("memberships_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Publications Summary
                    <textarea value={profileForm.publications_summary} onChange={(event) => setProfileField("publications_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Judging Summary
                    <textarea value={profileForm.judging_summary} onChange={(event) => setProfileField("judging_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Original Contributions Summary
                    <textarea value={profileForm.original_contributions_summary} onChange={(event) => setProfileField("original_contributions_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Leading / Critical Roles Summary
                    <textarea value={profileForm.leading_roles_summary} onChange={(event) => setProfileField("leading_roles_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    Media / Published Material Summary
                    <textarea value={profileForm.media_summary} onChange={(event) => setProfileField("media_summary", event.target.value)} />
                  </label>
                  <label className="profile-span-2">
                    High Salary / Compensation Summary
                    <textarea value={profileForm.salary_summary} onChange={(event) => setProfileField("salary_summary", event.target.value)} />
                  </label>
                </div>
              ) : null}

              <label className="consent-line profile-confirm">
                <input type="checkbox" checked={Boolean(profileForm.profile_confirmed)} onChange={(event) => setProfileField("profile_confirmed", event.target.checked)} />
                <span>I confirm these profile details are accurate and can be used by Ascend and the attorney team.</span>
              </label>

              <div className="form-actions">
                <button className="primary compact-btn" type="submit" disabled={profileBusy || !profileForm.profile_confirmed}>
                  {profileBusy ? "Saving..." : "Save Profile"}
                </button>
                <button className="ghost compact-btn" type="button" onClick={() => setView({ type: "home", criterionCode: "" })}>Back to Home</button>
              </div>
            </form>
          </section>
        ) : (
          <section className="workspace-page">
            <div className="workspace-top">
              <div>
                <div className="section-kicker">Evidence Workspace</div>
                <h2>{selectedCriterion?.name || "Criterion workspace"}</h2>
                <p>Drag folders and files between columns to reorganize this criterion without leaving the page.</p>
              </div>
              <button className="ghost compact-btn" type="button" onClick={() => setView({ type: "home", criterionCode: "" })}>Back</button>
            </div>
            <div className="workspace-toolbar"><input className="search-input" value={workspaceQuery} onChange={(event) => setWorkspaceQuery(event.target.value)} placeholder={`Search folders and files in ${selectedCriterion?.name || "this criterion"}`} /></div>
            {workspace?.document_type_counts?.length ? (
              <div className="document-type-strip">
                {workspace.document_type_counts.map((item) => (
                  <span key={item.label} className="document-type-chip">{item.label} ({item.count})</span>
                ))}
              </div>
            ) : null}
            <div className="workspace-layout">
              <aside className="workspace-sidebar">
                <section className="panel">
                  <div className="panel-header"><h3>Folders</h3><span>{workspace?.folders?.length || 0}</span></div>
                  <p className="mini-note">Current location: {selectedFolderId ? (workspace?.folders.find((folder) => folder.id === selectedFolderId)?.path || "Root") : "Root"}</p>
                  <button className={`tree-item ${!selectedFolderId ? "active" : ""}`} type="button" onClick={() => setSelectedFolderId("")}><span className="folder-dot root" />Root</button>
                  {(workspace?.folders || []).map((folder) => <button key={folder.id} className={`tree-item ${selectedFolderId === folder.id ? "active" : ""}`} type="button" onClick={() => setSelectedFolderId(folder.id)}><span className="folder-dot" style={{ background: folder.color }} />{folder.path}</button>)}
                </section>
                <section className="panel">
                  <div className="panel-header"><h3>Create Folder</h3><span>Color coded</span></div>
                  <form className="stacked-form" onSubmit={createFolder}>
                    <label>Name<input value={newFolderName} onChange={(event) => setNewFolderName(event.target.value)} /></label>
                    <label>Parent<select value={newFolderParent} onChange={(event) => setNewFolderParent(event.target.value)}>{folderOptions.map((option) => <option key={option.value || "root"} value={option.value}>{option.label}</option>)}</select></label>
                    <div><span className="field-label">Color</span><FolderColorPicker value={newFolderColor} onChange={setNewFolderColor} /></div>
                    <button className="primary compact-btn" type="submit">Create</button>
                  </form>
                </section>
                <section className="panel">
                  <div className="panel-header"><h3>Edit Folder</h3><span>{selectedFolderId ? "Selected" : "Pick a folder"}</span></div>
                  {selectedFolderId ? (
                    <form className="stacked-form" onSubmit={updateFolder}>
                      <label>Name<input value={folderForm.name} onChange={(event) => setFolderForm((current) => ({ ...current, name: event.target.value }))} /></label>
                      <div><span className="field-label">Color</span><FolderColorPicker value={folderForm.color} onChange={(value) => setFolderForm((current) => ({ ...current, color: value }))} /></div>
                      <div className="form-actions"><button className="primary compact-btn" type="submit">Save</button><button className="danger compact-btn" type="button" onClick={deleteFolder}>Delete</button></div>
                    </form>
                  ) : <p className="empty-state">Select a folder from the list to rename, recolor, or delete it.</p>}
                </section>
              </aside>
              <section className="workspace-board panelless">
                {workspaceBusy || !workspace ? <div className="loading">Loading workspace...</div> : (
                  <React.Fragment>
                    <p className="mini-note workspace-note">Each column is a folder location. Drag items across columns, and the portal will save the new structure.</p>
                    <div className="board-grid">
                      {board.map((container) => <WorkspaceColumn key={container.id || "root"} container={container} active={selectedFolderId === (container.id || "")} onDragStart={handleDragStart} onOpenFolder={(folderId) => setSelectedFolderId(folderId)} onDeleteFile={deleteFile} onDropItem={moveDraggedItem} />)}
                    </div>
                  </React.Fragment>
                )}
              </section>
            </div>
          </section>
        )}
        </section>
      </main>
      {supportPanel}
      {helpManualDialog}
    </React.Fragment>
  );
}

export default App;

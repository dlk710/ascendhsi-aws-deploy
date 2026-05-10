import React, { useEffect, useMemo, useRef, useState } from "react";

const API_URL = (window.ASCEND_RUNTIME_CONFIG?.apiUrl || window.ASCEND_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const LOGO_URL = "https://ascendhsi.com/wp-content/uploads/2024/08/Ascend-logo-no-bg.webp";
const AUTH_TOKEN_KEY = "ascend_member_token";
const AUTH_MEMBER_KEY = "ascend_member_info";
const ASSISTANT_SESSION_PREFIX = "ascend_assistant_thread_";
const PORTAL_OPTIONS = [
  { value: "member", label: "Member Portal", intro: "Sign in to manage evidence, keep your profile current, and stay aligned with Ascend on what comes next." },
  { value: "builder", label: "Profile Builder Portal", intro: "Sign in to manage assigned members, push profile-building opportunities, and keep progress moving across your roster." },
  { value: "leader", label: "Leader Portal", intro: "Sign in to review member progress across builders, rebalance assignments, and keep the broader operation moving." },
  { value: "attorney", label: "Attorney Portal", intro: "Sign in to review the full client profile, assess gaps and strengths, and prepare petition strategy with complete context." },
  { value: "admin", label: "Admin Portal", intro: "Sign in to monitor system health, operational flow, user activity, and case movement across the platform." },
];
const PORTAL_ROLE_VALUES = new Set(PORTAL_OPTIONS.map((item) => item.value));
const STAFF_ROLE_VALUES = new Set(["leader", "attorney", "admin"]);
const LOGIN_HELPERS_ENABLED = Boolean(window.ASCEND_RUNTIME_CONFIG?.showDemoLogins || window.ASCEND_SHOW_DEMO_LOGINS || ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname));
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
  member: [{ username: "vas@ascendhsi.com", email: "vas@ascendhsi.com", display_name: "Member" }],
  builder: [{ username: "builder@ascendhsi.com", email: "builder@ascendhsi.com", display_name: "Profile Builder" }],
  leader: PREVIEW_ACCOUNTS.leader,
  attorney: PREVIEW_ACCOUNTS.attorney,
  admin: PREVIEW_ACCOUNTS.admin,
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
const EMPLOYMENT_TYPE_OPTIONS = ["W-2 / Full-time", "Contract", "Part-time", "Consulting", "Volunteer", "Founder", "Other"];
const PROJECT_STATUS_OPTIONS = ["Active", "Completed", "Launched", "In planning", "On hold", "Other"];
const CONTRIBUTION_CATEGORY_OPTIONS = ["Work-related", "Research", "Grant work", "Entrepreneurship", "External collaboration", "Nonprofit", "Other"];
const MEMBER_VIEW_TYPES = new Set(["home", "workspace", "profile", "critical_roles", "original_contributions", "planner", "intake", "messages"]);
const MEMBER_PAGE_ALIASES = {
  "critical-role": "critical_roles",
  "critical-role-projects": "critical_roles",
  criticalRole: "critical_roles",
  "original-contributions": "original_contributions",
  "original-contribution": "original_contributions",
  originalContribution: "original_contributions",
};
const GUIDED_MEMBER_CRITERION_FORM_LABELS = {
  leading_critical_role: "Open Critical Role Form",
  original_contributions: "Open Original Contributions Form",
};
const BUILDER_SECTIONS = new Set(["home", "members", "opportunities", "messages"]);
const ATTORNEY_SECTIONS = new Set(["home", "dossier", "petition", "endeavor", "recommendations", "batch", "evidence", "messages"]);
const LEADER_EXEC_SECTIONS = new Set(["home", "invite", "members", "risks", "capacity", "timeline", "backlog", "oversight", "opportunities", "batch", "messages"]);
const ADMIN_SECTIONS = new Set(["home", "health", "costs", "support", "issues", "debug", "messages"]);
const LEADER_PERSPECTIVES = new Set(["leader", "builder", "attorney"]);
const PATH_PORTALS = new Set(["builder", "leader", "attorney", "admin"]);
const PORTAL_SECTION_ALIASES = {
  builder: { profiles: "members" },
};
const PORTAL_SECTION_PATHS = {
  builder: { members: "profiles" },
};
const SECTION_SUBTITLES = {
  builder: {
    home: "Assigned member momentum and profile-building actions",
    members: "Search members, review evidence, and update profile-building status",
    opportunities: "Create reusable EB1A opportunities and member tasks",
    messages: "Keep builder collaboration in one thread view",
  },
  attorney: {
    home: "Case queue, evidence readiness, and legal drafting priorities",
    dossier: "Review full member profile, criteria, and evidence exports",
    petition: "Generate petition strategy and drafting structure",
    endeavor: "Create compact endeavor letter drafts",
    recommendations: "Generate dependent and independent recommendation letters",
    batch: "Review batch evidence before committing",
    evidence: "Review uploaded evidence and attorney notes",
    messages: "Attorney collaboration and member follow-up",
  },
  leader: {
    home: "Executive-level movement across the EB1A operation",
    invite: "Create member invitations and optional assignments",
    members: "Review roster readiness and case progress",
    risks: "See late members and bottlenecks before they become filing delays",
    capacity: "Rebalance profile builder and attorney workloads",
    timeline: "Track realistic petition delivery timelines",
    backlog: "Capture product suite feature requests",
    oversight: "Assign members to profile builders and attorneys",
    opportunities: "Review strategic opportunities across members",
    batch: "Monitor batch intake and evidence routing",
    messages: "Lead team collaboration",
  },
  admin: {
    home: "Operational monitoring for the product suite",
    health: "Platform health, AWS stack, and response-time visibility",
    costs: "AWS and OpenAI cost tracking",
    support: "Support ticket triage",
    issues: "Excel-style issue portal and bug backlog",
    debug: "Debug console and activity logs",
    messages: "Admin communications",
  },
};
const ASSESSMENT_ROUTE_LABELS = {
  home: "Customer-facing free assessment and lead capture",
  questions: "Chat-style eligibility questions with saved answers",
  lead: "Collect email and optional phone before showing final result",
  results: "Show sample visa path result and next steps",
  leads: "Marketing lead table for future follow-up",
};

const ISSUE_STATUS_OPTIONS = [
  { value: "new", label: "New" },
  { value: "triaged", label: "Triaged" },
  { value: "in_progress", label: "In progress" },
  { value: "testing", label: "Testing" },
  { value: "fixed_local", label: "Fixed local" },
  { value: "fixed", label: "Fixed" },
  { value: "wont_do", label: "Won't do" },
  { value: "duplicate", label: "Duplicate" },
];

const LEGACY_ISSUE_STATUS_LABELS = {
  open: "New",
  blocked: "Testing",
  closed: "Fixed",
};
const SIDEBAR_WIDTH_KEY = "ascend_sidebar_width";
const SIDEBAR_MIN_WIDTH = 220;
const SIDEBAR_MAX_WIDTH = 420;
const DESKTOP_SIDEBAR_BREAKPOINT = 1100;

const FOLDER_COLORS = {
  Emerald: "#2f7d67",
  Amber: "#c6a15b",
  Coral: "#c8674a",
  Plum: "#7a5ea8",
  Slate: "#51606f",
};

const VISA_COMPASS_QUESTIONS = [
  {
    id: "goal",
    eyebrow: "Step 1",
    question: "What outcome are you trying to reach?",
    helper: "Choose the path closest to your current immigration goal.",
    type: "single",
    options: [
      { value: "green_card", label: "Permanent residence without relying on one employer", detail: "I want a green card strategy that can stand on my own profile.", scores: { eb1a: 4, niw: 3, o1: 1 }, reason: "You are prioritizing a self-petition style permanent path." },
      { value: "temporary_work", label: "Temporary work authorization as soon as possible", detail: "I need to work in the U.S. while a longer case develops.", scores: { o1: 4, h1b: 3, eb1a: 1 }, reason: "A temporary work visa may be useful while permanent strategy matures." },
      { value: "startup_transfer", label: "Build, invest, or transfer a business into the U.S.", detail: "My move is connected to a company, founder role, or investment plan.", scores: { l1: 4, e2: 4, o1: 2, niw: 1 }, reason: "Business ownership, transfer, or investment can point to founder/operator routes." },
      { value: "unsure", label: "I am not sure yet", detail: "I want Ascend to tell me which track looks most realistic.", scores: { eb1a: 1, niw: 1, o1: 1, h1b: 1 }, reason: "The tool will compare multiple paths from your profile signals." },
    ],
  },
  {
    id: "profile",
    eyebrow: "Step 2",
    question: "Which profile best describes you?",
    helper: "This helps weigh extraordinary ability, national interest, and employer-driven routes.",
    type: "single",
    options: [
      { value: "researcher", label: "Researcher, scientist, physician, or academic expert", detail: "Publications, citations, grants, patents, clinical impact, or peer review may matter.", scores: { eb1a: 3, niw: 4, o1: 2 }, reason: "Research and expert work can support both national interest and extraordinary ability." },
      { value: "tech_leader", label: "Technology, product, data, or engineering leader", detail: "Scale, critical systems, original products, and business impact can be central.", scores: { eb1a: 3, o1: 3, niw: 2, h1b: 1 }, reason: "High-impact technology work often maps to critical role and original contribution evidence." },
      { value: "founder_exec", label: "Founder, executive, investor, or business operator", detail: "Revenue, funding, job creation, press, market adoption, or leadership role may matter.", scores: { eb1a: 3, o1: 3, e2: 3, l1: 2, niw: 1 }, reason: "Founder and executive profiles can combine business impact with leadership evidence." },
      { value: "creator", label: "Artist, designer, media, sports, or creator profile", detail: "Awards, press, judging, commercial success, exhibitions, or audience reach may matter.", scores: { o1: 4, eb1a: 3 }, reason: "Creative recognition is often evaluated through sustained acclaim and public impact." },
      { value: "professional", label: "Professional specialist with strong employer support", detail: "A role, employer, degree, and specialty occupation may be the strongest starting point.", scores: { h1b: 4, niw: 1, o1: 1 }, reason: "Employer-backed routes may be more realistic if independent evidence is still developing." },
    ],
  },
  {
    id: "recognition",
    eyebrow: "Step 3",
    question: "Which recognition or evidence signals do you already have?",
    helper: "Select everything you can document. Ascend will later help convert these into evidence buckets.",
    type: "multi",
    options: [
      { value: "awards", label: "Major awards or competitive prizes", detail: "Awards from recognized institutions, competitions, or professional bodies.", scores: { eb1a: 3, o1: 3 }, reason: "Awards can demonstrate recognized achievement." },
      { value: "press", label: "Press, media, interviews, or public coverage", detail: "Articles, podcasts, broadcasts, profiles, or credible third-party mentions.", scores: { eb1a: 2, o1: 3 }, reason: "Published coverage can support public recognition." },
      { value: "publications", label: "Publications, citations, patents, or technical authorship", detail: "Scholarship, technical papers, patents, books, or widely referenced work.", scores: { eb1a: 3, niw: 3, o1: 1 }, reason: "Published work and citations can show contribution and expert standing." },
      { value: "judging", label: "Judging, peer review, selection panels, or advisory review", detail: "Reviewing others' work, judging competitions, peer review, grants, or panels.", scores: { eb1a: 2, o1: 2, niw: 1 }, reason: "Judging is a strong expert-recognition signal when well documented." },
      { value: "critical_role", label: "Leading or critical role at a distinguished organization", detail: "Important role in a notable company, institution, product, or initiative.", scores: { eb1a: 3, o1: 2, l1: 1 }, reason: "Critical role evidence can connect your work to distinguished organizations." },
      { value: "original_contribution", label: "Original contribution with measurable field or business value", detail: "A product, method, platform, research, or system others use or rely on.", scores: { eb1a: 3, niw: 2, o1: 2 }, reason: "Original contribution evidence can be central for EB-1A and NIW strategy." },
      { value: "high_salary", label: "High salary, equity, revenue, or commercial success", detail: "Compensation, funding, adoption, sales, or financial outcomes above peers.", scores: { eb1a: 2, o1: 2, e2: 1 }, reason: "Commercial success and compensation can show market recognition." },
      { value: "none_yet", label: "Not much yet", detail: "I need help identifying what evidence can be built or collected.", scores: { h1b: 2, niw: 1 }, reason: "If evidence is early, Ascend can help plan what to gather next." },
    ],
  },
  {
    id: "impact",
    eyebrow: "Step 4",
    question: "How broad is the impact of your work?",
    helper: "The strongest cases usually connect achievements to measurable outcomes.",
    type: "single",
    options: [
      { value: "field_level", label: "Field, industry, national, or global impact", detail: "Others outside my company use, cite, adopt, or recognize my work.", scores: { eb1a: 4, niw: 4, o1: 3 }, reason: "External impact is highly valuable for self-petition and extraordinary ability routes." },
      { value: "company_level", label: "Major company or product-level impact", detail: "My work drove revenue, scale, cost savings, reliability, users, or strategic outcomes.", scores: { eb1a: 3, o1: 2, l1: 2, h1b: 1 }, reason: "Company-level impact can support critical role and business value narratives." },
      { value: "team_level", label: "Important team-level impact", detail: "I can show strong internal contributions but limited external proof so far.", scores: { o1: 1, h1b: 2, niw: 1 }, reason: "This may need more external corroboration before an EB-1A strategy is strong." },
      { value: "early", label: "Still early or hard to quantify", detail: "I need help turning my work into evidence and measurable claims.", scores: { h1b: 2, niw: 1 }, reason: "Early evidence should be strengthened before relying on high-threshold categories." },
    ],
  },
  {
    id: "education",
    eyebrow: "Step 5",
    question: "What education or specialized expertise can you document?",
    helper: "This is especially important for NIW, H-1B, and some employer-backed paths.",
    type: "multi",
    options: [
      { value: "advanced_degree", label: "Master's, PhD, MD, or equivalent advanced degree", detail: "Advanced academic qualification in the field.", scores: { niw: 4, h1b: 2, eb1a: 1 }, reason: "Advanced education is a strong NIW and specialty-role signal." },
      { value: "bachelor_five", label: "Bachelor's degree plus 5 or more years of progressive experience", detail: "Documented experience that shows deep specialization.", scores: { niw: 3, h1b: 2 }, reason: "Experience can support advanced ability and specialty occupation arguments." },
      { value: "licenses", label: "Professional license, certification, or regulated credential", detail: "Credential required or valued in your field.", scores: { niw: 2, h1b: 2, eb1a: 1 }, reason: "Credentials can strengthen expert positioning." },
      { value: "no_degree", label: "No degree path, but strong achievement record", detail: "My case depends more on achievements than formal education.", scores: { eb1a: 2, o1: 2, e2: 1 }, reason: "Extraordinary ability routes can rely more on achievement evidence." },
    ],
  },
  {
    id: "support",
    eyebrow: "Step 6",
    question: "What support path is available right now?",
    helper: "Some visas need an employer, petitioner, investment, or company relationship.",
    type: "single",
    options: [
      { value: "self", label: "I prefer a self-directed route", detail: "I do not want the case to depend on one employer.", scores: { eb1a: 4, niw: 4 }, reason: "Self-directed preference points toward EB-1A or NIW when evidence supports it." },
      { value: "us_employer", label: "A U.S. employer can sponsor or petition", detail: "I have an employer, offer, or strong company backing.", scores: { h1b: 4, o1: 2, eb1a: 1 }, reason: "Employer support opens specialty or petitioning options." },
      { value: "foreign_company", label: "I work for a foreign company with a U.S. affiliate", detail: "A transfer or executive/manager/specialized knowledge story may apply.", scores: { l1: 5, h1b: 1 }, reason: "A multinational relationship may support L-1 style planning." },
      { value: "investment", label: "I can invest or operate a qualifying U.S. business", detail: "I am exploring investor or founder pathways.", scores: { e2: 5, l1: 2, o1: 1 }, reason: "Investment or operating control may support business visa planning." },
    ],
  },
  {
    id: "timeline",
    eyebrow: "Step 7",
    question: "How soon do you need a strategy?",
    helper: "This helps separate urgent work authorization from longer evidence-building plans.",
    type: "single",
    options: [
      { value: "now", label: "Immediately or within 3 months", detail: "I need a practical path quickly.", scores: { o1: 2, h1b: 2, l1: 1 }, reason: "Urgent timelines may require a temporary or employer-supported bridge." },
      { value: "six_months", label: "Within 3 to 6 months", detail: "I can gather evidence but want a clear plan soon.", scores: { eb1a: 2, niw: 2, o1: 1 }, reason: "A few months can support evidence cleanup and attorney strategy." },
      { value: "year", label: "Six months or more", detail: "I can build profile strength before filing.", scores: { eb1a: 3, niw: 2 }, reason: "A longer runway helps build a stronger evidence record." },
      { value: "exploring", label: "Just exploring", detail: "I want to understand my best options.", scores: { eb1a: 1, niw: 1, o1: 1 }, reason: "Exploration is a good time to map evidence gaps." },
    ],
  },
];

const ASSESSMENT_QUESTIONS = [
  {
    code: "outcome",
    question: "What outcome are you trying to reach?",
    type: "single",
    options: ["Green card", "Work visa", "Long-term plan", "Just exploring"],
  },
  {
    code: "profile",
    question: "Which profile best describes you?",
    type: "single",
    options: ["Tech leader", "Researcher", "Executive", "Founder", "Creative", "Other"],
  },
  {
    code: "recognition",
    question: "Which recognition signals do you already have?",
    type: "multi",
    options: ["Awards", "Critical role", "Original contribution", "Judging", "Press", "Membership", "Patents", "High salary", "None"],
  },
  {
    code: "impact",
    question: "How broad is the impact of your work?",
    type: "single",
    options: ["Local", "Company", "Industry", "Global"],
  },
  {
    code: "education",
    question: "What education or expertise can you document?",
    type: "single",
    options: ["Advanced degree", "Bachelor's + experience", "Equivalent expertise"],
  },
  {
    code: "support_path",
    question: "What support path is available?",
    type: "single",
    options: ["Self-directed", "Employer-supported", "Co-founder", "Investor", "Other"],
  },
  {
    code: "timing",
    question: "How soon do you need a strategy?",
    type: "single",
    options: ["Now", "3-6 months", "6-12 months", "Just researching"],
  },
];

const ASSESSMENT_STORAGE_KEY = "ascend_assessment_session_v1";

const VISA_PATH_INFO = {
  eb1a: {
    label: "EB-1A",
    title: "Extraordinary Ability Green Card",
    summary: "Best when the record shows sustained acclaim, strong third-party recognition, and multiple documented EB-1A criteria.",
    next: "Map your evidence into awards, judging, original contributions, critical role, media, authorship, high salary, and related categories.",
  },
  niw: {
    label: "EB-2 NIW",
    title: "National Interest Waiver",
    summary: "Best when your work has national importance, you are well positioned to advance it, and the U.S. benefits from waiving employer sponsorship.",
    next: "Clarify the proposed endeavor, national importance, credentials, impact proof, and independent recommendation support.",
  },
  o1: {
    label: "O-1",
    title: "Extraordinary Ability Temporary Visa",
    summary: "Best when strong recognition exists and a petitioner or work arrangement can support a temporary U.S. work path.",
    next: "Organize acclaim, expert letters, work itinerary, press, judging, awards, and critical project proof.",
  },
  h1b: {
    label: "H-1B",
    title: "Specialty Occupation",
    summary: "Best when a U.S. employer can sponsor a role that requires specialized education or equivalent experience.",
    next: "Confirm role requirements, degree fit, employer sponsorship readiness, and timing constraints.",
  },
  l1: {
    label: "L-1",
    title: "Company Transfer",
    summary: "Best when you have qualifying work for a foreign company and a related U.S. entity can receive you.",
    next: "Document company relationship, prior employment, executive/manager or specialized knowledge role, and U.S. role plan.",
  },
  e2: {
    label: "E-2",
    title: "Treaty Investor",
    summary: "Best when nationality, investment, ownership, and active business operation requirements can be satisfied.",
    next: "Confirm treaty eligibility, investment source, operating plan, ownership/control, and business viability.",
  },
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

function readStoredSidebarWidth() {
  const parsed = Number(window.localStorage.getItem(SIDEBAR_WIDTH_KEY) || 256);
  if (!Number.isFinite(parsed)) return 256;
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, parsed));
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

function isPreviewRole(role) {
  return PREVIEW_ROLES.includes(role);
}

function previewIdentity(role, username = "") {
  const account = (PREVIEW_ACCOUNTS[role] || []).find((item) => item.username === username) || (PREVIEW_ACCOUNTS[role] || [])[0];
  const fallbackAccount = (DEV_LOGIN_ACCOUNTS[role] || [])[0] || {};
  return {
    account_id: `preview_${role}_${(account?.username || fallbackAccount.username || role).replace(/[^a-z0-9]+/gi, "_")}`,
    username: account?.username || fallbackAccount.username || "",
    email: account?.email || fallbackAccount.email || "",
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
      steps: ["Open Invite Member or Assignment Oversight.", "Enter member name, email, domain, title, and employer.", "Optionally choose builder and attorney.", "Create invite.", "Track registration and rebalance later."],
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

function visaCompassResult(answers) {
  const scores = { eb1a: 0, niw: 0, o1: 0, h1b: 0, l1: 0, e2: 0 };
  const reasons = [];
  const selectedLabels = {};
  VISA_COMPASS_QUESTIONS.forEach((question) => {
    const rawAnswer = answers[question.id];
    const selectedValues = Array.isArray(rawAnswer) ? rawAnswer : rawAnswer ? [rawAnswer] : [];
    const selectedOptions = question.options.filter((option) => selectedValues.includes(option.value));
    selectedLabels[question.id] = selectedOptions.map((option) => option.label);
    selectedOptions.forEach((option) => {
      Object.entries(option.scores || {}).forEach(([key, value]) => {
        scores[key] = (scores[key] || 0) + Number(value || 0);
      });
      if (option.reason) reasons.push(option.reason);
    });
  });
  const ranked = Object.entries(scores)
    .map(([key, score]) => ({ key, score, ...(VISA_PATH_INFO[key] || {}) }))
    .sort((left, right) => right.score - left.score);
  const top = ranked[0] || { key: "eb1a", score: 0, ...VISA_PATH_INFO.eb1a };
  const second = ranked[1] || { key: "niw", score: 0, ...VISA_PATH_INFO.niw };
  const maxScore = Math.max(1, VISA_COMPASS_QUESTIONS.length * 5);
  const readinessScore = Math.min(99, Math.max(18, Math.round((top.score / maxScore) * 100)));
  return {
    top_match: top.key,
    match_label: top.label,
    title: top.title,
    summary: top.summary,
    next: top.next,
    readiness_score: readinessScore,
    runner_up: { key: second.key, label: second.label, title: second.title, score: second.score },
    ranked: ranked.slice(0, 4).map((item) => ({ key: item.key, label: item.label, title: item.title, score: item.score })),
    reasons: [...new Set(reasons)].slice(0, 5),
    selected_labels: selectedLabels,
  };
}

function AscendVisaCompass() {
  const [isOpen, setIsOpen] = useState(false);
  const [answers, setAnswers] = useState({});
  const [step, setStep] = useState(0);
  const [leadForm, setLeadForm] = useState({ name: "", email: "", phone: "" });
  const [leadCaptured, setLeadCaptured] = useState(false);
  const [leadBusy, setLeadBusy] = useState(false);
  const [leadError, setLeadError] = useState("");
  const currentQuestion = VISA_COMPASS_QUESTIONS[step];
  const answeredCount = VISA_COMPASS_QUESTIONS.filter((question) => {
    const value = answers[question.id];
    return Array.isArray(value) ? value.length > 0 : Boolean(value);
  }).length;
  const isComplete = answeredCount === VISA_COMPASS_QUESTIONS.length;
  const result = visaCompassResult(answers);
  const progress = Math.round((answeredCount / VISA_COMPASS_QUESTIONS.length) * 100);
  const currentAnswer = currentQuestion ? answers[currentQuestion.id] : "";
  const selectedCurrentLabels = currentQuestion
    ? currentQuestion.options
      .filter((option) => Array.isArray(currentAnswer) ? currentAnswer.includes(option.value) : currentAnswer === option.value)
      .map((option) => option.label)
    : [];

  function chooseAnswer(question, value) {
    setLeadError("");
    setLeadCaptured(false);
    setAnswers((current) => {
      if (question.type === "multi") {
        const existing = Array.isArray(current[question.id]) ? current[question.id] : [];
        const next = existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value];
        return { ...current, [question.id]: next };
      }
      return { ...current, [question.id]: value };
    });
  }

  function questionAnswered(question) {
    const value = answers[question.id];
    return Array.isArray(value) ? value.length > 0 : Boolean(value);
  }

  async function submitLead(event) {
    event.preventDefault();
    setLeadBusy(true);
    setLeadError("");
    try {
      const response = await sendJson("/api/marketing/leads/visa-compass", {
        name: leadForm.name,
        email: leadForm.email,
        phone: leadForm.phone,
        source_url: window.location.href,
        answers,
        result,
        metadata: {
          answered_count: answeredCount,
          tool: "Ascend Visa Compass",
          version: "2026-05-07",
        },
      });
      if (!response.ok) {
        setLeadError(response.payload?.error || "Please enter a valid email to view your result.");
        return;
      }
      setLeadCaptured(true);
    } catch (_error) {
      setLeadError("We could not save your lead right now. Please try again in a moment.");
    } finally {
      setLeadBusy(false);
    }
  }

  function resetCompass() {
    setAnswers({});
    setStep(0);
    setLeadForm({ name: "", email: "", phone: "" });
    setLeadCaptured(false);
    setLeadError("");
  }

  return (
    <section className="visa-compass-launch-card">
      <p className="eyebrow">Free Assessment Tool</p>
      <h2>Find the best starting visa path.</h2>
      <p>Use Ascend Visa Compass as a quick guided chat before you speak with the team.</p>
      <button className="visa-compass-launch-btn" type="button" onClick={() => setIsOpen(true)}>
        <span>Ascend Visa Compass</span>
        <strong>Start assessment</strong>
      </button>
      <small>Email is requested before the final result so Ascend can follow up with the right guidance.</small>

      {isOpen ? (
        <div className="visa-chat-backdrop" role="presentation">
          <section className="visa-chat-shell" role="dialog" aria-modal="true" aria-labelledby="visa-compass-title">
            <div className="visa-chat-header">
              <div>
                <p className="eyebrow">Ascend Lead Navigator</p>
                <h2 id="visa-compass-title">Ascend Visa Compass</h2>
                <span>Answer a few questions. We will summarize the path that deserves attorney review first.</span>
              </div>
              <button className="icon-action" type="button" aria-label="Close Visa Compass" onClick={() => setIsOpen(false)}>x</button>
            </div>
            <div className="visa-chat-progress">
              <span style={{ width: `${progress}%` }} />
            </div>

            <div className="visa-chat-body">
              {!isComplete ? (
                <React.Fragment>
                  <div className="visa-chat-message assistant">
                    <span>{currentQuestion.eyebrow} of {VISA_COMPASS_QUESTIONS.length}</span>
                    <h3>{currentQuestion.question}</h3>
                    <p>{currentQuestion.helper}</p>
                  </div>
                  {selectedCurrentLabels.length ? (
                    <div className="visa-chat-message user">
                      <span>Your selection</span>
                      <p>{selectedCurrentLabels.join(", ")}</p>
                    </div>
                  ) : null}
                  <div className="visa-chat-options">
                    {currentQuestion.options.map((option) => {
                      const value = answers[currentQuestion.id];
                      const active = Array.isArray(value) ? value.includes(option.value) : value === option.value;
                      return (
                        <button
                          key={option.value}
                          className={`visa-chat-option ${active ? "active" : ""}`}
                          type="button"
                          onClick={() => chooseAnswer(currentQuestion, option.value)}
                        >
                          <strong>{option.label}</strong>
                          <span>{option.detail}</span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="visa-chat-actions">
                    <button className="ghost compact-btn" type="button" disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</button>
                    <span>{progress}% complete</span>
                    <button
                      className="primary compact-btn"
                      type="button"
                      disabled={!questionAnswered(currentQuestion)}
                      onClick={() => setStep((value) => Math.min(VISA_COMPASS_QUESTIONS.length - 1, value + 1))}
                    >
                      {step === VISA_COMPASS_QUESTIONS.length - 1 ? "Continue" : "Next"}
                    </button>
                  </div>
                </React.Fragment>
              ) : !leadCaptured ? (
                <React.Fragment>
                  <div className="visa-chat-message assistant">
                    <span>Almost done</span>
                    <h3>Your result is ready.</h3>
                    <p>Enter your email to unlock the match. Phone is optional and helps Ascend follow up faster.</p>
                  </div>
                  <form className="visa-chat-lead-form" onSubmit={submitLead}>
                    <label>Name<input value={leadForm.name} onChange={(event) => setLeadForm((current) => ({ ...current, name: event.target.value }))} placeholder="Your name" /></label>
                    <label>Email required<input type="email" required value={leadForm.email} onChange={(event) => setLeadForm((current) => ({ ...current, email: event.target.value }))} placeholder="you@example.com" /></label>
                    <label>Phone optional<input value={leadForm.phone} onChange={(event) => setLeadForm((current) => ({ ...current, phone: event.target.value }))} placeholder="+1 555 000 0000" /></label>
                    {leadError ? <div className="banner error">{leadError}</div> : null}
                    <div className="visa-chat-actions">
                      <button className="ghost compact-btn" type="button" onClick={resetCompass}>Start over</button>
                      <button className="primary compact-btn" type="submit" disabled={leadBusy}>{leadBusy ? "Saving..." : "Show My Match"}</button>
                    </div>
                  </form>
                </React.Fragment>
              ) : (
                <React.Fragment>
                  <div className="visa-chat-message assistant">
                    <span>Your first-pass match</span>
                    <div className="visa-chat-result-score">
                      <strong>{result.match_label}</strong>
                      <em>{result.readiness_score}% signal fit</em>
                    </div>
                    <h3>{result.title}</h3>
                    <p>{result.summary}</p>
                  </div>
                  <div className="visa-chat-result-grid">
                    <div><strong>Runner-up</strong><span>{result.runner_up.label} - {result.runner_up.title}</span></div>
                    <div><strong>Next step</strong><span>{result.next}</span></div>
                  </div>
                  <div className="visa-chat-reasons">
                    {result.reasons.map((reason) => <span key={reason}>{reason}</span>)}
                  </div>
                  <p className="visa-chat-disclaimer">This is intake guidance, not legal advice. Ascend and an attorney should review documents before any filing decision.</p>
                  <div className="visa-chat-actions">
                    <button className="ghost compact-btn" type="button" onClick={resetCompass}>Start over</button>
                    <button className="primary compact-btn" type="button" onClick={() => setIsOpen(false)}>Done</button>
                  </div>
                </React.Fragment>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function loadAssessmentState() {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(ASSESSMENT_STORAGE_KEY) || "{}");
    return {
      answers: parsed.answers || {},
      lead: parsed.lead || { name: "", email: "", phone: "", country: "", consent: false },
      resultToken: parsed.resultToken || "",
    };
  } catch (_error) {
    return { answers: {}, lead: { name: "", email: "", phone: "", country: "", consent: false }, resultToken: "" };
  }
}

function persistAssessmentState(nextState) {
  window.sessionStorage.setItem(ASSESSMENT_STORAGE_KEY, JSON.stringify(nextState));
}

function scoreAssessmentAnswers(answers) {
  const recognition = answers.recognition || [];
  const scores = { "EB-1A": 20, "EB-2 NIW": 20, "O-1": 18, "L-1": 12 };
  const signals = Array.isArray(recognition) ? recognition.filter((item) => item !== "None") : [];
  if (answers.outcome === "Green card") { scores["EB-1A"] += 18; scores["EB-2 NIW"] += 16; }
  if (answers.outcome === "Work visa") scores["O-1"] += 18;
  if (["Tech leader", "Executive", "Founder"].includes(answers.profile)) { scores["EB-1A"] += 12; scores["O-1"] += 8; }
  if (answers.profile === "Researcher") scores["EB-2 NIW"] += 16;
  if (signals.includes("Critical role")) scores["EB-1A"] += 12;
  if (signals.includes("Original contribution")) { scores["EB-1A"] += 12; scores["EB-2 NIW"] += 10; }
  if (signals.includes("Judging")) { scores["EB-1A"] += 8; scores["O-1"] += 6; }
  if (signals.includes("Press") || signals.includes("Awards")) { scores["EB-1A"] += 8; scores["O-1"] += 8; }
  if (["Industry", "Global"].includes(answers.impact)) { scores["EB-1A"] += 12; scores["EB-2 NIW"] += 12; }
  if (answers.education === "Advanced degree") scores["EB-2 NIW"] += 14;
  if (answers.support_path === "Employer-supported") scores["O-1"] += 8;
  if (answers.support_path === "Investor") scores["L-1"] += 10;
  const ranked = Object.entries(scores).sort((left, right) => right[1] - left[1]);
  return {
    topPath: ranked[0]?.[0] || "EB-1A",
    score: Math.min(96, ranked[0]?.[1] || 50),
    runnerUp: ranked[1]?.[0] || "EB-2 NIW",
    signals,
    nextStep: "Book a consultation so Ascend can review documents, evidence depth, and timing with the right strategy lens.",
  };
}

function AssessmentPublicPortal({ initialPage = "home" }) {
  const restored = loadAssessmentState();
  const [page, setPage] = useState(["home", "questions", "lead", "results"].includes(initialPage) ? initialPage : "home");
  const [answers, setAnswers] = useState(restored.answers);
  const [lead, setLead] = useState(restored.lead);
  const [resultToken, setResultToken] = useState(restored.resultToken);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const answeredCount = ASSESSMENT_QUESTIONS.filter((question) => {
    const value = answers[question.code];
    return Array.isArray(value) ? value.length : Boolean(value);
  }).length;
  const result = scoreAssessmentAnswers(answers);

  useEffect(() => {
    const handlePopState = () => {
      const route = readPortalRoute();
      if (route.portal === "assessment") setPage(["home", "questions", "lead", "results"].includes(route.page) ? route.page : "home");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    persistAssessmentState({ answers, lead, resultToken });
  }, [answers, lead, resultToken]);

  function navigate(nextPage) {
    setPage(nextPage);
    window.history.pushState({}, "", `/assessment/${nextPage === "home" ? "" : nextPage}`.replace(/\/$/, ""));
  }

  function setAnswer(question, option) {
    setError("");
    setAnswers((current) => {
      if (question.type === "multi") {
        const existing = Array.isArray(current[question.code]) ? current[question.code] : [];
        const next = existing.includes(option) ? existing.filter((item) => item !== option) : [...existing, option];
        return { ...current, [question.code]: next };
      }
      return { ...current, [question.code]: option };
    });
  }

  function resetAnswers() {
    setAnswers({});
    setLead({ name: "", email: "", phone: "", country: "", consent: false });
    setResultToken("");
    window.sessionStorage.removeItem(ASSESSMENT_STORAGE_KEY);
    navigate("questions");
  }

  async function submitLead(event) {
    event.preventDefault();
    if (!lead.name.trim() || !lead.email.trim() || !lead.country.trim() || !lead.consent) {
      setError("Full name, email, country, and consent are required before showing the result.");
      return;
    }
    setBusy(true);
    setError("");
    const token = `result_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
    try {
      const response = await sendJson("/api/marketing/leads/visa-compass", {
        name: lead.name,
        email: lead.email,
        phone: lead.phone,
        source_url: window.location.href,
        answers,
        result,
        metadata: { country: lead.country, consent: lead.consent, tool: "Ascend Visa Compass" },
      });
      if (!response.ok) {
        setError(response.payload?.error || "We could not save your assessment yet. Please try again before viewing the result.");
        setBusy(false);
        return;
      }
      setResultToken(token);
      setBusy(false);
      navigate("results");
    } catch (_error) {
      setError("We could not save your assessment yet. Please try again before viewing the result.");
      setBusy(false);
    }
  }

  return (
    <main className="assessment-shell">
      <header className="assessment-header">
        <PortalBrand onHome={() => navigate("home")} label="Go to assessment home" />
        <div>
          <span className="section-kicker">Ascend Visa Compass</span>
          <strong>{ASSESSMENT_ROUTE_LABELS[page] || ASSESSMENT_ROUTE_LABELS.home}</strong>
        </div>
      </header>
      {page === "questions" ? (
        <React.Fragment>
          <section className="hero assessment-hero">
            <p className="eyebrow">Assessment Chat</p>
            <h1>Chat-style eligibility questions.</h1>
            <p>Answer the fixed assessment questions. Your answers stay in this browser session so refresh and back/forward keep context.</p>
          </section>
          <section className="assessment-grid">
            <div className="panel">
              <div className="section-kicker">Chat Preview</div>
              <h3 className="section-title">Ascend asks, prospect answers</h3>
              <div className="assessment-chat-log">
                {ASSESSMENT_QUESTIONS.map((question, index) => {
                  const answer = answers[question.code];
                  const answerLabel = Array.isArray(answer) ? answer.join(", ") : answer;
                  return (
                    <React.Fragment key={question.code}>
                      <article className={`assessment-message assistant ${index === answeredCount ? "active" : ""}`}>
                        <span>Ascend</span>
                        <p>{question.question}</p>
                      </article>
                      {answerLabel ? <article className="assessment-message user"><span>Prospect</span><p>{answerLabel}</p></article> : null}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
            <div className="panel">
              <div className="panel-header">
                <div>
                  <div className="section-kicker">Question Bank</div>
                  <h3 className="section-title">{answeredCount} of {ASSESSMENT_QUESTIONS.length} answered</h3>
                </div>
                <span className="status-pill planned">{Math.round((answeredCount / ASSESSMENT_QUESTIONS.length) * 100)}%</span>
              </div>
              <div className="assessment-question-list">
                {ASSESSMENT_QUESTIONS.map((question, index) => (
                  <article key={question.code} className="assessment-question-card">
                    <strong>{index + 1}. {question.question}</strong>
                    <div className="assessment-options">
                      {question.options.map((option) => {
                        const value = answers[question.code];
                        const active = Array.isArray(value) ? value.includes(option) : value === option;
                        return <button key={option} className={active ? "active" : ""} type="button" onClick={() => setAnswer(question, option)}>{option}</button>;
                      })}
                    </div>
                  </article>
                ))}
              </div>
              <div className="form-actions">
                <button className="primary compact-btn" type="button" disabled={answeredCount < 6} onClick={() => navigate("lead")}>Continue to lead capture</button>
                <button className="ghost compact-btn" type="button" onClick={resetAnswers}>Reset answers</button>
              </div>
            </div>
          </section>
        </React.Fragment>
      ) : page === "lead" ? (
        <section className="assessment-grid">
          <form className="panel stacked-form" onSubmit={submitLead}>
            <div className="panel-header">
              <div>
                <div className="section-kicker">Lead Capture</div>
                <h2 className="section-title">Collect contact before showing final result</h2>
                <p className="section-intro">Email is required so Ascend can follow up. Phone is optional.</p>
              </div>
              <span className={`status-pill ${resultToken ? "completed" : "planned"}`}>{resultToken ? "Captured" : "Required before result"}</span>
            </div>
            <div className="profile-grid">
              <label>Full name *<input value={lead.name} onChange={(event) => setLead((current) => ({ ...current, name: event.target.value }))} /></label>
              <label>Email address *<input type="email" value={lead.email} onChange={(event) => setLead((current) => ({ ...current, email: event.target.value }))} /></label>
              <label>Phone number (optional)<input value={lead.phone} onChange={(event) => setLead((current) => ({ ...current, phone: event.target.value }))} /></label>
              <label>Current country *<input value={lead.country} onChange={(event) => setLead((current) => ({ ...current, country: event.target.value }))} /></label>
            </div>
            <label className="consent-line"><input type="checkbox" checked={Boolean(lead.consent)} onChange={(event) => setLead((current) => ({ ...current, consent: event.target.checked }))} /><span>I agree Ascend may contact me about my assessment result and EB1A planning.</span></label>
            {error ? <div className="banner error">{error}</div> : null}
            <div className="form-actions">
              <button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Capturing..." : "Show My Assessment Result"}</button>
              <button className="ghost compact-btn" type="button" onClick={() => navigate("questions")}>Back to questions</button>
            </div>
          </form>
          <section className="panel">
            <div className="section-kicker">UX Behavior</div>
            <h3 className="section-title">Lead gate behavior</h3>
            <div className="task-mini-list">
              {["Email required before result", "Phone optional for faster follow-up", "Consent stored with timestamp-ready context"].map((item) => <article key={item} className="task-mini-item"><strong>{item}</strong><p>Built for a clear marketing funnel without hiding the assessment value.</p></article>)}
            </div>
          </section>
        </section>
      ) : page === "results" ? (
        <section className="panel">
          {!resultToken ? (
            <div className="banner warning assessment-lock-banner">
              <span>Result is locked in the real UX until email is captured.</span>
              <button className="primary compact-btn" type="button" onClick={() => navigate("lead")}>Go to lead capture</button>
            </div>
          ) : (
            <React.Fragment>
              <div className="panel-header">
                <div>
                  <div className="section-kicker">Sample Result</div>
                  <h2 className="section-title">Likely fit: {result.topPath}</h2>
                  <p className="section-intro">The result is intentionally high-level and framed as intake guidance, not legal advice.</p>
                </div>
                <span className={`status-pill ${result.score >= 75 ? "completed" : result.score >= 55 ? "planned" : "in_progress"}`}>{result.score}% match</span>
              </div>
              <div className="metrics-grid">
                <MetricCard label="Top path" value={result.topPath} />
                <MetricCard label="Runner up" value={result.runnerUp} />
                <MetricCard label="Signals" value={result.signals.length || "TBD"} />
                <MetricCard label="Next step" value="Consult" />
              </div>
              <section className="panel panel-subsection">
                <div className="section-kicker">Evidence signals detected</div>
                <div className="hero-chips">{(result.signals.length ? result.signals : ["More evidence needed"]).map((signal) => <span key={signal} className="document-type-chip">{signal}</span>)}</div>
                <p className="section-intro">{result.nextStep}</p>
                <p className="mini-note">This is a high-level guide, not legal advice. An Ascend attorney will assess your specific situation.</p>
              </section>
              <div className="form-actions">
                <a className="primary compact-btn" href="/contact?source=assessment">Book Consultation</a>
                <button className="ghost compact-btn" type="button" onClick={resetAnswers}>Start Over</button>
              </div>
            </React.Fragment>
          )}
        </section>
      ) : (
        <React.Fragment>
          <section className="hero assessment-hero">
            <p className="eyebrow">Free Assessment Tool</p>
            <h1>Ascend Visa Compass.</h1>
            <p>A customer-facing, chatbot-style free assessment that captures qualified leads before showing personalized visa-path guidance.</p>
            <div className="hero-chips">
              <span className="hero-chip">Lead generation</span>
              <span className="hero-chip">Email required</span>
              <span className="hero-chip">Phone optional</span>
              <span className="hero-chip">Visa-path match</span>
            </div>
          </section>
          <section className="metrics-grid">
            <MetricCard label="Starts today" value="Live" />
            <MetricCard label="Completed" value={`${Math.round((answeredCount / ASSESSMENT_QUESTIONS.length) * 100)}%`} />
            <MetricCard label="Leads captured" value={resultToken ? 1 : 0} />
            <MetricCard label="Top path" value={result.topPath} />
          </section>
          <section className="panel">
            <div className="panel-header">
              <div>
                <div className="section-kicker">Experience Flow</div>
                <h2 className="section-title">Questionnaire to lead capture to result</h2>
                <p className="section-intro">This mirrors the intended marketing funnel: helpful assessment first, contact capture before final answer, then clear next step.</p>
              </div>
              <button className="primary compact-btn" type="button" onClick={() => navigate("questions")}>Start Assessment</button>
            </div>
            <div className="assessment-flow-grid">
              {[
                ["1. Ask questions", "Prospect answers seven guided questions in a chat-style flow."],
                ["2. Capture lead", "Email is required before the final result; phone is optional."],
                ["3. Show result", "The tool shows a high-level path match and suggested next step."],
                ["4. Store lead", "Ascend stores the lead for future marketing and follow-up."],
              ].map(([title, body]) => <article key={title} className="action-row"><strong>{title}</strong><p>{body}</p></article>)}
            </div>
          </section>
        </React.Fragment>
      )}
    </main>
  );
}

function confirmDeleteAction(primaryMessage, finalMessage = "This will move the item to archive storage. Do you want to continue?") {
  if (!window.confirm(primaryMessage)) return false;
  return window.confirm(finalMessage);
}

function readPortalRoute() {
  const params = new URLSearchParams(window.location.search);
  const pathParts = window.location.pathname.split("/").filter(Boolean);
  if (pathParts[0] === "assessment") {
    return {
      portal: "assessment",
      page: pathParts[1] || "home",
      section: pathParts[1] || "home",
      perspective: "",
      memberId: "",
      criterion: "",
      folderId: "",
      registrationToken: "",
    };
  }
  if (pathParts[0] === "staff" && pathParts[1] === "assessment") {
    return {
      portal: "assessment",
      page: "leads",
      section: "leads",
      perspective: "",
      memberId: "",
      criterion: "",
      folderId: "",
      registrationToken: "",
    };
  }
  if (pathParts[0] === "member") {
    return {
      portal: "member",
      page: pathParts[1] || params.get("page") || "home",
      section: "",
      perspective: "",
      memberId: "",
      criterion: params.get("criterion") || "",
      folderId: params.get("folder") || "",
      registrationToken: params.get("registration") || params.get("invite") || "",
    };
  }
  if (PATH_PORTALS.has(pathParts[0])) {
    return {
      portal: pathParts[0],
      page: "",
      section: normalizePortalSection(pathParts[0], pathParts[1] || params.get("section") || "home"),
      perspective: params.get("perspective") || "",
      memberId: params.get("member") || "",
      criterion: "",
      folderId: "",
      registrationToken: "",
    };
  }
  return {
    portal: params.get("portal") || "",
    page: params.get("page") || "",
    section: params.get("section") || "",
    perspective: params.get("perspective") || "",
    memberId: params.get("member") || "",
    criterion: params.get("criterion") || "",
    folderId: params.get("folder") || "",
    registrationToken: params.get("registration") || params.get("invite") || "",
  };
}

function memberPagePathSegment(page) {
  return {
    critical_roles: "critical-role",
    original_contributions: "original-contributions",
  }[page] || page || "home";
}

function firstNameFromDisplay(value) {
  return String(value || "").trim().split(/\s+/)[0] || String(value || "");
}

function normalizePortalSection(portal, section) {
  const raw = String(section || "home").trim() || "home";
  return PORTAL_SECTION_ALIASES[portal]?.[raw] || raw;
}

function portalSectionPathSegment(portal, section) {
  return PORTAL_SECTION_PATHS[portal]?.[section] || section || "home";
}

function subtitleForPortalSection(role, section, perspective = "") {
  if (role === "leader" && perspective === "builder") {
    return SECTION_SUBTITLES.builder[section] || SECTION_SUBTITLES.builder.home;
  }
  if (role === "leader" && perspective === "attorney") {
    return SECTION_SUBTITLES.attorney[section] || SECTION_SUBTITLES.attorney.home;
  }
  return SECTION_SUBTITLES[role]?.[section] || "";
}

function memberViewForCriterion(code) {
  if (code === "leading_critical_role") return { type: "critical_roles", criterionCode: "" };
  if (code === "original_contributions") return { type: "original_contributions", criterionCode: "" };
  return { type: "workspace", criterionCode: code || "" };
}

function criterionAccent(code) {
  return {
    awards: "#c58a2f",
    memberships: "#7c6db3",
    published_material: "#4f86c6",
    judging: "#2d7d68",
    original_contributions: "#b95c42",
    scholarly_articles: "#5d7f9a",
    leading_critical_role: "#1f6b57",
    high_salary: "#a46a2a",
    comparable_evidence: "#7a8a45",
    other: "#7c8792",
    all: "#2f7d67",
  }[code || "other"] || "#7c8792";
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

function renderLinkedMessageText(text) {
  const raw = String(text || "");
  if (!raw) return null;
  const parts = raw.split(/(https?:\/\/[^\s]+|\/api\/[^\s]+)/g);
  return parts.map((part, index) => {
    if (/^https?:\/\//.test(part)) {
      return <a key={`msg_link_${index}`} className="message-link" href={part} target="_blank" rel="noreferrer">{part}</a>;
    }
    if (/^\/api\//.test(part)) {
      return <a key={`msg_link_${index}`} className="message-link" href={`${API_URL}${part}`} target="_blank" rel="noreferrer">{part}</a>;
    }
    return <React.Fragment key={`msg_text_${index}`}>{part}</React.Fragment>;
  });
}

function actorMessageKeys(member) {
  if (!member) return new Set();
  return new Set([
    member.storage_key,
    member.numeric_identifier ? String(member.numeric_identifier) : "",
    member.legacy_key,
    member.role === "member" ? member.client_id : member.email,
  ].filter(Boolean).map((item) => String(item).trim()));
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

function costPeriodValue(source, period, field = "actual") {
  const row = (source?.recurring || []).find((item) => String(item.period || "").toLowerCase() === String(period || "").toLowerCase());
  return Number(row?.[field] || 0);
}

function formatResponseMs(value) {
  const amount = Number(value || 0);
  if (!amount) return "N/A";
  if (amount >= 1000) return `${(amount / 1000).toFixed(amount >= 2000 ? 1 : 2)}s`;
  return `${Math.round(amount)}ms`;
}

function browserTimingSnapshot() {
  const navigation = window.performance?.getEntriesByType?.("navigation")?.[0];
  if (!navigation) return {};
  const responseMs = Math.max(0, Math.round((navigation.responseEnd || 0) - (navigation.requestStart || 0)));
  const interactiveMs = Math.max(0, Math.round((navigation.domInteractive || 0) - (navigation.startTime || 0)));
  return {
    navigation_response_ms: responseMs,
    dom_interactive_ms: interactiveMs,
  };
}

function healthStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (["healthy", "online", "success", "available", "configured", "synced"].includes(normalized)) return "completed";
  if (["degraded", "fallback", "needs_refresh", "warning"].includes(normalized)) return "planned";
  return "blocked";
}

function issueStatusLabel(value) {
  const normalized = String(value || "new").toLowerCase();
  return ISSUE_STATUS_OPTIONS.find((option) => option.value === normalized)?.label || LEGACY_ISSUE_STATUS_LABELS[normalized] || normalized.replaceAll("_", " ");
}

function activeIssueCount(backlog) {
  const counts = backlog?.status_counts || {};
  return ["new", "open", "triaged", "in_progress", "testing", "blocked", "fixed_local"].reduce((total, status) => total + Number(counts[status] || 0), 0);
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
  if (normalized.includes("ai") || normalized.includes("classification")) return "support-category-ai";
  if (normalized.includes("message") || normalized.includes("communication")) return "support-category-message";
  if (normalized.includes("bug") || normalized.includes("error")) return "support-category-bug";
  return "support-category-other";
}

function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), undefined, { sensitivity: "base" });
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

function normalizeFolderId(value) {
  return value || "";
}

function workspaceFolderMap(workspace) {
  return new Map((workspace?.folders || []).map((folder) => [folder.id, folder]));
}

function workspaceFolderDepth(folder, folderMap) {
  let depth = 0;
  let current = folderMap.get(folder?.parent_id || "");
  while (current && depth < 12) {
    depth += 1;
    current = folderMap.get(current.parent_id || "");
  }
  return depth;
}

function workspaceFolderLabel(workspace, folderId) {
  if (!folderId) return "Root";
  const folder = workspaceFolderMap(workspace).get(folderId);
  return folder?.path || folder?.name || "Selected folder";
}

function workspaceBreadcrumb(workspace, folderId) {
  const folderMap = workspaceFolderMap(workspace);
  const trail = [];
  let current = folderMap.get(folderId || "");
  while (current) {
    trail.unshift(current);
    current = folderMap.get(current.parent_id || "");
  }
  return trail;
}

function workspaceFolderMatches(folder, query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [folder.name, folder.path].some((value) => String(value || "").toLowerCase().includes(normalized));
}

function workspaceFileMatches(file, query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;
  return [file.file_name, file.title, file.description, file.ai_summary, file.document_type, file.folder_path]
    .some((value) => String(value || "").toLowerCase().includes(normalized));
}

function buildDriveRows(workspace, selectedFolderId, query = "") {
  if (!workspace) return [];
  const folderId = normalizeFolderId(selectedFolderId);
  const searchActive = Boolean(query.trim());
  const folders = (workspace.folders || [])
    .filter((folder) => (searchActive ? workspaceFolderMatches(folder, query) : normalizeFolderId(folder.parent_id) === folderId))
    .map((folder) => ({
      id: `folder:${folder.id}`,
      kind: "folder",
      entityId: folder.id,
      label: folder.name,
      documentType: "Folder",
      subtitle: `${folder.file_count || 0} files, ${folder.child_folder_count || 0} folders`,
      timestamp: folder.updated_at ? `Updated ${formatDateTime(folder.updated_at)}` : folder.path || "Folder",
      parentId: normalizeFolderId(folder.parent_id),
      folderId: folder.id,
      path: folder.path || folder.name,
      color: folder.color || FOLDER_COLORS.Emerald,
      href: null,
    }));
  const files = (workspace.files || [])
    .filter((file) => (searchActive ? workspaceFileMatches(file, query) : normalizeFolderId(file.folder_id) === folderId))
    .map((file) => ({
      id: `file:${file.id}`,
      kind: "file",
      entityId: file.id,
      label: file.file_name,
      documentType: file.document_type || "Other",
      subtitle: cleanSummary(file.ai_summary || file.description),
      timestamp: formatUploadedAt(file.created_at),
      folderId: normalizeFolderId(file.folder_id),
      path: file.folder_path || "Root",
      color: criterionAccent(file.criterion_code),
      href: file.open_url || file.drive_web_url || null,
    }));
  return [...folders, ...files].sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === "folder" ? -1 : 1;
    return compareText(left.label, right.label);
  });
}

function workspaceDragPayload(item) {
  return {
    kind: item.kind,
    entityId: item.entityId,
    label: item.label,
    folderId: normalizeFolderId(item.folderId),
    parentId: normalizeFolderId(item.parentId),
  };
}

function readWorkspaceDragPayload(event) {
  const raw = event.dataTransfer.getData("application/json");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (_error) {
    return null;
  }
}

function readDirectoryEntries(reader) {
  return new Promise((resolve, reject) => {
    reader.readEntries(resolve, reject);
  });
}

function fileFromEntry(entry) {
  return new Promise((resolve) => {
    entry.file((file) => resolve(file), () => resolve(null));
  });
}

async function walkDroppedEntry(entry, prefix, files) {
  if (entry.isFile) {
    const file = await fileFromEntry(entry);
    if (file) files.push({ file, relativePath: `${prefix}${file.name}` });
    return;
  }
  if (!entry.isDirectory) return;
  const reader = entry.createReader();
  let batch = await readDirectoryEntries(reader);
  while (batch.length) {
    for (const child of batch) {
      await walkDroppedEntry(child, `${prefix}${entry.name}/`, files);
    }
    batch = await readDirectoryEntries(reader);
  }
}

async function collectDroppedFiles(dataTransfer) {
  const entries = Array.from(dataTransfer?.items || [])
    .map((item) => (typeof item.webkitGetAsEntry === "function" ? item.webkitGetAsEntry() : null))
    .filter(Boolean);
  if (entries.length) {
    const files = [];
    for (const entry of entries) {
      await walkDroppedEntry(entry, "", files);
    }
    return files;
  }
  return Array.from(dataTransfer?.files || []).map((file) => ({
    file,
    relativePath: file.webkitRelativePath || file.name,
  }));
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

function emptyEndeavorPromptForm() {
  return {
    who_you_are: "You are an expert EB1A Attorney looking at multiple successful cases. Write down the endeavor letter so that USCIS officer is convinced naturally without RFE.",
    field_of_expertise: "",
    proposed_endeavor: "",
    current_work_continuity: "",
    future_work_plan: "",
    national_importance: "",
    evidence_emphasis: "",
    attorney_strategy_notes: "",
    tone_guidance: "Write in first person, professional, concrete, and measured. Keep the storyline natural and cohesive. Avoid bullet points, numbered-list phrasing, overclaiming, speculation, and unsupported legal conclusions.",
    length_constraints: "Keep the final letter within two pages, roughly 700 to 900 words, and closely follow the endeavor-letter template format.",
  };
}

function buildEndeavorPromptDefaults(member, detail, evidenceItems) {
  const form = emptyEndeavorPromptForm();
  const profile = detail?.profile || {};
  const criteria = detail?.criteria || [];
  const strongCriteria = criteria.filter((item) => item.evidence_count).sort((left, right) => right.evidence_count - left.evidence_count).slice(0, 4);
  const evidenceTitles = (evidenceItems || []).slice(0, 6).map((item) => item.title || item.file_name).filter(Boolean);
  const fieldBits = [profile.primary_field, profile.specialization].filter(Boolean);
  const fieldLabel = fieldBits.join(" • ") || profile.industry_domain || member?.primary_field || "the member's field of expertise";
  const roleLine = [profile.current_title || member?.current_title, profile.current_employer || member?.current_employer].filter(Boolean).join(" at ");
  return {
    ...form,
    field_of_expertise: fieldLabel,
    proposed_endeavor: `${member?.display_name || "The member"} should continue advancing ${fieldLabel} in the United States through ongoing professional work, technical leadership, and field-shaping contributions.`,
    current_work_continuity: `Connect the proposed endeavor directly to ${roleLine || "the member's current professional responsibilities"}, prior evidence-backed achievements, and the same area of recognized expertise already reflected in the record.`,
    future_work_plan: profile.top_achievements || profile.proposed_final_merits_summary || "Describe the specific work the member plans to continue in the United States over the near and medium term, including applied innovation, publications, judging, mentoring, and other lawful field contributions where supported.",
    national_importance: `Explain why this work matters in the United States, focusing on practical impact, innovation, sector value, and downstream benefit. Domain context: ${profile.industry_domain || fieldLabel}.`,
    evidence_emphasis: evidenceTitles.length ? `Ground the letter in these uploaded materials where relevant: ${evidenceTitles.join("; ")}.` : "Use the uploaded evidence set to ground the member's prior achievements, role progression, recognition, and future work trajectory.",
    attorney_strategy_notes: `Emphasize continuity, credibility, and a fact-grounded future plan. Strongest criterion areas currently reflected in the record: ${strongCriteria.length ? strongCriteria.map((item) => item.name).join(", ") : "use the strongest documented criteria first"}.`,
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

function emptyCriticalRoleProjectForm() {
  return {
    id: "",
    organization_name: "",
    organization_unit: "",
    organization_location: "",
    organization_website: "",
    employment_type: "",
    role_title: "",
    role_start_date: "",
    role_end_date: "",
    is_current_role: false,
    project_name: "",
    project_start_date: "",
    project_end_date: "",
    project_status: "Active",
    organization_achievements: "",
    organization_distinctiveness: "",
    role_summary: "",
    role_responsibilities: "",
    role_evolution: "",
    leadership_scope: "",
    cross_functional_partners: "",
    project_summary: "",
    business_need: "",
    strategic_importance: "",
    contributions_summary: "",
    innovation_originality: "",
    business_value_summary: "",
    quantitative_metrics: "",
    revenue_impact: "",
    cost_savings: "",
    efficiency_gain: "",
    user_or_customer_impact: "",
    market_or_geographic_impact: "",
    compliance_or_risk_impact: "",
    peer_distinction_summary: "",
    mentorship_leadership: "",
    executive_visibility: "",
    evidence_available: "",
    attorney_friendly_summary: "",
    workflow_status: "draft",
  };
}

function hydrateCriticalRoleProject(project) {
  return {
    ...emptyCriticalRoleProjectForm(),
    ...project,
    is_current_role: Boolean(project?.is_current_role),
    workflow_status: project?.workflow_status || "draft",
  };
}

function formatCompactDate(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString([], { month: "short", year: "numeric" });
}

function formatProjectDateRange(start, end, isCurrent = false) {
  const startLabel = formatCompactDate(start);
  const endLabel = isCurrent ? "Present" : formatCompactDate(end);
  if (startLabel && endLabel) return `${startLabel} to ${endLabel}`;
  return startLabel || endLabel || "Dates not added yet";
}

function criticalRoleProjectCardMetric(project) {
  return project.quantitative_metrics || project.business_value_summary || project.user_or_customer_impact || "Add measurable outcomes and business value.";
}

function emptyOriginalContributionForm() {
  return {
    id: "",
    contribution_title: "",
    contribution_category: "Work-related",
    field_of_expertise: "",
    job_title: "",
    organization_name: "",
    project_name: "",
    contribution_start_date: "",
    contribution_end_date: "",
    contribution_status: "Completed",
    originality_summary: "",
    challenging_paradigms: "",
    prior_state_of_field: "",
    work_vs_external_context: "",
    personal_role: "",
    distinct_contribution_summary: "",
    technical_or_business_problem: "",
    solution_or_innovation: "",
    unique_features: "",
    impact_metrics: "",
    adoption_scale: "",
    beneficiary_summary: "",
    time_savings: "",
    cost_savings: "",
    revenue_impact: "",
    quality_or_risk_impact: "",
    field_wide_impact: "",
    recognition_and_influence: "",
    media_or_public_mentions: "",
    adoption_letters_targets: "",
    evidence_available: "",
    attorney_friendly_summary: "",
    workflow_status: "draft",
  };
}

function hydrateOriginalContribution(entry) {
  return {
    ...emptyOriginalContributionForm(),
    ...entry,
  };
}

function originalContributionCardMetric(entry) {
  return entry.impact_metrics || entry.field_wide_impact || entry.adoption_scale || "Add the measurable impact of this contribution.";
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

function LeaderInvitePanel({ form, builders = [], attorneys = [], busy, onFieldChange, onSubmit, showFlow = true }) {
  return (
    <section className="panel leader-invite-panel">
      <div className="section-kicker">Member Intake</div>
      <h3 className="section-title">Invite A New Member</h3>
      <p className="section-intro">Send the member registration path by email, then optionally route the case to a Profile Builder and Attorney now or leave assignment open for later.</p>
      {showFlow ? <AssignmentFlowGuide /> : null}
      <form className="stacked-form leader-invite-form" onSubmit={onSubmit}>
        <div className="leader-invite-grid">
          <label>First name<input value={form.first_name} onChange={(event) => onFieldChange("first_name", event.target.value)} /></label>
          <label>Last name<input value={form.last_name} onChange={(event) => onFieldChange("last_name", event.target.value)} /></label>
          <label>Email<input type="email" value={form.email} onChange={(event) => onFieldChange("email", event.target.value)} /></label>
          <label>Domain<select value={form.industry_domain} onChange={(event) => onFieldChange("industry_domain", event.target.value)}>{DOMAIN_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select></label>
          <label>Primary field<input value={form.primary_field} onChange={(event) => onFieldChange("primary_field", event.target.value)} placeholder="For example: Clinical AI, Claims Analytics, Biotechnology" /></label>
          <label>Current title<input value={form.current_title} onChange={(event) => onFieldChange("current_title", event.target.value)} /></label>
          <label>Current employer<input value={form.current_employer} onChange={(event) => onFieldChange("current_employer", event.target.value)} /></label>
          <label>Profile builder (optional)<select value={form.builder_id} onChange={(event) => onFieldChange("builder_id", event.target.value)}><option value="">Assign later</option>{builders.map((builder) => <option key={builder.id} value={builder.id}>{builder.display_name}</option>)}</select></label>
          <label>Attorney (optional)<select value={form.attorney_id} onChange={(event) => onFieldChange("attorney_id", event.target.value)}><option value="">Assign later</option>{attorneys.map((attorney) => <option key={attorney.id} value={attorney.id}>{attorney.display_name}</option>)}</select></label>
        </div>
        <div className="form-actions">
          <button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Preparing..." : "Create Invite And Route"}</button>
        </div>
      </form>
    </section>
  );
}

function LeaderRecentInvitesPanel({ invites = [] }) {
  return (
    <section className="panel">
      <div className="section-kicker">Registration Flow</div>
      <h3 className="section-title">Recent Member Invites</h3>
      <p className="section-intro">Quick confirmation of who has been invited, who has registered, and where the next assignment handoff should happen.</p>
      <div className="task-mini-list">
        {invites.length ? invites.map((item) => (
          <article key={item.id} className="task-mini-item">
            <strong>{item.display_name}</strong>
            <p>{item.email}</p>
            <div className="task-mini-meta">
              <span>{item.status === "registered" ? "Registered" : "Invite sent"}</span>
              <span>Email: {item.email_delivery_status || "pending"}</span>
              <span>{item.invite_sent_at ? `Invited ${item.invite_sent_at}` : "Invite pending"}</span>
              <span>{item.registered_at ? `Registered ${item.registered_at}` : "Awaiting registration"}</span>
            </div>
          </article>
        )) : <p className="empty-state">No member invites yet.</p>}
      </div>
    </section>
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

function emptyFeatureRequestForm() {
  return {
    title: "",
    request_type: "enhancement",
    target_portals: "Leader Portal",
    priority: "P1",
    business_value: "",
    description: "",
    acceptance_criteria: "",
    requested_by: "",
    screenshots: [],
  };
}

function emptyIssueLogForm() {
  return {
    title: "",
    portal: "Admin Portal",
    section: "Cost Explorer",
    priority: "P1",
    status: "new",
    description: "",
    reported_by: "",
  };
}

function emptyRecommendationPromptForm() {
  return {
    letter_kind: "independent",
    project_type: "",
    project_id: "",
    who_you_are: "You are an expert EB1A attorney drafting a recommendation letter for review and signature by a recommender.",
    recommender_name: "",
    recommender_title: "",
    recommender_organization: "",
    recommender_relationship: "",
    facts_to_confirm: "Confirm dates, scope, personal contribution, measurable impact, and why this project matters.",
    independence_guidance: "For independent letters, explain the recommender's independence and field authority. For dependent/project letters, explain firsthand knowledge and project-specific credibility.",
    attorney_strategy_notes: "Ground the letter in the selected Critical Role or Original Contribution project and avoid generic praise.",
    tone_guidance: "Professional, factual, concrete, and suitable for recommender signature.",
    length_constraints: "Keep the letter around one to two pages.",
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
    case "invite":
      return <svg {...commonProps}><path d="M4 7h16v10H4z" /><path d="m4.5 7.5 7.5 5 7.5-5" /><path d="M18 4.5v5" /><path d="M15.5 7h5" /></svg>;
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
    if (itemValue === "invite") return "invite";
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
            {item.icon ? item.icon : <NavIcon name={iconForItem(item.value)} />}
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
      <span className="brand-row">
        <span className="brand-mark">A</span>
        <span className="brand">ASCEND</span>
      </span>
    </button>
  );
}

function MagicRewriteTextarea({
  className = "",
  label,
  required = false,
  value,
  placeholder,
  help,
  rewrite,
  busy,
  onChange,
  onRewrite,
  onShowOriginal,
  onShowRewrite,
  onRevert,
}) {
  const activeVersion = rewrite?.activeVersion || "";
  return (
    <label className={`magic-field ${className}`.trim()}>
      <span className="magic-field-top">
        <span>{label}{required ? " *" : ""}</span>
        <button className="magic-rewrite-btn" type="button" onClick={onRewrite} disabled={busy} title="Rewrite with Ascend AI">
          <span className="magic-orb">✦</span>
          <span>{busy ? "Rewriting" : "AI rewrite"}</span>
        </button>
      </span>
      <textarea value={value} onChange={(event) => onChange(event.target.value)} required={required} placeholder={placeholder} />
      {help ? <span className="field-help">{help}</span> : null}
      {rewrite ? (
        <div className="magic-compare-panel">
          <div>
            <strong>AI rewrite ready</strong>
            <span>{rewrite.source === "openai" ? "Generated with OpenAI" : "Structured fallback draft"}{rewrite.rationale ? ` • ${rewrite.rationale}` : ""}</span>
          </div>
          <div className="magic-compare-actions">
            <button className={activeVersion === "original" ? "active" : ""} type="button" onClick={onShowOriginal}>Original</button>
            <button className={activeVersion === "rewrite" ? "active" : ""} type="button" onClick={onShowRewrite}>AI draft</button>
            <button type="button" onClick={onRevert}>Revert</button>
          </div>
        </div>
      ) : null}
    </label>
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
            <p>{renderLinkedMessageText(item.body)}</p>
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
            <span>{renderLinkedMessageText(item.body)}</span>
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
                      <span>ID {selectedRecipient.numeric_identifier || selectedRecipient.key} • {selectedRecipient.email || selectedRecipient.detail}</span>
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
                          <span>ID {item.numeric_identifier || item.key} • {item.email || item.detail}</span>
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

function WorkspaceBreadcrumb({ workspace, selectedFolderId, onSelect, onDropItem }) {
  const trail = workspaceBreadcrumb(workspace, selectedFolderId);
  function dropOn(event, folderId) {
    event.preventDefault();
    const payload = readWorkspaceDragPayload(event);
    if (payload) onDropItem(payload, folderId);
  }
  return (
    <nav className="workspace-breadcrumb" aria-label="Evidence folder path">
      <button
        type="button"
        className={!selectedFolderId ? "active" : ""}
        onClick={() => onSelect("")}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => dropOn(event, "")}
      >
        Root
      </button>
      {trail.map((folder) => (
        <React.Fragment key={folder.id}>
          <span>/</span>
          <button
            type="button"
            className={selectedFolderId === folder.id ? "active" : ""}
            onClick={() => onSelect(folder.id)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => dropOn(event, folder.id)}
          >
            {folder.name}
          </button>
        </React.Fragment>
      ))}
    </nav>
  );
}

function WorkspaceFolderTree({ workspace, selectedFolderId, onSelect, onDropItem }) {
  const folders = [...(workspace?.folders || [])].sort((left, right) => compareText(left.path || left.name, right.path || right.name));
  const folderMap = workspaceFolderMap(workspace);
  function dropOn(event, folderId) {
    event.preventDefault();
    const payload = readWorkspaceDragPayload(event);
    if (payload) onDropItem(payload, folderId);
  }
  return (
    <div className="workspace-folder-tree">
      <button
        className={`tree-item drive-tree-item ${!selectedFolderId ? "active" : ""}`}
        type="button"
        onClick={() => onSelect("")}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => dropOn(event, "")}
      >
        <span className="folder-dot root" />
        <span>Root</span>
      </button>
      {folders.map((folder) => {
        const depth = workspaceFolderDepth(folder, folderMap);
        return (
          <button
            key={folder.id}
            className={`tree-item drive-tree-item ${selectedFolderId === folder.id ? "active" : ""}`}
            style={{ "--folder-depth": depth }}
            type="button"
            title={folder.path}
            onClick={() => onSelect(folder.id)}
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => dropOn(event, folder.id)}
          >
            <span className="folder-dot" style={{ background: folder.color }} />
            <span>{folder.name}</span>
            <small>{folder.file_count || 0}</small>
          </button>
        );
      })}
    </div>
  );
}

function WorkspaceItemRow({ item, folderOptions, onDragStart, onOpenFolder, onDeleteFile, onDeleteFolder, onMoveItem }) {
  const currentFolderId = item.kind === "folder" ? normalizeFolderId(item.parentId) : normalizeFolderId(item.folderId);
  const moveOptions = folderOptions.filter((option) => item.kind !== "folder" || option.value !== item.entityId);
  function handleDrop(event) {
    event.preventDefault();
    if (item.kind !== "folder") return;
    const payload = readWorkspaceDragPayload(event);
    if (payload) onMoveItem(payload, item.entityId);
  }
  return (
    <article
      className={`drive-row drive-row-${item.kind}`}
      draggable
      onDragStart={(event) => onDragStart(event, item)}
      onDragOver={item.kind === "folder" ? (event) => event.preventDefault() : undefined}
      onDrop={item.kind === "folder" ? handleDrop : undefined}
    >
      <button className="drag-handle drive-drag-handle" type="button" aria-label={`Drag ${item.label}`}>⋮⋮</button>
      <div className="drive-kind" aria-hidden="true">
        <span className={`drive-icon ${item.kind}`} style={{ "--folder-color": item.color }} />
      </div>
      <div className="drive-name-cell">
        {item.kind === "folder" ? (
          <button className="board-folder-link" type="button" onClick={() => onOpenFolder(item.entityId)}>{item.label}</button>
        ) : item.href ? (
          <a className="board-link" href={item.href} target="_blank" rel="noreferrer">{item.label}</a>
        ) : (
          <strong>{item.label}</strong>
        )}
        <span>{item.kind === "folder" ? item.path : item.subtitle}</span>
      </div>
      <span className="drive-type">{item.documentType}</span>
      <span className="drive-date">{item.timestamp}</span>
      <label className="drive-move-select">
        <span>Move to</span>
        <select
          value={currentFolderId}
          onChange={(event) => onMoveItem(item, event.target.value)}
          aria-label={`Move ${item.label} to folder`}
        >
          {moveOptions.map((option) => <option key={option.value || "root"} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <button
        className="icon-action drive-delete-action"
        type="button"
        onClick={() => (item.kind === "folder" ? onDeleteFolder(item) : onDeleteFile(item))}
      >
        Delete
      </button>
    </article>
  );
}

function WorkspaceDriveDropZone({ targetFolderId, disabled, children, onMoveItem, onUploadFiles }) {
  async function handleDrop(event) {
    event.preventDefault();
    if (disabled) return;
    const payload = readWorkspaceDragPayload(event);
    if (payload) {
      onMoveItem(payload, targetFolderId);
      return;
    }
    const droppedFiles = await collectDroppedFiles(event.dataTransfer);
    if (droppedFiles.length) onUploadFiles(droppedFiles, targetFolderId);
  }
  return (
    <section
      className="workspace-drive-dropzone"
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
    >
      {children}
    </section>
  );
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

function buildMemberEvidenceRegister(evidence = [], criteriaByCode = {}) {
  return [...evidence]
    .map((item) => ({
      ...item,
      categoryLabel: criteriaByCode[item.criterion_code]?.name || String(item.criterion_code || "Uncategorized").replaceAll("_", " "),
      evidenceLabel: item.title || item.file_name || "Uploaded evidence",
      documentType: item.document_type || "Other",
    }))
    .sort((left, right) => {
      const categoryOrder = compareText(left.categoryLabel, right.categoryLabel);
      if (categoryOrder !== 0) return categoryOrder;
      return String(right.created_at || "").localeCompare(String(left.created_at || ""));
    });
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

function MemberEvidenceCoveragePanel({ criteria = [], evidence = [], criteriaByCode = {}, onOpenCriterion }) {
  const [activeCriterion, setActiveCriterion] = useState("all");
  const rows = buildMemberEvidenceRegister(evidence, criteriaByCode);
  const rowsForActiveCriterion = activeCriterion === "all" ? rows : rows.filter((item) => item.criterion_code === activeCriterion);
  const evidenceCounts = rows.reduce((acc, item) => {
    const key = item.criterion_code || "other";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const visibleCriteria = criteria.length ? criteria : Object.values(criteriaByCode || {});
  const knownCriterionCodes = new Set(visibleCriteria.map((criterion) => criterion.code));
  const extraCriteria = Array.from(new Set(rows.map((item) => item.criterion_code || "other").filter((code) => code && !knownCriterionCodes.has(code))))
    .map((code) => ({ code, name: criteriaByCode[code]?.name || String(code).replaceAll("_", " ") }));
  const criterionOptions = [{ code: "all", name: "All Evidence", count: rows.length }, ...visibleCriteria, ...extraCriteria];
  const activeCriterionLabel = activeCriterion === "all"
    ? "All Evidence"
    : (criterionOptions.find((criterion) => criterion.code === activeCriterion)?.name || String(activeCriterion).replaceAll("_", " "));
  return (
    <section className="panel evidence-register-panel">
      <div className="panel-header compact-panel-header">
        <div>
          <div className="section-kicker">Evidence By Criterion</div>
          <h3 className="section-title">Uploaded evidence and guided forms</h3>
          <p className="section-intro">Click regular categories to filter evidence. Click the two guided criteria to open the member questionnaire forms.</p>
        </div>
        <div className="evidence-register-actions">
          <span>{rowsForActiveCriterion.length}</span>
          {activeCriterion !== "all" && onOpenCriterion ? (
            <button className="ghost compact-btn evidence-workspace-btn" type="button" onClick={() => onOpenCriterion(activeCriterion)}>Open workspace</button>
          ) : null}
        </div>
      </div>
      <div className="evidence-register-layout">
        <aside className="evidence-criterion-rail" role="tablist" aria-label="Evidence criterion tabs">
          {criterionOptions.map((criterion) => (
            (() => {
              const guidedFormLabel = GUIDED_MEMBER_CRITERION_FORM_LABELS[criterion.code];
              return (
                <button
                  key={criterion.code}
                  type="button"
                  className={`${activeCriterion === criterion.code ? "active" : ""} ${guidedFormLabel ? "guided-form-criterion" : ""}`}
                  onClick={() => guidedFormLabel && onOpenCriterion ? onOpenCriterion(criterion.code) : setActiveCriterion(criterion.code)}
                  style={{ "--category-accent": criterion.code === "all" ? "var(--green)" : criterionAccent(criterion.code) }}
                  title={guidedFormLabel || `Show ${criterion.name || criterion.code} evidence`}
                >
                  <span>
                    {criterion.name || criterion.code}
                    {guidedFormLabel ? <em className="evidence-criterion-action">{guidedFormLabel}</em> : null}
                  </span>
                  <strong>{criterion.code === "all" ? rows.length : evidenceCounts[criterion.code] || 0}</strong>
                </button>
              );
            })()
          ))}
        </aside>
        <div className="evidence-register-sheet">
          <div className="evidence-register-subhead">
            <strong>{activeCriterionLabel}</strong>
            <span>{rowsForActiveCriterion.length} uploaded</span>
          </div>
          <div className="evidence-register-table">
            <div className="evidence-register-head">
              <span>Category</span>
              <span>Evidence</span>
              <span>Uploaded</span>
              <span>Type</span>
              <span>Action</span>
            </div>
            {rowsForActiveCriterion.map((item) => (
              <article
                key={item.id || `${item.criterion_code}_${item.file_name}_${item.created_at}`}
                className="evidence-register-row"
                style={{ "--category-accent": criterionAccent(item.criterion_code) }}
              >
                <div className="evidence-register-cell">
                  <span className="evidence-register-category">{item.categoryLabel}</span>
                </div>
                <div className="evidence-register-cell evidence-register-name">
                  {item.open_url ? <a href={item.open_url} target="_blank" rel="noreferrer">{item.evidenceLabel}</a> : <span>{item.evidenceLabel}</span>}
                </div>
                <div className="evidence-register-cell">
                  <span>{formatDateTime(item.created_at)}</span>
                </div>
                <div className="evidence-register-cell">
                  <span>{item.documentType}</span>
                </div>
                <div className="evidence-register-cell">
                  <button className="ghost compact-btn compact-link-btn" type="button" onClick={() => onOpenCriterion?.(item.criterion_code)}>
                    Review
                  </button>
                </div>
              </article>
            ))}
          </div>
          {!rowsForActiveCriterion.length ? <p className="empty-state evidence-register-empty">No uploaded evidence in this criterion yet.</p> : null}
        </div>
      </div>
    </section>
  );
}

function MemberGeneralWorkspacePanel({ criteria = [], evidence = [], criteriaByCode = {}, onOpenCriterion, onBack }) {
  const rows = buildMemberEvidenceRegister(evidence, criteriaByCode);
  const visibleCriteria = (criteria.length ? criteria : Object.values(criteriaByCode || {})).filter((criterion) => criterion.code);
  const populatedCodes = Array.from(new Set(rows.map((item) => item.criterion_code || "other")));
  const codes = Array.from(new Set(["all", ...visibleCriteria.map((item) => item.code), ...populatedCodes])).slice(0, 9);
  const firstWorkspaceCriterion = visibleCriteria.find((item) => item.code && item.code !== "all")?.code || populatedCodes.find((code) => code && code !== "all") || "";
  const columns = codes.map((code) => {
    const files = code === "all" ? rows.slice(0, 4) : rows.filter((item) => (item.criterion_code || "other") === code).slice(0, 4);
    return {
      code,
      name: code === "all" ? "Root" : (criteriaByCode[code]?.name || visibleCriteria.find((item) => item.code === code)?.name || String(code).replaceAll("_", " ")),
      files,
    };
  });
  return (
    <section className="workspace-page member-drive-page">
      <div className="workspace-top">
        <div>
          <div className="section-kicker">Evidence Workspace</div>
          <h2>Drive-like evidence folders</h2>
          <p>Organize files and folders by EB1A criterion.</p>
        </div>
        <button className="ghost compact-btn" type="button" onClick={onBack}>Back</button>
      </div>
      <div className="workspace-toolbar drive-toolbar">
        <input className="search-input" value="" readOnly placeholder="Search folders and files across your evidence workspace" />
        <div className="drive-toolbar-actions">
          <button className="primary compact-btn" type="button" onClick={() => onOpenCriterion?.("all")}>Upload files</button>
          <button className="ghost compact-btn" type="button" disabled={!firstWorkspaceCriterion} onClick={() => onOpenCriterion?.(firstWorkspaceCriterion)}>New subfolder</button>
        </div>
      </div>
      <div className="workspace-columns">
        {columns.map((column) => (
          <section key={column.code} className="workspace-column" style={{ "--category-accent": criterionAccent(column.code) }}>
            <div className="workspace-column-header">
              <strong>{column.name}</strong>
              <span>{column.files.length} file{column.files.length === 1 ? "" : "s"}</span>
            </div>
            <div className="workspace-file-list">
              {column.files.map((item) => (
                <article key={`${column.code}_${item.id || item.evidenceLabel}`} className="workspace-file-card">
                  <strong>{item.evidenceLabel}</strong>
                  <span>{item.documentType} • {formatDateTime(item.created_at)}</span>
                  <button className="ghost compact-btn compact-link-btn" type="button" onClick={() => onOpenCriterion?.(item.criterion_code)}>Open criterion</button>
                </article>
              ))}
              {!column.files.length ? <p className="empty-state">No files here yet. Use Evidence Intake to upload evidence into this category.</p> : null}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function ExportedNarrativePanel({ title, sectionLabel, items = [], emptyText }) {
  return (
    <section className="panel">
      <div className="section-kicker">{sectionLabel}</div>
      <h3 className="section-title">{title}</h3>
      {items.length ? (
        <div className="task-mini-list">
          {items.map((item) => (
            <article key={item.id} className="task-mini-item">
              <div>
                <strong>{item.project_name || item.contribution_title || "Untitled entry"}</strong>
                <p>{item.organization_name || item.summary_line || "Organization not yet added."}</p>
                <span className="muted-inline">
                  {(item.project_date_label || item.date_label || item.role_date_label || "Dates not added yet")}
                  {item.workflow_status ? ` • ${item.workflow_status}` : ""}
                </span>
              </div>
              <div className="task-mini-meta">
                {item.export_file_name ? <span>{item.export_file_name}</span> : <span>Export pending</span>}
                {item.export_created_at ? <span>{formatUploadedAt(item.export_created_at)}</span> : null}
                {item.export_open_url ? <a href={item.export_open_url} target="_blank" rel="noreferrer">Open export</a> : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty-state">{emptyText}</p>
      )}
    </section>
  );
}

function PetitionAccelerationPanel({ data, busy, compact = false }) {
  if (busy && !data) {
    return (
      <section className="panel petition-accelerator">
        <div className="section-kicker">Petition Accelerator</div>
        <h3 className="section-title">Loading P0/P1 workspace...</h3>
        <p className="empty-state">Gathering claim map, gap scoring, playbooks, QA, and filing package signals.</p>
      </section>
    );
  }
  if (!data) {
    return (
      <section className="panel petition-accelerator">
        <div className="section-kicker">Petition Accelerator</div>
        <h3 className="section-title">P0/P1 workspace not loaded yet</h3>
        <p className="empty-state">Select a member to load the petition acceleration workspace.</p>
      </section>
    );
  }
  const p0 = data.p0 || {};
  const p1 = data.p1 || {};
  const claimMap = p0.claim_map || [];
  const topActions = p0.top_next_actions || [];
  const highGaps = (p0.gap_detector?.gaps || []).filter((item) => item.severity === "high");
  const filingChecks = p1.filing_qa_checklist?.checks || [];
  const requestPacks = p0.criterion_request_packs || [];
  const qaFlags = p1.document_qa?.flags || [];
  const reviewCounts = p0.attorney_review_queue?.counts || {};
  return (
    <section className="panel petition-accelerator">
      <div className="panel-header">
        <div>
          <div className="section-kicker">Petition Accelerator</div>
          <h3 className="section-title">P0/P1 petition acceleration workspace</h3>
          <p className="section-intro">One shared source for claim mapping, member guidance, attorney review, builder playbooks, operations, QA, and filing packaging.</p>
        </div>
        <span className={`status-pill ${data.status === "success" ? "completed" : "in_progress"}`}>{data.status}</span>
      </div>
      <div className="metrics-grid accelerator-metrics">
        <MetricCard label="Evidence" value={data.snapshot?.evidence_count || 0} />
        <MetricCard label="Criteria Started" value={data.snapshot?.criteria_started || 0} />
        <MetricCard label="High Gaps" value={data.snapshot?.high_severity_gaps || 0} />
        <MetricCard label="QA Flags" value={data.snapshot?.qa_flags || 0} />
      </div>
      <div className="accelerator-grid">
        <section className="accelerator-card">
          <div className="section-kicker">Top Next Actions</div>
          {topActions.length ? topActions.map((item, index) => (
            <article key={`${item.action}_${index}`} className="accelerator-row">
              <strong>{item.action}</strong>
              <p>{item.why_it_matters}</p>
              <div className="task-mini-meta">
                <span className={`status-pill ${item.priority === "high" ? "blocked" : "planned"}`}>{item.priority}</span>
                <span>{item.owner}</span>
              </div>
            </article>
          )) : <p className="empty-state">No urgent next actions detected.</p>}
        </section>
        <section className="accelerator-card">
          <div className="section-kicker">Claim Map</div>
          <div className="accelerator-table">
            {claimMap.slice(0, compact ? 5 : 10).map((item) => (
              <article key={item.criterion_code} className="accelerator-table-row">
                <strong>{item.criterion_name}</strong>
                <span>{item.status}</span>
                <span>{item.evidence_count} src</span>
              </article>
            ))}
          </div>
        </section>
        <section className="accelerator-card">
          <div className="section-kicker">Gap Detector</div>
          {highGaps.length ? highGaps.slice(0, 5).map((item) => (
            <article key={item.criterion_code} className="accelerator-row">
              <strong>{item.criterion_name}</strong>
              <p>{item.issues?.slice(0, 2).join(" • ")}</p>
            </article>
          )) : <p className="empty-state">No high-severity gaps surfaced.</p>}
        </section>
        <section className="accelerator-card">
          <div className="section-kicker">Filing QA</div>
          {filingChecks.slice(0, 6).map((item) => (
            <article key={item.item} className="accelerator-table-row">
              <strong>{item.item}</strong>
              <span className={`status-pill ${item.status === "pass" ? "completed" : item.status === "fail" ? "blocked" : "planned"}`}>{item.status}</span>
            </article>
          ))}
        </section>
      </div>
      {!compact ? (
        <React.Fragment>
          <div className="accelerator-grid">
            <section className="accelerator-card">
              <div className="section-kicker">Member Request Packs</div>
              {requestPacks.slice(0, 6).map((item) => (
                <article key={item.criterion_code} className="accelerator-row">
                  <strong>{item.criterion_name}</strong>
                  <p>{item.member_prompt}</p>
                  <span>{item.upload_checklist?.join(" • ")}</span>
                </article>
              ))}
            </section>
            <section className="accelerator-card">
              <div className="section-kicker">Recommendation Workspace</div>
              {(p0.recommendation_letter_workspace?.recommended_targets || []).slice(0, 5).map((item) => (
                <article key={item.target_type} className="accelerator-row">
                  <strong>{item.target_type}</strong>
                  <p>{item.purpose}</p>
                  <span>{item.linked_criteria?.join(" • ")}</span>
                </article>
              ))}
              {!(p0.recommendation_letter_workspace?.recommended_targets || []).length ? <p className="empty-state">No recommendation targets needed yet.</p> : null}
            </section>
            <section className="accelerator-card">
              <div className="section-kicker">Review Queue</div>
              <div className="accelerator-table">
                {Object.entries(reviewCounts).map(([stage, count]) => (
                  <article key={stage} className="accelerator-table-row">
                    <strong>{stage.replaceAll("_", " ")}</strong>
                    <span>{count}</span>
                  </article>
                ))}
              </div>
            </section>
            <section className="accelerator-card">
              <div className="section-kicker">Document QA</div>
              {qaFlags.slice(0, 5).map((item, index) => (
                <article key={`${item.type}_${index}`} className="accelerator-row">
                  <strong>{item.message}</strong>
                  <p>{item.recommended_fix}</p>
                  <span className={`status-pill ${item.severity === "high" ? "blocked" : item.severity === "medium" ? "planned" : "completed"}`}>{item.severity}</span>
                </article>
              ))}
              {!qaFlags.length ? <p className="empty-state">No document QA flags detected.</p> : null}
            </section>
          </div>
          <div className="accelerator-grid">
            <section className="accelerator-card">
              <div className="section-kicker">Exhibit Assembly</div>
              <p>{p1.exhibit_assembly_manager?.exhibits?.length || 0} exhibit(s) indexed for package order.</p>
              <div className="accelerator-table">
                {(p1.exhibit_assembly_manager?.exhibits || []).slice(0, 6).map((item) => (
                  <article key={item.exhibit_number} className="accelerator-table-row">
                    <strong>{item.exhibit_number}</strong>
                    <span>{item.criterion_name}</span>
                    <span>{item.file_name}</span>
                  </article>
                ))}
              </div>
            </section>
            <section className="accelerator-card">
              <div className="section-kicker">USCIS Packager</div>
              {(p1.uscis_upload_packager?.bundles || []).map((bundle) => (
                <article key={bundle.bundle_name} className="accelerator-row">
                  <strong>{bundle.bundle_name}</strong>
                  <p>{bundle.exhibits?.length || 0} exhibit(s) • limit {p1.uscis_upload_packager?.bundle_size_limit_mb || 24} MB</p>
                </article>
              ))}
            </section>
          </div>
        </React.Fragment>
      ) : null}
    </section>
  );
}

function shortDisplayDate(value, fallback = "TBD") {
  if (!value) return fallback;
  const date = new Date(String(value).replace(" ", "T"));
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "2-digit", year: "numeric" });
}

function daysBetween(start, end) {
  const startDate = new Date(String(start || "").replace(" ", "T"));
  const endDate = new Date(String(end || "").replace(" ", "T"));
  if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return 0;
  return Math.round((endDate.getTime() - startDate.getTime()) / 86400000);
}

function memberTimelineStatusMeta(status) {
  if (["late", "red", "at_risk", "blocked"].includes(status)) return { label: "At Risk - needs action", className: "red" };
  if (["amber", "watch", "planned"].includes(status)) return { label: "Watch - action helpful", className: "blue" };
  return { label: "On Track", className: "green" };
}

function FilingTimelinePanel({ data, busy = false, compact = false, memberCommitment = false, dashboard = null, onOpenIntake = null }) {
  if (busy && !data) {
    return (
      <section className="panel filing-timeline-panel">
        <div className="section-kicker">{memberCommitment ? "Original Commitment Timeline" : "Petition Timeline"}</div>
        <h3 className="section-title">Loading filing timeline...</h3>
      </section>
    );
  }
  if (!data) {
    return (
      <section className="panel filing-timeline-panel">
        <div className="section-kicker">{memberCommitment ? "Original Commitment Timeline" : "Petition Timeline"}</div>
        <h3 className="section-title">{memberCommitment ? "Where you stand today" : "Select a member to view timeline"}</h3>
        <p className="empty-state">The timeline appears after member context is available.</p>
      </section>
    );
  }
  const stages = data.stages || [];
  const alerts = data.alerts || [];
  if (memberCommitment) {
    const targetDate = data.summary?.target_filing_date || data.target_filing_date || dashboard?.client?.target_filing_date || stages[stages.length - 1]?.end_date || "";
    const onboardingDate = data.summary?.onboarding_date || data.onboarding_date || dashboard?.client?.onboarding_date || stages[0]?.start_date || "";
    const todayIso = new Date().toISOString().slice(0, 10);
    const totalDays = Math.max(daysBetween(onboardingDate, targetDate), 1);
    const elapsedDays = Math.max(daysBetween(onboardingDate, todayIso), 0);
    const progress = Math.max(3, Math.min(100, Math.round((elapsedDays / totalDays) * 100)));
    const daysRemaining = data.summary?.days_to_target ?? daysBetween(todayIso, targetDate);
    const currentStage = stages.find((stage) => ["current", "in_progress", "active"].includes(stage.status)) || stages.find((stage) => stage.status !== "completed") || stages[0] || {};
    const statusMeta = memberTimelineStatusMeta(data.status || data.risk_level || data.summary?.risk_level);
    const stageRows = stages.length ? stages : [
      { label: "Profile and evidence baseline", start_date: onboardingDate, end_date: targetDate, status: "current", description: "Finish profile confirmation, guided criteria forms, and initial uploads." },
    ];
    const actionText = alerts[0]?.message || "To get back on track: finish profile confirmation, submit Critical Role project details, and upload missing judging thank-you proof by May 15.";
    const isAtRisk = statusMeta.className !== "green";
    return (
      <section className="panel filing-timeline-panel commitment-panel">
        <div className="panel-header">
          <div>
            <div className="section-kicker">Original Commitment Timeline</div>
            <h3 className="section-title">Where you stand today</h3>
            <p className="section-intro">Transparent member-facing timeline comparing the original filing commitment against the current case position. This answers: what was promised, where am I now, and how long until filing?</p>
          </div>
          <span className={`status-pill ${statusMeta.className === "red" ? "blocked" : statusMeta.className === "blue" ? "planned" : "completed"}`}>{statusMeta.label}</span>
        </div>
        <div className="commitment-grid">
          <div className="commitment-stat"><span>Original filing commitment</span><strong>{shortDisplayDate(targetDate)}</strong></div>
          <div className="commitment-stat"><span>Current checkpoint</span><strong>{shortDisplayDate(todayIso)}</strong></div>
          <div className="commitment-stat"><span>Current stage</span><strong>{currentStage.label || currentStage.stage || dashboard?.client?.stage || "Evidence baseline"}</strong></div>
          <div className="commitment-stat"><span>Time remaining</span><strong>{Number.isFinite(Number(daysRemaining)) ? `${Math.max(0, Number(daysRemaining))} days to target filing` : "Target date pending"}</strong></div>
        </div>
        <div className="commitment-rail" style={{ "--progress": `${progress}%`, "--position": `${progress}%` }}>
          <div className="commitment-marker">NOW</div>
        </div>
        <div className="commitment-caption">
          <span>Onboarding: {shortDisplayDate(onboardingDate)}</span>
          <span>Today: {shortDisplayDate(todayIso)}</span>
          <span>Target filing: {shortDisplayDate(targetDate)}</span>
        </div>
        <div className="stage-grid">
          <div className="stage-row header"><span>Stage</span><span>Original committed window</span><span>Current status</span><span>What this means for you</span></div>
          {stageRows.map((stage, index) => {
            const stageStatus = stage.status || (index === 0 ? "current" : "upcoming");
            const accent = stage.accent || (["current", "in_progress", "active"].includes(stageStatus) ? "var(--green)" : stageStatus === "rfe" ? "var(--plum)" : index <= 2 ? "var(--amber)" : "var(--muted)");
            return (
              <article key={stage.key || stage.label || index} className="stage-row" style={{ "--accent": accent }}>
                <strong>{stage.label || stage.stage || "Timeline stage"}</strong>
                <span>{shortDisplayDate(stage.start_date || stage.window_start)} to {shortDisplayDate(stage.end_date || stage.window_end)}</span>
                <span>{String(stageStatus).replaceAll("_", " ")}</span>
                <span>{stage.description || stage.blurb || "This stage keeps the case moving toward the original filing commitment."}</span>
              </article>
            );
          })}
          {data.rfe_support ? (
            <article className="stage-row" style={{ "--accent": "var(--plum)" }}>
              <strong>{data.rfe_support.label || "RFE support if needed"}</strong>
              <span>{shortDisplayDate(data.rfe_support.start_date)} to {shortDisplayDate(data.rfe_support.end_date)}</span>
              <span>Contingency</span>
              <span>Dotted support window only if USCIS requests more evidence.</span>
            </article>
          ) : null}
        </div>
        {isAtRisk ? (
          <div className="banner warning commitment-action-banner">
            <span>{actionText}</span>
            <button className="ghost compact-btn" type="button" onClick={() => onOpenIntake?.()}>Upload evidence</button>
          </div>
        ) : null}
      </section>
    );
  }
  return (
    <section className="panel filing-timeline-panel">
      <div className="panel-header">
        <div>
          <div className="section-kicker">Petition Timeline</div>
          <h3 className="section-title">Realistic path to filing</h3>
          <p className="section-intro">Built from current readiness, evidence depth, open tasks, project intakes, and profile confirmation.</p>
        </div>
        <span className={`status-pill ${data.status === "late" ? "blocked" : data.status === "at_risk" ? "planned" : "completed"}`}>{data.status?.replaceAll("_", " ")}</span>
      </div>
      <div className="metrics-grid timeline-metrics">
        <MetricCard label="Target Filing" value={data.summary?.target_filing_date || "TBD"} />
        <MetricCard label="Days To Target" value={data.summary?.days_to_target ?? 0} />
        <MetricCard label="Late Stages" value={data.summary?.late_stage_count || 0} />
        <MetricCard label="Alerts" value={data.summary?.alert_count || 0} />
      </div>
      <div className="gantt-chart" style={{ "--stage-count": Math.max(stages.length, 1) }}>
        {stages.map((stage) => (
          <article key={stage.key} className={`gantt-stage ${stage.status}`}>
            <div className="gantt-bar">
              <span>{stage.label}</span>
            </div>
            <small>{stage.start_date} to {stage.end_date}</small>
          </article>
        ))}
        {data.rfe_support ? (
          <article className="gantt-stage rfe">
            <div className="gantt-bar dotted"><span>{data.rfe_support.label}</span></div>
            <small>{data.rfe_support.start_date} to {data.rfe_support.end_date}</small>
          </article>
        ) : null}
      </div>
      {!compact ? (
        <div className="timeline-detail-grid">
          <section className="accelerator-card">
            <div className="section-kicker">Stage Details</div>
            {stages.map((stage) => (
              <article key={`detail_${stage.key}`} className="accelerator-row">
                <strong>{stage.label}</strong>
                <p>{stage.description}</p>
                <div className="task-mini-meta">
                  <span>{stage.owner}</span>
                  <span className={`status-pill ${stage.status === "late" ? "blocked" : stage.status === "completed" ? "completed" : "planned"}`}>{stage.status}</span>
                </div>
              </article>
            ))}
          </section>
          <section className="accelerator-card">
            <div className="section-kicker">Alerts</div>
            {alerts.length ? alerts.map((alert, index) => (
              <article key={`${alert.message}_${index}`} className="accelerator-row">
                <strong>{alert.message}</strong>
                <div className="task-mini-meta">
                  <span>{alert.owner}</span>
                  <span className={`status-pill ${alert.severity === "high" ? "blocked" : "planned"}`}>{alert.severity}</span>
                </div>
              </article>
            )) : <p className="empty-state">No active timeline alerts.</p>}
          </section>
        </div>
      ) : null}
    </section>
  );
}

function ProductBacklogPanel({ backlog, form, busy, onFormChange, onSubmit, onUpdate }) {
  const items = backlog?.items || [];
  return (
    <section className="panel product-backlog-panel">
      <div className="panel-header">
        <div>
          <div className="section-kicker">Product Backlog</div>
          <h3 className="section-title">Feature intake and prioritization</h3>
          <p className="section-intro">Capture enhancements, style changes, new workflows, and supporting screenshots in a format ready for development, testing, and deployment.</p>
        </div>
      </div>
      <div className="metrics-grid">
        {["P0", "P1", "P2", "P3"].map((priority) => <MetricCard key={priority} label={priority} value={backlog?.priority_counts?.[priority] || 0} />)}
      </div>
      <div className="builder-layout" style={{ marginTop: "18px" }}>
        <form className="panel stacked-form" onSubmit={onSubmit}>
          <div className="section-kicker">New Feature Request</div>
          <label>Title<input value={form.title} onChange={(event) => onFormChange("title", event.target.value)} placeholder="Add AI letter approval queue" /></label>
          <div className="form-grid two">
            <label>
              Type
              <select value={form.request_type} onChange={(event) => onFormChange("request_type", event.target.value)}>
                <option value="enhancement">Enhancement</option>
                <option value="new_feature">New feature</option>
                <option value="style">Style/UI</option>
                <option value="workflow">Workflow</option>
                <option value="bug_fix">Bug fix</option>
              </select>
            </label>
            <label>
              Priority
              <select value={form.priority} onChange={(event) => onFormChange("priority", event.target.value)}>
                <option value="P0">P0 - critical</option>
                <option value="P1">P1 - high</option>
                <option value="P2">P2 - normal</option>
                <option value="P3">P3 - later</option>
              </select>
            </label>
          </div>
          <label>Target portals<input value={form.target_portals} onChange={(event) => onFormChange("target_portals", event.target.value)} placeholder="Leader, Attorney, Member" /></label>
          <label>Business value<textarea value={form.business_value} onChange={(event) => onFormChange("business_value", event.target.value)} placeholder="Explain how this speeds petitions, improves quality, or reduces rework." /></label>
          <label>Description<textarea value={form.description} onChange={(event) => onFormChange("description", event.target.value)} placeholder="What should the product do and where should it live?" /></label>
          <label>Acceptance criteria<textarea value={form.acceptance_criteria} onChange={(event) => onFormChange("acceptance_criteria", event.target.value)} placeholder="How will we know this is ready to test and deploy?" /></label>
          <label>Supporting screenshots<input type="file" accept="image/*" multiple onChange={(event) => onFormChange("screenshots", Array.from(event.target.files || []))} /></label>
          <div className="form-actions"><button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Saving..." : "Add To Backlog"}</button></div>
        </form>
        <section className="panel">
          <div className="section-kicker">Prioritized Backlog</div>
          <div className="backlog-table">
            <div className="backlog-row backlog-head"><span>Priority</span><span>Feature</span><span>Status</span><span>Evidence</span></div>
            {items.map((item) => (
              <article key={item.id} className={`backlog-row priority-${item.priority?.toLowerCase()}`}>
                <select value={item.priority} onChange={(event) => onUpdate(item, { priority: event.target.value })}>
                  <option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option>
                </select>
                <div><strong>{item.title}</strong><p>{item.description}</p><small>{item.target_portals} • {item.business_value}</small></div>
                <select value={item.status} onChange={(event) => onUpdate(item, { status: event.target.value })}>
                  <option value="backlog">Backlog</option><option value="ready">Ready</option><option value="in_progress">In progress</option><option value="testing">Testing</option><option value="deployed">Deployed</option><option value="blocked">Blocked</option>
                </select>
                <span>{item.attachment_count || 0} screenshot(s)</span>
              </article>
            ))}
            {!items.length ? <p className="empty-state">No feature requests captured yet.</p> : null}
          </div>
        </section>
      </div>
    </section>
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
            <h3 className="section-title">Excel-style bug backlog</h3>
            <p className="section-intro">Log issues with priority, status, reproduction notes, screenshots, and enough context for developers to retest quickly.</p>
          </div>
          <button className="primary compact-btn" type="button" onClick={() => document.querySelector(".issue-entry-row input")?.focus()}>Log Issue</button>
        </div>
        <p className="mini-note">AWS mirror: {backlog?.aws_table_name || "ascend_product_issue_logs"} • {backlog?.aws_region || "us-east-2"}</p>
        <div className="admin-count-strip">
          {["P0", "P1", "P2", "P3"].map((priority) => (
            <span key={priority}><strong>{priority}</strong>{backlog?.priority_counts?.[priority] || 0}</span>
          ))}
          {ISSUE_STATUS_OPTIONS.slice(0, 6).map((status) => (
            <span key={status.value}><strong>{status.label}</strong>{backlog?.status_counts?.[status.value] || (status.value === "new" ? backlog?.status_counts?.open : 0) || 0}</span>
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
            {ISSUE_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
          <input value={form.reported_by} onChange={(event) => onFormChange("reported_by", event.target.value)} placeholder="Reporter" aria-label="Reported by" />
          <input value={form.description} onChange={(event) => onFormChange("description", event.target.value)} placeholder="Short description / reproduction notes" aria-label="Description" />
          <button className="primary compact-btn" type="submit" disabled={busy}>{busy ? "Saving" : "Add row"}</button>
        </form>

        <div className="issue-log-table">
          <div className="issue-log-row issue-log-head"><span>ID</span><span>Issue</span><span>Priority</span><span>Status</span><span>Repro</span></div>
          {items.map((item) => (
            <article key={item.bug_id} className={`issue-log-row priority-${item.priority?.toLowerCase()}`}>
              <div>
                <strong>{item.bug_id}</strong>
                <small>{item.updated_at || item.created_at}</small>
              </div>
              <div>
                <strong>{item.title}</strong>
                <small>{item.portal} / {item.section}</small>
              </div>
              <select value={item.priority} onChange={(event) => onUpdate(item, { priority: event.target.value })}>
                <option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option><option value="P3">P3</option>
              </select>
              <select value={item.status} onChange={(event) => onUpdate(item, { status: event.target.value })}>
                {ISSUE_STATUS_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                {["open", "blocked", "closed"].includes(item.status) ? <option value={item.status}>{issueStatusLabel(item.status)}</option> : null}
              </select>
              <div>
                <strong>{item.description}</strong>
                <small>{item.reported_by || "Admin"} • AWS {item.aws_sync_status || "pending"}</small>
                <button className="danger compact-btn" type="button" onClick={() => onRemove(item)}>Remove</button>
              </div>
            </article>
          ))}
          {!items.length ? <p className="empty-state">No bug logs captured yet. Use the add row above to start the registry.</p> : null}
        </div>
      </div>
    </section>
  );
}

function RecommendationLetterPanel({
  workspace,
  form,
  busy,
  activeLetterId,
  onFieldChange,
  onSubmit,
  onSelectLetter,
  onApprove,
  onSend,
}) {
  const projects = workspace?.projects || [];
  const letters = workspace?.letters || [];
  const selectedLetter = letters.find((item) => item.id === activeLetterId) || letters[0] || null;
  const letter = selectedLetter?.letter || null;
  return (
    <React.Fragment>
      <header className="hero endeavor-hero recommendation-hero">
        <p className="eyebrow">Recommendation Letters</p>
        <div className="endeavor-hero-row">
          <div>
            <h1>{workspace?.member?.display_name || "Selected member"} project-specific letters</h1>
            <p>Select a member, project, recommender, and letter type before generating a document draft.</p>
          </div>
          <div className="endeavor-stat-strip" aria-label="Recommendation letter summary">
            <span><strong>{projects.length}</strong> projects</span>
            <span><strong>{letters.length}</strong> drafts</span>
            <span><strong>{letters.filter((item) => item.status === "sent_to_member").length}</strong> sent</span>
          </div>
        </div>
      </header>

      <section className="panel recommendation-panel">
        <div className="panel-header">
          <div>
            <div className="section-kicker">Recommendation Letters</div>
            <h3 className="section-title">Independent and dependent letter generator</h3>
            <p className="section-intro">Select a member, project, recommender, and letter type before generating a document draft.</p>
          </div>
          {selectedLetter ? <span className={`status-pill ${selectedLetter.status === "sent_to_member" ? "completed" : selectedLetter.status === "approved" ? "planned" : "in_progress"}`}>{selectedLetter.status?.replaceAll("_", " ")}</span> : null}
        </div>

        <div className="recommendation-workspace">
          <form className="stacked-form recommendation-form" onSubmit={onSubmit}>
            <div className="recommendation-form-head">
              <div>
                <div className="section-kicker">Prompt</div>
                <h4>Select project and confirm facts</h4>
              </div>
              <button className="primary compact-btn" type="submit" disabled={busy || !projects.length}>{busy ? "Generating..." : "Generate Letter"}</button>
            </div>
            <div className="recommendation-field-grid">
              <label>
                Letter type
                <select value={form.letter_kind} onChange={(event) => onFieldChange("letter_kind", event.target.value)}>
                  <option value="independent">Independent recommendation</option>
                  <option value="dependent">Dependent/project recommendation</option>
                </select>
              </label>
              <label>
                Project
                <select value={`${form.project_type}|${form.project_id}`} onChange={(event) => {
                  const [projectType, projectId] = event.target.value.split("|");
                  onFieldChange("project_type", projectType || "");
                  onFieldChange("project_id", projectId || "");
                }}>
                  <option value="|">Select Critical Role or Original Contribution project</option>
                  {projects.map((project) => (
                    <option key={`${project.project_type}_${project.id}`} value={`${project.project_type}|${project.id}`}>
                      {project.criterion_name}: {project.title}
                    </option>
                  ))}
                </select>
              </label>
              <label>Recommender name<input value={form.recommender_name} onChange={(event) => onFieldChange("recommender_name", event.target.value)} /></label>
              <label>Recommender title<input value={form.recommender_title} onChange={(event) => onFieldChange("recommender_title", event.target.value)} /></label>
              <label className="wide">Recommender organization<input value={form.recommender_organization} onChange={(event) => onFieldChange("recommender_organization", event.target.value)} /></label>
              <label>Relationship / credibility<textarea value={form.recommender_relationship} onChange={(event) => onFieldChange("recommender_relationship", event.target.value)} /></label>
              <label>Prompt facts<textarea value={form.facts_to_confirm} onChange={(event) => onFieldChange("facts_to_confirm", event.target.value)} placeholder="Emphasize project ownership, measurable impact, and why the member's role was not routine." /></label>
              <label>Independence guidance<textarea value={form.independence_guidance} onChange={(event) => onFieldChange("independence_guidance", event.target.value)} /></label>
              <label>Attorney strategy notes<textarea value={form.attorney_strategy_notes} onChange={(event) => onFieldChange("attorney_strategy_notes", event.target.value)} /></label>
            </div>
            {!projects.length ? <p className="empty-state">No submitted Critical Role or Original Contribution projects are available yet. Ask the member to submit one first.</p> : null}
          </form>

          <section className="recommendation-review-column">
          <div className="panel-header">
            <div><div className="section-kicker">Generated Draft Preview</div><h3 className="section-title">Recommendation Letter Draft</h3></div>
          </div>
          <div className="recommendation-letter-list">
            {letters.map((item) => (
              <button key={item.id} type="button" className={`thread-card recommendation-letter-row ${selectedLetter?.id === item.id ? "active" : ""}`} onClick={() => onSelectLetter(item.id)}>
                <strong>{item.letter?.title || "Recommendation letter"}</strong>
                <p>{item.project_type?.replaceAll("_", " ")} • {item.letter_kind}</p>
                <div className="task-mini-meta"><span>{formatUploadedAt(item.created_at)}</span><span>{item.status}</span></div>
              </button>
            ))}
            {!letters.length ? <p className="empty-state">Generate a recommendation letter to begin attorney review.</p> : null}
          </div>
          {letter ? (
            <section className="letter-preview">
              <div className="letter-actions">
                <a className="ghost compact-btn" href={`${API_URL}${selectedLetter.download_url}`} target="_blank" rel="noreferrer">Download</a>
                <button className="ghost compact-btn" type="button" onClick={() => onApprove(selectedLetter.id)} disabled={selectedLetter.status === "approved" || selectedLetter.status === "sent_to_member"}>Approve</button>
                <button className="primary compact-btn" type="button" onClick={() => onSend(selectedLetter.id)} disabled={selectedLetter.status !== "approved"}>Push To Member</button>
              </div>
              <div className="letter-paper">
                <p className="letter-title">{letter.title}</p>
                <p>{letter.date_line}</p>
                <p>{letter.addressee_line}</p>
                <p>{letter.re_line}</p>
                <p>{letter.salutation}</p>
                <p>{letter.opening_paragraph}</p>
                {(letter.sections || []).map((section, index) => (
                  <div key={`rec_section_${index}`}>
                    {section.heading ? <p className="letter-heading">{section.heading}</p> : null}
                    <p>{section.body}</p>
                  </div>
                ))}
                <p>{letter.closing_paragraph}</p>
                <p className="letter-signature">{letter.signature_line}</p>
              </div>
            </section>
          ) : null}
        </section>
        </div>
      </section>
    </React.Fragment>
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

function App() {
  const initialRoute = readPortalRoute();
  const initialStoredMember = readStoredMember();
  const initialPortalRole = normalizePortalRole(initialRoute.portal);
  const [authMode, setAuthMode] = useState(initialPortalRole || normalizePortalRole(initialStoredMember?.role) || "member");
  const [authReady, setAuthReady] = useState(false);
  const [authMember, setAuthMember] = useState(initialStoredMember);
  const [builderDashboard, setBuilderDashboard] = useState(null);
  const [builderMembers, setBuilderMembers] = useState([]);
  const [memberSearchQuery, setMemberSearchQuery] = useState("");
  const [builderMemberDetail, setBuilderMemberDetail] = useState(null);
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
  const [criticalRoleProjects, setCriticalRoleProjects] = useState([]);
  const [criticalRoleForm, setCriticalRoleForm] = useState(emptyCriticalRoleProjectForm());
  const [activeCriticalRoleId, setActiveCriticalRoleId] = useState("");
  const [criticalRoleBusy, setCriticalRoleBusy] = useState(false);
  const [originalContributions, setOriginalContributions] = useState([]);
  const [originalContributionForm, setOriginalContributionForm] = useState(emptyOriginalContributionForm());
  const [activeOriginalContributionId, setActiveOriginalContributionId] = useState("");
  const [originalContributionBusy, setOriginalContributionBusy] = useState(false);
  const [memberRewriteDrafts, setMemberRewriteDrafts] = useState({});
  const [memberRewriteBusyKey, setMemberRewriteBusyKey] = useState("");
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
  const [uploadBusy, setUploadBusy] = useState(false);
  const [duplicateState, setDuplicateState] = useState(null);
  const [intakeSort, setIntakeSort] = useState({ key: "uploaded", direction: "desc" });

  const [newFolderName, setNewFolderName] = useState("");
  const [newFolderParent, setNewFolderParent] = useState("");
  const [newFolderColor, setNewFolderColor] = useState("Emerald");
  const [selectedFolderId, setSelectedFolderId] = useState("");
  const [folderForm, setFolderForm] = useState({ name: "", color: "Emerald" });
  const [workspaceUploadBusy, setWorkspaceUploadBusy] = useState(false);
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
  const [registrationToken, setRegistrationToken] = useState(initialRoute.registrationToken || "");
  const [registrationInfo, setRegistrationInfo] = useState(null);
  const [registrationForm, setRegistrationForm] = useState({ password: "", confirm_password: "", phone: "" });
  const [registrationBusy, setRegistrationBusy] = useState(false);
  const [productBacklog, setProductBacklog] = useState({ items: [], priority_counts: {}, status_counts: {} });
  const [featureRequestForm, setFeatureRequestForm] = useState(emptyFeatureRequestForm());
  const [featureRequestBusy, setFeatureRequestBusy] = useState(false);
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
  const [petitionAcceleration, setPetitionAcceleration] = useState(null);
  const [petitionAccelerationBusy, setPetitionAccelerationBusy] = useState(false);
  const [endeavorPromptForm, setEndeavorPromptForm] = useState(emptyEndeavorPromptForm());
  const [endeavorDraft, setEndeavorDraft] = useState(null);
  const [endeavorBusy, setEndeavorBusy] = useState(false);
  const [endeavorLetterView, setEndeavorLetterView] = useState(false);
  const [filingTimeline, setFilingTimeline] = useState(null);
  const [filingTimelineBusy, setFilingTimelineBusy] = useState(false);
  const [recommendationWorkspace, setRecommendationWorkspace] = useState(null);
  const [recommendationPromptForm, setRecommendationPromptForm] = useState(emptyRecommendationPromptForm());
  const [recommendationBusy, setRecommendationBusy] = useState(false);
  const [activeRecommendationLetterId, setActiveRecommendationLetterId] = useState("");
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
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth);
  const [sidebarResizing, setSidebarResizing] = useState(false);
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth);
  const lastActivitySignatureRef = useRef("");
  const routeSyncRef = useRef({ initialized: false, applying: false, lastUrl: "" });
  const routeNoticeRef = useRef(null);
  const sidebarWidthRef = useRef(sidebarWidth);
  const workspaceFileInputRef = useRef(null);

  useEffect(() => {
    sidebarWidthRef.current = sidebarWidth;
  }, [sidebarWidth]);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidth));
  }, [sidebarWidth]);

  useEffect(() => {
    function handleResize() {
      setViewportWidth(window.innerWidth);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!sidebarResizing) return undefined;
    function handlePointerMove(event) {
      const nextWidth = Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, event.clientX));
      if (nextWidth !== sidebarWidthRef.current) {
        setSidebarWidth(nextWidth);
      }
    }
    function handlePointerUp() {
      setSidebarResizing(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp);
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
    };
  }, [sidebarResizing]);

  function startSidebarResize(event) {
    if (viewportWidth <= DESKTOP_SIDEBAR_BREAKPOINT) return;
    event.preventDefault();
    setSidebarResizing(true);
  }

  const sidebarResizeEnabled = viewportWidth > DESKTOP_SIDEBAR_BREAKPOINT;
  const shellStyle = sidebarResizeEnabled ? { "--sidebar-width": `${sidebarWidth}px` } : undefined;
  const sidebarResizer = sidebarResizeEnabled ? (
    <div
      className={`sidebar-resizer${sidebarResizing ? " active" : ""}`}
      onMouseDown={startSidebarResize}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
    />
  ) : null;

  const criteriaByCode = useMemo(() => Object.fromEntries((criteriaList || dashboard?.criteria || []).map((item) => [item.code, item])), [criteriaList, dashboard]);
  const actionItems = useMemo(() => buildActionItems(dashboard?.criteria || [], evidenceItems), [dashboard, evidenceItems]);
  const memberIntakeHistory = useMemo(() => {
    const items = [...(evidenceItems || [])];
    const directionFactor = intakeSort.direction === "asc" ? 1 : -1;
    items.sort((left, right) => {
      let result = 0;
      if (intakeSort.key === "evidence") {
        result = compareText(left.title || left.file_name, right.title || right.file_name);
      } else if (intakeSort.key === "category") {
        result = compareText(criteriaByCode[left.criterion_code]?.name || left.criterion_code, criteriaByCode[right.criterion_code]?.name || right.criterion_code);
      } else if (intakeSort.key === "type") {
        result = compareText(left.document_type || "Other", right.document_type || "Other");
      } else {
        result = compareText(left.created_at || "", right.created_at || "");
      }
      if (result === 0) {
        result = compareText(left.title || left.file_name, right.title || right.file_name);
      }
      return result * directionFactor;
    });
    return items;
  }, [criteriaByCode, evidenceItems, intakeSort]);
  const folderOptions = useMemo(() => [{ value: "", label: "Root" }, ...((workspace?.folders || []).map((folder) => ({ value: folder.id, label: folder.path })))], [workspace]);
  const selectedWorkspaceFolder = useMemo(() => (selectedFolderId ? (workspace?.folders || []).find((folder) => folder.id === selectedFolderId) || null : null), [workspace, selectedFolderId]);
  const driveRows = useMemo(() => buildDriveRows(workspace, selectedFolderId, workspaceQuery), [workspace, selectedFolderId, workspaceQuery]);
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
        if (portalSection === "endeavor") return "Endeavor Letter Generator";
        if (portalSection === "recommendations") return "Recommendation Letters";
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
      if (portalSection === "invite") return "Invite Member";
      if (portalSection === "members") return "Member Review";
      if (portalSection === "risks") return "Risk & Bottlenecks";
      if (portalSection === "capacity") return "Team Capacity";
      if (portalSection === "timeline") return "Delivery Timeline";
      if (portalSection === "backlog") return "Product Backlog";
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
      if (portalSection === "endeavor") return "Endeavor Letter Generator";
      if (portalSection === "recommendations") return "Recommendation Letters";
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

  function toggleIntakeSort(key) {
    setIntakeSort((current) => current.key === key
      ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
      : { key, direction: key === "uploaded" ? "desc" : "asc" });
  }

  function intakeSortLabel(key) {
    if (intakeSort.key !== key) return "↕";
    return intakeSort.direction === "asc" ? "↑" : "↓";
  }

  function actorParams(member = authMember) {
    if (!member) return {};
    return {
      actor_role: member.role,
      actor_email: member.role === "member" ? "" : (member.email || ""),
      actor_client_id: member.role === "member" ? (member.client_id || "") : "",
    };
  }

  async function logPortalActivity(eventType, messageText, metadata = {}) {
    if (!authMember) return;
    try {
      await sendJson("/api/activity-events", {
        ...actorParams(authMember),
        event_type: eventType,
        message: messageText,
        endpoint: window.location.pathname || "/",
        related_client_id: supportRelatedClientId || "",
        metadata: {
          section: supportSectionLabel,
          portal_section: portalSection,
          view_type: view.type,
          leader_perspective: leaderPerspective,
          selected_member_id: selectedBuilderMemberId || "",
          current_url: window.location.href,
          ...browserTimingSnapshot(),
          ...metadata,
        },
      });
    } catch (_error) {
      // Activity logging should never block the portal workflow.
    }
  }

  useEffect(() => {
    if (!authMember) return;
    const signature = JSON.stringify({
      role: authMember.role,
      section: supportSectionLabel,
      portalSection: portalSection,
      viewType: view.type,
      criterionCode: view.criterionCode,
      leaderPerspective,
      selectedMemberId: selectedBuilderMemberId || "",
    });
    if (lastActivitySignatureRef.current === signature) return;
    lastActivitySignatureRef.current = signature;
    logPortalActivity("page_view", `Viewed ${supportSectionLabel}.`, {
      criterion_code: view.criterionCode || "",
    });
  }, [authMember, supportSectionLabel, portalSection, view.type, view.criterionCode, leaderPerspective, selectedBuilderMemberId]);

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

  function syncCriterionUrl(code) {
    const url = new URL(window.location.href);
    if (code) {
      url.searchParams.set("criterion", code);
    } else {
      url.searchParams.delete("criterion");
      url.searchParams.delete("folder");
    }
    window.history.replaceState({}, "", url.toString());
  }

  function buildRouteUrl(snapshot) {
    const url = new URL(window.location.href);
    ["portal", "page", "section", "perspective", "member", "criterion", "folder", "registration", "invite"].forEach((key) => url.searchParams.delete(key));
    if (snapshot.portal === "member" && snapshot.page && !snapshot.registrationToken) {
      url.pathname = `/member/${memberPagePathSegment(snapshot.page)}`;
      if (snapshot.criterion) url.searchParams.set("criterion", snapshot.criterion);
      if (snapshot.folderId) url.searchParams.set("folder", snapshot.folderId);
      return url.toString();
    }
    if (PATH_PORTALS.has(snapshot.portal) && snapshot.section && !snapshot.registrationToken) {
      url.pathname = `/${snapshot.portal}/${portalSectionPathSegment(snapshot.portal, snapshot.section)}`;
      if (snapshot.perspective && snapshot.portal === "leader" && snapshot.perspective !== "leader") url.searchParams.set("perspective", snapshot.perspective);
      if (snapshot.memberId) url.searchParams.set("member", snapshot.memberId);
      return url.toString();
    }
    url.pathname = "/";
    if (snapshot.portal) url.searchParams.set("portal", snapshot.portal);
    if (snapshot.page) url.searchParams.set("page", snapshot.page);
    if (snapshot.section) url.searchParams.set("section", snapshot.section);
    if (snapshot.perspective) url.searchParams.set("perspective", snapshot.perspective);
    if (snapshot.memberId) url.searchParams.set("member", snapshot.memberId);
    if (snapshot.criterion) url.searchParams.set("criterion", snapshot.criterion);
    if (snapshot.folderId) url.searchParams.set("folder", snapshot.folderId);
    if (snapshot.registrationToken) url.searchParams.set("registration", snapshot.registrationToken);
    return url.toString();
  }

  function currentRouteSnapshot() {
    const portal = normalizePortalRole(authMember?.role) || normalizePortalRole(authMode) || "member";
    if (!authMember) {
      return { portal: registrationToken ? "member" : portal, registrationToken };
    }
    if (portal === "member") {
      return {
        portal,
        page: MEMBER_VIEW_TYPES.has(view.type) ? view.type : "home",
        criterion: view.type === "workspace" ? view.criterionCode || "" : "",
        folderId: view.type === "workspace" ? selectedFolderId || "" : "",
      };
    }
    if (portal === "leader") {
      return {
        portal,
        perspective: leaderPerspective,
        section: portalSection || "home",
        memberId: selectedBuilderMemberId || "",
      };
    }
    return {
      portal,
      section: portalSection || "home",
      memberId: ["builder", "attorney", "admin"].includes(portal) ? (selectedBuilderMemberId || "") : "",
    };
  }

  function applyRouteSnapshot(snapshot, options = {}) {
    const requestedPortal = normalizePortalRole(snapshot.portal);
    const authenticatedRole = normalizePortalRole(authMember?.role);
    if (authMember && requestedPortal && requestedPortal !== authenticatedRole) {
      clearAuth();
      clearAssistantSessions();
      setAuthMember(null);
      setAuthMode(requestedPortal);
      setLoading(false);
      routeNoticeRef.current = {
        type: "error",
        text: `Please sign in with ${portalMeta(requestedPortal).label} credentials to open that portal.`,
      };
      setMessage(routeNoticeRef.current);
      return;
    }
    const role = options.role || authenticatedRole || requestedPortal || normalizePortalRole(authMode) || "member";
    if (!authMember && requestedPortal) {
      setAuthMode(requestedPortal);
    }
    if (snapshot.registrationToken) {
      setRegistrationToken(snapshot.registrationToken);
      setAuthMode("member");
    } else if (!authMember) {
      setRegistrationToken("");
    }
    if (role === "member") {
      const requestedPage = String(snapshot.page || "").trim();
      const normalizedPage = MEMBER_PAGE_ALIASES[requestedPage] || requestedPage;
      const hasKnownPage = MEMBER_VIEW_TYPES.has(normalizedPage);
      const nextPage = hasKnownPage ? normalizedPage : (snapshot.criterion ? "workspace" : "home");
      if (requestedPage && !hasKnownPage) {
        routeNoticeRef.current = {
          type: "error",
          text: `Page "${requestedPage}" was not found. Opened ${snapshot.criterion ? "the requested evidence workspace" : "Member Home"} instead.`,
        };
      }
      setView({ type: nextPage, criterionCode: nextPage === "workspace" ? snapshot.criterion || "" : "" });
      setSelectedFolderId(nextPage === "workspace" ? snapshot.folderId || "" : "");
      return;
    }
    if (role === "leader") {
      const nextPerspective = LEADER_PERSPECTIVES.has(snapshot.perspective) ? snapshot.perspective : "leader";
      const requestedSection = normalizePortalSection("leader", snapshot.section);
      setLeaderPerspective(nextPerspective);
      const validLeaderSections = nextPerspective === "attorney" ? ATTORNEY_SECTIONS : nextPerspective === "builder" ? BUILDER_SECTIONS : LEADER_EXEC_SECTIONS;
      setPortalSection(validLeaderSections.has(requestedSection) ? requestedSection : "home");
      setSelectedBuilderMemberId(snapshot.memberId || "");
      return;
    }
    if (role === "builder") {
      const requestedSection = normalizePortalSection("builder", snapshot.section);
      setPortalSection(BUILDER_SECTIONS.has(requestedSection) ? requestedSection : "home");
      setSelectedBuilderMemberId(snapshot.memberId || "");
      return;
    }
    if (role === "attorney") {
      const requestedSection = normalizePortalSection("attorney", snapshot.section);
      setPortalSection(ATTORNEY_SECTIONS.has(requestedSection) ? requestedSection : "home");
      setSelectedBuilderMemberId(snapshot.memberId || "");
      return;
    }
    if (role === "admin") {
      const requestedSection = normalizePortalSection("admin", snapshot.section);
      setPortalSection(ADMIN_SECTIONS.has(requestedSection) ? requestedSection : "home");
      setSelectedBuilderMemberId(snapshot.memberId || "");
    }
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
      const nextCriticalProjects = profileData.critical_role_projects || [];
      setCriticalRoleProjects(nextCriticalProjects);
      if (nextCriticalProjects.length) {
        const initialProject = nextCriticalProjects.find((item) => item.id === activeCriticalRoleId) || nextCriticalProjects[0];
        setActiveCriticalRoleId(initialProject.id);
        setCriticalRoleForm(hydrateCriticalRoleProject(initialProject));
      } else {
        setActiveCriticalRoleId("");
        setCriticalRoleForm(emptyCriticalRoleProjectForm());
      }
      const nextOriginalContributions = profileData.original_contribution_entries || [];
      setOriginalContributions(nextOriginalContributions);
      if (nextOriginalContributions.length) {
        const initialEntry = nextOriginalContributions.find((item) => item.id === activeOriginalContributionId) || nextOriginalContributions[0];
        setActiveOriginalContributionId(initialEntry.id);
        setOriginalContributionForm(hydrateOriginalContribution(initialEntry));
      } else {
        setActiveOriginalContributionId("");
        setOriginalContributionForm(emptyOriginalContributionForm());
      }
      if (!manualCategory && dashboardData.criteria.length) setManualCategory(dashboardData.criteria[0].code);
      if (!manualDocumentType) setManualDocumentType("Other");
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
      const requestedMemberId = memberId || "";
      const rosterMemberIds = new Set(roster.map((item) => item.client_id));
      const activeMemberId = requestedMemberId && rosterMemberIds.has(requestedMemberId) ? requestedMemberId : roster[0]?.client_id || "";
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
          builder_id: item.builder_id || "",
          builder_name: item.builder_name || "",
          builder_email: item.builder_email || "",
          attorney_id: item.attorney_id || "",
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
      const [opsData, issueData, costData, membersData, criteriaData] = await Promise.all([
        getJson("/api/admin/operations"),
        getJson("/api/admin/issue-log"),
        getJson("/api/admin/costs"),
        getJson("/api/builder/members"),
        getJson("/api/criteria"),
      ]);
      const roster = membersData.length ? membersData : [];
      const readinessTotal = roster.reduce((sum, item) => sum + Number(item.readiness_score || 0), 0);
      const activeTasks = roster.reduce((sum, item) => sum + Number(item.open_task_count || 0), 0);
      const adminBuilderSummary = {
        metrics: {
          member_count: roster.length,
          active_tasks: activeTasks,
          avg_readiness: roster.length ? Math.round(readinessTotal / roster.length) : 0,
          opportunity_count: 0,
        },
        members: roster,
      };
      setAdminDashboard(opsData);
      setAdminIssueLog(issueData);
      setAdminCosts(costData);
      setBuilderDashboard(adminBuilderSummary);
      setBuilderMembers(roster);
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
    const routeSnapshot = readPortalRoute();
    const requestedPortal = normalizePortalRole(routeSnapshot.portal);
    const routeMemberId = routeSnapshot.memberId || "";
    const routePerspective = LEADER_PERSPECTIVES.has(routeSnapshot.perspective) ? routeSnapshot.perspective : "leader";
    const token = authToken();
    if (!token) {
      setAuthReady(true);
      setLoading(false);
      return;
    }
    try {
      const stored = readStoredMember();
      const role = normalizePortalRole(stored?.role) || "member";
      if (requestedPortal && requestedPortal !== role) {
        clearAuth();
        clearAssistantSessions();
        setAuthMember(null);
        setAuthMode(requestedPortal);
        setLoading(false);
        setMessage({ type: "error", text: `Please sign in with ${portalMeta(requestedPortal).label} credentials to open that portal.` });
        return;
      }
      if (isPreviewRole(role)) {
        setAuthMember(stored);
        setAuthMode(role);
        if (role === "admin") {
          await loadAdminPortal(routeMemberId);
        } else if (role === "leader") {
          setLeaderPerspective(routePerspective);
          await loadLeaderPortal(routeMemberId);
        } else {
          await loadReviewPortals(routeMemberId, stored?.email || "");
        }
        setAuthReady(true);
        return;
      }
      const identity = await getJson(roleConfig(role).mePath);
      setAuthMember(identity);
      setAuthMode(role);
      persistAuth(token, identity);
      if (role === "builder") {
        await loadBuilderDashboard(routeMemberId);
      } else if (role === "leader") {
        setLeaderPerspective(routePerspective);
        await loadLeaderPortal(routeMemberId);
      } else if (role === "attorney") {
        await loadReviewPortals(routeMemberId, identity.email || "");
      } else if (role === "admin") {
        await loadAdminPortal(routeMemberId);
      } else {
        await loadHome();
      }
    } catch (_error) {
      try {
        const identity = await getJson("/api/builder/auth/me");
        setAuthMember(identity);
        setAuthMode("builder");
        persistAuth(token, identity);
        await loadBuilderDashboard(routeMemberId);
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

  async function loadProductBacklog() {
    try {
      const data = await getJson("/api/leader/product-backlog");
      setProductBacklog(data);
    } catch (_error) {
      setProductBacklog({ items: [], priority_counts: {}, status_counts: {} });
    }
  }

  async function submitFeatureRequest(event) {
    event.preventDefault();
    setFeatureRequestBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(featureRequestForm).forEach(([key, value]) => {
        if (key !== "screenshots") formData.set(key, value || "");
      });
      formData.set("actor_email", authMember?.email || "");
      (featureRequestForm.screenshots || []).forEach((file) => formData.append("screenshots", file, file.name));
      const result = await sendForm("/api/leader/product-backlog", formData);
      if (result.ok) {
        setFeatureRequestForm(emptyFeatureRequestForm());
        await loadProductBacklog();
        setMessage({ type: "success", text: "Feature request added to the product backlog." });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not add feature request." });
      }
    } finally {
      setFeatureRequestBusy(false);
    }
  }

  async function updateFeatureRequest(item, updates) {
    const formData = new FormData();
    formData.set("actor_email", authMember?.email || "");
    if (updates.priority) formData.set("priority", updates.priority);
    if (updates.status) formData.set("status", updates.status);
    const result = await sendForm(`/api/leader/product-backlog/${item.id}`, formData, "PATCH");
    if (result.ok) {
      await loadProductBacklog();
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not update backlog item." });
    }
  }

  async function loadFilingTimeline(clientId = selectedBuilderMemberId) {
    const resolvedClientId = clientId || authMember?.client_id || "";
    if (!resolvedClientId || !authMember?.role) return;
    setFilingTimelineBusy(true);
    try {
      const data = await getJson(`/api/members/${resolvedClientId}/filing-timeline`, actorParams(authMember));
      setFilingTimeline(data);
    } catch (_error) {
      setFilingTimeline(null);
    } finally {
      setFilingTimelineBusy(false);
    }
  }

  async function loadRecommendationWorkspace(clientId = selectedBuilderMemberId) {
    if (!clientId || !["attorney", "leader"].includes(authMember?.role)) return;
    try {
      const data = await getJson(`/api/attorney/members/${clientId}/recommendation-letter-workspace`, {
        actor_role: authMember.role === "leader" ? "leader" : "attorney",
        actor_email: authMember.role === "leader" ? "" : (authMember.email || ""),
      });
      setRecommendationWorkspace(data);
      const firstProject = data.projects?.[0];
      setRecommendationPromptForm((current) => ({
        ...emptyRecommendationPromptForm(),
        ...data.default_prompt,
        letter_kind: current.letter_kind || "independent",
        project_type: current.project_type || firstProject?.project_type || "",
        project_id: current.project_id || firstProject?.id || "",
      }));
      setActiveRecommendationLetterId((current) => current || data.letters?.[0]?.id || "");
    } catch (_error) {
      setRecommendationWorkspace(null);
    }
  }

  function updateRecommendationPrompt(field, value) {
    setRecommendationPromptForm((current) => ({ ...current, [field]: value }));
  }

  async function generateRecommendationLetter(event) {
    event.preventDefault();
    if (!selectedBuilderMemberId || !recommendationPromptForm.project_id || !recommendationPromptForm.project_type) {
      setMessage({ type: "error", text: "Choose a Critical Role or Original Contribution project first." });
      return;
    }
    setRecommendationBusy(true);
    setMessage(null);
    try {
      const result = await sendJson("/api/attorney/recommendation-letter-generator", {
        client_id: selectedBuilderMemberId,
        actor_role: authMember.role === "leader" ? "leader" : "attorney",
        actor_email: authMember.role === "leader" ? "" : (authMember.email || ""),
        letter_kind: recommendationPromptForm.letter_kind,
        project_type: recommendationPromptForm.project_type,
        project_id: recommendationPromptForm.project_id,
        prompt_config: recommendationPromptForm,
      });
      if (result.ok) {
        await loadRecommendationWorkspace(selectedBuilderMemberId);
        setActiveRecommendationLetterId(result.payload.letter_record?.id || "");
        setMessage({ type: "success", text: "Recommendation letter generated for attorney review." });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not generate recommendation letter." });
      }
    } finally {
      setRecommendationBusy(false);
    }
  }

  async function approveRecommendationLetter(letterId) {
    const result = await sendJson(`/api/attorney/recommendation-letters/${letterId}`, {
      status: "approved",
      actor_role: authMember.role === "leader" ? "leader" : "attorney",
      actor_email: authMember.role === "leader" ? "" : (authMember.email || ""),
    }, "PATCH");
    if (result.ok) {
      await loadRecommendationWorkspace(selectedBuilderMemberId);
      setMessage({ type: "success", text: "Recommendation letter approved." });
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not approve recommendation letter." });
    }
  }

  async function sendRecommendationLetter(letterId) {
    const result = await sendJson(`/api/attorney/recommendation-letters/${letterId}/send-to-member`, {
      actor_role: authMember.role === "leader" ? "leader" : "attorney",
      actor_email: authMember.role === "leader" ? "" : (authMember.email || ""),
    });
    if (result.ok) {
      await loadRecommendationWorkspace(selectedBuilderMemberId);
      await loadMessageCenterData(authMember);
      setMessage({ type: "success", text: "Recommendation letter sent to member messages." });
    } else {
      setMessage({ type: "error", text: result.payload.error || "Could not send recommendation letter." });
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

  async function loadPetitionAcceleration(clientId = selectedBuilderMemberId) {
    if (!clientId) return;
    setPetitionAccelerationBusy(true);
    try {
      let data;
      if (authMember?.role === "member") {
        data = await getJson("/api/member/petition-acceleration");
      } else if (authMember?.role === "attorney") {
        data = await getJson(`/api/attorney/members/${clientId}/petition-acceleration`, { attorney_email: authMember.email || "" });
      } else if (authMember?.role === "leader") {
        data = await getJson(`/api/leader/members/${clientId}/petition-acceleration`);
      } else if (authMember?.role === "admin") {
        data = await getJson("/api/admin/petition-acceleration", { client_id: clientId });
      } else {
        data = await getJson(`/api/builder/members/${clientId}/petition-acceleration`, { actor_email: authMember?.email || "" });
      }
      setPetitionAcceleration(data);
    } catch (_error) {
      setPetitionAcceleration(null);
    } finally {
      setPetitionAccelerationBusy(false);
    }
  }

  function setEndeavorPromptField(field, value) {
    setEndeavorPromptForm((current) => ({ ...current, [field]: value }));
  }

  async function generateEndeavorLetter(clientId = selectedBuilderMemberId) {
    if (!clientId || !["attorney", "leader"].includes(authMember?.role)) return;
    setEndeavorBusy(true);
    try {
      const result = await sendJson("/api/attorney/endeavor-letter-generator", {
        client_id: clientId,
        actor_role: authMember.role === "leader" ? "leader" : "attorney",
        actor_email: authMember.role === "leader" ? "" : (authMember.email || ""),
        prompt_config: endeavorPromptForm,
      });
      if (result.ok) {
        setEndeavorDraft(result.payload);
        if (result.payload.prompt_config) setEndeavorPromptForm(result.payload.prompt_config);
        setEndeavorLetterView(true);
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not generate endeavor letter." });
      }
    } finally {
      setEndeavorBusy(false);
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
    if (!selectedBuilderMemberId) {
      setMessage({ type: "error", text: "Please select a member before uploading a ZIP." });
      return;
    }
    if (!batchZipFile) {
      setMessage({ type: "error", text: "Please select a ZIP file before submitting." });
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
    if (item.commit_evidence_id || batchSession.status === "committed" || item.review_status === "committed") {
      setMessage({
        type: "warning",
        text: "This file has already been committed to the evidence folder. Start a new batch or upload a replacement if the destination needs to change.",
      });
      return;
    }
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

  useEffect(() => {
    const snapshot = readPortalRoute();
    routeSyncRef.current.initialized = true;
    routeSyncRef.current.lastUrl = window.location.href;
    routeSyncRef.current.applying = true;
    applyRouteSnapshot(snapshot, { allowPortalMode: true });
    bootstrapAuth();
  }, []);
  useEffect(() => {
    if (!authMember) return;
    loadMessageCenterData(authMember);
  }, [authMember]);
  useEffect(() => {
    if (!authMember && registrationToken) {
      setAuthMode("member");
      loadRegistrationInvite(registrationToken);
    }
  }, [authMember, registrationToken]);
  useEffect(() => {
    if (authMember?.role === "leader") loadProductBacklog();
  }, [authMember?.role]);
  useEffect(() => {
    if (["builder", "leader", "attorney", "admin"].includes(authMember?.role)) return;
    if (!authMember) return;
    if (view.type === "workspace" && view.criterionCode) {
      loadWorkspace(view.criterionCode, workspaceQuery);
    }
  }, [view, workspaceQuery]);
  useEffect(() => {
    const handlePopState = () => {
      routeSyncRef.current.applying = true;
      routeSyncRef.current.lastUrl = window.location.href;
      applyRouteSnapshot(readPortalRoute(), { allowPortalMode: true });
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [authMember, authMode, leaderPerspective]);
  useEffect(() => {
    if (!authReady) return;
    if (readPortalRoute().portal === "assessment") return;
    const nextUrl = buildRouteUrl(currentRouteSnapshot());
    if (routeSyncRef.current.applying) {
      routeSyncRef.current.applying = false;
      routeSyncRef.current.lastUrl = nextUrl;
      window.history.replaceState({}, "", nextUrl);
      return;
    }
    if (routeSyncRef.current.lastUrl === nextUrl) return;
    if (!routeSyncRef.current.initialized) {
      window.history.replaceState({}, "", nextUrl);
      routeSyncRef.current.initialized = true;
    } else {
      window.history.pushState({}, "", nextUrl);
    }
    routeSyncRef.current.lastUrl = nextUrl;
  }, [authReady, authMode, authMember?.role, registrationToken, view.type, view.criterionCode, selectedFolderId, portalSection, leaderPerspective, selectedBuilderMemberId]);
  useEffect(() => {
    if (!authReady || loading || !routeNoticeRef.current) return;
    setMessage(routeNoticeRef.current);
    routeNoticeRef.current = null;
  }, [authReady, loading, view.type, portalSection]);
  useEffect(() => {
    if (!workspace || !selectedFolderId) return;
    const folder = workspace.folders.find((item) => item.id === selectedFolderId);
    if (folder) setFolderForm({ name: folder.name, color: folderColorName(folder.color) });
  }, [workspace, selectedFolderId]);
  useEffect(() => {
    if (view.type === "workspace") setNewFolderParent(selectedFolderId || "");
  }, [view.type, selectedFolderId]);
  useEffect(() => {
    loadPlannerFolders(plannerForm.criterion_code);
  }, [plannerForm.criterion_code]);
  useEffect(() => {
    setPlannerRows(plannerItems.map((item) => ({ ...emptyPlannerRow(), ...item, isNew: false })));
  }, [plannerItems]);
  useEffect(() => {
    if (!["builder", "leader", "attorney", "admin"].includes(authMember?.role) || !selectedBuilderMemberId) return;
    const path = authMember?.role === "attorney" ? `/api/attorney/members/${selectedBuilderMemberId}` : `/api/builder/members/${selectedBuilderMemberId}`;
    const params = authMember?.role === "attorney" ? { attorney_email: authMember?.email || "" } : undefined;
    getJson(path, params).then((detail) => {
      setBuilderMemberDetail(detail);
      if (authMember?.role === "attorney") setProfile(detail.profile || null);
      if (["attorney", "leader"].includes(authMember?.role)) loadAttorneyEvidence(selectedBuilderMemberId);
    }).catch(() => {});
  }, [selectedBuilderMemberId, authMember?.role]);
  useEffect(() => {
    if (!authMember?.role) return;
    if (authMember.role === "member") {
      loadFilingTimeline(authMember.client_id || "");
      return;
    }
    if (["builder", "leader", "attorney", "admin"].includes(authMember.role) && selectedBuilderMemberId) {
      loadFilingTimeline(selectedBuilderMemberId);
    }
  }, [authMember?.role, authMember?.client_id, selectedBuilderMemberId]);
  useEffect(() => {
    if (!["attorney", "leader"].includes(authMember?.role) || portalSection !== "petition" || !selectedBuilderMemberId) return;
    if (authMember?.role === "leader" && leaderPerspective !== "attorney") return;
    loadAttorneyPetition(selectedBuilderMemberId);
  }, [authMember?.role, portalSection, leaderPerspective, selectedBuilderMemberId]);
  useEffect(() => {
    if (!selectedBuilderMemberId || !authMember?.role) return;
    const shouldLoad =
      (authMember.role === "attorney" && portalSection === "petition") ||
      (authMember.role === "builder" && portalSection === "members") ||
      (authMember.role === "leader" && ((leaderPerspective === "attorney" && portalSection === "petition") || (leaderPerspective !== "attorney" && portalSection === "members"))) ||
      (authMember.role === "admin" && portalSection === "debug");
    if (!shouldLoad) return;
    loadPetitionAcceleration(selectedBuilderMemberId);
  }, [authMember?.role, portalSection, leaderPerspective, selectedBuilderMemberId]);
  useEffect(() => {
    if (!["attorney", "leader"].includes(authMember?.role) || !selectedBuilderMemberId) return;
    setEndeavorPromptForm(buildEndeavorPromptDefaults(selectedAttorneyMember, builderMemberDetail, evidenceItems));
    setEndeavorDraft(null);
    setEndeavorLetterView(false);
  }, [authMember?.role, selectedBuilderMemberId, selectedAttorneyMember, builderMemberDetail, evidenceItems]);
  useEffect(() => {
    if (!["attorney", "leader"].includes(authMember?.role)) return;
    setBatchSession(null);
    setBatchSessions([]);
    setBatchZipFile(null);
    setBatchContext("");
    setRecommendationWorkspace(null);
    setActiveRecommendationLetterId("");
    setRecommendationPromptForm(emptyRecommendationPromptForm());
  }, [selectedBuilderMemberId, authMember?.role]);
  useEffect(() => {
    if (!["attorney", "leader"].includes(authMember?.role) || !selectedBuilderMemberId) return;
    if (authMember.role === "leader" && leaderPerspective !== "attorney") return;
    if (portalSection !== "recommendations") return;
    loadRecommendationWorkspace(selectedBuilderMemberId);
  }, [authMember?.role, portalSection, leaderPerspective, selectedBuilderMemberId]);
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

  async function submitLogin(username, password) {
    setLoginBusy(true);
    setMessage(null);
    try {
      if (isPreviewRole(authMode)) {
        const options = PREVIEW_ACCOUNTS[authMode] || [];
        const match = options.find((item) => item.username === username.trim().toLowerCase());
        if (!match) {
          const examples = options.map((item) => item.username).join(" or ");
          setMessage({ type: "error", text: `Use ${examples || "a configured preview account"} for the ${portalMeta(authMode).label}.` });
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
          setMessage({ type: "error", text: `These credentials belong to ${actualRole ? portalMeta(actualRole).label : "another portal"}, not ${portalMeta(expectedRole).label}.` });
          return;
        }
        persistAuth(result.payload.token, payloadUser);
        setAuthMember(payloadUser);
        setLoginForm({ username: "", password: "" });
        setAuthReady(true);
        if (authMode === "builder") {
          await loadBuilderDashboard();
        } else if (authMode === "leader") {
          setLeaderPerspective("leader");
          await loadLeaderPortal();
        } else if (authMode === "attorney") {
          await loadReviewPortals(selectedBuilderMemberId, payloadUser.email || "");
        } else if (authMode === "admin") {
          await loadAdminPortal();
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

  async function handleLogin(event) {
    event.preventDefault();
    await submitLogin(loginForm.username, loginForm.password);
  }

  async function handleDevLogin(account) {
    setLoginForm({ username: account.username, password: "" });
    setMessage({ type: "success", text: "Username filled. Enter the password to sign in." });
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
    setDuplicateState(null);
    const picker = document.getElementById("member-file");
    if (picker) picker.value = "";
  }

  function buildEvidenceUploadForm({ file, criterionCode, documentType, title, description, aiSummary = "", qualityScore = 45, duplicateAction = "", folderId = "" }) {
    const formData = new FormData();
    formData.set("criterion_code", criterionCode);
    formData.set("document_type", documentType);
    formData.set("title", title);
    formData.set("description", description);
    formData.set("ai_summary", aiSummary);
    formData.set("quality_score", String(qualityScore));
    formData.set("duplicate_action", duplicateAction);
    formData.set("folder_id", folderId || "");
    formData.set("file", file);
    return formData;
  }

  function buildUploadForm(options) {
    return buildEvidenceUploadForm({ ...options, file: selectedFile });
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
        const emailStatus = result.payload.email_delivery_status || "pending";
        const emailNote = emailStatus === "sent"
          ? (result.payload.resent ? "Invitation email re-sent" : "Invitation email sent")
          : `${result.payload.resent ? "Invite refreshed" : "Invite created"}, but email was not sent yet (${emailStatus}${result.payload.email_error ? `: ${result.payload.email_error}` : ""}). Registration link: ${result.payload.registration_link || "not available"}`;
        setMessage({
          type: emailStatus === "failed" ? "error" : "success",
          text: `${emailNote}. ${routed || "Assignments can be completed later"}.`,
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

  async function loadRegistrationInvite(token) {
    if (!token) return;
    setRegistrationBusy(true);
    setMessage(null);
    try {
      const invite = await getJson("/api/member/registration-invite", { token });
      setRegistrationInfo(invite);
    } catch (error) {
      setRegistrationInfo(null);
      setMessage({ type: "error", text: error.error || "Registration link is invalid or expired." });
    } finally {
      setRegistrationBusy(false);
    }
  }

  async function submitRegistration(event) {
    event.preventDefault();
    setMessage(null);
    if (registrationForm.password !== registrationForm.confirm_password) {
      setMessage({ type: "error", text: "Passwords do not match." });
      return;
    }
    setRegistrationBusy(true);
    try {
      const formData = new FormData();
      formData.set("token", registrationToken);
      formData.set("password", registrationForm.password);
      formData.set("phone", registrationForm.phone);
      const result = await sendForm("/api/member/register", formData);
      if (!result.ok) {
        setMessage({ type: "error", text: result.payload.error || "Could not complete registration." });
        return;
      }
      persistAuth(result.payload.token, result.payload.member);
      setAuthMode("member");
      setAuthMember(result.payload.member);
      setRegistrationToken("");
      setRegistrationInfo(null);
      setRegistrationForm({ password: "", confirm_password: "", phone: "" });
      await loadHome();
      setView({ type: "profile", criterionCode: "" });
      setProfileTab("identity");
      setMessage({ type: "success", text: "Registration complete. Please review and complete your member profile." });
    } finally {
      setRegistrationBusy(false);
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
    const actorKeys = actorMessageKeys(authMember);
    const unreadItems = thread.messages.filter((item) => item.recipient_role === authMember.role && !item.is_read && actorKeys.has(String(item.recipient_key || "").trim()));
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
    if (!confirmDeleteAction("Delete this message?", "This action cannot be undone from the portal. Continue?")) return;
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

  function setCriticalRoleField(field, value) {
    setCriticalRoleForm((current) => {
      const next = { ...current, [field]: value };
      if (field === "is_current_role" && value) next.role_end_date = "";
      return next;
    });
  }

  function openCriticalRoleProject(project) {
    setActiveCriticalRoleId(project.id || "");
    setCriticalRoleForm(hydrateCriticalRoleProject(project));
    setMemberRewriteDrafts({});
  }

  function startNewCriticalRoleProject() {
    setActiveCriticalRoleId("");
    setCriticalRoleForm(emptyCriticalRoleProjectForm());
    setMemberRewriteDrafts({});
  }

  function setOriginalContributionField(field, value) {
    setOriginalContributionForm((current) => ({ ...current, [field]: value }));
  }

  function openOriginalContribution(entry) {
    setActiveOriginalContributionId(entry.id || "");
    setOriginalContributionForm(hydrateOriginalContribution(entry));
    setMemberRewriteDrafts({});
  }

  function startNewOriginalContribution() {
    setActiveOriginalContributionId("");
    setOriginalContributionForm(emptyOriginalContributionForm());
    setMemberRewriteDrafts({});
  }

  function memberRewriteKey(formType, field) {
    return `${formType}:${field}`;
  }

  function memberRewriteContext(formType) {
    if (formType === "critical_role") {
      return {
        organization_name: criticalRoleForm.organization_name,
        organization_unit: criticalRoleForm.organization_unit,
        role_title: criticalRoleForm.role_title,
        project_name: criticalRoleForm.project_name,
        project_status: criticalRoleForm.project_status,
        business_value_summary: criticalRoleForm.business_value_summary,
        quantitative_metrics: criticalRoleForm.quantitative_metrics,
      };
    }
    return {
      contribution_title: originalContributionForm.contribution_title,
      contribution_category: originalContributionForm.contribution_category,
      field_of_expertise: originalContributionForm.field_of_expertise,
      job_title: originalContributionForm.job_title,
      organization_name: originalContributionForm.organization_name,
      project_name: originalContributionForm.project_name,
      impact_metrics: originalContributionForm.impact_metrics,
      field_wide_impact: originalContributionForm.field_wide_impact,
    };
  }

  function setMemberRewriteFieldValue(formType, field, value) {
    if (formType === "critical_role") {
      setCriticalRoleField(field, value);
    } else {
      setOriginalContributionField(field, value);
    }
  }

  async function rewriteMemberField(formType, field, label, value) {
    const key = memberRewriteKey(formType, field);
    setMemberRewriteBusyKey(key);
    setMessage(null);
    try {
      const result = await sendJson("/api/member/intake-field-rewrite", {
        criterion_type: formType,
        field_key: field,
        field_label: label,
        field_value: value || "",
        form_context: memberRewriteContext(formType),
      });
      if (!result.ok) {
        setMessage({ type: "error", text: result.payload.error || "Could not rewrite this field." });
        return;
      }
      const rewrittenValue = result.payload.rewritten_value || "";
      setMemberRewriteDrafts((current) => ({
        ...current,
        [key]: {
          originalValue: value || "",
          rewrittenValue,
          activeVersion: "rewrite",
          source: result.payload.source || "fallback",
          rationale: result.payload.rationale || "",
          generatedAt: result.payload.generated_at || "",
        },
      }));
      setMemberRewriteFieldValue(formType, field, rewrittenValue);
    } finally {
      setMemberRewriteBusyKey("");
    }
  }

  function applyMemberRewriteVersion(formType, field, version) {
    const key = memberRewriteKey(formType, field);
    const draft = memberRewriteDrafts[key];
    if (!draft) return;
    const nextValue = version === "original" ? draft.originalValue : draft.rewrittenValue;
    setMemberRewriteFieldValue(formType, field, nextValue);
    setMemberRewriteDrafts((current) => ({
      ...current,
      [key]: { ...draft, activeVersion: version },
    }));
  }

  function revertMemberRewrite(formType, field) {
    const key = memberRewriteKey(formType, field);
    const draft = memberRewriteDrafts[key];
    if (draft) setMemberRewriteFieldValue(formType, field, draft.originalValue);
    setMemberRewriteDrafts((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function renderMemberMagicTextarea(formType, field, label, options = {}) {
    const value = formType === "critical_role" ? criticalRoleForm[field] : originalContributionForm[field];
    const key = memberRewriteKey(formType, field);
    return (
      <MagicRewriteTextarea
        key={key}
        className={options.className}
        label={label}
        required={options.required}
        value={value || ""}
        placeholder={options.placeholder}
        help={options.help}
        rewrite={memberRewriteDrafts[key]}
        busy={memberRewriteBusyKey === key}
        onChange={(nextValue) => setMemberRewriteFieldValue(formType, field, nextValue)}
        onRewrite={() => rewriteMemberField(formType, field, label, value || "")}
        onShowOriginal={() => applyMemberRewriteVersion(formType, field, "original")}
        onShowRewrite={() => applyMemberRewriteVersion(formType, field, "rewrite")}
        onRevert={() => revertMemberRewrite(formType, field)}
      />
    );
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
        setMessage({ type: "success", text: "Profile saved." });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not update member profile." });
      }
    } finally {
      setProfileBusy(false);
    }
  }

  async function persistCriticalRoleProject(mode = "draft") {
    setCriticalRoleBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(criticalRoleForm).forEach(([key, value]) => {
        if (key === "id") return;
        formData.set(key, typeof value === "boolean" ? String(value) : value);
      });
      formData.set("workflow_status", mode);
      const path = activeCriticalRoleId ? `/api/member/critical-role-projects/${activeCriticalRoleId}` : "/api/member/critical-role-projects";
      const method = activeCriticalRoleId ? "PATCH" : "POST";
      const result = await sendForm(path, formData, method);
      if (result.ok) {
        const saved = hydrateCriticalRoleProject(result.payload);
        setCriticalRoleForm(saved);
        setActiveCriticalRoleId(saved.id);
        await loadHome();
        await logPortalActivity(mode === "submitted" ? "critical_role_submit" : "critical_role_draft_save", mode === "submitted" ? "Submitted a critical role project." : "Saved a critical role draft.", {
          project_id: saved.id || "",
          workflow_status: mode,
          project_name: saved.project_name || "",
          organization_name: saved.organization_name || "",
        });
        setMessage({ type: "success", text: mode === "submitted" ? "Project submitted." : "Draft saved." });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not save critical role project." });
      }
    } finally {
      setCriticalRoleBusy(false);
    }
  }

  async function saveCriticalRoleProjectDraft() {
    await persistCriticalRoleProject("draft");
  }

  async function submitCriticalRoleProject() {
    await persistCriticalRoleProject("submitted");
  }

  async function deleteCriticalRoleProject() {
    if (!activeCriticalRoleId) return;
    if (!confirmDeleteAction("Delete this critical role project?", "This will remove the project from the portal and archive any generated evidence. Continue?")) return;
    setCriticalRoleBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/api/member/critical-role-projects/${activeCriticalRoleId}`, {
        method: "DELETE",
        headers: { ...authHeaders() },
      });
      const payload = await response.json();
      if (response.ok) {
        await logPortalActivity("critical_role_delete", "Deleted a critical role project.", { project_id: activeCriticalRoleId });
        setMessage({ type: "success", text: "Critical role project removed." });
        setActiveCriticalRoleId("");
        setCriticalRoleForm(emptyCriticalRoleProjectForm());
        await loadHome();
      } else {
        setMessage({ type: "error", text: (payload.detail || payload).error || "Could not delete critical role project." });
      }
    } finally {
      setCriticalRoleBusy(false);
    }
  }

  async function persistOriginalContribution(mode = "draft") {
    setOriginalContributionBusy(true);
    setMessage(null);
    try {
      const formData = new FormData();
      Object.entries(originalContributionForm).forEach(([key, value]) => {
        if (key === "id") return;
        formData.set(key, value);
      });
      formData.set("workflow_status", mode);
      const path = activeOriginalContributionId ? `/api/member/original-contributions/${activeOriginalContributionId}` : "/api/member/original-contributions";
      const method = activeOriginalContributionId ? "PATCH" : "POST";
      const result = await sendForm(path, formData, method);
      if (result.ok) {
        const saved = hydrateOriginalContribution(result.payload);
        setOriginalContributionForm(saved);
        setActiveOriginalContributionId(saved.id);
        await loadHome();
        await logPortalActivity(mode === "submitted" ? "original_contribution_submit" : "original_contribution_draft_save", mode === "submitted" ? "Submitted an original contribution." : "Saved an original contribution draft.", {
          entry_id: saved.id || "",
          workflow_status: mode,
          contribution_title: saved.contribution_title || "",
          organization_name: saved.organization_name || "",
        });
        setMessage({ type: "success", text: mode === "submitted" ? "Contribution submitted." : "Draft saved." });
      } else {
        setMessage({ type: "error", text: result.payload.error || "Could not save original contribution." });
      }
    } finally {
      setOriginalContributionBusy(false);
    }
  }

  async function saveOriginalContributionDraft() {
    await persistOriginalContribution("draft");
  }

  async function submitOriginalContribution() {
    await persistOriginalContribution("submitted");
  }

  async function deleteOriginalContribution() {
    if (!activeOriginalContributionId) return;
    if (!confirmDeleteAction("Delete this original contribution entry?", "This will remove the entry from the portal and archive any generated evidence. Continue?")) return;
    setOriginalContributionBusy(true);
    setMessage(null);
    try {
      const response = await fetch(`${API_URL}/api/member/original-contributions/${activeOriginalContributionId}`, {
        method: "DELETE",
        headers: { ...authHeaders() },
      });
      const payload = await response.json();
      if (response.ok) {
        await logPortalActivity("original_contribution_delete", "Deleted an original contribution.", { entry_id: activeOriginalContributionId });
        setMessage({ type: "success", text: "Original contribution removed." });
        setActiveOriginalContributionId("");
        setOriginalContributionForm(emptyOriginalContributionForm());
        await loadHome();
      } else {
        setMessage({ type: "error", text: (payload.detail || payload).error || "Could not delete original contribution." });
      }
    } finally {
      setOriginalContributionBusy(false);
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
    if (!confirmDeleteAction("Delete this planner item?")) return;
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
    if (!selectedFile) {
      setMessage({ type: "error", text: "Please choose a file before uploading evidence." });
      return;
    }
    if (routeMode === "ai" && !memberContext.trim()) {
      setMessage({ type: "error", text: "Please add a short note before using AI review." });
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
          setMessage({ type: "success", text: "Evidence uploaded." });
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
        } else {
          setMessage({ type: "error", text: "Evidence review failed. Please try again or contact Ascend support." });
        }
      }
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleSaveDraft(duplicateAction = "") {
    if (!selectedFile) {
      setMessage({ type: "error", text: "Please choose a file before saving evidence." });
      return;
    }
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
        setMessage({ type: "error", text: "Please approve the AI draft before saving." });
        return;
      }
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
        setMessage({ type: "success", text: "Evidence uploaded." });
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
    formData.set("parent_id", newFolderParent || selectedFolderId || "");
    formData.set("color", FOLDER_COLORS[newFolderColor]);
    const result = await sendForm(`/api/criteria/${view.criterionCode}/folders`, formData);
    if (result.ok) {
      setMessage({ type: "success", text: "Folder created." });
      setNewFolderName("");
      setNewFolderParent(selectedFolderId || "");
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
    await deleteFolderById(selectedFolderId, workspaceFolderLabel(workspace, selectedFolderId));
  }

  async function deleteFolderById(folderId, label = "this folder") {
    if (!folderId) return;
    if (!confirmDeleteAction(`Delete folder "${label}"? Files and subfolders will stay available.`, "This folder will be removed, but the evidence will remain available and move up one level. Continue?")) return;
    const response = await fetch(`${API_URL}/api/folders/${folderId}`, { method: "DELETE", headers: { ...authHeaders() } });
    const payload = await response.json();
    const body = payload.detail || payload;
    if (response.ok) {
      setMessage({ type: "success", text: "Folder deleted. Files and subfolders were kept." });
      if (selectedFolderId === folderId) setSelectedFolderId("");
      loadWorkspace(view.criterionCode, workspaceQuery);
    } else {
      setMessage({ type: "error", text: body.error || "Could not delete folder." });
    }
  }

  async function deleteFile(item) {
    if (!confirmDeleteAction(`Remove ${item.label} from your active evidence list?`, "This will archive the evidence from the active workspace. Continue?")) return;
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
    event.dataTransfer.setData("application/json", JSON.stringify(workspaceDragPayload(item)));
    event.dataTransfer.effectAllowed = "move";
  }

  async function moveDraggedItem(item, targetFolderId) {
    if (!view.criterionCode) return;
    const normalizedTarget = normalizeFolderId(targetFolderId);
    if (item.kind === "folder" && item.entityId === normalizedTarget) {
      setMessage({ type: "error", text: "A folder cannot be moved into itself." });
      return;
    }
    const currentParent = item.kind === "folder" ? normalizeFolderId(item.parentId) : normalizeFolderId(item.folderId);
    if (currentParent === normalizedTarget) {
      setMessage({ type: "success", text: "Item is already in that folder." });
      return;
    }
    if (item.kind === "file") {
      const formData = new FormData();
      formData.set("folder_id", normalizedTarget);
      const result = await sendForm(`/api/evidence/${item.entityId}/folder`, formData, "PATCH");
      if (!result.ok) return setMessage({ type: "error", text: result.payload.error || "Could not move file." });
    } else {
      const formData = new FormData();
      formData.set("parent_id", normalizedTarget);
      const result = await sendForm(`/api/folders/${item.entityId}`, formData, "PATCH");
      if (!result.ok) return setMessage({ type: "error", text: result.payload.error || "Could not move folder." });
    }
    setMessage({ type: "success", text: "Workspace updated." });
    loadWorkspace(view.criterionCode, workspaceQuery);
  }

  async function ensureWorkspaceFolderPath(parts, baseFolderId, folderCache) {
    let parentId = normalizeFolderId(baseFolderId);
    for (const rawPart of parts) {
      const name = rawPart.trim();
      if (!name) continue;
      const existing = folderCache.find((folder) => normalizeFolderId(folder.parent_id) === parentId && folder.name.trim().toLowerCase() === name.toLowerCase());
      if (existing) {
        parentId = existing.id;
        continue;
      }
      const formData = new FormData();
      formData.set("name", name);
      formData.set("parent_id", parentId);
      formData.set("color", FOLDER_COLORS.Emerald);
      const result = await sendForm(`/api/criteria/${view.criterionCode}/folders`, formData);
      if (!result.ok) throw new Error(result.payload.error || `Could not create folder ${name}.`);
      folderCache.push(result.payload);
      parentId = result.payload.id;
    }
    return parentId;
  }

  async function uploadWorkspaceFiles(filePayloads, targetFolderId = selectedFolderId) {
    const payloads = (filePayloads || []).filter((item) => item?.file);
    if (!payloads.length || !view.criterionCode) {
      setMessage({ type: "error", text: "Drop files or folders that contain files into the workspace." });
      return;
    }
    setWorkspaceUploadBusy(true);
    setMessage(null);
    const folderCache = [...(workspace?.folders || [])];
    const failures = [];
    let uploaded = 0;
    try {
      for (const item of payloads) {
        const file = item.file;
        const relativePath = item.relativePath || file.webkitRelativePath || file.name;
        const pathParts = relativePath.split("/").filter(Boolean);
        const parentParts = pathParts.length > 1 ? pathParts.slice(0, -1) : [];
        const destinationFolderId = await ensureWorkspaceFolderPath(parentParts, targetFolderId, folderCache);
        const title = file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ").trim() || "Uploaded evidence";
        const folderLabel = workspaceFolderLabel({ folders: folderCache }, destinationFolderId);
        const result = await sendForm("/api/evidence", buildEvidenceUploadForm({
          file,
          criterionCode: view.criterionCode,
          documentType: inferDocumentType(`${file.name} ${relativePath}`),
          title,
          description: `Uploaded from the Evidence Workspace into ${folderLabel}. Original path: ${relativePath}.`,
          aiSummary: `Member uploaded this evidence into ${folderLabel}.`,
          qualityScore: 45,
          folderId: destinationFolderId,
        }));
        if (result.ok) {
          uploaded += 1;
        } else {
          failures.push(result.payload.message || result.payload.error || `${file.name} could not be uploaded.`);
        }
      }
      await refreshAfterSave();
      if (uploaded && !failures.length) {
        setMessage({ type: "success", text: `${uploaded} file${uploaded === 1 ? "" : "s"} uploaded into ${workspaceFolderLabel(workspace, targetFolderId)}.` });
      } else if (uploaded) {
        setMessage({ type: "error", text: `${uploaded} file${uploaded === 1 ? "" : "s"} uploaded. ${failures.length} file${failures.length === 1 ? "" : "s"} need review: ${failures.slice(0, 2).join(" ")}` });
      } else {
        setMessage({ type: "error", text: failures[0] || "No files were uploaded." });
      }
    } catch (error) {
      setMessage({ type: "error", text: error.message || "Could not upload the dropped folder or files." });
    } finally {
      setWorkspaceUploadBusy(false);
      if (workspaceFileInputRef.current) workspaceFileInputRef.current.value = "";
    }
  }

  async function handleWorkspaceFileSelection(event) {
    const files = Array.from(event.target.files || []).map((file) => ({ file, relativePath: file.webkitRelativePath || file.name }));
    await uploadWorkspaceFiles(files, selectedFolderId);
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

  const waitingForBuilderPortal = authMember?.role === "builder" && (loading || !builderDashboard);
  const waitingForLeaderPortal = authMember?.role === "leader" && (loading || !builderDashboard);
  const waitingForAttorneyPortal = authMember?.role === "attorney" && (loading || !dashboard);
  const waitingForAdminPortal = authMember?.role === "admin" && (loading || !adminDashboard);
  const waitingForMemberPortal = authMember?.role === "member" && (loading || !dashboard);
  const liveRoute = readPortalRoute();

  if (liveRoute.portal === "assessment" && liveRoute.page !== "leads") {
    return <AssessmentPublicPortal initialPage={liveRoute.page || "home"} />;
  }

  if (!authReady || loading || waitingForBuilderPortal || waitingForLeaderPortal || waitingForAttorneyPortal || waitingForAdminPortal || waitingForMemberPortal) {
    return <main className="shell auth-shell"><div className="loading">Loading Ascend portal...</div></main>;
  }

  if (!authMember) {
    if (registrationToken) {
      return (
        <main className="login-page">
          <div className="landing-grid">
            <section className="login-hero">
              <img className="brand-logo login-logo" src={LOGO_URL} alt="Ascend HSI logo" />
              <p className="eyebrow">Member Registration</p>
              <h1>Complete your Ascend access.</h1>
              <p>Set your password to activate your Member Portal account, then finish your profile intake.</p>
              {message ? <div className={`banner ${message.type}`}>{message.text}</div> : null}
              {registrationInfo ? (
                <div className="side-card" style={{ color: "var(--ink)", background: "#fffdfa", borderColor: "var(--line)" }}>
                  <strong>{registrationInfo.display_name || "Invited member"}</strong>
                  <p>{registrationInfo.email}</p>
                  <p>{registrationInfo.current_title || "Profile title pending"}{registrationInfo.current_employer ? ` • ${registrationInfo.current_employer}` : ""}</p>
                </div>
              ) : null}
              <form className="login-card" onSubmit={submitRegistration}>
                <label>
                  Phone number
                  <input value={registrationForm.phone} onChange={(event) => setRegistrationForm((current) => ({ ...current, phone: event.target.value }))} placeholder="Optional, can be completed later" />
                </label>
                <label>
                  Password
                  <input type="password" value={registrationForm.password} onChange={(event) => setRegistrationForm((current) => ({ ...current, password: event.target.value }))} placeholder="Create a secure password" required />
                </label>
                <label>
                  Confirm password
                  <input type="password" value={registrationForm.confirm_password} onChange={(event) => setRegistrationForm((current) => ({ ...current, confirm_password: event.target.value }))} placeholder="Re-enter password" required />
                </label>
                <button className="primary" type="submit" disabled={registrationBusy}>{registrationBusy ? "Completing..." : "Complete Registration"}</button>
                <button className="ghost" type="button" onClick={() => { setRegistrationToken(""); setMessage(null); }}>Back to sign in</button>
              </form>
            </section>
            <AscendVisaCompass />
          </div>
        </main>
      );
    }
    const selectedPortal = portalMeta(authMode);
    const loginChoices = devLoginOptions(authMode);
    return (
      <main className="login-page">
        <div className="landing-grid">
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
                <div className="section-kicker">Development Login Shortcuts</div>
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
          <AscendVisaCompass />
        </div>
      </main>
    );
  }

  const selectedCriterion = dashboard?.criteria?.find((item) => item.code === view.criterionCode);
  const memberInitials = `${(authMember.display_name || "M").slice(0, 1)}${(profile?.last_name || "").slice(0, 1)}`.toUpperCase();
  const portalTitle = authMember.role === "leader" ? "Leader Portal" : authMember.role === "attorney" ? "Attorney Portal" : authMember.role === "admin" ? "Admin Portal" : authMember.role === "builder" ? "Profile Builder Portal" : "Member Portal";
  const isLeaderExecutiveView = authMember.role === "leader" && leaderPerspective === "leader";
  const isLeaderBuilderView = authMember.role === "leader" && leaderPerspective === "builder";
  const isLeaderAttorneyView = authMember.role === "leader" && leaderPerspective === "attorney";
  const showingBuilderWorkspace = authMember.role === "builder" || isLeaderBuilderView;
  const builderLabel = showingBuilderWorkspace ? "Profile Builder" : "Leader";
  const memberSection = view.type === "messages" ? "messages" : view.type === "profile" ? "profile" : view.type === "workspace" ? "workspace" : view.type === "critical_roles" ? "critical_roles" : view.type === "original_contributions" ? "original_contributions" : view.type === "planner" ? "planner" : view.type === "intake" ? "intake" : "home";
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
  function handlePortalSectionChange(nextSection) {
    setMessage(null);
    if (authMember.role === "leader" && nextSection === "invite") {
      setLeaderPerspective("leader");
      setPortalSection("invite");
      return;
    }
    setPortalSection(nextSection);
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
      { value: "home", label: "Builder Home", icon: "H" },
      ...(authMember.role === "leader" ? [{ value: "invite", label: "Invite Member" }] : []),
      { value: "members", label: "Profiles", icon: "P" },
      { value: "opportunities", label: "Opportunities", icon: "O" },
      { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}`, icon: "M" },
    ];
    const leaderSidebarItems = [
      { value: "home", label: "Executive Overview", icon: "H" },
      { value: "invite", label: "Invite Member", icon: "I" },
      { value: "members", label: "Member Review", icon: "R" },
      { value: "risks", label: "Risk & Bottlenecks", icon: "B" },
      { value: "capacity", label: "Team Capacity", icon: "C" },
      { value: "timeline", label: "Delivery Timeline", icon: "T" },
      { value: "backlog", label: "Product Backlog", icon: "P" },
      { value: "oversight", label: "Assignment Oversight", icon: "A" },
      { value: "opportunities", label: "Opportunities", icon: "O" },
      { value: "batch", label: "Batch Intake", icon: "D" },
      { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}`, icon: "M" },
    ];
    return (
      <React.Fragment>
        <main className="shell attorney-shell" style={shellStyle}>
          <aside className="sidebar attorney-sidebar">
          <PortalBrand onHome={goToPortalHome} label={`Go to ${isLeaderExecutiveView ? "leader" : isLeaderBuilderView ? "builder" : "profile builder"} home`} />
          <div className="brand-sub">{isLeaderExecutiveView ? "Executive Workspace" : isLeaderBuilderView ? "Leader Acting As Builder" : "Profile Builder Workspace"}</div>
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
            onChange={handlePortalSectionChange}
          />
          <div className="side-card">
            <strong>{isLeaderExecutiveView ? "Leader snapshot" : "Builder load"}</strong>
            <p>{isLeaderExecutiveView ? "Members count, late cases, and open backlog stay visible while leadership works." : "Assigned members, late cases, and tasks due this week stay visible while builders work."}</p>
          </div>
          <div className="side-card">
            <strong>At a glance</strong>
            {isLeaderExecutiveView ? (
              <React.Fragment>
                <p>Members count: {leaderMetrics.member_count || builderMembers.length || 0}</p>
                <p>Late cases: {leaderMetrics.late_timeline_cases || 0}</p>
                <p>Open backlog: {(productBacklog.items || []).filter((item) => !["shipped", "closed"].includes(String(item.status || "").toLowerCase())).length}</p>
              </React.Fragment>
            ) : (
              <React.Fragment>
                <p>Assigned: {builderDashboard?.metrics.member_count || builderMembers.length || 0}</p>
                <p>Late: {builderDashboard?.metrics.late_count || builderMembers.filter((item) => item.timeline_summary?.late).length || 0}</p>
                <p>Tasks due this week: {builderDashboard?.metrics.active_tasks || 0}</p>
              </React.Fragment>
            )}
          </div>
          <span className="side-note">{authMember.role === "leader" ? (isLeaderExecutiveView ? "Leader portal only" : "Leader operating in builder visibility mode") : "Profile builder portal only"}</span>
        </aside>
        {sidebarResizer}
        <section className="main attorney-main">
          <div className="topbar">
            <div className="topbar-copy">
              <span className="topbar-label">{portalTitle}</span>
              <div className="topbar-welcome">Welcome {firstNameFromDisplay(authMember.display_name)}.</div>
              <strong>{subtitleForPortalSection(authMember.role === "leader" ? "leader" : "builder", portalSection, leaderPerspective) || (isLeaderExecutiveView ? "Executive-level movement across the EB1A operation" : "Assigned member momentum and profile-building actions")}</strong>
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

          {isLeaderExecutiveView && portalSection === "invite" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Invite Member</p>
                <h1>Start a new member journey.</h1>
                <p>Create a registration invite, optionally assign a profile builder and attorney, and let the member register from email.</p>
                <div className="hero-chips">
                  <span className="hero-chip">Real email path</span>
                  <span className="hero-chip">Optional assignments</span>
                  <span className="hero-chip">Registration token</span>
                </div>
              </header>
              <section className="builder-layout">
                <LeaderInvitePanel
                  form={leaderInviteForm}
                  builders={leaderBuilders}
                  attorneys={leaderAttorneys}
                  busy={builderBusy}
                  onFieldChange={setLeaderInviteField}
                  onSubmit={submitLeaderInvite}
                />
                <LeaderRecentInvitesPanel invites={leaderInvites} />
              </section>
            </React.Fragment>
          ) : portalSection === "messages" ? (
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
          ) : isLeaderExecutiveView && portalSection === "timeline" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Delivery Timeline</p>
                <h1>Portfolio timing to petition filing.</h1>
                <p>Use the member selector to inspect a realistic filing path, then watch the table for late cases that need intervention.</p>
              </header>
              <section className="metrics-grid">
                <MetricCard label="Late Cases" value={leaderMetrics.late_timeline_cases || 0} />
                <MetricCard label="At Risk Cases" value={leaderMetrics.at_risk_cases || 0} />
                <MetricCard label="Active Tasks" value={leaderMetrics.active_tasks || 0} />
                <MetricCard label="Avg Readiness" value={`${leaderMetrics.avg_readiness || 0}%`} />
              </section>
              <FilingTimelinePanel data={filingTimeline} busy={filingTimelineBusy} />
              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Timeline Alerts</div>
                <h3 className="section-title">Members running late or at risk</h3>
                <div className="backlog-table">
                  <div className="backlog-row backlog-head"><span>Status</span><span>Member</span><span>Target</span><span>Action</span></div>
                  {builderMembers.map((item) => (
                    <article key={`timeline_${item.client_id}`} className={`backlog-row ${item.timeline_summary?.late ? "priority-p0" : "priority-p2"}`}>
                      <span className={`status-pill ${item.timeline_summary?.late ? "blocked" : item.timeline_summary?.status === "at_risk" ? "planned" : "completed"}`}>{item.timeline_summary?.status || "unknown"}</span>
                      <div><strong>{item.display_name}</strong><p>{item.stage_label || caseStatusLabel(item.status)} • {item.readiness_score || 0}% readiness</p></div>
                      <span>{item.timeline_summary?.target_filing_date || "TBD"}</span>
                      <button className="ghost compact-btn" type="button" onClick={() => { setSelectedBuilderMemberId(item.client_id); loadFilingTimeline(item.client_id); }}>Review</button>
                    </article>
                  ))}
                </div>
              </section>
            </React.Fragment>
          ) : isLeaderExecutiveView && portalSection === "backlog" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Product Backlog</p>
                <h1>Convert field feedback into shippable work.</h1>
                <p>Capture enhancement requests with priority, screenshots, value, and acceptance criteria.</p>
              </header>
              <ProductBacklogPanel
                backlog={productBacklog}
                form={featureRequestForm}
                busy={featureRequestBusy}
                onFormChange={(field, value) => setFeatureRequestForm((current) => ({ ...current, [field]: value }))}
                onSubmit={submitFeatureRequest}
                onUpdate={updateFeatureRequest}
              />
            </React.Fragment>
          ) : isLeaderExecutiveView && portalSection === "oversight" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Assignment Oversight</p>
                <h1>Routing and workload, one view.</h1>
                <p>Leaders can assign or rebalance profile builders and attorneys from one readable table.</p>
                <div className="hero-chips">
                  <button className="primary compact-btn" type="button" onClick={() => setPortalSection("invite")}>Invite Member</button>
                  <span className="hero-chip">Builder optional</span>
                  <span className="hero-chip">Attorney optional</span>
                </div>
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

              <div style={{ marginTop: "18px" }}>
                <LeaderRecentInvitesPanel invites={leaderInvites} />
              </div>
            </React.Fragment>
          ) : portalSection === "members" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">{isLeaderExecutiveView ? "Member Review" : "Profiles"}</p>
                <h1>{isLeaderExecutiveView ? "Member progress, ready for review." : "Search members, review evidence, and update profile-building status."}</h1>
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
                        {item.timeline_summary ? <span>Target filing {item.timeline_summary.target_filing_date} • {item.timeline_summary.status?.replaceAll("_", " ")}</span> : null}
                        <span className={`status-pill ${item.momentum === "Strong" ? "completed" : item.momentum === "Needs focus" ? "blocked" : "in_progress"}`}>{item.momentum}</span>
                      </button>
                    ))}
                    {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                  </div>
                </section>

                <section className="panel">
                  <div className="section-kicker">Selected Profile</div>
                  <h3 className="section-title">{builderMemberDetail?.member?.display_name || "Select a member"}</h3>
                  <p className="section-intro">Review profile facts, evidence coverage, and builder tasks before attorney handoff.</p>
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
                      <FilingTimelinePanel data={filingTimeline} busy={filingTimelineBusy} compact />
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
                      <section className="panel panel-subsection">
                        <div className="section-kicker">Member Narrative Exports</div>
                        <h3 className="section-title">Critical role and original contribution exports</h3>
                        <p className="section-intro">These generated PDF exports are built from the member’s structured intake and stored back into the secure evidence path for review.</p>
                        <div className="builder-layout">
                          <ExportedNarrativePanel
                            title="Critical Role Exports"
                            sectionLabel="Leading Or Critical Role"
                            items={builderMemberDetail.critical_role_projects || []}
                            emptyText="No critical role exports generated yet."
                          />
                          <ExportedNarrativePanel
                            title="Original Contribution Exports"
                            sectionLabel="Original Contributions"
                            items={builderMemberDetail.original_contribution_entries || []}
                            emptyText="No original contribution exports generated yet."
                          />
                        </div>
                      </section>
                      <PetitionAccelerationPanel data={petitionAcceleration} busy={petitionAccelerationBusy} compact />
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
                <h1>Create a member task.</h1>
                <p>Turn profile-building ideas into clear member tasks tied to EB1A criteria.</p>
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
                  <h3 className="section-title">Create a member task</h3>
                  <p className="section-intro">Turn profile-building ideas into clear member tasks tied to EB1A criteria.</p>
                  <form className="stacked-form" onSubmit={assignBuilderTask}>
                    <label>Opportunity template<select value={builderTaskForm.opportunity_id} onChange={(event) => { setBuilderTaskField("opportunity_id", event.target.value); applyOpportunity(event.target.value); }}><option value="">Custom task</option>{builderOpportunities.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
                    <label>Task title<input value={builderTaskForm.title} onChange={(event) => setBuilderTaskField("title", event.target.value)} placeholder="Example: Upload IEEE reviewer thank you email" /></label>
                    <label>Guidance for member<textarea value={builderTaskForm.description} onChange={(event) => setBuilderTaskField("description", event.target.value)} placeholder="Explain what the member should collect and why it matters." /></label>
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
                <p className="eyebrow">{isLeaderExecutiveView ? "Leader Portal" : "Profile Builder Portal"}</p>
                <h1>{isLeaderExecutiveView ? "See profile-building momentum in one executive view." : "Move assigned members toward attorney-ready evidence."}</h1>
                <p>{isLeaderExecutiveView ? "Track readiness, invitation flow, late cases, assignment load, and petition delivery risk across the product suite." : "Review member readiness, create profile-building opportunities, and keep each case moving with clean next steps."}</p>
                <div className="hero-chips">
                  <span className="hero-chip">{isLeaderExecutiveView ? "Late-case alerts" : "Assigned roster"}</span>
                  <span className="hero-chip">{isLeaderExecutiveView ? "Assignment oversight" : "Evidence gap review"}</span>
                  <span className="hero-chip">{isLeaderExecutiveView ? "Timeline to filing" : "Opportunity tasks"}</span>
                </div>
              </header>

              <section className="metrics-grid">
                <MetricCard label={isLeaderExecutiveView ? "Active members" : "Assigned members"} value={builderDashboard?.metrics.member_count || builderMembers.length || 0} />
                <MetricCard label={isLeaderExecutiveView ? "Late cases" : "Avg readiness"} value={isLeaderExecutiveView ? (leaderMetrics.late_timeline_cases || 0) : `${builderDashboard?.metrics.avg_readiness || 0}%`} />
                <MetricCard label={isLeaderExecutiveView ? "Avg readiness" : "Tasks due"} value={isLeaderExecutiveView ? `${leaderMetrics.avg_readiness || 0}%` : (builderDashboard?.metrics.active_tasks || 0)} />
                <MetricCard label={isLeaderExecutiveView ? "Open backlog" : "Late cases"} value={isLeaderExecutiveView ? ((productBacklog.items || []).filter((item) => !["shipped", "closed"].includes(String(item.status || "").toLowerCase())).length) : (builderDashboard?.metrics.late_count || builderMembers.filter((item) => item.timeline_summary?.late).length || 0)} />
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
                <LeaderInvitePanel
                  form={leaderInviteForm}
                  builders={leaderBuilders}
                  attorneys={leaderAttorneys}
                  busy={builderBusy}
                  onFieldChange={setLeaderInviteField}
                  onSubmit={submitLeaderInvite}
                />

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
    const selectedMemberRequired = ["dossier", "petition", "endeavor", "recommendations", "batch", "evidence"].includes(portalSection) && !selectedBuilderMemberId;
    const statusEntries = Object.entries(attorneyCaseStatusSummary);
    const attorneyTotalOpenTasks = builderMembers.reduce((sum, item) => sum + (item.open_task_count || 0), 0);
    const attorneyTotalEvidence = builderMembers.reduce((sum, item) => sum + (item.evidence_count || 0), 0);
    const attorneyAverageReadiness = builderMembers.length ? Math.round(builderMembers.reduce((sum, item) => sum + (item.readiness_score || 0), 0) / builderMembers.length) : 0;
    const attorneyCriteriaStarted = builderMembers.reduce((sum, item) => sum + (item.criteria_started || 0), 0);
    const attorneyAttentionCases = builderMembers.filter((item) => (item.open_task_count || 0) > 0 || (item.readiness_score || 0) < 60).length;
    const attorneyDeeperReviewCases = builderMembers.filter((item) => caseStatusLabel(item.status) === "legal review").length;
    return (
      <React.Fragment>
        <main className="shell attorney-shell" style={shellStyle}>
          <aside className="sidebar attorney-sidebar">
          <PortalBrand onHome={goToPortalHome} label={`Go to ${isLeaderAttorneyView ? "leader attorney view" : "attorney"} home`} />
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
              { value: "home", label: "Attorney Home", icon: "H" },
              ...(isLeaderAttorneyView ? [{ value: "invite", label: "Invite Member" }] : []),
              { value: "dossier", label: "Member Dossier", icon: "D" },
              { value: "petition", label: "Petition Generator", icon: "P" },
              { value: "endeavor", label: "Endeavor Letter", icon: "E" },
              { value: "recommendations", label: "Recommendations", icon: "R" },
              { value: "batch", label: "Batch Intake", icon: "B" },
              { value: "evidence", label: "Evidence Review", icon: "V" },
              { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}`, icon: "M" },
            ]}
            value={portalSection}
            onChange={handlePortalSectionChange}
          />
          <div className="side-card">
            <strong>Attorney queue</strong>
            <p>Ready for review, letters pending, and drafts in progress remain visible while legal strategy work happens.</p>
          </div>
          <div className="side-card">
            <strong>At a glance</strong>
            <p>Ready for review: {attorneyDeeperReviewCases}</p>
            <p>Letters pending: {recommendationWorkspace?.letters?.filter((item) => item.status !== "pushed").length || 0}</p>
            <p>Drafts in progress: {(petitionDraft ? 1 : 0) + (endeavorDraft ? 1 : 0)}</p>
          </div>
          <span className="side-note">{isLeaderAttorneyView ? "Leader operating in attorney visibility mode" : "Attorney portal only"}</span>
        </aside>
        {sidebarResizer}
        <section className="main attorney-main">
          <div className="topbar">
            <div className="topbar-copy">
              <span className="topbar-label">{isLeaderAttorneyView ? "Leader Portal • Attorney View" : "Attorney Portal"}</span>
              <div className="topbar-welcome">Welcome {firstNameFromDisplay(authMember.display_name)}.</div>
              <strong>{subtitleForPortalSection("attorney", portalSection)}</strong>
            </div>
            <div className="panel" style={{ minWidth: "280px", margin: 0 }}>
              <div className="section-kicker">Selected Member</div>
              <MemberSearchBox
                value={memberSearchQuery}
                onChange={setMemberSearchQuery}
                total={builderMembers.length}
                visible={filteredBuilderMembers.length}
                label="Search cases"
              />
              <label style={{ display: "block", marginTop: "8px" }}>
                <select value={selectedBuilderMemberId || ""} onChange={(event) => setSelectedBuilderMemberId(event.target.value)}>
                  <option value="">{portalSection === "home" ? "Choose a member for case-specific work" : "Select member"}</option>
                  {memberSelectorOptions.map((member) => (
                    <option key={member.client_id} value={member.client_id}>
                      {member.display_name}
                    </option>
                  ))}
                </select>
              </label>
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
                <p className="eyebrow">Attorney Portal</p>
                <h1>Turn member evidence into stronger EB1A drafting inputs.</h1>
                <p>Review profiles, evidence, Critical Role and Original Contribution exports, then generate petition, endeavor, and recommendation letter drafts.</p>
                <div className="hero-chips">
                  <span className="hero-chip">Petition accelerator</span>
                  <span className="hero-chip">Recommendation letters</span>
                  <span className="hero-chip">Evidence review</span>
                </div>
              </header>

              <section className="metrics-grid">
                <MetricCard label="Ready for legal review" value={attorneyDeeperReviewCases} />
                <MetricCard label="Letters pending" value={recommendationWorkspace?.letters?.filter((item) => item.status !== "pushed").length || 0} />
                <MetricCard label="Drafts in progress" value={(petitionDraft ? 1 : 0) + (endeavorDraft ? 1 : 0)} />
                <MetricCard label="High-risk gaps" value={attorneyAttentionCases} />
              </section>
              {selectedBuilderMemberId ? <FilingTimelinePanel data={filingTimeline} busy={filingTimelineBusy} compact /> : null}

              <section className="builder-layout" style={{ marginTop: "18px" }}>
                <section className="panel">
                  <div className="section-kicker">Assigned Matters</div>
                  <h3 className="section-title">Case roster snapshot</h3>
                  <p className="section-intro">Keep this view portfolio-level: who is assigned, which stage each case is in, and where attorney attention is likely needed. Use the member selector in the header when you want to move into dossier, petition, endeavor, evidence, or batch work.</p>
                  <MemberSearchBox
                    value={memberSearchQuery}
                    onChange={setMemberSearchQuery}
                    total={builderMembers.length}
                    visible={filteredBuilderMembers.length}
                    label="Search cases"
                  />
                  <div className="task-mini-list">
                    {filteredBuilderMembers.map((item) => (
                      <article key={item.client_id} className="task-mini-item">
                        <strong>{item.display_name}</strong>
                        <p>{caseStatusLabel(item.status)} • Readiness {item.readiness_score || 0}%</p>
                        <div className="task-mini-meta">
                          <span>{item.evidence_count || 0} evidence items</span>
                          <span>{item.criteria_started || 0} criteria started</span>
                          <span>{item.open_task_count || 0} open tasks</span>
                        </div>
                      </article>
                    ))}
                    {filteredBuilderMembers.length ? null : <p className="empty-state">No members match that search.</p>}
                  </div>
                </section>

                <section className="panel">
                  <div className="section-kicker">Portfolio Signals</div>
                  <h3 className="section-title">Case-stage and workload summary</h3>
                  <p className="section-intro">Use these counts to decide where legal attention is needed first, without dropping into one member’s detailed record from the dashboard itself.</p>
                  <div className="task-mini-list">
                    {statusEntries.map(([status, count]) => (
                      <article key={status} className="task-mini-item">
                        <strong>{status}</strong>
                        <p>{count} case(s)</p>
                      </article>
                    ))}
                    <article className="task-mini-item">
                      <strong>Needs attention</strong>
                      <p>{attorneyAttentionCases} case(s) currently have open work or lower readiness.</p>
                    </article>
                    <article className="task-mini-item">
                      <strong>Evidence depth</strong>
                      <p>{builderMembers.filter((item) => (item.evidence_count || 0) >= 5).length} case(s) have at least five evidence items already on file.</p>
                    </article>
                  </div>
                </section>
              </section>
            </React.Fragment>
          ) : selectedMemberRequired ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Select A Member</p>
                <h1>Choose the case before opening the workspace.</h1>
                <p>Petition drafting, endeavor-letter drafting, evidence review, dossier analysis, and batch intake are all member-specific. Choose the member once, then the rest of the attorney sections work against that member record.</p>
              </header>
              <section className="panel" style={{ marginTop: "18px" }}>
                <div className="section-kicker">Member Selector</div>
                <h3 className="section-title">Select member</h3>
                <MemberSearchBox
                  value={memberSearchQuery}
                  onChange={setMemberSearchQuery}
                  total={builderMembers.length}
                  visible={filteredBuilderMembers.length}
                  label="Search cases"
                />
                <label style={{ display: "block", marginTop: "10px" }}>
                  <select value={selectedBuilderMemberId || ""} onChange={(event) => { setSelectedBuilderMemberId(event.target.value); }}>
                    <option value="">Select member</option>
                    {memberSelectorOptions.map((item) => (
                      <option key={item.client_id} value={item.client_id}>
                        {item.display_name} • {caseStatusLabel(item.status)} • {item.readiness_score}% readiness
                      </option>
                    ))}
                  </select>
                </label>
                {selectedBuilderMemberId ? (
                  <div className="form-actions" style={{ marginTop: "14px" }}>
                    <button className="primary compact-btn" type="button" onClick={() => setPortalSection("dossier")}>Open Member Workspace</button>
                  </div>
                ) : null}
              </section>
            </React.Fragment>
          ) : portalSection === "dossier" ? (
            <React.Fragment>
              <header className="hero">
                <p className="eyebrow">Member Dossier</p>
                <h1>{builderMemberDetail?.member?.display_name || "Member"} summary.</h1>
                <p>Attorney view of profile, evidence map, critical role exports, and original contribution exports.</p>
              </header>
              <FilingTimelinePanel data={filingTimeline} busy={filingTimelineBusy} compact />

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
                <section className="panel">
                  <div className="section-kicker">Member Narrative Exports</div>
                  <h3 className="section-title">Template-style member submissions</h3>
                  <p className="section-intro">Review the member-submitted Critical Role and Original Contribution narratives as exported evidence artifacts before drafting or legal follow-up.</p>
                  <div className="builder-layout">
                    <ExportedNarrativePanel
                      title="Critical Role Exports"
                      sectionLabel="Leading Or Critical Role"
                      items={builderMemberDetail?.critical_role_projects || []}
                      emptyText="No critical role exports generated yet."
                    />
                    <ExportedNarrativePanel
                      title="Original Contribution Exports"
                      sectionLabel="Original Contributions"
                      items={builderMemberDetail?.original_contribution_entries || []}
                      emptyText="No original contribution exports generated yet."
                    />
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
                    <div className="section-kicker">Petition Generator</div>
                    <h3 className="section-title">{selectedAttorneyMember?.display_name || "Selected member"} petition workspace</h3>
                    <p className="section-intro">Generate a structured EB1A petition draft from profile, evidence, exports, and attorney strategy.</p>
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
              <FilingTimelinePanel data={filingTimeline} busy={filingTimelineBusy} compact />
              <PetitionAccelerationPanel data={petitionAcceleration} busy={petitionAccelerationBusy} />
            </React.Fragment>
          ) : portalSection === "endeavor" ? (
            <React.Fragment>
              <header className="hero endeavor-hero">
                <p className="eyebrow">Endeavor Letter Generator</p>
                <div className="endeavor-hero-row">
                  <div>
                    <h1>{selectedAttorneyMember?.display_name || "Selected member"} proposed endeavor letter</h1>
                    <p>Smaller-font, merged sections for fast attorney drafting.</p>
                  </div>
                  <div className="endeavor-stat-strip" aria-label="Endeavor case summary">
                    <span><strong>{evidenceItems.length}</strong> evidence</span>
                    <span><strong>{builderMemberDetail?.criteria?.filter((item) => item.evidence_count).length || 0}</strong> criteria</span>
                    <span><strong>{builderMemberDetail?.tasks?.filter((item) => item.status === "open").length || 0}</strong> open tasks</span>
                  </div>
                </div>
              </header>

              <section className="panel endeavor-panel">
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">Attorney Input</div>
                    <h3 className="section-title">Direction, facts, and generated letter</h3>
                    <p className="section-intro">Smaller prompts, same output: use these notes as the instruction set for the endeavor letter.</p>
                  </div>
                  <div className="form-actions">
                    {endeavorDraft ? (
                      <button className="ghost compact-btn" type="button" onClick={() => setEndeavorLetterView((current) => !current)}>
                        {endeavorLetterView ? "Edit Inputs" : "Review Letter"}
                      </button>
                    ) : null}
                    <button className="primary compact-btn" type="button" onClick={() => generateEndeavorLetter(selectedBuilderMemberId)} disabled={endeavorBusy}>
                      {endeavorBusy ? "Generating..." : endeavorDraft ? "Regenerate Letter" : "Generate Letter"}
                    </button>
                  </div>
                </div>

                {!endeavorLetterView ? (
                  <React.Fragment>
                    {endeavorDraft ? (
                      <div className="endeavor-ready-strip">
                        <strong>Latest draft ready.</strong>
                        <span>{endeavorDraft.letter?.estimated_word_count || 0} words • {endeavorDraft.snapshot?.parsed_documents || 0} documents parsed</span>
                        <button className="ghost compact-btn" type="button" onClick={() => setEndeavorLetterView(true)}>Review Letter</button>
                      </div>
                    ) : null}

                    <form className="stacked-form endeavor-form" onSubmit={(event) => { event.preventDefault(); generateEndeavorLetter(selectedBuilderMemberId); }}>
                      <label className="endeavor-field">
                        Who you are
                        <textarea value={endeavorPromptForm.who_you_are} onChange={(event) => setEndeavorPromptField("who_you_are", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        Field of expertise
                        <textarea value={endeavorPromptForm.field_of_expertise} onChange={(event) => setEndeavorPromptField("field_of_expertise", event.target.value)} />
                      </label>
                      <label className="endeavor-field wide">
                        Proposed endeavor
                        <textarea value={endeavorPromptForm.proposed_endeavor} onChange={(event) => setEndeavorPromptField("proposed_endeavor", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        Current work continuity
                        <textarea value={endeavorPromptForm.current_work_continuity} onChange={(event) => setEndeavorPromptField("current_work_continuity", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        Future work plan
                        <textarea value={endeavorPromptForm.future_work_plan} onChange={(event) => setEndeavorPromptField("future_work_plan", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        National importance
                        <textarea value={endeavorPromptForm.national_importance} onChange={(event) => setEndeavorPromptField("national_importance", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        Evidence emphasis
                        <textarea value={endeavorPromptForm.evidence_emphasis} onChange={(event) => setEndeavorPromptField("evidence_emphasis", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        Attorney strategy notes
                        <textarea value={endeavorPromptForm.attorney_strategy_notes} onChange={(event) => setEndeavorPromptField("attorney_strategy_notes", event.target.value)} />
                      </label>
                      <label className="endeavor-field">
                        Tone guidance
                        <textarea value={endeavorPromptForm.tone_guidance} onChange={(event) => setEndeavorPromptField("tone_guidance", event.target.value)} />
                      </label>
                      <label className="endeavor-field wide compact">
                        Length constraints
                        <textarea value={endeavorPromptForm.length_constraints} onChange={(event) => setEndeavorPromptField("length_constraints", event.target.value)} />
                      </label>
                      <div className="form-actions endeavor-submit-row">
                        <button className="primary compact-btn" type="submit" disabled={endeavorBusy}>
                          {endeavorBusy ? "Generating..." : "Generate Endeavor Letter"}
                        </button>
                      </div>
                    </form>
                  </React.Fragment>
                ) : endeavorDraft ? (
                  <React.Fragment>
                    <div className="endeavor-ready-strip review">
                      <strong>Letter review</strong>
                      <span>{endeavorDraft.letter?.estimated_word_count || 0} words • {endeavorDraft.letter?.estimated_page_count || 0} pages • {endeavorDraft.snapshot?.parsed_documents || 0} docs parsed • {endeavorDraft.snapshot?.parsed_with_text || 0} with text</span>
                      <button className="ghost compact-btn" type="button" onClick={() => setEndeavorLetterView(false)}>Edit Inputs</button>
                    </div>

                    <section className="endeavor-review">
                      <div className="letter-paper endeavor-letter-paper">
                        <p className="letter-title">{endeavorDraft.letter?.title}</p>
                        <p>{endeavorDraft.letter?.date_line}</p>
                        <p>U.S. Citizenship and Immigration Services</p>
                        <p>{endeavorDraft.letter?.re_line}</p>
                        <p>{endeavorDraft.letter?.beneficiary_line}</p>
                        <p>{endeavorDraft.letter?.subject_line}</p>
                        <p>{endeavorDraft.letter?.salutation}</p>
                        <p>{endeavorDraft.letter?.opening_paragraph}</p>
                        {(endeavorDraft.letter?.sections || []).map((section, index) => (
                          <div key={`endeavor_letter_${index}`}>
                            {section.heading ? <p className="letter-heading">{section.heading}</p> : null}
                            <p>{section.body}</p>
                          </div>
                        ))}
                        <p>{endeavorDraft.letter?.closing_paragraph}</p>
                        <p className="letter-signature">{endeavorDraft.letter?.signature_line}</p>
                      </div>
                    </section>
                  </React.Fragment>
                ) : null}
              </section>
            </React.Fragment>
          ) : portalSection === "recommendations" ? (
            <RecommendationLetterPanel
              workspace={recommendationWorkspace}
              form={recommendationPromptForm}
              busy={recommendationBusy}
              activeLetterId={activeRecommendationLetterId}
              onFieldChange={updateRecommendationPrompt}
              onSubmit={generateRecommendationLetter}
              onSelectLetter={setActiveRecommendationLetterId}
              onApprove={approveRecommendationLetter}
              onSend={sendRecommendationLetter}
            />
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
    const ops = adminDashboard?.metrics || {};
    const costData = adminCosts || {};
    const awsCosts = costData.aws || {};
    const openaiCosts = costData.openai || {};
    const awsMtd = costPeriodValue(awsCosts, "Monthly", "actual");
    const openaiMtd = costPeriodValue(openaiCosts, "Monthly", "actual");
    const awsProjected = costPeriodValue(awsCosts, "Monthly", "projected");
    const openaiProjected = costPeriodValue(openaiCosts, "Monthly", "projected");
    const dailyAverage = costPeriodValue(awsCosts, "Daily", "actual") + costPeriodValue(openaiCosts, "Daily", "actual");
    const monthlySpend = awsMtd + openaiMtd;
    const projectedTotal = awsProjected + openaiProjected;
    const openIssueTotal = activeIssueCount(adminIssueLog);
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
        <main className="shell admin-shell" style={shellStyle}>
          <aside className="sidebar">
            <PortalBrand onHome={goToPortalHome} label="Go to admin home" />
            <div className="brand-sub">Admin Operations</div>
            <SidebarNav
              items={[
                { value: "home", label: "Admin Home", icon: "H" },
                { value: "health", label: "System Health", icon: "S" },
                { value: "costs", label: "Cost Explorer", icon: "C" },
                { value: "support", label: `Support Tickets${supportSummary.open_count ? ` (${supportSummary.open_count})` : ""}`, icon: "T" },
                { value: "issues", label: `Issue Portal${openIssueTotal ? ` (${openIssueTotal})` : ""}`, icon: "I" },
                { value: "debug", label: "Debug Console", icon: "D" },
                { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}`, icon: "M" },
              ]}
              value={portalSection}
              onChange={setPortalSection}
            />
            <div className="side-card">
              <strong>Admin health</strong>
              <p>Portals online, open issues, and monthly spend stay visible for operations review.</p>
            </div>
            <div className="side-card">
              <strong>At a glance</strong>
              <p>Portals online: {portalHealth.filter((item) => ["online", "healthy"].includes(String(item.status || "").toLowerCase())).length || portalHealth.length || 0}</p>
              <p>Open issues: {openIssueTotal}</p>
              <p>Monthly spend: {formatCostAmount(monthlySpend, awsCosts.currency || openaiCosts.currency || "USD")}</p>
            </div>
            <span className="side-note">Admin portal only</span>
          </aside>
          {sidebarResizer}
          <section className="main admin-main">
            <div className="topbar">
              <div className="topbar-copy">
                <span className="topbar-label">Admin Portal</span>
                <div className="topbar-welcome">Welcome {firstNameFromDisplay(authMember.display_name)}.</div>
                <strong>{subtitleForPortalSection("admin", portalSection)}</strong>
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

            {portalSection === "messages" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Messages</p>
                  <h1>Operations communications.</h1>
                  <p>Keep all inbound and outbound threads in one dedicated place so the operational dashboard stays focused on health and debugging.</p>
                </header>
                {messagePanel}
              </React.Fragment>
            ) : portalSection === "issues" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Issue Portal</p>
                  <h1>Excel-style bug backlog.</h1>
                  <p>Excel-style bug backlog.</p>
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
                  <h1>AWS and OpenAI spend overview.</h1>
                  <p>AWS, OpenAI, and infrastructure spend overview. Refresh pulls latest billing.</p>
                </header>

                <section className="panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Cost Explorer</div>
                      <h3 className="section-title">AWS and OpenAI spend overview</h3>
                      <p className="section-intro">{costData.detail || "Use Refresh to pull the latest cost data into the Admin Portal."}</p>
                    </div>
                    <div className="cost-toolbar">
                      <span className="mini-note">Last refreshed: {formatDateTime(costData.refreshed_at)}</span>
                      <button className="primary compact-btn" type="button" onClick={refreshAdminCosts} disabled={adminCostBusy}>
                        {adminCostBusy ? "Refreshing..." : "Refresh Costs"}
                      </button>
                    </div>
                  </div>
                </section>

                <section className="metrics-grid cost-mini-grid">
                  <MetricCard label="AWS MTD" value={formatCostAmount(awsMtd, awsCosts.currency || "USD")} />
                  <MetricCard label="OpenAI MTD" value={formatCostAmount(openaiMtd, openaiCosts.currency || "USD")} />
                  <MetricCard label="Projected total" value={formatCostAmount(projectedTotal, awsCosts.currency || openaiCosts.currency || "USD")} />
                  <MetricCard label="Daily avg" value={formatCostAmount(dailyAverage, awsCosts.currency || openaiCosts.currency || "USD")} />
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
            ) : portalSection === "health" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Platform Health</p>
                  <h1>AWS tech stack and response times.</h1>
                  <p>Platform health, AWS stack, and response-time visibility.</p>
                </header>

                <section className="panel admin-health-panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Platform Health</div>
                      <h3 className="section-title">AWS tech stack and response times</h3>
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
            ) : portalSection === "support" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Support Tickets</p>
                  <h1>Support queue.</h1>
                  <p>Support ticket triage.</p>
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
                      <div className="section-kicker">Support Tickets</div>
                      <h3 className="section-title">Support queue</h3>
                    </div>
                    <button className="primary compact-btn" type="button" onClick={() => setSupportOpen(true)}>New Ticket</button>
                  </div>
                  <p className="mini-note">{supportTickets.length} visible</p>
                  <div className="support-ticket-table">
                    <div className="support-ticket-head">
                      <span>Ticket</span>
                      <span>Portal</span>
                      <span>Priority</span>
                      <span>Status</span>
                      <span>Owner</span>
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
                        <span>{ticket.portal}</span>
                        <span>{supportPriorityLabel(ticket.priority)}</span>
                        <span className={`status-pill ${ticket.behavior_assessment === "likely_bug" ? "blocked" : ticket.behavior_assessment === "expected_behavior" ? "planned" : "in_progress"}`}>{ticket.behavior_assessment?.replaceAll("_", " ") || ticket.status || "needs verification"}</span>
                        <span>{ticket.owner_name || ticket.assigned_to || ticket.reporter_name || "Unassigned"}</span>
                      </article>
                    )) : <p className="empty-state">No support tickets submitted yet.</p>}
                  </div>
                </section>
              </React.Fragment>
            ) : portalSection === "debug" ? (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Debug Console</p>
                  <h1>Activity and audit log.</h1>
                  <p>Minimal rows with timestamps for debugging user journeys.</p>
                </header>

                <section className="panel admin-table-panel">
                  <div className="panel-header">
                    <div>
                      <div className="section-kicker">Debug Console</div>
                      <h3 className="section-title">Activity and audit log</h3>
                      <p className="section-intro">Minimal rows with timestamps for debugging user journeys.</p>
                    </div>
                    <button className="primary compact-btn" type="button">Export Logs</button>
                  </div>
                  <p className="mini-note">{(adminDashboard?.recent_errors || []).length} visible</p>
                  <div className="debug-error-table">
                    <div className="debug-error-row debug-error-head"><span>Timestamp</span><span>Actor</span><span>Portal</span><span>Action</span><span>Status</span></div>
                    {(adminDashboard?.recent_errors || []).length ? (
                      adminDashboard.recent_errors.map((item) => (
                        <article key={item.id} className="debug-error-row">
                          <span>{formatDateTime(item.created_at)}</span>
                          <span>{item.actor_email || item.user_email || item.member_email || "system"}</span>
                          <span>{item.portal || "system"}</span>
                          <strong>{item.event_type || item.action || item.endpoint || "activity"}</strong>
                          <span className="status-pill blocked">{item.status || "error"}</span>
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
                <PetitionAccelerationPanel data={petitionAcceleration} busy={petitionAccelerationBusy} compact />
              </React.Fragment>
            ) : (
              <React.Fragment>
                <header className="hero">
                  <p className="eyebrow">Admin Portal</p>
                  <h1>Operate the Ascend Product Suite with clear visibility.</h1>
                  <p>Monitor system health, costs, support tickets, issue portal activity, debug logs, and user journeys.</p>
                  <div className="hero-chips">
                    <span className="hero-chip">AWS stack health</span>
                    <span className="hero-chip">Cost Explorer</span>
                    <span className="hero-chip">Issue Portal</span>
                  </div>
                </header>

                <section className="metrics-grid">
                  <MetricCard label="Portals online" value={`${portalHealth.filter((item) => ["online", "healthy"].includes(String(item.status || "").toLowerCase())).length || portalHealth.length || 0}/${portalHealth.length || 5}`} />
                  <MetricCard label="Open issues" value={openIssueTotal} />
                  <MetricCard label="Monthly spend" value={formatCostAmount(monthlySpend, awsCosts.currency || openaiCosts.currency || "USD")} />
                  <MetricCard label="Avg API latency" value={formatResponseMs(responseTimes.find((item) => item.name === "FastAPI")?.avg_ms || ops.avg_api_latency_ms_p50 || 0)} />
                </section>

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
      <main className="shell member-shell" style={shellStyle}>
        <aside className="sidebar">
        <PortalBrand onHome={goToPortalHome} label="Go to member home" />
        <div className="brand-sub">Member Workspace</div>
        <SidebarNav
          items={[
            { value: "home", label: "Member Home", icon: "H" },
            { value: "profile", label: "Profile", icon: "P" },
            { value: "planner", label: "Event Planner", icon: "E" },
            { value: "intake", label: "Evidence Intake", icon: "I" },
            { value: "workspace", label: "Evidence Workspace", icon: "W" },
            { value: "critical_roles", label: "Critical Role Projects", icon: "C" },
            { value: "original_contributions", label: "Original Contributions", icon: "O" },
            { value: "messages", label: `Messages${messageCenter.unread_count ? ` (${messageCenter.unread_count})` : ""}`, icon: "M" },
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
            } else if (next === "workspace") {
              setView({ type: "workspace", criterionCode: "" });
              setSelectedFolderId("");
            } else if (next === "critical_roles") {
              setView({ type: "critical_roles", criterionCode: "" });
            } else if (next === "original_contributions") {
              setView({ type: "original_contributions", criterionCode: "" });
            } else if (next === "messages") {
              setView({ type: "messages", criterionCode: "" });
            } else {
              setView({ type: "home", criterionCode: "" });
            }
          }}
        />
        <div className="side-card">
          <strong>Welcome {dashboard.client.display_name}</strong>
          <p>Your portal is focused only on evidence intake, organization, and next steps.</p>
        </div>
        <div className="side-card">
          <strong>At a glance</strong>
          <p>Readiness: {dashboard.metrics.readiness_score}%</p>
          <p>Evidence items: {dashboard.metrics.evidence_count}</p>
          <p>Criteria started: {dashboard.metrics.criteria_started}</p>
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
      {sidebarResizer}

      <section className="main">
        <div className="topbar">
          <div className="topbar-copy">
            <span className="topbar-label">{view.type === "workspace" ? "Evidence Workspace" : view.type === "profile" ? "Member Profile" : view.type === "critical_roles" ? "Critical Role Projects" : view.type === "original_contributions" ? "Original Contributions" : view.type === "planner" ? "Event Planner" : view.type === "intake" ? "Evidence Intake" : view.type === "messages" ? "Messages" : "Member Home"}</span>
            <div className="topbar-welcome">Welcome {(authMember.display_name || "").split(" ")[0] || authMember.display_name}.</div>
            <strong>{view.type === "workspace" ? "Organize files and folders by EB1A criterion" : view.type === "profile" ? "Keep your attorney-ready profile current" : view.type === "critical_roles" ? "Capture one detailed project at a time" : view.type === "original_contributions" ? "Document originality, significance, and adoption" : view.type === "planner" ? "Track upcoming opportunities and target dates" : view.type === "intake" ? "Upload and review evidence in a focused intake page" : view.type === "messages" ? "Keep conversations in one dedicated workspace" : "Evidence intake, planning, and organization"}</strong>
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

        {view.type === "home" ? (
          <React.Fragment>
            <header className="hero">
              <p className="eyebrow">Member Portal</p>
              <h1>Welcome {authMember.display_name?.split(" ")[0] || dashboard.client.display_name}.</h1>
              <p>Capture evidence, use guided EB1A forms, and keep each category organized for attorney review.</p>
              <div className="hero-chips">
                <span className="hero-chip">AI-assisted intake</span>
                <span className="hero-chip">Guided EB1A forms</span>
                <span className="hero-chip">Drive-like folders</span>
                <span className="hero-chip">Browser back and forward friendly</span>
              </div>
            </header>

            <section className="metrics-grid">
              <MetricCard label="Readiness" value={`${dashboard.metrics.readiness_score}%`} />
              <MetricCard label="Evidence items" value={dashboard.metrics.evidence_count} />
              <MetricCard label="Open tasks" value={dashboard.metrics.open_tasks} />
              <MetricCard label="Criteria started" value={dashboard.metrics.criteria_started} />
            </section>
            <FilingTimelinePanel data={filingTimeline} busy={filingTimelineBusy} memberCommitment dashboard={dashboard} onOpenIntake={() => setView({ type: "intake", criterionCode: "" })} />
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
            <MemberEvidenceCoveragePanel
              criteria={dashboard.criteria || []}
              evidence={evidenceItems || []}
              criteriaByCode={criteriaByCode}
              onOpenCriterion={(code) => setView(memberViewForCriterion(code))}
            />
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
                      {dashboard.criteria.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
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
              <p className="section-intro intake-intro">Upload evidence with AI assistance or manual category selection. Review before saving.</p>
              <span className="soft-badge">Review before saving</span>
              <p className="intake-helper">Choose the faster AI route or place the evidence yourself. Manual uploads only require a file and category.</p>

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
                        {dashboard.criteria.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
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
                  <h3>{draft.fallback_used ? "Manual Review Recommended" : "Review Draft"}</h3>
                  {draft.fallback_used ? (
                    <p className="empty-state">The portal could not confidently classify this file automatically. Please review the suggested category and adjust it before saving.</p>
                  ) : null}
                  <dl>
                    <div><dt>Suggested category</dt><dd>{criteriaByCode[draft.criterion_code]?.name || draft.criterion_code}</dd></div>
                    <div><dt>Suggested evidence type</dt><dd>{draft.document_type || "Other"}</dd></div>
                    <div><dt>Suggested title</dt><dd>{draft.title}</dd></div>
                    <div><dt>Summary</dt><dd>{draft.ai_description}</dd></div>
                    {!draft.fallback_used ? <div><dt>Confidence</dt><dd>{draft.quality_score}%</dd></div> : null}
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
                          {dashboard.criteria.map((criterion) => <option key={criterion.code} value={criterion.code}>{criterion.name}</option>)}
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
                  <label className="consent-line"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>I approve this evidence draft and want to save it.</span></label>
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

              <section className="intake-history-panel">
                <div className="panel-header">
                  <div>
                    <div className="section-kicker">Upload History</div>
                    <h3 className="section-title">Submitted evidence history</h3>
                    <p className="section-intro">Review what you have already uploaded, when it was saved, and which EB1A category it supports.</p>
                  </div>
                  <span>{memberIntakeHistory.length}</span>
                </div>
                {memberIntakeHistory.length ? (
                  <div className="intake-history-table">
                    <div className="intake-history-head">
                      <button className="intake-sort-btn" type="button" onClick={() => toggleIntakeSort("evidence")}>
                        <span>Evidence</span>
                        <strong>{intakeSortLabel("evidence")}</strong>
                      </button>
                      <button className="intake-sort-btn" type="button" onClick={() => toggleIntakeSort("category")}>
                        <span>Category</span>
                        <strong>{intakeSortLabel("category")}</strong>
                      </button>
                      <button className="intake-sort-btn" type="button" onClick={() => toggleIntakeSort("uploaded")}>
                        <span>Uploaded</span>
                        <strong>{intakeSortLabel("uploaded")}</strong>
                      </button>
                      <button className="intake-sort-btn" type="button" onClick={() => toggleIntakeSort("type")}>
                        <span>Type</span>
                        <strong>{intakeSortLabel("type")}</strong>
                      </button>
                      <span>Links</span>
                    </div>
                    {memberIntakeHistory.map((item) => (
                      <article
                        key={item.id || item.file_name}
                        className="intake-history-row"
                        style={{ "--category-accent": criterionAccent(item.criterion_code) }}
                      >
                        <div className="intake-history-cell intake-history-evidence">
                          <strong>{item.title || item.file_name || "Uploaded evidence"}</strong>
                        </div>
                        <div className="intake-history-cell">
                          <span className="intake-category-badge">{criteriaByCode[item.criterion_code]?.name || item.criterion_code || "Uncategorized"}</span>
                        </div>
                        <div className="intake-history-cell">
                          <span>{formatUploadedAt(item.created_at)}</span>
                        </div>
                        <div className="intake-history-cell">
                          <span>{item.document_type || "Other"}</span>
                        </div>
                        <div className="intake-history-cell intake-history-actions">
                          {item.open_url ? <a href={item.open_url} target="_blank" rel="noreferrer">Open evidence</a> : null}
                          <button
                            className="ghost compact-btn compact-link-btn"
                            type="button"
                            onClick={() => setView(memberViewForCriterion(item.criterion_code))}
                          >
                            Review category
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="empty-state">No submitted uploads yet. Once you save evidence here, the history will appear in this list.</p>
                )}
              </section>
            </section>
        ) : view.type === "critical_roles" ? (
          <section className="profile-panel">
            <div className="panel-header profile-header">
              <div>
                <div className="section-kicker">Leading Or Critical Role</div>
                <h3 className="section-title">Critical Role Projects</h3>
                <p className="section-intro">A strong critical role entry shows that you held a job title with responsibilities central to a distinguished organization or unit, and that your work materially affected growth, revenue, product direction, compliance, market expansion, or other high-stakes outcomes. <em>Examples: leading a global launch, owning a platform strategy, driving a major market expansion, or being the person leadership relied on for a business-critical initiative.</em></p>
              </div>
            </div>
            <section className="critical-role-workspace">
              <div className="critical-role-overview">
                <div>
                  <div className="section-kicker">Project-by-project intake</div>
                  <h4 className="section-title">Attorney-ready member details</h4>
                  <p className="section-intro"><em>Save Draft</em> at any time and return later. Use <em>Submit Project</em> only when that entry is ready for attorney review. Each summary card opens the full project detail editor.</p>
                </div>
                <button className="primary compact-btn" type="button" onClick={startNewCriticalRoleProject}>Add Project</button>
              </div>

              <div className="critical-role-guidance">
                <strong>What attorneys need here</strong>
                <ul className="guidance-list">
                  <li>Create a separate entry for each major project. <em>Do not combine different employers in one write-up.</em></li>
                  <li>Contract, part-time, and founder work can still be relevant if the role was truly leading or critical. <em>The issue is not the pay structure; it is whether the role materially mattered.</em></li>
                  <li>Explain why the organization was distinguished, then explain why your project mattered inside that organization. <em>Think market leadership, scale, user base, flagship products, or industry reputation.</em></li>
                  <li>Quantify business value with revenue, cost savings, adoption, users reached, launch speed, market expansion, risk reduction, or compliance impact whenever you can. <em>Examples: 4B users reached, 50% faster releases, $36M enabled, 30% fewer issues.</em></li>
                  <li>Use the peer-distinction section to show how your expertise went beyond your title, not just to repeat responsibilities. <em>Explain why leadership trusted you, why peers relied on you, or why your judgment was uncommon.</em></li>
                </ul>
              </div>

              <div className="critical-role-layout">
                <aside className="critical-role-list panel">
                  <div className="panel-header">
                    <h3>Projects</h3>
                    <span>{criticalRoleProjects.length}</span>
                  </div>
                  {criticalRoleProjects.length ? (
                    <div className="critical-role-list-items">
                      {criticalRoleProjects.map((project) => (
                        <button
                          key={project.id}
                          type="button"
                          className={`critical-role-card ${activeCriticalRoleId === project.id ? "active" : ""}`}
                          onClick={() => openCriticalRoleProject(project)}
                        >
                          <strong>{project.project_name || "Untitled project"}</strong>
                          <span>{project.organization_name || "Organization pending"}{project.role_title ? ` • ${project.role_title}` : ""}</span>
                          <span>{formatProjectDateRange(project.project_start_date, project.project_end_date, false)}{project.workflow_status ? ` • ${project.workflow_status}` : ""}</span>
                          <p>{criticalRoleProjectCardMetric(project)}</p>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-state">No critical role projects added yet. Start with the strongest project where your role was clearly central and measurable.</p>
                  )}
                </aside>

                <form className="critical-role-form panel" onSubmit={(event) => event.preventDefault()}>
                  <div className="panel-header">
                    <h3>{activeCriticalRoleId ? "Edit project" : "New project"}</h3>
                    <span>{criticalRoleForm.workflow_status === "submitted" ? "Submitted" : "Draft"}</span>
                  </div>

                  <div className="critical-role-section">
                    <h4>Organization</h4>
                    <div className="profile-grid">
                      <label>
                        Organization Name *
                        <input value={criticalRoleForm.organization_name} onChange={(event) => setCriticalRoleField("organization_name", event.target.value)} required placeholder="Example: Meta, Google DeepMind, Mayo Clinic, Stripe" />
                        <span className="field-help">Use the formal company or institution name exactly as it should appear in attorney drafts.</span>
                      </label>
                      <label>
                        Business Unit / Team
                        <input value={criticalRoleForm.organization_unit} onChange={(event) => setCriticalRoleField("organization_unit", event.target.value)} placeholder="Example: Payments Platform, AI Store, Research Lab" />
                        <span className="field-help">Name the unit where your project lived so the legal team can frame your specific sphere of responsibility.</span>
                      </label>
                      <label>
                        Organization Location
                        <input value={criticalRoleForm.organization_location} onChange={(event) => setCriticalRoleField("organization_location", event.target.value)} placeholder="City, State, Country" />
                      </label>
                      <label>
                        Organization Website
                        <input value={criticalRoleForm.organization_website} onChange={(event) => setCriticalRoleField("organization_website", event.target.value)} placeholder="https://example.com" />
                      </label>
                      <label>
                        Employment Type
                        <select value={criticalRoleForm.employment_type} onChange={(event) => setCriticalRoleField("employment_type", event.target.value)}>
                          <option value="">Choose one</option>
                          {EMPLOYMENT_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                        <span className="field-help">The template notes that W-2, contract, and part-time work can still qualify if the role itself was critical.</span>
                      </label>
                      {renderMemberMagicTextarea("critical_role", "organization_distinctiveness", "Why This Organization Was Distinguished", {
                        className: "profile-span-2",
                        placeholder: "Describe market leadership, scale, brand recognition, flagship products, industry position, or why the organization is notable in its field.",
                        help: "Focus on size, market presence, user base, reputation, or industry contribution so attorneys can show the employer was not ordinary.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "organization_achievements", "Organization Achievements, Awards, or Reputation Signals", {
                        className: "profile-span-2",
                        placeholder: "Examples: market share, awards, valuation, public recognition, flagship products, global reach, research impact.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Role</h4>
                    <div className="profile-grid">
                      <label>
                        Job Title / Role Title *
                        <input value={criticalRoleForm.role_title} onChange={(event) => setCriticalRoleField("role_title", event.target.value)} placeholder="Example: Senior Product Manager, Principal Scientist, Director of Engineering" />
                      </label>
                      <label>
                        Role Start Date
                        <input type="date" value={criticalRoleForm.role_start_date} onChange={(event) => setCriticalRoleField("role_start_date", event.target.value)} />
                      </label>
                      <label>
                        Role End Date
                        <input type="date" value={criticalRoleForm.role_end_date} onChange={(event) => setCriticalRoleField("role_end_date", event.target.value)} disabled={criticalRoleForm.is_current_role} />
                      </label>
                      <label className="consent-line">
                        <input type="checkbox" checked={criticalRoleForm.is_current_role} onChange={(event) => setCriticalRoleField("is_current_role", event.target.checked)} />
                        <span>This is my current role</span>
                      </label>
                      {renderMemberMagicTextarea("critical_role", "role_summary", "Role Summary", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Summarize the role in attorney-friendly terms and explain why the responsibilities were crucial to the organization.",
                        help: "This should read like the short explanation an attorney would use to describe why the position mattered.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "role_responsibilities", "Core Responsibilities", {
                        className: "profile-span-2",
                        placeholder: "List the highest-value responsibilities: product strategy, launch ownership, technical leadership, stakeholder management, compliance ownership, revenue responsibility, etc.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "role_evolution", "How The Role Evolved", {
                        className: "profile-span-2",
                        placeholder: "Explain how your scope grew, what higher-stakes work you inherited, and how the organization relied on you over time.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "leadership_scope", "Leadership Scope", {
                        placeholder: "Teams led, regions covered, budget owned, products managed, or executives supported.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "cross_functional_partners", "Cross-functional Partners", {
                        placeholder: "Engineering, design, sales, policy, legal, research, operations, regional teams, partner organizations.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Project</h4>
                    <div className="profile-grid">
                      <label>
                        Project Name *
                        <input value={criticalRoleForm.project_name} onChange={(event) => setCriticalRoleField("project_name", event.target.value)} required placeholder="Example: Global Payments Expansion, AI Safety Platform, Clinical Decision Engine" />
                      </label>
                      <label>
                        Project Status
                        <select value={criticalRoleForm.project_status} onChange={(event) => setCriticalRoleField("project_status", event.target.value)}>
                          {PROJECT_STATUS_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </label>
                      <label>
                        Project Start Date
                        <input type="date" value={criticalRoleForm.project_start_date} onChange={(event) => setCriticalRoleField("project_start_date", event.target.value)} />
                      </label>
                      <label>
                        Project End Date
                        <input type="date" value={criticalRoleForm.project_end_date} onChange={(event) => setCriticalRoleField("project_end_date", event.target.value)} />
                      </label>
                      {renderMemberMagicTextarea("critical_role", "project_summary", "Project Summary", {
                        className: "profile-span-2",
                        placeholder: "What was the initiative, what did it do, and why was it important to the organization?",
                      })}
                      {renderMemberMagicTextarea("critical_role", "business_need", "Business Need Or Problem To Solve", {
                        className: "profile-span-2",
                        placeholder: "Describe the urgent need, revenue problem, platform gap, market opportunity, or operational bottleneck.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "strategic_importance", "Strategic Importance", {
                        className: "profile-span-2",
                        placeholder: "Explain why leadership cared: market expansion, user trust, retention, AI leadership, infrastructure modernization, payments growth, etc.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Your contribution and value</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("critical_role", "contributions_summary", "Your Specific Contributions", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Spell out what you personally ideated, built, led, approved, designed, negotiated, launched, or rescued.",
                        help: "Use direct ownership language so the attorneys can distinguish your work from the team’s work.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "innovation_originality", "Originality / Innovation", {
                        className: "profile-span-2",
                        placeholder: "What was novel, first-of-its-kind, unusually hard, or strategically inventive about your approach?",
                      })}
                      {renderMemberMagicTextarea("critical_role", "business_value_summary", "Business Value Summary", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Summarize the measurable business value this work created for the organization or users.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "quantitative_metrics", "Quantitative Metrics", {
                        className: "profile-span-2",
                        placeholder: "Include user counts, revenue impact, adoption metrics, faster launch timelines, reduced incident rates, CSAT gains, downloads, retention, or global reach.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "revenue_impact", "Revenue / Monetization Impact", {
                        placeholder: "Examples: annual revenue enabled, subscription uplift, new market spend, transaction value supported.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "cost_savings", "Cost Savings / Efficiency", {
                        placeholder: "Examples: reduced headcount need, time saved, faster release cycle, fewer manual steps.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "efficiency_gain", "Speed / Operational Gain", {
                        placeholder: "Examples: launch in days instead of months, 50% faster release, 30% maintenance reduction.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "user_or_customer_impact", "User / Customer Impact", {
                        placeholder: "Who benefited and at what scale? Mention users, developers, customers, patients, or enterprises.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "market_or_geographic_impact", "Market / Geographic Impact", {
                        placeholder: "Mention countries, regions, enterprise accounts, new market entry, or strategic partnerships.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "compliance_or_risk_impact", "Compliance / Risk Impact", {
                        placeholder: "Describe trust, safety, privacy, policy, fraud reduction, or legal compliance impact if relevant.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Why you stood out</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("critical_role", "peer_distinction_summary", "How You Were Distinguished From Peers", {
                        className: "profile-span-2",
                        placeholder: "Explain how your leadership, judgment, product sense, technical depth, innovation, or execution went beyond what peers typically delivered.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "mentorship_leadership", "Mentorship / Leadership Beyond Title", {
                        placeholder: "Coaching, mentoring, shaping team culture, setting frameworks, guiding cross-functional teams.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "executive_visibility", "Executive Visibility / Trusted Advisor Role", {
                        placeholder: "How closely leadership relied on you, which VPs or executives reviewed the work, and what decisions you influenced.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Evidence and attorney draft</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("critical_role", "evidence_available", "Evidence You Can Potentially Provide", {
                        className: "profile-span-2",
                        placeholder: "List emails, launch docs, decks, org charts, screenshots, press coverage, metrics dashboards, performance reviews, patents, awards, or recommendation letter sources.",
                      })}
                      {renderMemberMagicTextarea("critical_role", "attorney_friendly_summary", "Attorney-friendly Summary", {
                        className: "profile-span-2",
                        placeholder: "Write a tight paragraph the legal team could reuse in a petition draft to explain why your role on this project was leading or critical.",
                      })}
                    </div>
                  </div>

                  <div className="form-actions">
                    <button className="ghost compact-btn" type="button" disabled={criticalRoleBusy} onClick={saveCriticalRoleProjectDraft}>{criticalRoleBusy ? "Saving..." : "Save Draft"}</button>
                    <button className="primary compact-btn" type="button" disabled={criticalRoleBusy} onClick={submitCriticalRoleProject}>{criticalRoleBusy ? "Submitting..." : activeCriticalRoleId ? "Submit Project" : "Create And Submit"}</button>
                    <button className="ghost compact-btn" type="button" onClick={startNewCriticalRoleProject}>New Blank Project</button>
                    {activeCriticalRoleId ? <button className="danger compact-btn" type="button" onClick={deleteCriticalRoleProject} disabled={criticalRoleBusy}>Delete</button> : null}
                  </div>
                </form>
              </div>
            </section>
          </section>
        ) : view.type === "original_contributions" ? (
          <section className="profile-panel">
            <div className="panel-header profile-header">
              <div>
                <div className="section-kicker">Original Contributions</div>
                <h3 className="section-title">Original Contributions</h3>
                <p className="section-intro">A strong original contributions entry shows that you introduced something genuinely new and that it mattered beyond routine team output. The legal team is looking for originality plus significance. <em>Examples: a first-of-its-kind workflow, a research contribution adopted by others, a platform capability that changed how customers operate, or a method that saved major time or money at scale.</em></p>
              </div>
            </div>
            <section className="critical-role-workspace">
              <div className="critical-role-overview">
                <div>
                  <div className="section-kicker">Contribution-by-contribution intake</div>
                  <h4 className="section-title">Attorney-ready member details</h4>
                  <p className="section-intro"><em>Save Draft</em> at any time and return later. Use <em>Submit Contribution</em> only when that entry is ready for attorney review. If you have multiple distinct innovations, create separate entries rather than combining them.</p>
                </div>
                <button className="primary compact-btn" type="button" onClick={startNewOriginalContribution}>Add Contribution</button>
              </div>

              <div className="critical-role-guidance">
                <strong>What attorneys need here</strong>
                <ul className="guidance-list">
                  <li>Each entry should satisfy all three prongs: a real contribution, something original, and major significance. <em>Do not stop at “I worked on it.” Explain what was actually new.</em></li>
                  <li>Work-related contributions and external contributions can both count, but explain the context clearly. <em>Research, grant work, entrepreneurship, and nonprofit work can all matter when supported well.</em></li>
                  <li>Metrics matter. Include adoption, users, citations, funding, valuation, revenue, time savings, bug reduction, or quality gains wherever possible. <em>Examples: 90% time reduction, 10,000 adopters, 20% revenue growth, 50% fewer production bugs.</em></li>
                  <li>If the contribution had multiple strong use cases, describe each one so the legal team can choose the best framing later. <em>For example, one capability may help global testing, pricing experiments, and launch quality.</em></li>
                  <li>Show broader field influence through recognition, press, community mentions, or adoption letters when available. <em>Examples: LinkedIn posts, Medium articles, press releases, citations, or third-party letters.</em></li>
                </ul>
              </div>

              <div className="critical-role-layout">
                <aside className="critical-role-list panel">
                  <div className="panel-header">
                    <h3>Contributions</h3>
                    <span>{originalContributions.length}</span>
                  </div>
                  {originalContributions.length ? (
                    <div className="critical-role-list-items">
                      {originalContributions.map((entry) => (
                        <button
                          key={entry.id}
                          type="button"
                          className={`critical-role-card ${activeOriginalContributionId === entry.id ? "active" : ""}`}
                          onClick={() => openOriginalContribution(entry)}
                        >
                          <strong>{entry.contribution_title || "Untitled contribution"}</strong>
                          <span>{entry.organization_name || "Organization pending"}{entry.contribution_category ? ` • ${entry.contribution_category}` : ""}</span>
                          <span>{formatProjectDateRange(entry.contribution_start_date, entry.contribution_end_date, false)}{entry.workflow_status ? ` • ${entry.workflow_status}` : ""}</span>
                          <p>{originalContributionCardMetric(entry)}</p>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="empty-state">No original contributions added yet. Start with the strongest innovation where you can explain originality and measurable significance.</p>
                  )}
                </aside>

                <form className="critical-role-form panel" onSubmit={(event) => event.preventDefault()}>
                  <div className="panel-header">
                    <h3>{activeOriginalContributionId ? "Edit contribution" : "New contribution"}</h3>
                    <span>{originalContributionForm.workflow_status === "submitted" ? "Submitted" : "Draft"}</span>
                  </div>

                  <div className="critical-role-section">
                    <h4>Contribution basics</h4>
                    <div className="profile-grid">
                      <label>
                        Contribution Title *
                        <input value={originalContributionForm.contribution_title} onChange={(event) => setOriginalContributionField("contribution_title", event.target.value)} required placeholder="Example: Experimentation Platform, Diagnostic Model, Fraud Detection Framework" />
                        <span className="field-help">Name the innovation, framework, feature, methodology, research output, or initiative as specifically as possible.</span>
                      </label>
                      <label>
                        Contribution Category
                        <select value={originalContributionForm.contribution_category} onChange={(event) => setOriginalContributionField("contribution_category", event.target.value)}>
                          {CONTRIBUTION_CATEGORY_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </label>
                      <label>
                        Field Of Expertise
                        <input value={originalContributionForm.field_of_expertise} onChange={(event) => setOriginalContributionField("field_of_expertise", event.target.value)} placeholder="Technical Product Management, AI, Payments, Research, etc." />
                      </label>
                      <label>
                        Job Title
                        <input value={originalContributionForm.job_title} onChange={(event) => setOriginalContributionField("job_title", event.target.value)} placeholder="Senior Product Manager, Founder, Principal Researcher, etc." />
                      </label>
                      <label>
                        Organization Or Context
                        <input value={originalContributionForm.organization_name} onChange={(event) => setOriginalContributionField("organization_name", event.target.value)} placeholder="Employer, research lab, startup, nonprofit, or external collaboration" />
                      </label>
                      <label>
                        Project Or Product Name
                        <input value={originalContributionForm.project_name} onChange={(event) => setOriginalContributionField("project_name", event.target.value)} placeholder="Example: Ads Ranking Platform, Oncology Research Program, Enterprise Risk Suite" />
                      </label>
                      <label>
                        Contribution Status
                        <select value={originalContributionForm.contribution_status} onChange={(event) => setOriginalContributionField("contribution_status", event.target.value)}>
                          {PROJECT_STATUS_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                        </select>
                      </label>
                      <label>
                        Start Date
                        <input type="date" value={originalContributionForm.contribution_start_date} onChange={(event) => setOriginalContributionField("contribution_start_date", event.target.value)} />
                      </label>
                      <label>
                        End Date
                        <input type="date" value={originalContributionForm.contribution_end_date} onChange={(event) => setOriginalContributionField("contribution_end_date", event.target.value)} />
                      </label>
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Originality and innovation</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("original_contribution", "originality_summary", "What Was Original", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Describe the specific innovation you introduced and why it was unique in your field or company.",
                        help: "Attorneys need enough detail to show this was not routine execution or a small variation on existing work.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "challenging_paradigms", "How It Challenged Existing Methods Or Paradigms", {
                        className: "profile-span-2",
                        placeholder: "Explain what the old way was, why it was limited, and how your contribution changed the approach.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "prior_state_of_field", "Prior State Of The Field Or Workflow", {
                        className: "profile-span-2",
                        placeholder: "Describe the baseline process, common limitations, and the pain points that existed before your contribution.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Your role and distinct contribution</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("original_contribution", "work_vs_external_context", "Work-related Vs External Context", {
                        className: "profile-span-2",
                        placeholder: "Clarify whether this was work-related, research-based, entrepreneurial, grant-related, nonprofit, or external collaboration.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "personal_role", "Your Personal Role", {
                        placeholder: "Product lead, researcher, founder, inventor, principal engineer, etc.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "distinct_contribution_summary", "Your Distinct Contribution", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Spell out exactly what you personally introduced, designed, led, authored, built, validated, or commercialized.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Problem, solution, and use cases</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("original_contribution", "technical_or_business_problem", "Technical Or Business Problem", {
                        className: "profile-span-2",
                        placeholder: "Describe the pain point, inefficiency, market gap, scientific limitation, or operational challenge your contribution addressed.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "solution_or_innovation", "Solution Or Innovation You Created", {
                        className: "profile-span-2",
                        placeholder: "Explain the mechanism, framework, feature, app, method, product, or process you created.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "unique_features", "Unique Features Or Notable Use Cases", {
                        className: "profile-span-2",
                        placeholder: "List the strongest use cases, novel features, downstream capabilities, or examples showing why the contribution was different.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Impact and major significance</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("original_contribution", "impact_metrics", "Impact Metrics", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Include numbers wherever possible: time savings, users reached, revenue, citations, funding, valuation, bug reduction, adoption, quality improvement, or market size.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "adoption_scale", "Adoption Scale", {
                        placeholder: "Who used or adopted it, and at what scale?",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "beneficiary_summary", "Beneficiaries", {
                        placeholder: "Developers, researchers, hospitals, customers, startups, platform users, or the broader public.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "time_savings", "Time Savings", {
                        placeholder: "Examples: reduced a 6-week process to 1 week, cut testing by 90%.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "cost_savings", "Cost Savings", {
                        placeholder: "Examples: saved millions in labor, infrastructure, or lost revenue.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "revenue_impact", "Revenue Or Funding Impact", {
                        placeholder: "Examples: increased spend, monetization, funding raised, valuation achieved.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "quality_or_risk_impact", "Quality / Risk Impact", {
                        placeholder: "Bug reduction, quality improvement, reduced escalations, safer releases, policy or compliance improvement.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "field_wide_impact", "Broader Field Impact", {
                        className: "profile-span-2",
                        required: true,
                        placeholder: "Explain how the contribution influenced the broader field, market, ecosystem, or industry rather than helping only one team.",
                      })}
                    </div>
                  </div>

                  <div className="critical-role-section">
                    <h4>Recognition and evidence</h4>
                    <div className="profile-grid">
                      {renderMemberMagicTextarea("original_contribution", "recognition_and_influence", "Recognition And Influence", {
                        className: "profile-span-2",
                        placeholder: "Describe recognition by other experts, adoption by others, conference talks, citations, internal executive recognition, or industry influence.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "media_or_public_mentions", "Media Or Public Mentions", {
                        className: "profile-span-2",
                        placeholder: "List Medium posts, LinkedIn posts, press releases, media articles, public product pages, or field references.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "adoption_letters_targets", "Adoption Letters Targets", {
                        placeholder: "Who could write letters about adoption or significance? Include names, companies, titles, and likely use cases if known.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "evidence_available", "Evidence Available", {
                        placeholder: "Product docs, citations, dashboards, screenshots, patents, press, external references, executive emails, research metrics.",
                      })}
                      {renderMemberMagicTextarea("original_contribution", "attorney_friendly_summary", "Attorney-friendly Summary", {
                        className: "profile-span-2",
                        placeholder: "Write a short paragraph the legal team could reuse to explain why this contribution was original and of major significance.",
                      })}
                    </div>
                  </div>

                  <div className="form-actions">
                    <button className="ghost compact-btn" type="button" disabled={originalContributionBusy} onClick={saveOriginalContributionDraft}>{originalContributionBusy ? "Saving..." : "Save Draft"}</button>
                    <button className="primary compact-btn" type="button" disabled={originalContributionBusy} onClick={submitOriginalContribution}>{originalContributionBusy ? "Submitting..." : activeOriginalContributionId ? "Submit Contribution" : "Create And Submit"}</button>
                    <button className="ghost compact-btn" type="button" onClick={startNewOriginalContribution}>New Blank Contribution</button>
                    {activeOriginalContributionId ? <button className="danger compact-btn" type="button" onClick={deleteOriginalContribution} disabled={originalContributionBusy}>Delete</button> : null}
                  </div>
                </form>
              </div>
            </section>
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

            {false ? (
              <section className="critical-role-workspace">
                <div className="critical-role-overview">
                  <div>
                    <div className="section-kicker">Leading Or Critical Role</div>
                    <h4 className="section-title">Project-by-project attorney intake</h4>
                    <p className="section-intro">Add one entry for each qualifying project within an organization. Keep companies separate, quantify impact wherever possible, and explain why both your role and the organization were distinguished.</p>
                  </div>
                  <button className="primary compact-btn" type="button" onClick={startNewCriticalRoleProject}>Add Project</button>
                </div>

                <div className="critical-role-guidance">
                  <strong>What attorneys need here</strong>
                  <ul className="guidance-list">
                    <li>Create a separate entry for each major project. Do not combine different employers in one write-up.</li>
                    <li>Contract, part-time, and founder work can still be relevant if the role was truly leading or critical.</li>
                    <li>Explain why the organization was distinguished, then explain why your project mattered inside that organization.</li>
                    <li>Quantify business value with revenue, cost savings, adoption, users reached, launch speed, market expansion, risk reduction, or compliance impact whenever you can.</li>
                    <li>Use the peer-distinction section to show how your expertise went beyond your title, not just to repeat responsibilities.</li>
                  </ul>
                </div>

                <div className="critical-role-layout">
                  <aside className="critical-role-list panel">
                    <div className="panel-header">
                      <h3>Projects</h3>
                      <span>{criticalRoleProjects.length}</span>
                    </div>
                    {criticalRoleProjects.length ? (
                      <div className="critical-role-list-items">
                        {criticalRoleProjects.map((project) => (
                          <button
                            key={project.id}
                            type="button"
                            className={`critical-role-card ${activeCriticalRoleId === project.id ? "active" : ""}`}
                            onClick={() => openCriticalRoleProject(project)}
                          >
                            <strong>{project.project_name || "Untitled project"}</strong>
                            <span>{project.organization_name || "Organization pending"}{project.role_title ? ` • ${project.role_title}` : ""}</span>
                            <span>{formatProjectDateRange(project.project_start_date, project.project_end_date, false)}</span>
                            <p>{criticalRoleProjectCardMetric(project)}</p>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="empty-state">No critical role projects added yet. Start with the strongest project where your role was clearly central and measurable.</p>
                    )}
                  </aside>

                  <form className="critical-role-form panel" onSubmit={saveCriticalRoleProject}>
                    <div className="panel-header">
                      <h3>{activeCriticalRoleId ? "Edit project" : "New project"}</h3>
                      <span>{criticalRoleForm.organization_name || "Draft"}</span>
                    </div>

                    <div className="critical-role-section">
                      <h4>Organization</h4>
                      <div className="profile-grid">
                        <label>
                          Organization Name *
                          <input value={criticalRoleForm.organization_name} onChange={(event) => setCriticalRoleField("organization_name", event.target.value)} required />
                          <span className="field-help">Use the formal company or institution name exactly as it should appear in attorney drafts.</span>
                        </label>
                        <label>
                          Business Unit / Team
                          <input value={criticalRoleForm.organization_unit} onChange={(event) => setCriticalRoleField("organization_unit", event.target.value)} placeholder="Example: Payments Platform, AI Store, Research Lab" />
                          <span className="field-help">Name the unit where your project lived so the legal team can frame your specific sphere of responsibility.</span>
                        </label>
                        <label>
                          Organization Location
                          <input value={criticalRoleForm.organization_location} onChange={(event) => setCriticalRoleField("organization_location", event.target.value)} placeholder="City, State, Country" />
                        </label>
                        <label>
                          Organization Website
                          <input value={criticalRoleForm.organization_website} onChange={(event) => setCriticalRoleField("organization_website", event.target.value)} placeholder="https://example.com" />
                        </label>
                        <label>
                          Employment Type
                          <select value={criticalRoleForm.employment_type} onChange={(event) => setCriticalRoleField("employment_type", event.target.value)}>
                            <option value="">Choose one</option>
                            {EMPLOYMENT_TYPE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                          </select>
                          <span className="field-help">The template notes that W-2, contract, and part-time work can still qualify if the role itself was critical.</span>
                        </label>
                        <label className="profile-span-2">
                          Why This Organization Was Distinguished
                          <textarea value={criticalRoleForm.organization_distinctiveness} onChange={(event) => setCriticalRoleField("organization_distinctiveness", event.target.value)} placeholder="Describe market leadership, scale, brand recognition, flagship products, industry position, or why the organization is notable in its field." />
                          <span className="field-help">Focus on size, market presence, user base, reputation, or industry contribution so attorneys can show the employer was not ordinary.</span>
                        </label>
                        <label className="profile-span-2">
                          Organization Achievements, Awards, or Reputation Signals
                          <textarea value={criticalRoleForm.organization_achievements} onChange={(event) => setCriticalRoleField("organization_achievements", event.target.value)} placeholder="Examples: market share, awards, valuation, public recognition, flagship products, global reach, research impact." />
                        </label>
                      </div>
                    </div>

                    <div className="critical-role-section">
                      <h4>Role</h4>
                      <div className="profile-grid">
                        <label>
                          Role Title *
                          <input value={criticalRoleForm.role_title} onChange={(event) => setCriticalRoleField("role_title", event.target.value)} required />
                        </label>
                        <label>
                          Role Start Date
                          <input type="date" value={criticalRoleForm.role_start_date} onChange={(event) => setCriticalRoleField("role_start_date", event.target.value)} />
                        </label>
                        <label>
                          Role End Date
                          <input type="date" value={criticalRoleForm.role_end_date} onChange={(event) => setCriticalRoleField("role_end_date", event.target.value)} disabled={criticalRoleForm.is_current_role} />
                        </label>
                        <label className="consent-line">
                          <input type="checkbox" checked={criticalRoleForm.is_current_role} onChange={(event) => setCriticalRoleField("is_current_role", event.target.checked)} />
                          <span>This is my current role</span>
                        </label>
                        <label className="profile-span-2">
                          Role Summary *
                          <textarea value={criticalRoleForm.role_summary} onChange={(event) => setCriticalRoleField("role_summary", event.target.value)} required placeholder="Summarize the role in attorney-friendly terms and explain why the responsibilities were crucial to the organization." />
                          <span className="field-help">This should read like the short explanation an attorney would use to describe why the position mattered.</span>
                        </label>
                        <label className="profile-span-2">
                          Core Responsibilities
                          <textarea value={criticalRoleForm.role_responsibilities} onChange={(event) => setCriticalRoleField("role_responsibilities", event.target.value)} placeholder="List the highest-value responsibilities: product strategy, launch ownership, technical leadership, stakeholder management, compliance ownership, revenue responsibility, etc." />
                        </label>
                        <label className="profile-span-2">
                          How The Role Evolved
                          <textarea value={criticalRoleForm.role_evolution} onChange={(event) => setCriticalRoleField("role_evolution", event.target.value)} placeholder="Explain how your scope grew, what higher-stakes work you inherited, and how the organization relied on you over time." />
                        </label>
                        <label>
                          Leadership Scope
                          <textarea value={criticalRoleForm.leadership_scope} onChange={(event) => setCriticalRoleField("leadership_scope", event.target.value)} placeholder="Teams led, regions covered, budget owned, products managed, or executives supported." />
                        </label>
                        <label>
                          Cross-functional Partners
                          <textarea value={criticalRoleForm.cross_functional_partners} onChange={(event) => setCriticalRoleField("cross_functional_partners", event.target.value)} placeholder="Engineering, design, sales, policy, legal, research, operations, regional teams, partner organizations." />
                        </label>
                      </div>
                    </div>

                    <div className="critical-role-section">
                      <h4>Project</h4>
                      <div className="profile-grid">
                        <label>
                          Project Name *
                          <input value={criticalRoleForm.project_name} onChange={(event) => setCriticalRoleField("project_name", event.target.value)} required />
                        </label>
                        <label>
                          Project Status
                          <select value={criticalRoleForm.project_status} onChange={(event) => setCriticalRoleField("project_status", event.target.value)}>
                            {PROJECT_STATUS_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}
                          </select>
                        </label>
                        <label>
                          Project Start Date
                          <input type="date" value={criticalRoleForm.project_start_date} onChange={(event) => setCriticalRoleField("project_start_date", event.target.value)} />
                        </label>
                        <label>
                          Project End Date
                          <input type="date" value={criticalRoleForm.project_end_date} onChange={(event) => setCriticalRoleField("project_end_date", event.target.value)} />
                        </label>
                        <label className="profile-span-2">
                          Project Summary
                          <textarea value={criticalRoleForm.project_summary} onChange={(event) => setCriticalRoleField("project_summary", event.target.value)} placeholder="What was the initiative, what did it do, and why was it important to the organization?" />
                        </label>
                        <label className="profile-span-2">
                          Business Need Or Problem To Solve
                          <textarea value={criticalRoleForm.business_need} onChange={(event) => setCriticalRoleField("business_need", event.target.value)} placeholder="Describe the urgent need, revenue problem, platform gap, market opportunity, compliance requirement, or operational bottleneck." />
                        </label>
                        <label className="profile-span-2">
                          Strategic Importance
                          <textarea value={criticalRoleForm.strategic_importance} onChange={(event) => setCriticalRoleField("strategic_importance", event.target.value)} placeholder="Explain why leadership cared: market expansion, user trust, retention, AI leadership, infrastructure modernization, payments growth, etc." />
                        </label>
                      </div>
                    </div>

                    <div className="critical-role-section">
                      <h4>Your contribution and value</h4>
                      <div className="profile-grid">
                        <label className="profile-span-2">
                          Your Specific Contributions *
                          <textarea value={criticalRoleForm.contributions_summary} onChange={(event) => setCriticalRoleField("contributions_summary", event.target.value)} required placeholder="Spell out what you personally ideated, built, led, approved, designed, negotiated, launched, or rescued." />
                          <span className="field-help">Use direct ownership language so the attorneys can distinguish your work from the team’s work.</span>
                        </label>
                        <label className="profile-span-2">
                          Originality / Innovation
                          <textarea value={criticalRoleForm.innovation_originality} onChange={(event) => setCriticalRoleField("innovation_originality", event.target.value)} placeholder="What was novel, first-of-its-kind, unusually hard, or strategically inventive about your approach?" />
                        </label>
                        <label className="profile-span-2">
                          Business Value Summary *
                          <textarea value={criticalRoleForm.business_value_summary} onChange={(event) => setCriticalRoleField("business_value_summary", event.target.value)} required placeholder="Summarize the measurable business value this work created for the organization or users." />
                        </label>
                        <label className="profile-span-2">
                          Quantitative Metrics
                          <textarea value={criticalRoleForm.quantitative_metrics} onChange={(event) => setCriticalRoleField("quantitative_metrics", event.target.value)} placeholder="Include user counts, revenue impact, adoption metrics, faster launch timelines, reduced incident rates, CSAT gains, downloads, retention, or global reach." />
                        </label>
                        <label>
                          Revenue / Monetization Impact
                          <textarea value={criticalRoleForm.revenue_impact} onChange={(event) => setCriticalRoleField("revenue_impact", event.target.value)} placeholder="Examples: annual revenue enabled, subscription uplift, new market spend, transaction value supported." />
                        </label>
                        <label>
                          Cost Savings / Efficiency
                          <textarea value={criticalRoleForm.cost_savings} onChange={(event) => setCriticalRoleField("cost_savings", event.target.value)} placeholder="Examples: reduced headcount need, time saved, faster release cycle, fewer manual steps." />
                        </label>
                        <label>
                          Speed / Operational Gain
                          <textarea value={criticalRoleForm.efficiency_gain} onChange={(event) => setCriticalRoleField("efficiency_gain", event.target.value)} placeholder="Examples: launch in days instead of months, 50% faster release, 30% maintenance reduction." />
                        </label>
                        <label>
                          User / Customer Impact
                          <textarea value={criticalRoleForm.user_or_customer_impact} onChange={(event) => setCriticalRoleField("user_or_customer_impact", event.target.value)} placeholder="Who benefited and at what scale? Mention users, developers, customers, patients, merchants, or enterprises." />
                        </label>
                        <label>
                          Market / Geographic Impact
                          <textarea value={criticalRoleForm.market_or_geographic_impact} onChange={(event) => setCriticalRoleField("market_or_geographic_impact", event.target.value)} placeholder="Mention countries, regions, enterprise accounts, new market entry, or strategic partnerships." />
                        </label>
                        <label>
                          Compliance / Risk Impact
                          <textarea value={criticalRoleForm.compliance_or_risk_impact} onChange={(event) => setCriticalRoleField("compliance_or_risk_impact", event.target.value)} placeholder="Describe trust, safety, privacy, policy, fraud reduction, or legal compliance impact if relevant." />
                        </label>
                      </div>
                    </div>

                    <div className="critical-role-section">
                      <h4>Why you stood out</h4>
                      <div className="profile-grid">
                        <label className="profile-span-2">
                          How You Were Distinguished From Peers
                          <textarea value={criticalRoleForm.peer_distinction_summary} onChange={(event) => setCriticalRoleField("peer_distinction_summary", event.target.value)} placeholder="Explain how your leadership, judgment, product sense, technical depth, innovation, or execution went beyond what peers typically delivered." />
                        </label>
                        <label>
                          Mentorship / Leadership Beyond Title
                          <textarea value={criticalRoleForm.mentorship_leadership} onChange={(event) => setCriticalRoleField("mentorship_leadership", event.target.value)} placeholder="Coaching, mentoring, shaping team culture, setting frameworks, guiding cross-functional teams." />
                        </label>
                        <label>
                          Executive Visibility / Trusted Advisor Role
                          <textarea value={criticalRoleForm.executive_visibility} onChange={(event) => setCriticalRoleField("executive_visibility", event.target.value)} placeholder="How closely leadership relied on you, which VPs or executives reviewed the work, and what decisions you influenced." />
                        </label>
                      </div>
                    </div>

                    <div className="critical-role-section">
                      <h4>Evidence and attorney draft</h4>
                      <div className="profile-grid">
                        <label className="profile-span-2">
                          Evidence You Can Potentially Provide
                          <textarea value={criticalRoleForm.evidence_available} onChange={(event) => setCriticalRoleField("evidence_available", event.target.value)} placeholder="List emails, launch docs, decks, org charts, screenshots, press coverage, metrics dashboards, performance reviews, patents, awards, or recommendation letter sources." />
                        </label>
                        <label className="profile-span-2">
                          Attorney-friendly Summary
                          <textarea value={criticalRoleForm.attorney_friendly_summary} onChange={(event) => setCriticalRoleField("attorney_friendly_summary", event.target.value)} placeholder="Write a tight paragraph the legal team could reuse in a petition draft to explain why your role on this project was leading or critical." />
                        </label>
                      </div>
                    </div>

                    <div className="form-actions">
                      <button className="primary compact-btn" type="submit" disabled={criticalRoleBusy}>{criticalRoleBusy ? "Saving..." : activeCriticalRoleId ? "Save Changes" : "Create Project"}</button>
                      <button className="ghost compact-btn" type="button" onClick={startNewCriticalRoleProject}>New Blank Project</button>
                      {activeCriticalRoleId ? <button className="danger compact-btn" type="button" onClick={deleteCriticalRoleProject} disabled={criticalRoleBusy}>Delete</button> : null}
                    </div>
                  </form>
                </div>
              </section>
            ) : (
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
            )}
          </section>
        ) : view.type === "workspace" && !view.criterionCode ? (
          <MemberGeneralWorkspacePanel
            criteria={dashboard.criteria || []}
            evidence={evidenceItems || []}
            criteriaByCode={criteriaByCode}
            onOpenCriterion={(code) => {
              if (code === "all") {
                setView({ type: "intake", criterionCode: "" });
                return;
              }
              setView(memberViewForCriterion(code));
            }}
            onBack={() => setView({ type: "home", criterionCode: "" })}
          />
        ) : (
          <section className="workspace-page">
            <div className="workspace-top">
              <div>
                <div className="section-kicker">Evidence Workspace</div>
                <h2>{selectedCriterion?.name || "Criterion workspace"}</h2>
                <p>Create folders, upload files, and drag items into the right location without leaving this page.</p>
              </div>
              <button className="ghost compact-btn" type="button" onClick={() => setView({ type: "home", criterionCode: "" })}>Back</button>
            </div>
            <div className="workspace-toolbar drive-toolbar">
              <input
                ref={workspaceFileInputRef}
                className="hidden-file-input"
                type="file"
                multiple
                onChange={handleWorkspaceFileSelection}
              />
              <input className="search-input" value={workspaceQuery} onChange={(event) => setWorkspaceQuery(event.target.value)} placeholder={`Search folders and files in ${selectedCriterion?.name || "this criterion"}`} />
              <div className="drive-toolbar-actions">
                <button className="primary compact-btn" type="button" disabled={workspaceUploadBusy} onClick={() => workspaceFileInputRef.current?.click()}>
                  {workspaceUploadBusy ? "Uploading..." : "Upload files"}
                </button>
                <button className="ghost compact-btn" type="button" onClick={() => setNewFolderName("")}>New folder</button>
              </div>
            </div>
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
                  <p className="mini-note">Current location: {workspaceFolderLabel(workspace, selectedFolderId)}</p>
                  <WorkspaceFolderTree workspace={workspace} selectedFolderId={selectedFolderId} onSelect={setSelectedFolderId} onDropItem={moveDraggedItem} />
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
                    <WorkspaceBreadcrumb workspace={workspace} selectedFolderId={selectedFolderId} onSelect={setSelectedFolderId} onDropItem={moveDraggedItem} />
                    <div className="drive-current-folder">
                      <div>
                        <strong>{workspaceQuery.trim() ? "Search results" : (selectedWorkspaceFolder?.name || "Root")}</strong>
                        <span>{driveRows.length} item{driveRows.length === 1 ? "" : "s"} shown. Drag files or folders onto a folder row, the breadcrumb, the folder tree, or the empty space below.</span>
                      </div>
                      <button className="ghost compact-btn" type="button" disabled={workspaceUploadBusy} onClick={() => workspaceFileInputRef.current?.click()}>Add files here</button>
                    </div>
                    <WorkspaceDriveDropZone
                      targetFolderId={selectedFolderId}
                      disabled={workspaceUploadBusy}
                      onMoveItem={moveDraggedItem}
                      onUploadFiles={uploadWorkspaceFiles}
                    >
                      <div className="drive-table">
                        <div className="drive-table-head">
                          <span>Name</span>
                          <span>Type</span>
                          <span>Updated</span>
                          <span>Move</span>
                          <span>Action</span>
                        </div>
                        {driveRows.map((item) => (
                          <WorkspaceItemRow
                            key={item.id}
                            item={item}
                            folderOptions={folderOptions}
                            onDragStart={handleDragStart}
                            onOpenFolder={setSelectedFolderId}
                            onDeleteFile={deleteFile}
                            onDeleteFolder={(folderItem) => deleteFolderById(folderItem.entityId, folderItem.path || folderItem.label)}
                            onMoveItem={moveDraggedItem}
                          />
                        ))}
                      </div>
                      {!driveRows.length ? (
                        <div className="drive-empty-state">
                          <strong>This folder is empty.</strong>
                          <span>Drop files or folders here, or use Upload files to add evidence to {workspaceFolderLabel(workspace, selectedFolderId)}.</span>
                        </div>
                      ) : null}
                    </WorkspaceDriveDropZone>
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

"use strict";

const S = {
  data: null,
  tab: "overview",
  f: { q: "", region: "", level: "", type: "", fee: "", view: "open", sort: "start" },
  open: new Set(),
  draftId: null,
  draft: null,
};

const REGION = { europe: "Europe", north_america: "North America", australia: "Australia", scandinavia: "Nordics" };
const TYPE = {
  scholarship: "Scholarship",
  admission_funding: "Funded with admission",
  phd_position: "Salaried PhD",
  nomination_fellowship: "Nomination only",
};
const LEVEL = { masters: "Master's", phd: "PhD", undergraduate: "Undergrad", postdoc: "Postdoc" };
/* Tag grammar: outlined = a state, black filled = decided, red filled = urgent. */
const BUCKET = {
  eligible: ["Eligible", "ok"],
  needs_confirmation: ["Check details", "warn"],
  upcoming: ["Opens soon", "info"],
  near_miss: ["Near miss", "info"],
  ineligible: ["Not eligible", "bad"],
  expired: ["Closed", "dark"],
  unverified: ["Unverified lead", "warn"],
  rejected: ["Rejected", "bad"],
};
const STATUS = {
  shortlisted: ["Shortlisted", "dark"],
  preparing: ["Preparing", "accent"],
  ready: ["Ready to apply", "accent"],
  applying: ["Agent applying", "accent"],
  needs_you: ["Needs you", "bad"],
  awaiting_submit_ok: ["Awaiting your OK", "bad"],
  submitted: ["Submitted", "dark"],
  manual: ["Apply yourself", "bad"],
  dismissed: ["Dismissed", ""],
};
const URGENCY = { overdue: ["Start now", "bad"], this_week: ["This week", "warn"], soon: ["Within 30d", "accent"] };
const FEE = { fee: ["Application fee", "warn"], no_fee: ["No fee", "ok"], unknown: ["Fee unknown", ""] };
const DRAFT_STATE = { approved: ["Approved", "dark"], changes_requested: ["Changes asked", "warn"], draft: ["Draft", "accent"],
  not_drafted: ["Not drafted", ""] };
const MODE = {
  agent: "The agent can apply in the portal.",
  manual: "Apply by email or PDF form: the agent prepares everything, you send it.",
  nomination: "Nomination only: ask your university's graduate office how to be nominated.",
  unknown: "Application route unclear: open the official page.",
  none: "",
};
const OUTCOMES = ["pending", "interview", "shortlisted", "offer_won", "waitlisted", "rejected", "withdrawn"];
const OUTCOME_LABEL = { pending: "Waiting", interview: "Interview", shortlisted: "Shortlisted", offer_won: "Won / offer",
  waitlisted: "Waitlisted", rejected: "Not successful", withdrawn: "Withdrawn" };

/* ------------------------------------------------------------------ helpers */

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false || kid === "") continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

/* One small stroke icon set, drawn as SVG (no glyphs standing in for icons). */
const ICONS = {
  external: ["M14 5h5v5", "M19 5l-8 8", "M17 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h5"],
  chevron: ["M9 6l6 6-6 6"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  x: ["M6 6l12 12", "M18 6L6 18"],
  question: ["M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7", "M12 17h.01"],
  star: ["M12 3.8l2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z"],
};
function icon(name, filled) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "i" + (filled ? " fill" : ""));
  svg.setAttribute("aria-hidden", "true");
  for (const d of ICONS[name] || []) {
    const p = document.createElementNS(ns, "path");
    p.setAttribute("d", d);
    svg.append(p);
  }
  return svg;
}

function safeUrl(u) {
  try {
    const x = new URL(u);
    return x.protocol === "https:" || x.protocol === "http:" ? x.href : null;
  } catch {
    return null;
  }
}
function ext(url, label, cls) {
  const u = safeUrl(url);
  return u ? h("a", { href: u, target: "_blank", rel: "noopener noreferrer", class: cls },
    String(label).replace(/\s*↗$/, ""), " ", icon("external")) : null;
}
function pill(pair) {
  return pair && pair[0] ? h("span", { class: "pill " + (pair[1] || "") }, pair[0]) : null;
}
function chip(text, cls) {
  return h("span", { class: "chip " + (cls || "") }, text);
}
function trunc(text, n) {
  text = String(text || "");
  return text.length > n ? text.slice(0, n - 1) + "…" : text;
}
/* Shorten at a word boundary so figures like "€75,000" are never cut in half. */
function truncWords(text, n) {
  text = String(text || "");
  if (text.length <= n) return text;
  const cut = text.slice(0, n);
  const space = cut.lastIndexOf(" ");
  return (space > n * 0.5 ? cut.slice(0, space) : cut).replace(/[\s,;:(]+$/, "") + "…";
}
/* A short name for an opportunity: its title up to the first bracket or dash. */
function shortName(r) {
  const t = String(r.record.title || "").split(/\s+[(\-–—:]\s*|\s*\(/)[0];
  return truncWords(t, 26);
}
function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
function daysText(n) {
  if (n === null || n === undefined) return "";
  if (n < 0) return `${-n} days ago`;
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  return `in ${n} days`;
}
function ago(iso) {
  if (!iso) return "never";
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 60) return `${Math.max(mins, 0)} min ago`;
  if (mins < 48 * 60) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} days ago`;
}
function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove("show"), 2600);
}
function select(value, options, onchange, label) {
  const s = h("select", { "aria-label": label, onchange: (e) => onchange(e.target.value) });
  for (const [v, t] of options) {
    const o = h("option", { value: v }, t);
    if (v === value) o.selected = true;
    s.append(o);
  }
  return s;
}
function copy(text) {
  const done = () => toast("Copied — paste it into Claude: " + text);
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
  } else fallbackCopy(text, done);
}
function fallbackCopy(text, done) {
  const ta = h("textarea");
  ta.value = text;
  document.body.append(ta);
  ta.select();
  document.execCommand("copy");
  ta.remove();
  done();
}

async function post(path, body, quiet) {
  let data;
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Scholar": "1" },
      body: JSON.stringify(body),
    });
    data = await res.json();
  } catch {
    data = { ok: false, error: "Could not reach the dashboard server." };
  }
  if (!data.ok && !quiet) toast(data.error || (data.errors || []).join("; ") || "That did not work.");
  return data;
}
async function load() {
  try {
    const res = await fetch("/api/state", { cache: "no-store" });
    S.data = await res.json();
  } catch {
    document.getElementById("view").replaceChildren(
      h("div", { class: "empty" }, "Can't reach the dashboard server. Start it again: python -m scholar serve --open (or the Scholarship Desk shortcut on Windows)."));
    return;
  }
  render();
}
async function act(id, action, payload, quiet) {
  const r = await post("/api/action", { id, action, payload });
  if (r.ok) {
    if (!quiet) toast("Saved");
    await load();
  }
  return r;
}

const rows = () => (S.data ? S.data.rows : []);
const isOpen = (r) => ["eligible", "needs_confirmation", "upcoming"].includes(r.evaluation.bucket);
const pursuing = (r) => !["found", "dismissed"].includes(r.tracker.status);

function needsYourself(r) {
  const st = r.tracker.status;
  const ev = r.evaluation;
  if (["submitted", "dismissed"].includes(st)) return false;
  if (["manual", "needs_you", "awaiting_submit_ok"].includes(st)) return true;
  return ["eligible", "needs_confirmation"].includes(ev.bucket) && ev.in_scope &&
    ["manual", "nomination", "unknown"].includes(ev.apply_mode);
}

function commandFor(r) {
  const ev = r.evaluation;
  const d = r.drafts;
  if (!["eligible", "needs_confirmation"].includes(ev.bucket) && !r.tracker.override) return null;
  if (ev.apply_mode === "agent" && (!d.has_brief || d.all_approved) && r.doccheck && r.doccheck.ok) return `/apply ${r.id}`;
  return `/tailor ${r.id}`;
}

function statusPill(r) {
  const st = r.tracker.status;
  if (st && st !== "found") return pill(STATUS[st]);
  return pill(BUCKET[r.evaluation.bucket]);
}

function feeOf(r) {
  return r.evaluation.fee || { status: "unknown" };
}
function feeChip(r) {
  const f = feeOf(r);
  const [text, cls] = FEE[f.status] || FEE.unknown;
  const label = f.status === "fee" && f.amount ? `${text} · ${f.amount}` : text;
  const title = f.note || (f.status === "unknown" ? "The official page doesn't say whether applying costs anything." : "");
  return h("span", { class: "chip " + cls, title: title || null }, label);
}

function countryCell(c) {
  const title = [c.reasons && c.reasons.join(" "), c.quote ? `“${c.quote}”` : ""].filter(Boolean).join("\n");
  if (c.status === "eligible") return h("span", { class: "chip ok", title: title || "Your country is eligible" }, icon("check"), "OK");
  if (c.status === "ineligible") return h("span", { class: "chip bad", title }, icon("x"), "No");
  return h("span", { class: "chip warn", title: title || "Unclear" }, icon("question"), "Check");
}

/* ------------------------------------------------------------------ chrome */

function renderHeader() {
  const p = S.data.profile;
  const parts = [];
  if (p.name) parts.push(p.name);
  if (p.levels && p.levels.length) parts.push(p.levels.map((l) => LEVEL[l] || l).join(" & "));
  if (p.start_term) parts.push("Start " + p.start_term);
  parts.push(`Profile ${p.completeness_percent}%`);
  document.getElementById("profile-line").textContent = parts.join(" · ");
  const w = S.data.watch;
  const line = w.last_run
    ? `Checked ${ago(w.last_run.at)} · ${w.pages} pages watched${w.pending_changes ? ` · ${w.pending_changes} change(s) for Claude` : ""}`
    : `Daily check hasn't run yet · ${w.pages} pages watched`;
  document.getElementById("watch-line").textContent = line;
  const search = document.getElementById("search");
  if (search && document.activeElement !== search) search.value = S.f.q;
}

function go(tab) {
  S.tab = tab;
  if (tab === "profile") S.profile = null;
  render();
  window.scrollTo(0, 0);
}

/* Open one opportunity's details in the Opportunities tab and bring it into view. */
function openOpp(r) {
  S.tab = "opps";
  S.open.add(r.id);
  if (!r.tracker.seen) {
    r.tracker.seen = true;
    post("/api/action", { id: r.id, action: "seen" });
  }
  if (!filtered().some((x) => x.id === r.id)) Object.assign(S.f, { q: "", region: "", level: "", type: "", fee: "", view: "all" });
  render();
  const el = document.getElementById("row-" + r.id);
  if (el) {
    el.scrollIntoView({ block: "center" });
    el.classList.add("flash");
  }
}

function renderCounts() {
  const all = rows();
  const counts = {
    opps: all.filter((r) => isOpen(r) && r.evaluation.in_scope && !["dismissed", "submitted"].includes(r.tracker.status)).length,
    yourself: all.filter(needsYourself).length,
    week: S.data.week.tasks.length + S.data.week.undecided.length,
    near: all.filter((r) => r.evaluation.bucket === "near_miss" && r.evaluation.in_scope).length,
    drafts: all.filter((r) => r.drafts.has_brief && !r.drafts.all_approved).length,
    submitted: all.filter((r) => r.tracker.status === "submitted").length,
    supervisors: S.data.outreach.length,
    links: S.data.inbox.filter((l) => l.status === "queued").length,
    docs: (S.data.documents || []).length,
    profile: S.data.profile.completeness_percent != null ? S.data.profile.completeness_percent + "%" : "",
  };
  for (const el of document.querySelectorAll("[data-count]")) {
    const n = counts[el.dataset.count];
    el.textContent = n ? String(n) : "";
  }
}

function banners() {
  const out = [];
  const ps = S.data.profile_status;
  if (!ps.search_ready) {
    out.push(h("div", { class: "banner" }, "Your profile isn't ready for searching yet (missing: ",
      ps.missing_for_search.join(", "), "). In Claude, run ", h("code", null, "/profile"), "."));
  }
  if (S.data.library.documents_needing_ingest) {
    out.push(h("div", { class: "banner" }, `${S.data.library.documents_needing_ingest} document(s) are new or changed. In Claude, run `,
      h("code", null, "/ingest"), " so the writer uses the latest versions."));
  }
  if (S.data.watch.needs_browser.length) {
    out.push(h("div", { class: "banner" }, "Some watched pages block automatic checks and are reviewed by Claude's browser weekly: ",
      S.data.watch.needs_browser.join(", "), "."));
  }
  return out;
}

function render() {
  if (!S.data) return;
  renderHeader();
  renderCounts();
  for (const b of document.querySelectorAll("#tabs button")) b.classList.toggle("active", b.dataset.tab === S.tab);
  const main = document.getElementById("view");
  main.replaceChildren();
  VIEWS[S.tab](main);
  // Each tab has its own address (#overview, #profile, …) so refresh and bookmarks keep the tab.
  if (location.hash.slice(1) !== S.tab) history.replaceState(null, "", "#" + S.tab);
}

/* ------------------------------------------------------------ opportunities */

function filtered() {
  const f = S.f;
  const q = f.q.trim().toLowerCase();
  const list = rows().filter((r) => {
    const ev = r.evaluation;
    const st = r.tracker.status;
    const rec = r.record;
    const open = isOpen(r) && ev.in_scope && !["dismissed", "submitted"].includes(st);
    if (f.view === "open" && !open) return false;
    if (f.view === "pursuing" && !pursuing(r)) return false;
    if (f.view === "all" && !ev.in_scope) return false;
    if (f.view === "hidden" && open) return false;
    if (f.region && rec.region !== f.region) return false;
    if (f.level && !rec.levels.includes(f.level)) return false;
    if (f.type && rec.type !== f.type) return false;
    if (f.fee && feeOf(r).status !== f.fee) return false;
    if (q) {
      const hay = [rec.title, rec.sponsor, ...(rec.host_countries || []), ...(rec.fields || [])].join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const keys = {
    start: (r) => r.timeline.start_by || "9999",
    deadline: (r) => r.timeline.deadline || "9999",
    new: (r) => r.record.first_seen || "",
  };
  list.sort((a, b) => (f.sort === "new" ? keys.new(b).localeCompare(keys.new(a)) : keys[f.sort](a).localeCompare(keys[f.sort](b))));
  return list;
}

function viewOpps(main) {
  const f = S.f;
  const toolbar = h("div", { class: "toolbar" },
    select(f.view, [["open", "Can apply"], ["pursuing", "Shortlisted & in progress"], ["all", "Everything in scope"],
      ["hidden", "Hidden: not eligible, closed, leads"]], (v) => { f.view = v; drawTable(); }, "View"),
    select(f.region, [["", "All regions"], ...Object.entries(REGION)], (v) => { f.region = v; drawTable(); }, "Region"),
    select(f.level, [["", "All levels"], ["masters", "Master's"], ["phd", "PhD"]], (v) => { f.level = v; drawTable(); }, "Level"),
    select(f.type, [["", "All types"], ...Object.entries(TYPE)], (v) => { f.type = v; drawTable(); }, "Type"),
    select(f.fee, [["", "Any fee status"], ["no_fee", "No fee"], ["fee", "Application fee"], ["unknown", "Fee unknown"]],
      (v) => { f.fee = v; drawTable(); }, "Application fee"),
    select(f.sort, [["start", "Sort: start by"], ["deadline", "Sort: deadline"], ["new", "Sort: newest"]],
      (v) => { f.sort = v; drawTable(); }, "Sort"),
    h("button", { class: "ghost", type: "button", onclick: async () => { await post("/api/seen_all", {}); load(); } }, "Mark all seen"));
  const searching = f.q ? h("p", { class: "muted" }, `Showing matches for “${f.q}”. `,
    h("button", { type: "button", class: "link", onclick: () => { f.q = ""; render(); } }, "Clear search")) : null;
  main.append(...[...banners(), searching, toolbar, h("div", { id: "table" })].filter(Boolean));
  drawTable();
}

/* ---------------------------------------------------------------- overview */

function mod(title, opts, ...body) {
  const o = opts || {};
  return h("section", { class: "mod " + (o.cls || ""), "aria-label": title },
    h("div", { class: "mod-h" }, h("h2", null, title),
      o.note != null && o.note !== "" ? h("span", { class: "mod-note" }, String(o.note)) : null,
      o.tab ? h("button", { type: "button", class: "more", onclick: () => go(o.tab) }, o.more || "View all", icon("chevron")) : null),
    h("div", { class: "mod-b" }, ...body));
}
const emptyLine = (text) => h("p", { class: "empty-line" }, text);
const live = (r) => isOpen(r) && r.evaluation.in_scope && !["dismissed", "submitted"].includes(r.tracker.status);

function deadlineRow(r) {
  const left = r.evaluation.deadline.days_left;
  const where = [r.record.sponsor, (r.record.host_countries || []).join(", ")].filter(Boolean).join(" · ");
  return h("button", { type: "button", class: "dl", onclick: () => openOpp(r), title: "Open details" },
    h("span", { class: "dl-days" + (left <= 30 ? " hot" : "") }, String(left), h("small", null, left === 1 ? "day" : "days")),
    h("span", { class: "dl-main" }, h("span", { class: "dl-title" }, r.record.title), h("span", { class: "dl-sub" }, where)),
    h("span", { class: "dl-end" },
      h("span", { class: "dl-date" }, fmtDate(r.evaluation.deadline.date)),
      h("span", { class: "dl-tags" }, statusPill(r), feeChip(r))));
}

const daysTag = (r) => {
  const d = r && r.evaluation.deadline.days_left;
  return d == null ? "" : d < 0 ? "closed" : `${d}d`;
};

/* Concrete actions, most urgent first: each names the application and what to do. */
function needsList() {
  const all = rows();
  const byId = new Map(all.map((r) => [r.id, r]));
  const out = [];
  for (const r of all.filter(needsYourself)) {
    const label = r.tracker.status === "awaiting_submit_ok" ? "Say yes to submit" : r.tracker.status === "needs_you" ? "Do your step" : "Apply yourself";
    out.push({ text: `${label} · ${shortName(r)}`, count: daysTag(r), act: () => go("yourself") });
  }
  for (const t of S.data.week.tasks.filter((x) => !x.done && x.days_left < 0)) {
    const r = byId.get(t.id);
    out.push({ text: `${t.label.replace(/\s*and send them a brief$/, "")} · ${r ? shortName(r) : trunc(t.title, 30)}`,
      count: `${-t.days_left}d late`, hot: true, act: () => (r ? openOpp(r) : go("week")) });
  }
  for (const [t, list] of missingDocTypes()) {
    const what = { transcript: "transcript", degree_certificate: "degree certificate", language_certificate: "English test result",
      cv: "CV", research_proposal: "research proposal" }[t] || (DOC_LABEL[t] || t);
    const first = list.slice().sort((a, b) => (a.evaluation.deadline.days_left ?? 9999) - (b.evaluation.deadline.days_left ?? 9999))[0];
    out.push({ text: `Upload ${what} · ${shortName(first)}${list.length > 1 ? ` +${list.length - 1}` : ""}`,
      count: daysTag(first), act: () => go("docs") });
  }
  for (const r of all.filter((x) => x.drafts.has_brief && x.drafts.approved < x.drafts.total)) {
    out.push({ text: `Approve drafts · ${shortName(r)}`, count: `${r.drafts.total - r.drafts.approved} left`,
      act: () => { go("drafts"); openDraft(r.id); } });
  }
  for (const u of S.data.week.undecided.slice(0, 3)) {
    const r = byId.get(u.id);
    out.push({ text: `Shortlist or skip · ${r ? shortName(r) : trunc(u.title, 30)}`, count: r ? daysTag(r) : "", act: () => (r ? openOpp(r) : go("week")) });
  }
  const missing = S.data.profile_status.missing_for_apply.length;
  if (missing) out.push({ text: "Complete your profile", count: `${missing} field${missing > 1 ? "s" : ""}`, act: () => go("profile") });
  const fresh = S.data.library.documents_needing_ingest;
  if (fresh) out.push({ text: "Run /ingest in Claude for new documents", count: String(fresh), act: () => go("docs") });
  return out;
}

function kpis(items) {
  return h("div", { class: "kpis" }, items.map(([label, n, tab, hot]) =>
    h("button", { type: "button", class: "kpi" + (hot && n ? " hot" : ""),
      onclick: () => { if (tab === "hidden") { S.f.view = "hidden"; go("opps"); } else go(tab); } },
      h("b", null, String(n)), h("span", null, label))));
}

function viewOverview(main) {
  const all = rows();
  const open = all.filter(live);
  const next = open.filter((r) => r.evaluation.deadline.date && r.evaluation.deadline.days_left >= 0)
    .sort((a, b) => a.evaluation.deadline.date.localeCompare(b.evaluation.deadline.date)).slice(0, 7);
  const st = (r) => r.tracker.status;
  const needs = needsList();
  const docs = S.data.documents || [];
  const missing = missingDocTypes();
  const drafts = all.filter((r) => r.drafts.has_brief);
  // Next preparation steps across everything being pursued, overdue first.
  const upcoming = all.filter((r) => pursuing(r) && !["submitted", "dismissed"].includes(st(r)))
    .flatMap((r) => (r.timeline.tasks || []).filter((t) => !t.done).map((t) => ({ ...t, r })))
    .sort((a, b) => String(a.due || "9999").localeCompare(String(b.due || "9999"))).slice(0, 7);
  const fresh = open.filter((r) => !r.tracker.seen);
  const recent = all.slice().sort((a, b) => String(b.record.first_seen || "").localeCompare(String(a.record.first_seen || "")));
  const DOCSTATE = { read: ["Read", "ok"], new: ["New", "warn"], changed: ["Changed", "warn"], missing_on_disk: ["Missing", "bad"] };

  main.append(...banners());
  if (!all.length) {
    main.append(h("div", { class: "empty" }, "No opportunities yet. In Claude, run ", h("code", null, "/discover"),
      " to search your regions, or add a link in the Add link tab."));
  }
  const grid = h("div", { class: "mosaic" });
  grid.append(
    mod("Next deadlines", { cls: "span-6", note: next.length ? `${next.length} coming up` : "", tab: "opps" },
      next.length ? next.map(deadlineRow) : emptyLine("No upcoming deadlines among the options you can apply to.")),
    mod("Needs you", { cls: "span-3", note: needs.length || "" },
      needs.length ? h("ol", { class: "needs" }, needs.slice(0, 9).map((n, i) => h("li", null,
        h("span", { class: "rank" }, String(i + 1)),
        h("button", { type: "button", class: "link", onclick: n.act }, n.text),
        h("b", { class: n.hot ? "late" : null }, String(n.count)))))
        : emptyLine("Nothing needs you right now.")),
    mod("Pipeline", { cls: "span-3", tab: "submitted", more: "Results" },
      kpis([["Found", all.length, "opps"], ["Shortlisted", all.filter((r) => st(r) === "shortlisted").length, "opps"],
        ["Preparing", all.filter((r) => ["preparing", "ready", "applying", "needs_you", "awaiting_submit_ok"].includes(st(r))).length, "drafts"],
        ["Submitted", all.filter((r) => st(r) === "submitted").length, "submitted"]]),
      h("div", { class: "mod-sub" }, "Fit"),
      kpis([["Can apply", open.length, "opps"], ["Near miss", all.filter((r) => r.evaluation.bucket === "near_miss").length, "near"],
        ["Not eligible", all.filter((r) => r.evaluation.bucket === "ineligible").length, "hidden", true],
        ["Fee to apply", open.filter((r) => feeOf(r).status === "fee").length, "opps"]]),
      h("div", { class: "mod-sub" }, fresh.length ? "New since your last look" : "Recently found"),
      h("ul", { class: "lines" }, (fresh.length ? fresh : recent).slice(0, 4).map((r) => h("li", null,
        fresh.length ? chip("NEW", "new") : null,
        h("button", { type: "button", class: "link", onclick: () => openOpp(r) }, shortName(r)),
        h("span", { class: "due" }, daysTag(r)))))),
    mod("Documents", { cls: "span-4", note: missing.size ? `${missing.size} needed` : "", tab: "docs", more: "Upload" },
      h("ul", { class: "lines" },
        [...missing.keys()].map((t) => h("li", null, h("span", null, DOC_LABEL[t] || t), pill(["Needed", "bad"]))),
        docs.slice(0, 10).map((d) => h("li", null, h("span", null, d.label || d.name), pill(DOCSTATE[d.status] || [d.status, ""])))),
      !docs.length && !missing.size ? emptyLine("No documents yet.") : null),
    h("div", { class: "stack span-8" },
      mod("Drafts", { note: drafts.length ? `${drafts.reduce((n, r) => n + r.drafts.approved, 0)} / ${drafts.reduce((n, r) => n + r.drafts.total, 0)} approved` : "", tab: "drafts" },
        drafts.length === 1 ? h("div", { class: "mod-sub" }, drafts[0].record.title) : null,
        drafts.length ? h("ul", { class: "lines" }, drafts.flatMap((r) => (r.draft_items || []).map((q) => h("li", null,
          h("button", { type: "button", class: "link", onclick: () => { go("drafts"); openDraft(r.id); } },
            `${drafts.length > 1 ? shortName(r) + " · " : ""}${q.prompt.replace(/\s*[(:].*$/, "")}`),
          h("span", { class: "due" }, q.words ? `${q.words}${q.limit ? " / " + q.limit : ""} words` : "—"),
          pill(DRAFT_STATE[q.status] || [q.status, ""])))))
          : emptyLine("No drafts yet. In Claude, run /tailor for an opportunity.")),
      mod("Coming up", { note: upcoming.length || "", tab: "week", more: "This week" },
        upcoming.length ? h("ul", { class: "lines" }, upcoming.map((t) => h("li", null,
          h("button", { type: "button", class: "link", onclick: () => openOpp(t.r) }, `${t.label} · ${shortName(t.r)}`),
          h("span", { class: "due" + (t.days_left < 0 ? " late" : "") }, t.days_left < 0 ? `${-t.days_left}d late` : fmtDate(t.due)))))
          : emptyLine("No preparation tasks for applications you're pursuing."))),
    mod("All opportunities", { cls: "span-12", note: all.length || "", tab: "opps", more: "Filter and sort" }, overviewTable(all)));
  main.append(grid);
}

function overviewTable(list) {
  if (!list.length) return emptyLine("Nothing found yet.");
  const tbody = h("tbody");
  for (const r of list) {
    const ev = r.evaluation;
    tbody.append(h("tr", { class: "row", onclick: () => openOpp(r) },
      h("td", null, h("div", { class: "title" }, r.record.title), h("div", { class: "sub" }, r.record.sponsor)),
      h("td", null, (r.record.host_countries || []).join(", ")),
      h("td", null, truncWords((r.record.amount && r.record.amount.text) || "—", 72)),
      h("td", null, countryCell(ev.country)),
      h("td", { class: "nowrap" }, h("span", { class: "date-cell" }, fmtDate(ev.deadline.date)), h("div", { class: "sub" }, daysText(ev.deadline.days_left))),
      h("td", null, feeChip(r)),
      h("td", null, statusPill(r))));
  }
  return h("table", { class: "grid" }, h("thead", null, h("tr", null,
    ["Opportunity", "Where", "Funding", "Country", "Deadline", "Fee", "Status"].map((t) => h("th", { scope: "col" }, t)))), tbody);
}

function drawTable() {
  const box = document.getElementById("table");
  if (!box) return;
  box.replaceChildren();
  const list = filtered();
  if (!list.length) {
    box.append(rows().length
      ? h("div", { class: "empty" }, "Nothing matches these filters.")
      : h("div", { class: "empty" }, "No opportunities yet. In Claude, run ", h("code", null, "/discover"),
        " to search your regions, or paste a link into ", h("code", null, "/apply"), "."));
    return;
  }
  const tbody = h("tbody");
  for (const r of list) {
    tbody.append(rowEl(r));
    if (S.open.has(r.id)) tbody.append(detailEl(r));
  }
  const heads = ["", "Opportunity", "Where", "Funding", "Country", "Deadline", "Start by", "Status", "Links"];
  box.append(h("table", { class: "grid" }, h("thead", null, h("tr", null, heads.map((t) => h("th", { scope: "col" }, t)))), tbody));
}

function toggle(r) {
  if (S.open.has(r.id)) S.open.delete(r.id);
  else S.open.add(r.id);
  if (!r.tracker.seen) {
    r.tracker.seen = true;
    post("/api/action", { id: r.id, action: "seen" });
  }
  drawTable();
}

function deadlineSub(r) {
  const ev = r.evaluation;
  const bits = [];
  if (ev.deadline.date) bits.push(daysText(ev.deadline.days_left));
  else if (ev.deadline.type === "rolling") bits.push("rolling");
  else if (ev.deadline.type === "not_open") bits.push(ev.deadline.opens ? "opens " + fmtDate(ev.deadline.opens) : "not open yet");
  else bits.push("no date yet");
  if (ev.admission.required && ev.admission.deadline) bits.push("admission " + fmtDate(ev.admission.deadline));
  if (ev.internal_deadline.date) bits.push("internal " + fmtDate(ev.internal_deadline.date));
  return bits.join(" · ");
}

function rowEl(r) {
  const rec = r.record;
  const ev = r.evaluation;
  const tl = r.timeline;
  const st = r.tracker.status;
  const starred = st !== "found" && st !== "dismissed";
  const canStar = ["found", "shortlisted", "dismissed"].includes(st);
  const tr = h("tr", { class: "row", id: "row-" + r.id, onclick: (e) => { if (!e.target.closest("a,button,input,select,textarea")) toggle(r); } });
  tr.append(
    h("td", null, h("button", {
      class: "star" + (starred ? " on" : ""), type: "button", disabled: !canStar,
      title: starred ? "On your shortlist" : "Add to shortlist", "aria-label": starred ? "Remove from shortlist" : "Add to shortlist",
      onclick: () => act(r.id, st === "shortlisted" ? "unshortlist" : "shortlist"),
    }, icon("star", starred))),
    h("td", null,
      h("div", { class: "title" }, rec.title),
      h("div", { class: "sub" }, rec.sponsor),
      !r.tracker.seen ? chip("NEW", "new") : null,
      chip(TYPE[rec.type] || rec.type),
      rec.levels.map((l) => chip(LEVEL[l] || l)),
      feeChip(r)),
    h("td", null, (rec.host_countries || []).join(", "), h("div", { class: "sub" }, REGION[rec.region] || rec.region)),
    h("td", null, h("div", null, truncWords((rec.amount && rec.amount.text) || "—", 90)),
      rec.amount && rec.amount.full_funding ? chip("Full funding", "ok") : null),
    h("td", null, countryCell(ev.country)),
    h("td", { class: "nowrap" }, fmtDate(ev.deadline.date), h("div", { class: "sub" }, deadlineSub(r))),
    h("td", { class: "nowrap" }, tl.start_by ? fmtDate(tl.start_by) : "—", h("div", null, pill(URGENCY[tl.urgency]))),
    h("td", null, statusPill(r)),
    h("td", { class: "nowrap" }, ext(rec.official_url, "Official ↗"), h("br"), ext(rec.apply_url || ev.admission.url, "Apply ↗")));
  return tr;
}

function list(items, cls) {
  return items && items.length ? h("ul", { class: cls }, items.map((t) => h("li", null, t))) : null;
}

function detailEl(r) {
  const rec = r.record;
  const ev = r.evaluation;
  const tr = r.tracker;
  const app = rec.application || {};
  const why = h("div", null, h("h3", null, "Why it's here"),
    h("p", null, pill(BUCKET[ev.bucket]), " ", MODE[ev.apply_mode] || ""),
    list(ev.reasons), list(ev.gaps.map((g) => "Gap: " + g)), list(ev.open_items), list(ev.scope_notes.map((s) => "Outside your preferences: " + s)));
  const c = ev.country;
  const country = h("div", null, h("h3", null, "Country eligibility"),
    h("p", null, countryCell(c), " ", c.status === "eligible" ? "Your citizenship/residence qualifies." : ""),
    list(c.reasons), c.quote ? h("p", { class: "quote" }, `“${c.quote}”`) : null,
    c.list_url ? h("p", null, ext(c.list_url, "Sponsor's country list ↗")) : null);
  const reqs = h("div", null, h("h3", null, "Requirements"),
    ev.requirements.length ? h("ul", null, ev.requirements.map((q) => h("li", { class: "req-" + q.result },
      icon(q.result === "pass" ? "check" : q.result === "fail" ? "x" : "question"), q.text, q.hard ? "" : " (preference)",
      q.fixable && q.result !== "pass" ? " — fixable" : ""))) : h("p", { class: "muted" }, "No extra requirements recorded."));
  const dates = h("div", null, h("h3", null, "Dates"), h("ul", null,
    h("li", null, "Deadline: ", fmtDate(ev.deadline.date), ev.deadline.timezone ? ` (${ev.deadline.timezone})` : "", " ", daysText(ev.deadline.days_left)),
    ev.deadline.opens ? h("li", null, "Opens: ", fmtDate(ev.deadline.opens)) : null,
    ev.admission.required ? h("li", null, "Admission application: ", fmtDate(ev.admission.deadline), " ",
      ext(ev.admission.url, "admission portal ↗"), ev.admission.fee_note ? ` — ${ev.admission.fee_note}` : "") : null,
    ev.internal_deadline.date ? h("li", null, "University internal deadline: ", fmtDate(ev.internal_deadline.date),
      ev.internal_deadline.note ? ` — ${ev.internal_deadline.note}` : "") : null,
    h("li", { class: "muted" }, `Official page last checked ${ev.verified_days_ago ?? "?"} days ago`)));
  const funding = h("div", null, h("h3", null, "Funding"), h("p", null, (rec.amount && rec.amount.text) || "—"),
    rec.obligations && rec.obligations.length ? h("div", null, h("b", null, "Obligations"), list(rec.obligations)) : null);
  const plan = h("div", null, h("h3", null, "Plan"),
    r.timeline.tasks.length ? r.timeline.tasks.map((t) => taskEl(r.id, t)) : h("p", { class: "muted" }, "No tasks."));
  const appBox = h("div", null, h("h3", null, "Application"), h("ul", null,
    h("li", null, "Method: ", app.method || "unknown", app.platform ? ` (${app.platform})` : ""),
    (() => {
      const f = feeOf(r);
      const text = f.note || (f.status === "unknown" ? "Not stated on the official page." : f.status === "no_fee" ? "Free to apply." : "");
      return h("li", null, feeChip(r), text ? " " + text : "");
    })(),
    app.documents && app.documents.length ? h("li", null, "Documents: ", app.documents.join(", ")) : null,
    app.references ? h("li", null, `Referees: ${app.references}`) : null,
    app.questions && app.questions.length ? h("li", null, `Questions: ${app.questions.length}`) : null,
    r.drafts.has_brief ? h("li", null, `Answers approved: ${r.drafts.approved}/${r.drafts.total}`) : null,
    r.drafts.cv_choice ? h("li", null, "CV: ", r.drafts.cv_choice.path) : null,
    r.doccheck ? h("li", { class: r.doccheck.ok ? "req-pass" : "req-fail" },
      r.doccheck.ok ? "Document check passed" : "Document check: " + r.doccheck.errors.join("; ")) : null,
    tr.stop_reason ? h("li", { class: "req-fail" }, "Agent stopped: ", tr.stop_reason) : null,
    tr.waiting_for ? h("li", { class: "req-unknown" }, "Waiting for you: ", tr.waiting_for) : null),
    tr.history && tr.history.length ? h("details", null, h("summary", { class: "muted small" }, "Activity"),
      list(tr.history.slice().reverse().map((x) => `${fmtDate(x.at)} — ${x.event}${x.detail ? ": " + x.detail : ""}`), "small")) : null);
  const notes = h("textarea", { "aria-label": "Notes", placeholder: "Your notes…", rows: "3" });
  notes.value = tr.notes || "";
  const notesBox = h("div", null, h("h3", null, "Notes"), notes,
    h("div", { class: "actions" }, h("button", { type: "button", onclick: () => act(r.id, "note", { note: notes.value }) }, "Save notes")));

  const cmd = commandFor(r);
  const confirmInput = h("input", { type: "text", placeholder: "Confirmation no. (optional)", "aria-label": "Confirmation number" });
  const actions = h("div", { class: "actions" },
    tr.status === "found" ? h("button", { class: "primary", type: "button", onclick: () => act(r.id, "shortlist") }, "Shortlist") : null,
    tr.status === "shortlisted" ? h("button", { type: "button", onclick: () => act(r.id, "unshortlist") }, "Unshortlist") : null,
    cmd ? h("button", { type: "button", onclick: () => copy(cmd) }, `Copy ${cmd.split(" ")[0]} command`) : null,
    tr.status !== "submitted" ? [confirmInput, h("button", { type: "button", onclick: () => act(r.id, "applied_myself", { confirmation: confirmInput.value }) }, "I applied myself")] : null,
    tr.status === "submitted" ? outcomeSelect(r) : null,
    tr.status === "dismissed"
      ? h("button", { type: "button", onclick: () => act(r.id, "restore") }, "Restore")
      : tr.status !== "submitted" ? h("button", { class: "danger ghost", type: "button", onclick: () => act(r.id, "dismiss") }, "Dismiss") : null);
  return h("tr", { class: "detail" }, h("td", { colspan: "9" },
    h("div", { class: "details" }, why, country, reqs, dates, funding, plan, appBox, notesBox), actions));
}

function taskEl(id, t) {
  const box = h("input", { type: "checkbox", id: `t-${id}-${t.key}`, onchange: (e) => act(id, "task", { key: t.key, done: e.target.checked }, true) });
  box.checked = t.done;
  const due = t.done ? "done" : `${fmtDate(t.due)} · ${daysText(t.days_left)}`;
  return h("div", { class: "task" }, box, h("label", { for: `t-${id}-${t.key}` }, t.label, h("div", { class: "sub" }, due)));
}

function outcomeSelect(r) {
  const current = (r.tracker.outcome && r.tracker.outcome.result) || "pending";
  return select(current, OUTCOMES.map((o) => [o, "Outcome: " + OUTCOME_LABEL[o]]),
    (v) => act(r.id, "outcome", { result: v }), "Outcome");
}

/* --------------------------------------------------------------- yourself */

function viewYourself(main) {
  const items = rows().filter(needsYourself).sort((a, b) => (a.timeline.deadline || "9999").localeCompare(b.timeline.deadline || "9999"));
  main.append(h("p", { class: "muted" }, "Applications the agent couldn't finish or can't do: open the link and apply yourself, then mark it applied."));
  if (!items.length) {
    main.append(h("div", { class: "empty" }, "Nothing needs you right now."));
    return;
  }
  const grid = h("div", { class: "cards" });
  for (const r of items) {
    const rec = r.record;
    const ev = r.evaluation;
    const tr = r.tracker;
    const why = tr.stop_reason ? "Agent stopped: " + tr.stop_reason
      : tr.waiting_for ? "Waiting for you: " + tr.waiting_for
      : tr.status === "awaiting_submit_ok" ? "The agent is waiting for your yes in Claude to submit."
      : MODE[ev.apply_mode];
    const confirmInput = h("input", { type: "text", placeholder: "Confirmation no. (optional)", "aria-label": "Confirmation number" });
    const link = safeUrl(rec.apply_url) || safeUrl(ev.admission.url) || safeUrl(rec.official_url);
    grid.append(h("div", { class: "card" },
      h("div", null, statusPill(r), " ", pill(URGENCY[r.timeline.urgency]), " ", feeChip(r)),
      h("div", { class: "title" }, rec.title), h("div", { class: "sub" }, rec.sponsor, " · ", (rec.host_countries || []).join(", ")),
      h("p", null, why),
      h("div", { class: "sub" }, "Deadline ", fmtDate(ev.deadline.date), " · ", daysText(ev.deadline.days_left)),
      h("div", { class: "actions" },
        link ? h("a", { href: link, target: "_blank", rel: "noopener noreferrer", class: "btn primary" }, "Open application", icon("external")) : null,
        ext(rec.official_url, "Official page ↗"),
        confirmInput,
        h("button", { type: "button", onclick: () => act(r.id, "applied_myself", { confirmation: confirmInput.value }) }, "I applied"))));
  }
  main.append(grid);
}

/* ------------------------------------------------------------------- week */

function viewWeek(main) {
  const w = S.data.week;
  main.append(h("h2", null, "Due in the next 7 days"));
  if (!w.tasks.length) main.append(h("p", { class: "muted" }, "No tasks due this week for applications you're pursuing."));
  else {
    const card = h("div", { class: "card" });
    for (const t of w.tasks) {
      card.append(h("div", null, h("div", { class: "sub" }, t.title), taskEl(t.id, t)));
    }
    main.append(card);
  }
  main.append(h("h2", null, "Closing soon — you haven't decided yet"));
  if (!w.undecided.length) main.append(h("p", { class: "muted" }, "Nothing undecided is close."));
  else {
    const grid = h("div", { class: "cards" });
    for (const u of w.undecided) {
      grid.append(h("div", { class: "card" }, h("div", { class: "title" }, u.title),
        h("div", { class: "sub" }, "Start by ", fmtDate(u.start_by), " · deadline ", fmtDate(u.deadline)),
        h("div", { class: "actions" },
          h("button", { class: "primary", type: "button", onclick: () => act(u.id, "shortlist") }, "Shortlist"),
          h("button", { class: "ghost danger", type: "button", onclick: () => act(u.id, "dismiss") }, "Not for me"))));
    }
    main.append(grid);
  }
}

/* ------------------------------------------------------------------- near */

function viewNear(main) {
  const items = rows().filter((r) => r.evaluation.bucket === "near_miss" && r.evaluation.in_scope);
  main.append(h("p", { class: "muted" }, "You'd qualify for these with one fixable change (a test score, admission, a document, experience)."));
  if (!items.length) {
    main.append(h("div", { class: "empty" }, "No near misses."));
    return;
  }
  const grid = h("div", { class: "cards" });
  for (const r of items) {
    grid.append(h("div", { class: "card" }, h("div", null, feeChip(r)), h("div", { class: "title" }, r.record.title),
      h("div", { class: "sub" }, r.record.sponsor, " · deadline ", fmtDate(r.evaluation.deadline.date), " ", daysText(r.evaluation.deadline.days_left)),
      h("b", null, "What's missing"), list(r.evaluation.gaps),
      h("div", { class: "actions" }, ext(r.record.official_url, "Official page ↗"))));
  }
  main.append(grid);
}

/* ----------------------------------------------------------------- drafts */

async function openDraft(id) {
  S.draftId = id;
  try {
    const res = await fetch("/api/drafts/" + encodeURIComponent(id), { cache: "no-store" });
    S.draft = await res.json();
  } catch {
    S.draft = null;
  }
  render();
}

function viewDrafts(main) {
  const items = rows().filter((r) => r.drafts.has_brief);
  if (!items.length) {
    main.append(h("div", { class: "empty" }, "No drafts yet. In Claude, run ", h("code", null, "/tailor <id>"),
      " for an opportunity (use the copy button in its details)."));
    return;
  }
  const side = h("div", { class: "list" }, items.map((r) => h("button", {
    type: "button", class: S.draftId === r.id ? "active" : "", onclick: () => openDraft(r.id),
  }, h("div", { class: "title" }, trunc(r.record.title, 60)),
    h("div", { class: "sub" }, `${r.drafts.approved}/${r.drafts.total} approved`, r.drafts.changes_requested ? ` · ${r.drafts.changes_requested} to revise` : ""))));
  // Open the first application straight away instead of an empty pane.
  if (!S.draftId || !items.some((r) => r.id === S.draftId)) {
    openDraft(items[0].id);
    main.append(h("p", { class: "muted pad" }, "Loading drafts…"));
    return;
  }
  const body = h("div");
  if (!S.draft || !S.draft.brief) body.append(h("p", { class: "muted" }, "Pick an application on the left."));
  else body.append(draftBody(S.draftId, S.draft));
  main.append(h("div", { class: "split" }, side, body));
}

function draftBody(id, d) {
  const b = d.brief;
  const out = h("div");
  const cv = b.cv_choice;
  out.append(h("div", { class: "card" }, h("h3", null, "CV chosen"),
    cv ? [h("p", null, h("b", null, cv.path)), h("p", null, cv.reason),
      cv.runner_up ? h("p", { class: "sub" }, "Runner-up: ", cv.runner_up.path || "", cv.runner_up.reason ? " — " + cv.runner_up.reason : "") : null]
      : h("p", { class: "muted" }, "Not chosen yet."),
    b.criteria && b.criteria.length ? [h("h3", null, "What this funder scores"), list(b.criteria)] : null,
    b.ai_policy ? [h("h3", null, "AI-use policy"), h("p", null, b.ai_policy)] : null));
  for (const q of b.questions) {
    const a = d.answers[q.qid] || {};
    const checks = a.checks || {};
    const ta = h("textarea", { "aria-label": q.prompt });
    ta.value = a.text || "";
    const counter = h("span", { class: "chip" });
    const countNow = () => {
      const words = (ta.value.match(/\b\w[\w'’-]*\b/g) || []).length;
      const used = q.unit === "characters" ? ta.value.length : words;
      counter.textContent = `${used}${q.limit ? " / " + q.limit : ""} ${q.unit}`;
      counter.className = "chip " + (q.limit && used > q.limit ? "bad" : "");
    };
    ta.addEventListener("input", countNow);
    countNow();
    const feedback = h("input", { type: "text", placeholder: "What should change?", "aria-label": "Feedback" });
    const statusChip = a.status === "approved" ? chip("Approved", "dark") : a.status === "changes_requested" ? chip("Changes requested", "warn") : a.text ? chip("Draft", "accent") : chip("Not drafted");
    out.append(h("div", { class: "card q" },
      h("div", { class: "title" }, q.prompt),
      h("div", { class: "meta" }, statusChip, counter, q.category ? chip(q.category) : null,
        (checks.other_scholarship_names || []).length ? chip("Mentions another scholarship: " + checks.other_scholarship_names.join(", "), "bad") : null,
        a.sources && a.sources.length ? h("span", { class: "sub" }, "Based on facts: " + a.sources.join(", ")) : null),
      a.feedback ? h("p", { class: "sub" }, "Your last feedback: " + a.feedback) : null,
      ta,
      h("div", { class: "actions" },
        h("button", { class: "primary", type: "button", disabled: !ta.value.trim(), onclick: async () => {
          const edited = ta.value !== (a.text || "");
          const r = await post("/api/draft", { id, qid: q.qid, op: edited ? "edit_approve" : "approve", text: ta.value });
          if (r.ok) { toast("Approved"); await openDraft(id); await load(); }
        } }, a.status === "approved" ? "Save edits & keep approved" : "Approve"),
        feedback,
        h("button", { type: "button", onclick: async () => {
          if (!feedback.value.trim()) { toast("Write what should change first."); return; }
          const r = await post("/api/draft", { id, qid: q.qid, op: "request_changes", feedback: feedback.value });
          if (r.ok) { toast("Sent back — run /tailor again in Claude"); await openDraft(id); await load(); }
        } }, "Request changes"))));
  }
  return out;
}

/* -------------------------------------------------------------- submitted */

function viewSubmitted(main) {
  const items = rows().filter((r) => r.tracker.status === "submitted")
    .sort((a, b) => (b.tracker.submitted_at || "").localeCompare(a.tracker.submitted_at || ""));
  const st = S.data.stats;
  const by = st.by_result || {};
  main.append(h("div", { class: "stats" },
    h("div", { class: "stat" }, h("b", null, st.submitted), "submitted"),
    h("div", { class: "stat" }, h("b", null, (by.interview || 0) + (by.shortlisted || 0)), "interview / shortlisted"),
    h("div", { class: "stat" }, h("b", null, by.offer_won || 0), "won"),
    h("div", { class: "stat" }, h("b", null, by.pending || 0), "waiting")));
  const cvs = Object.entries(st.by_cv || {});
  if (cvs.length) {
    main.append(h("div", { class: "card" }, h("h3", null, "Which CV is working"),
      h("ul", null, cvs.map(([cv, s]) => h("li", null, `${cv}: ${s.submitted} sent, ${s.positive} interview/shortlist/win, ${s.won} won`)))));
  }
  if (!items.length) {
    main.append(h("div", { class: "empty" }, "Nothing submitted yet."));
    return;
  }
  const tbody = h("tbody");
  for (const r of items) {
    const tr = r.tracker;
    const snap = tr.snapshot ? encodeURIComponent(r.id) : null;
    tbody.append(h("tr", null,
      h("td", null, h("div", { class: "title" }, r.record.title), h("div", { class: "sub" }, r.record.sponsor)),
      h("td", { class: "nowrap" }, fmtDate(tr.submitted_at), h("div", { class: "sub" }, tr.submitted_by === "you" ? "by you" : "by the agent")),
      h("td", null, tr.confirmation || "—"),
      h("td", null, snap ? [h("a", { href: `/submitted/${snap}/answers.md`, target: "_blank" }, "Answers"), " · ",
        h("a", { href: `/submitted/${snap}/summary.json`, target: "_blank" }, "Full copy")] : "—"),
      h("td", null, outcomeSelect(r))));
  }
  main.append(h("table", { class: "grid" }, h("thead", null, h("tr", null,
    ["Application", "Submitted", "Confirmation", "Saved copy", "Outcome"].map((t) => h("th", { scope: "col" }, t)))), tbody));
}

/* ------------------------------------------------------------ supervisors */

function viewSupervisors(main) {
  const items = S.data.outreach;
  main.append(h("p", { class: "muted" }, "Supervisors suggested by ", h("code", null, "/outreach"), ". Emails are drafted for you; nothing is sent without your OK."));
  if (!items.length) {
    main.append(h("div", { class: "empty" }, "No supervisors yet."));
    return;
  }
  const statuses = ["suggested", "drafted", "sent", "replied_positive", "replied_negative", "no_reply", "dropped"];
  const tbody = h("tbody");
  for (const s of items) {
    tbody.append(h("tr", null,
      h("td", null, h("div", { class: "title" }, s.name), h("div", { class: "sub" }, s.institution, s.country ? " · " + s.country : "")),
      h("td", null, trunc(s.match, 220)),
      h("td", null, ext(s.profile_url, "Profile ↗")),
      h("td", null, select(s.status, statuses.map((x) => [x, x.replace(/_/g, " ")]), async (v) => {
        const r = await post("/api/outreach", { id: s.id, status: v });
        if (r.ok) { toast(r.warning || "Saved"); load(); }
      }, "Status"))));
  }
  main.append(h("table", { class: "grid" }, h("thead", null, h("tr", null,
    ["Supervisor", "Why they match", "Page", "Status"].map((t) => h("th", { scope: "col" }, t)))), tbody));
}

/* ------------------------------------------------------------------ links */

function viewLinks(main) {
  const url = h("input", { type: "url", placeholder: "https://… scholarship or PhD posting", "aria-label": "Link", class: "grow" });
  const note = h("input", { type: "text", placeholder: "Note (optional)", "aria-label": "Note" });
  const add = async () => {
    const r = await post("/api/inbox", { op: "add", url: url.value, note: note.value });
    if (r.ok) { toast(r.note || "Queued for the next daily run"); url.value = ""; note.value = ""; load(); }
  };
  main.append(h("div", { class: "card" }, h("h2", null, "Add a link"),
    h("p", { class: "muted" }, "Queued links are checked on the next daily run (official page, scam checks, your eligibility) and added to your list. For something urgent, paste it straight into Claude:"),
    h("div", { class: "toolbar" }, url, note, h("button", { class: "primary", type: "button", onclick: add }, "Queue link"),
      h("button", { type: "button", onclick: () => { if (safeUrl(url.value)) copy(`/apply ${url.value}`); else toast("Paste a full https:// link first"); } }, "Copy /apply command"))));
  const items = S.data.inbox.slice().reverse().filter((l) => l.status !== "removed");
  if (!items.length) return;
  const tbody = h("tbody");
  for (const l of items) {
    tbody.append(h("tr", null,
      h("td", null, ext(l.url, trunc(l.url, 70)), l.note ? h("div", { class: "sub" }, l.note) : null),
      h("td", null, fmtDate(l.added)),
      h("td", null, pill([l.status, l.status === "processed" ? "ok" : l.status === "rejected" ? "bad" : "accent"]), l.result ? h("div", { class: "sub" }, l.result) : null),
      h("td", null, l.status === "queued" ? h("button", { class: "ghost danger", type: "button", onclick: async () => {
        const r = await post("/api/inbox", { op: "remove", link_id: l.id });
        if (r.ok) load();
      } }, "Remove") : null)));
  }
  main.append(h("table", { class: "grid" }, h("thead", null, h("tr", null,
    ["Link", "Added", "Status", ""].map((t) => h("th", { scope: "col" }, t)))), tbody));
}

/* -------------------------------------------------------------- documents */

const DOC_LABEL = {
  cv: "CV / résumé", transcript: "Transcript / marksheet", degree_certificate: "Degree certificate",
  language_certificate: "English test (IELTS, TOEFL…)", research_proposal: "Research proposal",
  writing_sample: "Essay or past application", recommendation_letter: "Reference letter", portfolio: "Portfolio",
  photo: "Photo", publication: "Publication", cover_letter: "Cover letter", motivation_letter: "Statement of purpose",
  passport_scan: "Passport scan", id_document: "ID document", other: "Other",
};
const UPLOAD_MAX = 15 * 1024 * 1024;

function guessDocType(name) {
  const n = name.toLowerCase();
  const rules = [
    [/transcript|marksheet|mark sheet|grades/, "transcript"], [/degree|diploma|certificate of graduation/, "degree_certificate"],
    [/ielts|toefl|duolingo|pte|trf/, "language_certificate"], [/passport/, "passport_scan"], [/cnic|national id|\bid card/, "id_document"],
    [/proposal/, "research_proposal"], [/recommend|reference letter|\blor\b/, "recommendation_letter"],
    [/statement|sop|motivation/, "motivation_letter"], [/cover letter/, "cover_letter"], [/\bcv\b|resume|résumé|curriculum/, "cv"],
    [/photo|picture/, "photo"], [/paper|publication/, "publication"],
  ];
  for (const [re, type] of rules) if (re.test(n)) return type;
  return "other";
}
function fmtSize(bytes) {
  if (!bytes && bytes !== 0) return "—";
  return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
}
function readBase64(file) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result).split(",")[1] || "");
    fr.onerror = () => reject(fr.error);
    fr.readAsDataURL(file);
  });
}

function missingDocTypes() {
  const have = new Set((S.data.documents || []).map((d) => d.type));
  const need = new Map();
  for (const r of rows()) {
    if (!pursuing(r) || ["submitted", "dismissed"].includes(r.tracker.status)) continue;
    for (const t of (r.record.application || {}).documents || []) {
      // Referees send their own letters and statements are written in Drafts, so they aren't uploads.
      if (have.has(t) || ["passport_scan", "id_document", "recommendation_letter", "motivation_letter", "cover_letter"].includes(t)) continue;
      if (!need.has(t)) need.set(t, []);
      need.get(t).push(r);
    }
  }
  return need;
}

function viewDocs(main) {
  const docs = S.data.documents || [];
  const types = S.data.doc_types || Object.keys(DOC_LABEL);
  let file = null;

  const picked = h("div", { class: "sub" }, "No file chosen yet.");
  const typeSel = select("other", types.map((t) => [t, DOC_LABEL[t] || t]), () => {}, "Document type");
  const label = h("input", { type: "text", class: "grow", placeholder: "Label, e.g. 'CV - research focus'", "aria-label": "Label" });
  const input = h("input", { type: "file", id: "doc-file", class: "sr-only", accept: ".pdf,.docx,.png,.jpg,.jpeg,.txt,.md" });
  const choose = (f) => {
    if (!f) return;
    file = f;
    picked.textContent = `${f.name} · ${fmtSize(f.size)}`;
    typeSel.value = guessDocType(f.name);
    if (!label.value.trim()) label.value = f.name.replace(/\.[^.]+$/, "");
  };
  input.addEventListener("change", () => choose(input.files[0]));
  const zone = h("label", { for: "doc-file", class: "dropzone" },
    h("b", null, "Drop a file here or click to choose"),
    h("span", { class: "sub" }, "PDF, Word (.docx), PNG/JPG or text · up to 15 MB"));
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); choose(e.dataTransfer.files[0]); });

  const btn = h("button", { class: "primary", type: "button" }, "Upload");
  btn.addEventListener("click", async () => {
    if (!file) { toast("Choose a file first."); return; }
    if (file.size > UPLOAD_MAX) { toast("That file is over 15 MB."); return; }
    btn.disabled = true;
    btn.textContent = "Uploading…";
    try {
      const body = { name: file.name, type: typeSel.value, label: label.value, data: await readBase64(file) };
      let r = await post("/api/upload", body, true);
      if (!r.ok && r.exists && window.confirm(r.error)) r = await post("/api/upload", { ...body, replace: true }, true);
      if (r.ok) {
        toast((r.replaced ? "Replaced " : "Saved ") + r.document.path + (r.note ? " — " + r.note : " — run /ingest in Claude so the writer reads it"));
        await load();
        return;
      }
      if (!r.exists) toast(r.error || "Upload failed.");
    } catch {
      toast("Couldn't read that file.");
    }
    btn.disabled = false;
    btn.textContent = "Upload";
  });

  main.append(...banners());
  const need = missingDocTypes();
  if (need.size) {
    main.append(h("div", { class: "card hint" }, h("h3", null, "Your shortlisted applications still need"),
      h("ul", null, [...need].map(([t, list]) => h("li", null, h("b", null, DOC_LABEL[t] || t),
        h("span", { class: "sub" }, " — " + list.map((r) => shortName(r)).join("; "))))),
      h("p", { class: "sub" }, "Reference letters go straight from your referees to the portal, and statements are written in the Drafts tab.")));
  }
  main.append(h("div", { class: "card" }, h("h2", null, "Add a document"),
    h("p", { class: "muted" }, "Files are saved in the documents folder on this PC and are only uploaded to an application portal during an application you approve. Passport and ID scans are always uploaded by you, never by the agent."),
    input, zone, picked,
    h("div", { class: "toolbar upload-row" }, typeSel, label, btn)));

  if (!docs.length) {
    main.append(h("div", { class: "empty" }, "No documents yet."));
    return;
  }
  const STATE = { read: ["Read by the writer", "ok"], new: ["New — run /ingest", "warn"], changed: ["Changed — run /ingest", "warn"],
    missing_on_disk: ["File missing", "bad"] };
  const tbody = h("tbody");
  for (const d of docs.slice().sort((a, b) => (b.added || "").localeCompare(a.added || ""))) {
    tbody.append(h("tr", null,
      h("td", null, h("div", { class: "title" }, d.label || d.name), h("div", { class: "sub" }, d.name)),
      h("td", null, DOC_LABEL[d.type] || d.type),
      h("td", { class: "nowrap" }, fmtSize(d.size)),
      h("td", { class: "nowrap" }, fmtDate(d.added)),
      h("td", null, pill(STATE[d.status] || [d.status, ""])),
      h("td", null, d.id != null ? h("button", { class: "ghost danger", type: "button", onclick: async () => {
        if (!window.confirm(`Remove "${d.label || d.name}" from your list? The file itself stays in the documents folder.`)) return;
        const r = await post("/api/profile", { op: "remove", list: "documents", id: d.id });
        if (r.ok) { toast("Removed from the list"); load(); }
      } }, "Remove") : null)));
  }
  main.append(h("table", { class: "grid docs" }, h("thead", null, h("tr", null,
    ["Document", "Type", "Size", "Added", "Writer", ""].map((t) => h("th", { scope: "col" }, t)))), tbody));
}

/* ---------------------------------------------------------------- profile */

const SECTIONS = [
  ["identity", "About you & contact", "Used to fill application forms."],
  ["target", "What you're looking for", "Controls what the search finds and how eligibility is checked."],
  ["consent", "Search permissions", ""],
  ["narrative", "Your story (optional)", "Your own words. Your uploaded essays already cover much of this."],
];
const LISTS_UI = [
  ["education", "Education", (r) => [r.degree, r.institution, span(r.start, r.end)]],
  ["tests", "Tests (IELTS, TOEFL, GRE…)", (r) => [r.exam, r.score != null ? "score " + r.score : "", r.expires ? "expires " + r.expires : ""]],
  ["experience", "Work experience", (r) => [r.role, r.organization, span(r.start, r.end || "now")]],
  ["publications", "Publications", (r) => [r.title, r.venue, r.year, r.status, r.authors ? "authors: " + r.authors : "authors missing"]],
  ["awards", "Awards", (r) => [r.name, r.issuer, r.year]],
  ["activities", "Activities & community", (r) => [r.name, r.role]],
  ["references", "Referees", (r) => [r.name, r.title, r.institution, r.email]],
  ["languages", "Languages", (r) => [r.language, r.level, r.certificate]],
  ["residence", "Where you've lived", (r) => [r.country, span(r.from, r.to || "now"), r.status]],
];
function span(a, b) {
  return a || b ? `${a || "?"} – ${b || "?"}` : "";
}
function human(s) {
  s = String(s).replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

async function loadProfile() {
  try {
    const res = await fetch("/api/profile", { cache: "no-store" });
    S.profile = await res.json();
  } catch {
    S.profile = null;
  }
}

/* One form control per field type; get() returns what to send to the server. */
function fieldControl(spec, value, id) {
  const t = spec.type;
  const str = value == null ? "" : Array.isArray(value) ? value.join(", ") : String(value);
  if (t === "long_text") {
    const ta = h("textarea", { id, rows: "4" });
    ta.value = str;
    return { el: ta, get: () => ta.value };
  }
  if (t === "choice") {
    const s = select(str, [["", "—"], ...spec.choices.map((c) => [c, human(c)])], () => {}, spec.label);
    s.id = id;
    return { el: s, get: () => s.value };
  }
  if (t === "bool") {
    const v = value === true ? "yes" : value === false ? "no" : "";
    const s = select(v, [["", "—"], ["yes", "Yes"], ["no", "No"]], () => {}, spec.label);
    s.id = id;
    return { el: s, get: () => s.value };
  }
  if (t === "choice_list") {
    const chosen = new Set(Array.isArray(value) ? value : []);
    const boxes = spec.choices.map((c) => {
      const cb = h("input", { type: "checkbox", value: c, id: `${id}-${c}` });
      cb.checked = chosen.has(c);
      return [cb, h("label", { for: `${id}-${c}` }, human(c))];
    });
    const wrap = h("div", { class: "checks", id }, boxes.map(([cb, lb]) => h("span", null, cb, " ", lb)));
    return { el: wrap, get: () => boxes.filter(([cb]) => cb.checked).map(([cb]) => cb.value) };
  }
  const type = { email: "email", url: "url", phone: "tel", date: "date", month: "month", number: "text" }[t] || "text";
  const input = h("input", { type, id, value: str,
    placeholder: t === "list" || t === "country_list" ? "Separate with commas" : t === "month" ? "YYYY-MM" : "" });
  return { el: input, get: () => input.value };
}
function same(a, b) {
  const norm = (v) => (v == null ? "" : Array.isArray(v) ? v.join(", ") : v === true ? "yes" : v === false ? "no" : String(v));
  return norm(a) === norm(b);
}
function fieldBox(spec, control, id) {
  return h("div", { class: "field" + (spec.type === "long_text" ? " wide" : "") },
    h("label", { for: id }, spec.label, spec.required ? " *" : ""), control.el, h("div", { class: "error", "data-error": id }));
}

function scalarSection(prefix, title, intro) {
  const P = S.profile;
  const specs = P.schema.scalars.filter((s) => s.key.split(".")[0] === prefix);
  if (!specs.length) return null;
  const controls = specs.map((s) => [s, fieldControl(s, P.values[s.key], "f-" + s.key.replace(/\./g, "-"))]);
  const save = h("button", { class: "primary", type: "button" }, "Save changes");
  save.addEventListener("click", async () => {
    let saved = 0;
    let failed = 0;
    for (const [s, c] of controls) {
      const errBox = document.querySelector(`[data-error="f-${s.key.replace(/\./g, "-")}"]`);
      if (errBox) errBox.textContent = "";
      const v = c.get();
      if (same(v, P.values[s.key])) continue;
      const r = await post("/api/profile", { op: "set", key: s.key, value: v }, true);
      if (r.ok) saved++;
      else { failed++; if (errBox) errBox.textContent = r.error; }
    }
    if (failed) toast(`${failed} field(s) not saved — see the message under each one.`);
    else toast(saved ? `Saved ${saved} change(s)` : "Nothing changed");
    if (saved) { await loadProfile(); await load(); }
  });
  return h("section", { class: "card" }, h("h2", null, title), intro ? h("p", { class: "muted" }, intro) : null,
    h("div", { class: "form-grid" }, controls.map(([s, c]) => fieldBox(s, c, "f-" + s.key.replace(/\./g, "-")))),
    h("div", { class: "actions" }, save));
}

function rowForm(name, specs, row, onDone) {
  const controls = specs.map((s) => [s, fieldControl(s, row ? row[s.field] : null, `r-${name}-${row ? row.id : "new"}-${s.field}`)]);
  const err = h("div", { class: "error" });
  const save = h("button", { class: "primary", type: "button" }, row ? "Save" : "Add");
  save.addEventListener("click", async () => {
    const fields = {};
    for (const [s, c] of controls) {
      const v = c.get();
      if (row) { if (!same(v, row[s.field])) fields[s.field] = Array.isArray(v) ? v.join(", ") : v; }
      else if (!(v === "" || (Array.isArray(v) && !v.length))) fields[s.field] = Array.isArray(v) ? v.join(", ") : v;
    }
    if (row && !Object.keys(fields).length) { onDone(); return; }
    const r = await post("/api/profile", row ? { op: "update", list: name, id: row.id, fields } : { op: "add", list: name, fields }, true);
    if (!r.ok) { err.textContent = r.error; return; }
    toast(row ? "Saved" : "Added");
    await loadProfile();
    await load();
  });
  return h("div", { class: "row-form" },
    h("div", { class: "form-grid" }, controls.map(([s, c]) => fieldBox(s, c, c.el.id))), err,
    h("div", { class: "actions" }, save, h("button", { class: "ghost", type: "button", onclick: onDone }, "Cancel")));
}

function listSection(name, title, summary) {
  const P = S.profile;
  const specs = P.schema.lists[name] || [];
  const rowsList = P.lists[name] || [];
  const box = h("section", { class: "card" });
  const body = h("div");
  const draw = (editing) => {
    body.replaceChildren();
    if (!rowsList.length && editing !== "new") body.append(h("p", { class: "muted" }, "Nothing added yet."));
    for (const r of rowsList) {
      if (editing === r.id) { body.append(rowForm(name, specs, r, () => draw(null))); continue; }
      const parts = summary(r).filter((x) => x !== "" && x != null);
      body.append(h("div", { class: "row-item" },
        h("div", null, h("div", { class: "title" }, parts[0] || "(untitled)"), h("div", { class: "sub" }, parts.slice(1).join(" · "))),
        h("div", { class: "row-actions" },
          h("button", { type: "button", onclick: () => draw(r.id) }, "Edit"),
          h("button", { class: "ghost danger", type: "button", onclick: async () => {
            if (!window.confirm(`Remove "${parts[0] || "this entry"}"?`)) return;
            const res = await post("/api/profile", { op: "remove", list: name, id: r.id });
            if (res.ok) { toast("Removed"); await loadProfile(); await load(); }
          } }, "Remove"))));
    }
    if (editing === "new") body.append(rowForm(name, specs, null, () => draw(null)));
  };
  box.append(h("div", { class: "section-head" }, h("h2", null, title),
    h("button", { type: "button", onclick: () => draw("new") }, "+ Add")), body);
  draw(null);
  return box;
}

function viewProfile(main) {
  if (!S.profile) {
    main.append(h("p", { class: "muted pad" }, "Loading your profile…"));
    loadProfile().then(() => { if (S.tab === "profile") render(); });
    return;
  }
  const P = S.profile;
  if (!P.ok) { main.append(h("div", { class: "empty" }, "Couldn't load your profile.")); return; }
  const labelOf = (k) => (P.schema.scalars.find((s) => s.key === k) || {}).label || human(k.replace(/^.*[.:]/, ""));
  const st = P.status;
  const missing = [...st.missing_for_search, ...st.missing_for_apply.filter((k) => !st.missing_for_search.includes(k))];
  main.append(h("div", { class: "card" },
    h("h2", null, `Profile ${st.completeness_percent}% complete`),
    h("p", { class: "muted" }, "Everything here is saved only on this PC, and Claude reads the same details when it searches, writes and fills applications. You can also change any of it by asking Claude in chat. Passwords, passport/ID numbers and bank details are refused: you type those into portals yourself."),
    missing.length ? h("p", null, h("b", null, "Still needed: "), missing.map(labelOf).join(", ")) : h("p", { class: "req-pass" }, "Ready for searching and applying.")));
  for (const [prefix, title, intro] of SECTIONS) main.append(scalarSection(prefix, title, intro));
  for (const [name, title, summary] of LISTS_UI) main.append(listSection(name, title, summary));
}

const VIEWS = {
  overview: viewOverview, opps: viewOpps, yourself: viewYourself, week: viewWeek, near: viewNear, profile: viewProfile, docs: viewDocs, drafts: viewDrafts,
  submitted: viewSubmitted, supervisors: viewSupervisors, links: viewLinks,
};

document.getElementById("tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-tab]");
  if (!b) return;
  S.tab = b.dataset.tab;
  if (S.tab === "profile") S.profile = null; // always show the latest saved profile
  render();
  document.getElementById("view").focus();
});
const startTab = location.hash.slice(1);
if (VIEWS[startTab]) S.tab = startTab;
window.addEventListener("hashchange", () => {
  const t = location.hash.slice(1);
  if (VIEWS[t] && t !== S.tab) go(t);
});
document.getElementById("refresh").addEventListener("click", () => load().then(() => toast("Refreshed")));
document.getElementById("add-link").addEventListener("click", () => go("links"));
document.querySelector(".mark").addEventListener("click", (e) => { e.preventDefault(); go("overview"); });
// The header search filters opportunities; typing jumps to that tab and keeps focus in the box.
document.getElementById("search").addEventListener("input", (e) => {
  S.f.q = e.target.value;
  S.tab = "opps";
  render();
});
// Refresh when you come back to the window, except on tabs with forms (it would wipe what you're typing).
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !["profile", "docs", "drafts"].includes(S.tab)) load();
});
load();

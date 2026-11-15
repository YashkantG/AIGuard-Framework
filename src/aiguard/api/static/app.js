"use strict";

/* AIGuard dashboard. Plain JavaScript, no build step, no third-party code.
   All API data is inserted with textContent; innerHTML is used only for the
   constant SVG strings below. */

const state = { key: sessionStorage.getItem("aiguard.key") || "", me: null, renderToken: 0 };

const svg = (body) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
const ICONS = {
  overview: svg('<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'),
  models: svg('<path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"/><path d="m3 7 9 5 9-5M12 12v10"/>'),
  policies: svg('<path d="M9 11l2 2 4-4"/><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z"/>'),
  audit: svg('<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>'),
  plus: svg('<path d="M12 5v14M5 12h14"/>'),
  download: svg('<path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16"/>'),
  logout: svg('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>'),
  brand:
    '<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#6d8dff"/><stop offset="1" stop-color="#2dd4bf"/></linearGradient></defs><path d="M16 2 4 6.5v8.6c0 7.1 4.9 12.6 12 14.9 7.1-2.3 12-7.8 12-14.9V6.5L16 2Z" fill="url(#bg)"/><path d="m10.5 16.2 3.8 3.8 7.4-8" fill="none" stroke="#0b1020" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

// ---------------------------------------------------------------- helpers

function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key === "text") el.textContent = value;
    else if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}

function icon(name) {
  const span = h("span", { class: "row" });
  span.innerHTML = ICONS[name];
  return span.firstChild;
}

function toast(message, isError = false) {
  const el = h("div", { class: "toast" + (isError ? " error" : ""), text: message });
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), isError ? 7000 : 3500);
}

function errorText(data) {
  const detail = data && data.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  }
  return typeof detail === "string" ? detail : "Request failed";
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { "X-API-Key": state.key };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch("/api/v1" + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const isJson = (res.headers.get("content-type") || "").includes("json");
  const data = isJson ? await res.json() : await res.text();
  if (res.status === 401 && state.me) {
    signOut();
    throw new Error("Your session ended. Sign in again.");
  }
  if (!res.ok) throw new Error(isJson ? errorText(data) : `Request failed (${res.status})`);
  return data;
}

const canWrite = () => state.me && state.me.role !== "viewer";
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—");
const short = (hash, n = 12) => (hash ? hash.slice(0, n) + "…" : "—");
const num = (value, digits = 3) => (value == null ? "—" : Number(value).toFixed(digits));
const pct = (part, total) => (total ? (100 * part) / total : 0);

const TONE = {
  pass: "good", success: "good", stable: "good", generated: "good", low: "good",
  fail: "bad", drift_detected: "bad", high: "bad", critical: "bad", error: "bad", significant: "bad",
  medium: "warn", moderate: "warn", info: "info",
};
const LABEL = {
  pass: "Pass", fail: "Fail", success: "Success", stable: "Stable", generated: "Generated",
  drift_detected: "Drift detected", not_applicable: "Not applicable", error: "Error",
  low: "Low", medium: "Medium", high: "High", critical: "Critical", info: "Info",
  moderate: "Moderate", significant: "Significant",
};

function badge(value, fallback = "Not run") {
  if (!value) return h("span", { class: "badge plain", text: fallback });
  return h("span", { class: "badge " + (TONE[value] || ""), text: LABEL[value] || value });
}

function tierBadge(tier) {
  const tone = tier === "high" ? "warn" : tier === "minimal" ? "info" : "";
  return h("span", { class: `badge plain ${tone}`, text: `${tier} impact` });
}

function card(title, hint, ...body) {
  return h("section", { class: "card" },
    title && h("div", { class: "card-head" }, h("h2", { text: title }), h("span", { class: "spacer" }), hint && h("span", { class: "muted", text: hint })),
    ...body);
}

function empty(title, text, action) {
  return h("div", { class: "empty" }, h("h3", { text: title }), h("p", { text }), action && h("div", { class: "row" }, h("span", { class: "spacer" }), action, h("span", { class: "spacer" })));
}

function bar(name, value, max, tone, valueText, mark) {
  const fill = h("div", { class: `bar-fill c-${tone}` });
  fill.style.width = Math.min(100, pct(value, max)) + "%";
  if (value > 0) fill.style.minWidth = "3px";
  const track = h("div", { class: "bar-track" }, fill);
  if (mark != null) {
    const marker = h("div", { class: "bar-mark", title: "Threshold" });
    marker.style.left = Math.min(100, pct(mark, max)) + "%";
    track.append(marker);
  }
  return h("div", { class: "bar-row" }, h("div", { class: "name", text: name, title: name }), track, h("div", { class: "val", text: valueText }));
}

function button(label, onclick, { kind = "", iconName, small } = {}) {
  const el = h("button", { class: `btn ${kind} ${small ? "sm" : ""}`, type: "button" }, iconName && icon(iconName), label);
  el.addEventListener("click", async () => {
    el.disabled = true;
    try { await onclick(); } catch (err) { toast(err.message, true); } finally { el.disabled = false; }
  });
  return el;
}

function gaussian(n, mean, sd) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const u = 1 - Math.random(), v = Math.random();
    out.push(+(mean + sd * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)).toFixed(4));
  }
  return out;
}

// ---------------------------------------------------------------- session

async function signIn(key) {
  state.key = key;
  state.me = await api("/me");
  sessionStorage.setItem("aiguard.key", key);
}

function signOut() {
  state.key = "";
  state.me = null;
  sessionStorage.removeItem("aiguard.key");
  render();
}

function loginView() {
  const input = h("input", { type: "password", name: "key", autocomplete: "off", required: true, placeholder: "Paste your API key" });
  const error = h("p", { class: "small", role: "alert" });
  error.style.color = "var(--bad)";
  const form = h("form", { class: "stack" },
    h("label", null, "API key", input), error,
    h("button", { class: "btn primary", type: "submit" }, "Sign in"));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    try { await signIn(input.value.trim()); render(); }
    catch (err) { state.key = ""; error.textContent = "That key was not accepted."; }
  });
  const brand = h("div", { class: "brand" });
  brand.innerHTML = ICONS.brand;
  brand.append(h("div", null, h("div", { class: "brand-name", text: "AIGuard" }), h("div", { class: "brand-tag", text: "AI model governance & security" })));
  return h("div", { class: "login" }, h("div", { class: "card" }, brand,
    h("p", { class: "muted", text: "Sign in with an API key. The key stays in this browser tab and is cleared when you close it." }),
    form,
    h("p", { class: "small muted" }, "Keys are configured with AIGUARD_API_KEYS. If none is set, the server prints a temporary admin key at startup.")));
}

// ---------------------------------------------------------------- shell

const NAV = [["overview", "Overview"], ["models", "Models"], ["policies", "Policies"], ["audit", "Audit trail"]];

function shell(active, content) {
  const brand = h("a", { class: "brand", href: "#/overview" });
  brand.innerHTML = ICONS.brand;
  brand.append(h("div", null, h("div", { class: "brand-name", text: "AIGuard" }), h("div", { class: "brand-tag", text: "Governance & security" })));
  const nav = h("nav", { class: "nav", "aria-label": "Main" }, NAV.map(([id, label]) =>
    h("a", { href: `#/${id}`, class: id === active ? "active" : "", "aria-current": id === active ? "page" : null }, icon(id), h("span", { text: label }))));
  const me = state.me;
  const foot = h("div", { class: "side-foot" },
    h("div", { class: "user-chip" }, h("div", { class: "avatar", text: me.name.slice(0, 2).toUpperCase() }),
      h("div", { class: "who" }, h("div", { text: me.name }), h("div", { class: "small muted", text: `${me.role} · v${me.version}` }))),
    button("Sign out", signOut, { kind: "ghost", iconName: "logout", small: true }));
  return h("div", { class: "shell" }, h("aside", { class: "sidebar" }, brand, nav, foot), h("main", { class: "main" }, content));
}

function pageHead(title, subtitle, ...actions) {
  return h("div", { class: "page-head" }, h("div", null, h("h1", { text: title }), subtitle && h("p", { text: subtitle })), h("span", { class: "spacer" }), h("div", { class: "row" }, ...actions));
}

// ---------------------------------------------------------------- overview

const RISK_ORDER = [["low", "good", "Low"], ["medium", "warn", "Medium"], ["high", "bad", "High"], ["critical", "crit", "Critical"], ["unassessed", "muted", "Unassessed"]];
const SEVERITIES = [["critical", "crit"], ["high", "bad"], ["medium", "warn"], ["low", "info"], ["info", "muted"]];

function kpi(label, value, sub, tone) {
  return h("div", { class: `card kpi tone-${tone}` }, h("div", { class: "kpi-label", text: label }), h("div", { class: "kpi-value", text: value }), h("div", { class: "kpi-sub", text: sub }));
}

function eventFeed(events, showModel = true) {
  if (!events.length) return h("p", { class: "muted", text: "No events yet." });
  return h("div", { class: "feed" }, events.map((e) => h("div", { class: "feed-item" },
    h("span", { class: "dot " + (TONE[e.result] || "") }),
    h("div", null,
      h("div", null, h("span", { class: "title mono", text: e.action }), " ", badge(e.result)),
      h("div", { class: "small muted", text: `${e.actor}${showModel && e.model_id ? " · " + e.model_id : ""} · ${short(e.event_hash, 10)}` })),
    h("div", { class: "small muted", text: fmtTime(e.timestamp) }))));
}

async function overviewView() {
  const s = await api("/stats");
  const blocking = s.open_findings.high + s.open_findings.critical;
  const passing = s.policy.pass || 0;
  const head = pageHead("Overview", "Security and governance posture across registered models.");
  if (!s.models) {
    return h("div", null, head, card(null, null, empty("No models registered yet", "Register a model to start tracking its integrity, security and governance evidence.", h("a", { class: "btn primary", href: "#/models" }, "Go to models"))));
  }
  const stack = h("div", { class: "stackbar", role: "img", "aria-label": "Risk level distribution" });
  const legend = h("div", { class: "legend" });
  for (const [level, tone, label] of RISK_ORDER) {
    const count = s.risk_levels[level] || 0;
    if (!count) continue;
    const seg = h("span", { class: `c-${tone}`, title: `${label}: ${count}` });
    seg.style.width = pct(count, s.models) + "%";
    stack.append(seg);
    legend.append(h("span", null, h("i", { class: `c-${tone}` }), `${label} ${count}`));
  }
  const maxFinding = Math.max(1, ...Object.values(s.open_findings));
  return h("div", { class: "stack" }, head,
    h("div", { class: "grid kpis" },
      kpi("Models", s.models, `${s.policies_defined} policies defined`, "info"),
      kpi("Passing all policies", `${passing}/${s.models}`, passing === s.models ? "Every model is compliant" : `${s.models - passing} need attention`, passing === s.models ? "good" : "warn"),
      kpi("High & critical findings", blocking, blocking ? "Open across latest assessments" : "None open", blocking ? "bad" : "good"),
      kpi("Audit chain", s.audit_chain.valid ? "Verified" : "Broken", `${s.audit_events} events`, s.audit_chain.valid ? "good" : "bad")),
    h("div", { class: "grid two" },
      card("Risk distribution", `${s.models} models`, stack, legend,
        h("p", { class: "small muted", text: s.models_with_drift ? `${s.models_with_drift} model(s) currently show drift.` : "No model currently shows drift." })),
      card("Open findings by severity", "latest assessment per model",
        h("div", { class: "bars" }, SEVERITIES.map(([sev, tone]) => bar(LABEL[sev], s.open_findings[sev], maxFinding, tone, s.open_findings[sev]))))),
    card("Recent activity", "audit trail", eventFeed(s.recent_events)));
}

// ---------------------------------------------------------------- models

function field(label, control, wide) {
  return h("label", { class: wide ? "wide" : "" }, label, control);
}

function registerDialog() {
  const f = {
    name: h("input", { required: true, placeholder: "credit-scoring" }),
    version: h("input", { required: true, placeholder: "1.0.0" }),
    framework: h("input", { placeholder: "pytorch" }),
    owner: h("input", { placeholder: "Team or person" }),
    artifact_path: h("input", { placeholder: "model.safetensors" }),
    sha256: h("input", { placeholder: "64 hex characters", class: "mono" }),
    impact_tier: h("select", null, ["minimal", "limited", "high"].map((t) => h("option", { value: t, selected: t === "limited", text: t }))),
    description: h("textarea", { rows: 2 }),
    intended_use: h("textarea", { rows: 2 }),
    human_oversight: h("textarea", { rows: 2, placeholder: "Who reviews decisions and how they can intervene" }),
  };
  const dialog = h("dialog");
  const form = h("form", { class: "stack" },
    h("div", null, h("h2", { text: "Register a model" }), h("p", { class: "muted small", text: "Give a file path inside the server's artifact directory, or a SHA-256 digest you computed yourself." })),
    h("div", { class: "form-grid" },
      field("Name", f.name), field("Version", f.version), field("Framework", f.framework), field("Owner", f.owner),
      field("Artifact path", f.artifact_path), field("SHA-256 digest", f.sha256), field("Impact tier", f.impact_tier),
      field("Description", f.description, true), field("Intended use", f.intended_use, true), field("Human oversight", f.human_oversight, true)),
    h("div", { class: "row" }, h("span", { class: "spacer" }),
      h("button", { class: "btn ghost", type: "button", onclick: () => dialog.close() }, "Cancel"),
      h("button", { class: "btn primary", type: "submit" }, "Register")));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const body = {};
    for (const [key, el] of Object.entries(f)) if (el.value.trim()) body[key] = el.value.trim();
    try {
      const model = await api("/models", { method: "POST", body });
      dialog.close();
      toast(`Registered ${model.name} ${model.version}`);
      location.hash = `#/models/${model.id}`;
    } catch (err) { toast(err.message, true); }
  });
  dialog.append(form);
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

async function modelsView() {
  const models = await api("/models");
  const add = canWrite() && button("Register model", registerDialog, { kind: "primary", iconName: "plus" });
  const head = pageHead("Models", "Every registered model version and its latest evidence.", add);
  if (!models.length) return h("div", null, head, card(null, null, empty("No models registered", "Register a model version to record its digest and begin collecting evidence.")));
  const rows = models.map((m) => {
    const p = m.posture;
    const tr = h("tr", { class: "link", tabindex: "0" },
      h("td", null, h("div", { class: "title", text: m.name }), h("div", { class: "small muted", text: `v${m.version} · ${m.framework}` })),
      h("td", null, tierBadge(m.impact_tier)),
      h("td", null, badge(p.integrity, "Unverified")),
      h("td", null, badge(p.security)),
      h("td", null, badge(p.drift)),
      h("td", null, badge(p.policy)),
      h("td", null, p.risk_level ? h("span", { class: "row" }, badge(p.risk_level), h("span", { class: "small muted", text: p.risk_score })) : badge(null, "Unassessed")));
    const open = () => (location.hash = `#/models/${m.id}`);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (e) => e.key === "Enter" && open());
    return tr;
  });
  return h("div", null, head, card(null, null, h("div", { class: "table-wrap" }, h("table", null,
    h("thead", null, h("tr", null, ["Model", "Impact", "Integrity", "Security", "Drift", "Policies", "Risk"].map((t) => h("th", { text: t })))),
    h("tbody", null, rows)))));
}

// ---------------------------------------------------------------- model detail

const TABS = [["summary", "Summary"], ["security", "Security"], ["drift", "Drift"], ["explain", "Explainability"], ["governance", "Governance"], ["lineage", "Lineage"], ["audit", "Audit"]];
const CONTROLS = [
  ["authentication_enabled", "Authentication enabled", true], ["tls_enabled", "TLS enabled", true],
  ["integrity_check_on_load", "Integrity check on load", true], ["rate_limiting_enabled", "Rate limiting enabled", true],
  ["input_validation_enabled", "Input validation enabled", true], ["egress_restricted", "Egress restricted", true],
  ["allow_pickle", "Accepts pickle artifacts", false], ["debug_mode", "Debug mode on", false], ["runs_as_root", "Runs as root", false],
];

function gauge(risk) {
  const tone = TONE[risk.level] || "info";
  const length = 2 * Math.PI * 46;
  const wrap = h("div", { class: "gauge" });
  wrap.innerHTML = `<svg viewBox="0 0 110 110" role="img" aria-label="Risk score"><circle class="ring-track" cx="55" cy="55" r="46" fill="none" stroke-width="10"/><circle class="ring ring-${tone}" cx="55" cy="55" r="46" fill="none" stroke-width="10" stroke-linecap="round" stroke-dasharray="${(length * Number(risk.score)) / 100} ${length}" transform="rotate(-90 55 55)"/></svg>`;
  wrap.append(h("div", null, h("div", { class: "score", text: `${risk.score}/100` }), badge(risk.level), h("div", { class: "small muted", text: "Indicative, from recorded evidence" })));
  return wrap;
}

function summaryTab(ctx) {
  const { model: m, evidence: ev } = ctx;
  const p = m.posture;
  const tiles = [["Integrity", badge(p.integrity, "Unverified")], ["Security", badge(p.security)], ["Drift", badge(p.drift)], ["Explanation", badge(p.explanation)], ["Policies", badge(p.policy)]];
  const risk = ev.risk_assessment && ev.risk_assessment.payload;
  const meta = [["Owner", m.owner || "Not recorded"], ["Description", m.description || "Not recorded"], ["Intended use", m.intended_use || "Not recorded"], ["Human oversight", m.human_oversight || "Not recorded"],
    ["SHA-256", h("code", { text: m.sha256 })], ["Artifact", m.artifact_available ? `Registered file (${(m.size_bytes / 1024).toFixed(1)} KB)` : "Digest only"], ["Registered", `${fmtTime(m.created_at)} by ${m.created_by}`]];
  return h("div", { class: "stack" },
    card("Posture", "latest evidence of each kind", h("div", { class: "tiles" }, tiles.map(([label, b]) => h("div", { class: "tile" }, h("span", { class: "small muted", text: label }), b)))),
    h("div", { class: "grid two" },
      card("Details", null, h("dl", { class: "meta" }, meta.map(([k, v]) => [h("dt", { text: k }), h("dd", null, v)]))),
      card("Risk", risk ? fmtTime(ev.risk_assessment.created_at) : null,
        risk ? [gauge(risk), h("div", { class: "bars" }, risk.factors.map((f) => bar(f.factor, f.points, f.max_points, f.points ? (f.points / f.max_points > 0.6 ? "bad" : "warn") : "good", `${f.points}/${f.max_points}`)))]
          : empty("Not assessed", "Run a risk assessment to score this model from its evidence."))));
}

function findingCard(f) {
  return h("div", { class: `finding sev-${f.severity}` },
    h("div", { class: "row" }, badge(f.severity), h("strong", { text: f.title }), h("span", { class: "spacer" }), h("code", { class: "muted", text: f.id })),
    h("p", { text: f.description }),
    h("div", { class: "fix" }, h("strong", { text: "Fix: " }), f.recommendation),
    (f.reference || f.location) && h("p", { class: "small muted", text: [f.location && `Location: ${f.location}`, f.reference].filter(Boolean).join(" · ") }));
}

function securityTab(ctx) {
  const item = ctx.evidence.security_assessment;
  const boxes = CONTROLS.map(([key, label, secure]) => [key, h("input", { type: "checkbox", checked: secure })]);
  const include = h("input", { type: "checkbox" });
  const reqs = h("textarea", { placeholder: "Paste requirements.txt to check for unpinned dependencies" });
  const run = async () => {
    const body = {};
    if (include.checked) body.deployment_config = Object.fromEntries(boxes.map(([key, el]) => [key, el.checked]));
    if (reqs.value.trim()) body.requirements = reqs.value;
    const result = await api(`/models/${ctx.model.id}/assess`, { method: "POST", body });
    toast(`Assessment finished: ${result.findings.length} finding(s)`);
    render();
  };
  const order = SEVERITIES.map(([s]) => s);
  const findings = item ? [...item.payload.findings].sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity)) : [];
  const controls = canWrite() && h("details", { class: "adv" }, h("summary", { text: "Assessment options" }),
    h("div", { class: "stack" },
      h("div", { class: "checks" }, h("label", null, include, "Include the deployment controls below")),
      h("div", { class: "checks" }, boxes.map(([key, el], i) => h("label", null, el, CONTROLS[i][1]))),
      field("Dependencies (optional)", reqs)));
  return h("div", { class: "stack" },
    card("Security assessment", item ? `${fmtTime(item.created_at)} · format: ${item.payload.artifact_format || "n/a"}` : null,
      item ? h("div", { class: "row" }, badge(item.status), h("span", { class: "muted", text: item.summary }), h("span", { class: "spacer" }), canWrite() && button("Run again", run, { kind: "primary" }))
        : empty("No assessment yet", "The artifact is inspected statically. It is never loaded or executed.", canWrite() && button("Run assessment", run, { kind: "primary" })),
      controls),
    findings.length ? h("div", { class: "stack" }, findings.map(findingCard)) : null,
    item && h("p", { class: "notice", text: item.payload.notice }));
}

function driftSample(shift) {
  const cats = (pWeb) => Array.from({ length: 500 }, () => (Math.random() < pWeb ? "web" : Math.random() < 0.6 ? "branch" : "mobile"));
  return {
    features: {
      income: { reference: gaussian(500, 5, 1), current: gaussian(500, 5 + shift, 1 + shift / 2) },
      account_age: { reference: gaussian(500, 3, 1), current: gaussian(500, 3, 1) },
      utilisation: { reference: gaussian(500, 0, 1), current: gaussian(500, shift / 2, 1) },
      channel: { kind: "categorical", reference: cats(0.5), current: cats(0.5 - shift / 3) },
    },
  };
}

function driftTab(ctx) {
  const item = ctx.evidence.drift;
  const run = async (body) => {
    const result = await api(`/models/${ctx.model.id}/drift`, { method: "POST", body });
    toast(result.drift_detected ? `Drift detected in ${result.drifted_features.join(", ")}` : "No drift detected");
    render();
  };
  const custom = h("textarea", { placeholder: '{"features": {"age": {"reference": [1, 2, 3], "current": [2, 3, 4]}}}' });
  const actions = canWrite() && [
    h("div", { class: "row" },
      button("Evaluate stable sample", () => run(driftSample(0)), { small: true }),
      button("Evaluate shifted sample", () => run(driftSample(0.9)), { small: true }),
      h("span", { class: "small muted", text: "Synthetic data generated in your browser." })),
    h("details", { class: "adv" }, h("summary", { text: "Evaluate your own data (JSON)" }),
      h("div", { class: "stack" }, custom, h("div", null, button("Evaluate", () => run(JSON.parse(custom.value)), { kind: "primary", small: true }))))];
  if (!item) return card("Drift", null, empty("Drift has not been evaluated", "Compare a reference sample with current data using PSI and the Kolmogorov-Smirnov test."), actions);
  const r = item.payload;
  const max = Math.max(0.5, ...r.features.map((f) => f.psi));
  const rows = r.features.map((f) => h("tr", null,
    h("td", null, h("div", { class: "title", text: f.feature }), h("div", { class: "small muted", text: `${f.kind} · n=${f.n_reference}/${f.n_current}` })),
    h("td", null, bar("PSI", f.psi, max, f.psi_level === "stable" ? "good" : f.psi_level === "moderate" ? "warn" : "bad", num(f.psi), r.psi_threshold)),
    h("td", { class: "mono", text: f.kind === "numeric" ? `${num(f.ks_statistic)} (p=${Number(f.ks_p_value).toExponential(1)})` : "—" }),
    h("td", null, badge(f.drift_detected ? "drift_detected" : "stable"))));
  return h("div", { class: "stack" },
    card("Drift", fmtTime(item.created_at),
      h("div", { class: "row" }, badge(item.status), h("span", { class: "muted", text: item.summary })),
      h("div", { class: "table-wrap" }, h("table", null,
        h("thead", null, h("tr", null, ["Feature", `Population stability index (threshold ${r.psi_threshold})`, "KS statistic", "Result"].map((t) => h("th", { text: t })))),
        h("tbody", null, rows)))),
    card("Run an evaluation", null, actions || h("p", { class: "muted", text: "Your role is read-only." })),
    h("p", { class: "notice", text: "PSI thresholds (0.1 moderate, 0.25 significant) are a rule of thumb. Tune them for your data and sample sizes." }));
}

function explainSample() {
  const names = ["income", "account_age", "utilisation", "recent_enquiries", "tenure"];
  const weights = [1.6, 0.4, -1.1, -0.7, 0.1];
  const X = Array.from({ length: 250 }, () => gaussian(names.length, 0, 1));
  const predictions = X.map((row) => +(1 / (1 + Math.exp(-row.reduce((sum, v, i) => sum + v * weights[i], 0)))).toFixed(4));
  return { feature_names: names, X, predictions };
}

function explainTab(ctx) {
  const item = ctx.evidence.explanation;
  const run = async (body) => {
    await api(`/models/${ctx.model.id}/explain`, { method: "POST", body });
    toast("Explanation generated");
    render();
  };
  const custom = h("textarea", { placeholder: '{"feature_names": ["a", "b"], "X": [[1, 2], [2, 1], [3, 5], [4, 2]], "predictions": [0.2, 0.4, 0.7, 0.6]}' });
  const actions = canWrite() && [
    h("div", { class: "row" }, button("Explain synthetic sample", () => run(explainSample()), { small: true }), h("span", { class: "small muted", text: "Recorded inputs and predictions; the model is not executed." })),
    h("details", { class: "adv" }, h("summary", { text: "Explain your own recorded predictions (JSON)" }),
      h("div", { class: "stack" }, custom, h("div", null, button("Explain", () => run(JSON.parse(custom.value)), { kind: "primary", small: true }))))];
  if (!item) return card("Explainability", null, empty("No explanation on record", "Fit a surrogate to recorded predictions to see which features drive the model's output."), actions);
  const r = item.payload;
  const max = Math.max(...r.features.map((f) => Math.abs(f.importance)), 1e-9);
  return h("div", { class: "stack" },
    card("Feature attribution", `${r.method.replace(/_/g, " ")} · ${fmtTime(item.created_at)}`,
      h("div", { class: "bars" }, r.features.map((f) => bar(f.feature, Math.abs(f.importance), max, f.coefficient < 0 ? "warn" : "info", num(f.importance)))),
      r.fidelity_r2 != null && h("div", { class: "legend" },
        h("span", null, h("i", { class: "c-info" }), "Raises the output"), h("span", null, h("i", { class: "c-warn" }), "Lowers the output"),
        h("span", { text: `Surrogate fidelity R² = ${num(r.fidelity_r2)} over ${r.n_samples} samples` }))),
    h("p", { class: "notice", text: r.notice }),
    card("Generate a new explanation", null, actions || h("p", { class: "muted", text: "Your role is read-only." })));
}

function governanceTab(ctx) {
  const item = ctx.evidence.policy_evaluation;
  const id = ctx.model.id;
  const evaluate = async () => {
    await api(`/models/${id}/risk`, { method: "POST" });
    const result = await api("/policies/evaluate", { method: "POST", body: { model_id: id } });
    toast(`Policies: ${result.summary.pass} passed, ${result.summary.fail} failed`);
    render();
  };
  const download = async () => {
    const text = await api(`/models/${id}/report.md`);
    const link = h("a", { href: URL.createObjectURL(new Blob([text], { type: "text/markdown" })), download: `${ctx.model.name}-${ctx.model.version}-governance-report.md` });
    link.click();
    URL.revokeObjectURL(link.href);
  };
  const actions = h("div", { class: "row" }, canWrite() && button("Assess risk & evaluate policies", evaluate, { kind: "primary" }), button("Download evidence report", download, { iconName: "download" }));
  if (!item) return card("Governance policies", null, empty("Policies have not been evaluated", "Each policy is an executable check that points at the evidence behind its result."), actions);
  const { summary, results } = item.payload;
  const rows = results.map((r) => h("tr", null,
    h("td", null, h("div", { class: "title", text: r.title }), h("div", { class: "small muted mono", text: `${r.policy_id} · ${r.category}` })),
    h("td", null, badge(r.status)),
    h("td", null, h("div", { text: r.explanation }), r.remediation && h("div", { class: "fix" }, h("strong", { text: "Fix: " }), r.remediation),
      r.evidence_refs.length ? h("div", { class: "small muted mono", text: "Evidence: " + r.evidence_refs.map((ref) => (ref.length > 30 ? short(ref, 24) : ref)).join(", ") }) : null)));
  return h("div", { class: "stack" },
    card("Governance policies", fmtTime(item.created_at),
      h("div", { class: "row" }, badge(summary.status), h("span", { class: "muted", text: `${summary.pass} passed · ${summary.fail} failed · ${summary.not_applicable} not applicable` }), h("span", { class: "spacer" }), actions),
      h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, ["Policy", "Status", "Explanation"].map((t) => h("th", { text: t })))), h("tbody", null, rows)))),
    h("p", { class: "notice", text: "Passing these policies does not constitute certification or regulatory compliance." }));
}

const STAGES = [["dataset", "Dataset"], ["transformation", "Transformation"], ["training_run", "Training run"], ["model_version", "Model version"], ["evaluation", "Evaluation"], ["deployment", "Deployment"]];

function lineageTab(ctx) {
  const lin = ctx.lineage;
  const graph = h("div", { class: "lineage" });
  STAGES.forEach(([type, label], index) => {
    const nodes = lin.nodes.filter((n) => n.node_type === type);
    const stage = h("div", { class: "stage" + (nodes.length ? "" : " vacant") }, h("div", { class: "stage-title", text: label }),
      nodes.length ? nodes.map((n) => h("div", { class: "node" + (n.id === lin.root ? " root" : "") },
        h("div", { class: "title", text: n.name }),
        h("div", { class: "small muted mono", text: n.fingerprint ? "sha256 " + short(n.fingerprint, 10) : "no fingerprint" }),
        h("div", { class: "small muted mono", text: n.id })))
        : h("div", { class: "node", text: "Not recorded" }));
    graph.append(stage);
    if (index < STAGES.length - 1) graph.append(h("div", { class: "chev", text: "›", "aria-hidden": "true" }));
  });

  const type = h("select", null, STAGES.filter(([t]) => t !== "model_version").map(([t, label]) => h("option", { value: t, text: label })));
  const name = h("input", { placeholder: "applications-2026Q3", required: true });
  const fingerprint = h("input", { class: "mono", placeholder: "Optional SHA-256" });
  const options = () => [h("option", { value: "", text: "— none —" }), ...lin.nodes.map((n) => h("option", { value: n.id, text: `${n.name} (${n.node_type})` }))];
  const from = h("select", null, options());
  const to = h("select", null, options());
  const form = h("form", { class: "stack" },
    h("div", { class: "form-grid" }, field("Step type", type), field("Name", name), field("Fingerprint", fingerprint), field("Receives input from", from), field("Feeds into", to)),
    h("div", null, h("button", { class: "btn primary sm", type: "submit" }, "Add step")));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const body = { node_type: type.value, name: name.value.trim() };
      if (fingerprint.value.trim()) body.fingerprint = fingerprint.value.trim();
      const node = await api("/lineage/nodes", { method: "POST", body });
      if (from.value) await api("/lineage/edges", { method: "POST", body: { src_id: from.value, dst_id: node.id } });
      if (to.value) await api("/lineage/edges", { method: "POST", body: { src_id: node.id, dst_id: to.value } });
      toast("Lineage step added");
      render();
    } catch (err) { toast(err.message, true); }
  });
  return h("div", { class: "stack" },
    card("Lineage", lin.lineage_digest ? `inputs digest ${short(lin.lineage_digest, 12)}` : "no upstream steps recorded", graph,
      h("p", { class: "small muted", text: lin.has_dataset ? "This model's lineage reaches a dataset. Only metadata and fingerprints are stored." : "No dataset is linked upstream of this model yet." })),
    canWrite() && card("Add a lineage step", "a step must link to something already shown to appear here", form));
}

function auditTab(ctx) {
  return card("Audit history", `${ctx.audit.length} events`, eventFeed(ctx.audit, false));
}

const TAB_VIEWS = { summary: summaryTab, security: securityTab, drift: driftTab, explain: explainTab, governance: governanceTab, lineage: lineageTab, audit: auditTab };

async function modelView(id, tab = "summary") {
  const [model, evidence, lineage, audit] = await Promise.all([api(`/models/${id}`), api(`/models/${id}/evidence`), api(`/models/${id}/lineage`), api(`/models/${id}/audit`)]);
  const ctx = { model, evidence, lineage, audit };
  const verify = async () => {
    const result = await api(`/models/${id}/verify`, { method: "POST", body: {} });
    toast(result.verified ? "Integrity verified: digest matches" : "Integrity FAILED: digest does not match", !result.verified);
    render();
  };
  const view = TAB_VIEWS[tab] || summaryTab;
  return h("div", null,
    h("div", { class: "crumb" }, h("a", { href: "#/models", text: "Models" }), " / ", model.name),
    h("div", { class: "page-head" },
      h("div", null, h("h1", { text: `${model.name} ` }, h("span", { class: "muted", text: `v${model.version}` })),
        h("p", { class: "row" }, tierBadge(model.impact_tier), h("span", { class: "badge plain", text: model.framework }), h("code", { class: "muted", text: "sha256 " + short(model.sha256, 16), title: model.sha256 }))),
      h("span", { class: "spacer" }),
      canWrite() && model.artifact_available && button("Verify integrity", verify, { iconName: "policies" })),
    h("nav", { class: "tabs", "aria-label": "Model sections" }, TABS.map(([key, label]) => h("a", { href: `#/models/${id}/${key}`, class: key === (TAB_VIEWS[tab] ? tab : "summary") ? "active" : "", text: label }))),
    view(ctx));
}

// ---------------------------------------------------------------- policies & audit

async function policiesView() {
  const policies = await api("/policies");
  const rows = policies.map((p) => h("tr", null,
    h("td", null, h("div", { class: "title", text: p.title }), h("div", { class: "small muted mono", text: p.id })),
    h("td", null, h("span", { class: "badge plain", text: p.category })),
    h("td", null, badge(p.severity)),
    h("td", null, h("div", { text: p.description }), p.applies_to_tiers && h("div", { class: "small muted", text: `Applies to ${p.applies_to_tiers.join(", ")} impact models` }))));
  return h("div", null, pageHead("Policies", "Governance requirements expressed as executable, version-controlled checks."),
    card(null, null, h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, ["Policy", "Category", "Severity", "Requirement"].map((t) => h("th", { text: t })))), h("tbody", null, rows)))),
    h("p", { class: "notice", text: "Policies are loaded from YAML. Set AIGUARD_POLICY_FILE to use your own set." }));
}

async function auditView() {
  const [events, chain] = await Promise.all([api("/audit?limit=300"), api("/audit/verify")]);
  const rows = events.map((e) => h("tr", null,
    h("td", { class: "mono muted", text: e.seq }), h("td", { class: "small", text: fmtTime(e.timestamp) }),
    h("td", null, h("div", { class: "title mono", text: e.action }), h("div", { class: "small muted", text: e.actor })),
    h("td", null, e.model_id ? h("a", { href: `#/models/${e.model_id}/audit`, class: "mono", text: e.model_id }) : h("span", { class: "muted", text: "—" })),
    h("td", null, badge(e.result)), h("td", { class: "mono muted", text: short(e.event_hash, 14), title: e.event_hash })));
  return h("div", { class: "stack" },
    pageHead("Audit trail", "Every action is appended to a hash chain; edits, deletions and reordering are detectable.", button("Verify chain", async () => { const r = await api("/audit/verify"); toast(r.valid ? `Chain verified: ${r.events_checked} events` : `Chain broken at event ${r.first_invalid_seq}`, !r.valid); })),
    h("div", { class: "grid kpis" },
      kpi("Chain status", chain.valid ? "Verified" : "Broken", chain.valid ? "All links recomputed" : chain.reason, chain.valid ? "good" : "bad"),
      kpi("Events checked", chain.events_checked, "since genesis", "info"),
      kpi("Head hash", short(chain.head_hash, 10), "anchor this value externally", "info")),
    card(null, null, events.length ? h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, ["#", "Time", "Action", "Model", "Result", "Event hash"].map((t) => h("th", { text: t })))), h("tbody", null, rows))) : empty("No events yet", "Events appear here as models are registered and assessed.")),
    h("p", { class: "notice", text: "A hash chain gives tamper evidence, not tamper prevention: someone with full database access could rewrite the whole chain. Store the head hash somewhere they cannot reach." }));
}

// ---------------------------------------------------------------- router

async function render() {
  const root = document.getElementById("app");
  const token = ++state.renderToken;
  if (!state.me) {
    if (state.key) {
      try { await signIn(state.key); } catch { state.key = ""; sessionStorage.removeItem("aiguard.key"); }
    }
    if (!state.me) { root.replaceChildren(loginView()); return; }
  }
  const [view = "overview", id, tab] = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const active = NAV.some(([key]) => key === view) ? view : "overview";
  if (!root.querySelector(".shell")) root.replaceChildren(shell(active, h("div", { class: "stack" }, h("div", { class: "skeleton" }), h("div", { class: "skeleton" }))));
  let content;
  try {
    if (active === "models") content = id ? await modelView(id, tab) : await modelsView();
    else if (active === "policies") content = await policiesView();
    else if (active === "audit") content = await auditView();
    else content = await overviewView();
  } catch (err) {
    content = card(null, null, empty("Something went wrong", err.message, h("a", { class: "btn", href: "#/overview" }, "Back to overview")));
  }
  if (token !== state.renderToken || !state.me) return;
  const scroll = window.scrollY;
  root.replaceChildren(shell(active, content));
  window.scrollTo(0, state.lastHash === location.hash ? scroll : 0);
  state.lastHash = location.hash;
}

window.addEventListener("hashchange", render);
render();

"use strict";

/* AIGuard dashboard. Plain JavaScript, no build step, no third-party code.
   All API data is inserted with textContent; innerHTML is used only for the
   constant SVG strings below. */

const state = { key: sessionStorage.getItem("aiguard.key") || "", me: null, renderToken: 0, lastHash: "" };

const svg = (body) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
const ICONS = {
  overview: svg('<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>'),
  models: svg('<path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z"/><path d="m3 7 9 5 9-5M12 12v10"/>'),
  policies: svg('<path d="M9 11.5l2 2 4-4"/><path d="M12 2 4 5v6c0 5 3.4 9.3 8 11 4.6-1.7 8-6 8-11V5l-8-3Z"/>'),
  audit: svg('<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r="1"/><circle cx="3.5" cy="12" r="1"/><circle cx="3.5" cy="18" r="1"/>'),
  guide: svg('<path d="M5 3l14 9-14 9V3Z"/>'),
  plus: svg('<path d="M12 5v14M5 12h14"/>'),
  download: svg('<path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16"/>'),
  logout: svg('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>'),
  sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  moon: svg('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>'),
  search: svg('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
  alert: svg('<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>'),
  check: svg('<path d="M20 6 9 17l-5-5"/>'),
  x: svg('<path d="M18 6 6 18M6 6l12 12"/>'),
  arrow: svg('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  chevron: svg('<path d="m9 6 6 6-6 6"/>'),
  info: svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'),
  fingerprint: svg('<path d="M12 11v4a6 6 0 0 1-1 3.3M8 11a4 4 0 0 1 8 0v2a10 10 0 0 1-1.2 4.8M5 14v-3a7 7 0 0 1 12.6-4.2M19 11v2M4.6 18a8 8 0 0 0 .4-2"/>'),
  activity: svg('<path d="M3 12h4l3-8 4 16 3-8h4"/>'),
  sparkles: svg('<path d="M12 3l1.8 4.9L18.7 9.7l-4.9 1.8L12 16.4l-1.8-4.9L5.3 9.7l4.9-1.8L12 3Z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/>'),
  share: svg('<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="m8.2 10.9 7.6-3.8M8.2 13.1l7.6 3.8"/>'),
  terminal: svg('<path d="m5 8 4 4-4 4M12 16h7"/><rect x="2" y="3" width="20" height="18" rx="3"/>'),
  code: svg('<path d="m8 8-5 4 5 4M16 8l5 4-5 4M14 4l-4 16"/>'),
  globe: svg('<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>'),
  rocket: svg('<path d="M5 15c-1 1-1.5 4-1.5 4s3-.5 4-1.5M14 4c3-1.5 6-1 6-1s.5 3-1 6l-7 8-4-4 6-9Z"/><circle cx="15" cy="9" r="1.5"/>'),
  copy: svg('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>'),
  book: svg('<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5Z"/><path d="M19 19v2H6"/>'),
  play: svg('<path d="M6 4l14 8-14 8V4Z"/>'),
  brand:
    '<svg viewBox="0 0 32 32" aria-hidden="true"><defs><linearGradient id="brandGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7c8cff"/><stop offset="1" stop-color="#22d3ee"/></linearGradient></defs><path d="M16 2 4 6.5v8.6c0 7.1 4.9 12.6 12 14.9 7.1-2.3 12-7.8 12-14.9V6.5L16 2Z" fill="url(#brandGrad)"/><path d="m10.5 16.2 3.8 3.8 7.4-8" fill="none" stroke="#060a14" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
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

function s(tag, attrs, ...children) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs || {})) if (value != null) el.setAttribute(key, value);
  for (const child of children.flat()) if (child) el.append(child);
  return el;
}

function icon(name) {
  const holder = document.createElement("span");
  holder.innerHTML = ICONS[name] || ICONS.info;
  return holder.firstChild;
}

function bubble(name, tone) {
  return h("span", { class: `bubble ${tone ? "t-" + tone : ""}` }, icon(name));
}

function toast(message, isError = false) {
  const el = h("div", { class: "toast" + (isError ? " error" : "") }, icon(isError ? "alert" : "check"), h("span", { text: message }));
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), isError ? 7000 : 3500);
}

function errorText(data) {
  const detail = data && data.detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  return typeof detail === "string" ? detail : "Request failed";
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { "X-API-Key": state.key };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch("/api/v1" + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
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

function timeAgo(iso) {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return `${Math.floor(seconds / 86400)} d ago`;
}

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
    title && h("div", { class: "card-head" }, h("h2", { text: title }), h("span", { class: "spacer" }), hint && h("span", { class: "hint", text: hint })),
    ...body);
}

function empty(iconName, title, text, action) {
  return h("div", { class: "empty" }, bubble(iconName, "info"), h("h3", { text: title }), h("p", { text }), action);
}

function notice(text) {
  return h("p", { class: "notice" }, icon("info"), h("span", { text }));
}

function bar(name, value, max, tone, valueText, mark) {
  const fill = h("div", { class: `bar-fill t-${tone}`, "data-w": value > 0 ? Math.max(1.5, Math.min(100, pct(value, max))) + "%" : "0%" });
  const track = h("div", { class: "bar-track" }, fill);
  if (mark != null) {
    const marker = h("div", { class: "bar-mark", title: "Threshold" });
    marker.style.left = Math.min(100, pct(mark, max)) + "%";
    track.append(marker);
  }
  return h("div", { class: "bar-row" }, h("div", { class: "name", text: name, title: name }), track, h("div", { class: "val", text: valueText }));
}

function ring(fraction, tone, { size = 150, stroke = 12, big, small, cls = "" } = {}) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, mid = size / 2;
  const value = s("circle", { class: `ring-val t-${tone}`, cx: mid, cy: mid, r, fill: "none", "stroke-width": stroke, "stroke-linecap": "round", "stroke-dasharray": c, transform: `rotate(-90 ${mid} ${mid})`, "data-off": c * (1 - Math.max(0, Math.min(1, fraction))) });
  value.style.strokeDashoffset = c;
  const wrap = h("div", { class: `ring ${cls}` },
    s("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: "img", "aria-label": `${Math.round(fraction * 100)} percent` },
      s("circle", { class: "ring-track", cx: mid, cy: mid, r, fill: "none", "stroke-width": stroke }), value),
    h("div", { class: "ring-center" }, big != null && h("div", { class: "ring-big", text: big }), small && h("div", { class: "ring-small", text: small })));
  wrap.style.width = wrap.style.height = size + "px";
  return wrap;
}

function donut(segments, total, centerBig, centerSmall) {
  const size = 150, stroke = 16, r = (size - stroke) / 2, c = 2 * Math.PI * r, mid = size / 2;
  const svgEl = s("svg", { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: "img", "aria-label": "Distribution" },
    s("circle", { class: "ring-track", cx: mid, cy: mid, r, fill: "none", "stroke-width": stroke }));
  let offset = 0;
  for (const [count, tone] of segments) {
    if (!count) continue;
    const length = (c * count) / total;
    svgEl.append(s("circle", { class: `seg t-${tone}`, cx: mid, cy: mid, r, fill: "none", "stroke-width": stroke, "stroke-dasharray": `${Math.max(0, length - 3)} ${c - Math.max(0, length - 3)}`, "stroke-dashoffset": -offset, transform: `rotate(-90 ${mid} ${mid})` }));
    offset += length;
  }
  const wrap = h("div", { class: "ring md" }, svgEl, h("div", { class: "ring-center" }, h("div", { class: "ring-big", text: centerBig }), h("div", { class: "ring-small", text: centerSmall })));
  wrap.style.width = wrap.style.height = size + "px";
  return wrap;
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

function animateIn(root) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    root.querySelectorAll("[data-w]").forEach((el) => (el.style.width = el.dataset.w));
    root.querySelectorAll("[data-off]").forEach((el) => (el.style.strokeDashoffset = el.dataset.off));
  }));
}

// ---------------------------------------------------------------- posture model

const CHECKS = [
  ["integrity", "Integrity", "pass", ""],
  ["security", "Security", "pass", "security"],
  ["drift", "Drift", "stable", "drift"],
  ["explanation", "Explain", "generated", "explain"],
  ["policy", "Policies", "pass", "governance"],
];
const checkState = (posture, key, good) => (posture[key] == null ? "none" : posture[key] === good ? "good" : "bad");
const passing = (posture) => CHECKS.filter(([key, , good]) => posture[key] === good).length;
const scoreTone = (fraction) => (fraction >= 0.8 ? "good" : fraction >= 0.5 ? "warn" : "bad");

function pipeline(posture) {
  return h("div", { class: "pipeline" }, CHECKS.map(([key, label, good]) => {
    const st = checkState(posture, key, good);
    return h("div", { class: `pipe ${st}`, title: `${label}: ${posture[key] ? LABEL[posture[key]] || posture[key] : "not run"}` }, h("i"), h("span", { text: label }));
  }));
}

function attention(models) {
  const items = [];
  for (const m of models) {
    const p = m.posture, base = `#/models/${m.id}`;
    if (p.security === "fail") items.push([0, "alert", "bad", m, "Security findings need review", `${base}/security`]);
    if (p.integrity === "fail") items.push([0, "fingerprint", "bad", m, "File no longer matches its fingerprint", base]);
    if (p.drift === "drift_detected") items.push([1, "activity", "warn", m, "Data drift detected", `${base}/drift`]);
    if (p.policy === "fail") items.push([2, "policies", "warn", m, "Governance policies failing", `${base}/governance`]);
    if (p.integrity == null) items.push([3, "fingerprint", "muted", m, "Integrity not verified yet", base]);
    if (p.security == null) items.push([3, "policies", "muted", m, "No security assessment yet", `${base}/security`]);
  }
  return items.sort((a, b) => a[0] - b[0]).slice(0, 6);
}

// ---------------------------------------------------------------- theme & session

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("aiguard.theme", theme); } catch { /* storage unavailable */ }
}
function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem("aiguard.theme"); } catch { /* storage unavailable */ }
  document.documentElement.dataset.theme = saved || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
}
const currentTheme = () => document.documentElement.dataset.theme;

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

function brandMark(tag, href, tagline) {
  const el = h(tag, { class: "brand", href });
  el.innerHTML = ICONS.brand;
  el.append(h("div", null, h("div", { class: "brand-name", text: "AIGuard" }), h("div", { class: "brand-tag", text: tagline })));
  return el;
}

function loginView() {
  const input = h("input", { type: "password", name: "key", autocomplete: "off", required: true, placeholder: "Paste your API key" });
  const error = h("p", { class: "small login-error", role: "alert" });
  const form = h("form", { class: "stack" }, h("label", null, "API key", input), error,
    h("button", { class: "btn primary block", type: "submit" }, "Sign in", icon("arrow")));
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.textContent = "";
    try { await signIn(input.value.trim()); if (!location.hash) location.hash = "#/overview"; render(); }
    catch { state.key = ""; error.textContent = "That key was not accepted."; }
  });
  const feature = (iconName, title, text) => h("div", { class: "feature" }, bubble(iconName), h("div", null, h("h3", { text: title }), h("p", { text })));
  return h("div", { class: "login" },
    h("div", { class: "pitch" },
      brandMark("div", null, "AI model governance & security"),
      h("div", { class: "stack" },
        h("h1", null, "Know what you ", h("span", { class: "grad-text", text: "deploy." })),
        h("p", { class: "lead", text: "One place to check that a model is safe to load, unchanged, still seeing the data it was trained on, explainable, and ready for production." })),
      h("div", { class: "features" },
        feature("policies", "Scan before you load", "Finds hidden code in model files without ever running them."),
        feature("fingerprint", "Catch every change", "Fingerprints each model version and flags any modification."),
        feature("activity", "Watch for drift", "Compares live data with training data, feature by feature."),
        feature("audit", "Evidence you can show", "Policy results backed by a tamper-evident audit trail."))),
    h("div", { class: "login-side" },
      h("div", { class: "card login-card" },
        h("div", null, h("h2", { text: "Sign in" }), h("p", { class: "muted", text: "Use an API key. It stays in this browser tab only." })),
        form,
        h("p", { class: "small faint" }, "No key yet? Start the server with ", h("code", { text: "aiguard serve" }), " and copy the temporary admin key it prints."))));
}

// ---------------------------------------------------------------- shell

const NAV = [["overview", "Overview"], ["models", "Models"], ["policies", "Policies"], ["audit", "Audit trail"], ["guide", "Get started"]];

function shell(active, content, summary) {
  const link = ([id, label]) => h("a", { href: `#/${id}`, class: id === active ? "active" : "", "aria-current": id === active ? "page" : null },
    icon(id), h("span", { text: label }), id === "models" && summary && summary.models != null && h("span", { class: "count", text: summary.models }));
  const me = state.me;
  const themeBtn = h("button", { class: "icon-btn", type: "button", title: "Switch theme", "aria-label": "Switch theme" }, icon(currentTheme() === "dark" ? "sun" : "moon"));
  themeBtn.addEventListener("click", () => { applyTheme(currentTheme() === "dark" ? "light" : "dark"); themeBtn.replaceChildren(icon(currentTheme() === "dark" ? "sun" : "moon")); });
  const out = h("button", { class: "icon-btn", type: "button", title: "Sign out", "aria-label": "Sign out" }, icon("logout"));
  out.addEventListener("click", signOut);
  const chain = summary && summary.chainValid != null && h("a", { class: "chain-pill", href: "#/audit" },
    h("span", { class: "pulse" + (summary.chainValid ? "" : " bad") }), summary.chainValid ? "Audit chain verified" : "Audit chain broken");
  return h("div", { class: "shell" },
    h("aside", { class: "sidebar" },
      brandMark("a", "#/overview", "Governance & security"),
      h("nav", { class: "nav", "aria-label": "Main" }, h("div", { class: "eyebrow nav-label", text: "Workspace" }), NAV.slice(0, 4).map(link),
        h("div", { class: "eyebrow nav-label", text: "Help" }), link(NAV[4]),
        h("a", { href: "/api/docs", target: "_blank", rel: "noopener" }, icon("book"), h("span", { text: "API docs" }))),
      h("div", { class: "side-foot" }, chain,
        h("div", { class: "user-chip" }, h("div", { class: "avatar", text: me.name.slice(0, 2).toUpperCase() }),
          h("div", { class: "who" }, h("div", { class: "title", text: me.name }), h("div", { class: "small faint", text: `${me.role} · v${me.version}` })),
          themeBtn, out))),
    h("main", { class: "main" }, content));
}

function pageHead(title, subtitle, ...actions) {
  return h("div", { class: "page-head" }, h("div", null, h("h1", { text: title }), subtitle && h("p", { text: subtitle })), h("span", { class: "spacer" }), h("div", { class: "row" }, ...actions));
}

// ---------------------------------------------------------------- overview

const RISK_ORDER = [["low", "good", "Low"], ["medium", "warn", "Medium"], ["high", "bad", "High"], ["critical", "crit", "Critical"], ["unassessed", "muted", "Unassessed"]];
const SEVERITIES = [["critical", "crit"], ["high", "bad"], ["medium", "warn"], ["low", "info"], ["info", "muted"]];
const CATEGORY_ICON = { registry: "models", integrity: "fingerprint", security: "policies", monitoring: "activity", explainability: "sparkles", governance: "audit", provenance: "share" };

function stat(iconName, label, value, sub, tone) {
  return h("div", { class: `stat t-${tone}` }, h("div", { class: "stat-top" }, icon(iconName), label), h("div", { class: "stat-value", text: value }), h("div", { class: "stat-sub", text: sub }));
}

function eventFeed(events, names = {}) {
  if (!events.length) return h("p", { class: "muted", text: "No events yet." });
  return h("div", { class: "feed" }, events.map((e) => h("div", { class: "feed-item" },
    bubble(CATEGORY_ICON[e.category] || "info", TONE[e.result] || "info"),
    h("div", null,
      h("div", { class: "row" }, h("span", { class: "title mono", text: e.action }), badge(e.result)),
      h("div", { class: "small faint", text: [names[e.model_id], e.actor, short(e.event_hash, 10)].filter(Boolean).join(" · ") })),
    h("div", { class: "small faint", text: timeAgo(e.timestamp), title: fmtTime(e.timestamp) }))));
}

function modelCard(m) {
  const done = passing(m.posture), fraction = done / CHECKS.length;
  return h("a", { class: "card model-card", href: `#/models/${m.id}` },
    h("div", { class: "top" },
      ring(fraction, scoreTone(fraction), { size: 58, stroke: 6, big: `${done}/${CHECKS.length}`, cls: "sm" }),
      h("div", null, h("div", { class: "name", text: m.name }), h("div", { class: "small faint", text: `v${m.version} · ${m.framework}` })),
      h("span", { class: "spacer" }),
      m.posture.risk_level ? badge(m.posture.risk_level) : null),
    pipeline(m.posture),
    h("div", { class: "row small" }, tierBadge(m.impact_tier), h("span", { class: "spacer" }), h("span", { class: "faint", text: m.posture.risk_score != null ? `risk ${m.posture.risk_score}/100` : "risk not assessed" })));
}

async function overviewView() {
  const [st, models] = await Promise.all([api("/stats"), api("/models")]);
  if (!models.length) {
    return h("div", { class: "stack" },
      h("section", { class: "card hero" }, h("div", { class: "stack" },
        h("div", null, h("div", { class: "eyebrow", text: "Welcome" }), h("h1", null, "Let's check your ", h("span", { class: "grad-text", text: "first model." })),
          h("p", { text: "Register a model to fingerprint it, scan it for hidden code, and start collecting governance evidence." })),
        h("div", { class: "row actions" }, canWrite() && button("Register a model", registerDialog, { kind: "primary", iconName: "plus" }), h("a", { class: "btn", href: "#/guide" }, icon("guide"), "How to run AIGuard")),
        h("p", { class: "small faint" }, "Want sample data? Run ", h("code", { text: "aiguard seed-demo" }), " and refresh."))));
  }
  const total = models.length * CHECKS.length;
  const done = models.reduce((sum, m) => sum + passing(m.posture), 0);
  const fraction = done / total;
  const blocking = st.open_findings.high + st.open_findings.critical;
  const compliant = st.policy.pass || 0;
  const names = Object.fromEntries(models.map((m) => [m.id, m.name]));
  const todos = attention(models);
  const maxFinding = Math.max(1, ...Object.values(st.open_findings));
  const headline = fraction >= 0.8 ? "Your models are in good shape." : todos.length ? `${todos.length} thing${todos.length > 1 ? "s" : ""} need your attention.` : "Evidence is still being collected.";

  return h("div", { class: "stack" },
    h("section", { class: "card hero" }, h("div", { class: "hero-grid" },
      ring(fraction, scoreTone(fraction), { size: 168, stroke: 14, big: `${Math.round(fraction * 100)}%`, small: "checks passing" }),
      h("div", null, h("div", { class: "eyebrow", text: "Governance posture" }), h("h1", { text: headline }),
        h("p", { text: `${done} of ${total} checks are passing across ${models.length} model${models.length > 1 ? "s" : ""}: integrity, security, drift, explainability and policies.` }),
        h("div", { class: "row actions" }, h("a", { class: "btn primary", href: "#/models" }, "View models", icon("arrow")), h("a", { class: "btn", href: "#/guide" }, icon("guide"), "How to run AIGuard"))))),
    h("div", { class: "grid stats" },
      stat("models", "Models", models.length, `${st.policies_defined} policies defined`, "info"),
      stat("policies", "Fully compliant", `${compliant}/${models.length}`, compliant === models.length ? "All policies pass" : `${models.length - compliant} with failing policies`, compliant === models.length ? "good" : "warn"),
      stat("alert", "High & critical findings", blocking, blocking ? "Open in latest assessments" : "None open", blocking ? "bad" : "good"),
      stat("activity", "Models with drift", st.models_with_drift, st.models_with_drift ? "Data has shifted" : "Data looks stable", st.models_with_drift ? "warn" : "good"),
      stat("fingerprint", "Audit chain", st.audit_chain.valid ? "Verified" : "Broken", `${st.audit_events} events`, st.audit_chain.valid ? "good" : "bad")),
    h("div", null, h("div", { class: "card-head" }, h("h2", { text: "Models" }), h("span", { class: "spacer" }), h("a", { class: "small", href: "#/models", text: "See all" })),
      h("div", { class: "grid three" }, models.slice(0, 6).map(modelCard))),
    h("div", { class: "grid two" },
      card("Needs attention", todos.length ? `${todos.length} item${todos.length > 1 ? "s" : ""}` : null,
        todos.length ? h("div", { class: "stack tight" }, todos.map(([, iconName, tone, m, text, href]) => h("a", { class: "todo", href }, bubble(iconName, tone),
          h("div", null, h("div", { class: "title", text }), h("div", { class: "small faint", text: `${m.name} v${m.version}` })), h("span", { class: "go" }, icon("chevron")))))
          : empty("check", "Nothing needs attention", "Every model has passing checks.")),
      h("div", { class: "stack" },
        card("Risk levels", `${models.length} models`, h("div", { class: "donut-wrap" },
          donut(RISK_ORDER.map(([level, tone]) => [st.risk_levels[level] || 0, tone]), models.length, models.length, "models"),
          h("div", { class: "legend" }, RISK_ORDER.filter(([level]) => st.risk_levels[level]).map(([level, tone, label]) => h("div", { class: `t-${tone}` }, h("span", { class: "sw" }), label, h("b", { text: st.risk_levels[level] })))))),
        card("Open findings by severity", "latest assessment per model", h("div", { class: "bars" }, SEVERITIES.map(([sev, tone]) => bar(LABEL[sev], st.open_findings[sev], maxFinding, tone, st.open_findings[sev])))))),
    card("Recent activity", "audit trail", h("div", { class: "split-feed" }, eventFeed(st.recent_events.slice(0, 8), names))));
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
    h("div", null, h("h2", { text: "Register a model" }), h("p", { class: "muted small", text: "Give a file name inside the server's artifact folder, or a SHA-256 fingerprint you computed yourself." })),
    h("div", { class: "form-grid" },
      field("Name", f.name), field("Version", f.version), field("Framework", f.framework), field("Owner", f.owner),
      field("Artifact file", f.artifact_path), field("SHA-256 fingerprint", f.sha256), field("Impact tier", f.impact_tier),
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
  if (!models.length) return h("div", null, head, card(null, null, empty("models", "No models registered", "Register a model version to record its fingerprint and begin collecting evidence.", h("a", { class: "btn", href: "#/guide" }, "How to run AIGuard"))));

  const tbody = h("tbody");
  const count = h("span", { class: "small faint" });
  let query = "", filter = "all";
  const draw = () => {
    const shown = models.filter((m) => {
      const done = passing(m.posture) === CHECKS.length;
      if (filter === "attention" && done) return false;
      if (filter === "compliant" && !done) return false;
      return !query || `${m.name} ${m.version} ${m.framework} ${m.owner}`.toLowerCase().includes(query);
    });
    count.textContent = `${shown.length} of ${models.length}`;
    tbody.replaceChildren(...(shown.length ? shown.map(row) : [h("tr", null, h("td", { colspan: "7" }, h("p", { class: "muted", text: "No models match." })))]));
    animateIn(tbody);
  };
  const row = (m) => {
    const p = m.posture, done = passing(p), fraction = done / CHECKS.length;
    const tr = h("tr", { class: "link", tabindex: "0" },
      h("td", null, h("div", { class: "cell-model" }, ring(fraction, scoreTone(fraction), { size: 40, stroke: 5, big: done, cls: "sm" }),
        h("div", null, h("div", { class: "title", text: m.name }), h("div", { class: "small faint", text: `v${m.version} · ${m.framework}` })))),
      h("td", null, tierBadge(m.impact_tier)),
      h("td", null, badge(p.integrity, "Unverified")), h("td", null, badge(p.security)), h("td", null, badge(p.drift)), h("td", null, badge(p.policy)),
      h("td", null, p.risk_level ? h("span", { class: "row" }, badge(p.risk_level), h("span", { class: "small faint", text: p.risk_score })) : badge(null, "Unassessed")));
    const open = () => (location.hash = `#/models/${m.id}`);
    tr.addEventListener("click", open);
    tr.addEventListener("keydown", (e) => e.key === "Enter" && open());
    return tr;
  };
  const search = h("input", { type: "search", placeholder: "Search models", "aria-label": "Search models" });
  search.addEventListener("input", () => { query = search.value.trim().toLowerCase(); draw(); });
  const seg = h("div", { class: "segmented", role: "tablist" }, [["all", "All"], ["attention", "Needs attention"], ["compliant", "All checks pass"]].map(([key, label]) => {
    const b = h("button", { type: "button", class: key === filter ? "on" : "", text: label });
    b.addEventListener("click", () => { filter = key; seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b)); draw(); });
    return b;
  }));
  draw();
  return h("div", null, head,
    h("div", { class: "toolbar" }, h("div", { class: "search" }, icon("search"), search), seg, h("span", { class: "spacer" }), count),
    h("section", { class: "card flush" }, h("div", { class: "table-wrap" }, h("table", null,
      h("thead", null, h("tr", null, ["Model", "Impact", "Integrity", "Security", "Drift", "Policies", "Risk"].map((t) => h("th", { text: t })))), tbody))));
}

// ---------------------------------------------------------------- model detail

const TABS = [["summary", "Summary"], ["security", "Security", "security", "pass"], ["drift", "Drift", "drift", "stable"], ["explain", "Explainability", "explanation", "generated"], ["governance", "Governance", "policy", "pass"], ["lineage", "Lineage"], ["audit", "Audit"]];
const CONTROLS = [
  ["authentication_enabled", "Authentication enabled", true], ["tls_enabled", "TLS enabled", true],
  ["integrity_check_on_load", "Integrity check on load", true], ["rate_limiting_enabled", "Rate limiting enabled", true],
  ["input_validation_enabled", "Input validation enabled", true], ["egress_restricted", "Egress restricted", true],
  ["allow_pickle", "Accepts pickle artifacts", false], ["debug_mode", "Debug mode on", false], ["runs_as_root", "Runs as root", false],
];

function summaryTab(ctx) {
  const { model: m, evidence: ev } = ctx;
  const risk = ev.risk_assessment && ev.risk_assessment.payload;
  const meta = [["Owner", m.owner || "Not recorded"], ["Description", m.description || "Not recorded"], ["Intended use", m.intended_use || "Not recorded"], ["Human oversight", m.human_oversight || "Not recorded"],
    ["SHA-256", h("code", { text: m.sha256 })], ["Artifact", m.artifact_available ? `Registered file (${(m.size_bytes / 1024).toFixed(1)} KB)` : "Fingerprint only"], ["Registered", `${fmtTime(m.created_at)} by ${m.created_by}`]];
  const checks = CHECKS.map(([key, label, good, tab]) => {
    const st = checkState(m.posture, key, good);
    return h("a", { class: "todo", href: `#/models/${m.id}${tab ? "/" + tab : ""}` }, bubble(st === "good" ? "check" : st === "bad" ? "x" : "info", st === "good" ? "good" : st === "bad" ? "bad" : "muted"),
      h("div", null, h("div", { class: "title", text: label === "Explain" ? "Explainability" : label }), h("div", { class: "small faint", text: ev[key === "policy" ? "policy_evaluation" : key === "security" ? "security_assessment" : key] ? ev[key === "policy" ? "policy_evaluation" : key === "security" ? "security_assessment" : key].summary : "Not run yet" })),
      badge(m.posture[key]));
  });
  return h("div", { class: "stack" },
    h("div", { class: "grid two" },
      card("Checks", "latest evidence of each kind", h("div", { class: "stack tight" }, checks)),
      card("Risk", risk ? fmtTime(ev.risk_assessment.created_at) : null,
        risk ? [h("div", { class: "donut-wrap" }, ring(risk.score / 100, TONE[risk.level] || "info", { size: 120, stroke: 11, big: risk.score, small: "of 100", cls: "md" }),
          h("div", null, badge(risk.level), h("p", { class: "small faint", text: "Indicative score from recorded evidence." }))),
          h("div", { class: "bars" }, risk.factors.map((f) => bar(f.factor, f.points, f.max_points, f.points ? (f.points / f.max_points > 0.6 ? "bad" : "warn") : "good", `${f.points}/${f.max_points}`)))]
          : empty("activity", "Not assessed", "Run all checks to score this model from its evidence."))),
    card("Details", null, h("dl", { class: "meta" }, meta.map(([k, v]) => [h("dt", { text: k }), h("dd", null, v)]))));
}

function findingCard(f) {
  return h("div", { class: `finding sev-${f.severity}` },
    h("div", { class: "row" }, badge(f.severity), h("strong", { text: f.title }), h("span", { class: "spacer" }), h("code", { class: "faint", text: f.id })),
    h("p", { text: f.description }),
    h("div", { class: "fix" }, h("strong", { text: "Fix: " }), f.recommendation),
    (f.reference || f.location) && h("p", { class: "small faint", text: [f.location && `Location: ${f.location}`, f.reference].filter(Boolean).join(" · ") }));
}

function securityTab(ctx) {
  const item = ctx.evidence.security_assessment;
  const boxes = CONTROLS.map(([key, , secure]) => [key, h("input", { type: "checkbox", checked: secure })]);
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
  const order = SEVERITIES.map(([sev]) => sev);
  const findings = item ? [...item.payload.findings].sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity)) : [];
  const options = canWrite() && h("details", { class: "adv" }, h("summary", { text: "Assessment options" }),
    h("div", { class: "stack" },
      h("div", { class: "checks" }, h("label", null, include, "Include the deployment controls below")),
      h("div", { class: "checks" }, boxes.map(([, el], i) => h("label", null, el, CONTROLS[i][1]))),
      field("Dependencies (optional)", reqs)));
  return h("div", { class: "stack" },
    card("Security assessment", item ? `${fmtTime(item.created_at)} · format: ${item.payload.artifact_format || "n/a"}` : null,
      item ? [h("div", { class: "row" }, badge(item.status), h("span", { class: "muted", text: item.summary }), h("span", { class: "spacer" }), canWrite() && button("Run again", run, { kind: "primary", iconName: "play" })),
        h("div", { class: "row" }, SEVERITIES.filter(([sev]) => item.payload.counts[sev]).map(([sev, tone]) => h("span", { class: `chip-count t-${tone}` }, h("span", { class: "sw" }), LABEL[sev], h("b", { text: item.payload.counts[sev] }))))]
        : empty("policies", "No assessment yet", "The file is inspected as bytes. It is never loaded or executed.", canWrite() && button("Run assessment", run, { kind: "primary", iconName: "play" })),
      options),
    findings.length ? h("div", { class: "stack" }, findings.map(findingCard)) : null,
    item && notice(item.payload.notice));
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
      button("Try a stable sample", () => run(driftSample(0)), { small: true, iconName: "play" }),
      button("Try a shifted sample", () => run(driftSample(0.9)), { small: true, iconName: "play" }),
      h("span", { class: "small faint", text: "Synthetic data generated in your browser." })),
    h("details", { class: "adv" }, h("summary", { text: "Evaluate your own data (JSON)" }),
      h("div", { class: "stack" }, custom, h("div", null, button("Evaluate", () => run(JSON.parse(custom.value)), { kind: "primary", small: true }))))];
  if (!item) return card("Drift", null, empty("activity", "Drift has not been evaluated", "Compare a reference sample with current data using PSI and the Kolmogorov-Smirnov test."), actions);
  const r = item.payload;
  const max = Math.max(0.5, ...r.features.map((f) => f.psi));
  const rows = r.features.map((f) => h("tr", null,
    h("td", null, h("div", { class: "title", text: f.feature }), h("div", { class: "small faint", text: `${f.kind} · n=${f.n_reference}/${f.n_current}` })),
    h("td", null, bar("PSI", f.psi, max, f.psi_level === "stable" ? "good" : f.psi_level === "moderate" ? "warn" : "bad", num(f.psi), r.psi_threshold)),
    h("td", { class: "mono muted", text: f.kind === "numeric" ? `${num(f.ks_statistic)} (p=${Number(f.ks_p_value).toExponential(1)})` : "—" }),
    h("td", null, badge(f.drift_detected ? "drift_detected" : "stable"))));
  return h("div", { class: "stack" },
    card("Drift", fmtTime(item.created_at),
      h("div", { class: "row" }, badge(item.status), h("span", { class: "muted", text: item.summary })),
      h("div", { class: "table-wrap" }, h("table", null,
        h("thead", null, h("tr", null, ["Feature", `Population stability index (threshold ${r.psi_threshold})`, "KS statistic", "Result"].map((t) => h("th", { text: t })))),
        h("tbody", null, rows)))),
    card("Run an evaluation", null, actions || h("p", { class: "muted", text: "Your role is read-only." })),
    notice("PSI thresholds (0.1 moderate, 0.25 significant) are a rule of thumb. Tune them for your data and sample sizes."));
}

function explainSample() {
  const names = ["income", "account_age", "utilisation", "recent_enquiries", "tenure"];
  const weights = [1.6, 0.4, -1.1, -0.7, 0.1];
  const X = Array.from({ length: 250 }, () => gaussian(names.length, 0, 1));
  const predictions = X.map((r) => +(1 / (1 + Math.exp(-r.reduce((sum, v, i) => sum + v * weights[i], 0)))).toFixed(4));
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
    h("div", { class: "row" }, button("Try a synthetic sample", () => run(explainSample()), { small: true, iconName: "play" }), h("span", { class: "small faint", text: "Uses recorded inputs and predictions; the model is not executed." })),
    h("details", { class: "adv" }, h("summary", { text: "Explain your own recorded predictions (JSON)" }),
      h("div", { class: "stack" }, custom, h("div", null, button("Explain", () => run(JSON.parse(custom.value)), { kind: "primary", small: true }))))];
  if (!item) return card("Explainability", null, empty("sparkles", "No explanation on record", "Fit a surrogate to recorded predictions to see which features drive the model's output."), actions);
  const r = item.payload;
  const max = Math.max(...r.features.map((f) => Math.abs(f.importance)), 1e-9);
  return h("div", { class: "stack" },
    card("What drives this model", `${r.method.replace(/_/g, " ")} · ${fmtTime(item.created_at)}`,
      h("div", { class: "bars" }, r.features.map((f) => bar(f.feature, Math.abs(f.importance), max, f.coefficient < 0 ? "warn" : "info", num(f.importance)))),
      r.fidelity_r2 != null && h("div", { class: "legend inline" },
        h("div", { class: "t-info" }, h("span", { class: "sw" }), "Raises the output"), h("div", { class: "t-warn" }, h("span", { class: "sw" }), "Lowers the output"),
        h("div", null, `Surrogate fidelity R² = ${num(r.fidelity_r2)} over ${r.n_samples} samples`))),
    notice(r.notice),
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
  const actions = h("div", { class: "row" }, canWrite() && button("Evaluate policies", evaluate, { kind: "primary", iconName: "play" }), button("Download report", download, { iconName: "download" }));
  if (!item) return card("Governance policies", null, empty("audit", "Policies have not been evaluated", "Each policy is an executable check that points at the evidence behind its result."), h("div", { class: "row" }, h("span", { class: "spacer" }), actions, h("span", { class: "spacer" })));
  const { summary, results } = item.payload;
  const applicable = summary.total - summary.not_applicable;
  const rows = results.map((r) => h("tr", null,
    h("td", null, h("div", { class: "title", text: r.title }), h("div", { class: "small faint mono", text: `${r.policy_id} · ${r.category}` })),
    h("td", null, badge(r.status)),
    h("td", null, h("div", { text: r.explanation }), r.remediation && h("div", { class: "fix" }, h("strong", { text: "Fix: " }), r.remediation),
      r.evidence_refs.length ? h("div", { class: "small faint mono", text: "Evidence: " + r.evidence_refs.map((ref) => (ref.length > 30 ? short(ref, 24) : ref)).join(", ") }) : null)));
  return h("div", { class: "stack" },
    card("Governance policies", fmtTime(item.created_at),
      h("div", { class: "row" }, badge(summary.status), h("span", { class: "muted", text: `${summary.pass} of ${applicable} applicable policies pass` }), h("span", { class: "spacer" }), actions),
      h("div", { class: "progress" }, h("span", { "data-w": pct(summary.pass, applicable) + "%" })),
      h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, ["Policy", "Status", "Explanation"].map((t) => h("th", { text: t })))), h("tbody", null, rows)))),
    notice("Passing these policies does not constitute certification or regulatory compliance."));
}

const STAGES = [["dataset", "Dataset"], ["transformation", "Transformation"], ["training_run", "Training run"], ["model_version", "Model version"], ["evaluation", "Evaluation"], ["deployment", "Deployment"]];

function lineageTab(ctx) {
  const lin = ctx.lineage;
  const graph = h("div", { class: "lineage" });
  STAGES.forEach(([type, label], index) => {
    const nodes = lin.nodes.filter((n) => n.node_type === type);
    graph.append(h("div", { class: "stage" + (nodes.length ? "" : " vacant") }, h("div", { class: "eyebrow", text: label }),
      nodes.length ? nodes.map((n) => h("div", { class: "node" + (n.id === lin.root ? " root" : "") },
        h("div", { class: "title", text: n.name }),
        h("div", { class: "small faint mono", text: n.fingerprint ? "sha256 " + short(n.fingerprint, 10) : "no fingerprint" }),
        h("div", { class: "small faint mono", text: n.id })))
        : h("div", { class: "node", text: "Not recorded" })));
    if (index < STAGES.length - 1) graph.append(h("div", { class: "chev", "aria-hidden": "true" }, icon("chevron")));
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
    card("Where this model came from", lin.lineage_digest ? `inputs digest ${short(lin.lineage_digest, 12)}` : "no upstream steps recorded", graph,
      h("p", { class: "small faint", text: lin.has_dataset ? "This model's lineage reaches a dataset. Only metadata and fingerprints are stored." : "No dataset is linked upstream of this model yet." })),
    canWrite() && card("Add a lineage step", "link it to something already shown", form));
}

function auditTab(ctx) {
  return card("Audit history", `${ctx.audit.length} events`, eventFeed(ctx.audit));
}

const TAB_VIEWS = { summary: summaryTab, security: securityTab, drift: driftTab, explain: explainTab, governance: governanceTab, lineage: lineageTab, audit: auditTab };

async function modelView(id, tab = "summary") {
  const [model, evidence, lineage, audit] = await Promise.all([api(`/models/${id}`), api(`/models/${id}/evidence`), api(`/models/${id}/lineage`), api(`/models/${id}/audit`)]);
  const ctx = { model, evidence, lineage, audit };
  const current = TAB_VIEWS[tab] ? tab : "summary";
  const done = passing(model.posture), fraction = done / CHECKS.length;
  const verify = async () => {
    const result = await api(`/models/${id}/verify`, { method: "POST", body: {} });
    toast(result.verified ? "Integrity verified: file matches its fingerprint" : "Integrity FAILED: file does not match", !result.verified);
    render();
  };
  const runAll = async () => {
    if (model.artifact_available) await api(`/models/${id}/verify`, { method: "POST", body: {} });
    await api(`/models/${id}/assess`, { method: "POST", body: {} });
    await api(`/models/${id}/risk`, { method: "POST" });
    const result = await api("/policies/evaluate", { method: "POST", body: { model_id: id } });
    toast(`Checks finished: ${result.summary.pass} policies pass, ${result.summary.fail} fail`);
    render();
  };
  const tabDot = (key, good) => key && h("span", { class: "tdot " + (checkState(model.posture, key, good) === "none" ? "" : checkState(model.posture, key, good)) });
  return h("div", null,
    h("div", { class: "crumb" }, h("a", { href: "#/models", text: "Models" }), " / ", model.name),
    h("section", { class: "card hero model-hero" }, h("div", { class: "hero-grid" },
      ring(fraction, scoreTone(fraction), { size: 112, stroke: 10, big: `${done}/${CHECKS.length}`, small: "checks pass", cls: "md" }),
      h("div", { class: "stack tight" },
        h("h1", null, model.name, " ", h("span", { class: "v", text: `v${model.version}` })),
        h("div", { class: "row" }, tierBadge(model.impact_tier), h("span", { class: "badge plain", text: model.framework }), model.posture.risk_level && h("span", { class: "row small faint" }, "risk", badge(model.posture.risk_level)),
          h("code", { class: "faint", text: "sha256 " + short(model.sha256, 16), title: model.sha256 })),
        pipeline(model.posture)),
      canWrite() && h("div", { class: "side" }, button("Run all checks", runAll, { kind: "primary", iconName: "play" }), model.artifact_available && button("Verify integrity", verify, { iconName: "fingerprint" })))),
    h("nav", { class: "tabs", "aria-label": "Model sections" }, TABS.map(([key, label, postureKey, good]) =>
      h("a", { href: `#/models/${id}/${key}`, class: key === current ? "active" : "" }, label, tabDot(postureKey, good)))),
    TAB_VIEWS[current](ctx));
}

// ---------------------------------------------------------------- policies & audit

async function policiesView() {
  const policies = await api("/policies");
  const rows = policies.map((p) => h("tr", null,
    h("td", null, h("div", { class: "title", text: p.title }), h("div", { class: "small faint mono", text: p.id })),
    h("td", null, h("span", { class: "badge plain", text: p.category })),
    h("td", null, badge(p.severity)),
    h("td", null, h("div", { text: p.description }), p.applies_to_tiers && h("div", { class: "small faint", text: `Applies to ${p.applies_to_tiers.join(", ")} impact models` }))));
  return h("div", { class: "stack" }, pageHead("Policies", "Governance requirements expressed as executable, version-controlled checks."),
    h("section", { class: "card flush" }, h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, ["Policy", "Category", "Severity", "Requirement"].map((t) => h("th", { text: t })))), h("tbody", null, rows)))),
    notice("Policies are loaded from YAML. Set AIGUARD_POLICY_FILE to use your own set."));
}

async function auditView() {
  const [events, chain] = await Promise.all([api("/audit?limit=300"), api("/audit/verify")]);
  const rows = events.map((e) => h("tr", null,
    h("td", { class: "mono faint", text: e.seq }), h("td", { class: "small muted", text: fmtTime(e.timestamp) }),
    h("td", null, h("div", { class: "title mono", text: e.action }), h("div", { class: "small faint", text: e.actor })),
    h("td", null, e.model_id ? h("a", { href: `#/models/${e.model_id}/audit`, class: "mono", text: e.model_id }) : h("span", { class: "faint", text: "—" })),
    h("td", null, badge(e.result)), h("td", { class: "mono faint", text: short(e.event_hash, 14), title: e.event_hash })));
  const verify = button("Verify chain now", async () => { const r = await api("/audit/verify"); toast(r.valid ? `Chain verified: ${r.events_checked} events` : `Chain broken at event ${r.first_invalid_seq}`, !r.valid); }, { iconName: "fingerprint" });
  return h("div", { class: "stack" },
    pageHead("Audit trail", "Every action is appended to a hash chain, so edits, deletions and reordering are detectable.", verify),
    h("div", { class: "grid stats" },
      stat("fingerprint", "Chain status", chain.valid ? "Verified" : "Broken", chain.valid ? "All links recomputed" : chain.reason, chain.valid ? "good" : "bad"),
      stat("audit", "Events checked", chain.events_checked, "since the first event", "info"),
      stat("share", "Head hash", short(chain.head_hash, 10), "Store this value externally", "info")),
    h("section", { class: "card flush" }, events.length ? h("div", { class: "table-wrap" }, h("table", null, h("thead", null, h("tr", null, ["#", "Time", "Action", "Model", "Result", "Event hash"].map((t) => h("th", { text: t })))), h("tbody", null, rows))) : empty("audit", "No events yet", "Events appear here as models are registered and assessed.")),
    notice("A hash chain gives tamper evidence, not tamper prevention: someone with full database access could rewrite the whole chain. Keep the head hash somewhere they cannot reach."));
}

// ---------------------------------------------------------------- get started guide

function codeBlock(label, text) {
  const copy = h("button", { class: "copy", type: "button" }, icon("copy"), h("span", { text: "Copy" }));
  copy.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(text); copy.lastChild.textContent = "Copied"; setTimeout(() => (copy.lastChild.textContent = "Copy"), 1500); }
    catch { toast("Copy failed. Select the text and copy it manually.", true); }
  });
  return h("div", { class: "code" }, h("div", { class: "code-head" }, label, copy), h("pre", null, h("code", { text })));
}

function step(number, title, text, ...blocks) {
  return h("div", { class: "step" }, h("div", { class: "step-num", text: number }), h("div", { class: "step-body" }, h("h2", { text: title }), text && h("p", { text }), ...blocks));
}

function guideSections() {
  const origin = location.origin;
  return {
    dashboard: ["Dashboard", "overview", [
      step(1, "Install AIGuard", "You need Python 3.12 or newer.", codeBlock("Terminal", 'git clone https://github.com/YashkantG/AIGuard-Framework.git\ncd AIGuard-Framework\npip install -e ".[dev]"')),
      step(2, "Load sample data (optional)", "Creates three made-up models: one healthy, one with drifting data, one with a dangerous file.", codeBlock("Terminal", "aiguard seed-demo")),
      step(3, "Start the server", "The server prints a temporary admin key. Paste it on the sign-in screen.", codeBlock("Terminal", "aiguard serve"), codeBlock("Then open", "http://127.0.0.1:8000")),
      step(4, "Check a model", "Open Models, pick a model and press Run all checks. It verifies the file, scans it, scores risk and evaluates every policy.",
        h("div", { class: "row" }, h("a", { class: "btn primary", href: "#/models" }, "Open models", icon("arrow")), canWrite() && button("Register a model", registerDialog, { iconName: "plus" }))),
      step(5, "Keep a stable key", "Set your own keys so they survive restarts. Roles are viewer, analyst and admin; keys need 16 or more characters.", codeBlock("Terminal", 'export AIGUARD_API_KEYS="alice:admin:replace-with-a-long-random-key"\naiguard serve')),
    ]],
    cli: ["Command line", "terminal", [
      step(1, "Is this file safe to load?", "Reads the file as bytes and reports hidden code. Needs no database or server.", codeBlock("Terminal", "aiguard scan model.pkl")),
      step(2, "Register a model", "Records the file's SHA-256 fingerprint and prints the model ID.", codeBlock("Terminal", 'aiguard register fraud 1.0.0 model.pkl --owner "Risk" --description "Fraud scoring"')),
      step(3, "Has the file changed?", "Exits with code 1 if the file no longer matches its fingerprint.", codeBlock("Terminal", "aiguard verify <model-id>")),
      step(4, "Assess and gate", "assess runs the security assessment; gate fails if any governance policy fails.", codeBlock("Terminal", "aiguard assess <model-id>\naiguard gate <model-id>")),
      step(5, "Get the evidence", "Writes a governance report and checks the audit log.", codeBlock("Terminal", "aiguard report <model-id> --output report.md\naiguard audit-verify")),
    ]],
    python: ["Python", "code", [
      step(1, "Scan a model file", null, codeBlock("Python", 'from aiguard.security import scan_artifact\n\nresult = scan_artifact("model.pkl")\nfor finding in result["findings"]:\n    print(finding.severity, "-", finding.title)')),
      step(2, "Register and verify", "Put model files in the artifacts folder next to where you run the code.", codeBlock("Python", 'from aiguard import AIGuard\nfrom aiguard.core.models import ModelCreate\n\nguard = AIGuard()\nmodel = guard.register_model(\n    ModelCreate(name="spam-filter", version="1.0.0", artifact_path="model.bin")\n)\nprint(guard.verify_integrity(model["id"])["verified"])')),
      step(3, "Detect drift", null, codeBlock("Python", 'from aiguard.monitoring import detect_drift\n\nreport = detect_drift({\n    "income": {"reference": training_income, "current": this_month_income},\n})\nprint(report["drifted_features"])')),
      step(4, "Evaluate policies", null, codeBlock("Python", 'guard.assess_security(model["id"])\nguard.assess_risk(model["id"])\nprint(guard.evaluate_policies(model["id"])["summary"])')),
      step(5, "Run the ready-made examples", "Each one works on its own with made-up data.", codeBlock("Terminal", "python examples/01_scan_model_file.py\npython examples/02_detect_drift.py\npython examples/03_register_and_check.py\npython examples/04_full_lifecycle.py")),
    ]],
    api: ["REST API", "globe", [
      step(1, "Send your key", "Every request needs the X-API-Key header.", codeBlock("Terminal", `export AIGUARD_KEY="your-api-key"\ncurl -H "X-API-Key: $AIGUARD_KEY" ${origin}/api/v1/models`)),
      step(2, "Register a model", null, codeBlock("Terminal", `curl -X POST ${origin}/api/v1/models \\\n  -H "X-API-Key: $AIGUARD_KEY" -H "Content-Type: application/json" \\\n  -d '{"name": "fraud", "version": "1.0.0", "artifact_path": "fraud.safetensors"}'`)),
      step(3, "Verify, assess, evaluate", null, codeBlock("Terminal", `curl -X POST -H "X-API-Key: $AIGUARD_KEY" ${origin}/api/v1/models/<model-id>/verify\ncurl -X POST -H "X-API-Key: $AIGUARD_KEY" ${origin}/api/v1/models/<model-id>/assess\ncurl -X POST ${origin}/api/v1/policies/evaluate \\\n  -H "X-API-Key: $AIGUARD_KEY" -H "Content-Type: application/json" \\\n  -d '{"model_id": "<model-id>"}'`)),
      step(4, "Explore every endpoint", "Interactive documentation is served by this server.", h("div", null, h("a", { class: "btn", href: "/api/docs", target: "_blank", rel: "noopener" }, icon("book"), "Open API docs"))),
    ]],
    deploy: ["Deploy", "rocket", [
      step(1, "Docker with PostgreSQL", "Fill in real values in .env before starting.", codeBlock("Terminal", "cd deployment/docker\ncp .env.example .env\ndocker compose up --build")),
      step(2, "Kubernetes", "Read the comments at the top of the manifest and set the image and secret first.", codeBlock("Terminal", "kubectl apply -f deployment/kubernetes/aiguard.yaml")),
      step(3, "Gate models in CI", "Copy the example workflow into the repository that holds your model.", codeBlock("File", "examples/github-actions/model-gate.yml")),
      step(4, "Before going live", "Put TLS in front of the service, run a single replica, and keep keys in a secret manager."),
    ]],
  };
}

function guideView(section) {
  const sections = guideSections();
  const current = sections[section] ? section : "dashboard";
  const tabs = h("div", { class: "guide-tabs", role: "tablist" }, Object.entries(sections).map(([key, [label, iconName]]) => {
    const b = h("button", { type: "button", class: key === current ? "on" : "" }, icon(iconName), label);
    b.addEventListener("click", () => (location.hash = `#/guide/${key}`));
    return b;
  }));
  return h("div", null,
    pageHead("Get started", "How to run AIGuard, step by step. Pick how you want to use it."),
    tabs,
    card(null, null, h("div", { class: "steps" }, sections[current][2])));
}

// ---------------------------------------------------------------- router

async function summaryForShell() {
  try {
    const st = await api("/stats");
    return { models: st.models, chainValid: st.audit_chain.valid };
  } catch { return null; }
}

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
  if (!root.querySelector(".shell")) root.replaceChildren(shell(active, h("div", { class: "stack" }, h("div", { class: "skeleton tall" }), h("div", { class: "skeleton" }), h("div", { class: "skeleton" })), null));
  let content;
  const summaryPromise = summaryForShell();
  try {
    if (active === "models") content = id ? await modelView(id, tab) : await modelsView();
    else if (active === "policies") content = await policiesView();
    else if (active === "audit") content = await auditView();
    else if (active === "guide") content = guideView(id);
    else content = await overviewView();
  } catch (err) {
    content = card(null, null, empty("alert", "Something went wrong", err.message, h("a", { class: "btn", href: "#/overview" }, "Back to overview")));
  }
  const summary = await summaryPromise;
  if (token !== state.renderToken || !state.me) return;
  const scroll = window.scrollY;
  root.replaceChildren(shell(active, content, summary));
  window.scrollTo(0, state.lastHash === location.hash ? scroll : 0);
  state.lastHash = location.hash;
  animateIn(root);
}

initTheme();
window.addEventListener("hashchange", render);
render();

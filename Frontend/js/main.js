// BIFAS Research Desk: app state, sessions, run lifecycle and wiring.
import { $, h, ICONS, escapeHtml, prettyModel, humanize, prefersReducedMotion } from "./util.js";
import * as api from "./api.js";
import { createBriefing } from "./views/briefing.js";
import { createAgentsPanel, renderAgentNotes } from "./views/agents.js";
import { createSessionsRail } from "./views/sessions.js";

const FALLBACK_DEPTHS = {
  Quick: { max_agents: 3, description: "Fast analysis, 3 agents, ~25s" },
  Standard: { max_agents: 6, description: "Balanced analysis, 6 agents, ~35s" },
  Deep: { max_agents: 12, description: "Thorough analysis, 12 agents, ~60s" },
};
const FALLBACK_EXAMPLES = [
  "Analyze NVDA, AAPL, MSFT stock outlook with technicals and valuation",
  "Bitcoin and Ethereum price trends, on-chain metrics, and sentiment",
  "EUR/USD, GBP/USD, USD/JPY forex correlations and macro factors",
  "Gold and crude oil price analysis with dollar correlation",
];

const el = {
  body: document.body, composer: $("composer"), query: $("query"), examples: $("examples"),
  depthOptions: $("depth-options"), run: $("run"), runIcon: $("run-icon"), runLabel: $("run-label"),
  formError: $("form-error"), banners: $("banners"), thread: $("thread"), startSlot: $("start-slot"),
  threadSlot: $("thread-slot"), composerLabel: $("composer-label"), live: $("live"),
  modelPill: $("model-pill"), modelName: $("model-name"), quota: $("quota"), quotaBar: $("quota-bar"),
  quotaFill: $("quota-fill"), quotaText: $("quota-text"), agents: $("agents"), agentsCount: $("agents-count"),
  agentsEmpty: $("agents-empty"), sessionList: $("session-list"), newSession: $("new-session"),
  mastheadTitle: $("masthead-title"),
};

const state = {
  depths: FALLBACK_DEPTHS,
  usage: null,
  sessions: [],       // summaries for the rail
  session: null,      // the open session ({id, title, briefings}) or null for a new one
  views: [],          // briefing views in the thread, oldest first
  focused: null,      // the briefing whose details show in the side column
  run: null,          // { view, controller, agents: [] } while a run is in progress
};

// ---------- side column ----------

const agentsPanel = createAgentsPanel(el.agents, el.agentsCount, {
  onOpen: (agent) => toggleInlineNotes(agent),
  onCount: (done, total) => {
    el.agentsEmpty.hidden = total > 0;
    if (state.run && state.focused === state.run.view) state.run.view.setAgentCount(done, total);
  },
});

function toggleInlineNotes(agent) {
  const li = [...el.agents.children].find((node) => node.querySelector(".agent-name")?.textContent === humanize(agent.name));
  if (!li) return;
  const open = li.querySelector(".agent-body");
  const button = li.querySelector(".agent-toggle");
  if (open) {
    open.remove();
    button.setAttribute("aria-expanded", "false");
  } else {
    li.append(renderAgentNotes(agent));
    button.setAttribute("aria-expanded", "true");
  }
}

function showDetails(view) {
  if (state.focused) state.focused.setFocused(false);
  state.focused = view;
  if (!view) {
    agentsPanel.clear();
    return;
  }
  view.setFocused(true);
  if (state.run && view === state.run.view) agentsPanel.set(state.run.agents);
  else agentsPanel.set(view.data.agents || []);
  if (view.data.id && state.session) setHash(state.session.id, view.data.id);
}

// ---------- header status ----------

function renderUsage(usage) {
  if (!usage) return;
  state.usage = usage;
  const fallback = !!usage.fallback_active;
  el.modelPill.dataset.kind = fallback ? "fallback" : "primary";
  el.modelName.textContent = fallback ? `Fallback: ${prettyModel(usage.fallback_model)}` : prettyModel(usage.primary_model);
  el.modelPill.title = fallback
    ? `Today's ${prettyModel(usage.primary_model)} quota is used up, so analyses run on ${prettyModel(usage.fallback_model)}.`
    : `Analyses run on ${prettyModel(usage.primary_model)}.`;
  const limit = Math.max(usage.limit || 0, 0);
  const used = Math.min(usage.used || 0, limit || usage.used || 0);
  el.quota.hidden = false;
  el.quotaBar.setAttribute("aria-valuemax", String(limit));
  el.quotaBar.setAttribute("aria-valuenow", String(used));
  el.quotaFill.style.width = limit ? `${Math.min(100, (used / limit) * 100)}%` : "0%";
  el.quotaText.textContent = `${used} of ${limit} requests today`;
}

/** Session name in the masthead; click (or Enter) to rename in place. */
function renderMastheadTitle() {
  const session = state.session;
  if (!session) {
    el.mastheadTitle.replaceChildren(h("span", { class: "masthead-session is-new" }, "New session"));
    return;
  }
  const button = h("button", { type: "button", class: "masthead-session", title: "Rename session" },
    h("span", { class: "masthead-session-name" }, session.title), h("span", { html: ICONS.pencil }));
  button.addEventListener("click", () => {
    const input = h("input", { class: "masthead-rename", value: session.title, maxlength: "80", "aria-label": "Session name" });
    el.mastheadTitle.replaceChildren(input);
    input.focus();
    input.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      done = true;
      const title = input.value.trim();
      if (save && title && title !== session.title) {
        try {
          await renameSession(session.id, title);
        } catch (err) {
          banner("error", escapeHtml(err.message));
        }
      }
      renderMastheadTitle();
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); finish(true); }
      if (e.key === "Escape") { e.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
  });
  el.mastheadTitle.replaceChildren(button);
}

// ---------- sessions ----------

const rail = createSessionsRail(el.sessionList, {
  onSelect: (id) => { if (!state.session || state.session.id !== id) openSession(id); },
  onNew: () => newSession(),
  onRename: (id, title) => renameSession(id, title),
  onDelete: async (id) => {
    try {
      await api.deleteSession(id);
    } catch (err) {
      if (err.status !== 404) {
        banner("error", escapeHtml(err.message));
        throw err;
      }
    }
    if (state.session && state.session.id === id) newSession();
    await refreshSessions();
    announce("Session deleted.");
  },
});

async function refreshSessions() {
  try {
    state.sessions = (await api.listSessions()).sessions || [];
  } catch (err) {
    state.sessions = [];
  }
  rail.render(state.sessions, state.session?.id || null);
}

async function renameSession(id, title) {
  const summary = await api.renameSession(id, title);
  if (state.session && state.session.id === id) state.session.title = summary.title;
  renderMastheadTitle();
  await refreshSessions();
}

function setHash(sessionId, briefingId) {
  const params = new URLSearchParams();
  if (sessionId) params.set("s", sessionId);
  if (briefingId) params.set("b", briefingId);
  const hash = params.toString() ? `#${params}` : "";
  if (location.hash !== hash) history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
}

function clearThread() {
  state.views = [];
  state.focused = null;
  el.thread.replaceChildren();
  el.banners.replaceChildren();
  agentsPanel.clear();
}

function newSession() {
  if (state.run) return;
  state.session = null;
  clearThread();
  setLayout();
  setHash(null, null);
  renderMastheadTitle();
  rail.render(state.sessions, null);
  el.query.focus();
}

/** Open a saved session from Memory/; no model calls are made. */
async function openSession(id, briefingId) {
  if (state.run) return;
  let session;
  try {
    session = await api.getSession(id);
  } catch (err) {
    banner("error", err.status === 404 ? "That session no longer exists. It may have been deleted." : escapeHtml(err.message));
    newSession();
    return;
  }
  state.session = session;
  clearThread();
  for (const briefing of session.briefings) addBriefingView(briefing);
  const target = state.views.find((v) => v.data.id === briefingId) || state.views[state.views.length - 1];
  if (target) {
    state.views.forEach((v) => v.setExpanded(v === target));
    showDetails(target);
    target.el.scrollIntoView({ block: "start" });
  }
  setLayout();
  setHash(session.id, target?.data.id);
  renderMastheadTitle();
  rail.render(state.sessions, session.id);
}

// ---------- composer ----------

function renderDepths(depths) {
  state.depths = depths;
  el.depthOptions.replaceChildren(...Object.entries(depths).map(([name, cfg]) => {
    const id = `depth-${name.toLowerCase()}`;
    const time = (cfg.description.match(/~\s*[\d.]+\s*\w+/) || [""])[0].replace(/\s+/g, "");
    return h("div", { class: "depth-option" },
      h("input", { type: "radio", name: "depth", id, value: name, checked: name === "Standard" }),
      h("label", { for: id, title: cfg.description },
        h("span", { class: "depth-name" }, name),
        h("span", { class: "depth-meta", dataset: { depth: name } }, `${cfg.max_agents} analysts${time ? `, ${time}` : ""}`)));
  }));
}

function renderExamples(examples) {
  el.examples.replaceChildren(...examples.map((text) =>
    h("button", { type: "button", class: "chip", onclick: () => {
      el.query.value = text;
      el.formError.hidden = true;
      el.query.dispatchEvent(new Event("input"));
      el.query.focus();
    } }, text)));
}

function selectedDepth() {
  return (el.composer.querySelector('input[name="depth"]:checked') || {}).value || "Standard";
}

/** Start screen shows the big composer; once there are briefings it sits under the thread. */
function setLayout() {
  const hasThread = state.views.length > 0;
  el.body.dataset.view = hasThread ? "thread" : "start";
  (hasThread ? el.threadSlot : el.startSlot).append(el.composer);
  el.composerLabel.textContent = hasThread ? "Ask a follow-up or a new question" : "Your question";
  el.query.placeholder = hasThread ? "What about silver instead?" : "Is gold still a hedge against a weaker dollar?";
}

function setRunning(running) {
  el.run.classList.toggle("is-cancel", running);
  el.runIcon.innerHTML = running ? ICONS.stop : ICONS.play;
  el.runLabel.textContent = running ? "Cancel" : "Run analysis";
  el.run.setAttribute("aria-label", running ? "Cancel the running analysis" : "Run analysis");
  el.newSession.disabled = running;
  rail.setLocked(running);
}

// ---------- banners ----------

function banner(kind, html, action) {
  const node = h("div", { class: "banner", dataset: { kind } },
    h("span", { html: kind === "error" ? ICONS.alert : ICONS.info }),
    h("div", { class: "banner-text", html }));
  if (action) node.append(h("button", { type: "button", class: "ghost banner-action", onclick: () => { node.remove(); action.run(); } },
    h("span", { html: ICONS.retry }), action.label));
  el.banners.append(node);
  return node;
}

function serverHelp() {
  return `Start it with <code>cd Backend &amp;&amp; uvicorn server:app --port 5050</code>, then reload this page.`;
}

function announce(message) { el.live.textContent = message; }

// ---------- briefings ----------

function addBriefingView(data) {
  const view = createBriefing(data, { onFocus: (v) => { if (state.focused !== v) showDetails(v); } });
  state.views.push(view);
  el.thread.append(view.el);
  // Only the newest briefing stays open; older ones collapse to a one-line header.
  state.views.slice(0, -1).forEach((v) => v.setExpanded(false));
  addBriefingTools(view);
  setLayout();
  return view;
}

function addBriefingTools(view) {
  const del = h("button", { type: "button", class: "icon-btn", "aria-label": "Delete this briefing", title: "Delete briefing", html: ICONS.trash });
  view.toolsEl.replaceChildren(del);
  view.setToolsVisible(!!view.data.id);
  del.addEventListener("click", (e) => {
    e.stopPropagation();
    const keep = h("button", { type: "button", class: "ghost small" }, "Keep");
    const confirm = h("button", { type: "button", class: "danger small" }, "Delete");
    view.toolsEl.replaceChildren(h("span", { class: "tools-confirm" }, "Delete this briefing?"), confirm, keep);
    confirm.focus();
    keep.addEventListener("click", (ev) => { ev.stopPropagation(); addBriefingTools(view); });
    confirm.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      try {
        await api.deleteBriefing(state.session.id, view.data.id);
      } catch (err) {
        if (err.status !== 404) {
          banner("error", escapeHtml(err.message));
          addBriefingTools(view);
          return;
        }
      }
      removeBriefingView(view);
      await refreshSessions();
      announce("Briefing deleted.");
    });
  });
}

function removeBriefingView(view) {
  view.el.remove();
  state.views = state.views.filter((v) => v !== view);
  if (state.session) state.session.briefings = state.session.briefings.filter((b) => b.id !== view.data.id);
  const next = state.views[state.views.length - 1];
  if (next) {
    next.setExpanded(true);
    showDetails(next);
  } else {
    showDetails(null);
    setHash(state.session?.id, null);
  }
  setLayout();
}

// ---------- running an analysis ----------

async function runAnalysis(query, depth) {
  el.banners.replaceChildren();
  const view = addBriefingView({ query, depth, live: true });
  const run = { view, controller: new AbortController(), agents: [], finished: false };
  state.run = run;
  showDetails(view);
  setRunning(true);
  view.startTimer();
  view.activateStep("data");
  view.el.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });

  const finish = (payload) => {
    const result = payload.result || {};
    run.finished = true;
    view.live = false;
    view.stopTimer(result.execution_time);
    if (!view.data.final_report && result.final_report) view.setReport(result.final_report);
    if (result.audit_status && !view.data.audit_status) view.setStamp(result.audit_status, { animate: true });
    view.finishSteps(false);
    const total = (result.agent_squad || []).length;
    const done = (result.rounds || []).length;
    view.setMetrics({ execution_time: result.execution_time, done, total, models: result.models_used });
    if (done < total) view.setStep("agents", done ? "done" : "failed");
    if (state.focused === view) agentsPanel.stopRunning();
    run.agents.forEach((a) => { if (a.status === "running") a.status = "not finished"; });
    Object.assign(view.data, {
      id: payload.briefing_id, created_at: new Date().toISOString(), agents: run.agents,
      final_report: view.data.final_report || result.final_report, audit_status: result.audit_status,
      execution_time: result.execution_time, models_used: result.models_used, used_context: result.used_context,
      domains: result.domains, tickers: result.tickers, market_snapshot: result.market_snapshot,
    });
    view.setMeta();
    view.setToolsVisible(true);
    if (state.session && payload.session) {
      state.session.title = payload.session.title;
      state.session.briefings.push(view.data);
    }
    if (state.focused === view) setHash(payload.session_id, payload.briefing_id);
    renderMastheadTitle();
    refreshSessions();
    if (result.guardrail_triggered) banner("warn", escapeHtml(result.guardrail_triggered));
    if (result.fallback_used) {
      banner("warn", `Today's primary model quota is used up, so this briefing was written by ${escapeHtml((result.models_used || []).map(prettyModel).join(", "))}.`);
    }
    renderUsage(payload.usage);
    announce(`Analysis complete in ${Math.round(result.execution_time || 0)} seconds.`);
  };

  const fail = (message, { retry = true } = {}) => {
    if (run.finished) return;
    run.finished = true;
    view.stopTimer();
    view.finishSteps(true);
    if (state.focused === view) agentsPanel.stopRunning();
    if (!view.data.final_report) view.setReport("");
    banner("error", message, retry ? {
      label: "Try again",
      run: () => {
        removeBriefingView(view);
        startRun(query, depth);
      },
    } : null);
    announce("Analysis stopped.");
  };

  const onEvent = (type, data) => {
    switch (type) {
      case "session":
        if (!state.session || state.session.id !== data.id) {
          state.session = { id: data.id, title: data.title, briefings: [] };
          renderMastheadTitle();
          setHash(data.id, null);
          refreshSessions();
        }
        break;
      case "phase": view.activateStep(data.name); break;
      case "data": view.setAssets(data.domains, data.tickers); break;
      case "tasks":
        run.agents = (data.agents || []).map((a) => ({ ...a, status: "running" }));
        if (state.focused === view) agentsPanel.set(run.agents);
        view.setAgentCount(0, run.agents.length);
        break;
      case "agent": {
        const agent = run.agents.find((a) => a.name === data.name);
        if (agent) Object.assign(agent, { status: data.status, text: data.text, model: data.model });
        if (state.focused === view) agentsPanel.update(data);
        view.setAgentCount(run.agents.filter((a) => a.status !== "running").length, run.agents.length);
        announce(`${humanize(data.name)} ${data.status === "done" ? "finished" : data.status}`);
        break;
      }
      case "report": view.setReport(data.markdown); break;
      case "audit": view.setStamp(data.status, { animate: true }); break;
      case "done": finish(data); break;
      case "error": fail(escapeHtml(data.message || "The analysis failed.")); break;
      default: break;
    }
  };

  try {
    await api.streamAnalyze({ query, depth, session: state.session?.id }, onEvent, run.controller.signal);
    if (!run.finished) fail("The server closed the connection before the analysis finished.");
  } catch (err) {
    if (err.name === "AbortError") {
      fail("Analysis cancelled. Nothing was saved, and no more requests were used.");
    } else if (err.status === 0) {
      fail(`Can't reach the BIFAS server. ${serverHelp()}`);
    } else if (err.status === 404) {
      fail("This session no longer exists. Start a new session and try again.", { retry: false });
    } else {
      fail(escapeHtml(err.message));
    }
  } finally {
    if (state.run === run) state.run = null;
    setRunning(false);
    // A cancelled or failed first run leaves no saved session behind.
    if (!run.view.data.id && state.session && !state.session.briefings.length) refreshSessions();
  }
}

function startRun(query, depth) {
  if (state.run) return;
  runAnalysis(query, depth);
}

// ---------- events ----------

el.composer.addEventListener("submit", (e) => {
  e.preventDefault();
  if (state.run) {
    state.run.controller.abort();
    return;
  }
  const query = el.query.value.trim();
  if (!query) {
    el.formError.textContent = "Type a question or pick one of the examples.";
    el.formError.hidden = false;
    el.query.focus();
    return;
  }
  el.formError.hidden = true;
  startRun(query, selectedDepth());
  el.query.value = "";
  el.query.classList.remove("has-text");
});

el.query.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    el.composer.requestSubmit();
  }
});
el.query.addEventListener("input", () => {
  el.formError.hidden = true;
  el.query.classList.toggle("has-text", el.query.value.trim().length > 0);
});

el.newSession.addEventListener("click", () => newSession());

document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "") || document.activeElement?.isContentEditable;
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "/") {
    e.preventDefault();
    el.query.focus();
  } else if (e.key === "n" || e.key === "N") {
    e.preventDefault();
    newSession();
  }
});

window.addEventListener("hashchange", () => {
  const params = new URLSearchParams(location.hash.slice(1));
  const sid = params.get("s");
  if (sid && (!state.session || state.session.id !== sid)) openSession(sid, params.get("b"));
});

// ---------- start ----------

async function init() {
  setRunning(false);
  setLayout();
  renderMastheadTitle();
  try {
    const meta = await api.getMeta();
    renderDepths(meta.depths || FALLBACK_DEPTHS);
    renderExamples(meta.examples || FALLBACK_EXAMPLES);
    renderUsage(meta.usage);
  } catch (err) {
    renderDepths(FALLBACK_DEPTHS);
    renderExamples(FALLBACK_EXAMPLES);
    el.modelPill.dataset.kind = "offline";
    el.modelName.textContent = "Server offline";
    banner("error", `Can't reach the BIFAS server${api.API ? ` at <code>${escapeHtml(api.API)}</code>` : ""}. ${serverHelp()}`);
    rail.render([], null);
    return;
  }
  await refreshSessions();
  const params = new URLSearchParams(location.hash.slice(1));
  if (params.get("s")) await openSession(params.get("s"), params.get("b"));
}

init();

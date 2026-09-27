/* BIFAS Research Desk — talks to the FastAPI backend in ../Backend/server.py */
(function () {
  "use strict";

  const API = (new URLSearchParams(location.search).get("api") || window.BIFAS_API || "").replace(/\/+$/, "");
  const STEPS = ["data", "decompose", "agents", "synthesis", "audit"];

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
  const SYMBOL_NAMES = {
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "JPY=X": "USD/JPY", "CHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD", "NZDUSD=X": "NZD/USD", "CAD=X": "USD/CAD",
    "GC=F": "Gold", "SI=F": "Silver", "CL=F": "WTI crude", "BZ=F": "Brent crude",
    "HG=F": "Copper", "NG=F": "Natural gas", "PL=F": "Platinum", "PA=F": "Palladium",
    "bitcoin": "Bitcoin", "ethereum": "Ethereum", "solana": "Solana", "ripple": "XRP",
    "cardano": "Cardano", "dogecoin": "Dogecoin", "avalanche-2": "Avalanche",
    "polkadot": "Polkadot", "matic-network": "Polygon",
  };

  const ICONS = {
    waiting: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7"/></svg>',
    running: '<svg viewBox="0 0 20 20"><path d="M10 3a7 7 0 1 1-7 7"/></svg>',
    done: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7.5"/><path d="m6.5 10.2 2.3 2.3 4.7-4.9"/></svg>',
    failed: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7.5"/><path d="m7.5 7.5 5 5m0-5-5 5"/></svg>',
    chevron: '<svg class="chev" viewBox="0 0 16 16"><path d="m4 6 4 4 4-4"/></svg>',
    alert: '<svg viewBox="0 0 20 20"><path d="M10 3 2 17h16z"/><path d="M10 8.5v3.5m0 2.5v.01"/></svg>',
    info: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7.5"/><path d="M10 9v4.5m0-7v.01"/></svg>',
  };
  ICONS.skipped = ICONS.failed;

  const $ = (id) => document.getElementById(id);
  const el = {
    page: document.querySelector(".page"), form: $("ask-form"), query: $("query"), examples: $("examples"), depthOptions: $("depth-options"),
    run: $("run"), runLabel: $("run-label"), formError: $("form-error"), banners: $("banners"),
    progress: $("progress"), steps: $("steps"), agentCount: $("agent-count"), timer: $("timer"), live: $("live"),
    intro: $("intro"), workspace: $("workspace"), agents: $("agents"),
    memoQuery: $("memo-query"), stamp: $("stamp"), stampLabel: $("stamp-label"), stampReason: $("stamp-reason"),
    assets: $("assets"), metrics: $("metrics"), mTime: $("m-time"), mAgents: $("m-agents"), mModel: $("m-model"),
    report: $("report"), actions: $("memo-actions"), copy: $("copy"), download: $("download"),
    modelPill: $("model-pill"), modelName: $("model-name"),
    quota: $("quota"), quotaBar: $("quota-bar"), quotaFill: $("quota-fill"), quotaText: $("quota-text"),
  };

  const state = { running: false, started: 0, timerId: null, agents: new Map(), report: "", query: "", finished: false };

  // ---------- helpers ----------

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function renderMarkdown(text) {
    if (window.marked && window.DOMPurify) {
      return window.DOMPurify.sanitize(window.marked.parse(text || "", { gfm: true }));
    }
    // Libraries unavailable (offline): show plain paragraphs.
    return String(text || "").split(/\n{2,}/).map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`).join("");
  }

  function humanize(name) {
    const words = String(name).replace(/[_-]+/g, " ").trim();
    if (!words) return "Analyst";
    const sentence = words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
    return sentence.replace(/\b(usd|eur|gbp|jpy|btc|eth|nvda|aapl|msft|googl|amzn|tsla|jpm|wti|us|fx|etf|ai)\b/gi, (m) => m.toUpperCase());
  }

  function prettyModel(id) {
    if (!id) return "Unknown model";
    return id.split("-").filter((p) => p !== "it").map((p) =>
      /^a?\d+b$/i.test(p) ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
  }

  function formatElapsed(seconds) {
    const s = Math.max(0, Math.round(seconds));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }

  function announce(message) { el.live.textContent = message; }

  function banner(kind, html) {
    const div = document.createElement("div");
    div.className = "banner";
    div.dataset.kind = kind;
    div.innerHTML = `${kind === "error" ? ICONS.alert : ICONS.info}<div>${html}</div>`;
    el.banners.appendChild(div);
  }

  function serverHelp() {
    return `Start it with <code>cd Backend &amp;&amp; uvicorn server:app --port 5050</code>, then reload this page.`;
  }

  // ---------- setup ----------

  function renderDepths(depths) {
    el.depthOptions.innerHTML = "";
    Object.entries(depths).forEach(([name, cfg], i) => {
      const id = `depth-${name.toLowerCase()}`;
      const time = (cfg.description.match(/~\s*[\d.]+\s*\w+/) || [""])[0].replace(/\s+/g, "");
      const wrap = document.createElement("div");
      wrap.className = "depth-option";
      wrap.innerHTML = `
        <input type="radio" name="depth" id="${id}" value="${escapeHtml(name)}" ${name === "Standard" || (i === 0 && !depths.Standard) ? "checked" : ""}>
        <label for="${id}" title="${escapeHtml(cfg.description)}">
          <span class="depth-name">${escapeHtml(name)}</span>
          <span class="depth-meta">${cfg.max_agents} analysts${time ? `, ${escapeHtml(time)}` : ""}</span>
        </label>`;
      el.depthOptions.appendChild(wrap);
    });
  }

  function renderExamples(examples) {
    el.examples.innerHTML = "";
    examples.forEach((text) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = text;
      b.addEventListener("click", () => {
        el.query.value = text;
        el.formError.hidden = true;
        el.query.focus();
      });
      el.examples.appendChild(b);
    });
  }

  function renderUsage(usage) {
    if (!usage) return;
    const fallback = !!usage.fallback_active;
    el.modelPill.dataset.kind = fallback ? "fallback" : "primary";
    el.modelName.textContent = fallback
      ? `Fallback: ${prettyModel(usage.fallback_model)}`
      : prettyModel(usage.primary_model);
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
    el.quota.title = `${used} of ${limit} ${prettyModel(usage.primary_model)} requests used today`;
  }

  async function loadMeta() {
    try {
      const res = await fetch(`${API}/api/meta`, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(String(res.status));
      const meta = await res.json();
      renderDepths(meta.depths || FALLBACK_DEPTHS);
      renderExamples(meta.examples || FALLBACK_EXAMPLES);
      renderUsage(meta.usage);
    } catch (err) {
      renderDepths(FALLBACK_DEPTHS);
      renderExamples(FALLBACK_EXAMPLES);
      el.modelPill.dataset.kind = "offline";
      el.modelName.textContent = "Server offline";
      banner("error", `Can't reach the BIFAS server${API ? ` at <code>${escapeHtml(API)}</code>` : ""}. ${serverHelp()}`);
    }
  }

  // ---------- run lifecycle ----------

  function setStep(name, stateName) {
    const li = el.steps.querySelector(`[data-step="${name}"]`);
    if (li) li.dataset.state = stateName;
  }

  function activateStep(name) {
    const idx = STEPS.indexOf(name);
    STEPS.forEach((s, i) => {
      const li = el.steps.querySelector(`[data-step="${s}"]`);
      if (i < idx && li.dataset.state !== "failed") li.dataset.state = "done";
      if (i === idx) li.dataset.state = "active";
    });
    const labels = { data: "Fetching live market data", decompose: "Planning analyst tasks", agents: "Analysts are working",
      synthesis: "Writing the briefing", audit: "Auditing the briefing" };
    announce(labels[name] || "");
  }

  function startTimer() {
    state.started = performance.now();
    el.timer.textContent = "0:00";
    clearInterval(state.timerId);
    state.timerId = setInterval(() => {
      el.timer.textContent = formatElapsed((performance.now() - state.started) / 1000);
    }, 250);
  }

  function stopTimer(seconds) {
    clearInterval(state.timerId);
    state.timerId = null;
    if (typeof seconds === "number") el.timer.textContent = formatElapsed(seconds);
  }

  function setRunning(running) {
    state.running = running;
    el.run.disabled = running;
    el.runLabel.textContent = running ? "Analyzing…" : "Run analysis";
    el.report.setAttribute("aria-busy", running ? "true" : "false");
  }

  function resetWorkspace(query) {
    el.banners.innerHTML = "";
    el.page.classList.add("is-compact");
    el.intro.hidden = true;
    el.progress.hidden = false;
    el.workspace.hidden = false;
    STEPS.forEach((s) => setStep(s, "pending"));
    el.agentCount.textContent = "";
    el.agents.innerHTML = "";
    state.agents.clear();
    state.report = "";
    state.finished = false;
    el.memoQuery.textContent = query;
    el.stamp.hidden = true;
    el.stamp.className = "stamp";
    el.stampReason.hidden = true;
    el.assets.innerHTML = "";
    el.metrics.hidden = true;
    el.actions.hidden = true;
    el.report.className = "memo-body";
    el.report.innerHTML = `
      <div class="skeleton" aria-hidden="true">
        <div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div>
        <div class="skeleton-line"></div><div class="skeleton-line"></div>
      </div>
      <p class="skeleton-note">The briefing appears here once the analysts finish.</p>`;
  }

  function renderAssets(domains, tickers) {
    el.assets.innerHTML = "";
    (domains || []).forEach((d) => {
      const span = document.createElement("span");
      span.className = "asset";
      span.dataset.domain = d;
      span.textContent = d.charAt(0).toUpperCase() + d.slice(1);
      el.assets.appendChild(span);
    });
    Object.values(tickers || {}).flat().forEach((sym) => {
      const span = document.createElement("span");
      span.className = "asset";
      span.textContent = SYMBOL_NAMES[sym] || sym;
      span.title = sym;
      el.assets.appendChild(span);
    });
  }

  function agentRow(agent) {
    const li = document.createElement("li");
    li.className = "agent";
    li.dataset.status = "running";
    const bodyId = `agent-body-${state.agents.size}`;
    li.innerHTML = `
      <button type="button" class="agent-toggle" aria-expanded="false" aria-controls="${bodyId}" disabled>
        <span class="status-icon">${ICONS.running}</span>
        <span class="agent-name"></span>
        <span class="agent-state"><span class="agent-state-text">Working</span></span>
      </button>
      <p class="agent-task"></p>
      <div class="agent-body prose" id="${bodyId}" hidden></div>`;
    li.querySelector(".agent-name").textContent = humanize(agent.name);
    li.querySelector(".agent-task").textContent = agent.task || "";
    const toggle = li.querySelector(".agent-toggle");
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      li.querySelector(".agent-body").hidden = open;
    });
    return li;
  }

  function renderAgents(agents) {
    agents.forEach((a) => {
      const li = agentRow(a);
      state.agents.set(a.name, { li, status: "running" });
      el.agents.appendChild(li);
    });
    updateAgentCount();
  }

  function updateAgentCount() {
    const total = state.agents.size;
    const done = [...state.agents.values()].filter((a) => a.status !== "running").length;
    el.agentCount.textContent = total ? `${done}/${total}` : "";
  }

  function updateAgent(data) {
    let entry = state.agents.get(data.name);
    if (!entry) {
      renderAgents([{ name: data.name, task: "" }]);
      entry = state.agents.get(data.name);
    }
    const { li } = entry;
    entry.status = data.status;
    li.dataset.status = data.status;
    li.querySelector(".status-icon").innerHTML = ICONS[data.status] || ICONS.done;
    const stateText = li.querySelector(".agent-state");
    const toggle = li.querySelector(".agent-toggle");
    if (data.status === "done") {
      li.querySelector(".agent-body").innerHTML = renderMarkdown(data.text);
      toggle.disabled = false;
      stateText.innerHTML = `<span class="agent-state-text">Read</span>${ICONS.chevron}`;
    } else {
      stateText.innerHTML = `<span class="agent-state-text">${data.status === "skipped" ? "Timed out" : "Failed"}</span>`;
    }
    updateAgentCount();
    announce(`${humanize(data.name)} ${data.status === "done" ? "finished" : data.status}`);
  }

  function renderReport(markdown) {
    state.report = markdown || "";
    el.report.className = "memo-body prose";
    el.report.innerHTML = state.report ? renderMarkdown(state.report) : '<p class="empty-note">No briefing was produced.</p>';
    el.actions.hidden = !state.report;
  }

  function parseVerdict(status) {
    const text = String(status || "");
    const reason = text.includes("—") ? text.split("—").slice(1).join("—").trim() : text.replace(/^STATUS:\s*/i, "");
    if (/APPROVED/i.test(text)) return { kind: "approved", label: "Approved", reason };
    if (/REJECTED/i.test(text)) return { kind: "rejected", label: "Rejected", reason };
    if (/UNVERIFIED/i.test(text)) return { kind: "other", label: "Unverified", reason };
    return { kind: "other", label: "Not audited", reason: text };
  }

  function renderStamp(status) {
    const v = parseVerdict(status);
    el.stamp.hidden = false;
    el.stamp.dataset.kind = v.kind;
    el.stampLabel.textContent = v.label;
    el.stamp.setAttribute("aria-label", `Audit verdict: ${v.label}`);
    el.stamp.classList.remove("is-new");
    void el.stamp.offsetWidth; // restart the stamp animation
    el.stamp.classList.add("is-new");
    el.stampReason.textContent = v.reason;
    el.stampReason.hidden = !v.reason;
    setStep("audit", v.kind === "rejected" ? "failed" : v.label === "Not audited" ? "skipped" : "done");
  }

  function finish(result, usage) {
    state.finished = true;
    stopTimer(result.execution_time);
    setRunning(false);

    if (!state.report && result.final_report) renderReport(result.final_report);
    if (el.stamp.hidden) renderStamp(result.audit_status);
    STEPS.forEach((s) => {
      const li = el.steps.querySelector(`[data-step="${s}"]`);
      if (li.dataset.state === "active") li.dataset.state = "done";
      if (li.dataset.state === "pending") li.dataset.state = "skipped";
    });

    const total = (result.agent_squad || []).length;
    const done = (result.rounds || []).length;
    el.mTime.textContent = `${(result.execution_time || 0).toFixed(1)}s`;
    el.mAgents.textContent = `${done} of ${total} finished`;
    el.mModel.textContent = (result.models_used || []).map(prettyModel).join(", ") || "None";
    el.metrics.hidden = false;
    if (done < total) setStep("agents", done ? "done" : "failed");

    if (result.guardrail_triggered) {
      banner("warn", escapeHtml(result.guardrail_triggered));
    }
    if (result.fallback_used) {
      banner("warn", `Today's primary model quota is used up, so this briefing was written by ${escapeHtml((result.models_used || []).map(prettyModel).join(", "))}.`);
    }
    renderUsage(usage);
    announce(`Analysis complete in ${(result.execution_time || 0).toFixed(0)} seconds. Verdict: ${parseVerdict(result.audit_status).label}.`);
  }

  function fail(message) {
    if (state.finished) return;
    state.finished = true;
    stopTimer();
    setRunning(false);
    STEPS.forEach((s) => {
      const li = el.steps.querySelector(`[data-step="${s}"]`);
      if (li.dataset.state === "active") li.dataset.state = "failed";
    });
    [...state.agents.values()].filter((a) => a.status === "running")
      .forEach((a) => updateAgent({ name: [...state.agents.entries()].find(([, v]) => v === a)[0], status: "skipped" }));
    if (!state.report) {
      el.report.className = "memo-body";
      el.report.innerHTML = '<p class="empty-note">No briefing was produced. Check the message above and try again.</p>';
    }
    banner("error", message);
    announce("Analysis stopped with an error.");
  }

  function handleEvent(type, data) {
    switch (type) {
      case "phase": activateStep(data.name); break;
      case "data": renderAssets(data.domains, data.tickers); break;
      case "tasks": renderAgents(data.agents || []); break;
      case "agent": updateAgent(data); break;
      case "report": renderReport(data.markdown); break;
      case "audit": renderStamp(data.status); break;
      case "done": finish(data.result || {}, data.usage); break;
      case "error": fail(escapeHtml(data.message || "The analysis failed.")); break;
      default: break;
    }
  }

  async function run(query, depth) {
    state.query = query;
    resetWorkspace(query);
    setRunning(true);
    startTimer();
    activateStep("data");
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.progress.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });

    const url = `${API}/api/analyze?${new URLSearchParams({ query, depth })}`;
    let res;
    try {
      res = await fetch(url, { headers: { Accept: "text/event-stream" } });
    } catch (err) {
      fail(`Can't reach the BIFAS server. ${serverHelp()}`);
      return;
    }
    if (!res.ok) {
      let detail = "";
      try { detail = (await res.json()).detail; } catch (e) { /* not JSON */ }
      const msg = typeof detail === "string" ? detail
        : res.status === 429 ? "Too many analyses are running. Try again in a minute."
        : `The server rejected the request (HTTP ${res.status}).`;
      fail(escapeHtml(msg));
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let split;
        while ((split = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, split);
          buffer = buffer.slice(split + 2);
          let type = "message";
          const dataLines = [];
          block.split("\n").forEach((line) => {
            if (line.startsWith("event:")) type = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
          });
          if (!dataLines.length) continue; // keep-alive comment
          let data;
          try { data = JSON.parse(dataLines.join("\n")); } catch (e) { continue; }
          handleEvent(type, data);
        }
      }
    } catch (err) {
      fail("The connection to the server dropped before the analysis finished. Try again.");
      return;
    }
    if (!state.finished) fail("The server closed the connection before the analysis finished. Try again.");
  }

  // ---------- events ----------

  el.form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (state.running) return;
    const query = el.query.value.trim();
    if (!query) {
      el.formError.textContent = "Type a question or pick one of the examples.";
      el.formError.hidden = false;
      el.query.focus();
      return;
    }
    el.formError.hidden = true;
    const depth = (el.form.querySelector('input[name="depth"]:checked') || {}).value || "Standard";
    run(query, depth);
  });

  el.query.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      el.form.requestSubmit();
    }
  });
  el.query.addEventListener("input", () => { el.formError.hidden = true; });

  el.copy.addEventListener("click", async () => {
    const label = el.copy.querySelector("span");
    try {
      await navigator.clipboard.writeText(state.report);
      label.textContent = "Copied";
    } catch (e) {
      label.textContent = "Copy failed";
    }
    setTimeout(() => { label.textContent = "Copy report"; }, 1600);
  });

  el.download.addEventListener("click", () => {
    const header = `# BIFAS briefing\n\n> ${state.query}\n\n`;
    const blob = new Blob([header + state.report], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `bifas-briefing-${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  loadMeta();
})();

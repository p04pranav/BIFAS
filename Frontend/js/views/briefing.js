// One briefing in the thread: header, live progress, verdict stamp, report and actions.
import { h, ICONS, renderMarkdown, parseVerdict, formatElapsed, relativeTime, prettyModel,
  assetNames, prefersReducedMotion } from "../util.js";

const STEPS = [
  ["data", "Market data"],
  ["decompose", "Plan tasks"],
  ["agents", "Analysts"],
  ["synthesis", "Write report"],
  ["audit", "Audit"],
];

/**
 * Build a briefing view.
 * data: a saved briefing ({id, query, depth, created_at, final_report, audit_status, ...})
 *       or {query, depth, live: true} for a run in progress.
 * handlers: { onFocus(view), onDelete(view) }
 */
export function createBriefing(data, handlers = {}) {
  const view = { data: { ...data }, el: null, live: !!data.live };
  const verdictChip = h("span", { class: "verdict-chip", hidden: true });
  const metaText = h("span", { class: "briefing-meta-text" });
  const toggle = h("button", { type: "button", class: "briefing-toggle", "aria-expanded": "true" },
    h("span", { class: "briefing-q" }, data.query || ""),
    h("span", { class: "briefing-meta" }, verdictChip, metaText, h("span", { html: ICONS.chevron })));
  const actionsMenu = h("div", { class: "briefing-tools" });

  const steps = h("ol", { class: "steps" }, STEPS.map(([key, label]) =>
    h("li", { class: "step", dataset: { step: key, state: "pending" } },
      h("span", { class: "step-label" }, label, key === "agents" ? h("span", { class: "step-count" }) : null))));
  const timer = h("span", { class: "timer", "aria-label": "Elapsed time" }, "0:00");
  const progress = h("div", { class: "progress", hidden: !view.live }, steps, timer);

  const stamp = h("div", { class: "stamp", hidden: true }, h("span", { class: "stamp-label" }));
  const stampReason = h("p", { class: "stamp-reason", hidden: true });
  const assets = h("div", { class: "assets", "aria-label": "Assets analyzed" });
  const metrics = h("dl", { class: "metrics", hidden: true });
  const report = h("div", { class: "memo-body", "aria-busy": view.live ? "true" : "false" });
  const copyBtn = h("button", { type: "button", class: "ghost", html: `${ICONS.copy}<span>Copy report</span>` });
  const downloadBtn = h("button", { type: "button", class: "ghost", html: `${ICONS.download}<span>Download .md</span>` });
  const memoActions = h("footer", { class: "memo-actions", hidden: true }, copyBtn, downloadBtn);

  const memo = h("div", { class: "memo" },
    h("div", { class: "memo-head" }, h("div", { class: "memo-context" }, assets), stamp),
    stampReason, metrics, report, memoActions);
  const body = h("div", { class: "briefing-body" }, progress, memo);
  const el = h("article", { class: "briefing", dataset: { id: data.id || "" }, tabindex: "-1" },
    h("header", { class: "briefing-head" }, toggle, actionsMenu), body);
  view.el = el;

  toggle.addEventListener("click", () => view.setExpanded(toggle.getAttribute("aria-expanded") !== "true"));
  el.addEventListener("focusin", () => handlers.onFocus && handlers.onFocus(view));
  el.addEventListener("click", () => handlers.onFocus && handlers.onFocus(view));

  copyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const label = copyBtn.querySelector("span");
    try {
      await navigator.clipboard.writeText(view.data.final_report || "");
      label.textContent = "Copied";
    } catch (err) {
      label.textContent = "Copy failed";
    }
    setTimeout(() => { label.textContent = "Copy report"; }, 1600);
  });
  downloadBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const text = `# BIFAS briefing\n\n> ${view.data.query}\n\n${view.data.final_report || ""}`;
    const a = h("a", { href: URL.createObjectURL(new Blob([text], { type: "text/markdown" })),
      download: `bifas-briefing-${(view.data.created_at || new Date().toISOString()).slice(0, 10)}.md` });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  // ---- API used by main.js ----

  view.setExpanded = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    body.hidden = !open;
    el.classList.toggle("is-collapsed", !open);
  };

  view.setStep = (name, state) => {
    const li = steps.querySelector(`[data-step="${name}"]`);
    if (li) li.dataset.state = state;
  };

  view.activateStep = (name) => {
    const idx = STEPS.findIndex(([key]) => key === name);
    STEPS.forEach(([key], i) => {
      const li = steps.querySelector(`[data-step="${key}"]`);
      if (i < idx && li.dataset.state !== "failed") li.dataset.state = "done";
      if (i === idx) li.dataset.state = "active";
    });
  };

  view.setAgentCount = (done, total) => {
    steps.querySelector(".step-count").textContent = total ? `${done}/${total}` : "";
  };

  let timerId = null;
  let started = 0;
  view.startTimer = () => {
    started = performance.now();
    timerId = setInterval(() => { timer.textContent = formatElapsed((performance.now() - started) / 1000); }, 250);
  };
  view.stopTimer = (seconds) => {
    clearInterval(timerId);
    if (typeof seconds === "number") timer.textContent = formatElapsed(seconds);
  };

  view.setAssets = (domains, tickers) => {
    assets.replaceChildren(
      ...(domains || []).map((d) => h("span", { class: "asset", dataset: { domain: d } }, d.charAt(0).toUpperCase() + d.slice(1))),
      ...assetNames(tickers).map((name) => h("span", { class: "asset" }, name)),
    );
  };

  view.showSkeleton = () => {
    report.className = "memo-body";
    report.innerHTML = `<div class="skeleton" aria-hidden="true">${'<div class="skeleton-line"></div>'.repeat(5)}</div>
      <p class="skeleton-note">The briefing appears here once the analysts finish.</p>`;
  };

  view.setReport = (markdown) => {
    view.data.final_report = markdown || "";
    report.className = "memo-body prose";
    report.innerHTML = markdown ? renderMarkdown(markdown) : '<p class="empty-note">No briefing was produced.</p>';
    report.setAttribute("aria-busy", "false");
    memoActions.hidden = !markdown;
  };

  view.setStamp = (status, { animate = false } = {}) => {
    view.data.audit_status = status;
    const v = parseVerdict(status);
    stamp.hidden = false;
    stamp.dataset.kind = v.kind;
    stamp.querySelector(".stamp-label").textContent = v.label;
    stamp.setAttribute("aria-label", `Audit verdict: ${v.label}`);
    if (animate && !prefersReducedMotion()) {
      stamp.classList.remove("is-new");
      void stamp.offsetWidth;
      stamp.classList.add("is-new");
    }
    stampReason.textContent = v.reason;
    stampReason.hidden = !v.reason;
    verdictChip.hidden = false;
    verdictChip.dataset.kind = v.kind;
    verdictChip.textContent = v.label;
    if (view.live) view.setStep("audit", v.kind === "rejected" ? "failed" : v.label === "Not audited" ? "skipped" : "done");
  };

  view.setMetrics = ({ execution_time, done, total, models }) => {
    metrics.replaceChildren(
      h("div", {}, h("dt", {}, "Time"), h("dd", {}, `${(execution_time || 0).toFixed(1)}s`)),
      h("div", {}, h("dt", {}, "Analysts"), h("dd", {}, `${done} of ${total} finished`)),
      h("div", {}, h("dt", {}, "Model"), h("dd", {}, (models || []).map(prettyModel).join(", ") || "None")),
    );
    metrics.hidden = false;
  };

  view.setMeta = () => {
    const parts = [view.data.depth];
    if (view.data.created_at) parts.unshift(relativeTime(view.data.created_at));
    if (view.data.used_context) parts.push("follow-up");
    metaText.textContent = parts.filter(Boolean).join(", ");
  };

  /** Mark all unfinished steps at the end of a run. */
  view.finishSteps = (failed) => {
    steps.querySelectorAll(".step").forEach((li) => {
      if (li.dataset.state === "active") li.dataset.state = failed ? "failed" : "done";
      else if (li.dataset.state === "pending") li.dataset.state = "skipped";
    });
    report.setAttribute("aria-busy", "false");
  };

  view.setFocused = (focused) => el.classList.toggle("is-focused", focused);

  view.setToolsVisible = (visible) => { actionsMenu.hidden = !visible; };
  view.toolsEl = actionsMenu;

  // Saved briefing: render everything immediately.
  if (!view.live) {
    view.setAssets(data.domains, data.tickers);
    view.setReport(data.final_report);
    if (data.audit_status) view.setStamp(data.audit_status);
    const agents = data.agents || [];
    view.setMetrics({ execution_time: data.execution_time, done: agents.filter((a) => a.status === "done").length,
      total: agents.length, models: data.models_used });
  } else {
    view.showSkeleton();
  }
  view.setMeta();
  return view;
}

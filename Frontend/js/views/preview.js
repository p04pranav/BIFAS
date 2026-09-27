// Composer preview: what a question will analyze, whether it builds on the session,
// and what it costs in model requests. Uses /api/preview (local keyword matching, no AI).
import { h, assetNames } from "../util.js";
import * as api from "../api.js";

const DEBOUNCE_MS = 300;

/**
 * els: { box, assets, context, contextInput, contextLabel, cost, query }
 * getState(): { sessionId, briefingCount, depth, usage }
 */
export function createPreview(els, getState) {
  let timer = null;
  let estimates = null;
  let seq = 0;
  let lastPreview = null;

  async function loadEstimates() {
    try {
      estimates = (await api.getPreview("")).estimates;
    } catch (err) {
      estimates = null;
    }
    return estimates;
  }

  function renderAssets(preview) {
    lastPreview = preview;
    if (!preview || !els.query.value.trim()) {
      els.assets.replaceChildren();
      els.assets.hidden = true;
      return;
    }
    const names = assetNames(preview.tickers);
    const namedCount = Object.values(preview.named || {}).flat().length;
    let lead;
    if (preview.carried_over) lead = "Continuing with";
    else if (!namedCount) lead = "No specific assets named, so the desk will use";
    else lead = "Will analyze";
    els.assets.hidden = false;
    els.assets.replaceChildren(
      h("span", { class: "preview-lead" }, lead),
      ...(names.length
        ? names.map((n) => h("span", { class: "asset" }, n))
        : [h("span", { class: "preview-lead" }, "general market context")]));
  }

  function renderCost() {
    const { depth, usage } = getState();
    if (!estimates || !usage) {
      els.cost.hidden = true;
      return;
    }
    const cost = estimates[depth];
    const left = Math.max(0, (usage.limit || 0) - (usage.used || 0));
    els.cost.hidden = false;
    els.cost.dataset.kind = cost > left ? "warn" : "ok";
    els.cost.textContent = cost > left
      ? `Uses about ${cost} requests, but only ${left} are left today, so the slower fallback model will write part or all of it.`
      : `Uses about ${cost} of the ${left} requests left today.`;
  }

  function renderContext() {
    const { sessionId, briefingCount } = getState();
    const count = Math.min(briefingCount, 3);
    els.context.hidden = !(sessionId && count > 0);
    els.contextLabel.textContent = `Builds on ${count} earlier ${count === 1 ? "briefing" : "briefings"}`;
    els.context.title = els.contextInput.checked
      ? "The desk sees a summary of this session's recent briefings, so follow-ups like 'what about silver?' make sense. Numbers always come from fresh market data."
      : "This question is analyzed on its own, without the session's earlier briefings.";
  }

  async function refresh() {
    const query = els.query.value.trim();
    const mine = ++seq;
    if (!query) {
      renderAssets(null);
      return;
    }
    const { sessionId } = getState();
    try {
      const preview = await api.getPreview(query, els.contextInput.checked ? sessionId : null);
      if (mine === seq) renderAssets(preview);
    } catch (err) {
      if (mine === seq) renderAssets(null);
    }
  }

  els.query.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, DEBOUNCE_MS);
  });
  els.contextInput.addEventListener("change", () => {
    renderContext();
    refresh();
  });

  return {
    loadEstimates,
    /** Re-render after the session, depth or usage changed. */
    update() {
      renderContext();
      renderCost();
      if (els.query.value.trim()) refresh();
      else renderAssets(null);
    },
    renderCost,
    useContext: () => !els.contextInput.checked ? false : undefined,
    resetContext() {
      els.contextInput.checked = true;
      renderContext();
    },
    estimate: (depth) => (estimates ? estimates[depth] : null),
    last: () => lastPreview,
  };
}

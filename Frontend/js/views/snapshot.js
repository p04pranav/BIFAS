// Market snapshot: a stat tile per asset (price, daily change, RSI, 30-day sparkline),
// with a table view as the accessible alternative.
import { h, ICONS, formatPrice, formatPct } from "../util.js";

const W = 260;
const H = 44;
const PAD = 4;

function rsiZone(rsi) {
  if (rsi === null || rsi === undefined) return null;
  if (rsi < 30) return "Oversold";
  if (rsi > 70) return "Overbought";
  return "Neutral";
}

function direction(change) {
  if (change === null || change === undefined || Math.abs(change) < 0.005) return "flat";
  return change > 0 ? "up" : "down";
}

function formatDate(iso) {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString([], { month: "short", day: "numeric" });
}

/** A single-series sparkline: muted line, accent latest point, hover/keyboard crosshair with a tooltip. */
function sparkline(asset) {
  const points = asset.closes || [];
  const wrap = h("div", { class: "spark" });
  if (points.length < 2) return wrap;
  const values = points.map((p) => p[1]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const x = (i) => PAD + (i * (W - PAD * 2)) / (points.length - 1);
  const y = (v) => PAD + (H - PAD * 2) * (1 - (v - min) / span);
  const path = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const last = points.length - 1;
  const label = `${asset.name} closing prices over the last ${points.length} sessions, from ${formatPrice(values[0], asset.domain)} to ${formatPrice(values[last], asset.domain)}. Use the arrow keys to read each day.`;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("class", "spark-svg");
  svg.setAttribute("role", "img");
  svg.setAttribute("tabindex", "0");
  svg.setAttribute("aria-label", label);
  svg.innerHTML = `
    <path class="spark-line" d="${path}" vector-effect="non-scaling-stroke"/>
    <line class="spark-cross" x1="0" x2="0" y1="0" y2="${H}" vector-effect="non-scaling-stroke" visibility="hidden"/>
    <circle class="spark-last" cx="${x(last)}" cy="${y(values[last])}" r="4"/>
    <circle class="spark-hover" r="4" visibility="hidden"/>`;
  const cross = svg.querySelector(".spark-cross");
  const dot = svg.querySelector(".spark-hover");
  const tip = h("div", { class: "spark-tip", role: "status", hidden: true });
  wrap.append(svg, tip);

  let index = null;
  const show = (i) => {
    index = Math.max(0, Math.min(last, i));
    const px = x(index);
    cross.setAttribute("x1", px);
    cross.setAttribute("x2", px);
    cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", px);
    dot.setAttribute("cy", y(values[index]));
    dot.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.replaceChildren(h("span", { class: "spark-tip-date" }, formatDate(points[index][0])),
      h("strong", {}, formatPrice(values[index], asset.domain)));
    const pct = (px / W) * 100;
    tip.style.left = `${Math.min(78, Math.max(0, pct - 11))}%`;
  };
  const hide = () => {
    index = null;
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("visibility", "hidden");
    tip.hidden = true;
  };
  svg.addEventListener("pointermove", (e) => {
    const rect = svg.getBoundingClientRect();
    const rel = ((e.clientX - rect.left) / rect.width) * W;
    show(Math.round(((rel - PAD) / (W - PAD * 2)) * last));
  });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      show(index === null ? last : index + (e.key === "ArrowRight" ? 1 : -1));
    } else if (e.key === "Home") { e.preventDefault(); show(0); }
    else if (e.key === "End") { e.preventDefault(); show(last); }
    else if (e.key === "Escape") hide();
  });
  return wrap;
}

function tile(asset) {
  const dir = direction(asset.change_pct);
  const zone = rsiZone(asset.rsi);
  // Tickers help for stocks and crypto (NVDA, BTC); forex and futures codes (EURUSD=X, GC=F) only add noise.
  const symbol = (asset.domain === "stocks" || asset.domain === "crypto") && asset.symbol !== asset.name ? asset.symbol : "";
  const summary = [
    `${asset.name}: ${formatPrice(asset.price, asset.domain)}`,
    asset.change_pct === null || asset.change_pct === undefined ? ""
      : dir === "flat" ? "unchanged on the day"
      : `${dir} ${Math.abs(asset.change_pct).toFixed(2)}% on the day`,
    asset.rsi === null || asset.rsi === undefined ? "" : `RSI ${asset.rsi}, ${zone.toLowerCase()}`,
  ].filter(Boolean).join(", ");
  return h("li", { class: "tile", "aria-label": summary },
    h("div", { class: "tile-head" },
      h("span", { class: "tile-name" }, asset.name),
      symbol ? h("span", { class: "tile-symbol" }, symbol) : null),
    h("div", { class: "tile-row" },
      h("span", { class: "tile-value" }, formatPrice(asset.price, asset.domain)),
      h("span", { class: "tile-delta", dataset: { dir } },
        h("span", { class: "tile-delta-mark", html: ICONS[dir] }),
        formatPct(asset.change_pct),
        h("span", { class: "tile-delta-period" }, "today"))),
    sparkline(asset),
    asset.rsi === null || asset.rsi === undefined ? null : h("div", { class: "tile-rsi" },
      h("span", {}, `RSI ${asset.rsi}`),
      h("span", { class: "rsi-zone", dataset: { zone: zone.toLowerCase() } }, zone)));
}

function table(assets) {
  return h("table", { class: "snapshot-table" },
    h("caption", { class: "sr-only" }, "Market snapshot"),
    h("thead", {}, h("tr", {}, ["Asset", "Price", "Day", "RSI", "30-day low / high"].map((c) => h("th", { scope: "col" }, c)))),
    h("tbody", {}, assets.map((a) => {
      const values = (a.closes || []).map((p) => p[1]);
      const range = values.length
        ? [h("span", { class: "range-low" }, formatPrice(Math.min(...values), a.domain)),
           h("span", { class: "range-high" }, formatPrice(Math.max(...values), a.domain))]
        : "—";
      return h("tr", {},
        h("th", { scope: "row" }, a.name),
        h("td", {}, formatPrice(a.price, a.domain)),
        h("td", {}, formatPct(a.change_pct)),
        h("td", {}, a.rsi ?? "—"),
        h("td", { class: "range" }, range));
    })));
}

export function createSnapshotPanel(container, toggleBtn) {
  let assets = [];
  let asTable = false;

  function render() {
    toggleBtn.hidden = !assets.length;
    toggleBtn.setAttribute("aria-pressed", String(asTable));
    toggleBtn.querySelector("span").textContent = asTable ? "View as tiles" : "View as table";
    if (!assets.length) return;
    container.replaceChildren(asTable ? table(assets) : h("ul", { class: "tiles" }, assets.map(tile)));
  }

  toggleBtn.addEventListener("click", () => {
    asTable = !asTable;
    render();
  });

  return {
    set(list) {
      assets = list || [];
      if (!assets.length) {
        toggleBtn.hidden = true;
        container.replaceChildren(h("p", { class: "panel-empty" }, "No market data was fetched for this question."));
        return;
      }
      render();
    },
    loading() {
      assets = [];
      toggleBtn.hidden = true;
      container.replaceChildren(h("ul", { class: "tiles", "aria-hidden": "true" },
        [0, 1].map(() => h("li", { class: "tile tile--skeleton" },
          h("div", { class: "skeleton-line" }), h("div", { class: "skeleton-line" }), h("div", { class: "skeleton-line" })))));
    },
    empty() {
      assets = [];
      toggleBtn.hidden = true;
      container.replaceChildren(h("p", { class: "panel-empty" }, "Live prices for the assets in a briefing appear here."));
    },
  };
}

// Shared helpers: DOM building, formatting, markdown, icons.

export const $ = (id) => document.getElementById(id);

/** Create an element: h("div", { class: "x", onclick: fn }, child, "text", ...) */
export function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "html") node.innerHTML = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, String(value));
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function renderMarkdown(text) {
  if (window.marked && window.DOMPurify) {
    return window.DOMPurify.sanitize(window.marked.parse(text || "", { gfm: true }));
  }
  // Libraries unavailable (offline): plain paragraphs.
  return String(text || "").split(/\n{2,}/).map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`).join("");
}

const ACRONYMS = /\b(usd|eur|gbp|jpy|chf|btc|eth|nvda|aapl|msft|googl|amzn|tsla|jpm|wti|us|fx|etf|ai|rsi|macd|mvrv)\b/gi;

/** "us_dollar_correlation_analyst" -> "US dollar correlation analyst" */
export function humanize(name) {
  const words = String(name || "").replace(/[_-]+/g, " ").trim();
  if (!words) return "Analyst";
  const sentence = words.charAt(0).toUpperCase() + words.slice(1).toLowerCase();
  return sentence.replace(ACRONYMS, (m) => m.toUpperCase());
}

/** "gemini-3.5-flash-lite" -> "Gemini 3.5 Flash Lite", "gemma-4-26b-a4b-it" -> "Gemma 4 26B A4B" */
export function prettyModel(id) {
  if (!id) return "Unknown model";
  return id.split("-").filter((p) => p !== "it").map((p) =>
    /^a?\d+b$/i.test(p) ? p.toUpperCase() : p.charAt(0).toUpperCase() + p.slice(1)).join(" ");
}

export function formatElapsed(seconds) {
  const s = Math.max(0, Math.round(seconds || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function relativeTime(iso) {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const seconds = (Date.now() - then.getTime()) / 1000;
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400 && then.getDate() === new Date().getDate()) {
    return then.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  if (seconds < 7 * 86400) return then.toLocaleDateString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
  return then.toLocaleDateString([], { month: "short", day: "numeric" });
}

export function isToday(iso) {
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

/** Price formatting by asset type: forex to 4 decimals, the rest as dollars. */
export function formatPrice(value, domain) {
  if (value === null || value === undefined) return "—";
  if (domain === "forex") return value.toLocaleString("en-US", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
  const digits = Math.abs(value) >= 1 ? 2 : 4;
  return "$" + value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function formatPct(value) {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(2)}%`;
}

export function parseVerdict(status) {
  const text = String(status || "");
  const reason = text.includes("—") ? text.split("—").slice(1).join("—").trim() : text.replace(/^STATUS:\s*/i, "");
  if (/APPROVED/i.test(text)) return { kind: "approved", label: "Approved", reason };
  if (/REJECTED/i.test(text)) return { kind: "rejected", label: "Rejected", reason };
  if (/UNVERIFIED/i.test(text)) return { kind: "other", label: "Unverified", reason };
  if (/CANCELLED/i.test(text)) return { kind: "other", label: "Cancelled", reason: "" };
  return { kind: "other", label: "Not audited", reason: text };
}

export const SYMBOL_NAMES = {
  "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "JPY=X": "USD/JPY", "CHF=X": "USD/CHF",
  "AUDUSD=X": "AUD/USD", "NZDUSD=X": "NZD/USD", "CAD=X": "USD/CAD",
  "GC=F": "Gold", "SI=F": "Silver", "CL=F": "WTI crude", "BZ=F": "Brent crude",
  "HG=F": "Copper", "NG=F": "Natural gas", "PL=F": "Platinum", "PA=F": "Palladium",
  bitcoin: "Bitcoin", ethereum: "Ethereum", solana: "Solana", ripple: "XRP", cardano: "Cardano",
  dogecoin: "Dogecoin", "avalanche-2": "Avalanche", polkadot: "Polkadot", "matic-network": "Polygon",
};

export function assetNames(tickers) {
  return Object.values(tickers || {}).flat().map((s) => SYMBOL_NAMES[s] || s);
}

export function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// 20x20 stroke icons (Lucide-style).
const svg = (body, cls = "icon") => `<svg class="${cls}" viewBox="0 0 20 20" aria-hidden="true">${body}</svg>`;
export const ICONS = {
  waiting: svg('<circle cx="10" cy="10" r="7"/>'),
  running: svg('<path d="M10 3a7 7 0 1 1-7 7"/>', "icon spin"),
  done: svg('<circle cx="10" cy="10" r="7.5"/><path d="m6.5 10.2 2.3 2.3 4.7-4.9"/>'),
  failed: svg('<circle cx="10" cy="10" r="7.5"/><path d="m7.5 7.5 5 5m0-5-5 5"/>'),
  chevron: svg('<path d="m7 8 3 3 3-3"/>', "icon chev"),
  chevronRight: svg('<path d="m8 6 4 4-4 4"/>'),
  alert: svg('<path d="M10 3 2 17h16z"/><path d="M10 8.5v3.5m0 2.5v.01"/>'),
  info: svg('<circle cx="10" cy="10" r="7.5"/><path d="M10 9v4.5m0-7v.01"/>'),
  plus: svg('<path d="M10 4v12M4 10h12"/>'),
  play: svg('<path d="M6 4.5v11l9-5.5z" fill="currentColor" stroke="none"/>'),
  stop: svg('<rect x="5.5" y="5.5" width="9" height="9" rx="1.5" fill="currentColor" stroke="none"/>'),
  copy: svg('<rect x="7" y="7" width="9" height="10" rx="1.5"/><path d="M4 13V4.5A1.5 1.5 0 0 1 5.5 3H12"/>'),
  download: svg('<path d="M10 3v10m-4-4 4 4 4-4M4 16h12"/>'),
  trash: svg('<path d="M4 6h12M8 6V4h4v2m-6 0 .7 10h6.6L14 6"/>'),
  pencil: svg('<path d="M4 16l1-4 8-8 3 3-8 8z"/>'),
  close: svg('<path d="m5 5 10 10M15 5 5 15"/>'),
  up: svg('<path d="M10 5 15 13H5z" fill="currentColor" stroke="none"/>', "icon tri"),
  down: svg('<path d="M10 15 5 7h10z" fill="currentColor" stroke="none"/>', "icon tri"),
  flat: svg('<path d="M5 10h10"/>', "icon tri"),
  link: svg('<path d="M8 12l4-4m-5.5 1.5-2 2a2.8 2.8 0 0 0 4 4l2-2m1-7 2-2a2.8 2.8 0 0 1 4 4l-2 2"/>'),
  retry: svg('<path d="M4 10a6 6 0 1 0 2-4.5M4 3.5V7h3.5"/>'),
  table: svg('<rect x="3" y="4" width="14" height="12" rx="1.5"/><path d="M3 8h14M3 12h14M8 4v12"/>'),
};

// Report reading aids: drop the duplicated title, set the executive summary as a lead block,
// and build sticky section tabs with scroll-spy.
import { h, prefersReducedMotion } from "../util.js";

let counter = 0;

/** Enhance a rendered report in place. Returns a cleanup function. */
export function enhanceReport(reportEl, tabsEl) {
  // The briefing header already shows the question, so a leading "BIFAS Executive Report: …" h1 is noise.
  const first = reportEl.firstElementChild;
  if (first && first.tagName === "H1") first.remove();

  let headings = [...reportEl.querySelectorAll("h2")];
  if (headings.length < 2) headings = [...reportEl.querySelectorAll("h2, h3")];

  const summary = headings.find((hd) => /executive summary|summary|overview/i.test(hd.textContent));
  if (summary) {
    const lead = h("section", { class: "lead", "aria-label": summary.textContent.trim() });
    let node = summary.nextElementSibling;
    while (node && !/^H[1-3]$/.test(node.tagName)) {
      const nextNode = node.nextElementSibling;
      lead.append(node);
      node = nextNode;
    }
    summary.after(lead);
  }

  if (headings.length < 2) {
    tabsEl.hidden = true;
    tabsEl.replaceChildren();
    return () => {};
  }

  const prefix = `sec-${++counter}`;
  const buttons = headings.map((hd, i) => {
    hd.id = `${prefix}-${i}`;
    hd.setAttribute("tabindex", "-1");
    const label = hd.textContent.replace(/&/g, "and").trim();
    return h("button", { type: "button", class: "section-tab", dataset: { target: hd.id } }, label);
  });
  tabsEl.replaceChildren(...buttons);
  tabsEl.hidden = false;

  const setActive = (id) => {
    for (const b of buttons) {
      const active = b.dataset.target === id;
      b.classList.toggle("is-active", active);
      if (active) {
        b.setAttribute("aria-current", "true");
        const box = tabsEl.getBoundingClientRect();
        const r = b.getBoundingClientRect();
        if (r.left < box.left || r.right > box.right) tabsEl.scrollLeft += r.left - box.left - 24;
      } else {
        b.removeAttribute("aria-current");
      }
    }
  };
  setActive(headings[0].id);

  buttons.forEach((b) => b.addEventListener("click", () => {
    const target = document.getElementById(b.dataset.target);
    target.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    target.focus({ preventScroll: true });
    setActive(target.id);
  }));

  // Scroll-spy: the active section is the last heading that has passed the upper third of the viewport.
  const onScroll = () => {
    const line = window.innerHeight * 0.33;
    let current = headings[0];
    for (const hd of headings) {
      if (hd.getBoundingClientRect().top <= line) current = hd;
    }
    setActive(current.id);
  };
  let raf = null;
  const throttled = () => {
    if (raf) return;
    raf = requestAnimationFrame(() => { raf = null; onScroll(); });
  };
  window.addEventListener("scroll", throttled, { passive: true });
  return () => window.removeEventListener("scroll", throttled);
}

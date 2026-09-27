// Analyst notes drawer: a modal side sheet with previous/next, Esc to close and a focus trap.
import { h, ICONS, humanize, prettyModel, renderMarkdown } from "../util.js";

export function createDrawer() {
  const title = h("h2", { class: "drawer-title", id: "drawer-title" });
  const meta = h("p", { class: "drawer-meta" });
  const task = h("p", { class: "drawer-task" });
  const body = h("div", { class: "drawer-body prose" });
  const close = h("button", { type: "button", class: "icon-btn drawer-close", "aria-label": "Close analyst notes", html: ICONS.close });
  const prev = h("button", { type: "button", class: "ghost drawer-nav" });
  const next = h("button", { type: "button", class: "ghost drawer-nav" });
  const panel = h("div", { class: "drawer-panel", role: "dialog", "aria-modal": "true", "aria-labelledby": "drawer-title", tabindex: "-1" },
    h("header", { class: "drawer-head" }, h("div", {}, title, meta), close),
    h("div", { class: "drawer-scroll" }, task, body),
    h("footer", { class: "drawer-foot" }, prev, next));
  const backdrop = h("div", { class: "drawer-backdrop" });
  const root = h("div", { class: "drawer", hidden: true }, backdrop, panel);
  document.body.append(root);

  let agents = [];
  let index = 0;
  let returnFocus = null;
  let onClose = null;

  function readable() {
    return agents.filter((a) => a.status === "done" && a.text);
  }

  function show(i) {
    const list = readable();
    index = (i + list.length) % list.length;
    const agent = list[index];
    title.textContent = humanize(agent.name);
    meta.textContent = [`Analyst ${index + 1} of ${list.length}`, agent.model ? prettyModel(agent.model) : null].filter(Boolean).join(", ");
    task.textContent = agent.task || "";
    task.hidden = !agent.task;
    body.innerHTML = renderMarkdown(agent.text);
    panel.querySelector(".drawer-scroll").scrollTop = 0;
    const single = list.length < 2;
    prev.hidden = single;
    next.hidden = single;
    if (!single) {
      prev.innerHTML = `<span class="nav-dir">Previous</span><span class="nav-name">${humanize(list[(index - 1 + list.length) % list.length].name)}</span>`;
      next.innerHTML = `<span class="nav-dir">Next</span><span class="nav-name">${humanize(list[(index + 1) % list.length].name)}</span>`;
    }
  }

  function hide() {
    if (root.hidden) return;
    root.hidden = true;
    document.body.classList.remove("drawer-open");
    if (onClose) onClose(readable()[index]);
    if (returnFocus && document.contains(returnFocus)) returnFocus.focus();
  }

  close.addEventListener("click", hide);
  backdrop.addEventListener("click", hide);
  prev.addEventListener("click", () => show(index - 1));
  next.addEventListener("click", () => show(index + 1));
  root.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      hide();
      return;
    }
    if (e.key !== "Tab") return;
    const focusable = [...panel.querySelectorAll("button:not([hidden]), a[href], [tabindex='0']")].filter((n) => n.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  return {
    /** Open the drawer on `agent`; `list` is every analyst of the briefing (only finished ones are readable). */
    open(agent, list, { onClosed } = {}) {
      agents = list;
      onClose = onClosed || null;
      returnFocus = document.activeElement;
      const i = readable().findIndex((a) => a.name === agent.name);
      if (i < 0) return;
      root.hidden = false;
      document.body.classList.add("drawer-open");
      show(i);
      close.focus();
    },
    close: hide,
    isOpen: () => !root.hidden,
  };
}

// Sessions rail: list, switch, rename (F2 / double-click) and delete (with confirmation).
import { h, ICONS, relativeTime, isToday } from "../util.js";

/**
 * handlers: { onSelect(id), onNew(), onRename(id, title) -> Promise, onDelete(id) -> Promise }
 */
export function createSessionsRail(listEl, handlers) {
  let sessions = [];
  let activeId = null;
  let locked = false;

  function item(session) {
    const verdict = session.last_verdict || "none";
    const meta = `${relativeTime(session.updated_at)}, ${session.briefing_count} ${session.briefing_count === 1 ? "briefing" : "briefings"}`;
    const open = h("button", {
      type: "button", class: "session-open", "aria-current": session.id === activeId ? "page" : null,
      title: locked ? "Finish or cancel the running analysis first" : session.title,
      "aria-disabled": locked ? "true" : null,
    },
      h("span", { class: "session-dot", dataset: { verdict }, "aria-hidden": "true" }),
      h("span", { class: "session-text" },
        h("span", { class: "session-title" }, session.title),
        h("span", { class: "session-meta" }, meta)));
    const rename = h("button", { type: "button", class: "icon-btn", "aria-label": `Rename ${session.title}`, title: "Rename (F2)", html: ICONS.pencil });
    const del = h("button", { type: "button", class: "icon-btn", "aria-label": `Delete ${session.title}`, title: "Delete session", html: ICONS.trash });
    const li = h("li", { class: "session", dataset: { id: session.id } }, open, h("span", { class: "session-tools" }, rename, del));
    if (session.id === activeId) li.classList.add("is-active");

    open.addEventListener("click", () => { if (!locked) handlers.onSelect(session.id); });
    open.addEventListener("dblclick", () => startRename(li, session));
    open.addEventListener("keydown", (e) => {
      if (e.key === "F2") { e.preventDefault(); startRename(li, session); }
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        const buttons = [...listEl.querySelectorAll(".session-open")];
        const next = buttons[buttons.indexOf(open) + (e.key === "ArrowDown" ? 1 : -1)];
        if (next) next.focus();
      }
    });
    rename.addEventListener("click", () => startRename(li, session));
    del.addEventListener("click", () => confirmDelete(li, session));
    return li;
  }

  function startRename(li, session) {
    const input = h("input", { class: "session-rename", value: session.title, maxlength: "80", "aria-label": "Session name" });
    const error = h("span", { class: "session-error", role: "alert" });
    li.replaceChildren(input, error);
    input.focus();
    input.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      const title = input.value.trim();
      if (save && title && title !== session.title) {
        try {
          done = true;
          await handlers.onRename(session.id, title);
          return;
        } catch (err) {
          done = false;
          error.textContent = err.message;
          input.focus();
          return;
        }
      }
      done = true;
      render(sessions, activeId);
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); finish(true); }
      if (e.key === "Escape") { e.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
  }

  function confirmDelete(li, session) {
    const keep = h("button", { type: "button", class: "ghost small" }, "Keep");
    const del = h("button", { type: "button", class: "danger small" }, "Delete");
    li.replaceChildren(h("div", { class: "session-confirm", role: "group", "aria-label": "Confirm delete" },
      h("span", {}, `Delete "${session.title}" and its briefings?`), h("span", { class: "confirm-actions" }, del, keep)));
    del.focus();
    keep.addEventListener("click", () => render(sessions, activeId));
    del.addEventListener("click", async () => {
      del.disabled = true;
      del.textContent = "Deleting…";
      try {
        await handlers.onDelete(session.id);
      } catch (err) {
        del.disabled = false;
        del.textContent = "Delete";
      }
    });
    li.addEventListener("keydown", (e) => { if (e.key === "Escape") render(sessions, activeId); });
  }

  function group(label, items) {
    if (!items.length) return null;
    return h("li", { class: "session-group" },
      h("h3", { class: "session-group-title" }, label),
      h("ul", { class: "session-sublist" }, items.map(item)));
  }

  function render(list, active) {
    sessions = list;
    activeId = active;
    if (!sessions.length) {
      listEl.replaceChildren(h("li", { class: "rail-empty" }, "Your sessions will appear here. Ask a question to start one."));
      return;
    }
    const today = sessions.filter((s) => isToday(s.updated_at));
    const earlier = sessions.filter((s) => !isToday(s.updated_at));
    listEl.replaceChildren(...[group("Today", today), group("Earlier", earlier)].filter(Boolean));
  }

  return {
    render,
    setLocked(value) {
      locked = value;
      render(sessions, activeId);
    },
    focusActive() {
      listEl.querySelector(".session.is-active .session-open")?.focus();
    },
  };
}

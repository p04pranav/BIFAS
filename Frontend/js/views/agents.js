// Analysts panel in the right-hand column: one row per analyst with live status.
import { h, ICONS, humanize } from "../util.js";

const STATE_TEXT = { running: "Working", done: "Read", failed: "Failed", skipped: "Timed out", "not finished": "Not finished" };

export function createAgentsPanel(listEl, countEl, handlers = {}) {
  let rows = new Map();

  function statusIcon(status) {
    return status === "done" ? ICONS.done : status === "running" ? ICONS.running
      : status === "waiting" ? ICONS.waiting : ICONS.failed;
  }

  function updateCount() {
    const total = rows.size;
    const finished = [...rows.values()].filter((r) => r.status !== "running").length;
    countEl.textContent = total ? `${finished}/${total}` : "";
    handlers.onCount && handlers.onCount(finished, total);
  }

  function row(agent) {
    const name = h("span", { class: "agent-name" }, humanize(agent.name));
    const state = h("span", { class: "agent-state" });
    const icon = h("span", { class: "status-icon" });
    const button = h("button", { type: "button", class: "agent-toggle", disabled: true, "aria-haspopup": "dialog" }, icon, name, state);
    const task = h("p", { class: "agent-task" }, agent.task || "");
    const li = h("li", { class: "agent" }, button, task);
    const entry = { agent: { ...agent }, li, button, icon, state, status: "running" };
    button.addEventListener("click", () => handlers.onOpen && handlers.onOpen(entry.agent, [...rows.values()].map((r) => r.agent)));
    return entry;
  }

  function setStatus(entry, status, text, model) {
    entry.status = status;
    entry.agent.status = status;
    if (text !== undefined) entry.agent.text = text;
    if (model) entry.agent.model = model;
    entry.li.dataset.status = status;
    entry.icon.innerHTML = statusIcon(status);
    const readable = status === "done" && entry.agent.text;
    entry.button.disabled = !readable;
    entry.state.innerHTML = `<span>${STATE_TEXT[status] || status}</span>${readable ? ICONS.chevronRight : ""}`;
  }

  return {
    /** Replace the list with agents (saved briefings pass their final statuses). */
    set(agents, { live = false } = {}) {
      rows = new Map();
      listEl.replaceChildren();
      for (const agent of agents) {
        const entry = row(agent);
        rows.set(agent.name, entry);
        listEl.append(entry.li);
        setStatus(entry, live ? "running" : (agent.status || "done"), agent.text, agent.model);
      }
      updateCount();
    },
    update({ name, status, text, model }) {
      let entry = rows.get(name);
      if (!entry) {
        entry = row({ name, task: "" });
        rows.set(name, entry);
        listEl.append(entry.li);
      }
      setStatus(entry, status, text, model);
      updateCount();
    },
    /** At the end of a failed run, anything still working is marked as not finished. */
    stopRunning() {
      for (const entry of rows.values()) if (entry.status === "running") setStatus(entry, "skipped");
      updateCount();
    },
    agents: () => [...rows.values()].map((r) => r.agent),
    focusRow(name) {
      const entry = rows.get(name);
      if (entry) entry.button.focus();
    },
    clear() {
      rows = new Map();
      listEl.replaceChildren();
      updateCount();
    },
  };
}

// Talks to Backend/server.py. Same origin by default; override with ?api=http://host:5050
// or window.BIFAS_API for a separately hosted frontend.

export const API = (new URLSearchParams(location.search).get("api") || window.BIFAS_API || "").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json", Accept: "application/json" } : { Accept: "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (err) {
    throw new ApiError("offline", 0);
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty or non-JSON body */ }
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : `The server returned HTTP ${res.status}.`;
    throw new ApiError(detail, res.status);
  }
  return data;
}

export const getMeta = () => request("GET", "/api/meta");
export const getPreview = (query, session) =>
  request("GET", `/api/preview?${new URLSearchParams({ query, ...(session ? { session } : {}) })}`);
export const listSessions = () => request("GET", "/api/sessions");
export const createSession = (title) => request("POST", "/api/sessions", title ? { title } : {});
export const getSession = (id) => request("GET", `/api/sessions/${encodeURIComponent(id)}`);
export const renameSession = (id, title) => request("PATCH", `/api/sessions/${encodeURIComponent(id)}`, { title });
export const deleteSession = (id) => request("DELETE", `/api/sessions/${encodeURIComponent(id)}`);
export const deleteBriefing = (sid, bid) =>
  request("DELETE", `/api/sessions/${encodeURIComponent(sid)}/briefings/${encodeURIComponent(bid)}`);

/**
 * Run an analysis and call onEvent(type, data) for each Server-Sent Event.
 * Aborting `signal` hangs up, which makes the server cancel the run.
 * Resolves when the stream ends; rejects with ApiError on HTTP/network failure.
 */
export async function streamAnalyze({ query, depth, session, context }, onEvent, signal) {
  const params = new URLSearchParams({ query, depth });
  if (session) params.set("session", session);
  if (context === false) params.set("context", "0");
  let res;
  try {
    res = await fetch(`${API}/api/analyze?${params}`, { headers: { Accept: "text/event-stream" }, signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new ApiError("offline", 0);
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail; } catch (e) { /* not JSON */ }
    throw new ApiError(typeof detail === "string" && detail ? detail
      : res.status === 429 ? "Too many analyses are running. Try again in a minute."
      : `The server rejected the request (HTTP ${res.status}).`, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let split;
    while ((split = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      let type = "message";
      const lines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) type = line.slice(6).trim();
        else if (line.startsWith("data:")) lines.push(line.slice(5).trimStart());
      }
      if (!lines.length) continue; // keep-alive comment
      let data;
      try { data = JSON.parse(lines.join("\n")); } catch (e) { continue; }
      onEvent(type, data);
    }
  }
}

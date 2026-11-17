// JSON client for the GUI backend. All URLs are relative (no leading slash): the page sits below an ingress path.

export class ApiClientError extends Error {
  constructor(status, code, message) {
    super(message || code || `HTTP ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
  }
}

// encodeURIComponent keeps * and a few other marks; encode them too so topic wildcards are unambiguous.
const enc = (s) => encodeURIComponent(s).replace(/[!'()*]/g, (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`);

export function buildUrl(path, query) {
  if (typeof path !== "string" || path === "" || path.startsWith("/") || /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(path)) {
    throw new Error(`absolute or empty API path rejected: ${path}`);
  }
  let url = `api/${path.split("/").map(enc).join("/")}`;
  const parts = [];
  for (const [key, value] of Object.entries(query || {})) {
    if (value === null || value === undefined) continue;
    parts.push(`${enc(key)}=${enc(String(value))}`);
  }
  if (parts.length) url += `?${parts.join("&")}`;
  return url;
}

export async function request(method, path, { query, body, fetchImpl } = {}) {
  const doFetch = fetchImpl || ((...args) => fetch(...args));
  const headers = { Accept: "application/json" };
  const init = { method, headers, credentials: "same-origin", cache: "no-store" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let resp;
  try {
    resp = await doFetch(buildUrl(path, query), init);
  } catch (err) {
    throw new ApiClientError(0, "network_error", `network error: ${err && err.message ? err.message : err}`);
  }
  if (resp.status === 204) return null;
  let data = null;
  try {
    data = await resp.json();
  } catch {
    data = null;
  }
  if (!resp.ok) {
    const code = (data && data.error) || "http_error";
    throw new ApiClientError(resp.status, code, (data && data.message) || `HTTP ${resp.status}`);
  }
  return data;
}

export const get = (path, opts = {}) => request("GET", path, opts);
export const post = (path, opts = {}) => request("POST", path, opts);
export const put = (path, opts = {}) => request("PUT", path, opts);
export const patch = (path, opts = {}) => request("PATCH", path, opts);
export const del = (path, opts = {}) => request("DELETE", path, opts);

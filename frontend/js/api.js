// Thin wrapper over fetch for the same-origin JSON API.
// Every failure becomes an ApiError with the server's stable `code` and per-field
// reason codes, which the pages translate themselves (see i18n keys "error.*").

export class ApiError extends Error {
  constructor(status, { code = 'NETWORK', fields = {}, retry_after: retryAfter = null } = {}) {
    super(code);
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfter = retryAfter;
  }
}

export async function api(method, path, body) {
  const init = { method, credentials: 'same-origin', headers: {} };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0);
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* not JSON: handled below */ }
  if (!res.ok) throw new ApiError(res.status, data?.error ?? { code: 'HTTP_ERROR' });
  return data;
}

export const get = (path) => api('GET', path);
export const post = (path, body) => api('POST', path, body);
export const put = (path, body) => api('PUT', path, body);
export const del = (path, body) => api('DELETE', path, body);

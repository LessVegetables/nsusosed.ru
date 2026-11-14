// Thin wrapper over fetch for the same-origin JSON API.
// Every failure becomes an ApiError with the server's stable `code` and per-field
// reason codes, which the pages translate themselves (see i18n keys "error.*").

import { report, routeOf } from './errors.js';

export class ApiError extends Error {
  constructor(status, { code = 'NETWORK', fields = {}, retry_after: retryAfter = null, data = {} } = {}) {
    super(code);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfter = retryAfter;
    this.data = data; // extra facts for some errors, e.g. { room_id } for ROOM_TAKEN
  }
}

export async function api(method, path, body) {
  const init = { method, credentials: 'same-origin', headers: {} };
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.keepalive = true; // an autosave sent while the page is being left still arrives
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
  if (!res.ok) {
    const err = new ApiError(res.status, data?.error ?? { code: 'HTTP_ERROR' });
    if (res.status >= 500 || !data?.error) reportServerError(method, path, err);
    throw err;
  }
  return data;
}

// The pages show a friendly message for every failure, so a broken endpoint would go unnoticed.
// 4xx answers with an error code are the API working as designed and aren't reported; network
// failures (status 0) are the visitor's connection and aren't either.
function reportServerError(method, path, err) {
  const route = routeOf(path);
  const error = new Error(`${method} ${route} → ${err.status} ${err.code}`);
  error.name = 'ApiServerError';
  report(error, {
    tags: { route: `${method} ${route}`, status: String(err.status), code: err.code },
    fingerprint: ['api', method, route, String(err.status)],
  });
}

export const get = (path) => api('GET', path);
export const post = (path, body) => api('POST', path, body);
export const put = (path, body) => api('PUT', path, body);
export const del = (path, body) => api('DELETE', path, body);

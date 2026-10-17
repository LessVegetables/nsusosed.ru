// The only module that talks to the backend. Every endpoint the frontend uses
// is listed at the bottom, so this file doubles as a map of the API.
//
// Errors: every failed call throws ApiError with a `code` (see errors.js).
// The backend always answers {"error": {code, message, fields, request_id,
// retry_after}}; if something in between (nginx, the network) answers instead,
// we make up a code from the HTTP status.

import { API_BASE, USE_MOCK } from './config.js';

export class ApiError extends Error {
  constructor(status, error = {}) {
    super(error.code || 'UNKNOWN');
    this.name = 'ApiError';
    this.status = status;
    this.code = error.code || 'UNKNOWN';
    this.fields = error.fields || {};
    this.retryAfter = error.retry_after ?? null;
    this.requestId = error.request_id || '';
  }
}

function codeForStatus(status) {
  if (status === 401) return 'AUTH_REQUIRED';
  if (status === 403) return 'FORBIDDEN';
  if (status === 404) return 'NOT_FOUND';
  if (status === 413) return 'PAYLOAD_TOO_LARGE';
  if (status === 429) return 'RATE_LIMITED';
  if (status === 502 || status === 503 || status === 504) return 'SERVICE_UNAVAILABLE';
  if (status >= 500) return 'INTERNAL_ERROR';
  return 'UNKNOWN';
}

function toResult(status, data, retryAfterHeader) {
  if (status >= 200 && status < 300) return status === 204 ? null : data;
  if (data && data.error && data.error.code) throw new ApiError(status, data.error);
  const retry = Number(retryAfterHeader);
  throw new ApiError(status, {
    code: codeForStatus(status),
    retry_after: Number.isFinite(retry) && retry > 0 ? retry : null,
  });
}

let mockHandle = null;

async function request(method, path, body) {
  if (USE_MOCK) {
    // Loaded only when the mock is on, so production never downloads it.
    mockHandle ??= (await import('./mock/server.js')).handle;
    const { status, data } = await mockHandle(method, path, body);
    return toResult(status, data);
  }

  const headers = { Accept: 'application/json' };
  const init = { method, headers, credentials: 'same-origin', cache: 'no-store' };
  if (body instanceof FormData) {
    init.body = body; // The browser sets multipart/form-data with its boundary.
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(API_BASE + path, init);
  } catch {
    throw new ApiError(0, { code: 'NETWORK_ERROR' });
  }

  let data = null;
  if (res.status !== 204) {
    try {
      data = await res.json();
    } catch {
      data = null; // Not JSON: an nginx error page, for example.
    }
  }
  return toResult(res.status, data, res.headers.get('Retry-After'));
}

const enc = encodeURIComponent;

export const api = {
  // Auth
  requestCode: (email, privacyAccepted) =>
    request('POST', '/auth/request-code', { email, privacy_accepted: privacyAccepted }),
  verifyCode: (email, code) => request('POST', '/auth/verify-code', { email, code }),
  logout: () => request('POST', '/auth/logout'),

  // Account
  getMe: () => request('GET', '/me'),
  // {display_name} and/or {language}
  updateMe: (changes) => request('PUT', '/me', changes),
  deleteMe: (confirm) => request('DELETE', '/me', { confirm }),

  // Questionnaire
  getQuestions: () => request('GET', '/questions'),
  getProfile: () => request('GET', '/profile'),
  saveProfile: (payload) => request('PUT', '/profile', payload),

  // The user's home (they live there; admins can change it)
  getMyListing: () => request('GET', '/listings/mine'),
  createListing: (payload) => request('POST', '/listings', payload),
  updateListing: (id, payload) => request('PUT', `/listings/${enc(id)}`, payload),
  deleteListing: (id) => request('DELETE', `/listings/${enc(id)}`),
  createInvite: (id, expectedVersion) =>
    request('POST', `/listings/${enc(id)}/invite`, { expected_version: expectedVersion }),
  confirmListing: (id, expectedVersion) =>
    request('POST', `/listings/${enc(id)}/confirm`, { expected_version: expectedVersion }),
  addPhoto: (id, file) => {
    const form = new FormData();
    form.append('file', file);
    return request('POST', `/listings/${enc(id)}/photos`, form);
  },
  deletePhoto: (id, photoId) => request('DELETE', `/listings/${enc(id)}/photos/${enc(photoId)}`),
  reorderPhotos: (id, photoIds) => request('PUT', `/listings/${enc(id)}/photos/order`, { photo_ids: photoIds }),

  // Residents
  joinRoom: (inviteToken) => request('POST', '/memberships/join', { invite_token: inviteToken }),
  leaveRoom: () => request('DELETE', '/membership'),
  makeAdmin: (id, userId) => request('POST', `/listings/${enc(id)}/admins/${enc(userId)}`, {}),
  removeAdmin: (id, userId) => request('DELETE', `/listings/${enc(id)}/admins/${enc(userId)}`),
  removeResident: (id, userId) => request('DELETE', `/listings/${enc(id)}/members/${enc(userId)}`),

  // Matching. includeUnmatched also returns places that break a hard
  // condition or the budget (fits: false, with reasons).
  getMatches: (kind, offset, limit, includeUnmatched = false) =>
    request('GET', `/matches?kind=${enc(kind)}&offset=${enc(offset)}&limit=${enc(limit)}`
      + (includeUnmatched ? '&include_unmatched=true' : '')),
  getListing: (id) => request('GET', `/listings/${enc(id)}`),
  getContact: (id) => request('GET', `/listings/${enc(id)}/contact`),
};

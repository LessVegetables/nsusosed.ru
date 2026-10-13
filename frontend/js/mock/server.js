// Mock API: a fake backend that runs in the browser, for working on the
// frontend without FastAPI and Postgres. It follows the API contract in
// frontend/README.md, including error codes, versions and the matching formula.
//
// On: open any page on localhost with ?mock=1. Off: ?mock=0.
// The data lives in localStorage ("nsusosed.mockdb"); the banner's "Turn off"
// link keeps it, and resetMockDb() in the console starts over.
//
// Not loaded at all unless the mock is on (see api.js).

import { MOCK_LOGIN_CODE } from '../config.js';
import { local } from '../storage.js';
import QUESTIONNAIRE from './questionnaire.js';
import { seedDb } from './seed.js';

const DB_KEY = 'nsusosed.mockdb';
const LATENCY_MS = 300;
const OTP_TTL_S = 120;
const RESEND_COOLDOWN_S = 60;
const LISTING_TTL_DAYS = 30;
const INVITE_TTL_DAYS = 7;
const DAY_MS = 86_400_000;
const THRESHOLDS = { similar: 0.85, minor_difference: 0.6 };
const DISPERSION_THRESHOLD = 3;
const Q = Object.fromEntries(QUESTIONNAIRE.questions.map((q) => [q.key, q]));
const KEYS = QUESTIONNAIRE.questions.map((q) => q.key);

class MockError extends Error {
  constructor(status, code, fields = {}, retryAfter = null) {
    super(code);
    this.status = status;
    this.code = code;
    this.fields = fields;
    this.retryAfter = retryAfter;
  }
}

const fail = (status, code, fields, retryAfter) => {
  throw new MockError(status, code, fields, retryAfter);
};
const invalid = (fields) => fail(422, 'VALIDATION_ERROR', fields);
const now = () => new Date();
const iso = (date) => date.toISOString();
const newId = () => crypto.randomUUID();

function loadDb() {
  try {
    const raw = local.get(DB_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // Broken JSON: start over.
  }
  return seedDb(QUESTIONNAIRE);
}

function saveDb(db) {
  local.set(DB_KEY, JSON.stringify(db));
}

window.resetMockDb = () => {
  local.remove(DB_KEY);
  location.reload();
};

// ------------------------------------------------------------- helpers

function currentUser(db) {
  const user = db.session && db.users[db.session];
  if (!user) fail(401, 'AUTH_REQUIRED');
  return user;
}

function membersOf(db, listingId) {
  return Object.entries(db.memberships).filter(([, lid]) => lid === listingId).map(([uid]) => uid);
}

function residentsBrief(db, listingId) {
  return membersOf(db, listingId).map((uid) => ({
    display_name: db.users[uid]?.display_name ?? 'Пользователь',
    profile_complete: Boolean(db.profiles[uid]),
  }));
}

function ownerDto(db, l) {
  const residents = residentsBrief(db, l.id);
  const { invite_token: _t, invite_expires_at: _e, ...rest } = l;
  return {
    ...rest,
    free_places: l.capacity - l.occupied_count,
    answered_count: residents.filter((r) => r.profile_complete).length,
    residents,
    expires_at: iso(new Date(new Date(l.confirmed_at).getTime() + LISTING_TTL_DAYS * DAY_MS)),
  };
}

function isVisible(l) {
  const fresh = now() - new Date(l.confirmed_at) <= LISTING_TTL_DAYS * DAY_MS;
  return l.status === 'active' && fresh && l.capacity - l.occupied_count > 0;
}

// ------------------------------------------------------------- matching
// Same formula as backend/app/services/matching_service.py.

function checkHard(candidate, resident) {
  return KEYS.every((key) => {
    const c = candidate[key];
    const r = resident[key];
    if (c.hard && !c.allowed.includes(r.value)) return false;
    if (r.hard && !r.allowed.includes(c.value)) return false;
    return true;
  });
}

function compatibility(candidate, residents, occupied) {
  const n = residents.length;
  const dims = [];
  let num = 0;
  let den = 0;
  for (const key of KEYS) {
    const div = Q[key].normalize_divisor;
    const c = candidate[key];
    const roomVal = residents.reduce((s, r) => s + r[key].value / div, 0) / n;
    const roomImp = residents.reduce((s, r) => s + r[key].importance, 0) / n;
    const weight = (c.importance + roomImp) / 2;
    const similarity = 1 - Math.abs(c.value / div - roomVal);
    num += weight * similarity;
    den += weight;
    const label = similarity >= THRESHOLDS.similar ? 'similar'
      : similarity >= THRESHOLDS.minor_difference ? 'minor_difference' : 'noticeable_difference';
    dims.push({ key, candidate_value: c.value, room_average: roomVal * div, similarity, weight, contribution_points: 0, label });
  }
  const scoreRaw = den > 0 ? (100 * num) / den : 0;
  for (const d of dims) d.contribution_points = den > 0 ? (100 * d.weight * d.similarity) / den : 0;

  const warnings = [];
  if (n < occupied) warnings.push({ code: 'PARTIAL_ANSWERS', answered: n, occupied });
  for (const key of KEYS) {
    const values = residents.map((r) => r[key].value);
    const spread = Math.max(...values) - Math.min(...values);
    if ((key === 'smoking' && spread > 0) || (key !== 'smoking' && spread >= DISPERSION_THRESHOLD)) {
      warnings.push({ code: 'RESIDENTS_DISAGREE', key });
      break;
    }
  }
  return { score: Math.floor(scoreRaw + 0.5), score_raw: scoreRaw, score_version: 1, warnings, dimensions: dims };
}

// Compatibility of `user` with listing `l`, or null if hard conditions/budget hide it.
function matchFor(db, user, l) {
  const me = db.profiles[user.id];
  const answers = membersOf(db, l.id).map((uid) => db.profiles[uid]?.answers).filter(Boolean);
  if (!answers.length) return null;
  if (l.kind === 'apartment' && l.monthly_cost_per_person_rub > me.budget_max_rub) return null;
  if (!answers.every((a) => checkHard(me.answers, a))) return null;
  return compatibility(me.answers, answers, l.occupied_count);
}

// ------------------------------------------------------------- validation

const TELEGRAM_RE = /^[a-zA-Z][a-zA-Z0-9_]{4,31}$/;

function normalizeContact(type, rawValue) {
  const value = String(rawValue ?? '').trim();
  if (!['telegram', 'whatsapp', 'max', 'phone', 'other'].includes(type)) return [null, 'INVALID_CHOICE'];
  if (type === 'telegram') {
    const name = value.replace(/^(https?:\/\/)?(t\.me|telegram\.me)\//i, '').replace(/^@/, '');
    return TELEGRAM_RE.test(name) ? [name, null] : [null, 'INVALID_TELEGRAM'];
  }
  if (type === 'phone' || type === 'whatsapp') {
    let digits = value.replace(/\D/g, '');
    if (!value.startsWith('+') && digits.length === 11 && digits[0] === '8') digits = `7${digits.slice(1)}`;
    return digits.length >= 10 && digits.length <= 15 ? [`+${digits}`, null] : [null, 'INVALID_PHONE'];
  }
  if (!value) return [null, 'REQUIRED'];
  if (value.length > 100) return [null, 'TOO_LONG'];
  return [value, null];
}

function contactUrl(type, value) {
  if (type === 'telegram') return `https://t.me/${value}`;
  if (type === 'whatsapp') return `https://wa.me/${value.replace(/^\+/, '')}`;
  if (type === 'phone') return `tel:${value}`;
  return null;
}

function intIn(errors, body, name, min, max, required) {
  const v = body[name];
  if (v == null) {
    if (required) errors[name] = 'MISSING';
    return;
  }
  if (!Number.isInteger(v)) errors[name] = 'INT_PARSING';
  else if (v < min) errors[name] = 'GREATER_THAN_EQUAL';
  else if (v > max) errors[name] = 'LESS_THAN_EQUAL';
}

function validateListing(kind, body) {
  const errors = {};
  intIn(errors, body, 'capacity', 1, 10, true);
  intIn(errors, body, 'occupied_count', 1, 10, true);
  if (kind === 'dorm') {
    for (const f of ['building', 'room_number', 'floor']) if (body[f] == null || body[f] === '') errors[f] = 'REQUIRED';
    intIn(errors, body, 'room_number', 1, 999);
    intIn(errors, body, 'floor', 1, 999);
    intIn(errors, body, 'windows_count', 1, 5);
    if (body.view != null && !['forest', 'road', 'yard', 'other', 'unknown'].includes(body.view)) errors.view = 'INVALID_CHOICE';
    for (const f of ['district', 'monthly_cost_per_person_rub']) if (body[f] != null) errors[f] = 'MUST_BE_EMPTY';
  } else if (kind === 'apartment') {
    for (const f of ['district', 'monthly_cost_per_person_rub']) if (body[f] == null) errors[f] = 'REQUIRED';
    intIn(errors, body, 'monthly_cost_per_person_rub', 1, 200000);
  } else errors.kind = 'INVALID_CHOICE';
  if (body.description && body.description.length > 1000) errors.description = 'STRING_TOO_LONG';
  if (!errors.capacity && !errors.occupied_count && body.occupied_count > body.capacity) errors.occupied_count = 'EXCEEDS_CAPACITY';
  const [contact, reason] = normalizeContact(body.contact_type, body.contact_value);
  if (reason) errors[reason === 'INVALID_CHOICE' ? 'contact_type' : 'contact_value'] = reason;
  if (body.status && !['active', 'paused'].includes(body.status)) errors.status = 'INVALID_CHOICE';
  if (Object.keys(errors).length) invalid(errors);
  return contact;
}

function listingFields(kind, body, contact) {
  const f = {
    capacity: body.capacity,
    occupied_count: body.occupied_count,
    description: body.description || null,
    contact_type: body.contact_type,
    contact_value: contact,
    building: null, room_number: null, floor: null, is_corner: null, windows_count: null, view: null, layout: null,
    district: null, monthly_cost_per_person_rub: null,
  };
  if (kind === 'dorm') {
    Object.assign(f, {
      building: String(body.building).trim().toUpperCase(), room_number: body.room_number, floor: body.floor,
      is_corner: body.is_corner ?? null, windows_count: body.windows_count ?? null, view: body.view ?? null, layout: body.layout || null,
    });
  } else {
    Object.assign(f, { district: body.district, monthly_cost_per_person_rub: body.monthly_cost_per_person_rub });
  }
  return f;
}

function ownListing(db, user, id) {
  const l = db.listings[id];
  if (!l) fail(404, 'NOT_FOUND');
  if (l.owner_id !== user.id) fail(403, 'FORBIDDEN');
  return l;
}

function checkVersion(l, expected) {
  if (expected !== l.version) fail(409, 'VERSION_CONFLICT');
}

// ------------------------------------------------------------- routes

const routes = [
  ['POST', /^\/auth\/request-code$/, (db, body) => {
    const email = String(body.email ?? '').trim().toLowerCase();
    if (!email.includes('@')) invalid({ email: 'INVALID_EMAIL' });
    if (!email.endsWith('@g.nsu.ru')) invalid({ email: 'DOMAIN_NOT_ALLOWED' });
    if (body.privacy_accepted !== true) invalid({ privacy_accepted: 'MUST_ACCEPT' });
    const last = db.otp[email];
    const wait = last ? Math.ceil(RESEND_COOLDOWN_S - (now() - new Date(last)) / 1000) : 0;
    if (wait > 0) fail(429, 'RATE_LIMITED', {}, wait);
    db.otp[email] = iso(now());
    console.info(`[mock] login code for ${email}: ${MOCK_LOGIN_CODE}`);
    const [name, domain] = email.split('@');
    return { message: 'Код отправлен на почту', email_masked: `${name[0]}***@${domain}`, ttl_seconds: OTP_TTL_S };
  }],

  ['POST', /^\/auth\/verify-code$/, (db, body) => {
    const email = String(body.email ?? '').trim().toLowerCase();
    const sent = db.otp[email];
    const fresh = sent && (now() - new Date(sent)) / 1000 <= OTP_TTL_S;
    if (!fresh || String(body.code).trim() !== MOCK_LOGIN_CODE) fail(401, 'INVALID_CODE');
    delete db.otp[email];
    let user = Object.values(db.users).find((u) => u.email === email);
    if (!user) {
      user = { id: newId(), email, display_name: 'Пользователь' };
      db.users[user.id] = user;
    }
    db.session = user.id;
    return { user, profile_complete: Boolean(db.profiles[user.id]) };
  }],

  ['POST', /^\/auth\/logout$/, (db) => {
    db.session = null;
    return null;
  }],

  ['GET', /^\/me$/, (db) => currentUser(db)],

  ['PUT', /^\/me$/, (db, body) => {
    const user = currentUser(db);
    const name = String(body.display_name ?? '');
    if (name.length < 2) invalid({ display_name: 'STRING_TOO_SHORT' });
    if (name.length > 60) invalid({ display_name: 'STRING_TOO_LONG' });
    user.display_name = name;
    return user;
  }],

  ['DELETE', /^\/me$/, (db, body) => {
    const user = currentUser(db);
    if (body.confirm !== 'DELETE') fail(422, 'VALIDATION_ERROR', { confirm: 'MUST_BE_DELETE' });
    for (const l of Object.values(db.listings)) {
      if (l.owner_id === user.id) {
        for (const uid of membersOf(db, l.id)) delete db.memberships[uid];
        delete db.listings[l.id];
      }
    }
    delete db.memberships[user.id];
    delete db.profiles[user.id];
    delete db.users[user.id];
    db.session = null;
    return null;
  }],

  ['GET', /^\/questions$/, () => QUESTIONNAIRE],

  ['GET', /^\/profile$/, (db) => ({ profile: db.profiles[currentUser(db).id] ?? null })],

  ['PUT', /^\/profile$/, (db, body) => {
    const user = currentUser(db);
    const current = db.profiles[user.id];
    const errors = {};
    if (body.questionnaire_version !== 1) errors.questionnaire_version = 'UNSUPPORTED_VERSION';
    if (!['looking', 'dorm_resident', 'apartment_host'].includes(body.situation)) errors.situation = 'INVALID_CHOICE';
    intIn(errors, body, 'budget_max_rub', 1, 200000);
    const answers = body.answers ?? {};
    if (Object.keys(answers).sort().join() !== [...KEYS].sort().join()) errors.answers = 'INVALID_QUESTION_SET';
    else {
      for (const key of KEYS) {
        const a = answers[key];
        const { min_value: min, max_value: max } = Q[key];
        if (!Number.isInteger(a.value) || a.value < min || a.value > max) errors[`answers.${key}.value`] = 'OUT_OF_SCALE';
        if (!Number.isInteger(a.importance) || a.importance < 1 || a.importance > 10) errors[`answers.${key}.importance`] = 'LESS_THAN_EQUAL';
        if (a.hard && !a.allowed.length) errors[`answers.${key}.allowed`] = 'REQUIRED_WHEN_HARD';
        if (!a.hard && a.allowed.length) errors[`answers.${key}.allowed`] = 'MUST_BE_EMPTY';
      }
    }
    if (Object.keys(errors).length) invalid(errors);
    if (body.expected_version !== (current?.version ?? 0)) fail(409, 'VERSION_CONFLICT');
    const profile = {
      user_id: user.id,
      questionnaire_version: 1,
      answers,
      situation: body.situation,
      budget_max_rub: body.budget_max_rub ?? null,
      version: (current?.version ?? 0) + 1,
      updated_at: iso(now()),
    };
    db.profiles[user.id] = profile;
    return profile;
  }],

  ['GET', /^\/listings\/mine$/, (db) => {
    const user = currentUser(db);
    const l = Object.values(db.listings).find((x) => x.owner_id === user.id);
    return { item: l ? ownerDto(db, l) : null };
  }],

  ['POST', /^\/listings$/, (db, body) => {
    const user = currentUser(db);
    const contact = validateListing(body.kind, body);
    if (!db.profiles[user.id]) fail(422, 'PROFILE_REQUIRED');
    if (Object.values(db.listings).some((x) => x.owner_id === user.id)) fail(409, 'LISTING_EXISTS');
    if (db.memberships[user.id]) fail(409, 'ALREADY_IN_ROOM');
    const fields = listingFields(body.kind, body, contact);
    if (body.kind === 'dorm' && Object.values(db.listings).some((x) => x.building === fields.building && x.room_number === fields.room_number)) {
      fail(409, 'ROOM_TAKEN');
    }
    const l = {
      id: newId(), owner_id: user.id, kind: body.kind, ...fields, status: 'active', version: 1,
      confirmed_at: iso(now()), created_at: iso(now()), invite_token: null, invite_expires_at: null,
    };
    db.listings[l.id] = l;
    db.memberships[user.id] = l.id;
    return { status: 201, data: ownerDto(db, l) };
  }],

  ['PUT', /^\/listings\/([\w-]+)$/, (db, body, [id]) => {
    const user = currentUser(db);
    const l = ownListing(db, user, id);
    checkVersion(l, body.expected_version);
    if (body.occupied_count < membersOf(db, l.id).length) fail(409, 'OCCUPANCY_CONFLICT');
    const contact = validateListing(l.kind, body);
    const fields = listingFields(l.kind, body, contact);
    if (l.kind === 'dorm' && Object.values(db.listings).some((x) => x.id !== l.id && x.building === fields.building && x.room_number === fields.room_number)) {
      fail(409, 'ROOM_TAKEN');
    }
    Object.assign(l, fields);
    l.status = l.capacity - l.occupied_count <= 0 ? 'paused' : (body.status || 'active');
    if (l.status === 'active') l.confirmed_at = iso(now());
    l.version += 1;
    return ownerDto(db, l);
  }],

  ['DELETE', /^\/listings\/([\w-]+)$/, (db, body, [id]) => {
    const l = ownListing(db, currentUser(db), id);
    for (const uid of membersOf(db, l.id)) delete db.memberships[uid];
    delete db.listings[l.id];
    return null;
  }],

  ['POST', /^\/listings\/([\w-]+)\/confirm$/, (db, body, [id]) => {
    const l = ownListing(db, currentUser(db), id);
    checkVersion(l, body.expected_version);
    l.confirmed_at = iso(now());
    if (l.capacity - l.occupied_count > 0) l.status = 'active';
    l.version += 1;
    return ownerDto(db, l);
  }],

  ['POST', /^\/listings\/([\w-]+)\/invite$/, (db, body, [id]) => {
    const l = ownListing(db, currentUser(db), id);
    checkVersion(l, body.expected_version);
    l.invite_token = crypto.randomUUID().replace(/-/g, '');
    l.invite_expires_at = iso(new Date(Date.now() + INVITE_TTL_DAYS * DAY_MS));
    l.version += 1;
    return { invite_url: `${location.origin}/join#token=${l.invite_token}`, expires_at: l.invite_expires_at, version: l.version };
  }],

  ['POST', /^\/memberships\/join$/, (db, body) => {
    const user = currentUser(db);
    if (!db.profiles[user.id]) fail(422, 'PROFILE_REQUIRED');
    const l = Object.values(db.listings).find((x) => x.invite_token && x.invite_token === body.invite_token);
    if (!l) fail(404, 'INVITE_INVALID');
    if (new Date(l.invite_expires_at) < now()) fail(404, 'INVITE_EXPIRED');
    if (db.memberships[user.id] === l.id) return { listing_id: l.id, version: l.version };
    if (db.memberships[user.id]) fail(409, 'ALREADY_IN_ROOM');
    if (membersOf(db, l.id).length >= l.occupied_count) fail(409, 'ROOM_FULL');
    db.memberships[user.id] = l.id;
    l.version += 1;
    return { listing_id: l.id, version: l.version };
  }],

  ['DELETE', /^\/membership$/, (db) => {
    const user = currentUser(db);
    const lid = db.memberships[user.id];
    if (!lid) return null;
    if (db.listings[lid]?.owner_id === user.id) fail(403, 'OWNER_CANNOT_LEAVE');
    delete db.memberships[user.id];
    if (db.listings[lid]) db.listings[lid].version += 1;
    return null;
  }],

  ['GET', /^\/matches$/, (db, body, groups, query) => {
    const user = currentUser(db);
    const kind = query.get('kind');
    const offset = Number(query.get('offset') ?? 0);
    const limit = Number(query.get('limit') ?? 20);
    if (!['dorm', 'apartment'].includes(kind)) invalid({ 'query.kind': 'STRING_PATTERN_MISMATCH' });
    const me = db.profiles[user.id];
    if (!me) fail(422, 'PROFILE_REQUIRED');
    if (kind === 'apartment' && me.budget_max_rub == null) fail(422, 'BUDGET_REQUIRED');
    const items = [];
    for (const l of Object.values(db.listings)) {
      if (l.kind !== kind || !isVisible(l) || db.memberships[user.id] === l.id) continue;
      const compat = matchFor(db, user, l);
      if (!compat) continue;
      const answered = membersOf(db, l.id).filter((uid) => db.profiles[uid]).length;
      items.push({
        id: l.id, kind: l.kind, building: l.building, room_number: l.room_number, district: l.district,
        free_places: l.capacity - l.occupied_count, answered_count: answered, occupied_count: l.occupied_count,
        compatibility: compat,
      });
    }
    items.sort((a, b) => b.compatibility.score_raw - a.compatibility.score_raw);
    return { items: items.slice(offset, offset + limit), total: items.length, offset, limit, score_version: 1 };
  }],

  ['GET', /^\/listings\/([\w-]+)$/, (db, body, [id]) => {
    const user = currentUser(db);
    const l = db.listings[id];
    if (!l) fail(404, 'NOT_FOUND');
    const own = l.owner_id === user.id || db.memberships[user.id] === l.id;
    const residents = residentsBrief(db, l.id);
    const { owner_id: _o, contact_type: _ct, contact_value: _cv, invite_token: _t, invite_expires_at: _e, created_at: _c, ...rest } = l;
    const detail = {
      ...rest, free_places: l.capacity - l.occupied_count,
      answered_count: residents.filter((r) => r.profile_complete).length, residents, compatibility: null,
    };
    if (own) return detail;
    if (!isVisible(l)) fail(404, 'NOT_FOUND');
    const me = db.profiles[user.id];
    if (!me) fail(422, 'PROFILE_REQUIRED');
    if (l.kind === 'apartment' && me.budget_max_rub == null) fail(422, 'BUDGET_REQUIRED');
    detail.compatibility = matchFor(db, user, l);
    if (!detail.compatibility) fail(404, 'NOT_FOUND');
    return detail;
  }],

  ['GET', /^\/listings\/([\w-]+)\/contact$/, (db, body, [id]) => {
    const user = currentUser(db);
    const l = db.listings[id];
    if (!l) fail(404, 'NOT_FOUND');
    const own = l.owner_id === user.id || db.memberships[user.id] === l.id;
    if (!own && (!isVisible(l) || !db.profiles[user.id] || !matchFor(db, user, l))) fail(404, 'NOT_FOUND');
    return { type: l.contact_type, value: l.contact_value, url: contactUrl(l.contact_type, l.contact_value) };
  }],
];

export async function handle(method, path, body) {
  await new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
  const url = new URL(path, 'http://mock');
  const db = loadDb();
  try {
    for (const [m, re, fn] of routes) {
      const match = m === method && url.pathname.match(re);
      if (!match) continue;
      const result = fn(db, body ?? {}, match.slice(1), url.searchParams);
      saveDb(db);
      if (result && typeof result === 'object' && 'status' in result && 'data' in result) return result;
      return { status: result === null ? 204 : 200, data: result };
    }
    fail(404, 'NOT_FOUND');
  } catch (err) {
    if (!(err instanceof MockError)) throw err;
    saveDb(db); // Keep side effects such as the resend timer.
    return {
      status: err.status,
      data: {
        error: { code: err.code, message: 'mock', fields: err.fields, request_id: `mock-${Date.now()}`, retry_after: err.retryAfter },
      },
    };
  }
}

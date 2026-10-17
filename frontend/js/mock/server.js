// Mock API: a fake backend that runs in the browser, for working on the
// frontend without FastAPI and Postgres. It follows the API contract in
// backend/README.md, including error codes, versions and the matching formula.
// Photos are shrunk and kept as data URLs.
//
// On: open any page on localhost with ?mock=1. Off: ?mock=0.
// The data lives in localStorage ("nsusosed.mockdb.v2"); the banner's "Turn off"
// link keeps it, and resetMockDb() in the console starts over.
//
// Not loaded at all unless the mock is on (see api.js).

import { MOCK_LOGIN_CODE } from '../config.js';
import { local } from '../storage.js';
import QUESTIONNAIRE from './questionnaire.js';
import { seedDb } from './seed.js';

const DB_KEY = 'nsusosed.mockdb.v2'; // v2: homes with admins, contacts, photos
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

function meDto(db, user) {
  const profile = db.profiles[user.id];
  const m = db.memberships[user.id];
  return {
    ...user,
    situation: profile?.situation ?? null,
    profile_complete: Boolean(profile) && profile.questionnaire_version === QUESTIONNAIRE.version,
    home: m ? { id: m.listing_id, is_admin: m.is_admin } : null,
  };
}

// Members of a home, longest-standing first.
function membersOf(db, listingId) {
  return Object.entries(db.memberships)
    .filter(([, m]) => m.listing_id === listingId)
    .sort(([, a], [, b]) => a.joined_at.localeCompare(b.joined_at))
    .map(([uid]) => uid);
}

function residentsOf(db, listingId) {
  return membersOf(db, listingId).map((uid) => ({
    user_id: uid,
    display_name: db.users[uid]?.display_name ?? 'Пользователь',
    profile_complete: Boolean(db.profiles[uid]),
    is_admin: db.memberships[uid].is_admin,
    joined_at: db.memberships[uid].joined_at,
  }));
}

function contactsOut(l) {
  return l.contacts.map((c) => ({ ...c, url: contactUrl(c.type, c.value) }));
}

function homeDto(db, l, user) {
  const residents = residentsOf(db, l.id);
  const { invite_token: _t, invite_expires_at: _e, ...rest } = l;
  return {
    ...rest,
    contacts: contactsOut(l),
    free_places: l.capacity - l.occupied_count,
    answered_count: residents.filter((r) => r.profile_complete).length,
    residents,
    you_are_admin: Boolean(db.memberships[user.id]?.is_admin && db.memberships[user.id].listing_id === l.id),
    expires_at: iso(new Date(new Date(l.confirmed_at).getTime() + LISTING_TTL_DAYS * DAY_MS)),
  };
}

function isVisible(l) {
  const fresh = now() - new Date(l.confirmed_at) <= LISTING_TTL_DAYS * DAY_MS;
  return l.status === 'active' && fresh && l.capacity - l.occupied_count > 0;
}

// Same rules as backend/app/services/membership_service.py: the last admin
// leaving promotes the longest-standing member (one with a questionnaire
// first); the last member leaving deletes the home.
function removeMember(db, uid) {
  const m = db.memberships[uid];
  if (!m) return;
  delete db.memberships[uid];
  const l = db.listings[m.listing_id];
  const rest = membersOf(db, m.listing_id);
  if (!rest.length) {
    delete db.listings[m.listing_id];
    return;
  }
  if (!rest.some((id) => db.memberships[id].is_admin)) {
    const heir = rest.find((id) => db.profiles[id]) ?? rest[0];
    db.memberships[heir].is_admin = true;
  }
  l.version += 1;
}

// ------------------------------------------------------------- matching
// Same formula as backend/app/services/matching_service.py. A question that
// one side hasn't answered (older questionnaire) is skipped.

function hardConflicts(candidate, resident) {
  const out = [];
  for (const key of KEYS) {
    const c = candidate[key];
    const r = resident[key];
    if (!c || !r) continue;
    if (c.hard && !c.allowed.includes(r.value)) out.push([key, 'yours']);
    if (r.hard && !r.allowed.includes(c.value)) out.push([key, 'theirs']);
  }
  return out;
}

function compatibility(candidate, residents, occupied) {
  const dims = [];
  let num = 0;
  let den = 0;
  for (const key of KEYS) {
    const c = candidate[key];
    const answers = residents.map((r) => r[key]).filter(Boolean);
    if (!c || !answers.length) continue;
    const div = Q[key].normalize_divisor;
    const roomVal = answers.reduce((s, a) => s + a.value / div, 0) / answers.length;
    const roomImp = answers.reduce((s, a) => s + a.importance, 0) / answers.length;
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
  if (residents.length < occupied) warnings.push({ code: 'PARTIAL_ANSWERS', answered: residents.length, occupied });
  for (const key of KEYS) {
    const values = residents.map((r) => r[key]?.value).filter((v) => v !== undefined);
    if (!values.length) continue;
    const spread = Math.max(...values) - Math.min(...values);
    if ((key === 'smoking' && spread > 0) || (key !== 'smoking' && spread >= DISPERSION_THRESHOLD)) {
      warnings.push({ code: 'RESIDENTS_DISAGREE', key });
      break;
    }
  }
  return { score: Math.floor(scoreRaw + 0.5), score_raw: scoreRaw, score_version: 1, warnings, dimensions: dims };
}

function residentAnswers(db, l) {
  return membersOf(db, l.id).map((uid) => db.profiles[uid]?.answers).filter(Boolean);
}

function reasonsFor(me, l, answers) {
  const reasons = [];
  const seen = new Set();
  for (const a of answers) {
    for (const [key, side] of hardConflicts(me.answers, a)) {
      if (seen.has(key + side)) continue;
      seen.add(key + side);
      reasons.push({ code: 'HARD_CONDITION', key, side, price: null, budget: null });
    }
  }
  if (l.kind === 'apartment' && l.monthly_cost_per_person_rub > me.budget_max_rub) {
    reasons.push({ code: 'OVER_BUDGET', key: null, side: null, price: l.monthly_cost_per_person_rub, budget: me.budget_max_rub });
  }
  return reasons;
}

function candidateProfile(db, user, kind) {
  const me = db.profiles[user.id];
  if (!me) fail(422, 'PROFILE_REQUIRED');
  if (kind === 'apartment' && me.budget_max_rub == null) fail(422, 'BUDGET_REQUIRED');
  return me;
}

// The home and whether the user lives there. Someone else's only while shown.
function homeForViewer(db, user, id) {
  const l = db.listings[id];
  if (!l) fail(404, 'NOT_FOUND');
  const livesHere = db.memberships[user.id]?.listing_id === l.id;
  if (!livesHere && !isVisible(l)) fail(404, 'NOT_FOUND');
  return [l, livesHere];
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

// Returns the normalized contacts.
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
  const contacts = Array.isArray(body.contacts) ? body.contacts : [];
  if (!contacts.length) errors.contacts = 'TOO_SHORT';
  if (contacts.length > 10) errors.contacts = 'TOO_LONG';
  const normalized = contacts.map((c, i) => {
    const [value, reason] = normalizeContact(c.type, c.value);
    if (reason) errors[`contacts.${i}.${reason === 'INVALID_CHOICE' ? 'type' : 'value'}`] = reason;
    return { type: c.type, value };
  });
  if (body.status && !['active', 'paused'].includes(body.status)) errors.status = 'INVALID_CHOICE';
  if (Object.keys(errors).length) invalid(errors);
  return normalized;
}

function listingFields(kind, body, contacts) {
  const f = {
    capacity: body.capacity,
    occupied_count: body.occupied_count,
    description: body.description || null,
    contacts,
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

// A home the user is an admin of.
function adminListing(db, user, id) {
  const l = db.listings[id];
  if (!l) fail(404, 'NOT_FOUND');
  const m = db.memberships[user.id];
  if (!m || m.listing_id !== id || !m.is_admin) fail(403, 'NOT_ADMIN');
  return l;
}

function targetMember(db, l, uid) {
  if (db.memberships[uid]?.listing_id !== l.id) fail(404, 'NOT_MEMBER');
  return db.memberships[uid];
}

function checkVersion(l, expected) {
  if (expected !== l.version) fail(409, 'VERSION_CONFLICT');
}

// Shrink an uploaded photo to a small data URL, so it fits in localStorage.
async function photoDataUrl(file) {
  if (!(file instanceof Blob) || !/^image\/(jpeg|png|webp)$/.test(file.type)) fail(415, 'PHOTO_BAD_TYPE');
  if (file.size > 10 * 1024 * 1024) fail(413, 'PHOTO_TOO_LARGE');
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    fail(415, 'PHOTO_BAD_TYPE');
  }
  const scale = Math.min(1, 480 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return { url: canvas.toDataURL('image/jpeg', 0.7), width: canvas.width, height: canvas.height };
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
      user = { id: newId(), email, display_name: 'Пользователь', language: null };
      db.users[user.id] = user;
    }
    db.session = user.id;
    const { id, display_name: displayName } = user;
    return { user: { id, email, display_name: displayName }, profile_complete: meDto(db, user).profile_complete };
  }],

  ['POST', /^\/auth\/logout$/, (db) => {
    db.session = null;
    return null;
  }],

  ['GET', /^\/me$/, (db) => meDto(db, currentUser(db))],

  ['PUT', /^\/me$/, (db, body) => {
    const user = currentUser(db);
    if (body.display_name != null) {
      const name = String(body.display_name);
      if (name.length < 2) invalid({ display_name: 'STRING_TOO_SHORT' });
      if (name.length > 60) invalid({ display_name: 'STRING_TOO_LONG' });
      user.display_name = name;
    }
    if (body.language != null) {
      if (!['ru', 'en'].includes(body.language)) invalid({ language: 'LITERAL_ERROR' });
      user.language = body.language;
    }
    return meDto(db, user);
  }],

  ['DELETE', /^\/me$/, (db, body) => {
    const user = currentUser(db);
    if (body.confirm !== 'DELETE') fail(422, 'VALIDATION_ERROR', { confirm: 'MUST_BE_DELETE' });
    removeMember(db, user.id);
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
    if (body.questionnaire_version !== QUESTIONNAIRE.version) errors.questionnaire_version = 'UNSUPPORTED_VERSION';
    if (!['seeker', 'host'].includes(body.situation)) errors.situation = 'INVALID_CHOICE';
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
    if (body.situation === 'seeker' && db.memberships[user.id]) fail(409, 'LEAVE_HOME_FIRST');
    if (body.expected_version !== (current?.version ?? 0)) fail(409, 'VERSION_CONFLICT');
    const profile = {
      user_id: user.id,
      questionnaire_version: QUESTIONNAIRE.version,
      answers,
      situation: body.situation,
      budget_max_rub: body.situation === 'seeker' ? body.budget_max_rub ?? null : null,
      version: (current?.version ?? 0) + 1,
      updated_at: iso(now()),
    };
    db.profiles[user.id] = profile;
    return profile;
  }],

  ['GET', /^\/listings\/mine$/, (db) => {
    const user = currentUser(db);
    const m = db.memberships[user.id];
    return { item: m ? homeDto(db, db.listings[m.listing_id], user) : null };
  }],

  ['POST', /^\/listings$/, (db, body) => {
    const user = currentUser(db);
    const contacts = validateListing(body.kind, body);
    if (!db.profiles[user.id]) fail(422, 'PROFILE_REQUIRED');
    if (db.memberships[user.id]) fail(409, 'ALREADY_IN_ROOM');
    const fields = listingFields(body.kind, body, contacts);
    if (body.kind === 'dorm' && Object.values(db.listings).some((x) => x.building === fields.building && x.room_number === fields.room_number)) {
      fail(409, 'ROOM_TAKEN');
    }
    const l = {
      id: newId(), kind: body.kind, ...fields, photos: [], status: 'active', version: 1,
      confirmed_at: iso(now()), created_at: iso(now()), invite_token: null, invite_expires_at: null,
    };
    db.listings[l.id] = l;
    db.memberships[user.id] = { listing_id: l.id, is_admin: true, joined_at: iso(now()) };
    Object.assign(db.profiles[user.id], { situation: 'host', budget_max_rub: null });
    return { status: 201, data: homeDto(db, l, user) };
  }],

  ['PUT', /^\/listings\/([\w-]+)\/photos\/order$/, (db, body, [id]) => {
    const user = currentUser(db);
    const l = adminListing(db, user, id);
    const ids = body.photo_ids ?? [];
    if (ids.length !== l.photos.length || !l.photos.every((p) => ids.includes(p.id))) invalid({ photo_ids: 'INVALID_SET' });
    l.photos = ids.map((pid) => l.photos.find((p) => p.id === pid));
    return homeDto(db, l, user);
  }],

  ['PUT', /^\/listings\/([\w-]+)$/, (db, body, [id]) => {
    const user = currentUser(db);
    const l = adminListing(db, user, id);
    checkVersion(l, body.expected_version);
    if (body.occupied_count < membersOf(db, l.id).length) fail(409, 'OCCUPANCY_CONFLICT');
    const contacts = validateListing(l.kind, body);
    const fields = listingFields(l.kind, body, contacts);
    if (l.kind === 'dorm' && Object.values(db.listings).some((x) => x.id !== l.id && x.building === fields.building && x.room_number === fields.room_number)) {
      fail(409, 'ROOM_TAKEN');
    }
    Object.assign(l, fields);
    l.status = l.capacity - l.occupied_count <= 0 ? 'paused' : (body.status || 'active');
    if (l.status === 'active') l.confirmed_at = iso(now());
    l.version += 1;
    return homeDto(db, l, user);
  }],

  ['DELETE', /^\/listings\/([\w-]+)$/, (db, body, [id]) => {
    const l = adminListing(db, currentUser(db), id);
    for (const uid of membersOf(db, l.id)) removeMember(db, uid);
    return null;
  }],

  ['POST', /^\/listings\/([\w-]+)\/confirm$/, (db, body, [id]) => {
    const user = currentUser(db);
    const l = adminListing(db, user, id);
    checkVersion(l, body.expected_version);
    l.confirmed_at = iso(now());
    if (l.capacity - l.occupied_count > 0) l.status = 'active';
    l.version += 1;
    return homeDto(db, l, user);
  }],

  ['POST', /^\/listings\/([\w-]+)\/invite$/, (db, body, [id]) => {
    const l = adminListing(db, currentUser(db), id);
    checkVersion(l, body.expected_version);
    l.invite_token = crypto.randomUUID().replace(/-/g, '');
    l.invite_expires_at = iso(new Date(Date.now() + INVITE_TTL_DAYS * DAY_MS));
    l.version += 1;
    return { invite_url: `${location.origin}/join#token=${l.invite_token}`, expires_at: l.invite_expires_at, version: l.version };
  }],

  ['POST', /^\/listings\/([\w-]+)\/photos$/, async (db, body, [id]) => {
    const user = currentUser(db);
    const l = adminListing(db, user, id);
    if (l.photos.length >= 10) fail(409, 'TOO_MANY_PHOTOS');
    const photo = await photoDataUrl(body instanceof FormData ? body.get('file') : null);
    l.photos.push({ id: newId(), ...photo });
    return { status: 201, data: homeDto(db, l, user) };
  }],

  ['DELETE', /^\/listings\/([\w-]+)\/photos\/([\w-]+)$/, (db, body, [id, photoId]) => {
    const user = currentUser(db);
    const l = adminListing(db, user, id);
    if (!l.photos.some((p) => p.id === photoId)) fail(404, 'NOT_FOUND');
    l.photos = l.photos.filter((p) => p.id !== photoId);
    return homeDto(db, l, user);
  }],

  ['POST', /^\/listings\/([\w-]+)\/admins\/([\w-]+)$/, (db, body, [id, uid]) => {
    const l = adminListing(db, currentUser(db), id);
    const target = targetMember(db, l, uid);
    if (!target.is_admin) {
      if (!db.profiles[uid]) fail(422, 'TARGET_PROFILE_REQUIRED');
      target.is_admin = true;
      l.version += 1;
    }
    return null;
  }],

  ['DELETE', /^\/listings\/([\w-]+)\/admins\/([\w-]+)$/, (db, body, [id, uid]) => {
    const l = adminListing(db, currentUser(db), id);
    const target = targetMember(db, l, uid);
    if (target.is_admin) {
      if (!membersOf(db, l.id).some((m) => m !== uid && db.memberships[m].is_admin)) fail(409, 'LAST_ADMIN');
      target.is_admin = false;
      l.version += 1;
    }
    return null;
  }],

  ['DELETE', /^\/listings\/([\w-]+)\/members\/([\w-]+)$/, (db, body, [id, uid]) => {
    const l = adminListing(db, currentUser(db), id);
    targetMember(db, l, uid);
    removeMember(db, uid);
    return null;
  }],

  ['POST', /^\/memberships\/join$/, (db, body) => {
    const user = currentUser(db);
    if (!db.profiles[user.id]) fail(422, 'PROFILE_REQUIRED');
    const l = Object.values(db.listings).find((x) => x.invite_token && x.invite_token === body.invite_token);
    if (!l) fail(404, 'INVITE_INVALID');
    if (new Date(l.invite_expires_at) < now()) fail(404, 'INVITE_EXPIRED');
    const m = db.memberships[user.id];
    if (m?.listing_id === l.id) return { listing_id: l.id, version: l.version };
    if (m) fail(409, 'ALREADY_IN_ROOM');
    if (membersOf(db, l.id).length >= l.occupied_count) fail(409, 'ROOM_FULL');
    db.memberships[user.id] = { listing_id: l.id, is_admin: false, joined_at: iso(now()) };
    Object.assign(db.profiles[user.id], { situation: 'host', budget_max_rub: null });
    l.version += 1;
    return { listing_id: l.id, version: l.version };
  }],

  ['DELETE', /^\/membership$/, (db) => {
    removeMember(db, currentUser(db).id);
    return null;
  }],

  ['GET', /^\/matches$/, (db, body, groups, query) => {
    const user = currentUser(db);
    const kind = query.get('kind');
    const offset = Number(query.get('offset') ?? 0);
    const limit = Number(query.get('limit') ?? 20);
    const all = ['true', '1'].includes(query.get('include_unmatched'));
    if (!['dorm', 'apartment'].includes(kind)) invalid({ 'query.kind': 'STRING_PATTERN_MISMATCH' });
    const me = candidateProfile(db, user, kind);
    const items = [];
    for (const l of Object.values(db.listings)) {
      if (l.kind !== kind || !isVisible(l) || db.memberships[user.id]?.listing_id === l.id) continue;
      const answers = residentAnswers(db, l);
      if (!answers.length) continue;
      const reasons = reasonsFor(me, l, answers);
      if (reasons.length && !all) continue;
      items.push({
        id: l.id, kind: l.kind, building: l.building, room_number: l.room_number, district: l.district,
        monthly_cost_per_person_rub: l.monthly_cost_per_person_rub, cover_url: l.photos[0]?.url ?? null,
        free_places: l.capacity - l.occupied_count, answered_count: answers.length, occupied_count: l.occupied_count,
        fits: !reasons.length, reasons, compatibility: compatibility(me.answers, answers, l.occupied_count),
      });
    }
    items.sort((a, b) => (a.fits === b.fits ? b.compatibility.score_raw - a.compatibility.score_raw : a.fits ? -1 : 1));
    return { items: items.slice(offset, offset + limit), total: items.length, offset, limit, score_version: 1 };
  }],

  ['GET', /^\/listings\/([\w-]+)$/, (db, body, [id]) => {
    const user = currentUser(db);
    const [l, livesHere] = homeForViewer(db, user, id);
    const residents = residentsOf(db, l.id).map(({ display_name: name, profile_complete: done, is_admin: admin }) => ({
      display_name: name, profile_complete: done, is_admin: admin,
    }));
    const { contacts: _c, invite_token: _t, invite_expires_at: _e, created_at: _cr, ...rest } = l;
    const detail = {
      ...rest, free_places: l.capacity - l.occupied_count,
      answered_count: residents.filter((r) => r.profile_complete).length, residents,
      you_live_here: livesHere, fits: true, reasons: [], compatibility: null,
    };
    if (livesHere) return detail;
    const me = candidateProfile(db, user, l.kind);
    const answers = residentAnswers(db, l);
    if (!answers.length) fail(404, 'NOT_FOUND');
    detail.reasons = reasonsFor(me, l, answers);
    detail.fits = !detail.reasons.length;
    detail.compatibility = compatibility(me.answers, answers, l.occupied_count);
    return detail;
  }],

  ['GET', /^\/listings\/([\w-]+)\/contact$/, (db, body, [id]) => {
    const user = currentUser(db);
    const [l, livesHere] = homeForViewer(db, user, id);
    if (!livesHere) candidateProfile(db, user, l.kind);
    return { items: contactsOut(l) };
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
      const result = await fn(db, body ?? {}, match.slice(1), url.searchParams);
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

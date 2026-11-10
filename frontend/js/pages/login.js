// Login without a password, in three steps:
//   1. email  →  2. name, while the code is on its way (first login only)  →  3. code.

import { ApiError, post } from '../api.js';
import { currentLang, t } from '../i18n.js';
import { mountLangSwitch } from '../lang-switch.js';
import { initPage } from '../layout.js';
import { homeFor } from '../routes.js';
import { KEYS, local, session } from '../storage.js';
import { errorText, setBusy } from '../ui.js';

const RESEND_COOLDOWN = 60; // seconds; the server enforces the same pause
const $ = (id) => document.getElementById(id);

const { user } = await initPage({ auth: 'optional' });
if (user) location.replace(homeFor(user));

// A pick here lasts for this tab and is saved to the account on login.
mountLangSwitch($('lang'), { onPick: (code) => { session.set(KEYS.lang, code); renderCodeStep(); } });

const steps = { email: $('step-email'), name: $('step-name'), code: $('step-code') };
const cells = [...$('code').querySelectorAll('input')];
const state = { email: '', isNew: false, firstName: '', lastName: '', expiresAt: 0, resendAt: 0 };

function show(step) {
  for (const [name, form] of Object.entries(steps)) form.hidden = name !== step;
  const focus = { email: $('email'), name: $('first-name'), code: cells[0] }[step];
  focus.focus();
}

/** Show or clear the red chip under a field. */
function fieldError(input, errorEl, message) {
  input.setAttribute('aria-invalid', String(Boolean(message)));
  errorEl.textContent = message || '';
  errorEl.hidden = !message;
}

const reason = (code) => {
  const key = `error.field.${code}`;
  const text = t(key);
  return text === key ? t('error.field.invalid') : text;
};

// ── Step 1: email ───────────────────────────────────────

async function requestCode(button) {
  setBusy(button, true);
  try {
    const res = await post('/auth/request-code', {
      email: state.email, privacy_accepted: true, language: currentLang(),
    });
    state.isNew = res.is_new;
    state.expiresAt = Date.now() + res.ttl_seconds * 1000;
    state.resendAt = Date.now() + RESEND_COOLDOWN * 1000;
    return true;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.fields.email) {
      fieldError($('email'), $('email-err'), reason(err.fields.email));
      show('email');
    } else {
      // Too many requests, mail service down, no network.
      const note = steps.email.hidden ? $('code-err') : $('email-note');
      note.textContent = `⚠ ${errorText(err)}`;
      note.hidden = false;
    }
    return false;
  } finally {
    setBusy(button, false);
  }
}

steps.email.addEventListener('submit', async (e) => {
  e.preventDefault();
  $('email-note').hidden = true;
  state.email = $('email').value.trim().toLowerCase();
  const emailProblem = !state.email ? 'REQUIRED' : !state.email.includes('@') ? 'INVALID_EMAIL' : null;
  fieldError($('email'), $('email-err'), emailProblem && reason(emailProblem));
  const accepted = $('privacy').checked;
  fieldError($('privacy'), $('privacy-err'), accepted ? '' : reason('MUST_ACCEPT'));
  if (emailProblem) { $('email').focus(); return; }
  if (!accepted) { $('privacy').focus(); return; }

  if (!await requestCode(e.submitter)) return;
  clearCode();
  renderCodeStep();
  show(state.isNew ? 'name' : 'code');
});

// ── Step 2: name ────────────────────────────────────────

steps.name.addEventListener('submit', (e) => {
  e.preventDefault();
  state.firstName = $('first-name').value.trim().replace(/\s+/g, ' ');
  state.lastName = $('last-name').value.trim().replace(/\s+/g, ' ');
  fieldError($('first-name'), $('first-name-err'), state.firstName ? '' : reason('REQUIRED'));
  fieldError($('last-name'), $('last-name-err'), state.lastName ? '' : reason('REQUIRED'));
  if (!state.firstName) { $('first-name').focus(); return; }
  if (!state.lastName) { $('last-name').focus(); return; }
  renderCodeStep();
  show('code');
});

// ── Step 3: code ────────────────────────────────────────

function renderCodeStep() {
  $('code-title').textContent = state.isNew
    ? t('login.code.titleNew', { name: state.firstName })
    : t('login.code.titleBack');
  $('code-text').textContent = t('login.code.text', { email: state.email });
  tick();
}

const code = () => cells.map((c) => c.value).join('');

function clearCode() {
  cells.forEach((c) => { c.value = ''; });
  codeError('');
}

function codeError(message) {
  $('code').setAttribute('aria-invalid', String(Boolean(message)));
  $('code-err').textContent = message ? `✕ ${message}` : '';
  $('code-err').hidden = !message;
}

/** Put digits into the boxes starting at `from`; used for typing, pasting and SMS-style autofill. */
function spread(digits, from) {
  digits.slice(0, cells.length - from).forEach((d, j) => { cells[from + j].value = d; });
  const next = Math.min(from + digits.length, cells.length - 1);
  cells[next].focus();
  if (code().length === cells.length) steps.code.requestSubmit();
}

cells.forEach((cell, i) => {
  cell.setAttribute('aria-label', String(i + 1));
  cell.addEventListener('input', () => {
    const digits = cell.value.replace(/\D/g, '').split('');
    cell.value = '';
    if (digits.length) spread(digits.length > 1 ? digits : digits.slice(-1), i);
  });
  cell.addEventListener('keydown', (e) => {
    if (e.key === 'Backspace' && !cell.value && cells[i - 1]) { cells[i - 1].value = ''; cells[i - 1].focus(); }
    if (e.key === 'ArrowLeft' && cells[i - 1]) cells[i - 1].focus();
    if (e.key === 'ArrowRight' && cells[i + 1]) cells[i + 1].focus();
  });
  cell.addEventListener('focus', () => cell.select());
  cell.addEventListener('paste', (e) => {
    const digits = (e.clipboardData.getData('text').match(/\d/g) || []);
    if (!digits.length) return;
    e.preventDefault();
    clearCode();
    spread(digits, 0);
  });
});

steps.code.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (code().length < cells.length) { codeError(t('login.code.incomplete')); cells[code().length].focus(); return; }
  const button = steps.code.querySelector('button[type=submit]');
  if (button.disabled) return;
  setBusy(button, true);
  try {
    const body = { email: state.email, code: code() };
    if (state.isNew) Object.assign(body, { first_name: state.firstName, last_name: state.lastName });
    // The account keeps its own language unless one was picked on the landing or here.
    if (state.isNew || session.get(KEYS.lang)) body.language = currentLang();
    const res = await post('/auth/verify-code', body);
    local.set(KEYS.seenLogin, '1');
    session.remove(KEYS.lang);
    if (res.account_restored) session.set(KEYS.flash, 'flash.restored');
    location.replace(homeFor(res));
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    setBusy(button, false);
    if (err.fields.first_name || err.fields.last_name) { show('name'); return; }
    clearCode();
    codeError(err.code === 'INVALID_CODE' ? t('login.code.wrong') : errorText(err));
    cells[0].focus();
  }
});

$('resend').addEventListener('click', async () => {
  codeError('');
  if (await requestCode($('resend'))) { clearCode(); renderCodeStep(); cells[0].focus(); }
});

$('change-email').addEventListener('click', () => { clearCode(); show('email'); });

// Countdowns: how long the code lives, and when another one can be sent.
const mmss = (ms) => {
  const s = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};

function tick() {
  if (steps.code.hidden && steps.name.hidden) return;
  const left = state.expiresAt - Date.now();
  $('timer').hidden = left <= 0;
  $('timer-left').textContent = mmss(left);
  if (left <= 0 && !steps.code.hidden && $('code-err').hidden) codeError(t('login.code.expired'));
  const wait = state.resendAt - Date.now();
  $('resend').hidden = wait > 0;
  $('resend-wait').textContent = wait > 0 ? t('login.code.resendIn', { time: mmss(wait) }) : '';
}
setInterval(tick, 1000);

show('email');

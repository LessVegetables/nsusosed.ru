// Joining a home by invite. The link looks like /join#code=K7QM2XWP; the field also takes
// a bare code or the whole link pasted in. People who aren't logged in are sent to log in
// first and come back here with the code still in the address.

import { ApiError, get, post } from '../api.js';
import { t } from '../i18n.js';
import { initPage } from '../layout.js';
import { KEYS, session } from '../storage.js';
import { errorText, setBusy } from '../ui.js';

const $ = (id) => document.getElementById(id);
const fromHash = () => new URLSearchParams(location.hash.slice(1)).get('code') ?? '';

// Keep the code across the login detour (the hash isn't sent to the server or kept by redirects).
if (fromHash()) session.set(KEYS.invite, fromHash());
const { user } = await initPage({ auth: 'required' });
if (!user.questionnaire_complete) {
  location.replace('/questionnaire'); // the invite waits in this tab and is picked up afterwards
  await new Promise(() => {});
}
const pending = fromHash() || session.get(KEYS.invite) || '';
session.remove(KEYS.invite);

if (user.home_id) {
  // Already living somewhere on the site: that home's page explains the rest.
  location.replace('/home');
}
const meta = await get('/meta');
let code = '';

function fail(message) {
  $('code').setAttribute('aria-invalid', 'true');
  $('code-err').textContent = message;
  $('code-err').hidden = false;
}

async function preview(button) {
  code = $('code').value.trim();
  $('code').setAttribute('aria-invalid', 'false');
  $('code-err').hidden = true;
  if (!code) { fail(t('error.field.REQUIRED')); return; }
  if (button) setBusy(button, true);
  try {
    const p = await post('/invites/preview', { code });
    const dorm = meta.dorms.find((d) => d.id === p.building);
    $('confirm-title').textContent = p.kind === 'dorm'
      ? t('home.dorm.n', { name: dorm?.name ?? p.building })
      : t('join.confirm.apartment', { district: p.district });
    $('confirm-emoji').textContent = p.emoji;
    $('confirm-hosts').textContent = t('join.confirm.hosts', { names: p.hosts.join(', ') });
    $('confirm-err').hidden = true;
    $('code-form').hidden = true;
    $('confirm').hidden = false;
    $('join').focus();
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    fail(errorText(err));
  } finally {
    if (button) setBusy(button, false);
  }
}

$('code-form').addEventListener('submit', (e) => { e.preventDefault(); preview(e.submitter); });

$('back').addEventListener('click', () => {
  $('confirm').hidden = true;
  $('code-form').hidden = false;
  $('code').focus();
});

$('join').addEventListener('click', async () => {
  setBusy($('join'), true);
  try {
    await post('/invites/join', { code });
    session.set(KEYS.flash, 'flash.joined');
    location.replace('/home');
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    setBusy($('join'), false);
    $('confirm-err').textContent = `✕ ${errorText(err)}`;
    $('confirm-err').hidden = false;
  }
});

if (pending) {
  $('code').value = pending;
  history.replaceState(null, '', '/join');
  preview(null);
}

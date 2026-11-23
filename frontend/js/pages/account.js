// Account page: profile, what you're here for, contacts, language, logout, deletion.
// Nothing has a save button: a choice saves when it is made, a text field a moment after
// typing stops (and when it is left). Each save answers with a "Saved" pop-up.

import { ApiError, del, get, post, put } from '../api.js';
import { autosaver, saveOnEdit } from '../autosave.js';
import { mountContacts } from '../contacts.js';
import { renderFacultyPicker } from '../faculty.js';
import { t } from '../i18n.js';
import { mountLangSwitch } from '../lang-switch.js';
import { mountInviteField } from '../invite-field.js';
import { initPage } from '../layout.js';
import { KEYS, local, session } from '../storage.js';
import { el, errorText, saved, setBusy, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);

let { user } = await initPage({ auth: 'required' });
const meta = await get('/meta');

const fieldReason = (code) => {
  const key = `error.field.${code}`;
  const text = t(key);
  return text === key ? t('error.field.invalid') : text;
};

function fieldError(input, errorEl, message) {
  input.setAttribute('aria-invalid', String(Boolean(message)));
  if (errorEl) { errorEl.textContent = message || ''; errorEl.hidden = !message; }
}

const TYPING_PAUSE = 1200; // ms without a keystroke before a text field saves

/** Run a save: "Saved" pop-up, and a toast for errors no field explains. */
async function save(action, onFieldErrors) {
  try {
    user = await action();
    saved();
    return true;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return false; }
    if (!(Object.keys(err.fields).length && onFieldErrors?.(err.fields))) {
      toast(t('error.title'), errorText(err), { error: true });
    }
    return false;
  }
}

// ── Single-choice button groups (.opts) ─────────────────

/** Picking a button saves it as `field`. */
function choice(group, field, onSaved = () => {}) {
  const buttons = [...group.querySelectorAll('button')];
  const set = (v) => buttons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.value === v)));
  buttons.forEach((b) => b.addEventListener('click', async () => {
    const value = b.dataset.value;
    if (value === user[field]) return;
    set(value);
    await save(() => put('/me', { [field]: value }));
    set(user[field]); // back to the saved one if the save failed
    onSaved();
  }));
  set(user[field]);
}

// ── Profile ─────────────────────────────────────────────

function renderAvatar() {
  const node = user.avatar_url
    ? el('img', { class: 'avatar', src: user.avatar_url, alt: t('account.avatar.alt') })
    : el('span', { class: 'avatar', 'aria-hidden': 'true' }, user.first_name.slice(0, 1));
  $('avatar').replaceChildren(node);
  $('avatar-remove').hidden = !user.avatar_url;
}

$('email').textContent = user.email;
$('first-name').value = user.first_name;
$('last-name').value = user.last_name;
$('bio').value = user.bio;
renderAvatar();

$('avatar-file').addEventListener('change', async () => {
  const file = $('avatar-file').files[0];
  $('avatar-file').value = '';
  if (!file) return;
  const body = new FormData();
  body.append('file', file);
  const label = $('avatar-file').closest('.btn');
  label.setAttribute('aria-busy', 'true');
  try {
    user = await post('/me/avatar', body);
    renderAvatar();
    saved();
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true });
  } finally {
    label.setAttribute('aria-busy', 'false');
  }
});

$('avatar-remove').addEventListener('click', async () => {
  if (await save(() => del('/me/avatar'))) renderAvatar();
});

const saveProfile = autosaver(async () => {
  const first = $('first-name').value.trim();
  const last = $('last-name').value.trim();
  fieldError($('first-name'), $('first-name-err'), first ? '' : fieldReason('REQUIRED'));
  fieldError($('last-name'), $('last-name-err'), last ? '' : fieldReason('REQUIRED'));
  if (!first || !last) return;
  const bio = $('bio').value.trim();
  if (first === user.first_name && last === user.last_name && bio === user.bio) return;
  const ok = await save(() => put('/me', { first_name: first, last_name: last, bio }), (fields) => {
    if (!fields.first_name && !fields.last_name) return false;
    if (fields.first_name) fieldError($('first-name'), $('first-name-err'), fieldReason(fields.first_name));
    if (fields.last_name) fieldError($('last-name'), $('last-name-err'), fieldReason(fields.last_name));
    return true;
  });
  if (ok) renderAvatar(); // the letter follows the name
}, TYPING_PAUSE);

for (const id of ['first-name', 'last-name', 'bio']) saveOnEdit($(id), saveProfile);
// Enter in a field saves it; there is nothing to submit.
for (const id of ['profile', 'about', 'contacts']) {
  $(id).addEventListener('submit', (e) => { e.preventDefault(); e.target.dispatchEvent(new Event('save')); });
}
$('profile').addEventListener('save', () => saveProfile.now());

// ── What you're looking for ─────────────────────────────

// "I was invited" and not living anywhere on the site yet: the link or code goes in right
// under the choice; the join page then shows the place.
const renderInvite = () => { $('invite-box').hidden = user.intent !== 'join' || Boolean(user.home_id); };
choice($('intent'), 'intent', () => {
  renderInvite();
  if (!$('invite-box').hidden) $('invite-code').focus();
});
renderInvite();
mountInviteField($('invite-code'), $('invite-hint'));

function findInvite() {
  const code = $('invite-code').value.trim();
  fieldError($('invite-code'), $('invite-err'), code ? '' : fieldReason('REQUIRED'));
  if (!code) { $('invite-code').focus(); return; }
  session.set(KEYS.invite, code); // picked up by the join page
  location.assign('/join');
}
$('invite-go').addEventListener('click', findInvite);
$('invite-code').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); findInvite(); }
});
choice($('gender'), 'gender');

function renderFaculties() {
  renderFacultyPicker($('faculty'), meta.faculties, user.faculty);
}
renderFaculties();
$('faculty').addEventListener('change', async () => {
  if ($('faculty').value) await save(() => put('/me', { faculty: $('faculty').value }));
});

// ── Contacts ────────────────────────────────────────────
// The same fields as on the home page while a place is being listed: js/contacts.js.

const contacts = mountContacts({
  fields: $('contact-fields'), error: $('contacts-err'),
  getUser: () => user, setUser: (next) => { user = next; },
});
$('contacts').addEventListener('save', () => contacts.save.now());

// ── Questionnaire status ────────────────────────────────

const renderQuizStatus = () => {
  $('quiz-status').textContent = user.questionnaire_complete ? t('account.quiz.done') : t('account.quiz.todo');
};
renderQuizStatus();

// ── Language ────────────────────────────────────────────

mountLangSwitch($('lang'), {
  onPick: async (code) => {
    session.remove(KEYS.lang);
    local.set(KEYS.lang, code);
    await save(() => put('/me', { language: code }));
  },
});

document.addEventListener('langchange', () => {
  renderFaculties();
  contacts.render();
  renderAvatar();
  renderQuizStatus();
});

// ── Logout and deletion ─────────────────────────────────

function forgetAccount() {
  local.remove(KEYS.lang);
}

$('logout').addEventListener('click', async () => {
  setBusy($('logout'), true);
  try { await post('/auth/logout'); } catch { /* the cookie may already be gone */ }
  forgetAccount();
  location.replace('/login');
});

const dialog = $('delete-dialog');
$('delete').addEventListener('click', () => dialog.showModal());
$('delete-cancel').addEventListener('click', () => dialog.close());
$('delete-confirm').addEventListener('click', async () => {
  setBusy($('delete-confirm'), true);
  try {
    await del('/me', { confirm: 'DELETE' });
    forgetAccount();
    local.remove(KEYS.seenLogin);
    session.set(KEYS.flash, 'flash.deleted');
    location.replace('/');
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    setBusy($('delete-confirm'), false);
    dialog.close();
    toast(t('error.title'), errorText(err), { error: true });
  }
});

if (location.hash === '#language') $('language').scrollIntoView();

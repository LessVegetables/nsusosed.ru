// Account page: profile, what you're here for, contacts, language, logout, deletion.
// Each box saves on its own; the language saves the moment it is picked.

import { ApiError, del, get, post, put } from '../api.js';
import { currentLang, t } from '../i18n.js';
import { mountLangSwitch } from '../lang-switch.js';
import { initPage } from '../layout.js';
import { KEYS, local, session } from '../storage.js';
import { el, errorText, setBusy, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);

// Primary ones first. `howto` = there are instructions for opening direct messages.
const CONTACTS = [
  { type: 'phone', primary: true, placeholder: '+7 913 123-45-67', inputmode: 'tel', autocomplete: 'tel' },
  { type: 'telegram', primary: true, placeholder: '@username', howto: true },
  { type: 'vk', primary: true, placeholder: 'vk.com/id…', howto: true },
  { type: 'max', placeholder: '+7 913 123-45-67', howto: true },
  { type: 'instagram', placeholder: '@username', howto: true },
  { type: 'snapchat', placeholder: 'username', howto: true },
  { type: 'wechat', placeholder: 'WeChat ID', howto: true },
];

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

/** Run a save: busy button, success toast, and a toast for errors no field explains. */
async function save(button, action, onFieldErrors) {
  setBusy(button, true);
  try {
    user = await action();
    toast(t('account.saved'), '', { ms: 2500 });
    return true;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return false; }
    if (!(Object.keys(err.fields).length && onFieldErrors?.(err.fields))) {
      toast(t('error.title'), errorText(err), { error: true });
    }
    return false;
  } finally {
    setBusy(button, false);
  }
}

// ── Single-choice button groups (.opts) ─────────────────

function choice(group, value) {
  const buttons = [...group.querySelectorAll('button')];
  const set = (v) => buttons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.value === v)));
  buttons.forEach((b) => b.addEventListener('click', () => set(b.dataset.value)));
  set(value);
  return () => buttons.find((b) => b.getAttribute('aria-pressed') === 'true')?.dataset.value ?? null;
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
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true });
  } finally {
    label.setAttribute('aria-busy', 'false');
  }
});

$('avatar-remove').addEventListener('click', async () => {
  user = await del('/me/avatar');
  renderAvatar();
});

$('profile').addEventListener('submit', async (e) => {
  e.preventDefault();
  const first = $('first-name').value.trim();
  const last = $('last-name').value.trim();
  fieldError($('first-name'), $('first-name-err'), first ? '' : fieldReason('REQUIRED'));
  fieldError($('last-name'), $('last-name-err'), last ? '' : fieldReason('REQUIRED'));
  if (!first) { $('first-name').focus(); return; }
  if (!last) { $('last-name').focus(); return; }
  const ok = await save(e.submitter, () => put('/me', { first_name: first, last_name: last, bio: $('bio').value }), (fields) => {
    if (!fields.first_name && !fields.last_name) return false;
    if (fields.first_name) fieldError($('first-name'), $('first-name-err'), fieldReason(fields.first_name));
    if (fields.last_name) fieldError($('last-name'), $('last-name-err'), fieldReason(fields.last_name));
    return true;
  });
  if (ok) renderAvatar(); // the letter follows the name
});

// ── What you're looking for ─────────────────────────────

const intent = choice($('intent'), user.intent);
const gender = choice($('gender'), user.gender);
$('is-adult').checked = user.is_adult === true;

function renderFaculties() {
  const lang = currentLang();
  $('faculty').replaceChildren(
    el('option', { value: '' }, t('account.faculty.none')),
    ...meta.faculties.map((f) => el('option', { value: f.id }, f[lang] ?? f.ru)));
  $('faculty').value = user.faculty ?? '';
}
renderFaculties();

$('about').addEventListener('submit', async (e) => {
  e.preventDefault();
  const body = { is_adult: $('is-adult').checked };
  if (intent()) body.intent = intent();
  if (gender()) body.gender = gender();
  if ($('faculty').value) body.faculty = $('faculty').value;
  await save(e.submitter, () => put('/me', body));
});

// ── Contacts ────────────────────────────────────────────

const contactInputs = {};

function renderContacts() {
  const saved = Object.fromEntries(user.contacts.map((c) => [c.type, c.value]));
  $('contact-fields').replaceChildren(...CONTACTS.map((c) => {
    const input = el('input', {
      id: `contact-${c.type}`, placeholder: c.placeholder, inputmode: c.inputmode, autocomplete: c.autocomplete ?? 'off',
      autocapitalize: 'none', spellcheck: 'false', maxlength: 100, 'aria-describedby': `contact-${c.type}-err`,
    });
    // Keep what is being typed when the language changes.
    input.value = contactInputs[c.type]?.value ?? saved[c.type] ?? '';
    contactInputs[c.type] = input;
    return el('div', {},
      el('label', { class: 'field' },
        el('span', {}, t(`contact.${c.type}`), c.primary && el('span', { class: 'tag fill-yellow' }, t('account.contacts.primary'))),
        input,
        el('span', { class: 'error', id: `contact-${c.type}-err`, hidden: true })),
      c.howto && el('details', { class: 'more' },
        el('summary', {}, t('account.contacts.howto')),
        el('p', { class: 'note' }, t(`contact.${c.type}.howto`))));
  }));
}
renderContacts();

$('contacts').addEventListener('submit', async (e) => {
  e.preventDefault();
  $('contacts-err').hidden = true;
  const sent = CONTACTS.map((c) => ({ type: c.type, value: contactInputs[c.type].value.trim() }));
  sent.forEach((c) => fieldError(contactInputs[c.type], $(`contact-${c.type}-err`), ''));
  const filled = sent.filter((c) => c.value);
  const ok = await save(e.submitter, () => put('/me/contacts', { contacts: filled }), (fields) => {
    let first = null;
    for (const [path, code] of Object.entries(fields)) {
      const item = filled[Number(path.split('.')[1])];
      if (item) {
        fieldError(contactInputs[item.type], $(`contact-${item.type}-err`), fieldReason(code));
        first ??= contactInputs[item.type];
      } else if (path === 'contacts') {
        $('contacts-err').textContent = `✕ ${fieldReason(code)}`;
        $('contacts-err').hidden = false;
        first ??= contactInputs.phone;
      }
    }
    first?.focus();
    return Boolean(first);
  });
  if (ok) {
    // Show the values as the server normalized them (+7…, no @, no link prefix).
    for (const c of CONTACTS) delete contactInputs[c.type];
    renderContacts();
  }
});

// ── Language ────────────────────────────────────────────

mountLangSwitch($('lang'), {
  onPick: async (code) => {
    session.remove(KEYS.lang);
    local.set(KEYS.lang, code);
    try {
      user = await put('/me', { language: code });
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      toast(t('error.title'), errorText(err), { error: true });
    }
  },
});

document.addEventListener('langchange', () => {
  renderFaculties();
  renderContacts();
  renderAvatar();
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

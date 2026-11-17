// The contact fields: on the account page, and on the home page while a place is being
// listed (a listing is shown only once a host can be reached). One implementation, so the two
// stay the same. Each field saves a moment after typing stops, and when it is left.

import { ApiError, put } from './api.js';
import { autosaver } from './autosave.js';
import { t } from './i18n.js';
import { el, errorText, saved, toast } from './ui.js';

// Primary ones first. `howto` = there are instructions for opening direct messages.
export const CONTACTS = [
  { type: 'phone', primary: true, placeholder: '+7 913 123-45-67', inputmode: 'tel', autocomplete: 'tel' },
  { type: 'telegram', primary: true, placeholder: '@username', howto: true },
  { type: 'vk', primary: true, placeholder: 'vk.com/id…', howto: true },
  { type: 'max', placeholder: '+7 913 123-45-67', howto: true },
  { type: 'instagram', placeholder: '@username', howto: true },
  { type: 'snapchat', placeholder: 'username', howto: true },
  { type: 'wechat', placeholder: 'WeChat ID', howto: true },
];
const PRIMARY = new Set(CONTACTS.filter((c) => c.primary).map((c) => c.type));

const TYPING_PAUSE = 1200; // ms without a keystroke before a field saves

const fieldReason = (code) => {
  const key = `error.field.${code}`;
  const text = t(key);
  return text === key ? t('error.field.invalid') : text;
};

function fieldError(input, errorEl, message) {
  input.setAttribute('aria-invalid', String(Boolean(message)));
  if (errorEl) { errorEl.textContent = message || ''; errorEl.hidden = !message; }
}

/** Does this person have a phone, Telegram or VK? */
export const hasPrimary = (user) => user.contacts.some((c) => PRIMARY.has(c.type));

/**
 * Contact fields drawn into `fields`, with the errors no single field explains in `error`.
 * `getUser()` / `setUser(user)`: the person as the server knows them (the save answers with it).
 * Returns { render, save, showError }: render() again after a language change; save.now()
 * sends what is typed right away; showError(code) shows an error from elsewhere (e.g. NEED_PRIMARY).
 */
export function mountContacts({ fields, error, getUser, setUser }) {
  const inputs = {};
  const errors = {};
  let sent = null; // what the last attempt sent: the same list isn't sent twice
  const storedValues = () => Object.fromEntries(getUser().contacts.map((c) => [c.type, c.value]));

  const save = autosaver(async () => {
    const all = CONTACTS.map((c) => ({ type: c.type, value: inputs[c.type].value.trim() }));
    const filled = all.filter((c) => c.value);
    const key = JSON.stringify(filled);
    sent ??= JSON.stringify(getUser().contacts.map((c) => ({ type: c.type, value: c.value })));
    if (key === sent) return;
    sent = key;
    error.hidden = true;
    all.forEach((c) => fieldError(inputs[c.type], errors[c.type], ''));
    try {
      setUser(await put('/me/contacts', { contacts: filled }));
      saved();
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      if (err.status === 401) { location.replace('/login'); return; }
      let marked = false;
      for (const [path, code] of Object.entries(err.fields ?? {})) {
        const item = filled[Number(path.split('.')[1])];
        if (item) { fieldError(inputs[item.type], errors[item.type], fieldReason(code)); marked = true; }
        else if (path === 'contacts') { showError(code); marked = true; }
      }
      if (!marked) toast(t('error.title'), errorText(err), { error: true });
      return;
    }
    // Show the values as the server normalized them (+7…, no @, no link prefix), except in a
    // field that was edited since or is being typed in.
    const stored = storedValues();
    for (const c of all) {
      const input = inputs[c.type];
      if (input.value.trim() === c.value && document.activeElement !== input) input.value = stored[c.type] ?? '';
    }
    sent = JSON.stringify(CONTACTS.map((c) => ({ type: c.type, value: inputs[c.type].value.trim() })).filter((c) => c.value));
  }, TYPING_PAUSE);

  function showError(code) {
    error.textContent = `✕ ${fieldReason(code)}`;
    error.hidden = false;
  }

  function render() {
    const stored = storedValues();
    fields.replaceChildren(...CONTACTS.map((c) => {
      const input = el('input', {
        id: `contact-${c.type}`, placeholder: c.placeholder, inputmode: c.inputmode, autocomplete: c.autocomplete ?? 'off',
        autocapitalize: 'none', spellcheck: 'false', maxlength: 100, 'aria-describedby': `contact-${c.type}-err`,
      });
      // Keep what is being typed when the language changes.
      input.value = inputs[c.type]?.value ?? stored[c.type] ?? '';
      inputs[c.type] = input;
      input.addEventListener('input', () => save());
      input.addEventListener('change', () => save.now());
      // Enter saves the field; it never submits a form around it (the home page's is "List it").
      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); save.now(); } });
      errors[c.type] = el('span', { class: 'error', id: `contact-${c.type}-err`, hidden: true });
      return el('div', {},
        el('label', { class: 'field' },
          el('span', {}, t(`contact.${c.type}`), c.primary && el('span', { class: 'tag fill-yellow' }, t('account.contacts.primary'))),
          input,
          errors[c.type]),
        c.howto && el('details', { class: 'more' },
          el('summary', {}, t('account.contacts.howto')),
          el('p', { class: 'note' }, t(`contact.${c.type}.howto`))));
    }));
  }

  render();
  return { render, save, showError };
}

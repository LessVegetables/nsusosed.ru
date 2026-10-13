// Small DOM helpers shared by all pages.

import { bindLocalized, bindText } from './i18n.js';
import { errorText, fieldReasonText } from './errors.js';

// h('p', {class: 'hint', i18n: 'key'}, child, 'text', ...)
//   i18n / i18nArgs  translated text (follows language changes)
//   localized        a {ru, en} pair as the text
//   onclick etc.     event listeners
//   other keys       attributes; true → empty attribute, false/null → skipped
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === false || value == null) continue;
    if (key === 'i18n') bindText(el, value, attrs.i18nArgs);
    else if (key === 'i18nArgs') continue;
    else if (key === 'localized') bindLocalized(el, value);
    else if (key === 'text') el.textContent = value;
    else if (key.startsWith('on') && typeof value === 'function') {
      el.addEventListener(key.slice(2), value);
    } else el.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

let idCounter = 0;
export function uid(prefix = 'id') {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
}

// Error box for an ApiError. `target` is an element that gets replaced content.
export function showError(target, err) {
  target.replaceChildren();
  target.hidden = false;
  target.classList.add('alert', 'alert-error');
  target.setAttribute('role', 'alert');
  target.append(h('p', { localized: errorText(err) }));
  if (err?.code === 'AUTH_REQUIRED') {
    target.append(h('p', {}, h('a', { href: loginUrl(), i18n: 'nav.login' })));
  }
  if (err?.requestId && (err.code === 'INTERNAL_ERROR' || err.code === 'UNKNOWN')) {
    target.append(h('p', { class: 'muted small', i18n: 'error.requestId', i18nArgs: { id: err.requestId } }));
  }
  if (!err?.code) console.error(err);
}

export function clearError(target) {
  target.replaceChildren();
  target.hidden = true;
}

// Shows reason codes from error.fields next to the matching inputs. Each field
// wrapper carries data-field="path" (e.g. "answers.sleep.allowed"). Returns
// the paths that had no wrapper on the page.
export function showFieldErrors(form, fields = {}) {
  clearFieldErrors(form);
  const unmatched = [];
  let first = null;
  for (const [path, reason] of Object.entries(fields)) {
    const wrapper = form.querySelector(`[data-field="${CSS.escape(path)}"]`);
    if (!wrapper) {
      unmatched.push(path);
      continue;
    }
    const msg = h('p', { class: 'field-error', id: uid('err'), localized: fieldReasonText(reason) });
    wrapper.append(msg);
    wrapper.classList.add('has-error');
    for (const input of wrapper.querySelectorAll('input, select, textarea')) {
      input.setAttribute('aria-invalid', 'true');
      const described = (input.getAttribute('aria-describedby') || '').split(' ').filter(Boolean);
      described.push(msg.id);
      input.setAttribute('aria-describedby', described.join(' '));
    }
    first ??= wrapper.querySelector('input, select, textarea');
  }
  first?.focus();
  return unmatched;
}

export function setFieldError(form, path, key) {
  showFieldErrors(form, {});
  const wrapper = form.querySelector(`[data-field="${CSS.escape(path)}"]`);
  if (!wrapper) return;
  const msg = h('p', { class: 'field-error', id: uid('err'), i18n: key });
  wrapper.append(msg);
  wrapper.classList.add('has-error');
  const input = wrapper.querySelector('input, select, textarea');
  if (input) {
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), msg.id].filter(Boolean).join(' '));
    input.focus();
  }
}

export function clearFieldErrors(form) {
  for (const msg of form.querySelectorAll('.field-error')) {
    for (const input of form.querySelectorAll(`[aria-describedby~="${msg.id}"]`)) {
      const rest = input.getAttribute('aria-describedby').split(' ').filter((id) => id !== msg.id);
      if (rest.length) input.setAttribute('aria-describedby', rest.join(' '));
      else input.removeAttribute('aria-describedby');
    }
    msg.remove();
  }
  for (const el of form.querySelectorAll('.has-error')) el.classList.remove('has-error');
  for (const el of form.querySelectorAll('[aria-invalid]')) el.removeAttribute('aria-invalid');
}

// Disable a button while a request runs. Returns a function that restores it.
export function busy(button) {
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  button.classList.add('is-busy');
  return () => {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.classList.remove('is-busy');
  };
}

export function loading(target) {
  target.replaceChildren(
    h('p', { class: 'loading', role: 'status' }, h('span', { class: 'spinner', 'aria-hidden': 'true' }), h('span', { i18n: 'common.loading' })),
  );
}

// Page-level error with a "Try again" button.
export function loadFailed(target, err, retry) {
  const box = h('div');
  showError(box, err);
  target.replaceChildren(box);
  if (retry && err?.code !== 'AUTH_REQUIRED') {
    box.append(h('p', {}, h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.retry', onclick: retry })));
  }
}

// Short "Saved" style message in the page's live region.
export function toast(key, args) {
  const region = document.getElementById('toast');
  if (!region) return;
  region.replaceChildren(h('p', { i18n: key, i18nArgs: args }));
  region.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    region.hidden = true;
    region.replaceChildren();
  }, 5000);
}

// Accessible yes/no dialog built on <dialog>. Resolves to true or false.
export function confirmDialog({ title, body, confirm, danger = false }) {
  return new Promise((resolve) => {
    const titleId = uid('dlg');
    const dialog = h(
      'dialog',
      { class: 'dialog', 'aria-labelledby': titleId },
      h('h2', { id: titleId, i18n: title }),
      body ? h('p', { i18n: body }) : null,
      h(
        'form',
        { method: 'dialog', class: 'actions' },
        h('button', { value: 'cancel', class: 'btn btn-secondary', i18n: 'common.cancel' }),
        h('button', { value: 'ok', class: danger ? 'btn btn-danger' : 'btn', i18n: confirm }),
      ),
    );
    dialog.addEventListener('close', () => {
      dialog.remove();
      resolve(dialog.returnValue === 'ok');
    });
    document.body.append(dialog);
    dialog.showModal();
  });
}

// Build "/login?next=<current page>" so the user comes back after logging in.
export function loginUrl(next = location.pathname + location.search) {
  return `/login?next=${encodeURIComponent(next)}`;
}

// Only follow `next` if it points to a page on this site.
export function safeNext(next, fallback = '/matches') {
  if (typeof next !== 'string' || !next.startsWith('/') || next.startsWith('//') || next.startsWith('/\\')) {
    return fallback;
  }
  return next;
}

export function daysUntil(iso) {
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}

export function mmss(seconds) {
  const s = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

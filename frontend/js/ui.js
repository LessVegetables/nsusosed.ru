// Small shared UI helpers. State lives in ARIA attributes (the design system styles those).

import { t } from './i18n.js';

/** Create an element: el('a', { class: 'btn', href: '/login' }, 'Text', childNode) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === false || value == null) continue;
    if (name === 'i18n') node.dataset.i18n = value;
    else if (name.startsWith('on')) node.addEventListener(name.slice(2), value);
    else node.setAttribute(name, value === true ? '' : value);
  }
  node.append(...children.filter((c) => c != null && c !== false));
  return node;
}

export function setBusy(button, busy) {
  button.setAttribute('aria-busy', String(busy));
  button.disabled = busy;
}

let toastTimer;

/** Green pop-up (red with { error: true }). One at a time. */
export function toast(title, text = '', { error = false, ms = 6000 } = {}) {
  document.querySelector('.toast')?.remove();
  clearTimeout(toastTimer);
  const node = el('div', { class: error ? 'toast error' : 'toast', role: error ? 'alert' : 'status' },
    el('b', {}, title), text,
    el('button', { class: 'close', type: 'button', 'aria-label': t('a11y.close'), onclick: () => node.remove() }, '×'));
  document.body.append(node);
  if (ms) toastTimer = setTimeout(() => node.remove(), ms);
  return node;
}

/** Translate an ApiError into a sentence for the person. */
export function errorText(err) {
  const key = `error.${err.code}`;
  const text = t(key, { seconds: err.retryAfter });
  return text === key ? t('error.generic') : text;
}

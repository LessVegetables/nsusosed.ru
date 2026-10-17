// Interface language: Russian (default) and English.
//
// Texts live in js/i18n/ru.js and js/i18n/en.js. Static HTML marks text with
// data-i18n="key" (and data-i18n-attr="placeholder:key" for attributes); JS
// uses bindText()/bindLocalized() so the text can be re-translated in place
// when the user switches language, without re-rendering forms.

import ru from './i18n/ru.js';
import en from './i18n/en.js';
import { local } from './storage.js';

const DICTS = { ru, en };
export const LANGS = ['ru', 'en'];
const STORAGE_KEY = 'nsusosed.lang';

// The language saved on this device, else the browser's. After login the
// account's language wins (layout.js); it is chosen once during onboarding and
// changed on the Account page.
function initialLang() {
  const saved = local.get(STORAGE_KEY);
  if (LANGS.includes(saved)) return saved;
  const browser = (navigator.languages?.[0] || navigator.language || '').toLowerCase();
  return browser && !browser.startsWith('ru') ? 'en' : 'ru';
}

let lang = initialLang();
document.documentElement.lang = lang;

export function getLang() {
  return lang;
}

export function locale() {
  return lang === 'ru' ? 'ru-RU' : 'en-GB';
}

export function setLang(next) {
  if (!LANGS.includes(next) || next === lang) return;
  lang = next;
  local.set(STORAGE_KEY, next);
  document.documentElement.lang = next;
  applyI18n();
  window.dispatchEvent(new CustomEvent('langchange', { detail: { lang } }));
}

// Pick the current language from a {ru, en} object (question labels from the
// API, error messages from errors.js).
export function pick(obj) {
  if (obj == null) return '';
  if (typeof obj === 'string') return obj;
  return obj[lang] || obj.ru || '';
}

// Argument values can be plain values, or objects resolved at render time so
// they follow the language too:
//   {t: 'key', args}  another translation key
//   {ru, en}          a localized pair
//   {date: iso}       a date, formatted for the current language
//   {num: n}          a number with locale grouping (15 000 / 15,000)
//   [ ... ]           a list of the above, joined with ", "
function resolveArg(value) {
  if (Array.isArray(value)) return value.map(resolveArg).join(', ');
  if (value && typeof value === 'object') {
    if ('t' in value) return t(value.t, value.args);
    if ('date' in value) return formatDate(value.date);
    if ('num' in value) return Number(value.num).toLocaleString(locale());
    return pick(value);
  }
  return value;
}

export function t(key, args = {}) {
  let text = DICTS[lang][key] ?? DICTS.ru[key];
  if (text === undefined) {
    console.warn(`[i18n] missing key: ${key}`);
    return key;
  }
  // Plural forms: {one, few, many, other}, chosen by args.count.
  if (typeof text === 'object') {
    const form = new Intl.PluralRules(locale()).select(Number(args.count ?? 0));
    text = text[form] ?? text.other;
  }
  return text.replace(/\{(\w+)\}/g, (match, name) =>
    name in args ? String(resolveArg(args[name])) : match,
  );
}

export function formatDate(iso, options = { day: 'numeric', month: 'long', year: 'numeric' }) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(locale(), options);
}

// Set an element's text from a key and remember the key for language changes.
export function bindText(el, key, args) {
  el.dataset.i18n = key;
  if (args) el.dataset.i18nArgs = JSON.stringify(args);
  else delete el.dataset.i18nArgs;
  delete el.dataset.i18nRu;
  delete el.dataset.i18nEn;
  el.textContent = t(key, args);
  return el;
}

// Same for a {ru, en} pair that comes from data rather than the dictionaries.
export function bindLocalized(el, obj) {
  delete el.dataset.i18n;
  delete el.dataset.i18nArgs;
  el.dataset.i18nRu = obj?.ru ?? '';
  el.dataset.i18nEn = obj?.en ?? '';
  el.textContent = pick(obj);
  return el;
}

export function applyI18n(root = document) {
  for (const el of root.querySelectorAll('[data-i18n]')) {
    const args = el.dataset.i18nArgs ? JSON.parse(el.dataset.i18nArgs) : undefined;
    el.textContent = t(el.dataset.i18n, args);
  }
  for (const el of root.querySelectorAll('[data-i18n-ru]')) {
    el.textContent = lang === 'en' && el.dataset.i18nEn ? el.dataset.i18nEn : el.dataset.i18nRu;
  }
  // data-i18n-attr="placeholder:key; aria-label:other.key"
  for (const el of root.querySelectorAll('[data-i18n-attr]')) {
    for (const pair of el.dataset.i18nAttr.split(';')) {
      const [attr, key] = pair.split(':').map((s) => s.trim());
      if (attr && key) el.setAttribute(attr, t(key));
    }
  }
}

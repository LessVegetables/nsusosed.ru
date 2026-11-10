// Translations: one flat dictionary per language in js/i18n/<lang>.js.
//
// Markup:  <p data-i18n="key">Русский текст по умолчанию</p>
//          <input data-i18n-attr="placeholder:key; aria-label:other.key">
// Strings: "Привет, {name}" takes parameters; "[[так же,]]" becomes the yellow headline
//          highlight (the only markup a translation can carry; it is built as DOM, never as HTML).
// Write every string in sentence case; uppercase comes from CSS.

import { KEYS, local, session } from './storage.js';

export const LANGS = ['ru', 'en', 'zh'];
export const LANG_NAMES = { ru: 'RU', en: 'EN', zh: '中文' };
const HTML_LANG = { ru: 'ru', en: 'en', zh: 'zh-CN' };

let lang = 'ru';
let dict = {};
let fallback = {};

/** Account language (cached) → a guest's pick for this tab → the browser's → Russian. */
export function detectLang() {
  const saved = local.get(KEYS.lang) || session.get(KEYS.lang);
  if (LANGS.includes(saved)) return saved;
  for (const tag of navigator.languages ?? [navigator.language ?? '']) {
    const short = tag.toLowerCase().slice(0, 2);
    if (LANGS.includes(short)) return short;
  }
  return 'ru';
}

export const currentLang = () => lang;

export function t(key, params) {
  let s = dict[key] ?? fallback[key] ?? key;
  if (params) s = s.replace(/\{(\w+)\}/g, (m, name) => (name in params ? String(params[name]) : m));
  return s;
}

/** Plain text of a translation (highlight markers removed), for attributes and titles. */
const plain = (s) => s.replace(/\[\[|\]\]/g, '');

function fill(el, text) {
  if (!text.includes('[[')) { el.textContent = text; return; }
  el.textContent = '';
  for (const part of text.split(/(\[\[.*?\]\])/)) {
    if (part.startsWith('[[')) {
      const mark = document.createElement('mark');
      mark.className = 'highlight';
      mark.textContent = part.slice(2, -2);
      el.append(mark);
    } else if (part) {
      el.append(part);
    }
  }
}

/** Translate everything under `root` (the whole page by default). */
export function translate(root = document) {
  for (const el of root.querySelectorAll('[data-i18n]')) {
    const text = t(el.dataset.i18n);
    if (el.tagName === 'TITLE') document.title = plain(text); else fill(el, text);
  }
  for (const el of root.querySelectorAll('[data-i18n-attr]')) {
    for (const pair of el.dataset.i18nAttr.split(';')) {
      const [attr, key] = pair.split(':').map((x) => x.trim());
      if (attr && key) el.setAttribute(attr, plain(t(key)));
    }
  }
}

async function load(code) {
  return (await import(`./i18n/${code}.js`)).default;
}

/** Load a language and translate the page. Russian is the fallback for a missing key. */
export async function setLang(code) {
  lang = LANGS.includes(code) ? code : 'ru';
  [dict, fallback] = await Promise.all([load(lang), lang === 'ru' ? {} : load('ru')]);
  document.documentElement.lang = HTML_LANG[lang];
  translate();
  document.dispatchEvent(new CustomEvent('langchange', { detail: lang }));
  return lang;
}

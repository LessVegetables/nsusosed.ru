// Shared page frame: language, session, header (with the phone tab bar) and footer.
//
// Every page calls initPage() once:
//   auth: 'none'     — public page, never asks the server who you are
//         'optional' — public page that looks different when logged in
//         'required' — sends guests to /login
//   onLangPick: puts the RU / EN / 中文 switch in a guest's header; called after each pick
// It resolves to { user } (null for a guest) after the page is translated and shown.

import { ApiError, get } from './api.js';
import { reportBug } from './errors.js';
import { detectLang, setLang, t, translate } from './i18n.js';
import { mountLangSwitch } from './lang-switch.js';
import { KEYS, local, session } from './storage.js';
import { el, toast } from './ui.js';

/** The header. Logged in: logo, then the sections centered (Account last); on phones the logo
 *  shrinks to the icon and the sections become a tab bar inside the header. A guest gets the
 *  language switch on the pages that offer one (landing, login), otherwise "Log in", on the right. */
function header(user, onLangPick) {
  const here = location.pathname.replace(/\.html$/, '');
  const current = (href) => (here === href ? 'page' : null);
  const logo = el('a', { class: 'logo', href: '/', 'data-i18n-attr': 'aria-label:nav.home' }, el('span', {}, 'nsu'), 'sosed');
  if (!user) {
    const action = onLangPick ? mountLangSwitch(el('div'), { onPick: onLangPick })
      : el('a', { class: 'btn', href: '/login', i18n: 'nav.login' });
    return el('div', { class: 'wrap' }, logo, action);
  }
  // Each nav gets its own labels: the tab bar's are short enough for a phone.
  const link = (href, label) => el('a', { href, ...label, 'aria-current': current(href) });
  return el('div', { class: 'wrap' },
    logo,
    el('a', { class: 'logo-icon', href: '/', 'data-i18n-attr': 'aria-label:nav.home' }, el('img', { src: '/img/logo-icon.svg', alt: '' })),
    el('nav', { class: 'site-nav', 'data-i18n-attr': 'aria-label:nav.label' }, link('/feed', { i18n: 'nav.feed' }), link('/home', { i18n: 'nav.myHome' }),
      link('/questionnaire', { i18n: 'nav.questionnaire' }), link('/account', { i18n: 'nav.account' })),
    el('nav', { class: 'tabbar', 'data-i18n-attr': 'aria-label:nav.label' }, link('/feed', { i18n: 'nav.feed' }), link('/home', { i18n: 'nav.homeShort' }),
      link('/questionnaire', { i18n: 'nav.questionnaire' }), link('/account', { i18n: 'nav.account' })));
}

function footer(user) {
  return el('div', { class: 'wrap' },
    el('span', { i18n: 'footer.tagline' }),
    el('nav', { class: 'row', 'data-i18n-attr': 'aria-label:footer.label' },
      // The language lives in the account; the footer only points there.
      user && el('a', { href: '/account#language', i18n: 'footer.language' }),
      el('a', { href: '/support', i18n: 'footer.support' }),
      el('a', { href: '/privacy', i18n: 'footer.privacy' })));
}

async function whoAmI(auth) {
  if (auth === 'none') return null;
  try {
    return await get('/me');
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
}

export async function initPage({ auth = 'optional', onLangPick } = {}) {
  const langReady = setLang(detectLang());
  let user = null;
  try {
    user = await whoAmI(auth);
  } catch (err) {
    // Server unreachable: public pages still render; private ones fall through to /login.
    reportBug(err, { where: 'initPage' });
  }
  if (!user && auth === 'required') {
    // Back to this page after logging in (routes.js). Not the hash: it can hold a code.
    session.set(KEYS.back, location.pathname.replace(/\.html$/, '') + location.search);
    location.replace('/login');
    return new Promise(() => {}); // the page is going away
  }
  await langReady;
  if (user) {
    local.set(KEYS.seenLogin, '1');
    if (user.language !== local.get(KEYS.lang)) {
      local.set(KEYS.lang, user.language);
      await setLang(user.language);
    }
  }

  document.querySelector('.site-header')?.replaceChildren(header(user, onLangPick));
  document.querySelector('.site-footer')?.replaceChildren(footer(user));
  translate();
  document.documentElement.dataset.ready = '';

  // A message left by the previous page ("flash.restored" → .title / .text).
  const flash = session.get(KEYS.flash);
  if (flash) {
    session.remove(KEYS.flash);
    toast(t(`${flash}.title`), t(`${flash}.text`));
  }
  return { user };
}

// Shared page frame: language, session, header (with the phone tab bar) and footer.
//
// Every page calls initPage() once:
//   auth: 'none'     — public page, never asks the server who you are
//         'optional' — public page that looks different when logged in
//         'required' — sends guests to /login
//   onLangPick: puts the RU / EN / 中文 switch in a guest's header; called after each pick
//   guestNav: shows a guest the sections too (the landing); they lead to /login and back
// It resolves to { user } (null for a guest) after the page is translated and shown.

import { ApiError, get } from './api.js';
import { reportBug } from './errors.js';
import { detectLang, setLang, t, translate } from './i18n.js';
import { mountLangSwitch } from './lang-switch.js';
import { withCampaign } from './routes.js';
import { KEYS, local, session } from './storage.js';
import { el, toast } from './ui.js';

/** The header. Logged in: logo, then the sections centered (Account last); on phones the logo
 *  shrinks to the icon and the sections become a tab bar inside the header. A guest gets the
 *  language switch on the pages that offer one (landing, login), otherwise "Log in", on the right.
 *  With guestNav (the landing) a guest also sees the sections, with "Log in" in place of Account;
 *  the pages behind them send guests to /login and back. On phones the language switch moves to
 *  the footer there: the tab bar fills the header. */
function header(user, { onLangPick, guestNav }) {
  const here = location.pathname.replace(/\.html$/, '');
  const current = (href) => (here === href ? 'page' : null);
  const logo = el('a', { class: 'logo', href: '/', 'data-i18n-attr': 'aria-label:nav.home' }, el('span', {}, 'nsu'), 'sosed');
  const login = (attrs = { class: 'btn' }) => el('a', { ...attrs, href: '/login', i18n: 'nav.login' });
  if (!user && !guestNav) {
    return el('div', { class: 'wrap' }, logo, onLangPick ? mountLangSwitch(el('div'), { onPick: onLangPick }) : login());
  }
  // Each nav gets its own labels: the tab bar's are short enough for a phone.
  const link = (href, label) => el('a', { href, ...label, 'aria-current': current(href) });
  const nav = (cls, home, last) => el('nav', { class: cls, 'data-i18n-attr': 'aria-label:nav.label' },
    link('/feed', { i18n: 'nav.feed' }), link('/home', home), link('/questionnaire', { i18n: 'nav.questionnaire' }), last);
  return el('div', { class: 'wrap' },
    logo,
    el('a', { class: 'logo-icon', href: '/', 'data-i18n-attr': 'aria-label:nav.home' }, el('img', { src: '/img/logo-icon.svg', alt: '' })),
    nav('site-nav', { i18n: 'nav.myHome' }, user && link('/account', { i18n: 'nav.account' })),
    nav('tabbar', { i18n: 'nav.homeShort' }, user ? link('/account', { i18n: 'nav.account' }) : login({})),
    !user && el('div', { class: 'row' }, onLangPick && mountLangSwitch(el('div'), { onPick: onLangPick }), login()));
}

function footer(user, { onLangPick, guestNav }) {
  return el('div', { class: 'wrap' },
    el('span', { i18n: 'footer.tagline' }),
    !user && guestNav && onLangPick && el('div', { class: 'footer-lang' }, mountLangSwitch(el('div'), { onPick: onLangPick })),
    el('nav', { class: 'row', 'data-i18n-attr': 'aria-label:footer.label' },
      // The language lives in the account; the footer only points there.
      user && el('a', { href: '/account#language', i18n: 'footer.language' }),
      el('a', { href: '/support', i18n: 'footer.support' }),
      el('a', { href: '/agreement', i18n: 'footer.agreement' }),
      el('a', { href: '/rules', i18n: 'footer.rules' }),
      el('a', { href: '/privacy', i18n: 'footer.privacy' })),
    el('div', { class: 'footer-note' },
      el('span', { i18n: 'footer.unaffiliated' }),
      el('span', { i18n: 'footer.byStudents' })));
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

export async function initPage({ auth = 'optional', onLangPick, guestNav = false } = {}) {
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
    location.replace(withCampaign('/login', location.search));
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

  document.querySelector('.site-header')?.replaceChildren(header(user, { onLangPick, guestNav }));
  document.querySelector('.site-footer')?.replaceChildren(footer(user, { onLangPick, guestNav }));
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

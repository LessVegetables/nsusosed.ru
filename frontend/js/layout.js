// Shared page frame: language, session, header and footer.
//
// Every page calls initPage() once:
//   auth: 'none'     — public page, never asks the server who you are
//         'optional' — public page that looks different when logged in
//         'required' — sends guests to /login
// It resolves to { user } (null for a guest) after the page is translated and shown.

import { ApiError, get } from './api.js';
import { detectLang, setLang, t, translate } from './i18n.js';
import { KEYS, local, session } from './storage.js';
import { el, toast } from './ui.js';

function header(user) {
  const action = user
    ? el('a', { class: 'btn secondary', href: '/account', i18n: 'nav.account' })
    : location.pathname.startsWith('/login') ? null : el('a', { class: 'btn', href: '/login', i18n: 'nav.login' });
  const here = location.pathname.replace(/\.html$/, '');
  const current = (href) => (here === href ? 'page' : null);
  return el('div', { class: 'wrap' },
    el('a', { class: 'logo', href: '/', 'data-i18n-attr': 'aria-label:nav.home' }, el('span', {}, 'nsu'), 'sosed'),
    user && el('nav', { class: 'site-nav', 'data-i18n-attr': 'aria-label:nav.label' }, 
      el('a', { href: '/home', i18n: 'nav.myHome', 'aria-current': current('/home') }),
      el('a', { href: '/questionnaire', i18n: 'nav.questionnaire', 'aria-current': current('/questionnaire') })),
    action);
}

function footer(user) {
  return el('div', { class: 'wrap' },
    el('span', { i18n: 'footer.tagline' }),
    el('nav', { class: 'row', 'data-i18n-attr': 'aria-label:footer.label' },
      // The language lives in the account; the footer only points there.
      user && el('a', { href: '/account#language', i18n: 'footer.language' }),
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

export async function initPage({ auth = 'optional' } = {}) {
  const langReady = setLang(detectLang());
  let user = null;
  try {
    user = await whoAmI(auth);
  } catch {
    // Server unreachable: public pages still render; private ones fall through to /login.
  }
  if (!user && auth === 'required') {
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

  document.querySelector('.site-header')?.replaceChildren(header(user));
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

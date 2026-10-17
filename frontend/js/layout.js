// Shared page frame: which menu links to show, the account's language, the
// mock-API banner, the login check and sending unfinished accounts to
// onboarding. Every page script starts with
//   const { me } = await initPage({ auth: 'required' });

import { api } from './api.js';
import { MOCK_LOGIN_CODE, USE_MOCK } from './config.js';
import { applyI18n, setLang } from './i18n.js';
import { h, loadFailed, loginUrl } from './ui.js';

// Seekers look for a place; hosts live in a home (or are about to list one).
export function roleOf(me) {
  if (!me) return 'guest';
  return me.home || me.situation === 'host' ? 'host' : 'seeker';
}

// Where "home" is for this user: the logo and the end of onboarding go there.
export function startPage(me) {
  return roleOf(me) === 'host' ? '/home' : '/matches';
}

// The account still needs onboarding: a language, a role and a questionnaire
// of the current version.
export function needsOnboarding(me) {
  return Boolean(me) && (!me.language || !me.situation || !me.profile_complete);
}

// The header and footer are static markup in every page. Menu items carry
// data-show="guest | seeker | host | onboarding" (several allowed) and start hidden.
function showNav(me) {
  // During onboarding there's no role yet: only Account (to log out).
  const role = needsOnboarding(me) ? 'onboarding' : roleOf(me);
  for (const item of document.querySelectorAll('.site-nav [data-show]')) {
    item.hidden = !item.dataset.show.split(' ').includes(role);
  }
  if (me) document.querySelector('.brand')?.setAttribute('href', startPage(me));
}

function renderMockBanner() {
  if (!USE_MOCK) return;
  document.body.prepend(
    h(
      'div',
      { class: 'mock-banner', role: 'note' },
      h('span', { i18n: 'mock.banner', i18nArgs: { code: MOCK_LOGIN_CODE } }),
      ' ',
      h('a', { href: '?mock=0', i18n: 'mock.turnOff' }),
    ),
  );
}

// auth: 'required' → redirect to /login when logged out;
//       'optional' → load the user if there is one;
//       'none'     → don't ask the API at all.
// onboarding: true on pages an unfinished account may use as they are
// (the questionnaire itself, /join, Account, static pages); everywhere else
// such an account is sent to the questionnaire first.
export async function initPage({ auth = 'required', onboarding = false } = {}) {
  applyI18n();
  renderMockBanner();

  let me = null;
  if (auth !== 'none') {
    try {
      me = await api.getMe();
    } catch (err) {
      if (err.code === 'AUTH_REQUIRED') {
        if (auth === 'required') {
          location.replace(loginUrl());
          return new Promise(() => {}); // The page is going away.
        }
      } else if (auth === 'required') {
        loadFailed(document.getElementById('main'), err, () => location.reload());
        return new Promise(() => {});
      }
    }
  }
  if (me?.language) setLang(me.language);
  if (needsOnboarding(me) && !onboarding) {
    const next = location.pathname + location.search;
    location.replace(`/questionnaire?next=${encodeURIComponent(next)}`);
    return new Promise(() => {});
  }
  showNav(me);
  return { me };
}

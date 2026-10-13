// Shared page frame: header with navigation and language switch, footer, the
// mock-API banner and the login check. Every page script starts with
//   const { me } = await initPage({ auth: 'required', nav: 'matches' });

import { api } from './api.js';
import { MOCK_LOGIN_CODE, USE_MOCK } from './config.js';
import { applyI18n, getLang, setLang } from './i18n.js';
import { h, loadFailed, loginUrl } from './ui.js';

const NAV = [
  { id: 'matches', href: '/matches', key: 'nav.matches' },
  { id: 'questionnaire', href: '/questionnaire', key: 'nav.questionnaire' },
  { id: 'my-listing', href: '/my-listing', key: 'nav.myListing' },
  { id: 'account', href: '/account', key: 'nav.account' },
];

let langSwitch = null;

// Created once: the header is rendered twice (before and after the login check).
function langButton() {
  if (langSwitch) return langSwitch;
  // The button is labelled in the language it switches to.
  const button = h('button', { type: 'button', class: 'lang-switch' });
  langSwitch = button;
  const update = () => {
    const other = getLang() === 'ru' ? 'en' : 'ru';
    button.textContent = other === 'en' ? 'English' : 'Русский';
    button.lang = other;
  };
  button.addEventListener('click', () => setLang(getLang() === 'ru' ? 'en' : 'ru'));
  window.addEventListener('langchange', update);
  update();
  return button;
}

// `me` undefined = still checking the session: brand and language only.
function renderHeader(me, current) {
  const header = document.getElementById('site-header');
  if (!header) return;
  const links = me === undefined ? [] : me
    ? NAV.map((item) =>
        h('li', {}, h('a', { href: item.href, i18n: item.key, 'aria-current': item.id === current ? 'page' : null })),
      )
    : [h('li', {}, h('a', { href: '/login', i18n: 'nav.login', 'aria-current': current === 'login' ? 'page' : null }))];

  header.replaceChildren(
    h(
      'div',
      { class: 'header-inner' },
      h('a', { class: 'brand', href: me ? '/matches' : '/' }, 'nsusosed'),
      h('nav', { class: 'site-nav', 'aria-label': 'Main', 'data-i18n-attr': 'aria-label:nav.label' }, h('ul', {}, links)),
      langButton(),
    ),
  );
  applyI18n(header);
}

function renderFooter() {
  const footer = document.getElementById('site-footer');
  if (!footer) return;
  footer.replaceChildren(
    h(
      'div',
      { class: 'footer-inner' },
      h('p', { i18n: 'footer.tagline' }),
      h('p', {}, h('a', { href: '/privacy', i18n: 'footer.privacy' })),
    ),
  );
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
export async function initPage({ auth = 'required', nav = null } = {}) {
  applyI18n();
  renderMockBanner();
  renderHeader(undefined, nav);
  renderFooter();

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
        renderHeader(null, nav);
        loadFailed(document.getElementById('main'), err, () => location.reload());
        return new Promise(() => {});
      }
    }
  }
  renderHeader(me, nav);
  return { me };
}

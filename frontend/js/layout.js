// Shared page frame: the language switch, which menu links to show, the
// mock-API banner and the login check. Every page script starts with
//   const { me } = await initPage({ auth: 'required' });

import { api } from './api.js';
import { MOCK_LOGIN_CODE, USE_MOCK } from './config.js';
import { applyI18n, getLang, setLang } from './i18n.js';
import { h, loadFailed, loginUrl } from './ui.js';

// The header and footer are static markup in every page. On pages that work
// both logged in and logged out (/, /login, /join, /privacy, 404) the menu has
// both sets of links, all hidden: data-auth="in" for users, "out" for guests.
function showNav(me) {
  for (const item of document.querySelectorAll('.site-nav [data-auth]')) {
    item.hidden = item.dataset.auth !== (me ? 'in' : 'out');
  }
  if (me) document.querySelector('.brand')?.setAttribute('href', '/matches');
}

// The button is labelled in the language it switches to.
function initLangSwitch() {
  const button = document.querySelector('.lang-switch');
  if (!button) return;
  const update = () => {
    const other = getLang() === 'ru' ? 'en' : 'ru';
    button.textContent = other === 'en' ? 'English' : 'Русский';
    button.lang = other;
  };
  button.addEventListener('click', () => setLang(getLang() === 'ru' ? 'en' : 'ru'));
  window.addEventListener('langchange', update);
  update();
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
export async function initPage({ auth = 'required' } = {}) {
  applyI18n();
  renderMockBanner();
  initLangSwitch();

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
  showNav(me);
  return { me };
}

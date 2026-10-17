// / — short intro. Logged-in users get a link straight to their matches or home.

import { initPage, startPage } from '../layout.js';
import { h } from '../ui.js';

const { me } = await initPage({ auth: 'optional' });

if (me) {
  const host = startPage(me) === '/home';
  document.getElementById('cta').replaceChildren(
    h('a', { class: 'btn', href: startPage(me), i18n: host ? 'home.toHome' : 'home.toMatches' }));
}

const params = new URLSearchParams(location.search);
if (params.get('deleted') === '1') {
  document.getElementById('notice').replaceChildren(
    h('div', { class: 'alert alert-success', role: 'status' }, h('p', { i18n: 'home.deleted' })),
  );
  history.replaceState(null, '', '/');
}

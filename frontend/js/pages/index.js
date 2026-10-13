// / — short intro. Logged-in users get a link straight to their matches.

import { initPage } from '../layout.js';
import { h } from '../ui.js';

const { me } = await initPage({ auth: 'optional' });

if (me) {
  document.getElementById('cta').replaceChildren(h('a', { class: 'btn', href: '/matches', i18n: 'home.toMatches' }));
}

const params = new URLSearchParams(location.search);
if (params.get('deleted') === '1') {
  document.getElementById('notice').replaceChildren(
    h('div', { class: 'alert alert-success', role: 'status' }, h('p', { i18n: 'home.deleted' })),
  );
  history.replaceState(null, '', '/');
}

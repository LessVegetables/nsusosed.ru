// /join#token=... — become a resident of a listing through an invite link.
//
// The token is read from the hash (never sent to the server in the URL),
// kept in sessionStorage while the user logs in or fills in the questionnaire,
// and removed from the address bar right away.

import { api } from '../api.js';
import { initPage, needsOnboarding } from '../layout.js';
import { session } from '../storage.js';
import { busy, h, showError } from '../ui.js';

const TOKEN_KEY = 'nsusosed.invite';

const fromHash = new URLSearchParams(location.hash.slice(1)).get('token');
if (fromHash) {
  session.set(TOKEN_KEY, fromHash);
  history.replaceState(null, '', '/join');
}
const token = fromHash || session.get(TOKEN_KEY);

const { me } = await initPage({ auth: 'optional', onboarding: true });
const content = document.getElementById('content');

function step(textKey, href, buttonKey, args) {
  content.replaceChildren(
    h('div', { class: 'card stack' },
      h('p', { i18n: textKey, i18nArgs: args }),
      h('p', {}, h('a', { class: 'btn', href, i18n: buttonKey }))),
  );
}

function joined() {
  content.replaceChildren(
    h('div', { class: 'alert alert-success stack', role: 'status' },
      h('p', { i18n: 'join.done' }),
      h('p', { class: 'actions' },
        h('a', { class: 'btn', href: '/home', i18n: 'join.toHome' }))),
  );
}

function confirmStep() {
  const error = h('div', { hidden: true });
  const button = h('button', { type: 'button', class: 'btn', i18n: 'join.join' });
  button.addEventListener('click', async () => {
    const done = busy(button);
    try {
      await api.joinRoom(token);
      session.remove(TOKEN_KEY);
      joined();
    } catch (err) {
      done();
      if (err.code === 'INVITE_INVALID' || err.code === 'INVITE_EXPIRED') {
        session.remove(TOKEN_KEY);
        button.remove();
      }
      showError(error, err);
      if (err.code === 'ALREADY_IN_ROOM') error.append(h('p', {}, h('a', { href: '/home', i18n: 'nav.home' })));
      if (err.code === 'PROFILE_REQUIRED') error.append(h('p', {}, h('a', { href: '/questionnaire?next=/join', i18n: 'matches.fillIn' })));
    }
  });
  content.replaceChildren(
    h('div', { class: 'card stack' },
      h('p', { i18n: 'join.question' }),
      h('p', { class: 'muted', 'data-private': true, i18n: 'join.explain', i18nArgs: { name: me.display_name } }),
      h('div', { class: 'actions' }, button),
      error),
  );
}

async function start() {
  if (!token) {
    content.replaceChildren(h('div', { class: 'alert alert-error', role: 'alert' }, h('p', { i18n: 'join.noToken' })));
    return;
  }
  if (!me) {
    step('join.needLogin', '/login?next=/join', 'nav.login');
    return;
  }
  // A new account answers the questionnaire first; it then comes back here.
  if (needsOnboarding(me)) step('join.needProfile', '/questionnaire?next=/join', 'matches.fillIn');
  else confirmStep();
}

await start();

// Comparing with friends. The link looks like /compare#code=K7QM2XWP.
//
// Opening a friend's link joins their comparison right away, before the questionnaire, so the
// friend can watch the progress ("12 of 20"). Someone who still has to answer goes on to the
// questionnaire and comes back here when done. People who aren't logged in log in first; the
// code waits in this tab (routes.js sends them back here).
//
// Nobody sees anybody's answers here: progress counts while people answer, then the score
// (rounded percent and topic badges) once both are done.

import { ApiError, del, get, post } from '../api.js';
import { breakdown, chips } from '../compat.js';
import { t } from '../i18n.js';
import { initPage } from '../layout.js';
import { KEYS, session } from '../storage.js';
import { el, errorText, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);
const fromHash = new URLSearchParams(location.hash.slice(1)).get('code') ?? '';

// Same as invites: keep the code across the login detour and out of the address bar (the
// analytics recorder keeps page addresses).
if (fromHash) {
  session.set(KEYS.compare, fromHash);
  history.replaceState(null, '', '/compare');
}
const { user } = await initPage({ auth: 'required' });

// "Came by a friend's link" is only needed until the questionnaire is done.
if (user.questionnaire_complete) session.remove(KEYS.compared);
const pending = session.get(KEYS.compare);
if (pending) {
  session.remove(KEYS.compare);
  try {
    const group = await post('/compare/join', { code: pending });
    if (!user.questionnaire_complete) {
      // The questionnaire says who asked, and skips "what are you looking for?" at the end.
      session.set(KEYS.compared, group.members.find((m) => !m.is_you)?.first_name ?? '');
      location.replace('/questionnaire');
      await new Promise(() => {});
    }
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true, ms: 0 });
  }
}

$('housing').hidden = user.intent !== 'compare';

let groups = [];
let link = null;

const avatar = (person) => (person.avatar_url
  ? el('img', { class: 'avatar sm', src: person.avatar_url, alt: '' })
  : el('span', { class: 'avatar sm', 'aria-hidden': 'true' }, person.first_name.slice(0, 1)));

function status(person, mineDone) {
  if (person.compatibility) return null;
  if (!person.complete) return el('p', { class: 'meta' }, t('compare.waiting', { done: person.answered, total: person.total }));
  return el('p', { class: 'meta' }, mineDone ? t('compare.done') : t('compare.youFirst'));
}

function personHead(person, mineDone) {
  const pct = person.compatibility && el('span', { class: 'pct person-pct' }, `${person.compatibility.percent}%`);
  return el('div', { class: 'row person-head' }, avatar(person),
    el('div', { class: 'person-name' }, el('h3', {}, person.first_name), status(person, mineDone)), pct);
}

/** Two people: the person, then the five topics in words across the whole box. */
function pairNodes(person, mineDone) {
  return [personHead(person, mineDone), person.compatibility && breakdown(person.compatibility)];
}

/** A bigger company: a card per person with chips. */
function personCard(person, mineDone) {
  return el('li', { class: 'box pad resident-card' }, personHead(person, mineDone),
    person.compatibility && chips(person.compatibility));
}

function groupNode(group) {
  const me = group.members.find((m) => m.is_you);
  const others = group.members.filter((m) => !m.is_you);
  const names = others.map((m) => m.first_name).join(', ');
  return el('section', { class: 'box pad cgroup', 'aria-label': t('compare.with', { names }) },
    el('div', { class: 'row cgroup-head' },
      el('h2', {}, t('compare.with', { names })),
      el('button', { class: 'linkbtn', type: 'button', onclick: () => leave(group) }, t('compare.leave'))),
    !me.complete && el('p', { class: 'note' }, `⚠ ${t('compare.finishFirst', { done: me.answered, total: me.total })} `,
      el('a', { href: '/questionnaire' }, t('compare.toQuiz'))),
    group.compatibility && el('div', { class: 'row coverall' },
      el('span', { class: 'pct' }, `${group.compatibility.percent}%`), el('span', { class: 'meta' }, t('compare.overall'))),
    group.compatibility && breakdown(group.compatibility),
    ...(others.length === 1
      ? pairNodes(others[0], me.complete)
      : [el('ul', { class: 'resident-cards' }, ...others.map((p) => personCard(p, me.complete)))]));
}

function render() {
  // The link nobody has opened yet is the share box, not a comparison.
  const shown = groups.filter((g) => g.members.length > 1);
  $('groups').replaceChildren(...shown.map(groupNode));
  $('groups').hidden = !shown.length;
  if (link) $('share-url').value = link.url;
}

async function load() {
  [groups, link] = await Promise.all([get('/compare'), post('/compare')]);
  render();
  watch();
}

async function leave(group) {
  try {
    await del(`/compare/${group.id}/membership`);
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true });
    return;
  }
  toast(t('compare.left'), '', { ms: 2500 });
  await load();
}

// While someone is still answering, check now and then, so the result shows up on its own.
let timer;
function watch() {
  clearTimeout(timer);
  const waiting = groups.some((g) => g.members.length > 1 && g.members.some((m) => !m.complete));
  if (waiting) timer = setTimeout(() => (document.hidden ? watch() : refresh()), 20000);
}

async function refresh() {
  try {
    groups = await get('/compare');
    render();
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
  }
  watch();
}
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });

$('share-copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('share-url').value);
    toast(t('compare.share.copied'), '', { ms: 2000 });
  } catch {
    $('share-url').select();
  }
});

await load();
document.addEventListener('langchange', render);
$('share-url').addEventListener('focus', (e) => e.target.select());

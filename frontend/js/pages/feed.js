// The feed: rooms with free places, best match first. Two tabs above the list: dorm rooms
// and apartments. Dorm rooms are limited to the buildings of the person's faculty, and every
// list to rooms they could move into by gender, until they ask to see more.

import { ApiError, get } from '../api.js';
import { chips } from '../compat.js';
import { t } from '../i18n.js';
import { initPage } from '../layout.js';
import { el, errorText } from '../ui.js';

const $ = (id) => document.getElementById(id);
const FILLS = ['fill-blue', 'fill-pink', 'fill-orange', 'fill-green', 'fill-purple'];

const { user } = await initPage({ auth: 'required' });
if (!user.questionnaire_complete) {
  location.replace('/questionnaire');
  await new Promise(() => {});
}
const meta = await get('/meta');
const dormName = (id) => t('home.dorm.n', { name: meta.dorms.find((d) => d.id === id)?.name ?? id });

const params = new URLSearchParams(location.search);
const state = {
  kind: ['dorm', 'apartment'].includes(params.get('kind')) ? params.get('kind') : user.intent === 'seek_apt' ? 'apartment' : 'dorm',
  wholeCampus: false, anyGender: false, feed: null, error: null,
};

const genderLabel = (g) => ({ f: t('feed.gender.f'), m: t('feed.gender.m'), any: t('feed.gender.any') }[g]);
const rub = (n) => `${n.toLocaleString('ru-RU')} ₽`;

function card(item, index) {
  const title = item.kind === 'dorm' ? dormName(item.building) : (item.room_name || t('feed.apartment'));
  const meta1 = item.kind === 'dorm'
    ? t('feed.places', { free: item.free_places, total: item.capacity })
    : `${item.district} · ${t('feed.places', { free: item.free_places, total: item.capacity })}`;
  return el('a', { class: 'card box', href: `/room?id=${item.room_id}` },
    el('div', { class: `top ${FILLS[index % FILLS.length]}` },
      item.cover_url && el('img', { class: 'cover', src: item.cover_url, alt: '', loading: 'lazy' }),
      el('span', { class: 'emoji' }, item.emoji),
      item.compatibility && el('span', { class: 'pct', 'aria-label': t('feed.percentLabel', { n: item.compatibility.percent }) }, `${item.compatibility.percent}%`)),
    el('div', { class: 'body' },
      el('h3', {}, title),
      el('p', { class: 'meta' }, meta1),
      el('p', { class: 'meta' }, [genderLabel(item.gender), item.rent_rub != null && rub(item.rent_rub), t('feed.residents', { n: item.residents })].filter(Boolean).join(' · ')),
      item.compatibility ? chips(item.compatibility) : el('p', { class: 'note' }, `⚠ ${t('feed.noScore')}`),
      item.outside_faculty && el('p', { class: 'note' }, `⚠ ${t('feed.outside')}`)));
}

function render() {
  for (const tab of document.querySelectorAll('[role=tab]')) tab.setAttribute('aria-selected', String(tab.dataset.kind === state.kind));
  $('list').setAttribute('aria-labelledby', `tab-${state.kind}`);
  if (state.error) {
    $('count').textContent = '';
    $('list').replaceChildren(el('p', { class: 'note error' }, `✕ ${state.error}`));
    $('more').replaceChildren();
    return;
  }
  if (!state.feed) {
    $('count').textContent = t('feed.loading');
    $('list').replaceChildren();
    $('more').replaceChildren();
    return;
  }
  const { items, hidden_by_faculty: byFaculty, hidden_by_gender: byGender } = state.feed;
  $('count').textContent = items.length ? t('feed.count', { n: items.length }) : '';
  $('list').replaceChildren(items.length
    ? el('div', { class: 'cards' }, ...items.map(card))
    : el('div', { class: 'box pad empty' },
      el('h2', {}, t('feed.empty.title')),
      el('p', {}, state.kind === 'dorm' && byFaculty ? t('feed.empty.faculty') : t('feed.empty.text'))));

  const more = [];
  if (state.kind === 'dorm' && !state.wholeCampus) {
    more.push(el('button', { class: 'btn secondary', type: 'button', onclick: () => $('campus-dialog').showModal() },
      byFaculty ? t('feed.more.campusN', { n: byFaculty }) : t('feed.more.campus')));
  }
  if (!state.anyGender && byGender) {
    more.push(el('button', { class: 'btn secondary', type: 'button', onclick: () => { state.anyGender = true; load(); } },
      t('feed.more.gender', { n: byGender })));
  }
  $('more').replaceChildren(...more);
}

async function load() {
  state.feed = null;
  state.error = null;
  render();
  const kind = state.kind;
  try {
    const query = new URLSearchParams({ kind, whole_campus: state.wholeCampus, any_gender: state.anyGender });
    const feed = await get(`/feed?${query}`);
    if (kind !== state.kind) return; // the tab changed while this was loading
    state.feed = feed;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return; }
    state.error = errorText(err);
  }
  render();
}

const tabs = [...document.querySelectorAll('[role=tab]')];
tabs.forEach((tab, i) => {
  tab.addEventListener('click', () => {
    if (state.kind === tab.dataset.kind) return;
    state.kind = tab.dataset.kind;
    history.replaceState(null, '', `/feed?kind=${state.kind}`);
    load();
  });
  // Arrow keys move between tabs, as people expect of a tab list.
  tab.addEventListener('keydown', (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    next.focus();
    next.click();
  });
});

$('campus-no').addEventListener('click', () => $('campus-dialog').close());
$('campus-yes').addEventListener('click', () => { $('campus-dialog').close(); state.wholeCampus = true; load(); });

document.addEventListener('langchange', render);
load();

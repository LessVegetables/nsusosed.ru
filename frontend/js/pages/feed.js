// The feed: rooms this person could move into, best match first. Two tabs above the list: dorm
// rooms and apartments. Every other listing (full, for another gender, a dorm outside their
// faculty) waits at the bottom behind "show all listings".

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
  showAll: false, feed: null, error: null,
};

const genderLabel = (g) => ({ f: t('feed.gender.f'), m: t('feed.gender.m'), any: t('feed.gender.any') }[g]);
const rub = (n) => `${n.toLocaleString('ru-RU')} ₽`;

// Why a room from the bottom list doesn't fit, as notes on its card.
function unfitNotes(item) {
  return [
    item.free_places <= 0 && t('feed.full'),
    item.wrong_gender && t('feed.wrongGender'),
    item.outside_faculty && t('feed.outside'),
  ].filter(Boolean).map((text) => el('p', { class: 'note' }, `⚠ ${text}`));
}

function card(item, index, unfit = false) {
  const title = item.kind === 'dorm' ? dormName(item.building) : (item.room_name || t('feed.apartment'));
  const meta1 = item.kind === 'dorm'
    ? t('feed.places', { free: item.free_places, total: item.capacity })
    : `${item.district} · ${t('feed.places', { free: item.free_places, total: item.capacity })}`;
  const pct = item.compatibility && t('feed.percentLabel', { n: item.compatibility.percent });
  return el('a', { class: unfit ? 'card box unfit' : 'card box', href: `/room?id=${item.room_id}` },
    el('div', { class: unfit ? 'top' : `top ${FILLS[index % FILLS.length]}` },
      item.cover_url && el('img', { class: 'cover', src: item.cover_url, alt: '', loading: 'lazy' }),
      el('span', { class: 'emoji' }, item.emoji),
      // A room that doesn't fit says so in the badge; its percent moves into the text.
      unfit
        ? el('span', { class: 'pct' }, item.free_places <= 0 ? t('feed.unfit.full') : t('feed.unfit.other'))
        : item.compatibility && el('span', { class: 'pct', 'aria-label': pct }, `${item.compatibility.percent}%`)),
    el('div', { class: 'body' },
      el('h3', {}, title),
      el('p', { class: 'meta' }, meta1),
      el('p', { class: 'meta' }, [genderLabel(item.gender), item.rent_rub != null && rub(item.rent_rub), t('feed.residents', { n: item.residents })].filter(Boolean).join(' · ')),
      unfit && pct && el('p', { class: 'meta' }, pct),
      item.compatibility ? chips(item.compatibility) : el('p', { class: 'note' }, `⚠ ${t('feed.noScore')}`),
      ...(unfit ? unfitNotes(item) : [item.outside_faculty && el('p', { class: 'note' }, `⚠ ${t('feed.outside')}`)])));
}

function render() {
  for (const tab of document.querySelectorAll('[role=tab]')) tab.setAttribute('aria-selected', String(tab.dataset.kind === state.kind));
  $('list').setAttribute('aria-labelledby', `tab-${state.kind}`);
  if (state.error || !state.feed) $('others').replaceChildren();
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
  const { items, others } = state.feed;
  $('count').textContent = items.length ? t('feed.count', { n: items.length }) : '';
  $('list').replaceChildren(items.length
    ? el('div', { class: 'cards' }, ...items.map((item, i) => card(item, i)))
    : el('div', { class: 'box pad empty' },
      el('h2', {}, t('feed.empty.title')),
      el('p', {}, others.length ? t('feed.empty.others') : t('feed.empty.text'))));

  if (!others.length) {
    $('more').replaceChildren();
    $('others').replaceChildren();
    return;
  }
  $('more').replaceChildren(el('button', {
    class: 'btn secondary', type: 'button', 'aria-expanded': String(state.showAll), 'aria-controls': 'others',
    onclick: () => { state.showAll = !state.showAll; render(); },
  }, state.showAll ? t('feed.more.hide') : t('feed.more.show', { n: others.length })));
  $('others').replaceChildren(...(state.showAll ? [
    el('h2', { class: 'title' }, t('feed.others.title')),
    el('p', { class: 'note' }, t('feed.others.text')),
    el('div', { class: 'cards' }, ...others.map((item, i) => card(item, i, true))),
  ] : []));
}

async function load() {
  state.feed = null;
  state.error = null;
  render();
  const kind = state.kind;
  try {
    const feed = await get(`/feed?${new URLSearchParams({ kind })}`);
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

document.addEventListener('langchange', render);
load();

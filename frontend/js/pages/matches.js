// /matches?kind=dorm|apartment&page=N — listings sorted by compatibility.

import { api } from '../api.js';
import { MATCHES_PAGE_SIZE } from '../config.js';
import { initPage } from '../layout.js';
import { explanation, listingTitle, scoreBadge, warnings } from '../listing-view.js';
import { h, loadFailed, loading } from '../ui.js';

const KINDS = ['dorm', 'apartment'];

await initPage({ auth: 'required', nav: 'matches' });

const params = new URLSearchParams(location.search);
let kind = KINDS.includes(params.get('kind')) ? params.get('kind') : 'dorm';
let page = Math.max(1, Number.parseInt(params.get('page'), 10) || 1);
let requestId = 0;

const panel = document.getElementById('panel');
const tabs = [...document.querySelectorAll('[role="tab"]')];

function updateTabs() {
  for (const tab of tabs) {
    const selected = tab.dataset.kind === kind;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
  }
  panel.setAttribute('aria-labelledby', `tab-${kind}`);
}

function updateUrl() {
  const query = new URLSearchParams({ kind });
  if (page > 1) query.set('page', String(page));
  history.replaceState(null, '', `/matches?${query}`);
}

function selectKind(next) {
  if (next === kind) return;
  kind = next;
  page = 1;
  updateTabs();
  load();
}

// Keyboard support from the ARIA tabs pattern: arrows, Home, End.
for (const tab of tabs) {
  tab.addEventListener('click', () => selectKind(tab.dataset.kind));
  tab.addEventListener('keydown', (event) => {
    const index = tabs.indexOf(tab);
    let target = null;
    if (event.key === 'ArrowRight') target = tabs[(index + 1) % tabs.length];
    else if (event.key === 'ArrowLeft') target = tabs[(index - 1 + tabs.length) % tabs.length];
    else if (event.key === 'Home') target = tabs[0];
    else if (event.key === 'End') target = tabs[tabs.length - 1];
    if (!target) return;
    event.preventDefault();
    target.focus();
    selectKind(target.dataset.kind);
  });
}

function card(item) {
  const c = item.compatibility;
  return h(
    'li',
    {},
    h(
      'article',
      { class: 'card match-card' },
      h(
        'div',
        { class: 'match-head' },
        h('h2', { class: 'match-title' }, h('a', { class: 'stretched-link', href: `/listing?id=${encodeURIComponent(item.id)}` }, listingTitle(item))),
        scoreBadge(c.score),
      ),
      h(
        'p',
        { class: 'meta' },
        h('span', { i18n: 'listing.freePlaces', i18nArgs: { count: item.free_places } }),
        // Not in the match list yet (see README, "Gaps"); shown once the API adds it.
        item.monthly_cost_per_person_rub != null
          ? h('span', { i18n: 'listing.costShort', i18nArgs: { cost: { num: item.monthly_cost_per_person_rub } } })
          : null,
      ),
      explanation(c.dimensions),
      warnings(c.warnings),
    ),
  );
}

function pager(total) {
  const pages = Math.max(1, Math.ceil(total / MATCHES_PAGE_SIZE));
  if (pages <= 1) return null;
  const go = (p) => {
    page = p;
    load({ focus: true });
  };
  return h(
    'nav',
    { class: 'pager', 'aria-label': 'Pages', 'data-i18n-attr': 'aria-label:pager.label' },
    h('button', { type: 'button', class: 'btn btn-secondary', disabled: page <= 1, onclick: () => go(page - 1), i18n: 'pager.prev' }),
    h('span', { i18n: 'pager.status', i18nArgs: { page, pages } }),
    h('button', { type: 'button', class: 'btn btn-secondary', disabled: page >= pages, onclick: () => go(page + 1), i18n: 'pager.next' }),
  );
}

function needsQuestionnaire(textKey, href, buttonKey) {
  panel.replaceChildren(
    h(
      'div',
      { class: 'empty card' },
      h('p', { i18n: textKey }),
      h('p', {}, h('a', { class: 'btn', href, i18n: buttonKey })),
    ),
  );
}

function render(data) {
  const pages = Math.max(1, Math.ceil(data.total / MATCHES_PAGE_SIZE));
  if (data.items.length === 0 && data.total > 0 && page > pages) {
    page = pages;
    load();
    return;
  }
  if (data.total === 0) {
    panel.replaceChildren(
      h(
        'div',
        { class: 'empty card' },
        h('p', { i18n: `matches.empty.${kind}` }),
        h('p', { class: 'muted', i18n: 'matches.emptyHint' }),
        h('p', {}, h('a', { href: '/questionnaire', i18n: 'matches.editAnswers' })),
      ),
    );
    return;
  }
  panel.replaceChildren(
    h('p', { class: 'muted', i18n: 'matches.found', i18nArgs: { count: data.total } }),
    h('ul', { class: 'cards' }, data.items.map(card)),
  );
  const pagerEl = pager(data.total);
  if (pagerEl) panel.append(pagerEl);
}

async function load({ focus = false } = {}) {
  const current = ++requestId;
  updateUrl();
  loading(panel);
  try {
    const data = await api.getMatches(kind, (page - 1) * MATCHES_PAGE_SIZE, MATCHES_PAGE_SIZE);
    if (current !== requestId) return; // A newer request (other tab or page) won.
    render(data);
    if (focus) {
      panel.focus();
      panel.scrollIntoView({ block: 'start' });
    }
  } catch (err) {
    if (current !== requestId) return;
    if (err.code === 'PROFILE_REQUIRED') {
      needsQuestionnaire('matches.needProfile', `/questionnaire?next=${encodeURIComponent('/matches')}`, 'matches.fillIn');
    } else if (err.code === 'BUDGET_REQUIRED') {
      needsQuestionnaire('matches.needBudget', '/questionnaire#budget', 'matches.setBudget');
    } else {
      loadFailed(panel, err, () => load());
    }
  }
}

updateTabs();
load();

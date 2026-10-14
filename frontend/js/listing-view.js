// Pieces shared by the matches list and the listing detail: titles, the score,
// the short explanation and the warnings.

import { h } from './ui.js';

const LABEL_ORDER = ['similar', 'minor_difference', 'noticeable_difference'];

export function listingTitle(item) {
  if (item.kind === 'dorm') {
    return h('span', { i18n: 'listing.dormTitle', i18nArgs: { building: item.building ?? '—', room: item.room_number ?? '—' } });
  }
  return h('span', { i18n: 'listing.apartmentTitle', i18nArgs: { district: item.district ?? '—' } });
}

export function scoreBadge(score) {
  const level = score >= 75 ? 'high' : score >= 50 ? 'mid' : 'low';
  return h(
    'div',
    { class: `score score-${level}` },
    h('span', { class: 'score-value' }, `${score}%`),
    h('span', { class: 'score-label', i18n: 'match.compatibility' }),
  );
}

// Group question keys by label, most important (highest weight) first.
function groupDimensions(dimensions = []) {
  const groups = Object.fromEntries(LABEL_ORDER.map((label) => [label, []]));
  const sorted = [...dimensions].sort((a, b) => b.weight - a.weight);
  for (const d of sorted) (groups[d.label] ??= []).push(d.key);
  return groups;
}

const topic = (key) => ({ t: `topic.${key}` });

// "Similar: sleep, cleaning, guests +2 · Differs: smoking". On cards the
// similar list is shortened; the detail page shows everything.
export function explanation(dimensions, { maxSimilar = 3 } = {}) {
  const groups = groupDimensions(dimensions);
  const list = h('ul', { class: 'explain' });
  for (const label of LABEL_ORDER) {
    const keys = groups[label];
    if (!keys.length) continue;
    const shown = label === 'similar' && maxSimilar ? keys.slice(0, maxSimilar) : keys;
    const more = keys.length - shown.length;
    list.append(
      h(
        'li',
        { class: `explain-${label}` },
        h('span', { class: 'explain-icon', 'aria-hidden': 'true' }, label === 'similar' ? '✓' : label === 'minor_difference' ? '≈' : '≠'),
        h(
          'span',
          {},
          h('span', { i18n: `explain.${label}`, i18nArgs: { topics: shown.map(topic) } }),
          more > 0 ? h('span', { class: 'muted', i18n: 'explain.more', i18nArgs: { count: more } }) : null,
        ),
      ),
    );
  }
  return list;
}

export function warnings(items = []) {
  if (!items.length) return null;
  return h(
    'ul',
    { class: 'warnings' },
    items.map((w) => {
      if (w.code === 'PARTIAL_ANSWERS') {
        return h('li', { i18n: 'warning.partial', i18nArgs: { answered: w.answered, count: w.occupied } });
      }
      if (w.code === 'RESIDENTS_DISAGREE') {
        return h('li', { i18n: 'warning.disagree', i18nArgs: { topic: topic(w.key) } });
      }
      return h('li', { i18n: 'warning.other' });
    }),
  );
}

// Description list of a listing's fields (detail page and "My listing").
export function facts(l) {
  const rows = [];
  const add = (key, value) => {
    if (value !== null && value !== undefined && value !== '') rows.push([key, value]);
  };
  if (l.kind === 'dorm') {
    add('listing.building', l.building);
    add('listing.room', l.room_number);
    add('listing.floor', l.floor);
    add('listing.corner', l.is_corner == null ? null : { t: l.is_corner ? 'common.yes' : 'common.no' });
    add('listing.windows', l.windows_count);
    add('listing.view', l.view ? { t: `view.${l.view}` } : null);
    add('listing.layout', l.layout);
  } else {
    add('listing.district', l.district);
    add('listing.cost', l.monthly_cost_per_person_rub == null ? null
      : { t: 'listing.costValue', args: { cost: { num: l.monthly_cost_per_person_rub } } });
  }
  add('listing.places', {
    t: 'listing.placesValue',
    args: { capacity: l.capacity, occupied: l.occupied_count, count: l.free_places },
  });
  return h(
    'dl',
    { class: 'facts' },
    rows.map(([key, value]) =>
      h(
        'div',
        {},
        h('dt', { i18n: key }),
        typeof value === 'object' ? h('dd', { i18n: value.t, i18nArgs: value.args }) : h('dd', {}, String(value)),
      ),
    ),
  );
}

export function residentsList(residents = []) {
  if (!residents.length) return h('p', { class: 'muted', i18n: 'residents.none' });
  return h(
    'ul',
    { class: 'residents', 'data-private': true },
    residents.map((r) =>
      h(
        'li',
        {},
        h('span', {}, r.display_name),
        h('span', {
          class: r.profile_complete ? 'badge badge-ok' : 'badge',
          i18n: r.profile_complete ? 'residents.answered' : 'residents.notAnswered',
        }),
      ),
    ),
  );
}

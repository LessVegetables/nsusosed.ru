// A room's page, as someone looking for a place sees it: photos, where it is (a dorm
// building exactly, an apartment as an approximate area), who lives there with their bios and
// per-person compatibility, and the button that reveals the hosts' contacts.

import { ApiError, get, post } from '../api.js';
import { breakdown, chips } from '../compat.js';
import { currentLang, t } from '../i18n.js';
import { initPage } from '../layout.js';
import { addArea, addPin, createMap } from '../map.js';
import { el, errorText, setBusy } from '../ui.js';

const root = document.getElementById('room');
const id = new URLSearchParams(location.search).get('id');

const { user } = await initPage({ auth: 'required' });
void user;

let room = null;
let quiz = null;
let meta = null;
let contacts = null;     // filled after "get contact info"
let contactsError = null;
let shownPhoto = 0;
let map = null;

try {
  [room, quiz, meta] = await Promise.all([get(`/rooms/${id}`), get('/questionnaire'), get('/meta')]);
} catch (err) {
  if (!(err instanceof ApiError)) throw err;
  if (err.status === 401) location.replace('/login');
}

const tr = (texts) => texts[currentLang()] ?? texts.ru;
const rub = (n) => `${n.toLocaleString('ru-RU')} ₽`;
const genderLabel = (g) => ({ f: t('feed.gender.f'), m: t('feed.gender.m'), any: t('feed.gender.any') }[g]);
const fact = (label, value) => el('div', {}, el('small', {}, label), el('b', {}, value));

function title() {
  if (room.kind === 'dorm') return t('home.dorm.n', { name: meta.dorms.find((d) => d.id === room.building)?.name ?? room.building });
  return room.room_name ? `${room.room_name} · ${room.district}` : t('join.confirm.apartment', { district: room.district });
}

function gallery() {
  if (!room.photos.length) return null;
  const main = el('img', { class: 'main', src: room.photos[shownPhoto].url, alt: t('home.photos.alt', { n: shownPhoto + 1 }) });
  const thumbs = room.photos.length > 1 && el('div', { class: 'thumbs' }, ...room.photos.map((p, i) => el('button', {
    type: 'button', 'aria-pressed': String(i === shownPhoto), 'aria-label': t('home.photos.alt', { n: i + 1 }),
    onclick: () => { shownPhoto = i; render(); },
  }, el('img', { src: p.url, alt: '', loading: 'lazy' }))));
  return el('div', { class: 'box gallery' }, main, thumbs);
}

function contactPanel() {
  if (room.is_mine) return el('p', { class: 'note' }, `✓ ${t('room.mine')} `, el('a', { href: '/home' }, t('room.mineLink')));
  if (contacts) {
    return el('div', { class: 'contact-box', role: 'status', 'data-private': true }, ...contacts.hosts.map((host) => el('div', {},
      el('p', {}, el('b', {}, host.first_name)),
      ...host.contacts.map((c) => el('p', {}, `${t(`contact.${c.type}`)}: `,
        c.url ? el('a', { href: c.url, target: c.type === 'phone' ? null : '_blank', rel: 'noopener' }, c.value) : c.value)))),
    el('p', { class: 'hint' }, t('room.contactsHint')));
  }
  if (!room.can_get_contacts) {
    return el('p', { class: 'note' }, `⚠ ${t('room.needQuiz')} `, el('a', { href: '/questionnaire' }, t('account.quiz.open')));
  }
  const button = el('button', { class: 'btn accent', type: 'button', onclick: async () => {
    setBusy(button, true);
    try {
      contacts = await post(`/rooms/${room.room_id}/contacts`);
      contactsError = null;
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      contactsError = errorText(err);
    }
    render();
  } }, t('room.getContacts'));
  return el('div', { class: 'stack' }, button, contactsError && el('p', { class: 'note error' }, `✕ ${contactsError}`));
}

function info() {
  const facts = [
    fact(t('room.fact.free'), t('feed.places', { free: room.free_places, total: room.capacity })),
    fact(t('room.fact.for'), genderLabel(room.gender)),
    room.sunlight && fact(t('room.fact.sun'), t(`home.sun.${room.sunlight}`)),
  ].filter(Boolean);
  if (room.kind === 'apartment') {
    facts.push(
      fact(t('room.fact.rent'), rub(room.rent_rub)),
      fact(t('room.fact.utilities'), room.utilities_mode === 'included' ? t('home.costs.included') : `≈ ${rub(room.utilities_rub)}`),
      fact(t('room.fact.internet'), { included: t('home.costs.internetIncluded'), split: t('home.costs.split'), none: t('home.costs.noInternet') }[room.internet_mode]),
      fact(t('room.fact.district'), room.district));
  }
  return el('div', { class: 'box info' },
    el('span', { class: 'emoji' }, room.emoji),
    el('h1', { class: 'title' }, title()),
    room.compatibility
      ? el('div', { class: 'score' }, el('span', { class: 'big-pct' }, `${room.compatibility.percent}%`), el('b', {}, t('room.compatibility')))
      : !room.is_mine && el('p', { class: 'note' }, `⚠ ${room.can_get_contacts ? t('feed.noScore') : t('room.needQuizScore')}`),
    el('div', { class: 'facts' }, ...facts),
    contactPanel());
}

/** How far apart two answers to one question are: 'far', 'near' or 'same'. Every visible question
 *  is a scale (its options run from one end to the other), so the distance is the step count. */
function gap(q, mine, theirs) {
  const steps = Math.abs(mine - theirs);
  const share = steps / Math.max(1, q.options.length - 1);
  return { share, level: steps === 0 ? 'same' : steps >= 2 && share >= 0.4 ? 'far' : 'near' };
}

/** One question where the answers differ: the scale with both marks on it, then both answers. */
function diffRow(person, q, level) {
  const mine = room.my_answers[q.id];
  const theirs = person.answers[q.id];
  const who = (i) => (i === mine ? 'me' : i === theirs ? 'them' : null);
  return el('li', { class: 'cmp-row' },
    el('p', { class: 'cmp-q' }, tr(q.text)),
    el('div', { class: 'cmp-track', 'aria-hidden': 'true' }, ...q.options.map((_, i) => el('i', { 'data-who': who(i) }))),
    el('p', { class: 'cmp-a' }, el('span', { class: 'cmp-who', 'data-who': 'them' }, person.first_name), tr(q.options[theirs])),
    el('p', { class: 'cmp-a' }, el('span', { class: 'cmp-who', 'data-who': 'me' }, t('room.you')), tr(q.options[mine])),
    level === 'near' && el('span', { class: 'sr-only' }, t('room.cmp.near')));
}

/** Visible answers compared with mine. The big differences sit open on the card, worst first;
 *  small ones and identical answers are folded away, the identical ones as one line each. */
function compare(person) {
  const items = quiz.questions
    .filter((q) => !q.hidden && person.answers[q.id] != null && room.my_answers[q.id] != null)
    .map((q) => ({ q, ...gap(q, room.my_answers[q.id], person.answers[q.id]) }))
    .sort((a, b) => b.share - a.share);
  if (!items.length) return null;
  const of = (level) => items.filter((item) => item.level === level);
  const [far, near, same] = [of('far'), of('near'), of('same')];
  const group = (cls, label, list, row) => list.length > 0 && el('div', { class: 'cmp-group' },
    el('p', { class: 'cmp-head' }, el('span', { class: `chip ${cls}` }, label), el('span', { class: 'meta' }, String(list.length))),
    el('ul', { class: 'cmp' }, ...list.map(row)));
  // At most three big differences sit open; any further ones lead the folded part.
  const open = far.slice(0, 3);
  const folded = far.slice(3);
  const rest = folded.length + near.length + same.length;
  return el('div', { class: 'cmp-wrap' },
    open.length
      ? group('mismatch', t('room.cmp.far'), open, ({ q }) => diffRow(person, q, 'far'))
      : el('p', { class: 'note success' }, `✓ ${t('room.cmp.noFar')}`),
    rest > 0 && el('details', { class: 'more' },
      el('summary', {}, t('room.compare', { n: rest })),
      group('mismatch', t('room.cmp.far'), folded, ({ q }) => diffRow(person, q, 'far')),
      group('partial', t('room.cmp.near'), near, ({ q }) => diffRow(person, q, 'near')),
      group('match', t('room.cmp.same'), same, ({ q }) => el('li', { class: 'cmp-row' },
        el('p', { class: 'cmp-q' }, tr(q.text)),
        el('p', { class: 'cmp-a' }, tr(q.options[person.answers[q.id]]))))));
}

function resident(person) {
  return el('li', { class: 'box pad resident-card', 'data-private': true },
    el('div', { class: 'row' },
      person.avatar_url ? el('img', { class: 'avatar', src: person.avatar_url, alt: '' }) : el('span', { class: 'avatar', 'aria-hidden': 'true' }, person.first_name.slice(0, 1)),
      el('div', {},
        el('h3', {}, `${person.first_name} ${person.last_name}`),
        room.kind === 'apartment' && el('p', { class: 'meta' }, person.in_this_room ? t('room.inThisRoom') : t('room.inOtherRoom')),
        person.compatibility && el('p', { class: 'meta' }, t('room.personScore', { n: person.compatibility.percent })))),
    person.bio && el('p', {}, person.bio),
    person.compatibility ? chips(person.compatibility) : !room.is_mine && el('p', { class: 'hint' }, t('room.personNoQuiz')),
    !room.is_mine && compare(person));
}

function render() {
  map?.remove();
  map = null;
  if (!room) {
    root.replaceChildren(el('div', { class: 'box pad solo-panel' },
      el('span', { class: 'tag fill-red' }, '404'),
      el('h1', { class: 'title' }, t('room.missing.title')),
      el('p', {}, t('room.missing.text')),
      el('a', { class: 'btn', href: '/feed' }, t('room.missing.back'))));
    return;
  }
  document.title = `${room.emoji} ${title()} — nsusosed`;
  const hasPlace = room.lat != null && room.lon != null;
  // replaceChildren() would print a `false`/`null` from the `cond && el(...)` items as text.
  root.replaceChildren(...[
    el('p', {}, el('a', { class: 'linkbtn', href: `/feed?kind=${room.kind}` }, t('room.back'))),
    el('div', { class: gallery() ? 'listing' : 'listing single' }, gallery(), info()),
    room.compatibility && el('section', {},
      breakdown(room.compatibility),
      el('p', { class: 'hint' }, el('a', { href: '/compatibility' }, t('quiz.how')))),
    room.description && el('section', { class: 'box pad rblock' }, el('h2', {}, t('home.about.title')), el('p', { class: 'prewrap' }, room.description)),
    hasPlace && el('section', { class: 'box pad rblock' },
      el('h2', {}, t('home.place.title')),
      el('p', { class: 'hint' }, room.radius_m ? t('room.place.area') : t('room.place.dorm')),
      el('div', { class: 'map', id: 'room-map' })),
    el('section', { class: 'rblock' },
      el('h2', { class: 'title' }, t('home.residents.title')),
      el('p', { class: 'hint' }, room.kind === 'apartment' ? t('room.residents.flat') : t('room.residents.dorm')),
      el('ul', { class: 'resident-cards' }, ...room.residents.map(resident))),
    room.other_rooms.length > 0 && el('section', { class: 'box pad rblock' },
      el('h2', {}, t('room.other.title')),
      el('ul', { class: 'other-rooms' }, ...room.other_rooms.map((r) => el('li', {},
        el('a', { href: `/room?id=${r.room_id}` }, `${r.emoji} ${r.room_name || t('home.room.title')}`),
        ` · ${rub(r.rent_rub)} · ${r.free_places ? t('room.other.free', { n: r.free_places }) : t('room.other.full')}`)))),
  ].filter(Boolean));

  const host = document.getElementById('room-map');
  if (host) {
    if (room.radius_m) {
      map = createMap(host, { lat: room.lat, lon: room.lon, zoom: 15 });
      addArea(map, room);
    } else {
      map = createMap(host, { lat: room.lat, lon: room.lon, zoom: 16 });
      addPin(map, room);
    }
  }
}

render();
document.addEventListener('langchange', render);

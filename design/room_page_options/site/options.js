// Room page layout options (scratchpad mockups). Built from the site's own modules and CSS;
// the data comes from the mock API in ../server.py.
//   /layout?opt=B&id=flat-5&gallery=auto&theme=light

import { get } from '/js/api.js';
import { breakdown, chips, TOPICS, topicName, levelName } from '/js/compat.js';
import { currentLang, t } from '/js/i18n.js';
import { initPage } from '/js/layout.js';
import { addArea, addPin, createMap } from '/js/map.js';
import { el } from '/js/ui.js';

const params = new URLSearchParams(location.search);
const opt = params.get('opt') || 'B';
const galleryPick = params.get('gallery') || 'auto';
if (params.get('theme') === 'dark') document.documentElement.dataset.theme = 'dark';
else document.documentElement.dataset.theme = 'light';

await initPage({ auth: 'required' });
const [room, quiz, meta] = await Promise.all([get(`/rooms/${params.get('id') || 'flat-5'}`), get('/questionnaire'), get('/meta')]);
const root = document.getElementById('room');
root.dataset.opt = opt;

const tr = (texts) => texts[currentLang()] ?? texts.ru;
const rub = (n) => `${n.toLocaleString('ru-RU')} ₽`;
const flat = room.kind === 'apartment';
const LEVEL_CLASS = { match: 'match', ok: 'partial', discuss: 'mismatch' };
const genderLabel = { f: t('feed.gender.f'), m: t('feed.gender.m'), any: t('feed.gender.any') }[room.gender];
const places = t('feed.places', { free: room.free_places, total: room.capacity });
const titleText = flat ? `${room.room_name} · ${room.district}` : t('home.dorm.n', { name: meta.dorms.find((d) => d.id === room.building)?.name });
const section = (title, ...children) => el('section', { class: 'box pad rblock' }, el('h2', {}, title), ...children);

/* ---------- pieces ---------- */

const back = () => el('p', {}, el('a', { class: 'linkbtn', href: '#' }, t('room.back')));
const emoji = () => el('span', { class: 'emoji' }, room.emoji);

function factList() {
  const list = [[t('room.fact.free'), places], [t('room.fact.for'), genderLabel], [t('room.fact.sun'), t(`home.sun.${room.sunlight}`)]];
  if (flat) list.push([t('room.fact.rent'), rub(room.rent_rub)], [t('room.fact.utilities'), `≈ ${rub(room.utilities_rub)}`],
    [t('room.fact.internet'), t('home.costs.split')], [t('room.fact.district'), room.district]);
  return list;
}
const facts = (list = factList()) => el('div', { class: 'facts' }, ...list.map(([label, value]) => el('div', {}, el('small', {}, label), el('b', {}, value))));
const factTags = () => el('div', { class: 'row fact-tags' }, ...[flat && `${rub(room.rent_rub)} в месяц`, places, genderLabel, t(`home.sun.${room.sunlight}`), flat && `коммуналка ≈ ${rub(room.utilities_rub)}`]
  .filter(Boolean).map((text) => el('span', { class: 'tag' }, text)));

const score = () => el('div', { class: 'score' }, el('span', { class: 'big-pct' }, `${room.compatibility.percent}%`), el('b', {}, t('room.compatibility')));
const how = () => el('p', { class: 'hint' }, el('a', { href: '#' }, t('quiz.how')));
/** Topics as rows (for a narrow column): name left, level right. */
const topicRows = () => el('ul', { class: 'topic-rows' }, ...TOPICS.map((topic) => {
  const level = room.compatibility.badges[topic];
  return el('li', {}, el('span', {}, topicName(topic)), el('span', { class: `chip ${LEVEL_CLASS[level]}` }, levelName(level)));
}));

/** "Show contacts": pink, full width; a click swaps it for the green contacts box. */
function cta() {
  const host = el('div', { class: 'cta' });
  const button = el('button', { class: 'btn accent', type: 'button', onclick: () => {
    host.replaceChildren(el('div', { class: 'contact-box' },
      el('div', {}, el('p', {}, el('b', {}, 'Маша')), el('p', {}, 'Telegram: ', el('a', { href: '#' }, '@masha_orlova')), el('p', {}, 'VK: ', el('a', { href: '#' }, 'vk.com/masha.orlova'))),
      el('div', {}, el('p', {}, el('b', {}, 'Аня')), el('p', {}, 'Telegram: ', el('a', { href: '#' }, '@anya_kim'))),
      el('p', { class: 'hint' }, t('room.contactsHint'))));
  } }, t('room.getContacts'));
  host.append(button);
  return host;
}
/** Phones: the same button pinned to the bottom of the screen, with the percent beside it. */
const ctaBar = () => el('div', { class: 'cta-bar' }, el('span', { class: 'big-pct' }, `${room.compatibility.percent}%`),
  el('button', { class: 'btn accent', type: 'button' }, t('room.getContacts')));

/* ---------- photos ---------- */

let lightbox;
function openPhoto(i) {
  if (!lightbox) {
    lightbox = el('dialog', { class: 'dialog lightbox' });
    document.body.append(lightbox);
    lightbox.addEventListener('click', (e) => { if (e.target === lightbox) lightbox.close(); });
  }
  const show = (n) => {
    const k = (n + room.photos.length) % room.photos.length;
    lightbox.replaceChildren(
      el('img', { src: room.photos[k].url, alt: '' }),
      el('div', { class: 'row spread' },
        el('button', { class: 'btn secondary', type: 'button', onclick: () => show(k - 1), disabled: room.photos.length < 2 }, '←'),
        el('span', { class: 'meta' }, `${k + 1} / ${room.photos.length}`),
        el('button', { class: 'btn secondary', type: 'button', onclick: () => show(k + 1), disabled: room.photos.length < 2 }, '→'),
        el('button', { class: 'btn dark', type: 'button', onclick: () => lightbox.close() }, '✕')));
  };
  show(i);
  lightbox.showModal();
}
const photoButton = (p, i, attrs = {}) => el('button', { type: 'button', 'aria-label': `Фото ${i + 1}`, onclick: () => openPhoto(i), ...attrs }, el('img', { src: p.url, alt: '', loading: i ? 'lazy' : null }));

/** 1. Main photo + thumbnails (what the site has now; the main photo opens full size). */
function gThumbs() {
  let shown = 0;
  const main = el('img', { class: 'main', src: room.photos[0].url, alt: '' });
  const count = el('span', { class: 'photo-count' }, `1 / ${room.photos.length}`);
  const mainButton = el('button', { class: 'main-btn', type: 'button', onclick: () => openPhoto(shown) }, main, room.photos.length > 1 && count);
  const thumbs = room.photos.length > 1 && el('div', { class: 'thumbs strip-thumbs' }, ...room.photos.map((p, i) => el('button', {
    type: 'button', 'aria-pressed': String(i === 0), onclick: (e) => {
      shown = i; main.src = p.url; count.textContent = `${i + 1} / ${room.photos.length}`;
      thumbs.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === e.currentTarget)));
    } }, el('img', { src: p.url, alt: '', loading: 'lazy' }))));
  return el('div', { class: 'box gallery g-thumbs' }, mainButton, thumbs);
}
/** 2. Mosaic: one big photo and up to four small ones; "+N" on the last. With a single photo the
 *  empty half is given to the map (pass a node), so the block never looks half-built. Phones: a
 *  swipe row of all the photos. */
function gMosaic(filler) {
  const n = room.photos.length;
  const extra = n - 5;
  return el('div', { class: 'mosaic', 'data-n': String(Math.min(n, 5)), 'data-filled': n === 1 && filler ? '' : null },
    ...room.photos.map((p, i) => photoButton(p, i, { 'data-more': i === 4 && extra > 0 ? `+${extra}` : null })),
    n === 1 && filler);
}
/** 3. Film strip: every photo whole, in its own shape (nothing cropped), in one row that scrolls. */
const gStrip = () => el('div', { class: 'strip', 'data-n': String(room.photos.length) }, ...room.photos.map((p, i) => photoButton(p, i)));
/** 4. One photo at a time filling a tile, with arrows and a counter (the bento tile). */
function gSlide() {
  let k = 0;
  const img = el('img', { src: room.photos[0].url, alt: '' });
  const count = el('span', { class: 'photo-count' }, `1 / ${room.photos.length}`);
  const go = (d) => { k = (k + d + room.photos.length) % room.photos.length; img.src = room.photos[k].url; count.textContent = `${k + 1} / ${room.photos.length}`; };
  const many = room.photos.length > 1;
  return el('div', { class: 'slide' },
    el('button', { class: 'slide-photo', type: 'button', onclick: () => openPhoto(k) }, img),
    many && el('button', { class: 'slide-arrow prev', type: 'button', onclick: () => go(-1) }, '←'),
    many && el('button', { class: 'slide-arrow next', type: 'button', onclick: () => go(1) }, '→'),
    many && count);
}
const gallery = (designed, filler) => ({ thumbs: gThumbs, mosaic: () => gMosaic(filler), strip: gStrip, slide: gSlide }[galleryPick === 'auto' ? designed : galleryPick])();

/* ---------- people ---------- */

function gap(q, mine, theirs) {
  const steps = Math.abs(mine - theirs);
  const share = steps / Math.max(1, q.options.length - 1);
  return { share, level: steps === 0 ? 'same' : steps >= 2 && share >= 0.4 ? 'far' : 'near' };
}
function diffRow(person, q) {
  const mine = room.my_answers[q.id];
  const theirs = person.answers[q.id];
  const who = (i) => (i === mine ? 'me' : i === theirs ? 'them' : null);
  return el('li', { class: 'cmp-row' },
    el('p', { class: 'cmp-q' }, tr(q.text)),
    el('div', { class: 'cmp-track' }, ...q.options.map((_, i) => el('i', { 'data-who': who(i) }))),
    el('p', { class: 'cmp-a' }, el('span', { class: 'cmp-who', 'data-who': 'them' }, person.first_name), tr(q.options[theirs])),
    el('p', { class: 'cmp-a' }, el('span', { class: 'cmp-who', 'data-who': 'me' }, t('room.you')), tr(q.options[mine])));
}
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
      ? group('mismatch', t('room.cmp.far'), open, ({ q }) => diffRow(person, q))
      : el('p', { class: 'note success' }, `✓ ${t('room.cmp.noFar')}`),
    rest > 0 && el('details', { class: 'more' },
      el('summary', {}, t('room.compare', { n: rest })),
      group('mismatch', t('room.cmp.far'), folded, ({ q }) => diffRow(person, q)),
      group('partial', t('room.cmp.near'), near, ({ q }) => diffRow(person, q)),
      group('match', t('room.cmp.same'), same, ({ q }) => el('li', { class: 'cmp-row' },
        el('p', { class: 'cmp-q' }, tr(q.text)),
        el('p', { class: 'cmp-a' }, tr(q.options[person.answers[q.id]]))))));
}
function resident(person) {
  return el('li', { class: 'box pad resident-card' },
    el('div', { class: 'row person-head' },
      el('span', { class: 'avatar sm' }, person.first_name.slice(0, 1)),
      el('div', { class: 'person-name' },
        el('h3', {}, `${person.first_name} ${person.last_name}`),
        flat && el('p', { class: 'meta' }, person.in_this_room ? t('room.inThisRoom') : t('room.inOtherRoom'))),
      person.compatibility && el('span', { class: 'pct person-pct' }, `${person.compatibility.percent}%`)),
    person.bio && el('p', {}, person.bio),
    person.compatibility ? chips(person.compatibility) : el('p', { class: 'hint' }, t('room.personNoQuiz')),
    compare(person));
}
const people = (cls = '') => el('ul', { class: `resident-cards ${cls}` }, ...room.residents.map(resident));
const peopleHint = () => el('p', { class: 'hint' }, flat ? t('room.residents.flat') : t('room.residents.dorm'));

/* ---------- other blocks ---------- */

const about = () => section(t('home.about.title'), el('p', { class: 'prewrap' }, room.description));
const mapNode = (cls = '') => el('div', { class: `map ${cls}`, 'data-map': '' });
const where = () => section(t('home.place.title'), el('p', { class: 'hint' }, room.radius_m ? t('room.place.area') : t('room.place.dorm')), mapNode());
const others = () => room.other_rooms.length > 0 && section(t('room.other.title'),
  el('ul', { class: 'other-list' }, ...room.other_rooms.map((r) => el('li', {},
    el('a', { class: 'other-room', href: '#' }, el('span', { class: 'emoji' }, r.emoji), el('b', {}, r.room_name),
      el('span', { class: 'meta' }, `${rub(r.rent_rub)} · ${r.free_places ? t('room.other.free', { n: r.free_places }) : t('room.other.full')}`))))));
const summaryBox = (...extra) => el('div', { class: 'box info' }, emoji(), el('h1', { class: 'title' }, titleText), score(), ...extra);

/* ---------- layouts ---------- */

const LAYOUTS = {
  // B. Classic listing: content on the left, a summary card that follows you on the right.
  B: () => [back(), el('div', { class: 'lb' },
    el('div', { class: 'lb-photos' }, gallery('thumbs')),
    el('aside', { class: 'lb-side' }, summaryBox(topicRows(), facts(), cta(), how())),
    el('div', { class: 'lb-rest' }, about(),
      el('section', { class: 'rblock' }, el('h2', { class: 'title' }, t('home.residents.title')), peopleHint(), people('one-col')),
      where(), others())), ctaBar()],

  // C. Photos first: a mosaic across the page, then a headline row with the price, then two columns.
  C: () => {
    const single = room.photos.length === 1 && (galleryPick === 'auto' || galleryPick === 'mosaic');
    return [back(), gallery('mosaic', mapNode('fill')),
      el('div', { class: 'lc-head' },
        el('div', { class: 'lc-title' }, emoji(), el('h1', { class: 'title' }, titleText), factTags()),
        flat && el('div', { class: 'lc-price' }, el('span', { class: 'big-pct' }, rub(room.rent_rub)), el('span', { class: 'meta' }, 'за место в месяц'))),
      el('div', { class: 'lb' },
        el('aside', { class: 'lb-side' }, el('div', { class: 'box info' }, el('span', { class: 'tag' }, 'Вы и жители'), score(), topicRows(), cta(), how())),
        el('div', { class: 'lb-rest' }, about(),
          el('section', { class: 'rblock' }, el('h2', { class: 'title' }, t('home.residents.title')), peopleHint(), people('one-col')),
          !single && where(), others())), ctaBar()];
  },

  // D. People first: the question the site answers ("will we get along?") leads; photos sit beside.
  D: () => [back(),
    el('div', { class: 'box pad ld-head' },
      el('div', { class: 'ld-title' }, emoji(), el('h1', { class: 'title' }, titleText), factTags()),
      cta()),
    el('div', { class: 'ld' },
      el('div', { class: 'ld-people' },
        el('section', { class: 'box pad rblock fill-yellow ld-score' },
          el('div', { class: 'score' }, el('span', { class: 'big-pct' }, `${room.compatibility.percent}%`), el('b', {}, 'совместимость со всеми, кто здесь живёт')),
          breakdown(room.compatibility), how()),
        people('one-col wide')),
      el('div', { class: 'ld-place' }, gallery('thumbs'), about(), where(), others())), ctaBar()],

  // E. Bento: every fact is its own sticker; the page reads at a glance, like the landing.
  E: () => [back(), el('div', { class: 'bento' },
    el('div', { class: 'box tile t-photo' }, gallery('slide')),
    el('div', { class: 'box pad tile t-title' }, emoji(), el('h1', { class: 'title' }, titleText), el('p', { class: 'meta' }, `${genderLabel} · ${t(`home.sun.${room.sunlight}`)}`)),
    el('div', { class: 'box pad tile t-num fill-yellow' }, el('span', { class: 'big-pct' }, `${room.compatibility.percent}%`), el('span', { class: 'meta' }, t('room.compatibility'))),
    flat
      ? el('div', { class: 'box pad tile t-num fill-pink' }, el('span', { class: 'big-pct small' }, rub(room.rent_rub)), el('span', { class: 'meta' }, `в месяц + ≈ ${rub(room.utilities_rub)} коммуналка`))
      : el('div', { class: 'box pad tile t-num fill-pink' }, el('span', { class: 'big-pct' }, `${room.free_places}/${room.capacity}`), el('span', { class: 'meta' }, 'мест свободно')),
    el('div', { class: 'box pad tile t-cta' }, el('p', {}, el('b', {}, places), flat ? ` · ${t('home.costs.split').toLowerCase()} интернет` : ''), cta()),
    el('div', { class: 'tile t-wide' }, breakdown(room.compatibility)),
    el('div', { class: 'tile t-half' }, about()),
    el('div', { class: 'tile t-half' }, where()),
    el('div', { class: 'tile t-wide rblock' }, el('h2', { class: 'title' }, t('home.residents.title')), peopleHint(), people()),
    room.other_rooms.length > 0 && el('div', { class: 'tile t-wide' }, others()))],

  // F. Tabs: the top of the page is the whole summary; the long parts are one tap away, not a scroll.
  F: () => {
    const panels = {
      people: () => el('div', { class: 'rblock' }, peopleHint(), people()),
      about: () => el('div', { class: 'lf-about' }, about(), others()),
      where: () => where(),
    };
    const panel = el('div', { class: 'lf-panel' });
    const tabs = el('div', { class: 'tabs lf-tabs', role: 'tablist' }, ...[['people', `${t('home.residents.title')} · ${room.residents.length}`], ['about', t('home.about.title')], ['where', t('home.place.title')]]
      .map(([key, label], i) => el('button', { role: 'tab', type: 'button', 'aria-selected': String(i === 0), onclick: (e) => {
        tabs.querySelectorAll('[role=tab]').forEach((b) => b.setAttribute('aria-selected', String(b === e.currentTarget)));
        panel.replaceChildren(...[panels[key]()].flat().filter(Boolean));
        mountMaps();
      } }, label)));
    panel.append(panels.people());
    return [back(), el('div', { class: 'listing lf-top' }, gallery('thumbs'), summaryBox(topicRows(), facts(), cta())), tabs, panel, ctaBar()];
  },
};

root.replaceChildren(...LAYOUTS[opt]().flat().filter(Boolean));
mountMaps();

function mountMaps() {
  for (const host of document.querySelectorAll('[data-map]:not(.leaflet-container)')) {
    const map = createMap(host, { lat: room.lat, lon: room.lon, zoom: room.radius_m ? 15 : 16 });
    if (room.radius_m) addArea(map, room); else addPin(map, room);
  }
}

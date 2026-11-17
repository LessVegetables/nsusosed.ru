// "My home": list a dorm room or an apartment, then edit it.
//
// Laid out as tiles like the room page (js/pages/room.js), so the host edits what visitors
// see: the photos on the left with the title, the status and the places beside them, then
// the places taken, the location, the rooms, the description, the residents and the invites.
//
// The page is rebuilt from `state` on every structural change (kind picked, room added,
// language switched); typing only writes into `state` and refreshes the summary tiles.
//
// Photos go up as soon as they are picked, even for a place that isn't listed yet: those wait
// on the server as "staged" photos (/homes/new/photos) and become the home's when it is created.
// A new place is sent once, with the "List it" button. After that there is no save button:
// every change saves itself (see "Autosave") and answers with a "Saved" pop-up.
//
// Every request that changes the home goes through serial(): the answer to each one is the
// whole home, so two in flight at once (an autosave and a photo upload) could otherwise
// overwrite each other's result on the page.
//
// Places: a room has a capacity (how many people live in it in all); how many of those places
// are taken is set in the "Places" tile for the whole home. The server keeps free places per
// room (the feed lists rooms one by one): free = capacity − taken.
//
// Privacy rules this page is responsible for:
//   - a dorm room's number is sent once and never shown again (the server doesn't return it);
//   - an apartment's address is used only to find a point on the map; the point is replaced
//     by an obfuscated circle here, in the browser, and only the circle is sent.

import { ApiError, del, get, post, put } from '../api.js';
import { autosaver } from '../autosave.js';
import { hasPrimary, mountContacts } from '../contacts.js';
import { reportBug } from '../errors.js';
import { currentLang, t } from '../i18n.js';
import { initPage } from '../layout.js';
import { AKADEMGORODOK, addArea, addPin, createMap, obfuscate } from '../map.js';
import { preparePhoto } from '../photo.js';
import { el, errorText, saved, setBusy, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);
const MAX_ROOMS = 6;
const MAX_PHOTOS = 10;

let { user } = await initPage({ auth: 'required' });
const [meta, mine] = await Promise.all([get('/meta'), get('/homes/mine')]);

let home = mine.home;   // as the server knows it; null until created
let errors = {};        // { "rooms.0.emoji": "EMOJI_TAKEN", … } from the last save
let takenRoomId = null; // set when the dorm room turned out to be listed already

// Photos uploaded for a place that isn't listed yet: [{ id, url }], in the order they'll go.
let staged = [];
if (!home) {
  try { staged = (await get('/homes/new/photos')).map(({ id, url }) => ({ id, url })); } catch (err) { reportBug(err, { where: 'staged' }); }
}

const canEdit = () => !home || home.permissions.can_edit;
const canPhotos = () => !home || home.permissions.can_photos;

/** Run the requests that change the home one at a time, in the order asked. */
let chain = Promise.resolve();
function serial(fn) {
  const run = chain.catch(() => {}).then(fn);
  chain = run;
  return run;
}

function apiFailed(err) {
  if (!(err instanceof ApiError)) throw err;
  if (err.status === 401) { location.replace('/login'); return; }
  toast(t('error.title'), errorText(err), { error: true });
}

// ── State ───────────────────────────────────────────────

const blankRoom = (emoji = '') => ({ id: null, name: '', gender: '', capacity: 2, free_places: 1, rent_rub: '', emoji,
  area_m2: '', description: '', sunlight: '', photo_ids: [], residents: 0 });

function stateFrom(h) {
  if (!h) {
    return { kind: null, description: '', building: '', room_number: '', room_letter: null, district: '', area: null,
      utilities_mode: '', utilities_rub: '', internet_mode: '', rooms: [blankRoom()] };
  }
  return {
    kind: h.kind, description: h.description, building: h.building ?? '', room_number: '', room_letter: null,
    district: h.district ?? '', area: h.kind === 'apartment' ? { lat: h.lat, lon: h.lon, radius_m: h.radius_m } : null,
    utilities_mode: h.utilities_mode ?? '', utilities_rub: h.utilities_rub ?? '', internet_mode: h.internet_mode ?? '',
    rooms: h.rooms.map((r) => ({ ...r, rent_rub: r.rent_rub ?? '', area_m2: r.area_m2 ?? '', sunlight: r.sunlight ?? '', photo_ids: [...r.photo_ids] })),
  };
}

let state = stateFrom(home);
// The address flow: 'search' → 'pin' (drag to the building) → 'area' (the circle that gets saved).
const place = { step: state.area ? 'area' : 'search', query: '', results: null, point: null };

async function rollEmoji(count = 1) {
  try {
    return (await post('/emoji/roll', { count })).emojis;
  } catch (err) {
    reportBug(err, { where: 'rollEmoji' });
    return [];
  }
}

const roomTitle = (room, index) => (state.kind === 'apartment' ? room.name.trim() || t('home.room.titleN', { n: index + 1 }) : t('home.room.title'));

// ── Small builders ──────────────────────────────────────

const reason = (code) => {
  const key = `error.field.${code}`;
  const text = t(key);
  return text === key ? t('error.field.invalid') : text;
};

/** The red note for a field path, if the last save complained about it. */
const problem = (path) => errors[path] && el('p', { class: 'note error', role: 'alert', 'data-error': path }, `✕ ${reason(errors[path])}`);

function field(label, input, { hint, path } = {}) {
  if (path && errors[path]) input.setAttribute('aria-invalid', 'true');
  return el('div', {},
    el('label', { class: 'field' }, el('span', {}, label), input, hint && el('small', {}, hint)),
    path && problem(path));
}

/** A text field bound to obj[key]. `digits`: numbers only. `save: false`: not part of the home. */
function textInput(obj, key, { digits = false, save = true, ...attrs } = {}) {
  const input = el('input', { ...attrs, disabled: !canEdit() });
  input.value = obj[key] ?? '';
  input.addEventListener('input', () => {
    if (digits) {
      const clean = input.value.replace(/\D/g, '');
      if (clean !== input.value) input.value = clean;
    }
    obj[key] = input.value;
    if (save) changed();
  });
  if (save) input.addEventListener('change', () => changed(true));
  return input;
}

function textArea(obj, key, attrs = {}) {
  const area = el('textarea', { rows: 4, maxlength: 1000, ...attrs, disabled: !canEdit() });
  area.value = obj[key];
  area.addEventListener('input', () => { obj[key] = area.value; changed(); });
  area.addEventListener('change', () => changed(true));
  return area;
}

/** A <select> of numbers. `onchange(value)` writes the state itself. */
function numberSelect(value, from, to, onchange, attrs = {}) {
  const node = el('select', { ...attrs, disabled: !canEdit() },
    ...Array.from({ length: to - from + 1 }, (_, i) => el('option', { value: String(from + i) }, String(from + i))));
  node.value = String(value);
  node.addEventListener('change', () => { onchange(Number(node.value)); changed(true); });
  return node;
}

/** Single-choice buttons. Changing the answer re-renders only when `rerender` is set. */
function choice(legend, obj, key, options, { path, hint, rerender = false, cls = '' } = {}) {
  const buttons = options.map(([value, label]) => el('button', {
    type: 'button', 'aria-pressed': String(obj[key] === value), disabled: !canEdit(),
    onclick: () => {
      obj[key] = value;
      if (rerender) render();
      else buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(options[i][0] === value)));
      changed(true);
    },
  }, label));
  return el('fieldset', {}, el('legend', {}, legend), el('div', { class: `opts ${cls}`.trim() }, ...buttons),
    hint && el('p', { class: 'hint' }, hint), path && problem(path));
}

/** Replace a tile in place (the rest of the page, and the field being typed in, stay). */
function refresh(id, build) {
  const node = $(id);
  if (node) node.replaceWith(build());
}

// ── Kind picker (a new place, before anything else) ────

function kindPicker() {
  let picking = false;
  return el('div', { class: 'box pad solo-panel hkind' },
    el('h1', { class: 'title' }, t('home.title.new')),
    el('p', { class: 'lead' }, t('home.lead.new')),
    el('h2', {}, t('home.kind.title')),
    el('div', { class: 'opts' },
      ...[['dorm', t('home.kind.dorm')], ['apartment', t('home.kind.apartment')]].map(([kind, label]) => el('button', {
        type: 'button', onclick: async () => {
          if (picking) return;
          picking = true;
          const [emoji] = await rollEmoji();
          state.kind = kind;
          state.rooms = [blankRoom(emoji ?? '')];
          render();
        },
      }, label))));
}

// ── Summary tiles (beside the photos, as on the room page) ──

function titleText() {
  if (state.kind === 'dorm') {
    const dorm = meta.dorms.find((d) => d.id === state.building);
    return dorm ? t('home.dorm.n', { name: dorm.name }) : t('home.kind.dorm');
  }
  const district = state.district.trim();
  return district ? t('join.confirm.apartment', { district }) : t('home.kind.apartment');
}

function titleTile() {
  const emoji = state.rooms.map((r) => r.emoji.trim()).filter(Boolean);
  return el('div', { class: 'box pad tile t-title', id: 'tile-title' },
    emoji.length > 0 && el('div', { class: 'emoji-row' }, ...emoji.map((e) => el('span', { class: 'emoji' }, e))),
    el('h1', { class: 'title' }, titleText()),
    el('p', { class: 'meta' }, home ? t('home.title.edit') : t('home.title.new')));
}

function statusTile() {
  const [fill, word] = !home ? ['fill-yellow', t('home.tile.draft')]
    : home.visible ? ['fill-green', t('home.tile.visible')] : ['fill-red', t('home.tile.hidden')];
  return el('div', { class: `box pad tile t-num ${fill}`, id: 'tile-status' },
    el('span', { class: 'big-pct small' }, word), el('span', { class: 'meta' }, t('home.tile.status')));
}

function placesTile() {
  const free = state.rooms.reduce((sum, r) => sum + (Number(r.free_places) || 0), 0);
  const total = state.rooms.reduce((sum, r) => sum + (Number(r.capacity) || 0), 0);
  return el('div', { class: 'box pad tile t-num fill-pink', id: 'tile-places' },
    el('span', { class: 'big-pct' }, `${free}/${total}`), el('span', { class: 'meta' }, t('room.tile.free')));
}

/** What still keeps the listing hidden, with a link to fix each. Listed homes only. */
function statusNotes() {
  const notes = [];
  // Autosave sends nothing while a field is missing or wrong; the field may be far below.
  if (Object.keys(errors).length || takenRoomId) {
    notes.push(el('p', { class: 'note error', role: 'alert' }, `✕ ${t('home.status.unsaved')} `,
      el('a', { href: '#home-form', onclick: (e) => {
        e.preventDefault();
        const target = document.querySelector('#home-form [data-error], #home-form .note.error[role="alert"]:not(#tile-cta *)');
        target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      } }, t('home.status.showUnsaved'))));
  }
  if (home.visible) notes.push(el('p', { class: 'note success' }, `✓ ${t('home.status.visible')}`));
  if (home.needs_contact) {
    notes.push(el('p', { class: 'note error' }, `✕ ${t('home.status.needsContact')} `,
      el('a', { href: '/account' }, t('home.status.addContact'))));
  }
  if (home.needs_photo) {
    notes.push(el('p', { class: 'note error' }, `✕ ${t('home.status.needsPhoto')} `,
      el('a', { href: '#tile-photos' }, t('home.status.addPhoto'))));
  }
  if (home.needs_free_place) notes.push(el('p', { class: 'note' }, `⚠ ${t('home.status.needsFreePlace')}`));
  if (!canEdit()) notes.push(el('p', { class: 'note' }, `⚠ ${t('home.status.readOnly')}`));
  return notes;
}

function ctaTile() {
  return el('div', { class: 'box pad tile t-cta', id: 'tile-cta' },
    el('div', { class: 'stack' }, ...statusNotes()),
    el('a', { class: 'btn secondary', href: `/room?id=${home.rooms[0].id}` }, t('home.preview')));
}

function refreshSummary() {
  refresh('tile-title', titleTile);
  refresh('tile-status', statusTile);
  refresh('tile-places', placesTile);
  if (home) refresh('tile-cta', ctaTile);
}

// ── Photos ──────────────────────────────────────────────

let uploading = 0;      // photos on their way to the server
let photoBusy = false;  // a delete or a reorder is being sent
let shown = 0;          // the photo shown large

const photoList = () => (home ? home.photos.map((p) => ({ id: p.id, url: p.url })) : staged);
const photoIds = () => new Set(photoList().map((p) => p.id));

/** Rooms keep only photos that still exist (after a delete). */
function dropMissingPhotos() {
  const ids = photoIds();
  state.rooms.forEach((room) => { room.photo_ids = room.photo_ids.filter((id) => ids.has(id)); });
}

function photoError(err) {
  if (err instanceof ApiError || err?.code) return errorText(err);
  reportBug(err, { where: 'photo' });
  return t('error.generic');
}

/** Files picked or dropped: shrunk here, then sent one by one. `room`: also show them in that room. */
async function addPhotos(files, room = null) {
  const images = files.filter((f) => !f.type || f.type.startsWith('image/'));
  if (!images.length) return;
  const space = MAX_PHOTOS - photoList().length - uploading;
  if (images.length > space) toast(t('error.title'), t('error.TOO_MANY_PHOTOS'), { error: true });
  const take = images.slice(0, Math.max(0, space));
  if (!take.length) return;

  uploading += take.length;
  renderPhotos();
  const failed = [];
  let added = 0;
  for (const file of take) {
    try {
      const blob = await preparePhoto(file);
      const body = new FormData();
      body.append('file', blob, 'photo.jpg');
      let id;
      await serial(async () => {
        if (home) {
          const before = photoIds();
          home = await post(`/homes/${home.id}/photos`, body);
          id = home.photos.find((p) => !before.has(p.id))?.id;
        } else {
          const photo = await post('/homes/new/photos', body);
          staged.push({ id: photo.id, url: photo.url });
          id = photo.id;
        }
      });
      if (room && id) room.photo_ids.push(id);
      added += 1;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) { location.replace('/login'); return; }
      failed.push(photoError(err));
    }
    uploading -= 1;
    if (photoList().length) delete errors.photos;
    renderPhotos();
    if (room) renderRoomPhotos();
    refreshSummary();
  }
  if (room && added) changed(true);
  if (failed.length) toast(t('home.photos.failed', { n: failed.length }), failed[0], { error: true });
  else if (home) saved();
}

async function photoAction(action) {
  if (photoBusy) return;
  photoBusy = true;
  renderPhotos();
  try {
    await serial(action);
    if (home) saved();
  } catch (err) { apiFailed(err); }
  photoBusy = false;
  dropMissingPhotos();
  renderPhotos();
  renderRoomPhotos();
  refreshSummary();
}

function makeCover(i) {
  const list = photoList();
  shown = 0;
  if (!home) { staged.unshift(...staged.splice(i, 1)); renderPhotos(); return; }
  photoAction(async () => {
    home = await put(`/homes/${home.id}/photos/order`, { photo_ids: [list[i].id, ...list.filter((_, j) => j !== i).map((p) => p.id)] });
  });
}

function removePhoto(i) {
  const { id } = photoList()[i];
  if (shown >= i && shown > 0) shown -= 1;
  photoAction(async () => {
    if (home) home = await del(`/homes/${home.id}/photos/${id}`);
    else { await del(`/homes/new/photos/${id}`); staged = staged.filter((p) => p.id !== id); }
  });
}

/** The "add photos" control: a label around a hidden file input. `big` fills the empty tile. */
function picker({ big = false, room = null } = {}) {
  const input = el('input', { class: 'sr-only', type: 'file', accept: 'image/*', multiple: true });
  input.addEventListener('change', () => addPhotos([...input.files], room));
  return el('label', { class: big ? 'upload upload-big' : 'upload', title: big ? null : t('home.photos.add') }, input,
    big ? el('span', {}, el('b', {}, `+ ${t('home.photos.add')}`), el('small', {}, t('home.photos.drop')))
      : el('span', {}, el('span', { 'aria-hidden': 'true' }, '+'), el('span', { class: 'sr-only' }, t('home.photos.add'))));
}

function photosTile() {
  const list = photoList();
  const can = canPhotos();
  shown = Math.min(shown, Math.max(0, list.length - 1));
  const space = can && list.length + uploading < MAX_PHOTOS;
  const status = uploading > 0 && el('p', { class: 'note', role: 'status' }, `⏳ ${t('home.photos.uploading', { n: uploading })}`);
  const tile = el('section', { class: 'box gallery tile t-photo hphotos', id: 'tile-photos', 'aria-busy': String(uploading > 0 || photoBusy) },
    el('div', { class: 'row spread' },
      el('h2', {}, t('home.photos.title')),
      el('span', { class: 'meta' }, `${list.length} / ${MAX_PHOTOS}`)));

  if (!list.length) {
    tile.append(...[
      space ? picker({ big: true }) : el('div', { class: 'photo-empty' }, t('home.photos.none')),
      status,
      el('p', { class: 'hint' }, t('home.photos.hint')),
      problem('photos'),
    ].filter(Boolean));
  } else {
    const current = list[shown];
    const thumbs = el('div', { class: 'thumbs' }, ...list.map((p, i) => el('button', {
      type: 'button', 'aria-pressed': String(i === shown), 'aria-label': t('home.photos.alt', { n: i + 1 }),
      onclick: () => { shown = i; renderPhotos(); },
    }, el('img', { src: p.url, alt: '', loading: 'lazy' }))), space && picker());
    tile.append(...[
      el('div', { class: 'main-wrap' },
        el('img', { class: 'main', src: current.url, alt: t('home.photos.alt', { n: shown + 1 }) }),
        shown === 0 && el('span', { class: 'photo-count' }, t('home.photos.cover'))),
      // Always both buttons, so the tile keeps its height whichever photo is shown.
      can && el('div', { class: 'row photo-actions' },
        el('button', { class: 'btn secondary', type: 'button', disabled: photoBusy || shown === 0, onclick: () => makeCover(shown) },
          `★ ${shown === 0 ? t('home.photos.cover') : t('home.photos.first')}`),
        el('button', { class: 'btn secondary', type: 'button', disabled: photoBusy, onclick: () => removePhoto(shown) }, `✕ ${t('home.photos.delete')}`)),
      thumbs,
      status,
      el('p', { class: 'hint' }, t('home.photos.hint')),
      problem('photos'),
    ].filter(Boolean));
  }

  if (space) {
    tile.addEventListener('dragover', (e) => { e.preventDefault(); tile.dataset.drop = ''; });
    tile.addEventListener('dragleave', () => delete tile.dataset.drop);
    tile.addEventListener('drop', (e) => { e.preventDefault(); delete tile.dataset.drop; addPhotos([...e.dataTransfer.files]); });
  }
  return tile;
}

const renderPhotos = () => refresh('tile-photos', photosTile);

/** A room's photos: all of the home's as thumbnails, the ones in this room pressed. [+] adds
 *  new ones straight into the room. */
function roomPhotos(room, index) {
  const chosen = new Set(room.photo_ids);
  const can = canEdit();
  return el('div', { class: 'field', id: `room-photos-${index}` },
    el('span', {}, t('home.room.photos')),
    el('div', { class: 'thumbs room-thumbs' },
      ...photoList().map((p, i) => el('button', {
        type: 'button', 'aria-pressed': String(chosen.has(p.id)), disabled: !can,
        'aria-label': t('home.photos.alt', { n: i + 1 }),
        onclick: () => {
          room.photo_ids = chosen.has(p.id) ? room.photo_ids.filter((id) => id !== p.id) : [...room.photo_ids, p.id];
          renderRoomPhotos();
          changed(true);
        },
      }, el('img', { src: p.url, alt: '', loading: 'lazy' }))),
      can && canPhotos() && photoList().length + uploading < MAX_PHOTOS && picker({ room })),
    el('small', {}, t('home.room.photosHint')),
    problem(`rooms.${index}.photo_ids`));
}

function renderRoomPhotos() {
  if (state.kind !== 'apartment') return;
  state.rooms.forEach((room, i) => refresh(`room-photos-${i}`, () => roomPhotos(room, i)));
}

// ── Places taken ────────────────────────────────────────

const taken = (room) => room.capacity - room.free_places;

function takenTile() {
  const total = state.rooms.reduce((sum, r) => sum + r.capacity, 0);
  const one = state.rooms.length === 1;
  const rows = state.rooms.map((room, i) => field(
    one ? t('home.places.taken') : t('home.places.takenIn', { room: `${room.emoji} ${roomTitle(room, i)}`.trim() }),
    numberSelect(taken(room), 0, room.capacity, (n) => { room.free_places = room.capacity - n; }, { id: `taken-${i}` }),
    { path: `rooms.${i}.free_places` }));
  return el('section', { class: 'box pad tile t-wide hblock', id: 'tile-taken' },
    el('div', { class: 'row spread' },
      el('h2', {}, t('home.places.title')),
      el('span', { class: 'meta' }, t('home.places.total', { n: total }))),
    el('p', { class: 'hint' }, t('home.places.hint')),
    el('div', { class: 'taken-fields' }, ...rows));
}

// ── Where it is ─────────────────────────────────────────

// A dorm room is a number from 100 to 999 plus the block letter: Б, М or none, read "100Б".
// The letter button right of the number starts at "?" (not chosen yet); each click moves it
// on to the next letter. The letters are Cyrillic in every language: that's what's on the doors.
const ROOM_LETTERS = ['b', 'm', ''];
const LETTER_TEXT = { b: 'Б', m: 'М', '': '' };
const ROOM_NUMBER = /^[1-9][0-9]{2}$/;

/** "100b", "100m", "100", or null while the number or the letter is missing. */
const roomLabel = () => (ROOM_NUMBER.test(state.room_number) && state.room_letter != null ? state.room_number + state.room_letter : null);
const roomTouched = () => state.room_number !== '' || state.room_letter != null;

function roomNumberField() {
  const letterName = () => (state.room_letter == null ? t('home.dorm.letterUnset')
    : state.room_letter === '' ? t('home.dorm.letterNone') : LETTER_TEXT[state.room_letter]);
  const letter = el('button', { type: 'button', class: 'room-letter', disabled: !canEdit() });
  const showLetter = () => {
    letter.textContent = state.room_letter == null ? '?' : LETTER_TEXT[state.room_letter];
    letter.setAttribute('aria-label', t('home.dorm.letter', { letter: letterName() }));
    letter.title = letter.getAttribute('aria-label');
  };
  letter.addEventListener('click', () => {
    state.room_letter = ROOM_LETTERS[(ROOM_LETTERS.indexOf(state.room_letter) + 1) % ROOM_LETTERS.length];
    showLetter();
    changed(true);
  });
  showLetter();

  const number = el('input', {
    id: 'room-number', maxlength: 3, inputmode: 'numeric', pattern: '[0-9]*', autocomplete: 'off',
    placeholder: home ? t('home.dorm.roomSaved') : '100', disabled: !canEdit(),
  });
  number.value = state.room_number;
  number.addEventListener('input', () => {
    const digits = number.value.replace(/\D/g, '').slice(0, 3);
    if (digits !== number.value) number.value = digits;
    state.room_number = digits;
    changed();
  });
  number.addEventListener('change', () => changed(true));
  if (errors.room_label) number.setAttribute('aria-invalid', 'true');

  // Not a <label> around everything: a click on the label text would press the letter button.
  return el('div', {},
    el('div', { class: 'field' },
      el('label', { for: 'room-number' }, t('home.dorm.room')),
      el('div', { class: 'room-field' }, number, letter),
      el('small', {}, home ? t('home.dorm.roomHintEdit') : t('home.dorm.roomHint'))),
    problem('room_label'));
}

function dormTile() {
  const buildings = meta.dorms.map((d) => [d.id, d.address ? `${t('home.dorm.n', { name: d.name })} · ${d.address}` : t('home.dorm.n', { name: d.name })]);
  const building = el('select', { disabled: !canEdit() }, ...[['', t('home.choose')], ...buildings].map(([value, label]) => el('option', { value }, label)));
  building.value = state.building;
  building.addEventListener('change', () => { state.building = building.value; rerender(); changed(true); });
  const takenNote = takenRoomId && el('p', { class: 'note error', role: 'alert' },
    `✕ ${t('home.dorm.taken')} `, el('a', { href: `/room?id=${takenRoomId}` }, t('home.dorm.takenLink')));
  return el('section', { class: 'box pad tile t-half hblock' },
    el('h2', {}, t('home.place.title')),
    field(t('home.dorm.building'), building, { path: 'building' }),
    state.building && el('div', { class: 'map', id: 'place-map' }),
    roomNumberField(),
    takenNote);
}

let mapHandle = null; // the Leaflet map currently on the page

function apartmentTile() {
  const host = el('div', { class: 'map', id: 'place-map' });
  const body = [];
  const edit = canEdit();

  if (place.step === 'search' && edit) {
    const input = textInput(place, 'query', { type: 'search', placeholder: t('home.place.placeholder'), autocomplete: 'off', enterkeyhint: 'search', save: false });
    const go = el('button', { class: 'btn secondary', type: 'button', onclick: () => search(go) }, t('home.place.find'));
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); search(go); } });
    body.push(
      el('p', { class: 'hint' }, t('home.place.why')),
      field(t('home.place.address'), input),
      el('div', { class: 'row place-actions' }, go,
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { place.point = { ...AKADEMGORODOK }; place.step = 'pin'; render(); } }, t('home.place.manual'))),
      place.results && (place.results.length
        ? el('div', { class: 'opts results' }, ...place.results.map((r) => el('button', {
          type: 'button', onclick: () => { place.point = { lat: r.lat, lon: r.lon }; if (r.district && !state.district) state.district = r.district; place.step = 'pin'; render(); },
        }, r.label)))
        : el('p', { class: 'note' }, `⚠ ${t('home.place.none')}`)));
  } else if (place.step === 'pin' && edit) {
    body.push(
      el('p', { class: 'hint' }, t('home.place.pinHint')),
      host,
      el('div', { class: 'row place-actions' },
        el('button', { class: 'btn', type: 'button', onclick: () => { state.area = obfuscate(place.point); place.step = 'area'; render(); changed(true); } }, t('home.place.hide')),
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { place.step = state.area ? 'area' : 'search'; render(); } }, t('home.place.back'))));
  } else if (state.area) {
    body.push(
      el('p', { class: 'note success' }, `✓ ${t('home.place.areaHint')}`),
      host,
      edit && el('div', { class: 'row place-actions' },
        place.point && el('button', { class: 'btn secondary', type: 'button', onclick: () => { state.area = obfuscate(place.point); render(); changed(true); } }, t('home.place.reroll')),
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { place.step = 'search'; place.results = null; render(); } }, t('home.place.again'))));
  }

  // data-private: the address search results and the exact pin are the real address.
  return el('section', { class: 'box pad tile t-half hblock', 'data-private': true },
    el('h2', {}, t('home.place.title')),
    ...body.filter(Boolean),
    problem('location'),
    field(t('home.place.district'), textInput(state, 'district', { maxlength: 60, placeholder: t('home.place.districtPlaceholder') }),
      { path: 'district', hint: t('home.place.districtHint') }));
}

/** Leaflet needs its element in the document, so maps are attached after render(). */
function mountMap() {
  mapHandle?.remove();
  mapHandle = null;
  const host = $('place-map');
  if (!host) return;
  if (state.kind === 'dorm') {
    const dorm = meta.dorms.find((d) => d.id === state.building);
    if (!dorm) return;
    mapHandle = createMap(host, { lat: dorm.lat, lon: dorm.lon, zoom: 16 });
    addPin(mapHandle, dorm);
  } else if (place.step === 'pin') {
    mapHandle = createMap(host, { ...place.point, zoom: 17 });
    addPin(mapHandle, place.point, (p) => { place.point = p; });
  } else if (state.area) {
    mapHandle = createMap(host, { lat: state.area.lat, lon: state.area.lon, zoom: 15 });
    addArea(mapHandle, state.area);
  }
}

async function search(button) {
  const query = place.query.trim();
  if (query.length < 3) return;
  setBusy(button, true);
  try {
    place.results = (await post('/geo/search', { query })).results;
  } catch (err) {
    setBusy(button, false);
    apiFailed(err);
    return;
  }
  render();
}

// ── Costs, rooms, description ───────────────────────────

function costsTile() {
  return el('section', { class: 'box pad tile t-half hblock' },
    el('h2', {}, t('home.costs.title')),
    choice(t('home.costs.utilities'), state, 'utilities_mode',
      [['included', t('home.costs.included')], ['split', t('home.costs.split')]], { path: 'utilities_mode', rerender: true, cls: 'list' }),
    state.utilities_mode === 'split' && field(t('home.costs.utilitiesRub'),
      textInput(state, 'utilities_rub', { inputmode: 'numeric', maxlength: 6, placeholder: '2500', digits: true }),
      { path: 'utilities_rub', hint: t('home.costs.utilitiesHint') }),
    choice(t('home.costs.internet'), state, 'internet_mode',
      [['included', t('home.costs.internetIncluded')], ['split', t('home.costs.split')], ['none', t('home.costs.noInternet')]], { path: 'internet_mode', cls: 'list' }));
}

const SUNLIGHT = ['sunny', 'partial', 'shady'];

function roomFields(room, index) {
  const apartment = state.kind === 'apartment';
  const genders = [['f', t('home.room.f')], ['m', t('home.room.m')], ...(apartment ? [['any', t('home.room.any')]] : [])];
  const emojiInput = textInput(room, 'emoji', { maxlength: 40, autocomplete: 'off', class: 'emoji-input', 'aria-describedby': `emoji-hint-${index}` });
  let rolling = false;
  const roll = el('button', { class: 'btn secondary', type: 'button', disabled: !canEdit(), onclick: async () => {
    if (rolling) return; // no spinner or dimming: the answer comes at once
    rolling = true;
    const [emoji] = await rollEmoji();
    rolling = false;
    if (emoji) { room.emoji = emoji; emojiInput.value = emoji; changed(true); }
  } }, t('home.room.roll'));
  // A smaller room keeps as many places taken as fit.
  const capacity = numberSelect(room.capacity, 1, 6, (n) => {
    room.free_places = Math.max(0, n - taken(room));
    room.capacity = n;
    refresh('tile-taken', takenTile);
  });

  return [
    problem(`rooms.${index}`),
    home && !room.id && el('p', { class: 'note' }, `⚠ ${t('home.room.unsaved')}`),
    apartment && field(t('home.room.name'), textInput(room, 'name', { maxlength: 40, placeholder: t('home.room.namePlaceholder') }), { path: `rooms.${index}.name` }),
    choice(t('home.room.gender'), room, 'gender', genders, { path: `rooms.${index}.gender`, hint: t('home.room.genderHint'), cls: apartment ? 'three' : '' }),
    el('div', { class: 'two-fields' },
      field(t('home.room.capacity'), capacity, { hint: t('home.room.capacityHint') }),
      field(t('home.room.area'), textInput(room, 'area_m2', { inputmode: 'numeric', maxlength: 3, placeholder: '12', digits: true }),
        { path: `rooms.${index}.area_m2` })),
    apartment && field(t('home.room.rent'), textInput(room, 'rent_rub', { inputmode: 'numeric', maxlength: 6, placeholder: '14000', digits: true }),
      { path: `rooms.${index}.rent_rub`, hint: t('home.room.rentHint') }),
    apartment && field(t('home.room.description'), textArea(room, 'description', { rows: 3, placeholder: t('home.room.descriptionHint') }),
      { path: `rooms.${index}.description` }),
    choice(t('home.sun.legend'), room, 'sunlight', SUNLIGHT.map((v) => [v, t(`home.sun.${v}`)]),
      { path: `rooms.${index}.sunlight`, cls: 'list' }),
    apartment && roomPhotos(room, index),
    el('div', {},
      el('label', { class: 'field' }, el('span', {}, t('home.room.emoji')),
        el('div', { class: 'emoji-field' }, emojiInput, roll),
        el('small', { id: `emoji-hint-${index}` }, t('home.room.emojiHint'))),
      problem(`rooms.${index}.emoji`)),
  ].filter(Boolean);
}

/** A dorm has one room: a half tile beside the location. */
function dormRoomTile() {
  return el('section', { class: 'box pad tile t-half hblock' }, el('h2', {}, t('home.room.title')), ...roomFields(state.rooms[0], 0));
}

/** An apartment's rooms: one card each, side by side on wide screens, "+ Add a room" under them. */
function apartmentRoomsTile() {
  const many = state.rooms.length > 1;
  const cards = state.rooms.map((room, index) => el('li', { class: 'box pad hblock room-card' },
    el('div', { class: 'row spread' },
      el('h3', {}, t('home.room.titleN', { n: index + 1 })),
      // A room someone lives in can't be removed (the server refuses: ROOM_OCCUPIED).
      canEdit() && many && !room.residents && el('button', { class: 'linkbtn', type: 'button',
        onclick: () => { state.rooms.splice(index, 1); render(); changed(true); } }, t('home.room.remove'))),
    ...roomFields(room, index)));
  return el('section', { class: 'tile t-wide rblock' },
    el('h2', { class: 'title' }, t('home.rooms.title')),
    el('ul', { class: 'room-cards' }, ...cards),
    canEdit() && state.rooms.length < MAX_ROOMS && el('div', { class: 'add-room' }, el('button', { class: 'btn secondary', type: 'button', onclick: async () => {
      const [emoji] = await rollEmoji();
      state.rooms.push(blankRoom(emoji ?? ''));
      render();
      changed(true);
    } }, `+ ${t('home.room.add')}`)));
}

function aboutTile() {
  return el('section', { class: 'box pad tile t-wide hblock' },
    el('h2', {}, t('home.about.title')),
    field(t('home.about.label'), textArea(state, 'description', { rows: 5, placeholder: t('home.about.hint') }), { path: 'description' }));
}

// ── Contacts (a new place only) ─────────────────────────
// A listing is shown once a host can be reached, so it can't be listed without a phone,
// Telegram or VK. The same fields as on the account page (js/contacts.js).

const contactFields = el('div', { class: 'stack' });
const contactError = el('p', { class: 'note error', role: 'alert', hidden: true });
const contacts = mountContacts({ fields: contactFields, error: contactError, getUser: () => user, setUser: (next) => { user = next; } });

function contactsTile() {
  return el('section', { class: 'box pad tile t-wide hblock', id: 'tile-contacts', 'data-private': true },
    el('h2', {}, t('account.contacts.title')),
    el('p', { class: 'hint' }, t('account.contacts.hint')),
    contactError,
    contactFields,
    el('p', { class: 'hint' }, t('account.contacts.meta')));
}

// ── Residents and rights ────────────────────────────────

const RIGHTS = ['can_edit', 'can_photos', 'can_invites', 'can_residents'];
const rightLabel = (name) => ({
  can_edit: t('home.rights.can_edit'), can_photos: t('home.rights.can_photos'),
  can_invites: t('home.rights.can_invites'), can_residents: t('home.rights.can_residents'),
}[name]);

/** null: in the apartment, in none of its listed rooms. */
const roomName = (id) => {
  const index = home.rooms.findIndex((r) => r.id === id);
  return index < 0 ? t('home.residents.flatOnly') : `${home.rooms[index].emoji} ${home.rooms[index].name || t('home.room.titleN', { n: index + 1 })}`;
};

async function homeAction(action) {
  try {
    await serial(async () => { home = await action(); });
    return true;
  } catch (err) {
    apiFailed(err);
    return false;
  }
}

function avatar(person) {
  return person.avatar_url
    ? el('img', { class: 'avatar sm', src: person.avatar_url, alt: '' })
    : el('span', { class: 'avatar sm', 'aria-hidden': 'true' }, person.first_name.slice(0, 1));
}

function residentCard(person) {
  const manage = home.permissions.can_residents;
  const url = `/homes/${home.id}/residents/${person.user_id}`;
  // Rights decide what this page lets you do, so a change to your own redraws everything.
  const update = async (change) => { if (await homeAction(() => put(url, change))) saved(); rerender(); };
  const rights = manage
    ? el('div', { class: 'rights' }, ...RIGHTS.map((name) => {
      const box = el('input', { type: 'checkbox' });
      box.checked = person.permissions[name];
      box.addEventListener('change', () => update({ [name]: box.checked }));
      return el('label', { class: 'check' }, box, el('span', {}, rightLabel(name)));
    }))
    : el('p', { class: 'hint' }, RIGHTS.filter((name) => person.permissions[name]).map(rightLabel).join(' · ') || t('home.rights.none'));
  let room = null;
  // An apartment's host may live in one of its rooms or just in the flat (an owner letting the rooms).
  if (home.kind === 'apartment') {
    if (manage || person.is_you) {
      const picker = el('select', { 'aria-label': t('home.residents.room') },
        el('option', { value: '' }, t('home.residents.flatOnly')),
        ...home.rooms.map((r) => el('option', { value: r.id }, roomName(r.id))));
      picker.value = person.room_id ?? '';
      picker.addEventListener('change', () => update({ room_id: picker.value || null }));
      room = el('label', { class: 'field' }, el('span', {}, t('home.residents.room')), picker);
    } else {
      room = el('p', { class: 'meta' }, roomName(person.room_id));
    }
  }
  return el('li', { class: 'box pad resident-card' },
    el('div', { class: 'row person-head' }, avatar(person),
      el('div', { class: 'person-name' },
        el('h3', {}, `${person.first_name} ${person.last_name}`),
        person.is_you && el('span', { class: 'tag fill-yellow' }, t('home.residents.you')))),
    room, rights,
    manage && !person.is_you && el('div', {}, el('button', { class: 'linkbtn', type: 'button', onclick: async () => {
      if (!window.confirm(t('home.residents.removeConfirm', { name: person.first_name }))) return;
      if (await homeAction(() => del(url))) saved();
      render();
    } }, t('home.residents.remove'))));
}

function residentsTile() {
  return el('section', { class: 'tile t-wide rblock', id: 'tile-residents', 'data-private': true },
    el('h2', { class: 'title' }, t('home.residents.title')),
    el('p', { class: 'hint' }, home.permissions.can_residents ? t('home.residents.hintManage') : t('home.residents.hint')),
    el('ul', { class: 'resident-cards' }, ...home.residents.map(residentCard)));
}

// ── Invites ─────────────────────────────────────────────

let invites = null;     // active invites, loaded once the person may see them
let invitesLoading = null;
let freshInvite = null; // the one just created: its link is shown once

async function loadInvites() {
  try { invites = await get(`/homes/${home.id}/invites`); } catch (err) { reportBug(err, { where: 'invites' }); invites = []; }
}

function ensureInvites() {
  if (invites !== null || invitesLoading) return;
  invitesLoading = loadInvites().then(() => { invitesLoading = null; refresh('tile-invites', invitesTile); });
}

function invitesTile() {
  const box = (...children) => el('section', { class: 'box pad tile t-half hblock', id: 'tile-invites', 'data-private': true },
    el('h2', {}, t('home.invites.title')), ...children.filter(Boolean));
  if (!home.permissions.can_invites) return box(el('p', { class: 'hint' }, t('home.invites.noRight')));
  if (invites === null) { ensureInvites(); return box(el('p', { class: 'hint' }, t('home.invites.hint'))); }
  const date = (iso) => new Date(iso).toLocaleDateString(currentLang() === 'zh' ? 'zh-CN' : currentLang(), { day: 'numeric', month: 'long' });

  let roomPicker = null;
  if (home.kind === 'apartment' && home.rooms.length > 1) {
    roomPicker = el('select', {}, ...home.rooms.map((r) => el('option', { value: r.id }, roomName(r.id))));
  }
  const create = el('button', { class: 'btn', type: 'button', onclick: async () => {
    setBusy(create, true);
    try {
      freshInvite = await post(`/homes/${home.id}/invites`, { room_id: roomPicker?.value ?? null });
      await loadInvites();
    } catch (err) {
      setBusy(create, false);
      apiFailed(err);
      return;
    }
    refresh('tile-invites', invitesTile);
  } }, t('home.invites.create'));

  let fresh = null;
  if (freshInvite) {
    const link = el('input', { readonly: true, 'aria-label': t('home.invites.link') });
    link.value = freshInvite.url;
    link.addEventListener('focus', () => link.select());
    const copy = el('button', { class: 'btn secondary', type: 'button', onclick: async () => {
      try { await navigator.clipboard.writeText(freshInvite.url); toast(t('home.invites.copied'), '', { ms: 2000 }); } catch { link.focus(); }
    } }, t('home.invites.copy'));
    fresh = el('div', { class: 'box pad fill-green invite-fresh' },
      el('b', {}, t('home.invites.ready')),
      el('label', { class: 'field' }, link),
      el('p', { class: 'hint' }, t('home.invites.readyHint', { code: freshInvite.code, date: date(freshInvite.expires_at) })),
      el('div', {}, copy));
  }

  const list = invites.length
    ? el('ul', { class: 'residents' }, ...invites.map((inv) => el('li', { class: 'resident' },
      el('p', {}, t('home.invites.item', { name: inv.created_by_name ?? '—', date: date(inv.expires_at), uses: inv.uses })),
      el('div', {}, el('button', { class: 'linkbtn', type: 'button', onclick: async () => {
        try { await del(`/homes/${home.id}/invites/${inv.id}`); } catch (err) { apiFailed(err); }
        if (freshInvite?.id === inv.id) freshInvite = null;
        await loadInvites();
        refresh('tile-invites', invitesTile);
      } }, t('home.invites.revoke'))))))
    : el('p', { class: 'hint' }, t('home.invites.empty'));

  return box(
    el('p', { class: 'hint' }, t('home.invites.hint')),
    roomPicker && el('label', { class: 'field' }, el('span', {}, t('home.invites.room')), roomPicker),
    el('div', {}, create),
    fresh, list);
}

// ── Leaving ─────────────────────────────────────────────

function leaveTile() {
  return el('section', { class: 'box pad tile t-half hblock' },
    el('h2', {}, t('home.leave.heading')),
    el('p', { class: 'hint' }, t('home.leave.hint'), ' ',
      el('a', { href: '#taken-0', onclick: (e) => {
        e.preventDefault();
        const target = $('taken-0');
        // Focus first: focusing during a smooth scroll stops it in Chromium.
        target?.focus({ preventScroll: true });
        target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      } }, t('home.leave.setZero'))),
    el('div', {}, el('button', { class: 'btn secondary', type: 'button', onclick: () => $('leave-dialog').showModal() }, t('home.leave.button'))));
}

$('leave-cancel').addEventListener('click', () => $('leave-dialog').close());
$('leave-confirm').addEventListener('click', async () => {
  setBusy($('leave-confirm'), true);
  try {
    await serial(() => del('/homes/mine/membership'));
    location.reload();
  } catch (err) {
    setBusy($('leave-confirm'), false);
    $('leave-dialog').close();
    apiFailed(err);
  }
});

// ── Render ──────────────────────────────────────────────

function render() {
  mapHandle?.remove();
  mapHandle = null;
  const form = $('home-form');
  if (!state.kind) {
    form.replaceChildren(kindPicker());
    return;
  }
  const apartment = state.kind === 'apartment';
  // replaceChildren() would print a `false` from the `cond && el(...)` items as text.
  form.replaceChildren(el('div', { class: home ? 'bento' : 'bento is-new' }, ...[
    photosTile(),
    titleTile(),
    statusTile(),
    placesTile(),
    home && ctaTile(),
    takenTile(),
    apartment ? apartmentTile() : dormTile(),
    apartment ? costsTile() : dormRoomTile(),
    apartment && apartmentRoomsTile(),
    aboutTile(),
    home && residentsTile(),
    home && invitesTile(),
    home && leaveTile(),
    !home && (contacts.render(), contactsTile()),
    !home && el('div', { class: 'tile t-wide hpublish' }, el('button', { class: 'btn', type: 'submit' }, t('home.publish'))),
  ].filter(Boolean)));
  mountMap();
}

/** Rebuild the page without losing the field being typed in. */
function rerender() {
  const controls = () => [...$('home-form').querySelectorAll('input, select, textarea, button')];
  const active = document.activeElement;
  const at = controls().indexOf(active);
  let range = null;
  try { if (at >= 0 && active.selectionStart != null) range = [active.selectionStart, active.selectionEnd]; } catch { /* not a text field */ }
  render();
  const node = at >= 0 ? controls()[at] : null;
  if (!node) return;
  node.focus({ preventScroll: true });
  try { if (range) node.setSelectionRange(...range); } catch { /* not a text field */ }
}

// ── Save ────────────────────────────────────────────────

const number = (value) => (value === '' || value == null ? null : Number(String(value).replace(/\D/g, '')));

function payload() {
  const apartment = state.kind === 'apartment';
  return {
    kind: state.kind,
    description: state.description,
    building: apartment ? null : state.building || null,
    room_label: apartment ? null : roomLabel(),
    district: apartment ? state.district : null,
    lat: state.area?.lat ?? null, lon: state.area?.lon ?? null, radius_m: state.area?.radius_m ?? null,
    utilities_mode: apartment ? state.utilities_mode || null : null,
    utilities_rub: apartment && state.utilities_mode === 'split' ? number(state.utilities_rub) : null,
    internet_mode: apartment ? state.internet_mode || null : null,
    photo_ids: home ? [] : staged.map((p) => p.id),
    rooms: state.rooms.map((r) => ({
      id: r.id ?? undefined, name: r.name, gender: r.gender || undefined, capacity: r.capacity, free_places: r.free_places,
      rent_rub: apartment ? number(r.rent_rub) : null, emoji: r.emoji,
      area_m2: number(r.area_m2), description: apartment ? r.description : '', sunlight: r.sunlight || null,
      photo_ids: apartment ? r.photo_ids : [],
    })),
  };
}

/** Everything that is plainly missing, at once (the server reports problems in rounds). */
function missing() {
  const out = {};
  const need = (path, ok) => { if (!ok) out[path] = 'REQUIRED'; };
  if (state.kind === 'dorm') {
    need('building', state.building);
    // Editing: the stored room stays unless a new one is typed in, and then it must be whole.
    if (!home || roomTouched()) {
      if (!state.room_number) out.room_label = 'REQUIRED';
      else if (!ROOM_NUMBER.test(state.room_number)) out.room_label = 'INVALID_ROOM';
      else if (state.room_letter == null) out.room_label = 'ROOM_LETTER';
    }
  } else {
    need('location', state.area);
    need('district', state.district.trim());
    need('utilities_mode', state.utilities_mode);
    if (state.utilities_mode === 'split') need('utilities_rub', String(state.utilities_rub).trim());
    need('internet_mode', state.internet_mode);
  }
  need('description', state.description.trim());
  if (!home && !staged.length) out.photos = 'PHOTO_REQUIRED';
  state.rooms.forEach((room, i) => {
    need(`rooms.${i}.gender`, room.gender);
    need(`rooms.${i}.sunlight`, room.sunlight);
    if (state.kind === 'apartment') {
      need(`rooms.${i}.name`, room.name.trim());
      need(`rooms.${i}.rent_rub`, String(room.rent_rub).trim());
    }
    const area = number(room.area_m2);
    if (area == null) out[`rooms.${i}.area_m2`] = 'REQUIRED';
    else if (area < 3 || area > 200) out[`rooms.${i}.area_m2`] = 'AREA_RANGE';
    if (state.kind === 'apartment') need(`rooms.${i}.description`, room.description.trim());
    need(`rooms.${i}.emoji`, room.emoji.trim());
  });
  return out;
}

const FORM_ERROR = '#home-form .note.error[data-error], #home-form .note.error[role="alert"]';

function showErrors() {
  render();
  document.querySelector(FORM_ERROR)?.scrollIntoView({ block: 'center' });
}

// A new place: sent once, by the button.
let creating = false;
$('home-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (home) { changed(true); return; } // Enter in a field
  if (creating) return;
  const button = e.submitter;
  // Photos still on their way: wait for them, or the listing would go without.
  if (uploading) { toast(t('home.photos.wait'), '', { ms: 3000 }); return; }
  takenRoomId = null;
  errors = missing();
  if (Object.keys(errors).length) { showErrors(); return; }
  // Contacts typed a moment ago may not be saved yet.
  creating = true;
  await contacts.save.now();
  if (!hasPrimary(user)) {
    creating = false;
    contacts.showError('NEED_CONTACT');
    $('tile-contacts')?.scrollIntoView({ block: 'center' });
    return;
  }
  if (button) setBusy(button, true);
  try {
    home = await serial(() => post('/homes', payload()));
  } catch (err) {
    creating = false;
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return; }
    const { contacts: contactCode, ...fields } = err.fields ?? {};
    errors = fields;
    if (err.code === 'ROOM_TAKEN') takenRoomId = err.data?.room_id ?? null;
    if (contactCode) {
      render();
      contacts.showError(contactCode);
      $('tile-contacts')?.scrollIntoView({ block: 'center' });
      return;
    }
    showErrors();
    if (!document.querySelector(FORM_ERROR)) toast(t('error.title'), errorText(err), { error: true });
    return;
  }
  staged = [];
  state = stateFrom(home);
  savedKey = JSON.stringify(payload());
  place.step = state.area ? 'area' : 'search';
  place.point = null;
  shown = 0;
  render();
  // Listed but not shown yet (e.g. no free place): the status tile says why.
  toast(t('home.created'), home.visible ? t('home.createdText') : t('home.createdHidden'));
  window.scrollTo(0, 0);
});

// ── Autosave (once the place is listed) ─────────────────

let savedKey = home ? JSON.stringify(payload()) : null; // the form as the server has it

function setErrors(next, taken = null) {
  if (JSON.stringify(next) === JSON.stringify(errors) && taken === takenRoomId) return;
  errors = next;
  takenRoomId = taken;
  rerender();
}

async function saveHome() {
  const body = payload();
  // e.g. a cleared field typed back. A half-typed room number also leaves the payload as it was,
  // so it goes on to missing() to say what is still needed.
  if (JSON.stringify(body) === savedKey && !(state.kind === 'dorm' && roomTouched())) { setErrors({}); return; }
  const gaps = missing();
  if (Object.keys(gaps).length) {
    // Nothing is sent until the form is whole. A room that was just added says so itself
    // ("not saved yet") instead of turning red before anyone had a chance to fill it in.
    setErrors(Object.fromEntries(Object.entries(gaps).filter(([path]) => {
      const room = path.match(/^rooms\.(\d+)\./);
      return !room || state.rooms[room[1]]?.id;
    })));
    return;
  }
  // The room objects as sent: rooms may be added or removed while the request is on its way.
  const sentRooms = state.rooms.slice();
  try {
    await serial(async () => { home = await put(`/homes/${home.id}`, body); });
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return; }
    setErrors(err.fields ?? {}, err.code === 'ROOM_TAKEN' ? err.data?.room_id ?? null : null);
    if (!document.querySelector(FORM_ERROR)) toast(t('error.title'), errorText(err), { error: true });
    return;
  }
  // Take over what only the server knows: the ids of new rooms (it keeps their order) and
  // how many live in each. The rest of `state` stays: the person may have typed on meanwhile.
  const added = body.rooms.some((room) => !room.id);
  sentRooms.forEach((room, i) => {
    const out = home.rooms[i];
    if (out) { room.id = out.id; room.residents = out.residents; }
  });
  // The dorm room number is sent once and not shown again.
  const sentLabel = body.room_label;
  if (sentLabel && roomLabel() === sentLabel) { state.room_number = ''; state.room_letter = null; }
  savedKey = JSON.stringify({ ...body, room_label: null, rooms: body.rooms.map((room, i) => ({ ...room, id: home.rooms[i]?.id })) });
  if (added || sentLabel || Object.keys(errors).length || takenRoomId) {
    errors = {};
    takenRoomId = null;
    rerender();
  } else {
    refreshSummary();
  }
  saved();
}

const saveSoon = autosaver(saveHome, 1200);

/** The form changed: save after a pause in typing, or at once (`now`) after a click or leaving a field. */
function changed(now = false) {
  refreshSummary();
  if (!home || !canEdit()) return;
  if (now) saveSoon.now(); else saveSoon();
}

render();
document.addEventListener('langchange', render);

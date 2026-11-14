// "My home": list a dorm room or an apartment, then edit it.
//
// The whole form is rebuilt from `state` on every structural change (kind picked, room added,
// language switched); typing only writes into `state`. That keeps one source of truth and
// makes re-translation free.
//
// A new place is sent once, with the "List it" button. After that there is no save button:
// every change to the form saves itself (see "Autosave") and answers with a "Saved" pop-up.
//
// Privacy rules this page is responsible for:
//   - a dorm room's number is sent once and never shown again (the server doesn't return it);
//   - an apartment's address is used only to find a point on the map; the point is replaced
//     by an obfuscated circle here, in the browser, and only the circle is sent.

import { ApiError, del, get, post, put } from '../api.js';
import { autosaver } from '../autosave.js';
import { reportBug } from '../errors.js';
import { currentLang, t } from '../i18n.js';
import { initPage } from '../layout.js';
import { AKADEMGORODOK, addArea, addPin, createMap, obfuscate } from '../map.js';
import { el, errorText, saved, setBusy, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);
// Moved into the form (above the "List it" button) while the place is new; see render().
const photosSection = $('photos-section');
const MAX_ROOMS = 6;

const { user } = await initPage({ auth: 'required' });
const [meta, mine] = await Promise.all([get('/meta'), get('/homes/mine')]);

let home = mine.home;   // as the server knows it; null until created
let errors = {};        // { "rooms.0.emoji": "EMOJI_TAKEN", … } from the last save
let takenRoomId = null; // set when the dorm room turned out to be listed already

// ── State ───────────────────────────────────────────────

const blankRoom = (emoji = '') => ({ id: null, name: '', gender: '', capacity: 2, free_places: 1, rent_rub: '', emoji });

function stateFrom(h) {
  if (!h) {
    return { kind: null, description: '', sunlight: '', building: '', room_number: '', room_letter: null, district: '', area: null,
      utilities_mode: '', utilities_rub: '', internet_mode: '', rooms: [blankRoom()] };
  }
  return {
    kind: h.kind, description: h.description, sunlight: h.sunlight ?? '', building: h.building ?? '', room_number: '', room_letter: null,
    district: h.district ?? '', area: h.kind === 'apartment' ? { lat: h.lat, lon: h.lon, radius_m: h.radius_m } : null,
    utilities_mode: h.utilities_mode ?? '', utilities_rub: h.utilities_rub ?? '', internet_mode: h.internet_mode ?? '',
    rooms: h.rooms.map((r) => ({ ...r, rent_rub: r.rent_rub ?? '' })),
  };
}

let state = stateFrom(home);
// The address flow: 'search' → 'pin' (drag to the building) → 'area' (the circle that gets saved).
const place = { step: state.area ? 'area' : 'search', query: '', results: null, point: null, searching: false };
const canEdit = !home || home.permissions.can_edit;

async function rollEmoji(count = 1) {
  try {
    return (await post('/emoji/roll', { count })).emojis;
  } catch (err) {
    reportBug(err, { where: 'rollEmoji' });
    return [];
  }
}

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

function textInput(obj, key, attrs = {}) {
  const input = el('input', { ...attrs, disabled: !canEdit });
  input.value = obj[key] ?? '';
  input.addEventListener('input', () => { obj[key] = input.value; changed(); });
  input.addEventListener('change', () => changed(true));
  return input;
}

function select(obj, key, options, { numeric = false, onchange } = {}) {
  const node = el('select', { disabled: !canEdit }, ...options.map(([value, label]) => el('option', { value }, label)));
  node.value = String(obj[key] ?? '');
  node.addEventListener('change', () => {
    obj[key] = numeric ? Number(node.value) : node.value;
    onchange?.();
    changed(true);
  });
  return node;
}

/** Single-choice buttons. Changing the answer re-renders only when `rerender` is set. */
function choice(legend, obj, key, options, { path, hint, rerender = false, cls = '' } = {}) {
  const buttons = options.map(([value, label]) => el('button', {
    type: 'button', 'aria-pressed': String(obj[key] === value), disabled: !canEdit,
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

// ── Sections of the form ────────────────────────────────

function kindPicker() {
  return el('section', { class: 'box pad hblock' },
    el('h2', {}, t('home.kind.title')),
    el('div', { class: 'opts' },
      ...[['dorm', t('home.kind.dorm')], ['apartment', t('home.kind.apartment')]].map(([kind, label]) => el('button', {
        type: 'button', onclick: async () => {
          state.kind = kind;
          const [emoji] = await rollEmoji();
          state.rooms = [blankRoom(emoji ?? '')];
          render();
        },
      }, label))));
}

function dormSection() {
  const lang = currentLang();
  const buildings = meta.dorms.map((d) => [d.id, d.address ? `${t('home.dorm.n', { name: d.name })} · ${d.address}` : t('home.dorm.n', { name: d.name })]);
  void lang;
  const taken = takenRoomId && el('p', { class: 'note error', role: 'alert' },
    `✕ ${t('home.dorm.taken')} `, el('a', { href: `/room?id=${takenRoomId}` }, t('home.dorm.takenLink')));
  return el('section', { class: 'box pad hblock' },
    el('h2', {}, t('home.dorm.title')),
    field(t('home.dorm.building'), select(state, 'building', [['', t('home.choose')], ...buildings]), { path: 'building' }),
    roomField(),
    taken);
}

// A dorm room is a number from 100 to 999 plus the block letter: Б, М or none, read "100Б".
// The letter button right of the number starts at "?" (not chosen yet); each click moves it
// on to the next letter. The letters are Cyrillic in every language: that's what's on the doors.
const ROOM_LETTERS = ['b', 'm', ''];
const LETTER_TEXT = { b: 'Б', m: 'М', '': '' };
const ROOM_NUMBER = /^[1-9][0-9]{2}$/;

/** "100b", "100m", "100", or null while the number or the letter is missing. */
const roomLabel = () => (ROOM_NUMBER.test(state.room_number) && state.room_letter != null ? state.room_number + state.room_letter : null);
const roomTouched = () => state.room_number !== '' || state.room_letter != null;

function roomField() {
  const letterName = () => (state.room_letter == null ? t('home.dorm.letterUnset')
    : state.room_letter === '' ? t('home.dorm.letterNone') : LETTER_TEXT[state.room_letter]);
  const letter = el('button', { type: 'button', class: 'room-letter', disabled: !canEdit });
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
    placeholder: home ? t('home.dorm.roomSaved') : '100', disabled: !canEdit,
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

let mapHandle = null; // { map, layer } of the map currently on the page

function placeSection() {
  const host = el('div', { class: 'map', id: 'place-map' });
  const body = [];

  if (place.step === 'search') {
    const input = textInput(place, 'query', { type: 'search', placeholder: t('home.place.placeholder'), autocomplete: 'off', enterkeyhint: 'search' });
    const go = el('button', { class: 'btn secondary', type: 'button', onclick: () => search(go) }, t('home.place.find'));
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); search(go); } });
    body.push(
      el('p', { class: 'hint' }, t('home.place.why')),
      field(t('home.place.address'), input),
      el('div', { class: 'row' }, go,
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { place.point = { ...AKADEMGORODOK }; place.step = 'pin'; render(); } }, t('home.place.manual'))),
      place.results && (place.results.length
        ? el('div', { class: 'opts results' }, ...place.results.map((r) => el('button', {
          type: 'button', onclick: () => { place.point = { lat: r.lat, lon: r.lon }; if (r.district && !state.district) state.district = r.district; place.step = 'pin'; render(); },
        }, r.label)))
        : el('p', { class: 'note' }, `⚠ ${t('home.place.none')}`)));
  } else if (place.step === 'pin') {
    body.push(
      el('p', { class: 'hint' }, t('home.place.pinHint')),
      host,
      el('div', { class: 'row' },
        el('button', { class: 'btn', type: 'button', onclick: () => { state.area = obfuscate(place.point); place.step = 'area'; render(); changed(true); } }, t('home.place.hide')),
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { place.step = 'search'; render(); } }, t('home.place.back'))));
  } else {
    body.push(
      el('p', { class: 'note success' }, `✓ ${t('home.place.areaHint')}`),
      host,
      canEdit && el('div', { class: 'row' },
        place.point && el('button', { class: 'btn secondary', type: 'button', onclick: () => { state.area = obfuscate(place.point); render(); changed(true); } }, t('home.place.reroll')),
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { place.step = 'search'; place.results = null; render(); } }, t('home.place.again'))));
  }

  // data-private: the address search results and the exact pin are the real address.
  return el('section', { class: 'box pad hblock', 'data-private': true },
    el('h2', {}, t('home.place.title')),
    ...body,
    problem('location'),
    field(t('home.place.district'), textInput(state, 'district', { maxlength: 60, placeholder: t('home.place.districtPlaceholder') }),
      { path: 'district', hint: t('home.place.districtHint') }));
}

/** Leaflet needs its element in the document, so maps are attached after render(). */
function mountMap() {
  mapHandle?.map.remove();
  mapHandle = null;
  const host = $('place-map');
  if (!host) return;
  if (place.step === 'pin') {
    const map = createMap(host, { ...place.point, zoom: 17 });
    addPin(map, place.point, (p) => { place.point = p; });
    mapHandle = { map };
  } else if (state.area) {
    const map = createMap(host, { lat: state.area.lat, lon: state.area.lon, zoom: 15 });
    addArea(map, state.area);
    mapHandle = { map };
  }
}

async function search(button) {
  const query = place.query.trim();
  if (query.length < 3) return;
  setBusy(button, true);
  try {
    place.results = (await post('/geo/search', { query })).results;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true });
    setBusy(button, false);
    return;
  }
  render();
}

function costsSection() {
  return el('section', { class: 'box pad hblock' },
    el('h2', {}, t('home.costs.title')),
    choice(t('home.costs.utilities'), state, 'utilities_mode',
      [['included', t('home.costs.included')], ['split', t('home.costs.split')]], { path: 'utilities_mode', rerender: true }),
    state.utilities_mode === 'split' && field(t('home.costs.utilitiesRub'),
      textInput(state, 'utilities_rub', { inputmode: 'numeric', maxlength: 6, placeholder: '2500' }),
      { path: 'utilities_rub', hint: t('home.costs.utilitiesHint') }),
    choice(t('home.costs.internet'), state, 'internet_mode',
      [['included', t('home.costs.internetIncluded')], ['split', t('home.costs.split')], ['none', t('home.costs.noInternet')]], { path: 'internet_mode' }));
}

function roomSection(room, index) {
  const apartment = state.kind === 'apartment';
  const genders = [['f', t('home.room.f')], ['m', t('home.room.m')], ...(apartment ? [['any', t('home.room.any')]] : [])];
  const places = (from, to) => Array.from({ length: to - from + 1 }, (_, i) => [String(from + i), String(from + i)]);
  const emojiInput = textInput(room, 'emoji', { maxlength: 40, autocomplete: 'off', class: 'emoji-input', 'aria-describedby': `emoji-hint-${index}` });
  const roll = el('button', { class: 'btn secondary', type: 'button', disabled: !canEdit, onclick: async () => {
    setBusy(roll, true);
    const [emoji] = await rollEmoji();
    setBusy(roll, false);
    if (emoji) { room.emoji = emoji; emojiInput.value = emoji; changed(true); }
  } }, t('home.room.roll'));

  return el('section', { class: 'box pad hblock' },
    el('div', { class: 'row spread' },
      el('h2', {}, apartment ? t('home.room.titleN', { n: index + 1 }) : t('home.room.title')),
      apartment && canEdit && state.rooms.length > 1 && el('button', { class: 'linkbtn', type: 'button',
        onclick: () => { state.rooms.splice(index, 1); render(); changed(true); } }, t('home.room.remove'))),
    problem(`rooms.${index}`),
    home && !room.id && el('p', { class: 'note' }, `⚠ ${t('home.room.unsaved')}`),
    apartment && field(t('home.room.name'), textInput(room, 'name', { maxlength: 40, placeholder: t('home.room.namePlaceholder') })),
    choice(t('home.room.gender'), room, 'gender', genders, { path: `rooms.${index}.gender`, hint: t('home.room.genderHint') }),
    el('div', { class: 'two-fields' },
      field(t('home.room.capacity'), select(room, 'capacity', places(1, 6), { numeric: true, onchange: () => {
        if (room.free_places > room.capacity) room.free_places = room.capacity;
        render();
      } })),
      field(t('home.room.free'), Object.assign(select(room, 'free_places', places(0, room.capacity), { numeric: true }), { id: `free-${index}` }),
        { path: `rooms.${index}.free_places` })),
    apartment && field(t('home.room.rent'), textInput(room, 'rent_rub', { inputmode: 'numeric', maxlength: 6, placeholder: '14000' }),
      { path: `rooms.${index}.rent_rub`, hint: t('home.room.rentHint') }),
    el('div', {},
      el('label', { class: 'field' }, el('span', {}, t('home.room.emoji')), emojiInput,
        el('small', { id: `emoji-hint-${index}` }, t('home.room.emojiHint'))),
      problem(`rooms.${index}.emoji`)),
    el('div', {}, roll));
}

function aboutSection() {
  const area = el('textarea', { rows: 5, maxlength: 1000, disabled: !canEdit });
  area.value = state.description;
  area.addEventListener('input', () => { state.description = area.value; changed(); });
  area.addEventListener('change', () => changed(true));
  return el('section', { class: 'box pad hblock' },
    el('h2', {}, t('home.about.title')),
    field(t('home.about.label'), area, { hint: t('home.about.hint') }),
    choice(t('home.sun.legend'), state, 'sunlight', SUNLIGHT.map((v) => [v, t(`home.sun.${v}`)]),
      { path: 'sunlight', hint: t('home.sun.hint'), cls: 'three' }));
}

const SUNLIGHT = ['sunny', 'partial', 'shady'];

// ── Status, photos, leaving ─────────────────────────────

function renderStatus() {
  if (!home) { $('status').replaceChildren(); return; }
  const notes = [];
  if (home.visible) notes.push(el('p', { class: 'note success' }, `✓ ${t('home.status.visible')}`));
  if (home.needs_contact) notes.push(el('p', { class: 'note' }, `⚠ ${t('home.status.needsContact')} `, el('a', { href: '/account' }, t('home.status.addContact'))));
  if (home.needs_free_place) notes.push(el('p', { class: 'note' }, `⚠ ${t('home.status.needsFreePlace')}`));
  // Red: unlike the other gaps, this one is easy to cause by accident (deleting the last photo).
  if (home.needs_photo) {
    notes.push(el('p', { class: 'note error', role: 'alert' }, `✕ ${t('home.status.needsPhoto')} `,
      el('a', { href: '#photos-section' }, t('home.status.addPhoto'))));
  }
  if (!canEdit) notes.push(el('p', { class: 'note' }, `⚠ ${t('home.status.readOnly')}`));
  $('status').replaceChildren(...notes);
}

// Photos picked before the place is listed wait here and are uploaded right after it is.
let pendingPhotos = []; // [{ file, url }]
const MAX_PHOTOS = 10;

function renderPhotos() {
  const section = photosSection;
  section.hidden = !home && !state.kind;
  if (section.hidden) return;
  const canPhotos = home ? home.permissions.can_photos : true;
  const act = async (action) => {
    try { home = await action(); renderPhotos(); renderStatus(); saved(); } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      toast(t('error.title'), errorText(err), { error: true });
    }
  };
  // The same tiles for both: on the server (home) or still in the browser (pending).
  const list = home ? home.photos.map((p) => ({ id: p.id, url: p.url })) : pendingPhotos;
  const makeFirst = (i) => (home
    ? act(() => put(`/homes/${home.id}/photos/order`, { photo_ids: [list[i].id, ...list.filter((_, j) => j !== i).map((x) => x.id)] }))
    : (pendingPhotos.unshift(...pendingPhotos.splice(i, 1)), renderPhotos()));
  const remove = (i) => {
    if (home) { act(() => del(`/homes/${home.id}/photos/${list[i].id}`)); return; }
    URL.revokeObjectURL(pendingPhotos[i].url);
    pendingPhotos.splice(i, 1);
    renderPhotos();
  };
  const tiles = list.map((p, i) => el('figure', {},
    el('img', { src: p.url, alt: t('home.photos.alt', { n: i + 1 }), loading: 'lazy' }),
    canPhotos && el('figcaption', {},
      i > 0 ? el('button', { type: 'button', 'aria-label': t('home.photos.first'), title: t('home.photos.first'), onclick: () => makeFirst(i) }, '★') : el('span', {}),
      el('button', { type: 'button', 'aria-label': t('home.photos.delete'), title: t('home.photos.delete'), onclick: () => remove(i) }, '×'))));
  let upload = null;
  if (canPhotos && list.length < MAX_PHOTOS) {
    const input = el('input', { class: 'sr-only', type: 'file', accept: 'image/jpeg,image/png,image/webp', multiple: true });
    upload = el('label', { class: 'upload' }, input, `+ ${t('home.photos.add')}`);
    input.addEventListener('change', async () => {
      const files = [...input.files].slice(0, MAX_PHOTOS - list.length);
      if (!home) {
        pendingPhotos.push(...files.map((file) => ({ file, url: URL.createObjectURL(file) })));
        if (errors.photos) { delete errors.photos; }
        renderPhotos();
        return;
      }
      upload.setAttribute('aria-busy', 'true');
      await uploadPhotos(files);
      renderPhotos();
      renderStatus();
    });
  }
  section.replaceChildren(el('div', { class: 'box pad hblock' },
    el('h2', {}, t('home.photos.title')),
    el('p', { class: 'hint' }, t('home.photos.hint')),
    !home && pendingPhotos.length > 0 && el('p', { class: 'note' }, `⚠ ${t('home.photos.pending')}`),
    el('div', { class: 'photos' }, ...tiles, upload),
    problem('photos')));
}

/** Upload one by one, in order; stop at the first that fails. */
async function uploadPhotos(files) {
  for (const file of files) {
    const body = new FormData();
    body.append('file', file);
    try { home = await post(`/homes/${home.id}/photos`, body); saved(); } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      toast(t('error.title'), errorText(err), { error: true });
      return;
    }
  }
}

// ── Residents and rights ────────────────────────────────

const RIGHTS = ['can_edit', 'can_photos', 'can_invites', 'can_residents'];
const rightLabel = (name) => ({
  can_edit: t('home.rights.can_edit'), can_photos: t('home.rights.can_photos'),
  can_invites: t('home.rights.can_invites'), can_residents: t('home.rights.can_residents'),
}[name]);

async function homeAction(action) {
  try {
    home = await action();
    return true;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true });
    return false;
  }
}

function avatar(person) {
  return person.avatar_url
    ? el('img', { class: 'avatar sm', src: person.avatar_url, alt: '' })
    : el('span', { class: 'avatar sm', 'aria-hidden': 'true' }, person.first_name.slice(0, 1));
}

function renderResidents() {
  const section = $('residents-section');
  section.hidden = !home;
  if (!home) return;
  const manage = home.permissions.can_residents;
  const roomName = (id) => {
    const index = home.rooms.findIndex((r) => r.id === id);
    return index < 0 ? '' : `${home.rooms[index].emoji} ${home.rooms[index].name || t('home.room.titleN', { n: index + 1 })}`;
  };
  const rows = home.residents.map((person) => {
    const url = `/homes/${home.id}/residents/${person.user_id}`;
    const update = async (change) => { if (await homeAction(() => put(url, change))) saved(); renderResidents(); renderInvites(); };
    const rights = manage
      ? el('div', { class: 'rights' }, ...RIGHTS.map((name) => {
        const box = el('input', { type: 'checkbox' });
        box.checked = person.permissions[name];
        box.addEventListener('change', () => update({ [name]: box.checked }));
        return el('label', { class: 'check' }, box, el('span', {}, rightLabel(name)));
      }))
      : el('p', { class: 'hint' }, RIGHTS.filter((name) => person.permissions[name]).map(rightLabel).join(' · ') || t('home.rights.none'));
    let room = null;
    if (home.kind === 'apartment' && home.rooms.length > 1) {
      if (manage || person.is_you) {
        const picker = el('select', { 'aria-label': t('home.residents.room') }, ...home.rooms.map((r) => el('option', { value: r.id }, roomName(r.id))));
        picker.value = person.room_id ?? '';
        picker.addEventListener('change', () => update({ room_id: picker.value }));
        room = el('label', { class: 'field' }, el('span', {}, t('home.residents.room')), picker);
      } else {
        room = el('p', { class: 'hint' }, roomName(person.room_id));
      }
    }
    return el('li', { class: 'resident' },
      el('div', { class: 'row' }, avatar(person),
        el('div', {}, el('b', {}, `${person.first_name} ${person.last_name}`),
          person.is_you && el('span', { class: 'tag fill-yellow' }, t('home.residents.you')))),
      room, rights,
      manage && !person.is_you && el('div', {}, el('button', { class: 'linkbtn', type: 'button', onclick: async () => {
        if (!window.confirm(t('home.residents.removeConfirm', { name: person.first_name }))) return;
        await homeAction(() => del(url));
        render();
      } }, t('home.residents.remove'))));
  });
  section.replaceChildren(el('div', { class: 'box pad hblock' },
    el('h2', {}, t('home.residents.title')),
    el('p', { class: 'hint' }, manage ? t('home.residents.hintManage') : t('home.residents.hint')),
    el('ul', { class: 'residents' }, ...rows)));
}

// ── Invites ─────────────────────────────────────────────

let invites = null;     // active invites, loaded once the person may see them
let freshInvite = null; // the one just created: its link is shown once

async function loadInvites() {
  invites = null;
  if (home?.permissions.can_invites) {
    try { invites = await get(`/homes/${home.id}/invites`); } catch (err) { reportBug(err, { where: 'invites' }); invites = []; }
  }
}

function renderInvites() {
  const section = $('invites-section');
  section.hidden = !home;
  if (!home) return;
  if (!home.permissions.can_invites) {
    section.replaceChildren(el('div', { class: 'box pad hblock' },
      el('h2', {}, t('home.invites.title')), el('p', { class: 'hint' }, t('home.invites.noRight'))));
    return;
  }
  if (invites === null) { loadInvites().then(renderInvites); return; }
  const date = (iso) => new Date(iso).toLocaleDateString(currentLang() === 'zh' ? 'zh-CN' : currentLang(), { day: 'numeric', month: 'long' });

  let roomPicker = null;
  if (home.kind === 'apartment' && home.rooms.length > 1) {
    roomPicker = el('select', {}, ...home.rooms.map((r, i) => el('option', { value: r.id }, `${r.emoji} ${r.name || t('home.room.titleN', { n: i + 1 })}`)));
  }
  const create = el('button', { class: 'btn', type: 'button', onclick: async () => {
    setBusy(create, true);
    try {
      freshInvite = await post(`/homes/${home.id}/invites`, { room_id: roomPicker?.value ?? null });
      await loadInvites();
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      toast(t('error.title'), errorText(err), { error: true });
    }
    renderInvites();
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
        try { await del(`/homes/${home.id}/invites/${inv.id}`); } catch (err) { if (!(err instanceof ApiError)) throw err; }
        if (freshInvite?.id === inv.id) freshInvite = null;
        await loadInvites();
        renderInvites();
      } }, t('home.invites.revoke'))))))
    : el('p', { class: 'hint' }, t('home.invites.empty'));

  section.replaceChildren(el('div', { class: 'box pad hblock' },
    el('h2', {}, t('home.invites.title')),
    el('p', { class: 'hint' }, t('home.invites.hint')),
    roomPicker && el('label', { class: 'field' }, el('span', {}, t('home.invites.room')), roomPicker),
    el('div', {}, create),
    fresh, list));
}

function renderDanger() {
  $('danger').hidden = !home;
  if (!home) return;
  $('danger').replaceChildren(el('div', { class: 'box pad hblock' },
    el('h2', {}, t('home.leave.heading')),
    el('p', { class: 'hint' }, t('home.leave.hint'), ' ',
      el('a', { href: '#free-0', onclick: (e) => {
        e.preventDefault();
        const target = $('free-0');
        // Focus first: focusing during a smooth scroll stops it in Chromium.
        target?.focus({ preventScroll: true });
        target?.scrollIntoView({ block: 'center', behavior: 'smooth' });
      } }, t('home.leave.setZero'))),
    el('div', {}, el('button', { class: 'btn secondary', type: 'button', onclick: () => $('leave-dialog').showModal() }, t('home.leave.button')))));
}

$('leave-cancel').addEventListener('click', () => $('leave-dialog').close());
$('leave-confirm').addEventListener('click', async () => {
  setBusy($('leave-confirm'), true);
  try {
    await del('/homes/mine/membership');
    location.reload();
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    setBusy($('leave-confirm'), false);
    $('leave-dialog').close();
    toast(t('error.title'), errorText(err), { error: true });
  }
});

// ── Render and save ─────────────────────────────────────

function render() {
  $('page-title').textContent = home ? t('home.title.edit') : t('home.title.new');
  $('page-lead').textContent = home ? t('home.lead.edit') : t('home.lead.new');
  renderStatus();

  const form = $('home-form');
  if (!state.kind) {
    form.replaceChildren(kindPicker());
  } else {
    const apartment = state.kind === 'apartment';
    // replaceChildren() would print a `false` from the `cond && el(...)` items as text.
    form.replaceChildren(...[
      apartment ? placeSection() : dormSection(),
      ...state.rooms.map(roomSection),
      apartment && canEdit && state.rooms.length < MAX_ROOMS && el('div', {},
        el('button', { class: 'btn secondary', type: 'button', onclick: async () => {
          const [emoji] = await rollEmoji();
          state.rooms.push(blankRoom(emoji ?? ''));
          render();
          changed(true);
        } }, `+ ${t('home.room.add')}`)),
      apartment && costsSection(),
      aboutSection(),
      !home && el('div', { class: 'qbar box' },
        el('button', { class: 'linkbtn', type: 'button', onclick: () => { state = stateFrom(null); errors = {}; takenRoomId = null; render(); } }, t('home.changeKind')),
        el('button', { class: 'btn', type: 'submit' }, t('home.publish'))),
    ].filter(Boolean));
  }
  // A new place needs a photo before it's listed, so the photos go above the button.
  const bar = form.querySelector('.qbar');
  if (bar) form.insertBefore(photosSection, bar); else form.after(photosSection);
  mountMap();
  renderPhotos();
  renderResidents();
  renderInvites();
  renderDanger();
}

const number = (value) => (value === '' || value == null ? null : Number(String(value).replace(/\s/g, '')));

function payload() {
  const apartment = state.kind === 'apartment';
  return {
    kind: state.kind,
    description: state.description,
    sunlight: state.sunlight || null,
    building: apartment ? null : state.building || null,
    room_label: apartment ? null : roomLabel(),
    district: apartment ? state.district : null,
    lat: state.area?.lat ?? null, lon: state.area?.lon ?? null, radius_m: state.area?.radius_m ?? null,
    utilities_mode: apartment ? state.utilities_mode || null : null,
    utilities_rub: apartment && state.utilities_mode === 'split' ? number(state.utilities_rub) : null,
    internet_mode: apartment ? state.internet_mode || null : null,
    rooms: state.rooms.map((r) => ({
      id: r.id ?? undefined, name: r.name, gender: r.gender || undefined, capacity: r.capacity, free_places: r.free_places,
      rent_rub: apartment ? number(r.rent_rub) : null, emoji: r.emoji,
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
  need('sunlight', state.sunlight);
  if (!home && !pendingPhotos.length) out.photos = 'PHOTO_REQUIRED';
  state.rooms.forEach((room, i) => {
    need(`rooms.${i}.gender`, room.gender);
    if (state.kind === 'apartment') need(`rooms.${i}.rent_rub`, String(room.rent_rub).trim());
    need(`rooms.${i}.emoji`, room.emoji.trim());
  });
  return out;
}

const FORM_ERROR = '#home-form .note.error, #photos-section .note.error';

function showErrors() {
  render();
  document.querySelector(FORM_ERROR)?.scrollIntoView({ block: 'center' });
}

// A new place: sent once, by the button.
$('home-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  if (home) { changed(true); return; } // Enter in a field
  const button = e.submitter;
  takenRoomId = null;
  errors = missing();
  if (Object.keys(errors).length) { showErrors(); return; }
  setBusy(button, true);
  try {
    home = await post('/homes', payload());
    state = stateFrom(home);
    savedKey = JSON.stringify(payload());
    place.step = state.area ? 'area' : 'search';
    place.point = null;
    render();
    toast(t('home.created'), t('home.createdText'));
    window.scrollTo(0, 0);
    if (pendingPhotos.length) {
      const queued = pendingPhotos;
      pendingPhotos = [];
      photosSection.setAttribute('aria-busy', 'true');
      await uploadPhotos(queued.map((p) => p.file));
      queued.forEach((p) => URL.revokeObjectURL(p.url));
      photosSection.removeAttribute('aria-busy');
      renderPhotos();
      renderStatus();
    }
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return; }
    errors = err.fields ?? {};
    if (err.code === 'ROOM_TAKEN') takenRoomId = err.data?.room_id ?? null;
    showErrors();
    if (!document.querySelector(FORM_ERROR)) toast(t('error.title'), errorText(err), { error: true });
  }
});

// ── Autosave (once the place is listed) ─────────────────

let savedKey = home ? JSON.stringify(payload()) : null; // the form as the server has it

/** Rebuild the form without losing the field being typed in. */
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
      return !room || state.rooms[room[1]].id;
    })));
    return;
  }
  try {
    home = await put(`/homes/${home.id}`, body);
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return; }
    setErrors(err.fields ?? {}, err.code === 'ROOM_TAKEN' ? err.data?.room_id ?? null : null);
    if (!document.querySelector(FORM_ERROR)) toast(t('error.title'), errorText(err), { error: true });
    return;
  }
  // Take over what only the server knows: the ids of new rooms (it keeps their order).
  // The rest of `state` stays as it is: the person may have typed on while this was sent.
  const added = body.rooms.some((room) => !room.id);
  state.rooms.forEach((room, i) => { if (i < body.rooms.length) room.id = home.rooms[i]?.id ?? room.id; });
  // The dorm room number is sent once and not shown again.
  const sentLabel = body.room_label;
  if (sentLabel && roomLabel() === sentLabel) { state.room_number = ''; state.room_letter = null; }
  savedKey = JSON.stringify({ ...body, room_label: null, rooms: body.rooms.map((room, i) => ({ ...room, id: home.rooms[i]?.id })) });
  if (added || sentLabel || Object.keys(errors).length || takenRoomId) {
    errors = {};
    takenRoomId = null;
    rerender();
  } else {
    renderStatus();
    renderResidents();
    renderInvites();
  }
  saved();
}

const saveSoon = autosaver(saveHome, 1200);

/** The form changed: save after a pause in typing, or at once (`now`) after a click or leaving a field. */
function changed(now = false) {
  if (!home || !canEdit) return;
  if (now) saveSoon.now(); else saveSoon();
}

render();
document.addEventListener('langchange', render);
void user;

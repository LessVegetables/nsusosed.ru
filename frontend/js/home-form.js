// The home form, shared by onboarding (/questionnaire) and /home: room or
// apartment details, places, description and any number of contacts. Also
// the photo editor. Pages put these pieces in their own <form> and read it
// back with readHomeForm().

import { api } from './api.js';
import { applyI18n } from './i18n.js';
import { busy, clearError, confirmDialog, h, showError, toast } from './ui.js';

const CONTACT_TYPES = ['telegram', 'whatsapp', 'max', 'phone', 'other'];
const MAX_CONTACTS = 10;
const MAX_PHOTOS = 10;
const VIEWS = ['forest', 'road', 'yard', 'other', 'unknown'];

// Field limits, the same as the backend's.
const LIMITS = {
  building: { maxLength: 20 },
  room_number: { min: 1, max: 999 },
  floor: { min: 1, max: 999 },
  windows_count: { min: 1, max: 5 },
  layout: { maxLength: 300 },
  district: { maxLength: 80 },
  monthly_cost_per_person_rub: { min: 1, max: 200000 },
  capacity: { min: 1, max: 10 },
  occupied_count: { min: 1, max: 10 },
  description: { maxLength: 1000 },
  contact_value: { maxLength: 100 },
};
const DORM_FIELDS = ['building', 'room_number', 'floor', 'is_corner', 'windows_count', 'view', 'layout'];
const APARTMENT_FIELDS = ['district', 'monthly_cost_per_person_rub'];
const NUMBER_FIELDS = ['room_number', 'floor', 'windows_count', 'monthly_cost_per_person_rub', 'capacity', 'occupied_count'];
const REQUIRED = {
  dorm: ['building', 'room_number', 'floor'],
  apartment: ['district', 'monthly_cost_per_person_rub'],
  both: ['capacity', 'occupied_count'],
};

function field(name, { type = 'text', label, hint, required = false, options, value, path = name }) {
  const id = `f-${name}`;
  const hintId = hint ? `${id}-hint` : null;
  const limits = LIMITS[name] || {};
  const common = { id, name, required, 'aria-describedby': hintId };
  let input;
  if (type === 'select') {
    input = h('select', common, options.map((o) => h('option', { value: o.value, i18n: o.key, selected: String(value ?? '') === o.value })));
  } else if (type === 'textarea') {
    input = h('textarea', { ...common, rows: '4', maxlength: limits.maxLength });
    input.value = value ?? '';
  } else {
    input = h('input', {
      ...common,
      type,
      inputmode: type === 'number' ? 'numeric' : null,
      min: limits.min,
      max: limits.max,
      step: type === 'number' ? '1' : null,
      maxlength: limits.maxLength,
      value: value ?? null,
    });
  }
  return h(
    'div',
    { class: 'field', 'data-field': path },
    h('label', { for: id }, h('span', { i18n: label }), required ? h('span', { class: 'req', 'aria-hidden': 'true' }, ' *') : null),
    input,
    hint ? h('p', { id: hintId, class: 'hint', i18n: hint }) : null,
  );
}

// ---------------------------------------------------------------- details

// Kind (only when creating), room or apartment fields, places, description.
// The returned box tracks the chosen kind in its data-home-kind attribute.
export function homeDetails({ values = {}, chooseKind = false } = {}) {
  const kind = values.kind || 'dorm';

  const kindChooser = chooseKind
    ? h(
        'fieldset',
        { class: 'choices choices-inline', 'data-field': 'kind' },
        h('legend', { i18n: 'myHome.kind' }),
        ['dorm', 'apartment'].map((k) =>
          h('div', { class: 'choice' },
            h('input', { type: 'radio', id: `kind-${k}`, name: 'kind', value: k, checked: k === kind }),
            h('label', { for: `kind-${k}`, i18n: `kind.${k}` })),
        ),
      )
    : null;

  const dormBox = h(
    'fieldset',
    { class: 'stack', 'data-kind': 'dorm' },
    h('legend', { i18n: 'myHome.room' }),
    h('div', { class: 'grid-3' },
      field('building', { label: 'listing.building', required: true, value: values.building, hint: 'myHome.buildingHint' }),
      field('room_number', { type: 'number', label: 'listing.room', required: true, value: values.room_number }),
      field('floor', { type: 'number', label: 'listing.floor', required: true, value: values.floor })),
    h('div', { class: 'grid-3' },
      field('is_corner', {
        type: 'select', label: 'listing.corner', value: values.is_corner == null ? '' : String(values.is_corner),
        options: [{ value: '', key: 'common.notSpecified' }, { value: 'true', key: 'common.yes' }, { value: 'false', key: 'common.no' }],
      }),
      field('windows_count', { type: 'number', label: 'listing.windows', value: values.windows_count }),
      field('view', {
        type: 'select', label: 'listing.view', value: values.view ?? '',
        options: [{ value: '', key: 'common.notSpecified' }, ...VIEWS.map((v) => ({ value: v, key: `view.${v}` }))],
      })),
    field('layout', { label: 'listing.layout', value: values.layout, hint: 'myHome.layoutHint' }),
  );

  const apartmentBox = h(
    'fieldset',
    { class: 'stack', 'data-kind': 'apartment' },
    h('legend', { i18n: 'myHome.apartment' }),
    field('district', { label: 'listing.district', required: true, value: values.district, hint: 'myHome.districtHint' }),
    field('monthly_cost_per_person_rub', { type: 'number', label: 'listing.cost', required: true, value: values.monthly_cost_per_person_rub }),
  );

  const description = field('description', { type: 'textarea', label: 'listing.description', value: values.description, hint: 'myHome.descriptionHint' });
  const counter = h('p', { class: 'hint counter', 'aria-hidden': 'true' });
  description.append(counter);
  const textarea = description.querySelector('textarea');
  const updateCounter = () => {
    counter.textContent = `${textarea.value.length} / ${LIMITS.description.maxLength}`;
  };
  textarea.addEventListener('input', updateCounter);
  updateCounter();

  const box = h(
    'div',
    { class: 'stack' },
    kindChooser,
    dormBox,
    apartmentBox,
    h(
      'fieldset',
      { class: 'stack' },
      h('legend', { i18n: 'myHome.places' }),
      h('div', { class: 'grid-2' },
        field('capacity', { type: 'number', label: 'myHome.capacity', required: true, value: values.capacity, hint: 'myHome.capacityHint' }),
        field('occupied_count', { type: 'number', label: 'myHome.occupied', required: true, value: values.occupied_count, hint: 'myHome.occupiedHint' })),
    ),
    description,
  );

  const showKind = (k) => {
    dormBox.hidden = k !== 'dorm';
    apartmentBox.hidden = k !== 'apartment';
    box.dataset.homeKind = k;
  };
  showKind(kind);
  for (const radio of box.querySelectorAll('input[name="kind"]')) {
    radio.addEventListener('change', () => showKind(radio.value));
  }
  return box;
}

// ---------------------------------------------------------------- contacts

// "<method>: <value>  ✕" rows with an "Add contact method" button below.
export function contactsEditor(contacts = []) {
  const rows = h('ol', { class: 'contact-rows' });
  const addButton = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'myHome.addContact' });

  const renumber = () => {
    [...rows.children].forEach((row, i) => {
      row.dataset.field = `contacts.${i}`;
      row.querySelector('[data-part="type"]').dataset.field = `contacts.${i}.type`;
      row.querySelector('[data-part="value"]').dataset.field = `contacts.${i}.value`;
      row.querySelector('.contact-remove').hidden = rows.children.length === 1;
    });
    addButton.hidden = rows.children.length >= MAX_CONTACTS;
  };

  const addRow = (contact = { type: 'telegram', value: '' }, focus = false) => {
    const select = h('select', { 'data-i18n-attr': 'aria-label:myHome.contactType', 'data-role': 'type' },
      CONTACT_TYPES.map((c) => h('option', { value: c, i18n: `contact.${c}`, selected: c === contact.type })));
    const input = h('input', {
      type: 'text', autocomplete: 'off', maxlength: LIMITS.contact_value.maxLength, value: contact.value || null,
      'data-role': 'value',
    });
    const row = h('li', { class: 'contact-row' },
      h('div', { class: 'field', 'data-part': 'type' }, select),
      h('div', { class: 'field', 'data-part': 'value' }, input),
      h('button', {
        type: 'button', class: 'btn btn-secondary btn-small contact-remove',
        'data-i18n-attr': 'aria-label:myHome.removeContact', text: '✕',
      }));
    const setPlaceholder = () => {
      input.dataset.i18nAttr = `aria-label:myHome.contactValue; placeholder:contact.placeholder.${select.value}`;
      input.inputMode = select.value === 'phone' || select.value === 'whatsapp' ? 'tel' : 'text';
      applyI18n(row);
    };
    select.addEventListener('change', setPlaceholder);
    row.querySelector('.contact-remove').addEventListener('click', () => {
      row.remove();
      renumber();
      rows.querySelector('input')?.focus();
    });
    rows.append(row);
    setPlaceholder();
    renumber();
    if (focus) input.focus();
  };

  for (const c of contacts.length ? contacts : [{ type: 'telegram', value: '' }]) addRow(c);
  addButton.addEventListener('click', () => addRow(undefined, true));

  return h(
    'fieldset',
    { class: 'stack', 'data-field': 'contacts' },
    h('legend', { i18n: 'myHome.contacts' }),
    h('p', { class: 'hint', i18n: 'myHome.contactsNote' }),
    rows,
    h('div', { class: 'actions' }, addButton),
  );
}

// Contacts as the API shows them on a home (Telegram with @).
export function contactText(c) {
  return c.type === 'telegram' ? `@${c.value}` : c.value;
}

// ---------------------------------------------------------------- reading

// Read a form holding homeDetails() and/or contactsEditor() into an API
// payload. Returns {payload} or {errors: {path: REASON}}.
export function readHomeForm(form, { details = true, contacts = true } = {}) {
  const errors = {};
  const payload = {};

  if (details) {
    const kind = form.querySelector('[data-home-kind]').dataset.homeKind;
    payload.kind = kind;
    const get = (name) => form.elements[name]?.value.trim() ?? '';
    const names = [...(kind === 'dorm' ? DORM_FIELDS : APARTMENT_FIELDS), 'capacity', 'occupied_count', 'description'];
    for (const name of names) {
      const raw = get(name);
      if (raw === '') {
        if ([...REQUIRED[kind], ...REQUIRED.both].includes(name)) errors[name] = 'REQUIRED';
        payload[name] = null;
        continue;
      }
      if (name === 'is_corner') payload[name] = raw === 'true';
      else if (NUMBER_FIELDS.includes(name)) {
        const n = Number(raw);
        const { min, max } = LIMITS[name];
        if (!Number.isInteger(n)) errors[name] = 'INT_PARSING';
        else if (n < min) errors[name] = 'GREATER_THAN_EQUAL';
        else if (n > max) errors[name] = 'LESS_THAN_EQUAL';
        payload[name] = n;
      } else payload[name] = raw;
    }
    if (!errors.capacity && !errors.occupied_count && payload.occupied_count > payload.capacity) {
      errors.occupied_count = 'EXCEEDS_CAPACITY';
    }
  }

  if (contacts) {
    payload.contacts = [];
    form.querySelectorAll('.contact-row').forEach((row, i) => {
      const value = row.querySelector('[data-role="value"]').value.trim();
      if (!value) errors[`contacts.${i}.value`] = 'REQUIRED';
      payload.contacts.push({ type: row.querySelector('[data-role="type"]').value, value });
    });
  }
  return Object.keys(errors).length ? { errors } : { payload };
}

// Full PUT payload from a home as stored, with some fields changed.
export function payloadFrom(l, overrides = {}) {
  const fields = l.kind === 'dorm' ? DORM_FIELDS : APARTMENT_FIELDS;
  const payload = {
    expected_version: l.version,
    capacity: l.capacity,
    occupied_count: l.occupied_count,
    description: l.description,
    contacts: l.contacts.map(({ type, value }) => ({ type, value })),
    status: l.status,
  };
  for (const f of fields) payload[f] = l[f];
  return { ...payload, ...overrides };
}

// Invite link with Copy and, where the browser can, Share.
export function inviteLink(invite) {
  const input = h('input', { id: 'invite-url', type: 'text', readonly: true, value: invite.invite_url, class: 'input-mono' });
  input.addEventListener('focus', () => input.select());
  const copy = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.copy' });
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(invite.invite_url);
      toast('common.copied');
    } catch {
      input.select();
      toast('common.copyFailed');
    }
  });
  const share = navigator.share
    ? h('button', {
        type: 'button', class: 'btn btn-secondary', i18n: 'common.share',
        onclick: () => navigator.share({ url: invite.invite_url }).catch(() => {}),
      })
    : null;
  return h('div', { class: 'field' },
    h('label', { for: 'invite-url', i18n: 'myHome.inviteLabel' }),
    h('div', { class: 'input-row' }, input, copy, share),
    h('p', { class: 'hint', i18n: 'myHome.inviteExpires', i18nArgs: { date: { date: invite.expires_at } } }));
}

// ---------------------------------------------------------------- photos

// Grid of a home's photos. Admins can add, delete and make one the cover;
// onChange(home) gets the updated home after each change.
export function photosEditor(home, { editable, onChange }) {
  const box = h('div', { class: 'stack' });
  const error = h('div', { hidden: true });

  const run = async (button, action) => {
    clearError(error);
    const done = busy(button);
    try {
      onChange(await action());
    } catch (err) {
      done();
      showError(error, err);
    }
  };

  const grid = h('ul', { class: 'photo-grid' }, home.photos.map((p, i) =>
    h('li', { class: 'photo' },
      h('a', { href: p.url, target: '_blank', rel: 'noopener' },
        h('img', { src: p.url, alt: '', loading: 'lazy', width: p.width, height: p.height })),
      i === 0 ? h('span', { class: 'badge photo-cover', i18n: 'myHome.cover' }) : null,
      editable
        ? h('div', { class: 'photo-actions' },
            i > 0
              ? h('button', {
                  type: 'button', class: 'btn btn-secondary btn-small', i18n: 'myHome.makeCover',
                  onclick: (e) => run(e.currentTarget, () =>
                    api.reorderPhotos(home.id, [p.id, ...home.photos.filter((x) => x.id !== p.id).map((x) => x.id)])),
                })
              : null,
            h('button', {
              type: 'button', class: 'btn btn-danger btn-small', i18n: 'common.delete',
              onclick: async (e) => {
                const button = e.currentTarget;
                if (await confirmDialog({ title: 'myHome.deletePhotoTitle', confirm: 'common.delete', danger: true })) {
                  run(button, () => api.deletePhoto(home.id, p.id));
                }
              },
            }))
        : null)));

  if (!home.photos.length) box.append(h('p', { class: 'muted', i18n: editable ? 'myHome.noPhotosAdmin' : 'myHome.noPhotos' }));
  else box.append(grid);

  if (editable && home.photos.length < MAX_PHOTOS) {
    const input = h('input', { type: 'file', accept: 'image/jpeg,image/png,image/webp', multiple: true, class: 'visually-hidden', id: `photo-input-${home.id}` });
    const label = h('label', { for: input.id, class: 'btn btn-secondary', i18n: 'myHome.addPhotos' });
    input.addEventListener('change', async () => {
      const files = [...input.files].slice(0, MAX_PHOTOS - home.photos.length);
      input.value = '';
      if (!files.length) return;
      clearError(error);
      label.classList.add('is-busy');
      label.setAttribute('aria-busy', 'true');
      let latest = null;
      try {
        for (const file of files) latest = await api.addPhoto(home.id, file);
        toast('myHome.photosAdded', { count: files.length });
      } catch (err) {
        showError(error, err);
      } finally {
        label.classList.remove('is-busy');
        label.removeAttribute('aria-busy');
      }
      if (latest) onChange(latest);
    });
    box.append(h('div', { class: 'actions' }, input, label), h('p', { class: 'hint', i18n: 'myHome.photosHint' }));
  }
  box.append(error);
  return box;
}

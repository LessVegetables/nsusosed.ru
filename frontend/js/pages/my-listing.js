// /my-listing — create, edit, pause/resume, confirm and delete the user's own
// listing; invite roommates and see who has joined.

import { api } from '../api.js';
import { applyI18n, bindText } from '../i18n.js';
import { initPage } from '../layout.js';
import { facts, listingTitle, residentsList } from '../listing-view.js';
import {
  busy, clearError, clearFieldErrors, confirmDialog, daysUntil, h, loadFailed, loading, showError, showFieldErrors, toast,
} from '../ui.js';

const CONTACT_TYPES = ['telegram', 'whatsapp', 'max', 'phone', 'other'];
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
  both: ['capacity', 'occupied_count', 'contact_value'],
};

await initPage({ auth: 'required' });

const content = document.getElementById('content');
let listing = null; // ListingOwner from the API, or null
let profile = null;

// ---------------------------------------------------------------- form

function field(name, { type = 'text', label, hint, required = false, options, value }) {
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
    { class: 'field', 'data-field': name },
    h('label', { for: id }, h('span', { i18n: label }), required ? h('span', { class: 'req', 'aria-hidden': 'true' }, ' *') : null),
    input,
    hint ? h('p', { id: hintId, class: 'hint', i18n: hint }) : null,
  );
}

function contactPlaceholder(type) {
  return `contact.placeholder.${type}`;
}

function listingForm({ mode, values = {} }) {
  const kind = values.kind || (profile?.situation === 'apartment_host' ? 'apartment' : 'dorm');
  const formError = h('div', { hidden: true });

  const kindChooser = mode === 'create'
    ? h(
        'fieldset',
        { class: 'choices choices-inline', 'data-field': 'kind' },
        h('legend', { i18n: 'myListing.kind' }),
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
    h('legend', { i18n: 'myListing.room' }),
    h('div', { class: 'grid-3' },
      field('building', { label: 'listing.building', required: true, value: values.building, hint: 'myListing.buildingHint' }),
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
    field('layout', { label: 'listing.layout', value: values.layout, hint: 'myListing.layoutHint' }),
  );

  const apartmentBox = h(
    'fieldset',
    { class: 'stack', 'data-kind': 'apartment' },
    h('legend', { i18n: 'myListing.apartment' }),
    field('district', { label: 'listing.district', required: true, value: values.district, hint: 'myListing.districtHint' }),
    field('monthly_cost_per_person_rub', { type: 'number', label: 'listing.cost', required: true, value: values.monthly_cost_per_person_rub }),
  );

  const description = field('description', { type: 'textarea', label: 'listing.description', value: values.description, hint: 'myListing.descriptionHint' });
  const counter = h('p', { class: 'hint counter', 'aria-hidden': 'true' });
  description.append(counter);
  const textarea = description.querySelector('textarea');
  const updateCounter = () => {
    counter.textContent = `${textarea.value.length} / ${LIMITS.description.maxLength}`;
  };
  textarea.addEventListener('input', updateCounter);
  updateCounter();

  const contactType = values.contact_type || 'telegram';
  const contactValue = field('contact_value', { label: 'myListing.contactValue', required: true, value: values.contact_value, hint: 'myListing.contactHint' });
  const contactInput = contactValue.querySelector('input');
  contactInput.setAttribute('autocomplete', 'off');
  const setPlaceholder = (type) => {
    contactInput.dataset.i18nAttr = `placeholder:${contactPlaceholder(type)}`;
    contactInput.inputMode = type === 'phone' || type === 'whatsapp' ? 'tel' : 'text';
    applyI18n(contactValue);
  };

  const contactTypeField = field('contact_type', {
    type: 'select', label: 'myListing.contactType', required: true, value: contactType,
    options: CONTACT_TYPES.map((c) => ({ value: c, key: `contact.${c}` })),
  });
  contactTypeField.querySelector('select').addEventListener('change', (e) => setPlaceholder(e.target.value));
  setPlaceholder(contactType);

  const form = h(
    'form',
    { class: 'stack card', novalidate: true },
    kindChooser,
    dormBox,
    apartmentBox,
    h(
      'fieldset',
      { class: 'stack' },
      h('legend', { i18n: 'myListing.places' }),
      h('div', { class: 'grid-2' },
        field('capacity', { type: 'number', label: 'myListing.capacity', required: true, value: values.capacity, hint: 'myListing.capacityHint' }),
        field('occupied_count', { type: 'number', label: 'myListing.occupied', required: true, value: values.occupied_count, hint: 'myListing.occupiedHint' })),
    ),
    description,
    h(
      'fieldset',
      { class: 'stack' },
      h('legend', { i18n: 'myListing.contact' }),
      h('p', { class: 'hint', i18n: 'myListing.contactNote' }),
      h('div', { class: 'grid-2' }, contactTypeField, contactValue),
    ),
    formError,
    h(
      'div',
      { class: 'actions' },
      h('button', { type: 'submit', class: 'btn', i18n: mode === 'create' ? 'myListing.create' : 'common.save' }),
      mode === 'edit' ? h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.cancel', onclick: () => renderOverview() }) : null,
    ),
  );

  const showKind = (k) => {
    dormBox.hidden = k !== 'dorm';
    apartmentBox.hidden = k !== 'apartment';
    form.dataset.kind = k;
  };
  showKind(kind);
  for (const radio of form.querySelectorAll('input[name="kind"]')) {
    radio.addEventListener('change', () => showKind(radio.value));
  }

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(form, formError, mode);
  });
  return form;
}

// Read the form into an API payload. Returns {payload} or {errors}.
function readForm(form) {
  const kind = form.dataset.kind;
  const get = (name) => form.elements[name]?.value.trim() ?? '';
  const errors = {};
  const payload = { kind };

  const names = [...(kind === 'dorm' ? DORM_FIELDS : APARTMENT_FIELDS), 'capacity', 'occupied_count', 'description', 'contact_type', 'contact_value'];
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
  return Object.keys(errors).length ? { errors } : { payload };
}

// Full payload for PUT from the listing as stored (pause/resume).
function payloadFrom(l, overrides = {}) {
  const fields = l.kind === 'dorm' ? DORM_FIELDS : APARTMENT_FIELDS;
  const payload = {
    expected_version: l.version,
    capacity: l.capacity,
    occupied_count: l.occupied_count,
    description: l.description,
    contact_type: l.contact_type,
    contact_value: l.contact_value,
    status: l.status,
  };
  for (const f of fields) payload[f] = l[f];
  return { ...payload, ...overrides };
}

async function submitForm(form, formError, mode) {
  clearError(formError);
  const { payload, errors } = readForm(form);
  if (errors) {
    showFieldErrors(form, errors);
    showError(formError, { code: 'VALIDATION_ERROR' });
    return;
  }
  clearFieldErrors(form);

  const done = busy(form.querySelector('[type="submit"]'));
  try {
    if (mode === 'create') {
      listing = await api.createListing({ ...payload, status: 'active' });
      toast('myListing.created');
    } else {
      delete payload.kind; // The type of a listing can't change.
      listing = await api.updateListing(listing.id, { ...payload, status: listing.status, expected_version: listing.version });
      toast('myListing.saved');
    }
    renderOverview();
    content.querySelector('h2')?.focus();
  } catch (err) {
    done();
    if (err.code === 'VERSION_CONFLICT') {
      // Someone joined or another tab saved. Keep the user's edits, take the
      // new version, and let them check and save again.
      try {
        const fresh = await api.getMyListing();
        if (fresh.item) listing = fresh.item;
      } catch {
        // Show the conflict message anyway.
      }
      formError.replaceChildren(h('p', { i18n: 'myListing.conflictEdit' }));
      formError.className = 'alert alert-error';
      formError.hidden = false;
      return;
    }
    if (err.code === 'VALIDATION_ERROR') showFieldErrors(form, err.fields);
    if (err.code === 'OCCUPANCY_CONFLICT') showFieldErrors(form, { occupied_count: 'OCCUPANCY_CONFLICT' });
    if (err.code === 'ROOM_TAKEN') showFieldErrors(form, { room_number: 'ROOM_TAKEN' });
    if (err.code === 'LISTING_EXISTS') {
      await load();
      return;
    }
    showError(formError, err);
    if (err.code === 'ALREADY_IN_ROOM') formError.append(h('p', {}, h('a', { href: '/account', i18n: 'nav.account' })));
    if (err.code === 'PROFILE_REQUIRED') formError.append(h('p', {}, h('a', { href: '/questionnaire?next=/my-listing', i18n: 'matches.fillIn' })));
  }
}

// ---------------------------------------------------------------- overview

// Run an action that needs expected_version. If the listing changed in the
// meantime (usually a roommate joined), reload it and try once more: these
// actions don't depend on the fields the user sees.
async function withFreshVersion(action) {
  try {
    return await action(listing);
  } catch (err) {
    if (err.code !== 'VERSION_CONFLICT') throw err;
    const fresh = await api.getMyListing();
    if (!fresh.item) throw err;
    listing = fresh.item;
    return action(listing);
  }
}

function statusBlock(l) {
  const days = daysUntil(l.expires_at);
  const box = h('div', { class: 'card status-card' });
  const error = h('div', { hidden: true });

  if (l.free_places <= 0) {
    box.append(
      h('p', {}, h('span', { class: 'badge', i18n: 'status.full' })),
      h('p', { i18n: 'myListing.fullText' }),
    );
    return box;
  }

  if (l.status === 'paused') {
    box.append(
      h('p', {}, h('span', { class: 'badge', i18n: 'status.paused' })),
      h('p', { i18n: 'myListing.pausedText' }),
    );
    return box;
  }

  const confirmButton = h('button', { type: 'button', class: 'btn', i18n: 'myListing.confirm' });
  confirmButton.addEventListener('click', async () => {
    const done = busy(confirmButton);
    try {
      listing = await withFreshVersion((cur) => api.confirmListing(cur.id, cur.version));
      toast('myListing.confirmed');
      renderOverview();
    } catch (err) {
      done();
      showError(error, err);
    }
  });

  if (days <= 0) {
    box.classList.add('status-hidden');
    box.append(
      h('p', {}, h('span', { class: 'badge badge-warn', i18n: 'status.expired' })),
      h('p', { i18n: 'myListing.expiredText', i18nArgs: { date: { date: l.expires_at } } }),
    );
  } else {
    box.append(
      h('p', {}, h('span', { class: 'badge badge-ok', i18n: 'status.active' })),
      h('p', { i18n: 'myListing.hiddenIn', i18nArgs: { count: days, date: { date: l.expires_at } } }),
    );
  }
  box.append(h('p', { class: 'hint', i18n: 'myListing.confirmHint' }), h('div', { class: 'actions' }, confirmButton), error);
  return box;
}

function inviteBlock(l) {
  const result = h('div', { 'data-private': true });
  const error = h('div', { hidden: true });
  const button = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'myListing.invite' });

  button.addEventListener('click', async () => {
    const done = busy(button);
    clearError(error);
    try {
      const invite = await withFreshVersion((cur) => api.createInvite(cur.id, cur.version));
      listing.version = invite.version;
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
      result.replaceChildren(
        h('div', { class: 'field' },
          h('label', { for: 'invite-url', i18n: 'myListing.inviteLabel' }),
          h('div', { class: 'input-row' }, input, copy),
          h('p', { class: 'hint', i18n: 'myListing.inviteExpires', i18nArgs: { date: { date: invite.expires_at } } })),
      );
      bindText(button, 'myListing.inviteNew');
      input.focus();
    } catch (err) {
      showError(error, err);
    } finally {
      done();
    }
  });

  return h(
    'div',
    { class: 'stack' },
    h('p', { class: 'hint', i18n: 'myListing.inviteHint' }),
    h('div', { class: 'actions' }, button),
    error,
    result,
  );
}

function renderOverview() {
  const l = listing;
  const actionError = h('div', { hidden: true });

  const editButton = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.edit' });
  editButton.addEventListener('click', () => {
    const form = listingForm({ mode: 'edit', values: l });
    content.replaceChildren(h('h2', { tabindex: '-1', i18n: 'myListing.editTitle' }), form);
    content.querySelector('h2').focus();
  });

  const paused = l.status === 'paused';
  const pauseButton = h('button', {
    type: 'button', class: 'btn btn-secondary', i18n: paused ? 'myListing.resume' : 'myListing.pause',
    disabled: paused && l.free_places <= 0,
  });
  pauseButton.addEventListener('click', async () => {
    const done = busy(pauseButton);
    clearError(actionError);
    try {
      listing = await withFreshVersion((cur) => api.updateListing(cur.id, payloadFrom(cur, { status: paused ? 'active' : 'paused' })));
      toast(paused ? 'myListing.resumed' : 'myListing.paused');
      renderOverview();
    } catch (err) {
      done();
      showError(actionError, err);
    }
  });

  const deleteButton = h('button', { type: 'button', class: 'btn btn-danger', i18n: 'common.delete' });
  deleteButton.addEventListener('click', async () => {
    const ok = await confirmDialog({ title: 'myListing.deleteTitle', body: 'myListing.deleteBody', confirm: 'common.delete', danger: true });
    if (!ok) return;
    const done = busy(deleteButton);
    clearError(actionError);
    try {
      await api.deleteListing(l.id);
      listing = null;
      toast('myListing.deleted');
      renderCreate();
    } catch (err) {
      done();
      showError(actionError, err);
    }
  });

  content.replaceChildren(
    h('div', { class: 'detail-head' },
      h('h2', { tabindex: '-1' }, listingTitle(l)),
      h('a', { href: `/listing?id=${encodeURIComponent(l.id)}`, i18n: 'myListing.preview' })),
    statusBlock(l),
    h('div', { class: 'actions' }, editButton, pauseButton, deleteButton),
    actionError,
    h(
      'section',
      { class: 'card', 'aria-labelledby': 'about-title' },
      h('h3', { id: 'about-title', i18n: 'detail.about' }),
      facts(l),
      l.description ? h('p', { class: 'description', 'data-private': true }, l.description) : null,
      h('p', {},
        h('span', { class: 'muted', i18n: 'myListing.yourContact' }), ' ',
        h('span', { i18n: `contact.${l.contact_type}` }), ': ',
        h('span', { 'data-private': true }, l.contact_type === 'telegram' ? `@${l.contact_value}` : l.contact_value)),
    ),
    h(
      'section',
      { class: 'card', 'aria-labelledby': 'residents-title' },
      h('h3', { id: 'residents-title', i18n: 'detail.residents' }),
      h('p', { class: 'muted', i18n: 'myListing.answered', i18nArgs: { answered: l.answered_count, count: l.occupied_count } }),
      residentsList(l.residents),
      inviteBlock(l),
    ),
  );
}

function renderCreate() {
  if (!profile) {
    content.replaceChildren(
      h('div', { class: 'empty card' },
        h('p', { i18n: 'myListing.needProfile' }),
        h('p', {}, h('a', { class: 'btn', href: '/questionnaire?next=/my-listing', i18n: 'matches.fillIn' }))),
    );
    return;
  }
  content.replaceChildren(
    h('p', { class: 'lead', i18n: 'myListing.intro' }),
    h('p', { class: 'muted', i18n: 'myListing.introResident' }),
    listingForm({ mode: 'create' }),
  );
}

async function load() {
  loading(content);
  try {
    const [mine, prof] = await Promise.all([api.getMyListing(), api.getProfile()]);
    listing = mine.item;
    profile = prof.profile;
    if (listing) renderOverview();
    else renderCreate();
  } catch (err) {
    loadFailed(content, err, load);
  }
}

await load();

// /home — the home the user lives in. Everyone who lives there sees it;
// admins can edit it, manage photos and contacts, confirm, pause or delete
// it, send invite links and make other residents admins.
// A host without a home can create one here.

import { api } from '../api.js';
import { bindText } from '../i18n.js';
import { initPage } from '../layout.js';
import {
  contactText, contactsEditor, homeDetails, inviteLink, payloadFrom, photosEditor, readHomeForm,
} from '../home-form.js';
import { facts, listingTitle } from '../listing-view.js';
import {
  busy, clearError, clearFieldErrors, confirmDialog, daysUntil, h, loadFailed, loading, showError, showFieldErrors, toast,
} from '../ui.js';

const { me } = await initPage({ auth: 'required' });

const content = document.getElementById('content');
let home = null; // ListingOwner from the API, or null

// Run an action that needs expected_version. If the home changed in the
// meantime (usually a roommate joined), reload it and try once more: these
// actions don't depend on the fields the user sees.
async function withFreshVersion(action) {
  try {
    return await action(home);
  } catch (err) {
    if (err.code !== 'VERSION_CONFLICT') throw err;
    const fresh = await api.getMyListing();
    if (!fresh.item) throw err;
    home = fresh.item;
    return action(home);
  }
}

// ---------------------------------------------------------------- form

function homeForm({ mode, values = {} }) {
  const formError = h('div', { hidden: true });
  const form = h(
    'form',
    { class: 'stack card', novalidate: true },
    homeDetails({ values, chooseKind: mode === 'create' }),
    contactsEditor(values.contacts),
    formError,
    h(
      'div',
      { class: 'actions' },
      h('button', { type: 'submit', class: 'btn', i18n: mode === 'create' ? 'myHome.create' : 'common.save' }),
      mode === 'edit' ? h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.cancel', onclick: () => renderOverview() }) : null,
    ),
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    submitForm(form, formError, mode);
  });
  return form;
}

async function submitForm(form, formError, mode) {
  clearError(formError);
  const { payload, errors } = readHomeForm(form);
  if (errors) {
    showFieldErrors(form, errors);
    showError(formError, { code: 'VALIDATION_ERROR' });
    return;
  }
  clearFieldErrors(form);

  const done = busy(form.querySelector('[type="submit"]'));
  try {
    if (mode === 'create') {
      home = await api.createListing({ ...payload, status: 'active' });
      toast('myHome.created');
    } else {
      delete payload.kind; // The type of a home can't change.
      home = await api.updateListing(home.id, { ...payload, status: home.status, expected_version: home.version });
      toast('myHome.saved');
    }
    renderOverview();
    content.querySelector('h2')?.focus();
  } catch (err) {
    done();
    if (err.code === 'VERSION_CONFLICT') {
      // Someone joined or another admin saved. Keep the user's edits, take
      // the new version, and let them check and save again.
      try {
        const fresh = await api.getMyListing();
        if (fresh.item) home = fresh.item;
      } catch {
        // Show the conflict message anyway.
      }
      formError.replaceChildren(h('p', { i18n: 'myHome.conflictEdit' }));
      formError.className = 'alert alert-error';
      formError.hidden = false;
      return;
    }
    if (err.code === 'VALIDATION_ERROR') showFieldErrors(form, err.fields);
    if (err.code === 'OCCUPANCY_CONFLICT') showFieldErrors(form, { occupied_count: 'OCCUPANCY_CONFLICT' });
    if (err.code === 'ROOM_TAKEN') showFieldErrors(form, { room_number: 'ROOM_TAKEN' });
    showError(formError, err);
    if (err.code === 'PROFILE_REQUIRED') formError.append(h('p', {}, h('a', { href: '/questionnaire?next=/home', i18n: 'matches.fillIn' })));
  }
}

// ---------------------------------------------------------------- overview

function statusBlock(l) {
  const days = daysUntil(l.expires_at);
  const box = h('div', { class: 'card status-card' });
  const error = h('div', { hidden: true });

  if (l.free_places <= 0) {
    box.append(h('p', {}, h('span', { class: 'badge', i18n: 'status.full' })), h('p', { i18n: 'myHome.fullText' }));
    return box;
  }
  if (l.status === 'paused') {
    box.append(h('p', {}, h('span', { class: 'badge', i18n: 'status.paused' })), h('p', { i18n: 'myHome.pausedText' }));
    return box;
  }

  if (days <= 0) {
    box.classList.add('status-hidden');
    box.append(
      h('p', {}, h('span', { class: 'badge badge-warn', i18n: 'status.expired' })),
      h('p', { i18n: 'myHome.expiredText', i18nArgs: { date: { date: l.expires_at } } }),
    );
  } else {
    box.append(
      h('p', {}, h('span', { class: 'badge badge-ok', i18n: 'status.active' })),
      h('p', { i18n: 'myHome.hiddenIn', i18nArgs: { count: days, date: { date: l.expires_at } } }),
    );
  }
  if (l.you_are_admin) {
    const confirmButton = h('button', { type: 'button', class: 'btn', i18n: 'myHome.confirm' });
    confirmButton.addEventListener('click', async () => {
      const done = busy(confirmButton);
      try {
        home = await withFreshVersion((cur) => api.confirmListing(cur.id, cur.version));
        toast('myHome.confirmed');
        renderOverview();
      } catch (err) {
        done();
        showError(error, err);
      }
    });
    box.append(h('p', { class: 'hint', i18n: 'myHome.confirmHint' }), h('div', { class: 'actions' }, confirmButton), error);
  }
  return box;
}

function inviteBlock() {
  const result = h('div', { 'data-private': true });
  const error = h('div', { hidden: true });
  const button = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'myHome.invite' });
  button.addEventListener('click', async () => {
    const done = busy(button);
    clearError(error);
    try {
      const invite = await withFreshVersion((cur) => api.createInvite(cur.id, cur.version));
      home.version = invite.version;
      result.replaceChildren(inviteLink(invite));
      bindText(button, 'myHome.inviteNew');
      result.querySelector('input').focus();
    } catch (err) {
      showError(error, err);
    } finally {
      done();
    }
  });
  return h('div', { class: 'stack' }, h('p', { class: 'hint', i18n: 'myHome.inviteHint' }), h('div', { class: 'actions' }, button), error, result);
}

// One resident with their badges and, for admins, what can be done to them.
function residentRow(r, error) {
  const isMe = r.user_id === me.id;
  const action = (key, run, { danger = false, confirm } = {}) =>
    h('button', {
      type: 'button', class: `btn btn-small ${danger ? 'btn-danger' : 'btn-secondary'}`, i18n: key,
      onclick: async (e) => {
        const button = e.currentTarget;
        if (confirm && !(await confirmDialog({ ...confirm, danger }))) return;
        clearError(error);
        const done = busy(button);
        try {
          await run();
          await reload();
        } catch (err) {
          done();
          showError(error, err);
        }
      },
    });

  const actions = [];
  if (home.you_are_admin && !isMe) {
    if (r.is_admin) actions.push(action('myHome.removeAdmin', () => api.removeAdmin(home.id, r.user_id)));
    else if (r.profile_complete) actions.push(action('myHome.makeAdmin', () => api.makeAdmin(home.id, r.user_id)));
    actions.push(action('myHome.removeResident', () => api.removeResident(home.id, r.user_id), {
      danger: true,
      confirm: { title: 'myHome.removeResidentTitle', body: 'myHome.removeResidentBody', confirm: 'myHome.removeResident' },
    }));
  }
  return h(
    'li',
    { class: 'resident' },
    h('span', { class: 'resident-name' }, r.display_name, isMe ? h('span', { class: 'muted', i18n: 'myHome.you' }) : null),
    r.is_admin ? h('span', { class: 'badge badge-admin', i18n: 'residents.admin' }) : null,
    h('span', { class: r.profile_complete ? 'badge badge-ok' : 'badge', i18n: r.profile_complete ? 'residents.answered' : 'residents.notAnswered' }),
    actions.length ? h('span', { class: 'resident-actions' }, actions) : null,
  );
}

function residentsSection(l) {
  const error = h('div', { hidden: true });
  return h(
    'section',
    { class: 'card stack', 'aria-labelledby': 'residents-title' },
    h('h3', { id: 'residents-title', i18n: 'detail.residents' }),
    h('p', { class: 'muted', i18n: 'myHome.answered', i18nArgs: { answered: l.answered_count, count: l.occupied_count } }),
    h('ul', { class: 'residents', 'data-private': true }, l.residents.map((r) => residentRow(r, error))),
    error,
    l.you_are_admin ? h('p', { class: 'hint', i18n: 'myHome.adminsHint' }) : null,
    l.you_are_admin ? inviteBlock() : null,
  );
}

function leaveSection(l) {
  const error = h('div', { hidden: true });
  const button = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'myHome.leave' });
  const last = l.residents.length === 1;
  const lastAdmin = l.you_are_admin && l.residents.filter((r) => r.is_admin).length === 1;
  const body = last ? 'myHome.leaveLastBody' : lastAdmin ? 'myHome.leaveLastAdminBody' : 'myHome.leaveBody';
  button.addEventListener('click', async () => {
    if (!(await confirmDialog({ title: 'myHome.leaveTitle', body, confirm: 'myHome.leave', danger: last }))) return;
    const done = busy(button);
    try {
      await api.leaveRoom();
      location.assign('/questionnaire');
    } catch (err) {
      done();
      showError(error, err);
    }
  });
  return h('section', { class: 'card stack', 'aria-labelledby': 'leave-title' },
    h('h3', { id: 'leave-title', i18n: 'myHome.leaveTitle' }),
    h('p', { class: 'muted', i18n: 'myHome.leaveText' }),
    h('div', { class: 'actions' }, button),
    error);
}

function renderOverview() {
  const l = home;
  const actionError = h('div', { hidden: true });
  const admin = l.you_are_admin;

  let adminActions = null;
  if (admin) {
    const editButton = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.edit' });
    editButton.addEventListener('click', () => {
      content.replaceChildren(h('h2', { tabindex: '-1', i18n: 'myHome.editTitle' }), homeForm({ mode: 'edit', values: l }));
      content.querySelector('h2').focus();
    });

    const paused = l.status === 'paused';
    const pauseButton = h('button', {
      type: 'button', class: 'btn btn-secondary', i18n: paused ? 'myHome.resume' : 'myHome.pause',
      disabled: paused && l.free_places <= 0,
    });
    pauseButton.addEventListener('click', async () => {
      const done = busy(pauseButton);
      clearError(actionError);
      try {
        home = await withFreshVersion((cur) => api.updateListing(cur.id, payloadFrom(cur, { status: paused ? 'active' : 'paused' })));
        toast(paused ? 'myHome.resumed' : 'myHome.paused');
        renderOverview();
      } catch (err) {
        done();
        showError(actionError, err);
      }
    });

    const deleteButton = h('button', { type: 'button', class: 'btn btn-danger', i18n: 'common.delete' });
    deleteButton.addEventListener('click', async () => {
      const ok = await confirmDialog({ title: 'myHome.deleteTitle', body: 'myHome.deleteBody', confirm: 'common.delete', danger: true });
      if (!ok) return;
      const done = busy(deleteButton);
      clearError(actionError);
      try {
        await api.deleteListing(l.id);
        home = null;
        toast('myHome.deleted');
        renderCreate();
      } catch (err) {
        done();
        showError(actionError, err);
      }
    });
    adminActions = h('div', { class: 'actions' }, editButton, pauseButton, deleteButton);
  }

  const photos = h('div');
  const drawPhotos = () => photos.replaceChildren(photosEditor(home, {
    editable: admin,
    onChange: (updated) => {
      home = updated;
      drawPhotos();
    },
  }));
  drawPhotos();

  // replaceChildren() would turn a null into the text "null".
  content.replaceChildren(...[
    h('div', { class: 'detail-head' },
      h('h2', { tabindex: '-1' }, listingTitle(l)),
      h('a', { href: `/listing?id=${encodeURIComponent(l.id)}`, i18n: 'myHome.preview' })),
    admin ? null : h('p', { class: 'alert alert-info', i18n: 'myHome.notAdmin' }),
    statusBlock(l),
    adminActions,
    actionError,
    h('section', { class: 'card stack', 'aria-labelledby': 'photos-title' },
      h('h3', { id: 'photos-title', i18n: 'myHome.photos' }),
      photos),
    h(
      'section',
      { class: 'card', 'aria-labelledby': 'about-title' },
      h('h3', { id: 'about-title', i18n: 'detail.about' }),
      facts(l),
      l.description ? h('p', { class: 'description', 'data-private': true }, l.description) : null,
      h('h4', { i18n: 'myHome.contacts' }),
      h('ul', { class: 'contacts', 'data-private': true }, l.contacts.map((c) =>
        h('li', {}, h('span', { class: 'contact-type', i18n: `contact.${c.type}` }), ' ', contactText(c)))),
    ),
    residentsSection(l),
    leaveSection(l),
  ].filter(Boolean));
}

function renderCreate() {
  if (me.situation !== 'host') {
    content.replaceChildren(
      h('div', { class: 'empty card' },
        h('p', { i18n: 'myHome.seekerText' }),
        h('p', {}, h('a', { class: 'btn', href: '/questionnaire', i18n: 'myHome.changeRole' }))),
    );
    return;
  }
  content.replaceChildren(
    h('p', { class: 'lead', i18n: 'myHome.intro' }),
    h('p', { class: 'muted', i18n: 'myHome.introResident' }),
    homeForm({ mode: 'create' }),
  );
}

async function reload() {
  const mine = await api.getMyListing();
  home = mine.item;
  if (home) renderOverview();
  else renderCreate();
}

async function load() {
  loading(content);
  try {
    await reload();
  } catch (err) {
    loadFailed(content, err, load);
  }
}

await load();

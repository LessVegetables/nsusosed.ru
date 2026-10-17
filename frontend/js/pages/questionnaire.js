// /questionnaire — onboarding and the habits questionnaire.
//
// An unfinished account (no language, no role or an old questionnaire) gets a
// step-by-step flow, one screen per step:
//   language → "looking for a place" / "have a place" → one screen per
//   unanswered question → seekers: budget; hosts: the home, its contacts,
//   photos and "do you already have roommates?" (invite link).
// Steps that are already done are skipped, so a user who answered an older
// questionnaire only sees the new questions. Someone who came from an invite
// link (/join) is a host of that home and skips the role and home steps.
//
// A finished account sees everything on one page: role, habits, budget.

import { api } from '../api.js';
import { setLang } from '../i18n.js';
import { initPage, needsOnboarding, startPage } from '../layout.js';
import { contactsEditor, homeDetails, inviteLink, photosEditor, readHomeForm } from '../home-form.js';
import { session } from '../storage.js';
import {
  busy, clearError, clearFieldErrors, h, loadFailed, loading, safeNext, showError, showFieldErrors, toast,
} from '../ui.js';

const ROLES = ['seeker', 'host'];
const DEFAULT_IMPORTANCE = 5;
const BUDGET_MAX = 200000;
const INVITE_KEY = 'nsusosed.invite';

const params = new URLSearchParams(location.search);
const next = params.has('next') ? safeNext(params.get('next')) : null;

const { me } = await initPage({ auth: 'required', onboarding: true });

const content = document.getElementById('content');
const lead = document.querySelector('.lead');
let questionnaire = null; // {version, questions}
let profile = null; // as stored, or null
let version = 0; // profile.version; 0 = never saved

// ---------------------------------------------------------------- pieces

function radio(name, value, label, checked) {
  const id = `${name}-${value}`;
  return h(
    'div',
    { class: 'choice' },
    h('input', { type: 'radio', id, name, value: String(value), checked }),
    h('label', { for: id, localized: label }),
  );
}

function checkbox(name, value, label, checked) {
  const id = `${name}-${value}`;
  return h(
    'div',
    { class: 'choice' },
    h('input', { type: 'checkbox', id, name, value: String(value), checked }),
    h('label', { for: id, localized: label }),
  );
}

function questionBlock(question, number, answer, { isNew = false } = {}) {
  const key = question.key;
  const importance = answer?.importance ?? DEFAULT_IMPORTANCE;
  const hard = Boolean(answer?.hard);
  const allowed = new Set(answer?.allowed ?? []);
  const titleId = `q-${key}`;

  const output = h('output', { for: `imp-${key}`, class: 'range-value' }, String(importance));
  const range = h('input', {
    type: 'range', id: `imp-${key}`, name: `imp-${key}`, min: '1', max: '10', step: '1', value: String(importance),
    'aria-describedby': `imp-${key}-hint`,
  });
  range.addEventListener('input', () => {
    output.textContent = range.value;
  });

  const allowedBox = h(
    'div',
    { class: 'field', 'data-field': `answers.${key}.allowed`, id: `allowed-${key}`, hidden: !hard },
    h(
      'fieldset',
      { class: 'choices' },
      h('legend', { i18n: 'questionnaire.allowed' }),
      question.scale.map((opt) => checkbox(`allowed-${key}`, opt.value, opt.label, allowed.has(opt.value))),
    ),
  );

  const hardInput = h('input', {
    type: 'checkbox', id: `hard-${key}`, name: `hard-${key}`, checked: hard, 'aria-controls': `allowed-${key}`,
    'aria-expanded': String(hard),
  });

  const block = h(
    'section',
    { class: 'card question', 'aria-labelledby': titleId, 'data-field': `answers.${key}`, 'data-question': key },
    isNew ? h('p', {}, h('span', { class: 'badge badge-new', i18n: 'questionnaire.newQuestion' })) : null,
    h('h2', { id: titleId, class: 'question-title', tabindex: '-1' },
      number ? h('span', { class: 'question-number' }, `${number}. `) : null,
      h('span', { localized: question.label })),
    h(
      'div',
      { class: 'field', 'data-field': `answers.${key}.value` },
      h(
        'fieldset',
        { class: 'choices' },
        h('legend', { i18n: 'questionnaire.yourAnswer' }),
        question.scale.map((opt) => radio(`value-${key}`, opt.value, opt.label, answer?.value === opt.value)),
      ),
    ),
    h(
      'div',
      { class: 'field', 'data-field': `answers.${key}.importance` },
      h('label', { for: `imp-${key}`, i18n: 'questionnaire.importance' }),
      h('div', { class: 'range-row' }, range, output),
      h('p', { id: `imp-${key}-hint`, class: 'hint', i18n: 'questionnaire.importanceHint' }),
    ),
    h(
      'div',
      { class: 'field field-check', 'data-field': `answers.${key}.hard` },
      hardInput,
      h('label', { for: `hard-${key}`, i18n: 'questionnaire.hard' }),
    ),
    allowedBox,
  );

  hardInput.addEventListener('change', () => {
    allowedBox.hidden = !hardInput.checked;
    hardInput.setAttribute('aria-expanded', String(hardInput.checked));
    if (hardInput.checked) {
      // Start from the user's own answer: the usual case is "same as me".
      const own = block.querySelector(`input[name="value-${key}"]:checked`);
      const boxes = allowedBox.querySelectorAll('input');
      if (own && ![...boxes].some((b) => b.checked)) {
        allowedBox.querySelector(`input[value="${own.value}"]`).checked = true;
      }
    }
  });
  return block;
}

// Read one question block: [answer, errors].
function readQuestion(root, key) {
  const errors = {};
  const chosen = root.querySelector(`input[name="value-${key}"]:checked`);
  const hard = root.querySelector(`#hard-${key}`).checked;
  const allowed = hard
    ? [...root.querySelectorAll(`input[name="allowed-${key}"]:checked`)].map((b) => Number(b.value))
    : [];
  if (!chosen) errors[`answers.${key}.value`] = 'REQUIRED';
  if (hard && allowed.length === 0) errors[`answers.${key}.allowed`] = 'REQUIRED_WHEN_HARD';
  const answer = {
    value: chosen ? Number(chosen.value) : null,
    importance: Number(root.querySelector(`#imp-${key}`).value),
    hard,
    allowed,
  };
  return [answer, errors];
}

function roleChoices(current, { locked = false } = {}) {
  return h(
    'div',
    { class: 'field', 'data-field': 'situation' },
    h(
      'fieldset',
      { class: 'choices choices-big' },
      h('legend', { class: 'visually-hidden', i18n: 'questionnaire.roleTitle' }),
      ROLES.map((r) =>
        h(
          'div',
          { class: 'choice' },
          h('input', {
            type: 'radio', id: `role-${r}`, name: 'situation', value: r, checked: current === r,
            disabled: locked && r === 'seeker',
          }),
          h('label', { for: `role-${r}` },
            h('span', { class: 'choice-title', i18n: `role.${r}` }),
            h('span', { class: 'hint', i18n: `role.${r}.hint` })),
        ),
      ),
    ),
    locked ? h('p', { class: 'hint', i18n: 'questionnaire.roleLocked' }) : null,
  );
}

function budgetField(value) {
  return h(
    'div',
    { class: 'field', 'data-field': 'budget_max_rub' },
    h('label', { for: 'budget', i18n: 'questionnaire.budget' }),
    h('input', {
      type: 'number', id: 'budget', name: 'budget', inputmode: 'numeric', min: '1', max: String(BUDGET_MAX), step: '1',
      value: value ?? null, 'aria-describedby': 'budget-hint',
    }),
    h('p', { id: 'budget-hint', class: 'hint', i18n: 'questionnaire.budgetHint' }),
  );
}

// [budget or null, errors]
function readBudget(root) {
  const raw = root.querySelector('#budget').value.trim();
  if (raw === '') return [null, {}];
  const budget = Number(raw);
  if (!Number.isInteger(budget)) return [null, { budget_max_rub: 'INT_PARSING' }];
  if (budget < 1) return [null, { budget_max_rub: 'GREATER_THAN_EQUAL' }];
  if (budget > BUDGET_MAX) return [null, { budget_max_rub: 'LESS_THAN_EQUAL' }];
  return [budget, {}];
}

function profilePayload({ situation, answers, budget }) {
  return {
    questionnaire_version: questionnaire.version,
    expected_version: version,
    situation,
    budget_max_rub: situation === 'seeker' ? budget : null,
    answers,
  };
}

function fixErrors(box, count) {
  box.replaceChildren(h('p', { i18n: 'questionnaire.fixErrors', i18nArgs: { count } }));
  box.className = 'alert alert-error';
  box.hidden = false;
}

// ---------------------------------------------------------------- onboarding

const invited = Boolean(session.get(INVITE_KEY)) && next === '/join';
const STAY = Symbol('stay'); // onNext result: handled, don't move on

function wizardSteps() {
  const steps = [];
  if (!me.language) steps.push({ id: 'language' });
  if (!me.home && !invited && !profile?.situation) steps.push({ id: 'role' });
  for (const q of questionnaire.questions) {
    if (!profile?.answers?.[q.key]) steps.push({ id: 'question', question: q, isNew: Boolean(profile) });
  }
  steps.push({ id: 'budget', when: (s) => s.situation === 'seeker' && !(profile && profile.budget_max_rub != null) });
  steps.push({ id: 'save' }); // Not a screen: saves the questionnaire.
  if (!me.home && !invited) {
    steps.push({ id: 'home', when: (s) => s.situation === 'host' });
    steps.push({ id: 'contacts', when: (s) => s.situation === 'host' });
    steps.push({ id: 'photos', when: (s) => s.situation === 'host' });
    steps.push({ id: 'roommates', when: (s) => s.situation === 'host' });
  }
  return steps;
}

function startWizard() {
  lead.hidden = true;
  const state = {
    situation: me.home || invited ? 'host' : (profile?.situation ?? null),
    answers: { ...(profile?.answers ?? {}) },
    budget: profile?.budget_max_rub ?? null,
    homeDraft: {}, // details from the "home" step until the home is created
    home: null, // the created home
  };
  const steps = wizardSteps();
  const history = []; // indexes of the screens shown, for "Back"
  let index = 0;

  const active = () => steps.filter((s) => s.id !== 'save' && (!s.when || s.when(state)));
  const finish = () => location.assign(next || startPage({ ...me, situation: state.situation }));

  const go = async (to) => {
    while (to < steps.length && steps[to].when && !steps[to].when(state)) to += 1;
    if (to >= steps.length) return finish();
    if (steps[to].id === 'save') {
      await saveProfile(state);
      return go(to + 1);
    }
    index = to;
    render();
  };

  const saveProfile = async (s) => {
    const saved = await api.saveProfile(profilePayload(s));
    version = saved.version;
    profile = saved;
  };

  function frame(step, body, { onNext, nextKey = 'common.next', back = true, extra = null }) {
    const error = h('div', { hidden: true });
    const shown = active();
    const position = shown.indexOf(step) + 1;
    const nextButton = onNext ? h('button', { type: 'submit', class: 'btn', i18n: nextKey }) : null;
    const form = h(
      'form',
      { class: 'stack wizard', novalidate: true },
      h('p', { class: 'wizard-progress muted', i18n: 'questionnaire.step', i18nArgs: { step: position, count: shown.length } }),
      h('progress', { max: String(shown.length), value: String(position), 'aria-hidden': 'true' }),
      body,
      error,
      h('div', { class: 'actions wizard-actions' },
        back && history.length
          ? h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'common.back', onclick: () => {
              index = history.pop();
              render();
            } })
          : null,
        extra,
        nextButton),
    );
    form.errorBox = error;
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!onNext) return;
      clearError(error);
      clearFieldErrors(form);
      const done = busy(nextButton);
      try {
        const errors = await onNext(form);
        if (errors === STAY) return;
        if (errors && Object.keys(errors).length) {
          showFieldErrors(form, errors);
          fixErrors(error, Object.keys(errors).length);
          done();
          return;
        }
        history.push(index);
        await go(index + 1);
      } catch (err) {
        done();
        if (err.code === 'VALIDATION_ERROR') showFieldErrors(form, err.fields);
        if (err.code === 'ROOM_TAKEN') showFieldErrors(form, { room_number: 'ROOM_TAKEN' });
        showError(error, err);
      }
    });
    return form;
  }

  const screens = {
    language(step) {
      const choose = async (lang, button) => {
        const done = busy(button);
        try {
          await api.updateMe({ language: lang });
          setLang(lang);
          me.language = lang;
          history.push(index);
          await go(index + 1);
        } catch (err) {
          done();
          showError(content.querySelector('form').errorBox, err);
        }
      };
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.languageTitle' }),
        h('div', { class: 'lang-choices' },
          h('button', { type: 'button', class: 'btn btn-choice', lang: 'ru', onclick: (e) => choose('ru', e.currentTarget) }, 'Русский'),
          h('button', { type: 'button', class: 'btn btn-choice', lang: 'en', onclick: (e) => choose('en', e.currentTarget) }, 'English')),
        h('p', { class: 'hint', i18n: 'questionnaire.languageHint' })), {});
    },

    role(step) {
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.roleTitle' }),
        h('p', { class: 'muted', i18n: 'questionnaire.roleLead' }),
        roleChoices(state.situation)), {
        onNext: (form) => {
          const chosen = form.querySelector('input[name="situation"]:checked')?.value;
          if (!chosen) return { situation: 'REQUIRED' };
          state.situation = chosen;
          return null;
        },
      });
    },

    question(step) {
      const number = questionnaire.questions.indexOf(step.question) + 1;
      return frame(step, questionBlock(step.question, number, state.answers[step.question.key], { isNew: step.isNew }), {
        onNext: (form) => {
          const [answer, errors] = readQuestion(form, step.question.key);
          if (Object.keys(errors).length) return errors;
          state.answers[step.question.key] = answer;
          return null;
        },
      });
    },

    budget(step) {
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.budgetTitle' }),
        budgetField(state.budget)), {
        onNext: (form) => {
          const [budget, errors] = readBudget(form);
          if (Object.keys(errors).length) return errors;
          state.budget = budget;
          return null;
        },
      });
    },

    home(step) {
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.homeTitle' }),
        h('p', { class: 'muted', i18n: 'myHome.introResident' }),
        homeDetails({ values: state.homeDraft, chooseKind: true })), {
        onNext: (form) => {
          const { payload, errors } = readHomeForm(form, { contacts: false });
          if (errors) return errors;
          state.homeDraft = payload;
          return null;
        },
      });
    },

    contacts(step) {
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.contactsTitle' }),
        contactsEditor(state.homeDraft.contacts)), {
        nextKey: 'myHome.create',
        onNext: async (form) => {
          const { payload, errors } = readHomeForm(form, { details: false });
          if (errors) return errors;
          state.homeDraft.contacts = payload.contacts;
          try {
            state.home = await api.createListing({ ...state.homeDraft, status: 'active' });
          } catch (err) {
            // Errors in the details belong to the previous screen: show them there.
            const detailsError = err.code === 'ROOM_TAKEN'
              || (err.code === 'VALIDATION_ERROR' && Object.keys(err.fields).some((f) => !f.startsWith('contacts')));
            if (!detailsError) throw err;
            state.homeError = err;
            index = history.pop();
            render();
            return STAY;
          }
          toast('myHome.created');
          history.length = 0; // The home exists now: no going back to edit it here.
          return null;
        },
      });
    },

    photos(step) {
      const holder = h('div');
      const draw = () => holder.replaceChildren(photosEditor(state.home, {
        editable: true,
        onChange: (home) => {
          state.home = home;
          draw();
        },
      }));
      draw();
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.photosTitle' }),
        h('p', { class: 'muted', i18n: 'questionnaire.photosLead' }),
        holder), { back: false, onNext: () => null });
    },

    roommates(step) {
      const result = h('div', { 'data-private': true });
      const yes = h('button', { type: 'button', class: 'btn btn-secondary', i18n: 'questionnaire.roommatesYes' });
      yes.addEventListener('click', async () => {
        const done = busy(yes);
        try {
          const invite = await api.createInvite(state.home.id, state.home.version);
          state.home.version = invite.version;
          result.replaceChildren(inviteLink(invite));
          yes.remove();
        } catch (err) {
          done();
          showError(result, err);
        }
      });
      return frame(step, h('div', { class: 'stack' },
        h('h2', { tabindex: '-1', i18n: 'questionnaire.roommatesTitle' }),
        h('p', { class: 'muted', i18n: 'questionnaire.roommatesLead' }),
        h('div', { class: 'actions' }, yes),
        result), { back: false, nextKey: 'questionnaire.finish', onNext: () => null });
    },
  };

  function render() {
    const step = steps[index];
    const form = screens[step.id](step);
    content.replaceChildren(form);
    content.querySelector('h2')?.focus();
    if (step.id === 'home' && state.homeError) {
      const err = state.homeError;
      state.homeError = null;
      showFieldErrors(form, err.code === 'ROOM_TAKEN' ? { room_number: 'ROOM_TAKEN' } : err.fields);
      showError(form.errorBox, err);
    }
  }

  go(0).catch((err) => loadFailed(content, err, () => location.reload()));
}

// ---------------------------------------------------------------- editing

function renderEdit() {
  const formError = h('div', { hidden: true });
  const result = h('div', { hidden: true });
  const budget = budgetField(profile.budget_max_rub);
  const form = h(
    'form',
    { class: 'stack', novalidate: true },
    h('section', { class: 'card', 'aria-labelledby': 'role-title' },
      h('h2', { id: 'role-title', i18n: 'questionnaire.roleTitle' }),
      roleChoices(profile.situation, { locked: Boolean(me.home) }),
      budget),
    questionnaire.questions.map((q, i) => questionBlock(q, i + 1, profile.answers[q.key])),
    formError,
    h('div', { class: 'actions' }, h('button', { type: 'submit', class: 'btn', i18n: 'common.save' })),
    result,
  );
  const showBudget = () => {
    budget.hidden = form.querySelector('input[name="situation"]:checked')?.value !== 'seeker';
  };
  for (const r of form.querySelectorAll('input[name="situation"]')) r.addEventListener('change', showBudget);
  showBudget();

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearError(formError);
    result.hidden = true;
    const errors = {};
    const answers = {};
    for (const q of questionnaire.questions) {
      const [answer, errs] = readQuestion(form, q.key);
      answers[q.key] = answer;
      Object.assign(errors, errs);
    }
    const situation = form.querySelector('input[name="situation"]:checked')?.value;
    const [budgetValue, budgetErrors] = situation === 'seeker' ? readBudget(form) : [null, {}];
    Object.assign(errors, budgetErrors);
    if (Object.keys(errors).length) {
      showFieldErrors(form, errors);
      fixErrors(formError, Object.keys(errors).length);
      return;
    }
    clearFieldErrors(form);

    const done = busy(form.querySelector('[type="submit"]'));
    try {
      const saved = await api.saveProfile(profilePayload({ situation, answers, budget: budgetValue }));
      const roleChanged = saved.situation !== profile.situation;
      version = saved.version;
      profile = saved;
      if (next || roleChanged) {
        location.assign(next || startPage({ ...me, situation: saved.situation }));
        return;
      }
      toast('questionnaire.savedShort');
      result.replaceChildren(h('p', { i18n: 'questionnaire.saved' }));
      result.className = 'alert alert-success';
      result.hidden = false;
    } catch (err) {
      if (err.code === 'VERSION_CONFLICT') {
        // Another tab saved first: show what is stored now, then let the user retry.
        await load();
        const box = content.querySelector('form > div[hidden]');
        if (box) showError(box, err);
        return;
      }
      if (err.code === 'VALIDATION_ERROR') showFieldErrors(form, err.fields);
      showError(formError, err);
    } finally {
      done();
    }
  });
  content.replaceChildren(form);

  if (location.hash === '#budget') {
    const input = form.querySelector('#budget');
    input.scrollIntoView({ block: 'center' });
    input.focus();
  }
}

async function load() {
  loading(content);
  try {
    const [questions, prof] = await Promise.all([api.getQuestions(), api.getProfile()]);
    questionnaire = questions;
    profile = prof.profile;
    version = profile?.version ?? 0;
    if (needsOnboarding(me)) startWizard();
    else renderEdit();
  } catch (err) {
    loadFailed(content, err, load);
  }
}

await load();

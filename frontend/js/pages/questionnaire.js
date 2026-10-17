// /questionnaire — the 9 questions, importance, hard conditions, situation
// and budget. GET /api/questions + GET /api/profile, saved with PUT /api/profile.

import { api } from '../api.js';
import { initPage } from '../layout.js';
import {
  busy, clearError, clearFieldErrors, h, loadFailed, loading, safeNext, showError, showFieldErrors, toast,
} from '../ui.js';

const SITUATIONS = ['looking', 'dorm_resident', 'apartment_host'];
const DEFAULT_IMPORTANCE = 5;
const BUDGET_MAX = 200000;

const params = new URLSearchParams(location.search);
const next = params.has('next') ? safeNext(params.get('next')) : null;

await initPage({ auth: 'required' });

const content = document.getElementById('content');
let questionnaire = null; // {version, questions}
let version = 0; // profile.version; 0 = never saved
let formError = null; // error box under the form, replaced on every render

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

function questionBlock(question, index, answer) {
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
  hardInput.addEventListener('change', () => {
    allowedBox.hidden = !hardInput.checked;
    hardInput.setAttribute('aria-expanded', String(hardInput.checked));
    if (hardInput.checked) {
      // Start from the user's own answer: the usual case is "same as me".
      const own = content.querySelector(`input[name="value-${key}"]:checked`);
      const boxes = allowedBox.querySelectorAll('input');
      if (own && ![...boxes].some((b) => b.checked)) {
        allowedBox.querySelector(`input[value="${own.value}"]`).checked = true;
      }
    }
  });

  return h(
    'section',
    { class: 'card question', 'aria-labelledby': titleId, 'data-field': `answers.${key}` },
    h('h2', { id: titleId, class: 'question-title' },
      h('span', { class: 'question-number' }, `${index + 1}. `),
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
}

function situationBlock(profile) {
  return h(
    'section',
    { class: 'card', 'aria-labelledby': 'situation-title' },
    h('h2', { id: 'situation-title', i18n: 'questionnaire.situationTitle' }),
    h(
      'div',
      { class: 'field', 'data-field': 'situation' },
      h(
        'fieldset',
        { class: 'choices' },
        h('legend', { class: 'visually-hidden', i18n: 'questionnaire.situationTitle' }),
        SITUATIONS.map((s) =>
          h(
            'div',
            { class: 'choice' },
            h('input', { type: 'radio', id: `situation-${s}`, name: 'situation', value: s, checked: profile?.situation === s }),
            h('label', { for: `situation-${s}` },
              h('span', { i18n: `situation.${s}` }),
              h('span', { class: 'hint', i18n: `situation.${s}.hint` })),
          ),
        ),
      ),
    ),
    h(
      'div',
      { class: 'field', 'data-field': 'budget_max_rub' },
      h('label', { for: 'budget', i18n: 'questionnaire.budget' }),
      h('input', {
        type: 'number', id: 'budget', name: 'budget', inputmode: 'numeric', min: '1', max: String(BUDGET_MAX), step: '1',
        value: profile?.budget_max_rub ?? null, 'aria-describedby': 'budget-hint',
      }),
      h('p', { id: 'budget-hint', class: 'hint', i18n: 'questionnaire.budgetHint' }),
    ),
  );
}

function render(profile) {
  formError = h('div', { hidden: true });
  const result = h('div', { hidden: true });
  const form = h(
    'form',
    { class: 'stack', novalidate: true },
    questionnaire.questions.map((q, i) => questionBlock(q, i, profile?.answers?.[q.key])),
    situationBlock(profile),
    formError,
    h('div', { class: 'actions' }, h('button', { type: 'submit', class: 'btn', i18n: 'common.save' })),
    result,
  );
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    save(form, result);
  });
  content.replaceChildren(form);

  if (location.hash === '#budget') {
    const budget = form.querySelector('#budget');
    budget.scrollIntoView({ block: 'center' });
    budget.focus();
  }
}

// Read the form; returns {payload} or {errors: {path: REASON}}.
function readForm(form) {
  const errors = {};
  const answers = {};
  for (const q of questionnaire.questions) {
    const key = q.key;
    const chosen = form.querySelector(`input[name="value-${key}"]:checked`);
    const hard = form.querySelector(`#hard-${key}`).checked;
    const allowed = hard
      ? [...form.querySelectorAll(`input[name="allowed-${key}"]:checked`)].map((b) => Number(b.value))
      : [];
    if (!chosen) errors[`answers.${key}.value`] = 'REQUIRED';
    if (hard && allowed.length === 0) errors[`answers.${key}.allowed`] = 'REQUIRED_WHEN_HARD';
    answers[key] = {
      value: chosen ? Number(chosen.value) : null,
      importance: Number(form.querySelector(`#imp-${key}`).value),
      hard,
      allowed,
    };
  }

  const situation = form.querySelector('input[name="situation"]:checked')?.value;
  if (!situation) errors.situation = 'REQUIRED';

  const budgetRaw = form.querySelector('#budget').value.trim();
  let budget = null;
  if (budgetRaw !== '') {
    budget = Number(budgetRaw);
    if (!Number.isInteger(budget)) errors.budget_max_rub = 'INT_PARSING';
    else if (budget < 1) errors.budget_max_rub = 'GREATER_THAN_EQUAL';
    else if (budget > BUDGET_MAX) errors.budget_max_rub = 'LESS_THAN_EQUAL';
  }

  if (Object.keys(errors).length) return { errors };
  return {
    payload: {
      questionnaire_version: questionnaire.version,
      expected_version: version,
      situation,
      budget_max_rub: budget,
      answers,
    },
  };
}

function showSaved(result, situation) {
  result.replaceChildren(
    h('p', { i18n: 'questionnaire.saved' }),
    h(
      'p',
      { class: 'actions' },
      h('a', { class: 'btn', href: '/matches', i18n: 'questionnaire.toMatches' }),
      situation === 'looking' ? null : h('a', { class: 'btn btn-secondary', href: '/my-listing', i18n: 'questionnaire.toListing' }),
    ),
  );
  result.className = 'alert alert-success';
  result.hidden = false;
}

async function save(form, result) {
  clearError(formError);
  result.hidden = true;
  const { payload, errors } = readForm(form);
  if (errors) {
    showFieldErrors(form, errors);
    formError.replaceChildren(h('p', { i18n: 'questionnaire.fixErrors', i18nArgs: { count: Object.keys(errors).length } }));
    formError.className = 'alert alert-error';
    formError.hidden = false;
    return;
  }
  clearFieldErrors(form);

  const done = busy(form.querySelector('[type="submit"]'));
  try {
    const saved = await api.saveProfile(payload);
    version = saved.version;
    if (next) {
      location.assign(next);
      return;
    }
    toast('questionnaire.savedShort');
    showSaved(result, saved.situation);
  } catch (err) {
    if (err.code === 'VERSION_CONFLICT') {
      // Another tab saved first: show what is stored now, then let the user retry.
      await load();
      showError(formError, err);
      formError.scrollIntoView({ block: 'center' });
      return;
    }
    if (err.code === 'VALIDATION_ERROR') {
      const unmatched = showFieldErrors(form, err.fields);
      if (unmatched.length) console.warn('Field errors without a field on the page:', unmatched);
    }
    showError(formError, err);
  } finally {
    done();
  }
}

async function load() {
  loading(content);
  try {
    const [questions, { profile }] = await Promise.all([api.getQuestions(), api.getProfile()]);
    questionnaire = questions;
    version = profile?.version ?? 0;
    render(profile);
  } catch (err) {
    loadFailed(content, err, load);
  }
}

await load();

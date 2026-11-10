// The questionnaire: one page, small sections.
//
// First visit:  facts (gender, 18+, faculty) + the required questions → "Готово!" →
//               the four optional questions (or skip) → "what are you looking for?" → their page.
// Later visits: everything on one page, optional questions inside their blocks, one save button.
//
// Question texts come from the server in all three languages (GET /api/questionnaire), so a
// new questionnaire version needs no change here.

import { ApiError, get, put } from '../api.js';
import { currentLang, t } from '../i18n.js';
import { initPage } from '../layout.js';
import { homeFor } from '../routes.js';
import { el, errorText, setBusy, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);

let { user } = await initPage({ auth: 'required' });
const [quiz, meta] = await Promise.all([get('/questionnaire'), get('/meta')]);

const firstVisit = !quiz.complete;
const answers = { ...quiz.answers };
const about = {
  gender: user.gender,
  adult: user.is_adult == null ? null : user.is_adult ? 'yes' : 'no',
  faculty: user.faculty ?? '',
};
const byId = Object.fromEntries(quiz.questions.map((q) => [q.id, q]));
const tr = (texts) => texts[currentLang()] ?? texts.ru;

// ── Which questions are asked right now ─────────────────

function applies(q) {
  if (q.adult_only && about.adult !== 'yes') return false;
  if (q.show_if) {
    const chosen = [answers[q.show_if.question]].flat();
    return chosen.some((c) => q.show_if.any_of.includes(c));
  }
  return true;
}

const answered = (q) => answers[q.id] != null && (!Array.isArray(answers[q.id]) || answers[q.id].length > 0);
const requiredNow = () => quiz.questions.filter((q) => q.required && applies(q));

// ── Rendering ───────────────────────────────────────────

function pick(q, index) {
  if (q.type === 'multi') {
    const exclusive = q.exclusive ?? [];
    let chosen = answers[q.id] ?? [];
    if (chosen.includes(index)) chosen = chosen.filter((i) => i !== index);
    else if (exclusive.includes(index)) chosen = [index];
    else chosen = [...chosen.filter((i) => !exclusive.includes(i)), index];
    answers[q.id] = chosen;
  } else {
    answers[q.id] = index;
  }
  // An answer can switch a later question on or off (nicotine → dependence).
  for (const other of quiz.questions) if (!applies(other)) delete answers[other.id];
  refresh();
}

function questionNode(q) {
  const options = q.options.map((option, index) => el('button', {
    type: 'button', 'data-index': index, 'aria-pressed': 'false', onclick: () => pick(q, index),
  }, tr(option)));
  return el('fieldset', { id: `q-${q.id}`, 'data-question': q.id },
    el('legend', {}, tr(q.text),
      q.hidden && el('span', { class: 'tag', title: t('quiz.hidden.title') }, `🔒 ${t('quiz.hidden')}`),
      !q.required && firstVisit === false && el('span', { class: 'tag' }, t('quiz.optional'))),
    q.hint && el('p', { class: 'hint' }, tr(q.hint)),
    el('div', { class: 'opts', 'data-choice': q.type }, ...options),
    el('p', { class: 'note error', hidden: true }, `✕ ${t('quiz.unanswered')}`));
}

function blockNode(block, questions) {
  return el('section', { class: 'box pad qblock', 'aria-labelledby': `block-${block.id}` },
    el('h2', { id: `block-${block.id}` }, tr(block.title)),
    block.note && questions.some((q) => q.id === 'E1') && el('p', { class: 'note' }, tr(block.note)),
    ...questions.map(questionNode));
}

function render() {
  const inMain = (q) => !firstVisit || q.required;
  $('blocks').replaceChildren(...quiz.blocks
    .map((b) => [b, quiz.questions.filter((q) => q.block === b.id && inMain(q))])
    .filter(([, qs]) => qs.length)
    .map(([b, qs]) => blockNode(b, qs)));
  $('extra-blocks').replaceChildren(el('section', { class: 'box pad qblock' },
    ...quiz.questions.filter((q) => !q.required).map(questionNode)));
  $('faculty').replaceChildren(
    el('option', { value: '' }, t('account.faculty.none')),
    ...meta.faculties.map((f) => el('option', { value: f.id }, f[currentLang()] ?? f.ru)));
  $('faculty').value = about.faculty;
  refresh();
}

/** Bring the page in line with `answers` and `about` without rebuilding it. */
function refresh() {
  for (const node of document.querySelectorAll('[data-question]')) {
    const q = byId[node.dataset.question];
    node.hidden = !applies(q);
    const chosen = [answers[q.id]].flat();
    for (const button of node.querySelectorAll('.opts button')) {
      button.setAttribute('aria-pressed', String(chosen.includes(Number(button.dataset.index))));
    }
    if (answered(q)) node.querySelector('.note').hidden = true;
  }
  for (const [group, value] of [['gender', about.gender], ['adult', about.adult]]) {
    for (const button of $(group).querySelectorAll('button')) {
      button.setAttribute('aria-pressed', String(button.dataset.value === value));
    }
  }
  const required = requiredNow();
  const done = required.filter(answered).length;
  $('progress-text').textContent = t('quiz.progress', { done, total: required.length });
  $('progress').replaceChildren(...required.map((q) => el('i', { class: answered(q) ? 'done' : '' })));
}

for (const [group, key] of [['gender', 'gender'], ['adult', 'adult']]) {
  for (const button of $(group).querySelectorAll('button')) {
    button.addEventListener('click', () => {
      about[key] = button.dataset.value;
      $(`f-${group}`).querySelector('.note')?.remove();
      for (const q of quiz.questions) if (!applies(q)) delete answers[q.id];
      refresh();
    });
  }
}
$('faculty').addEventListener('change', () => {
  about.faculty = $('faculty').value;
  $('f-faculty').querySelector('.note')?.remove();
});

render();
document.addEventListener('langchange', render);

// ── Saving ──────────────────────────────────────────────

function complain(host) {
  if (!host.querySelector(':scope > .note')) host.append(el('p', { class: 'note error' }, `✕ ${t('quiz.unanswered')}`));
  return host;
}

/** Mark what's missing; returns the first such element, or null when everything is answered. */
function firstGap() {
  const gaps = [];
  if (!about.gender) gaps.push(complain($('f-gender')));
  if (!about.adult) gaps.push(complain($('f-adult')));
  if (!about.faculty) gaps.push(complain($('f-faculty')));
  for (const q of requiredNow()) {
    if (answered(q)) continue;
    const node = $(`q-${q.id}`);
    node.querySelector('.note').hidden = false;
    gaps.push(node);
  }
  return gaps[0] ?? null;
}

async function send(button, only) {
  setBusy(button, true);
  try {
    if (!only) {
      user = await put('/me', { gender: about.gender, is_adult: about.adult === 'yes', faculty: about.faculty });
    }
    const body = Object.fromEntries(Object.entries(answers).filter(([id]) => !only || only.includes(id)));
    const saved = await put('/questionnaire', { version: quiz.version, answers: body });
    quiz.complete = saved.complete;
    return true;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return false; }
    // A newer questionnaire was published while this page was open.
    if (err.code === 'QUESTIONNAIRE_OUTDATED') { location.reload(); return false; }
    toast(t('error.title'), errorText(err), { error: true });
    return false;
  } finally {
    setBusy(button, false);
  }
}

function show(id) {
  for (const panel of ['quiz', 'done', 'extra', 'intent']) $(panel).hidden = panel !== id;
  window.scrollTo(0, 0);
  $(id).querySelector('h1')?.setAttribute('tabindex', '-1');
  $(id).querySelector('h1')?.focus();
}

/** After the questionnaire: ask what they came for (once), then go to their page. */
function finish() {
  if (!user.intent) { show('intent'); return; }
  location.assign(homeFor({ ...user, questionnaire_complete: true }));
}

$('quiz').addEventListener('submit', async (e) => {
  e.preventDefault();
  const gap = firstGap();
  if (gap) {
    gap.scrollIntoView({ block: 'center' });
    (gap.querySelector('button, select') ?? gap).focus({ preventScroll: true });
    return;
  }
  if (!await send(e.submitter)) return;
  if (firstVisit) show('done'); else toast(t('account.saved'), '', { ms: 2500 });
});

$('more').addEventListener('click', () => show('extra'));
$('skip').addEventListener('click', finish);
$('extra-skip').addEventListener('click', finish);

$('extra').addEventListener('submit', async (e) => {
  e.preventDefault();
  const optional = quiz.questions.filter((q) => !q.required && answered(q)).map((q) => q.id);
  if (optional.length && !await send(e.submitter, optional)) return;
  finish();
});

for (const button of $('intent-opts').querySelectorAll('button')) {
  button.addEventListener('click', async () => {
    setBusy(button, true);
    try {
      user = await put('/me', { intent: button.dataset.value });
      location.assign(homeFor(user));
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      setBusy(button, false);
      toast(t('error.title'), errorText(err), { error: true });
    }
  });
}

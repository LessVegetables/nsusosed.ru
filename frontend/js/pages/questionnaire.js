// The questionnaire: one page, small sections.
//
// First visit:  facts (gender, 18+, faculty) + the required questions → "Готово!" →
//               the four optional questions (or skip) → "what are you looking for?" → their page.
// Later visits: everything on one page, optional questions inside their blocks, one save button.
//
// Question texts come from the server in all three languages (GET /api/questionnaire), so a
// new questionnaire version needs no change here.

import { ApiError, get, put } from '../api.js';
import { reportBug } from '../errors.js';
import { currentLang, t } from '../i18n.js';
import { initPage } from '../layout.js';
import { homeFor } from '../routes.js';
import { KEYS, session } from '../storage.js';
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

/** An 18+ question for someone who said they're under 18: shown grayed out, never asked. */
const underage = (q) => q.adult_only && about.adult === 'no';

function applies(q) {
  if (underage(q)) return false;
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
    q.adult_only && el('p', { class: 'note', 'data-underage': '', hidden: true }, `⚠ ${t('quiz.underage')}`),
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
    node.hidden = !applies(q) && !underage(q);
    node.disabled = underage(q);
    const chosen = [answers[q.id]].flat();
    for (const button of node.querySelectorAll('.opts button')) {
      button.setAttribute('aria-pressed', String(chosen.includes(Number(button.dataset.index))));
    }
    const notice = node.querySelector('[data-underage]');
    if (notice) notice.hidden = !underage(q);
    if (answered(q) || underage(q)) node.querySelector('.note.error').hidden = true;
  }
  for (const [group, value] of [['gender', about.gender], ['adult', about.adult]]) {
    for (const button of $(group).querySelectorAll('button')) {
      button.setAttribute('aria-pressed', String(button.dataset.value === value));
    }
  }
  const required = requiredNow();
  const done = required.filter(answered).length;
  $('progress-text').textContent = t('quiz.progress', { done, total: required.length });
  drawStrips();
}

// ── The question strip ──────────────────────────────────
// One cell per thing on the form, in page order: the three facts, then every question shown.
// Empty = no answer yet, purple = answered, gray = doesn't apply (18+ for someone under 18),
// red = required and still empty after a "Save" that was refused.

let triedToSave = false;

function stripCells() {
  const facts = [
    { node: $('f-gender'), done: !!about.gender },
    { node: $('f-adult'), done: !!about.adult },
    { node: $('f-faculty'), done: !!about.faculty },
  ].map(({ node, done }) => ({
    node, label: node.querySelector('legend, span').textContent, state: done ? 'done' : triedToSave ? 'missing' : '',
  }));
  const questions = [...$('blocks').querySelectorAll('[data-question]')].filter((node) => !node.hidden).map((node) => {
    const q = byId[node.dataset.question];
    let state = '';
    if (underage(q)) state = 'off';
    else if (answered(q)) state = 'done';
    else if (triedToSave && q.required) state = 'missing';
    return { node, label: tr(q.text), state };
  });
  return [...facts, ...questions];
}

function drawStrips() {
  const cells = stripCells();
  for (const strip of [$('strip-top'), $('strip-bottom')]) {
    strip.replaceChildren(...cells.map(({ node, label, state }) => el('button', {
      type: 'button', tabindex: '-1', title: label, 'data-state': state || null,
      onclick: () => node.scrollIntoView({ block: 'start' }),
    })));
  }
}

/** Questions scrolled to must clear the sticky header and strip: tell the CSS how tall they are. */
function trackStickyHeight() {
  const header = document.querySelector('.site-header');
  const root = document.documentElement.style;
  const set = () => {
    root.setProperty('--header-h', `${header.offsetHeight}px`);
    root.setProperty('--sticky-h', `${header.offsetHeight + $('strip-bar').offsetHeight}px`);
  };
  const watcher = new ResizeObserver(set);
  watcher.observe(header);
  watcher.observe($('strip-bar'));
}

/** Wide screens: the top strip steps aside while the save bar (which has its own strip) is in view. */
new IntersectionObserver(([entry]) => {
  $('strip-bar').toggleAttribute('data-away', entry.isIntersecting);
}).observe($('qbar'));
trackStickyHeight();

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
    node.querySelector('.note.error').hidden = false;
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
  $('strip-bar').hidden = id !== 'quiz';
  window.scrollTo(0, 0);
  $(id).querySelector('h1')?.setAttribute('tabindex', '-1');
  $(id).querySelector('h1')?.focus();
}

/** After the questionnaire: ask what they came for (once), then go to their page. */
async function finish() {
  // Someone who came by invite link doesn't need to be asked what they are here for.
  if (!user.intent && session.get(KEYS.invite)) {
    try { user = await put('/me', { intent: 'join' }); } catch (err) { reportBug(err, { where: 'intent' }); /* the join page works without it */ }
  }
  if (!user.intent) { show('intent'); return; }
  location.assign(homeFor({ ...user, questionnaire_complete: true }));
}

$('quiz').addEventListener('submit', async (e) => {
  e.preventDefault();
  const gap = firstGap();
  triedToSave = true;
  drawStrips();
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
      location.assign(homeFor({ ...user, questionnaire_complete: true }));
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      setBusy(button, false);
      toast(t('error.title'), errorText(err), { error: true });
    }
  });
}

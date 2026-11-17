// The questionnaire: one page, small sections.
//
// Facts (gender, 18+, faculty) and all the questions, optional ones included, on one page.
// Every answer is saved the moment it is given (a draft: the page can be left and come back
// to), quietly: no "Saved" pop-up here. There is no save button.
// First visit:  a "Done" button under the last block checks nothing required is missing, then
//               "what are you looking for?" → their page.
// Later visits: no button at all; a required question left empty is marked right away.
// At the top: "taking it together?" makes a link for a friend (/compare), before any answer.
// Someone who came by a friend's link isn't asked "what are you looking for?": they go back
// to the compare page.
//
// Question texts come from the server in all three languages (GET /api/questionnaire), so a
// new questionnaire version needs no change here.

import { ApiError, get, post, put } from '../api.js';
import { autosaver } from '../autosave.js';
import { reportBug } from '../errors.js';
import { renderFacultyPicker } from '../faculty.js';
import { currentLang, t } from '../i18n.js';
import { mountInviteField } from '../invite-field.js';
import { initPage } from '../layout.js';
import { homeFor } from '../routes.js';
import { KEYS, session } from '../storage.js';
import { el, errorText, setBusy, toast } from '../ui.js';

const $ = (id) => document.getElementById(id);

let { user } = await initPage({ auth: 'required' });
const [quiz, meta, compares] = await Promise.all([get('/questionnaire'), get('/meta'), get('/compare')]);

// Still on the way in: the questionnaire isn't complete, or "what are you looking for?" wasn't answered.
const onboarding = !quiz.complete || !user.intent;
const answers = { ...quiz.answers };
const about = {
  gender: user.gender,
  adult: user.is_adult == null ? null : user.is_adult ? 'yes' : 'no',
  faculty: user.faculty ?? '',
};
const byId = Object.fromEntries(quiz.questions.map((q) => [q.id, q]));
const groups = Object.fromEntries((quiz.groups ?? []).map((g) => [g.id, g]));
const tr = (texts) => texts[currentLang()] ?? texts.ru;

// ── Which questions are asked right now ─────────────────

/** An 18+ question for someone who said they're under 18: never asked. */
const underage = (q) => q.adult_only && about.adult === 'no';
/** Of those, the ones that would be on the page anyway stay there grayed out; follow-ups stay hidden. */
const grayed = (q) => underage(q) && !q.show_if;

function applies(q) {
  if (underage(q)) return false;
  if (q.show_if) {
    const chosen = [answers[q.show_if.question]].flat();
    return chosen.some((c) => q.show_if.any_of.includes(c));
  }
  return true;
}

// Drawn on the strip and next to the question: required and still empty. On the first visit
// only after "Done" was pressed; later, at once.
let showGaps = !onboarding;

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
  saveDraft.now();
  // Several answers can be ticked: stay, unless the one picked rules out the rest ("none").
  if (q.type !== 'multi' || answers[q.id].length === 1 && (q.exclusive ?? []).includes(index)) advance($(`q-${q.id}`));
}

// ── Moving on (phones) ──────────────────────────────────
// On a phone an answer given brings the next question up, after a beat so the choice is seen
// first. It stops a quarter of the way down the screen, so its answers sit in the middle and
// lower part, under the thumb. Not on a computer: there the page stays where it is.

const phone = matchMedia('(max-width: 640px) and (pointer: coarse)');

/** Everything still to be answered on the page, in order: the facts, then the questions. */
function steps() {
  return [$('f-gender'), $('f-adult'), $('f-faculty'), ...$('blocks').querySelectorAll('[data-question]')]
    .filter((node) => !node.hidden && !node.disabled);
}

/** Scroll so `node` starts `share` of the way down the screen (never under the sticky header). */
function bringUp(node, share) {
  const sticky = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--sticky-h')) || 0;
  const offset = Math.max(innerHeight * share, sticky + 16);
  window.scrollTo({ top: scrollY + node.getBoundingClientRect().top - offset });
}

let advancing;
function advance(from) {
  if (!phone.matches) return;
  clearTimeout(advancing);
  advancing = setTimeout(() => {
    const list = steps();
    const next = list[list.indexOf(from) + 1];
    const group = next?.closest('.qgroup');
    // The next row of the same group is right below already.
    if (group && group === from.closest('.qgroup')) return;
    // A group comes up with its heading; after the last question, the "Done" button.
    if (next) bringUp(group ?? next, 1 / 4);
    else if (!$('qbar').hidden) bringUp($('qbar').querySelector('[type=submit]'), 1 / 2);
  }, 250);
}

/** Answers short in every language ("0–1", "2–3", "4 or more") fit side by side in one row.
    Checked across languages so the layout doesn't jump when the language changes. */
function shortOptions(q) {
  return q.options.every((option) => ['ru', 'en', 'zh'].every((lang) => (option[lang] ?? '').length <= 12));
}

function questionNode(q) {
  const options = q.options.map((option, index) => el('button', {
    type: 'button', 'data-index': index, 'aria-pressed': 'false', onclick: () => pick(q, index),
  }, tr(option)));
  return el('fieldset', { id: `q-${q.id}`, 'data-question': q.id },
    el('legend', {},
      q.hidden && el('span', { role: 'img', title: t('quiz.hidden.title'), 'aria-label': t('quiz.hidden.title') }, '🔒'),
      q.hidden && ' ', tr(q.text),
      !q.required && el('span', { class: 'tag' }, t('quiz.optional'))),
    q.hint && el('p', { class: 'hint' }, tr(q.hint)),
    el('div', { class: 'opts', 'data-choice': q.type, 'data-row': shortOptions(q) || null }, ...options),
    q.adult_only && !q.show_if && el('p', { class: 'note', 'data-underage': '', hidden: true }, `⚠ ${t('quiz.underage')}`),
    el('p', { class: 'note error', hidden: true }, `✕ ${t('quiz.unanswered')}`));
}

/** One row of a group (the two bedtime questions): its label and a scale of short cells.
    Same hooks as a question (id, data-question, option buttons with data-index). */
function rowNode(q, group) {
  const options = q.options.map((option, index) => el('button', {
    type: 'button', 'data-index': index, 'aria-pressed': 'false', 'aria-label': tr(option), title: tr(option),
    onclick: () => pick(q, index),
  }, tr(option.short)));
  return el('div', { class: 'qrow', id: `q-${q.id}`, 'data-question': q.id, role: 'group', 'aria-labelledby': `group-${group.id} label-${q.id}` },
    el('span', { class: 'qrow-label', id: `label-${q.id}` }, tr(q.label)),
    el('div', { class: 'scale' }, ...options),
    el('p', { class: 'note error', hidden: true }, `✕ ${t('quiz.unanswered')}`));
}

/** Questions that share a group sit under one heading, one row each, on scales that line up. */
function groupNode(group, questions) {
  return el('div', { class: 'qgroup' },
    el('p', { class: 'qgroup-title', id: `group-${group.id}` }, tr(group.text)),
    ...questions.map((q) => rowNode(q, group)));
}

function blockNode(block, questions) {
  const nodes = [];
  const drawn = new Set();
  for (const q of questions) {
    const group = q.group && groups[q.group];
    if (!group) nodes.push(questionNode(q));
    else if (!drawn.has(group.id)) {
      drawn.add(group.id);
      nodes.push(groupNode(group, questions.filter((other) => other.group === group.id)));
    }
  }
  return el('section', { class: 'box pad qblock', 'aria-labelledby': `block-${block.id}` },
    el('h2', { id: `block-${block.id}` }, tr(block.title)),
    block.note && questions.some((q) => q.id === 'E1') && el('p', { class: 'note' }, tr(block.note)),
    ...nodes);
}

function render() {
  $('blocks').replaceChildren(...quiz.blocks
    .map((b) => [b, quiz.questions.filter((q) => q.block === b.id)])
    .filter(([, qs]) => qs.length)
    .map(([b, qs]) => blockNode(b, qs)));
  renderFacultyPicker($('faculty'), meta.faculties, about.faculty);
  refresh();
}

/** Bring the page in line with `answers` and `about` without rebuilding it. */
function refresh() {
  for (const node of document.querySelectorAll('[data-question]')) {
    const q = byId[node.dataset.question];
    node.hidden = !applies(q) && !grayed(q);
    node.disabled = grayed(q);
    const chosen = [answers[q.id]].flat();
    for (const button of node.querySelectorAll('button[data-index]')) {
      button.setAttribute('aria-pressed', String(chosen.includes(Number(button.dataset.index))));
    }
    const notice = node.querySelector('[data-underage]');
    if (notice) notice.hidden = !grayed(q);
    node.querySelector('.note.error').hidden = !(showGaps && q.required && applies(q) && !answered(q));
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
// One cell per question, all 20, in page order.
// Empty = no answer yet, purple = answered, red = required and still empty (see showGaps),
// gray = doesn't apply: 18+ for someone under 18, or a follow-up that isn't asked (its cell
// leads to the question it depends on).

function stripCells() {
  return quiz.questions.map((q) => {
    const own = $(`q-${q.id}`);
    const node = own.hidden && q.show_if ? $(`q-${q.show_if.question}`) : own;
    let state = '';
    if (!applies(q)) state = 'off';
    else if (answered(q)) state = 'done';
    else if (showGaps && q.required) state = 'missing';
    return { node, label: tr(q.text), state };
  });
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
  // Exact (fractional) heights: offsetHeight rounds, which left a hairline gap under the header.
  const set = () => {
    const headerH = header.getBoundingClientRect().height;
    root.setProperty('--header-h', `${headerH}px`);
    root.setProperty('--sticky-h', `${headerH + $('strip-bar').getBoundingClientRect().height}px`);
  };
  const watcher = new ResizeObserver(set);
  watcher.observe(header);
  watcher.observe($('strip-bar'));
}

/** Wide screens: the top strip steps aside while the bottom bar (which has its own strip) is in view. */
$('qbar').hidden = !onboarding;
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
      saveDraft.now();
      advance($(`f-${group}`));
    });
  }
}
$('faculty').addEventListener('change', () => {
  about.faculty = $('faculty').value;
  $('f-faculty').querySelector('.note')?.remove();
  saveDraft.now();
  advance($('f-faculty'));
});

render();
document.addEventListener('langchange', render);

// ── Saving ──────────────────────────────────────────────

/** What is stored: the answers given, in question order (so two equal sets compare equal). */
function draft() {
  return Object.fromEntries(quiz.questions.filter(answered)
    .map((q) => [q.id, Array.isArray(answers[q.id]) ? [...answers[q.id]].sort((a, b) => a - b) : answers[q.id]]));
}

let savedDraft = JSON.stringify(draft());

/** Send what changed since the last save. Resolves to false if the server refused it. */
async function save() {
  try {
    const facts = {};
    if (about.gender && about.gender !== user.gender) facts.gender = about.gender;
    if (about.adult && (about.adult === 'yes') !== user.is_adult) facts.is_adult = about.adult === 'yes';
    if (about.faculty && about.faculty !== user.faculty) facts.faculty = about.faculty;
    if (Object.keys(facts).length) user = await put('/me', facts);
    // Which questions are asked depends on "are you 18?": until then the answers wait on the page.
    if (user.is_adult == null) return true;
    const body = draft();
    if (JSON.stringify(body) === savedDraft) return true;
    const saved = await put('/questionnaire', { version: quiz.version, answers: body, replace: true });
    savedDraft = JSON.stringify(body);
    quiz.complete = saved.complete;
    return true;
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    if (err.status === 401) { location.replace('/login'); return false; }
    // A newer questionnaire was published while this page was open.
    if (err.code === 'QUESTIONNAIRE_OUTDATED') { location.reload(); return false; }
    toast(t('error.title'), errorText(err), { error: true });
    return false;
  }
}

const saveDraft = autosaver(save);

function complain(host) {
  if (!host.querySelector(':scope > .note')) host.append(el('p', { class: 'note error' }, `✕ ${t('quiz.unanswered')}`));
  return host;
}

/** Mark what's missing; returns the first such element, or null when everything is answered. */
function firstGap() {
  showGaps = true;
  refresh();
  const gaps = [];
  if (!about.gender) gaps.push(complain($('f-gender')));
  if (!about.adult) gaps.push(complain($('f-adult')));
  if (!about.faculty) gaps.push(complain($('f-faculty')));
  gaps.push(...requiredNow().filter((q) => !answered(q)).map((q) => $(`q-${q.id}`)));
  return gaps[0] ?? null;
}

function show(id) {
  for (const panel of ['quiz', 'intent']) $(panel).hidden = panel !== id;
  $('strip-bar').hidden = id !== 'quiz';
  window.scrollTo(0, 0);
  $(id).querySelector('h1')?.setAttribute('tabindex', '-1');
  $(id).querySelector('h1')?.focus();
}

/** After the questionnaire: ask what they came for (once), then go to their page. */
async function finish() {
  // Came by a friend's compare link: the result is what they came for.
  if (!user.intent && session.get(KEYS.compared) != null) {
    try { user = await put('/me', { intent: 'compare' }); } catch (err) { reportBug(err, { where: 'intent' }); }
    session.remove(KEYS.compared);
    location.assign('/compare');
    return;
  }
  // Someone who came by invite link doesn't need to be asked what they are here for.
  if (!user.intent && session.get(KEYS.invite)) {
    try { user = await put('/me', { intent: 'join' }); } catch (err) { reportBug(err, { where: 'intent' }); /* the join page works without it */ }
  }
  if (!user.intent) { show('intent'); return; }
  location.assign(homeFor({ ...user, questionnaire_complete: true }));
}

// "Done" (first visit only): everything is saved already; check nothing required is missing.
$('quiz').addEventListener('submit', async (e) => {
  e.preventDefault();
  const gap = firstGap();
  if (gap) {
    gap.scrollIntoView({ block: 'center' });
    (gap.querySelector('button, select') ?? gap).focus({ preventScroll: true });
    return;
  }
  setBusy(e.submitter, true);
  const ok = await saveDraft.now();
  setBusy(e.submitter, false);
  if (ok) finish();
});

for (const button of [...$('intent-opts').querySelectorAll('button'), $('intent-compare')]) {
  button.addEventListener('click', async () => {
    if (button.dataset.value === 'join') { openInvite(button); return; }
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

// "I was invited": the link or code goes in right here; the join page then shows the place.
mountInviteField($('invite-code'), $('invite-hint'));

function openInvite(button) {
  button.setAttribute('aria-pressed', 'true');
  button.setAttribute('aria-expanded', 'true');
  $('invite-form').hidden = false;
  $('invite-code').focus();
}

$('invite-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const code = $('invite-code').value.trim();
  $('invite-code').setAttribute('aria-invalid', String(!code));
  $('invite-err').textContent = code ? '' : t('error.field.REQUIRED');
  $('invite-err').hidden = Boolean(code);
  if (!code) { $('invite-code').focus(); return; }
  setBusy(e.submitter, true);
  try {
    user = await put('/me', { intent: 'join' });
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    setBusy(e.submitter, false);
    toast(t('error.title'), errorText(err), { error: true });
    return;
  }
  session.set(KEYS.invite, code); // picked up by the join page
  location.assign('/join');
});

// ── Taking it together ──────────────────────────────────
// The same link as on the compare page (one nobody has opened yet is reused), so it can go
// out before anyone has answered and the friend's progress shows up there.

const invitedBy = session.get(KEYS.compared);
function drawInvitedBy() {
  if (invitedBy == null) return;
  $('together').hidden = true;
  $('together-joined').hidden = false;
  $('together-joined').textContent = invitedBy
    ? t('compare.quiz.joined', { name: invitedBy }) : t('compare.quiz.joinedNoName');
}
drawInvitedBy();
document.addEventListener('langchange', drawInvitedBy);
$('together-mine').hidden = !compares.some((g) => g.members.length > 1);

async function openTogether(copy) {
  const button = $('together-open');
  setBusy(button, true);
  try {
    const link = await post('/compare');
    $('together-url').value = link.url;
    $('together-link').hidden = false;
    $('together-mine').hidden = false;
    if (copy) await copyLink();
  } catch (err) {
    if (!(err instanceof ApiError)) throw err;
    toast(t('error.title'), errorText(err), { error: true });
  } finally {
    setBusy(button, false);
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText($('together-url').value);
    toast(t('compare.share.copied'), t('compare.quiz.copiedText'), { ms: 4000 });
  } catch {
    $('together-url').select();
  }
}

$('together-open').addEventListener('click', () => openTogether(true));
$('together-copy').addEventListener('click', copyLink);
// Picked "take it together" on the landing page: the link is ready (copying needs a click).
if (session.get(KEYS.together)) {
  session.remove(KEYS.together);
  if (invitedBy == null) openTogether(false);
}
$('together-url').addEventListener('focus', (e) => e.target.select());

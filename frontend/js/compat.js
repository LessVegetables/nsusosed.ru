// How a compatibility result is shown: a percent rounded to 5 and five topic badges with
// three levels. Meaning is always in words too, never in color alone.

import { currentLang, t } from './i18n.js';
import { el } from './ui.js';

const tr = (texts) => texts[currentLang()] ?? texts.ru;

export const TOPICS = ['sleep', 'order', 'quiet', 'air', 'living'];
// The server's level → the design system's class.
const LEVEL_CLASS = { match: 'match', ok: 'partial', discuss: 'mismatch' };

export const topicName = (topic) => ({
  sleep: t('compat.topic.sleep'), order: t('compat.topic.order'), quiet: t('compat.topic.quiet'),
  air: t('compat.topic.air'), living: t('compat.topic.living'),
}[topic]);

export const levelName = (level) => ({
  match: t('compat.level.match'), ok: t('compat.level.ok'), discuss: t('compat.level.discuss'),
}[level]);

/** Small chips for a card: one per topic. */
export function chips(compatibility) {
  return el('div', { class: 'chips' }, ...TOPICS.map((topic) => {
    const level = compatibility.badges[topic];
    return el('span', { class: `chip ${LEVEL_CLASS[level]}`, title: levelName(level) }, topicName(topic));
  }));
}

/** Tiles for the room page: topic and its level in words. */
export function breakdown(compatibility) {
  return el('div', { class: 'breakdown' }, ...TOPICS.map((topic) => {
    const level = compatibility.badges[topic];
    return el('div', { class: LEVEL_CLASS[level] }, el('small', {}, topicName(topic)), levelName(level));
  }));
}

/** How far apart two answers to one question are: 'far', 'near' or 'same'. Every visible question
 *  is a scale (its options run from one end to the other), so the distance is the step count. */
function gap(q, mine, theirs) {
  const steps = Math.abs(mine - theirs);
  const share = steps / Math.max(1, q.options.length - 1);
  return { share, level: steps === 0 ? 'same' : steps >= 2 && share >= 0.4 ? 'far' : 'near' };
}

/** One question where the answers differ: the scale with both marks on it, then both answers. */
function diffRow(mineAll, person, q, level) {
  const mine = mineAll[q.id];
  const theirs = person.answers[q.id];
  const who = (i) => (i === mine ? 'me' : i === theirs ? 'them' : null);
  return el('li', { class: 'cmp-row' },
    el('p', { class: 'cmp-q' }, tr(q.text)),
    el('div', { class: 'cmp-track', 'aria-hidden': 'true' }, ...q.options.map((_, i) => el('i', { 'data-who': who(i) }))),
    el('p', { class: 'cmp-a' }, el('span', { class: 'cmp-who', 'data-who': 'them' }, person.first_name), tr(q.options[theirs])),
    el('p', { class: 'cmp-a' }, el('span', { class: 'cmp-who', 'data-who': 'me' }, t('room.you')), tr(q.options[mine])),
    level === 'near' && el('span', { class: 'sr-only' }, t('room.cmp.near')));
}

/** Visible answers compared with mine (room page, compare page). The big differences sit open,
 *  worst first; small ones and identical answers are folded away, the identical ones as one line
 *  each. `questions` come from GET /api/questionnaire; `mine` and `person.answers` are
 *  {question id: option index}, visible answers only. */
export function answerDiff(questions, mine, person) {
  const items = questions
    .filter((q) => !q.hidden && person.answers[q.id] != null && mine[q.id] != null)
    .map((q) => ({ q, ...gap(q, mine[q.id], person.answers[q.id]) }))
    .sort((a, b) => b.share - a.share);
  if (!items.length) return null;
  const of = (level) => items.filter((item) => item.level === level);
  const [far, near, same] = [of('far'), of('near'), of('same')];
  const group = (cls, label, list, row) => list.length > 0 && el('div', { class: 'cmp-group' },
    el('p', { class: 'cmp-head' }, el('span', { class: `chip ${cls}` }, label), el('span', { class: 'meta' }, String(list.length))),
    el('ul', { class: 'cmp' }, ...list.map(row)));
  // At most three big differences sit open; any further ones lead the folded part.
  const open = far.slice(0, 3);
  const folded = far.slice(3);
  const rest = folded.length + near.length + same.length;
  return el('div', { class: 'cmp-wrap' },
    open.length
      ? group('mismatch', t('room.cmp.far'), open, ({ q }) => diffRow(mine, person, q, 'far'))
      : el('p', { class: 'note success' }, `✓ ${t('room.cmp.noFar')}`),
    rest > 0 && el('details', { class: 'more' },
      el('summary', {}, t('room.compare', { n: rest })),
      group('mismatch', t('room.cmp.far'), folded, ({ q }) => diffRow(mine, person, q, 'far')),
      group('partial', t('room.cmp.near'), near, ({ q }) => diffRow(mine, person, q, 'near')),
      group('match', t('room.cmp.same'), same, ({ q }) => el('li', { class: 'cmp-row' },
        el('p', { class: 'cmp-q' }, tr(q.text)),
        el('p', { class: 'cmp-a' }, tr(q.options[person.answers[q.id]]))))));
}

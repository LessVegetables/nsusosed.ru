// How a compatibility result is shown: a percent rounded to 5 and five topic badges with
// three levels. Meaning is always in words too, never in color alone.

import { t } from './i18n.js';
import { el } from './ui.js';

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

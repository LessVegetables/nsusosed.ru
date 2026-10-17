// /listing?id=<uuid> — one listing, its compatibility breakdown and the contact.

import { api } from '../api.js';
import { initPage } from '../layout.js';
import { explanation, facts, listingTitle, residentsList, scoreBadge, warnings } from '../listing-view.js';
import { busy, h, loadFailed, loading, showError, toast } from '../ui.js';

await initPage({ auth: 'required' });

const content = document.getElementById('content');
const id = new URLSearchParams(location.search).get('id');

// Label of the scale option closest to a value (room averages are fractional).
function optionLabel(question, value) {
  if (!question) return { ru: String(value), en: String(value) };
  let best = question.scale[0];
  for (const opt of question.scale) {
    if (Math.abs(opt.value - value) < Math.abs(best.value - value)) best = opt;
  }
  return best.label;
}

function breakdown(compat, questions) {
  const byKey = Object.fromEntries(questions.map((q) => [q.key, q]));
  return h(
    'ul',
    { class: 'breakdown' },
    compat.dimensions.map((d) => {
      const q = byKey[d.key];
      return h(
        'li',
        { class: `explain-${d.label}` },
        h('p', { class: 'breakdown-title' },
          h('span', { i18n: `topic.${d.key}`, class: 'topic' }),
          ' — ',
          h('span', { i18n: `label.${d.label}` })),
        h('p', { class: 'muted small' },
          h('span', { i18n: 'detail.you' }), ' ', h('span', { localized: optionLabel(q, d.candidate_value) }),
          ' · ',
          h('span', { i18n: 'detail.room' }), ' ≈ ', h('span', { localized: optionLabel(q, d.room_average) })),
      );
    }),
  );
}

function contactSection(listingId) {
  const result = h('div', { class: 'contact-result', 'aria-live': 'polite', 'data-private': true });
  const error = h('div', { hidden: true });
  const button = h('button', { type: 'button', class: 'btn', i18n: 'detail.showContact' });

  button.addEventListener('click', async () => {
    const done = busy(button);
    try {
      const contact = await api.getContact(listingId);
      button.remove();
      error.hidden = true;
      result.replaceChildren(renderContact(contact));
    } catch (err) {
      showError(error, err);
      done();
    }
  });

  return h(
    'section',
    { class: 'card', 'aria-labelledby': 'contact-title' },
    h('h2', { id: 'contact-title', i18n: 'detail.contactTitle' }),
    h('p', { class: 'muted', i18n: 'detail.contactHint' }),
    button,
    error,
    result,
  );
}

function renderContact(contact) {
  // Only follow links we expect from the API (https or tel); show anything else as text.
  const safeUrl = contact.url && /^(https:\/\/|tel:)/.test(contact.url) ? contact.url : null;
  const shown = contact.type === 'telegram' ? `@${contact.value}` : contact.value;
  const value = safeUrl
    ? h('a', { href: safeUrl, target: safeUrl.startsWith('https') ? '_blank' : null, rel: 'noopener noreferrer' }, shown)
    : h('span', {}, shown);

  const copy = h('button', { type: 'button', class: 'btn btn-secondary btn-small', i18n: 'common.copy' });
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(shown);
      toast('common.copied');
    } catch {
      toast('common.copyFailed');
    }
  });

  return h(
    'p',
    { class: 'contact' },
    h('span', { class: 'contact-type', i18n: `contact.${contact.type}` }),
    ' ',
    value,
    ' ',
    copy,
  );
}

function render(detail, questions) {
  document.title = `${listingTitle(detail).textContent} — nsusosed`;
  const compat = detail.compatibility;

  content.replaceChildren(
    h('p', {}, h('a', { href: `/matches?kind=${detail.kind}`, i18n: 'detail.back' })),
    h('div', { class: 'detail-head' }, h('h1', {}, listingTitle(detail)), compat ? scoreBadge(compat.score) : null),
    h('p', { class: 'muted', i18n: 'detail.confirmed', i18nArgs: { date: { date: detail.confirmed_at } } }),

    compat
      ? h(
          'section',
          { class: 'card', 'aria-labelledby': 'compat-title' },
          h('h2', { id: 'compat-title', i18n: 'detail.compatTitle' }),
          explanation(compat.dimensions, { maxSimilar: 0 }),
          warnings(compat.warnings),
          h('details', {}, h('summary', { i18n: 'detail.breakdown' }), breakdown(compat, questions)),
          h('p', { class: 'muted small', i18n: 'detail.scoreNote' }),
        )
      : h('p', { class: 'alert alert-info', i18n: 'detail.ownListing' }),

    h(
      'section',
      { class: 'card', 'aria-labelledby': 'about-title' },
      h('h2', { id: 'about-title', i18n: 'detail.about' }),
      facts(detail),
      detail.description ? h('p', { class: 'description', 'data-private': true }, detail.description) : null,
    ),

    h(
      'section',
      { class: 'card', 'aria-labelledby': 'residents-title' },
      h('h2', { id: 'residents-title', i18n: 'detail.residents' }),
      residentsList(detail.residents),
    ),

    contactSection(detail.id),
  );
}

function notFound() {
  content.replaceChildren(
    h('h1', { i18n: 'detail.notFoundTitle' }),
    h('p', { i18n: 'detail.notFound' }),
    h('p', {}, h('a', { class: 'btn', href: '/matches', i18n: 'detail.back' })),
  );
}

async function load() {
  if (!id) return notFound();
  loading(content);
  try {
    const [detail, questionnaire] = await Promise.all([api.getListing(id), api.getQuestions()]);
    render(detail, questionnaire.questions);
  } catch (err) {
    if (err.code === 'NOT_FOUND') return notFound();
    if (err.code === 'PROFILE_REQUIRED' || err.code === 'BUDGET_REQUIRED') {
      const box = h('div');
      showError(box, err);
      box.append(h('p', {}, h('a', { class: 'btn', href: err.code === 'BUDGET_REQUIRED' ? '/questionnaire#budget' : '/questionnaire', i18n: 'matches.fillIn' })));
      content.replaceChildren(box);
      return;
    }
    loadFailed(content, err, load);
  }
}

// Keep the tab title (the listing's name) in the current language.
window.addEventListener('langchange', () => {
  const title = content.querySelector('h1');
  if (title) document.title = `${title.textContent} — nsusosed`;
});

await load();

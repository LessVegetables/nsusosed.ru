// The faculty picker on the questionnaire and account pages. Every language lists faculties as
// "ММФ — Mechanics and Mathematics" (the Russian abbreviation first). On phones the closed
// picker shows only "ММФ": a label laid over the select (.short-select in pages.css); the
// open list still has the full names.

import { currentLang, t } from './i18n.js';
import { el } from './ui.js';

const wired = new WeakSet();

/** Fill `select` from GET /meta faculties and pick `value` ('' = not selected). */
export function renderFacultyPicker(select, faculties, value) {
  const lang = currentLang();
  select.replaceChildren(
    el('option', { value: '' }, t('account.faculty.none')),
    ...faculties.map((f) => {
      const name = f[lang] ?? f.ru;
      return el('option', { value: f.id, 'data-short': f.abbr ?? name }, f.abbr ? `${f.abbr} — ${name}` : name);
    }));
  select.value = value ?? '';
  syncShortLabel(select);
  if (!wired.has(select)) {
    wired.add(select);
    select.addEventListener('change', () => syncShortLabel(select));
  }
}

function syncShortLabel(select) {
  const label = select.parentElement.querySelector('.short-select-label');
  const option = select.selectedOptions[0];
  if (label) label.textContent = option ? option.dataset.short ?? option.textContent : '';
}

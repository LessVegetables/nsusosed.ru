// Behavior for design/specimen.html only: theme and language switches, plus the small
// interactions the components need (tabs, choices, slider fill, code boxes, contacts, toast).
// Kept in its own file so the specimen also runs under a strict CSP (no inline scripts).

const root = document.documentElement;

// Theme: auto (system) / light / dark.
document.querySelectorAll('[data-theme-set]').forEach((b) => b.addEventListener('click', () => {
  const t = b.dataset.themeSet;
  if (t === 'auto') root.removeAttribute('data-theme'); else root.dataset.theme = t;
  document.querySelectorAll('[data-theme-set]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
}));

// Language: swaps every [data-i18n] text and the <html lang>, so the Chinese rules can be checked.
const strings = {
  ru: {
    headline: 'Соседи, которые живут <mark class="highlight">так же,</mark> как вы',
    lead: 'Короткая анкета о привычках — и комнаты в общежитии и квартиры со свободными местами, отсортированные по совместимости.',
    cta: 'Войти по почте →', title: 'Сначала самые совместимые', card: 'Корпус 7, комната 412', meta: '4 этаж · 2 жильца',
  },
  en: {
    headline: 'Roommates who live <mark class="highlight">the way</mark> you do',
    lead: 'A short questionnaire about your habits, then dorm rooms and flats with free places, sorted by how well you match the people who live there.',
    cta: 'Log in with email →', title: 'Best matches first', card: 'Block 7, room 412', meta: 'Floor 4 · 2 residents',
  },
  zh: {
    headline: '找到和你<mark class="highlight">生活习惯</mark>一样的室友',
    lead: '填写一份简短的生活习惯问卷，即可查看有空位的宿舍和公寓，并按与现有住户的匹配度排序。',
    cta: '用邮箱登录 →', title: '最匹配的排在前面', card: '7号楼 412室', meta: '4楼 · 2位住户',
  },
};
const langCode = { ru: 'ru', en: 'en', zh: 'zh-CN' };
document.querySelectorAll('[data-lang-set]').forEach((b) => b.addEventListener('click', () => {
  const l = b.dataset.langSet;
  root.lang = langCode[l];
  document.querySelectorAll('[data-i18n]').forEach((el) => { el.innerHTML = strings[l][el.dataset.i18n]; });
  document.querySelectorAll('[data-lang-set]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
}));

// Tabs.
document.querySelectorAll('[role="tablist"]').forEach((list) => {
  const tabs = list.querySelectorAll('[role="tab"]');
  tabs.forEach((t) => t.addEventListener('click', () => tabs.forEach((x) => x.setAttribute('aria-selected', String(x === t)))));
});

// Single and multiple choice buttons.
document.querySelectorAll('[data-choice]').forEach((g) => {
  const multi = g.dataset.choice === 'multi';
  g.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => {
    if (multi) b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true'));
    else g.querySelectorAll('button').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  }));
});

// Slider: value readout and pink fill (CSSOM custom property; allowed under CSP).
document.querySelectorAll('.range input').forEach((r) => {
  const out = r.parentElement.querySelector('output');
  const upd = () => { out.textContent = r.value; r.style.setProperty('--fill', ((r.value - r.min) / (r.max - r.min) * 100) + '%'); };
  r.addEventListener('input', upd); upd();
});

// Code boxes: one digit each, auto-advance, backspace goes back, paste fills all six.
document.querySelectorAll('.code').forEach((box) => {
  const cells = [...box.querySelectorAll('input')];
  cells.forEach((c, i) => {
    c.addEventListener('input', () => { c.value = c.value.replace(/\D/g, '').slice(-1); if (c.value && cells[i + 1]) cells[i + 1].focus(); });
    c.addEventListener('keydown', (e) => { if (e.key === 'Backspace' && !c.value && cells[i - 1]) cells[i - 1].focus(); });
    c.addEventListener('paste', (e) => {
      const d = (e.clipboardData.getData('text').match(/\d/g) || []).slice(0, 6);
      if (!d.length) return;
      e.preventDefault();
      cells.forEach((x, j) => { x.value = d[j] || ''; });
      cells[Math.min(d.length, 5)].focus();
    });
  });
});

// "Show contacts" reveals the green box.
document.querySelectorAll('[data-reveal]').forEach((b) => b.addEventListener('click', () => {
  document.getElementById(b.dataset.reveal).hidden = false;
  b.hidden = true;
}));

// Toast: show on demand, close with the round button.
const toast = document.getElementById('toast');
document.querySelectorAll('[data-toast-show]').forEach((b) => b.addEventListener('click', () => { toast.hidden = false; }));
toast.querySelector('.close').addEventListener('click', () => { toast.hidden = true; });

// Busy button demo.
document.querySelectorAll('[data-busy-demo]').forEach((b) => b.addEventListener('click', () => {
  b.setAttribute('aria-busy', 'true');
  setTimeout(() => b.removeAttribute('aria-busy'), 1500);
}));

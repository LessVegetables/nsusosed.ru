// The RU / EN / 中文 switch. It appears on three pages only: landing, login, account.
// What a pick does besides re-translating the page is up to the page (onPick):
// the landing and login pages remember it for this tab, the account page saves it to the account.

import { LANGS, LANG_NAMES, currentLang, setLang, t } from './i18n.js';
import { el } from './ui.js';

export function mountLangSwitch(host, { onPick } = {}) {
  const buttons = LANGS.map((code) => el('button', {
    type: 'button', lang: code === 'zh' ? 'zh-CN' : code, 'aria-pressed': String(code === currentLang()),
    onclick: async () => {
      if (code === currentLang()) return;
      await setLang(code);
      await onPick?.(code);
    },
  }, LANG_NAMES[code]));
  const group = el('div', { class: 'langsw', role: 'group', 'aria-label': t('lang.label') }, ...buttons);
  document.addEventListener('langchange', () => {
    buttons.forEach((b, i) => b.setAttribute('aria-pressed', String(LANGS[i] === currentLang())));
    group.setAttribute('aria-label', t('lang.label'));
  });
  host.replaceChildren(group);
  return group;
}

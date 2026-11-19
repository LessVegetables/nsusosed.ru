// Translations: parameters, the Russian fallback, and which language a page starts in (js/i18n.js).
import { resetStorage, stores } from './env.js';
import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { detectLang, setLang, t } from '../../frontend/js/i18n.js';
import { KEYS } from '../../frontend/js/storage.js';

beforeEach(resetStorage);

const browserLanguages = (list) => Object.defineProperty(globalThis, 'navigator', { value: { languages: list }, configurable: true });

test('the account language beats a guest pick, which beats the browser', () => {
  browserLanguages(['zh-CN']);
  assert.equal(detectLang(), 'zh');
  stores.sessionStorage.setItem(KEYS.lang, 'en');
  assert.equal(detectLang(), 'en');
  stores.localStorage.setItem(KEYS.lang, 'ru');
  assert.equal(detectLang(), 'ru');
});

test('an unknown browser language means Russian', () => {
  browserLanguages(['de-DE', 'fr']);
  assert.equal(detectLang(), 'ru');
});

test('parameters are filled in; unknown ones and keys stay visible', async () => {
  await setLang('en');
  assert.equal(t('compare.with', { names: 'Anya' }), 'You and Anya');
  assert.equal(t('compare.with'), 'You and {names}');
  assert.equal(t('no.such.key'), 'no.such.key');
});

test('an unknown language falls back to Russian', async () => {
  assert.equal(await setLang('xx'), 'ru');
  assert.equal(t('compare.start.cta'), 'Пройти анкету');
});

// Where people land after logging in, and "their own page" (js/routes.js).
import { resetStorage, stores } from './env.js';
import { beforeEach, describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { afterLogin, homeFor, withCampaign } from '../../frontend/js/routes.js';
import { KEYS } from '../../frontend/js/storage.js';

const session = () => stores.sessionStorage;
const newUser = { questionnaire_complete: false, intent: null, home_id: null };
const done = (intent, extra = {}) => ({ questionnaire_complete: true, intent, home_id: null, ...extra });

beforeEach(resetStorage);

describe('homeFor', () => {
  test('a new person goes to the questionnaire', () => {
    assert.equal(homeFor(newUser), '/questionnaire');
  });

  test("a friend's compare code in this tab beats everything", () => {
    session().setItem(KEYS.compare, 'K7QM2XWP');
    assert.equal(homeFor(newUser), '/compare');
    assert.equal(homeFor(done('host', { home_id: 'h1' })), '/compare');
  });

  test('an invite waits for the questionnaire, then goes to join', () => {
    session().setItem(KEYS.invite, 'K7QM2XWP');
    assert.equal(homeFor(newUser), '/questionnaire');
    assert.equal(homeFor(done(null)), '/join');
    assert.equal(homeFor(done('seek_dorm', { home_id: 'h1' })), '/home', 'already living somewhere');
  });

  test('done but never said what for: the questionnaire asks', () => {
    assert.equal(homeFor(done(null)), '/questionnaire');
  });

  test('each intent has its page', () => {
    assert.equal(homeFor(done('host')), '/home');
    assert.equal(homeFor(done('seek_dorm', { home_id: 'h1' })), '/home');
    assert.equal(homeFor(done('join')), '/join');
    assert.equal(homeFor(done('compare')), '/compare');
    assert.equal(homeFor(done('seek_apt')), '/feed?kind=apartment');
    assert.equal(homeFor(done('seek_dorm')), '/feed?kind=dorm');
  });
});

describe('afterLogin', () => {
  test('nothing remembered: their own page', () => {
    assert.equal(afterLogin(newUser), '/questionnaire');
    assert.equal(afterLogin(done('seek_apt')), '/feed?kind=apartment');
  });

  test('back to the page the guest opened, query included', () => {
    session().setItem(KEYS.back, '/compare');
    assert.equal(afterLogin(newUser), '/compare');
    session().setItem(KEYS.back, '/room?id=42');
    assert.equal(afterLogin(done('seek_dorm')), '/room?id=42');
  });

  test('the remembered page is used once', () => {
    session().setItem(KEYS.back, '/account');
    assert.equal(afterLogin(newUser), '/account');
    assert.equal(session().getItem(KEYS.back), null);
    assert.equal(afterLogin(newUser), '/questionnaire');
  });

  test('never another site, never /login itself', () => {
    for (const bad of ['//evil.example/x', 'https://evil.example/', 'javascript:alert(1)', '/login', '']) {
      session().setItem(KEYS.back, bad);
      assert.equal(afterLogin(newUser), '/questionnaire', bad);
    }
  });
});

describe('withCampaign', () => {
  test('carries utm tags and nothing else', () => {
    assert.equal(withCampaign('/login', '?utm_source=poster&utm_content=test-a&x=1'), '/login?utm_source=poster&utm_content=test-a');
  });
  test('keeps the path untouched without tags', () => {
    assert.equal(withCampaign('/login', ''), '/login');
    assert.equal(withCampaign('/feed?kind=dorm', '?x=1'), '/feed?kind=dorm');
  });
  test("adds to a path's own query", () => {
    assert.equal(withCampaign('/feed?kind=dorm', '?utm_source=poster'), '/feed?kind=dorm&utm_source=poster');
  });
});

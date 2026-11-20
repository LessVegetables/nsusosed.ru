// Browser storage that never throws (js/storage.js).
import { blockStorage, resetStorage, stores } from './env.js';
import { beforeEach, test } from 'node:test';
import assert from 'node:assert/strict';
import { local, session } from '../../frontend/js/storage.js';

beforeEach(resetStorage);

test('session and local are separate stores', () => {
  session.set('k', 'tab');
  local.set('k', 'browser');
  assert.equal(stores.sessionStorage.getItem('k'), 'tab');
  assert.equal(stores.localStorage.getItem('k'), 'browser');
  session.remove('k');
  assert.equal(session.get('k'), null);
  assert.equal(local.get('k'), 'browser');
});

test('blocked storage reads as empty and writes do nothing', () => {
  blockStorage();
  assert.doesNotThrow(() => session.set('k', 'v'));
  assert.doesNotThrow(() => local.remove('k'));
  assert.equal(session.get('k'), null);
  assert.equal(local.get('k'), null);
});

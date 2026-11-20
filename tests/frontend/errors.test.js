// Error reports group by endpoint, not by id (js/errors.js).
import './env.js';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { routeOf } from '../../frontend/js/errors.js';

test('ids and numbers become :id, the query goes', () => {
  assert.equal(routeOf('/homes/3f2c1a2b-1111-4222-8333-444455556666/photos/12?x=1'), '/homes/:id/photos/:id');
  assert.equal(routeOf('/rooms/42'), '/rooms/:id');
  assert.equal(routeOf('/me'), '/me');
});

test('a number inside a word stays', () => {
  assert.equal(routeOf('/v2/meta'), '/v2/meta');
});

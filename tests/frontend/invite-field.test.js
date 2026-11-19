// What the invite field keeps from whatever is pasted (js/invite-field.js).
import './env.js';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inviteCode } from '../../frontend/js/invite-field.js';

test('a bare code, any case or spacing', () => {
  assert.equal(inviteCode('k7qm2xwp'), 'K7QM2XWP');
  assert.equal(inviteCode(' K7QM-2XWP '), 'K7QM2XWP');
});

test('the whole link', () => {
  assert.equal(inviteCode('https://nsusosed.ru/join#code=k7qm2xwp'), 'K7QM2XWP');
});

test('the message the code came in, preferring the word with a digit', () => {
  assert.equal(inviteCode('Here is the code: K7QM2XWP, see you'), 'K7QM2XWP');
  assert.equal(inviteCode('вот код ABCDEFGH и ещё K7QM2XWP'), 'K7QM2XWP');
});

test('half-typed input stays as typed', () => {
  assert.equal(inviteCode('k7q'), 'K7Q');
});

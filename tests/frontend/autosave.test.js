// Saves never overlap and the newest state wins (js/autosave.js).
import { fire } from './env.js';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { autosaver } from '../../frontend/js/autosave.js';

const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));

test('many quick calls make one save after the delay', async () => {
  let saves = 0;
  const soon = autosaver(async () => { saves += 1; }, 20);
  soon(); soon(); soon();
  assert.equal(saves, 0);
  await tick(40);
  assert.equal(saves, 1);
});

test('now() saves at once and resolves to what save returned', async () => {
  const soon = autosaver(async () => 'ok', 1000);
  soon();
  assert.equal(await soon.now(), 'ok');
});

test('saves run one after another, never at the same time', async () => {
  let running = 0;
  let overlap = false;
  const soon = autosaver(async () => {
    running += 1;
    if (running > 1) overlap = true;
    await tick(10);
    running -= 1;
  });
  await Promise.all([soon.now(), soon.now(), soon.now()]);
  assert.equal(overlap, false);
});

test('a failed save does not block the next one', async () => {
  let n = 0;
  const soon = autosaver(async () => { n += 1; if (n === 1) throw new Error('offline'); return n; });
  await assert.rejects(soon.now());
  assert.equal(await soon.now(), 2);
});

test('a save still waiting when the page is left is sent', async () => {
  let saves = 0;
  const soon = autosaver(async () => { saves += 1; }, 10_000);
  soon();
  fire('pagehide');
  await tick();
  assert.equal(saves, 1);
});

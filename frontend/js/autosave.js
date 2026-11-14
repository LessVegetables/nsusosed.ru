// Autosave: pages have no "Save" buttons; a change is sent as soon as it is made.

/**
 * Wrap a `save()` so it can be asked for as often as needed:
 *
 *   const saveSoon = autosaver(save, 1200);
 *   saveSoon();            // after typing: `delay` ms after the last call
 *   await saveSoon.now();  // after a click or leaving a field: right away
 *
 * Saves never overlap: one waits for the one before it, then sends the newest state. `save`
 * should skip the request when nothing changed, and handle its own ApiErrors.
 * `now()` resolves to what `save` returned. A save still waiting when the page is left is sent.
 */
export function autosaver(save, delay = 0) {
  let timer = null;
  let chain = Promise.resolve();
  const now = () => {
    clearTimeout(timer);
    timer = null;
    chain = chain.catch(() => {}).then(save);
    return chain;
  };
  const soon = () => {
    clearTimeout(timer);
    timer = setTimeout(now, delay);
  };
  soon.now = now;
  window.addEventListener('pagehide', () => { if (timer) now(); });
  return soon;
}

/** A text field saves a moment after typing stops, and at once when it is left. */
export function saveOnEdit(input, saveSoon) {
  input.addEventListener('input', () => saveSoon());
  input.addEventListener('change', () => saveSoon.now());
}

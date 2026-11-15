// Reporting to Umami's error tracking (the Errors tab at stat.gehrman.me).
// Uncaught exceptions and unhandled rejections are captured by the tracker itself; these
// helpers are for errors the code catches and would otherwise hide. They never throw, and do
// nothing when the tracker is blocked.
//
// The tracker is a deferred script after the page module, so it starts only once the page
// reaches its first `await` and can arrive after the first API call has already failed. Until
// it does, reports (and uncaught errors, tagged early=true) wait here; whatever is still waiting
// when the page finishes loading is sent then or dropped.

const pending = [];
const MAX_PENDING = 20;

const tracker = () => (typeof window.umami?.captureException === 'function' ? window.umami : null);

function flush() {
  const umami = tracker();
  for (const [error, options] of pending.splice(0)) {
    try { umami?.captureException(error, options); } catch { /* never break the page */ }
  }
}

if (document.readyState !== 'complete') {
  document.addEventListener('DOMContentLoaded', flush, { once: true });
  window.addEventListener('load', flush, { once: true });
  // The tracker adds its own listeners when it starts; until then, keep what it would miss.
  const early = (error) => {
    if (tracker() || document.readyState === 'complete') return;
    if (pending.length < MAX_PENDING) pending.push([error, { tags: { early: 'true' } }]);
  };
  window.addEventListener('error', (e) => { if (e.error) early(e.error); });
  window.addEventListener('unhandledrejection', (e) => early(e.reason));
}

export function report(error, { tags, fingerprint } = {}) {
  const umami = tracker();
  if (umami) {
    try { umami.captureException(error, { tags, fingerprint }); } catch { /* never break the page */ }
  } else if (document.readyState !== 'complete' && pending.length < MAX_PENDING) {
    pending.push([error, { tags, fingerprint }]);
  }
}

// For a catch that recovers on purpose: an ApiError is an expected answer from the server
// (and api.js already reports the 5xx ones), anything else is a bug in our code.
export function reportBug(error, tags) {
  if (error?.name !== 'ApiError') report(error, { tags });
}

// "/homes/3f2c…/photos/12?x=1" → "/homes/:id/photos/:id", so one broken endpoint is one issue.
export function routeOf(path) {
  return path.split('?')[0]
    .replace(/\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\/|$)/gi, '/:id')
    .replace(/\/\d+(?=\/|$)/g, '/:id');
}

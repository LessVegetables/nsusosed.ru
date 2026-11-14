// Umami's data-before-send hook (classic script, so it exists before the tracker sends anything).
// Umami already strips query strings and hashes from URLs and redacts emails, JWTs and
// "password=…"-style values from error reports. On top of that:
//   - invite codes (the "code=…" in a /join link) are redacted: a code lets anyone into a home;
//   - errors thrown by browser extensions are dropped: they aren't ours to fix.
// Wired up in every page as data-before-send="nsusosedBeforeSend". See frontend/README.md.
(function () {
  'use strict';

  var INVITE = /\bcode=[A-Za-z0-9-]+/g;
  var EXTENSION = /\b(?:chrome|moz|safari(?:-web)?|ms-browser)-extension:\/\//;

  function scrub(text) {
    return typeof text === 'string' ? text.replace(INVITE, 'code=[invite]') : text;
  }

  window.nsusosedBeforeSend = function (type, payload) {
    if (type !== 'error') return payload;
    if (EXTENSION.test(payload.stack || '')) return false;
    payload.message = scrub(payload.message);
    payload.stack = scrub(payload.stack);
    if (payload.tags) {
      for (var key in payload.tags) payload.tags[key] = scrub(payload.tags[key]);
    }
    return payload;
  };
})();

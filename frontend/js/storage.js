// Browser storage that never throws (private windows and in-app browsers can block it).

function area(kind) {
  try { return window[kind]; } catch { return null; }
}

function make(kind) {
  return {
    get(key) { try { return area(kind)?.getItem(key) ?? null; } catch { return null; } },
    set(key, value) { try { area(kind)?.setItem(key, value); } catch { /* blocked */ } },
    remove(key) { try { area(kind)?.removeItem(key); } catch { /* blocked */ } },
  };
}

export const local = make('localStorage');     // survives closing the browser
export const session = make('sessionStorage'); // this tab only

// Keys in one place.
export const KEYS = {
  lang: 'lang',           // local: the account's language, cached so pages don't flash; session: a guest's pick
  seenLogin: 'seenLogin', // local: this browser has logged in before → "/" skips the landing page
  flash: 'flash',         // session: i18n key prefix of a toast to show on the next page
};

// localStorage / sessionStorage can be missing or throw (private mode, blocked
// site data). Everything that touches them goes through these helpers, and the
// site must keep working when they return null.

function safe(storageName) {
  return {
    get(key) {
      try {
        return window[storageName].getItem(key);
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        window[storageName].setItem(key, value);
      } catch {
        // Not saved; fine.
      }
    },
    remove(key) {
      try {
        window[storageName].removeItem(key);
      } catch {
        // Nothing to do.
      }
    },
  };
}

export const local = safe('localStorage');
export const session = safe('sessionStorage');

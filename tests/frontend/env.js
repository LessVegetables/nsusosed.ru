// The little of a browser the frontend modules touch when imported and called outside a page.
// Import this first in every test file. `resetStorage()` gives each test empty storage;
// `blockStorage()` makes it throw, as private windows and some in-app browsers do.

class MemoryStorage {
  #items = new Map();
  getItem(key) { return this.#items.has(key) ? this.#items.get(key) : null; }
  setItem(key, value) { this.#items.set(key, String(value)); }
  removeItem(key) { this.#items.delete(key); }
  clear() { this.#items.clear(); }
}

const listeners = new Map();
const target = {
  addEventListener(type, fn) { (listeners.get(type) ?? listeners.set(type, []).get(type)).push(fn); },
  removeEventListener() {},
  dispatchEvent(event) { for (const fn of listeners.get(event.type) ?? []) fn(event); return true; },
};

let blocked = false;
const stores = { localStorage: new MemoryStorage(), sessionStorage: new MemoryStorage() };
const win = { ...target };
for (const kind of Object.keys(stores)) {
  Object.defineProperty(win, kind, {
    get() { if (blocked) throw new DOMException('blocked', 'SecurityError'); return stores[kind]; },
  });
}

globalThis.window = win;
globalThis.document = {
  ...target,
  readyState: 'complete',
  title: '',
  documentElement: { lang: 'ru', dataset: {} },
  querySelectorAll: () => [],
  querySelector: () => null,
};

export function resetStorage() {
  blocked = false;
  stores.localStorage.clear();
  stores.sessionStorage.clear();
}

export function blockStorage() { blocked = true; }

/** Fire a window event (e.g. 'pagehide') at the listeners the modules added. */
export function fire(type) { win.dispatchEvent({ type }); }

export { stores };

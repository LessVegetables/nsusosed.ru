// Frontend settings. There are no secrets here and there must never be any:
// everything in this folder is served to every visitor.

import { local } from './storage.js';

export const API_BASE = '/api';

// Only university addresses can log in (the backend checks this too).
export const EMAIL_DOMAIN = 'g.nsu.ru';

// The backend allows one code request per email every 60 s.
export const RESEND_COOLDOWN_SECONDS = 60;

// Matches per page on /matches.
export const MATCHES_PAGE_SIZE = 10;

// Mock API (see js/mock/). It only ever turns on for local development hosts,
// so a stray flag can't affect production. Turn it on with ?mock=1 and off
// with ?mock=0; the choice is remembered in localStorage.
const DEV_HOSTS = ['localhost', '127.0.0.1', '[::1]'];
const isDevHost = DEV_HOSTS.includes(location.hostname);

function readMockFlag() {
  if (!isDevHost) return false;
  const params = new URLSearchParams(location.search);
  if (params.has('mock')) {
    const on = params.get('mock') === '1';
    if (on) local.set('nsusosed.mock', '1');
    else local.remove('nsusosed.mock');
    params.delete('mock');
    const query = params.toString();
    history.replaceState(null, '', location.pathname + (query ? `?${query}` : '') + location.hash);
    return on;
  }
  return local.get('nsusosed.mock') === '1';
}

export const USE_MOCK = readMockFlag();

// The mock accepts this code for any @g.nsu.ru email.
export const MOCK_LOGIN_CODE = '123456';

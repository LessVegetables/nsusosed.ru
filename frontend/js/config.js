// Frontend settings. There are no secrets here and there must never be any:
// everything in this folder is served to every visitor.

export const API_BASE = '/api';

// Only university addresses can log in (the backend checks this too).
export const EMAIL_DOMAIN = 'g.nsu.ru';

// The backend allows one code request per email every 60 s.
export const RESEND_COOLDOWN_SECONDS = 60;

// Matches per page on /matches.
export const MATCHES_PAGE_SIZE = 10;

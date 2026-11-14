// "/" depends on who is asking:
//   never logged in here      → the landing page;
//   logged in, session alive  → their own page;
//   logged in before, expired → straight to /login (no landing).

import { ApiError, get } from '../api.js';
import { reportBug } from '../errors.js';
import { initPage } from '../layout.js';
import { homeFor } from '../routes.js';
import { KEYS, local, session } from '../storage.js';

async function destination() {
  if (!local.get(KEYS.seenLogin)) return null;
  try {
    return homeFor(await get('/me'));
  } catch (err) {
    // Server unreachable: better the landing page than a redirect loop.
    reportBug(err, { where: 'index' });
    return err instanceof ApiError && err.status === 401 ? '/login' : null;
  }
}

const go = await destination();
if (go) {
  location.replace(go);
} else {
  // A guest's pick lasts for this tab; the login page passes it on to the account.
  await initPage({ auth: 'none', onLangPick: (code) => session.set(KEYS.lang, code) });
}

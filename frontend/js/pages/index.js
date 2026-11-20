// "/" depends on who is asking:
//   never logged in here      → the landing page;
//   logged in, session alive  → their own page;
//   logged in before, expired → straight to /login (no landing).

import { ApiError, get } from '../api.js';
import { reportBug } from '../errors.js';
import { initPage } from '../layout.js';
import { homeFor, withCampaign } from '../routes.js';
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
  location.replace(withCampaign(go, location.search));
} else {
  // A guest's pick lasts for this tab; the login page passes it on to the account.
  await initPage({ auth: 'none', guestNav: true, onLangPick: (code) => session.set(KEYS.lang, code) });
  // "Take it together": the questionnaire opens with the link for a friend ready.
  document.getElementById('together').addEventListener('click', () => session.set(KEYS.together, '1'));
}

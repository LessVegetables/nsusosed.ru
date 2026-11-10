// Landing page. Stage 1 adds: skip it for people who have logged in before.
import { initPage } from '../layout.js';
import { mountLangSwitch } from '../lang-switch.js';
import { KEYS, session } from '../storage.js';

await initPage({ auth: 'none' });
// A guest's pick lasts for this tab; the login page passes it on to the new account.
mountLangSwitch(document.getElementById('lang'), { onPick: (code) => session.set(KEYS.lang, code) });

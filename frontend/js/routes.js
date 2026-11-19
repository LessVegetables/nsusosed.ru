// Where a logged-in person belongs right now: "their" page.
//   a friend's compare link opened in this tab → the compare page (it joins, then sends
//     them on to the questionnaire: the friend sees the progress from the start);
//   no questionnaire yet (or a new version came out) → the questionnaire;
//   questionnaire done but never said what they came for → the questionnaire page asks;
//   an invite link opened in this tab → the join page;
//   hosts → their home; invited people → the join page; only comparing → the compare page;
//   seekers → the feed on their tab.

import { KEYS, session } from './storage.js';

/** Right after logging in: back to the page the guest opened, otherwise their own page.
 *  The page itself sends them on if it needs the questionnaire first. */
export function afterLogin(user) {
  const back = session.get(KEYS.back);
  session.remove(KEYS.back);
  return back?.startsWith('/') && !back.startsWith('//') && back !== '/login' ? back : homeFor(user);
}

export function homeFor(user) {
  if (session.get(KEYS.compare)) return '/compare';
  // The questionnaire comes first even with an invite in hand: residents are what seekers
  // are matched against.
  if (!user.questionnaire_complete) return '/questionnaire';
  if (session.get(KEYS.invite) && !user.home_id) return '/join';
  if (!user.intent) return '/questionnaire';
  // Hosts go to their home: the form if it isn't listed yet, the listing if it is.
  if (user.intent === 'host' || user.home_id) return '/home';
  if (user.intent === 'join') return '/join';
  if (user.intent === 'compare') return '/compare';
  return user.intent === 'seek_apt' ? '/feed?kind=apartment' : '/feed?kind=dorm';
}

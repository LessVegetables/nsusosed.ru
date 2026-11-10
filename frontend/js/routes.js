// Where a logged-in person belongs right now: "their" page.
//   no questionnaire yet (or a new version came out) → the questionnaire;
//   questionnaire done but never said what they came for → the questionnaire page asks;
//   an invite link opened in this tab → the join page;
//   hosts → their home; invited people → the join page; seekers → the account page until
//   the feed exists (stage 5).

import { KEYS, session } from './storage.js';

export function homeFor(user) {
  // The questionnaire comes first even with an invite in hand: residents are what seekers
  // are matched against.
  if (!user.questionnaire_complete) return '/questionnaire';
  if (session.get(KEYS.invite) && !user.home_id) return '/join';
  if (!user.intent) return '/questionnaire';
  // Hosts go to their home: the form if it isn't listed yet, the listing if it is.
  if (user.intent === 'host' || user.home_id) return '/home';
  if (user.intent === 'join') return '/join';
  return '/account';
}

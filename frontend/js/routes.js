// Where a logged-in person belongs right now: "their" page.
//   no questionnaire yet (or a new version came out) → the questionnaire;
//   questionnaire done but never said what they came for → the questionnaire page asks;
//   hosts → their home; seekers and invited people → the account page until the feed and
//   invites exist (stages 4–5).

export function homeFor(user) {
  if (!user.questionnaire_complete || !user.intent) return '/questionnaire';
  // Hosts go to their home: the form if it isn't listed yet, the listing if it is.
  if (user.intent === 'host' || user.home_id) return '/home';
  return '/account';
}

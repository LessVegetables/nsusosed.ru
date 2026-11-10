// Where a logged-in person belongs right now: "their" page.
//   no questionnaire yet (or a new version came out) → the questionnaire;
//   questionnaire done but never said what they came for → the questionnaire page asks;
//   otherwise by intent. The feed and the home pages arrive in stages 3–5; until then
//   everyone lands on the account page.

export function homeFor(user) {
  if (!user.questionnaire_complete || !user.intent) return '/questionnaire';
  return '/account';
}

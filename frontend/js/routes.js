// Where a logged-in person belongs right now: "their" page.
// Later stages extend this (questionnaire → feed / own home / join).

export function homeFor(user) {
  void user;
  return '/account';
}

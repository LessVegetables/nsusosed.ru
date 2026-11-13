# nsusosed.ru

Find roommates at NSU who live the way you do.

A closed website for NSU students. You answer a short questionnaire about your everyday habits. The site then shows dorm rooms and apartments with free places, ranked by how well your habits match the people who already live there.

[Русская версия](README_RU.md)

**Status: pilot.** The MVP proved the tech; this version is being prepared for its first real users. Nothing from the MVP was migrated.

## The problem

- **Dorms.** At check-in, the dorm manager lists free rooms by number ("122, 512, 412 or 302?"). You pick without knowing who lives there, and you find out how they live only after moving in.
- **Apartments.** When flatmates move out, whoever is left pays for the empty rooms. Chats, flyers and rental sites don't help you find another student from your own university.

## Principles

- **It connects people; it does not collect data about them.** All communication happens off the site, in the messengers people already use.
- **No addresses, ever.** A dorm listing knows its building; its room number is stored only so the same room can't be listed twice and is never shown. An apartment is stored as a district and a circle a few hundred meters wide that the host's own browser moved off the real spot; the address never reaches the database.
- **Hidden answers stay hidden.** Some questionnaire answers are visible in a profile, some are for the algorithm only. Scores are shown as a percent rounded to 5 and five coarse badges, so a hidden answer can't be worked out from them.
- **Hosts and seekers.** A *host* lives somewhere with a free place; a *seeker* is looking for one. One person can be both.

## How it works

1. **Log in** with an NSU email (`@nsu.ru` or any subdomain, such as `@g.nsu.ru`). There are no passwords: we email a one-time code. First-timers give their name while the code is on its way. The session lasts about three months.
2. **The questionnaire** (version 1: 20 questions, 16 required): sleep, tidiness, noise, guests, nicotine and smells, evenings, sharing, how you bring up problems. Before it, three facts: gender, faculty and whether you are 18 (we never ask a birth date). Under-18s are not asked about nicotine.
3. **What are you here for?** Looking for a dorm place, looking for a room in an apartment, offering a place, or joining a place by invite. That decides the page you land on from then on.
4. **Seekers** get a feed with two tabs, dorm and apartments, best match first. Dorm rooms are limited to the buildings of their faculty and every list to rooms they could move into, until they ask to see the whole campus or all rooms. A room's page has photos, a map (the dorm building exactly; an apartment as an approximate area), the people who live there with their bios, compatibility with each of them, and a button that reveals the hosts' contacts.
5. **Hosts** list a dorm room or an apartment with one or more rooms, each with its own rent. Every room gets three emojis in place of a number, unique across the site. Hosts invite the roommates they already live with by link; each host has their own rights (edit the listing, photos, invites, manage residents).
6. **Contacts** belong to people, not listings: phone, Telegram or VK as the main ones, plus Max, Instagram, Snapchat and WeChat as extras. A listing becomes visible once a host has a main contact.

## Compatibility

Described for users at `/compatibility` and in full in `questionnaire/` (kept next to this repo). In short: a few combinations are never shown at all (for example a cigarette smoker and someone smells make unwell); one person's habit is compared with the other's tolerance in both directions and the worse direction counts; five topics (sleep, tidiness, quiet and guests, air and smells, living together) are combined as 0.7 × the weighted mean + 0.3 × the worst topic. A room's score blends the average over its residents with the worst one.

The questionnaire is versioned: each version has its own questions, scoring values and scorer in `backend/app/questionnaires/vN/`. Values the spec does not give are marked `PROVISIONAL` in `v1/scoring.json`.

## Not in the pilot

- Stale listings and stale accounts (no expiry rules yet)
- A bot check before contacts are shown
- Built-in chat, booking, payments, official room allocation
- Universities other than NSU; mobile apps

See [BACKLOG.md](BACKLOG.md) for the full list of things put off.

## Stack and layout

FastAPI + PostgreSQL, plain HTML/CSS/JS with no framework and no build step, nginx, one VPS. Login emails go through Yandex Cloud Postbox. Maps are Leaflet with OpenStreetMap tiles; address search goes through OpenStreetMap's Nominatim. No AI models; the score is arithmetic.

| Folder | What |
|---|---|
| [`backend/`](backend/README.md) | The API, migrations, tests |
| [`frontend/`](frontend/README.md) | The site |
| [`design/`](design/README.md) | The design system ("D · Neo-brutalism") and its specimen page |
| [`deploy/`](deploy/README.md) | Server setup and the release flow (`main` → PR → `deploy`) |

Interface languages: Russian, English, Chinese. Light and dark themes.

## Team

| | Role |
|---|---|
| Daniel Gehrman | Business hypothesis, development and deployment |
| Nikita Bezborodov | Architecture, technical spec |
| Anton Bykov | Development, MVP demo |

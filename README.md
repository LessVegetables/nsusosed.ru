# nsusosed.ru

Find roommates at NSU who live the way you do.

A closed website for NSU students. You fill in a short questionnaire about your daily habits. The site then shows dorm rooms and apartments with free places, ranked by how well your habits match the people who already live there.

[Русская версия](readme_ru.md)

## The problem

- **Dorms.** At check-in, the dorm manager lists free rooms by number ("122, 512, 412 or 302?"). You pick without knowing who lives there, and you find out how they live only after moving in.
- **Apartments.** When flatmates move out, whoever is left pays for the empty rooms. Chats, flyers and rental sites (CIAN, Avito) don't help you find another student from your own university.

## Who it's for

1. **First-years moving into a dorm.** They choose a room based on the people already in it.
2. **Residents with a free place in their room.** They want someone with a similar routine to move in.
3. **Students renting an apartment with a free room.** They want to fill it with an NSU student.

## How it works

1. **Sign up or log in** with an `@g.nsu.ru` email. There are no passwords: every time, we email a one-time code that's valid for 2 minutes. On sign-up you also agree to the personal-data policy.
2. **Fill in the questionnaire** (9 questions). For each habit you give:
   - your own answer;
   - how important it is to you (1–10);
   - optionally, a **hard condition**: the answers you won't accept from a roommate (for example, "no smoking in the room").

   At the end you say what you're after (a place, or a roommate for your room or apartment). If you're looking for an apartment, you also give your monthly budget.
3. **List your room or apartment** if you already live somewhere with a free place, then send your roommates an invite link so their answers count too. Each person can have one listing and be a resident of one room. The author confirms the listing every 30 days, otherwise it's hidden.
4. **Browse matches.** You see rooms with free places, sorted by compatibility %, with a short explanation (e.g. "sleep matches, cleaning differs").
5. **Contact the author.** Each listing shows one contact: Telegram, WhatsApp, Max, a phone number, whatever the author chose. Moving in is arranged outside the site.

## The 3 core features

| # | Feature | Done when |
|---|---|---|
| F1 | **Questionnaire.** Passwordless login with an email code; the 9-question questionnaire, which you can edit later | A user can log in with a code, save their answers and change them |
| F2 | **Room / apartment listing.** Dorm: building, room, floor, capacity, occupied places, corner room, windows, view, layout. Apartment: district, monthly cost per person. Plus a description and contact. Residents join through an invite link | A listing exists, with its residents attached |
| F3 | **Matches + contact.** Filtered and sorted list with an explanation of each score; the contact is shown on the listing | A user sees the rooms that suit them and can reach the author |

Also in the MVP: login/logout, editing and pausing a listing, deleting your account, Russian + English interface, layout that works on phones and computers.

## Matching rules

- **Questions:** sleep time, night noise, cleaning, guests, smoking in the room, alcohol in the room, studying in the room, airing, temperature.
- **Hard conditions filter first, in both directions.** If even one resident breaks your hard condition, or you break theirs, the room is hidden, however high its average.
- **Apartments:** hidden if the price per person is above your budget.
- **Room profile:** the average of the residents who filled in the questionnaire. If only some have, the card says "2 of 3 residents answered".
- **Score (0–100%):** answer similarity on each question, weighted by how important it is to both sides. It's a similarity index, not a guarantee that you won't have conflicts.
- Rooms with no free places, no answered residents, or a listing older than 30 days aren't shown.

## Not in the MVP

- Forming a group *before* anyone has an apartment (we only list existing apartments with free rooms)
- Built-in chat, booking, or official room allocation (the dorm manager still decides)
- Payments, including paid apartment listings
- Universities other than NSU; mobile apps

## Stack

FastAPI + PostgreSQL, plain HTML/CSS/JS (no framework), Nginx, one VPS at Selectel. Confirmation emails go through Yandex Cloud Postbox. No AI models; the score is a simple formula.

## Open questions

- [ ] Final wording of the 9 questions and their answer scales
- [ ] Dispute over who owns a room's listing: who on the team handles it, and how users reach them

## Team

| | Role |
|---|---|
| Daniel Gehrman | Business hypothesis, Development and Deployment |
| Nikita Bezborodov | Architecture, technical spec |
| Anton Bykov | Development and Development, MVP demo |

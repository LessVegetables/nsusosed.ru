# Room page: layout options

Six layouts for `/room`, made on 2026-11-15 to choose a new one. Each is shown at desktop and phone
width, for an apartment or a dorm room, with 1 to 8 photos (including a single portrait photo),
four gallery styles, and the light and dark themes.

```bash
python3 design/room_page_options/server.py 8090
```

Then open <http://localhost:8090/>. Standard library only; no backend or database needed.

**Chosen: E · Bento with the "Main + thumbs" gallery** (the viewer opens on it).

| Option | Idea |
|---|---|
| A · Now | The page as it was on 2026-11-15 (the real `room.js` against the mock API) |
| B · Sticky summary | Content scrolls on the left; score, facts and the contacts button follow on the right |
| C · Photo mosaic | Photos across the full width; with one photo the empty half becomes the map |
| D · People first | Score and resident cards take the wide column; photos, description and map sit beside |
| E · Bento | Each fact is its own tile: photo, title, score, price, contacts |
| F · Tabs | Summary on top; residents, description and map are tabs |

## What is here

| Path | What |
|---|---|
| `server.py` | Serves `site/` with clean URLs and a mock `/api` (`/me`, `/meta`, `/questionnaire`, `/rooms/{id}`). Room ids: `flat-5`, `dorm-1`, `flat-1p` (p = the single photo is a portrait one) |
| `site/options.html`, `shell.js`, `shell.css` | The viewer: the controls and the two previews |
| `site/layout.html`, `options.js`, `options.css` | The layouts B–F, built from the site's own modules and tokens (`/layout?opt=E&id=flat-5&gallery=thumbs&theme=light`) |
| `site/mock/` | Placeholder photos (drawn, in 4:3, 3:4, 16:9 and 1:1), the questions, the dorm list |
| everything else in `site/` | **A snapshot of `frontend/` from that day**, so the mockups keep working as the site changes. Not kept in sync; don't edit the site here |

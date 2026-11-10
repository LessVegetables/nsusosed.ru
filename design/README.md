# nsusosed.ru design system: "D · Neo-brutalism"

The visual language for the rewritten nsusosed.ru: thick black outlines, hard shadows, flat bright fills with black text, heavy type, and a little playful tilt. It comes from option D of the twelve design templates (`temp_frontend/d/`, live at <https://demo.nsusosed.ru/d/>).

| File | What it is |
|---|---|
| `README.md` | This spec: the rules and the reasons behind them |
| [`nsusosed.css`](nsusosed.css) | **The one stylesheet.** Tokens at the top, then base styles, components and utilities |
| [`specimen.html`](specimen.html) | Every token and component on one page, with theme and RU/EN/中文 switches |
| `specimen.css`, `specimen.js` | Layout and behavior for the specimen page only (not part of the system) |

To view the specimen, serve this folder and open `specimen.html` (opening the file directly won't run its script):

```bash
npx serve design
```

The language switch on the specimen only swaps a few sample strings (headline, lead, a card) to check fonts and line breaks; it isn't a translation of the page.

**Status.** The light theme and all components come from template D as it was approved. Anything D did not have is marked **NEW** below and in the CSS: the dark theme, focus/error/disabled/busy states, the hover grace zone, Chinese text, and reduced motion. **The dark theme uses Dark 3 · light cards by default; Dark 1 and Dark 2 are kept as alternatives until a final decision** (section 3).

---

## 1. Changing the design later: one file

Everything that defines the look lives in **section 1 of `nsusosed.css`** as CSS custom properties ("tokens"). Components never contain raw colors, fonts or sizes; they only reference tokens. So:

| To change… | Edit this token (section 1) |
|---|---|
| A color everywhere | `--yellow`, `--pink`, … (or point a meaning elsewhere: `--primary: var(--pink)`) |
| What "match / partial / mismatch" look like | `--match`, `--partial`, `--mismatch` |
| Page, card and text colors (per theme) | `--page`, `--page-text`, `--surface`, `--text`, `--edge`, … |
| Fonts | `--font`, `--mono`, `--cjk` |
| Heading or text sizes | `--fs-display`, `--fs-title`, `--fs-card`, `--fs-body`, … |
| Boldness | `--w-body` … `--w-black` |
| Outline thickness | `--line-w`, `--line-w-thin` |
| Roundness | `--r-xs`, `--r-sm`, `--r`, `--r-lg`, `--r-pill` |
| Shadow depth | `--depth-sm`, `--depth`, `--depth-lg` |
| The playful tilts | `--tilt-logo`, `--tilt-highlight`, `--tilt-badge`, `--tilt-unfit`, `--tilt-toast` (0deg = straight) |
| Button movement | `--hover-lift` (0px = buttons don't move), `--press-depth`, `--press` (speed) |
| Page width, gutters, section spacing | `--wrap`, `--gutter`, `--section-y`, `--gap` |

Component internals (a card's 16px padding, a chip's 3px × 8px) are deliberately not tokens: they are details of one component, not design decisions, and making everything a token would make the file harder to read than the 30-stylesheet setup it's meant to replace.

**Rules that keep it to one file:**

- The site links exactly one design stylesheet: `nsusosed.css`.
- Page-specific CSS is the exception, kept small, and written inside `@layer pages { … }`. It may arrange components on a page but never defines colors, fonts or sizes; if it needs a new one, that becomes a token here.
- No inline styles (the CSP forbids them anyway); color blocks with `.fill-*` classes.
- **Cascade layers** fix precedence by layer, not by position in the file or by selector cleverness: `tokens < base < components < pages < utilities`. A `.fill-blue` always wins over a component's background; a page rule always beats a component rule. (This avoids a bug we already hit once: a fill class placed above `.box` lost to it.)

## 2. Character and principles

Loud, friendly and very clear. Blocks look like stickers cut from colored paper and stuck on graph paper. It should feel like a student project done with confidence, not like a bank or a startup dashboard. Decoration never gets in the way of understanding what the service does: when the demo's hero collage of overlapping cards confused people on phones, it was replaced by one clean card.

1. **Every block is a box.** Outline 3px, radius 10px, hard shadow 5px down-right with no blur. No soft shadows, gradients or glass.
2. **Color is a flat fill, and text on a fill is black.** Fill colors are never text colors (red text on white is only 2.8:1).
3. **Color has fixed meanings.** Green = matches, yellow = partly matches, red = doesn't match / error. Always say it in words too ("совпадает", "немного отличается"), never color alone.
4. **Heavy type.** Rubik 800–900 for headings and buttons; JetBrains Mono in uppercase for labels, meta lines and anything typed (email, code).
5. **Things behave physically.** Buttons lift on hover and sink into their shadow when pressed; selected tabs and options stay pressed in.
6. **Tilt is a spice.** A few elements are rotated a couple of degrees (logo badge, headline highlight, % badge, toast). At most one or two tilted things in view at once; never tilt body text, inputs or buttons.
7. **Clarity beats decoration.** No decorations that cover content; on phones, one idea per block, stacked. (The spinning "10 вопросов" star was removed for this reason.)

## 3. Color

### Fills (same in every theme)

| Token | Hex | Meaning / use | Black text on it |
|---|---|---|---|
| `--yellow` | `#ffd43b` | Primary action, selected option, current step, "partial" | 14.7:1 |
| `--pink` | `#ff8fab` | Accent action ("Show contacts"), logo, multi-select "on", slider fill | 9.8:1 |
| `--blue` | `#74c0fc` | Informational blocks (code step), card tops | 10.7:1 |
| `--green` | `#8ce99a` | Match, success, revealed contacts, toast | 14.2:1 |
| `--purple` | `#b197fc` | The questionnaire panel | 8.7:1 |
| `--orange` | `#ffa94d` | Extra card-top color | 11.0:1 |
| `--red` | `#ff6b6b` | Mismatch, hard condition, errors | 7.6:1 |

All pass WCAG AAA (7:1) with black text. Components use the meanings, not the raw fills: `--primary`, `--accent`, `--match`, `--partial`, `--mismatch`, `--info`, `--quiz`. Card tops cycle through blue, pink, orange, green, purple; the color of a card top carries no meaning.

### Page, surfaces, text, edges (these change per theme)

| Token | Light | Use |
|---|---|---|
| `--page` | `#fef6e4` | Page background (with a 28px grid at 5% opacity, `--grid-line`) |
| `--page-text` | `#000000` | Text directly on the page (section titles, intros) |
| `--surface` | `#ffffff` | Boxes, inputs, tags |
| `--text` | `#000000` | Text on surfaces |
| `--edge` | `#000000` | Every outline and every hard shadow |
| `--on-fill` | `#000000` | Text on any color fill (all themes) |
| `--black` / `--on-black` | `#000` / yellow | Always-black badges: ticker, % badge, timer, slider readout, selected tab |
| `--soft` | `#fff4c2` | Warning notes |
| `--unfit` / `--unfit-2` | `#eee` / `#ddd` | Cards that don't fit (striped top) |
| `--field-focus` / `--error-soft` | `#fffbe0` / `#ffe3e3` | Focused / invalid text field |

Splitting "text" from "edge" (and "page text" from "text on surfaces") is what lets a dark theme keep black outlines with cream text, or dark text on light cards over a dark page.

### Dark theme (NEW, three candidates)

The first dark version inverted everything: cream outlines, cream shadows and cream text on near-black. It felt heavy because every 3px outline and every shadow became a glowing light line, and bold light text on black looks even bolder than it is. Three alternatives, switchable on the specimen:

| Candidate | `data-theme` | Idea |
|---|---|---|
| **Dark 1 · dimmed** | `dark-dim` | "Lights dimmed", not inverted: charcoal page `#2b261f`, dark-brown boxes `#3a342b`, cream text, but outlines and shadows stay black, so they read as real shadows instead of glowing lines |
| **Dark 2 · muted lines** | `dark-muted` | Darker page and boxes; outlines and shadows in a mid-tone tan `#857b69` instead of bright cream |
| **Dark 3 · light cards** (default) | `dark` or `dark-cards` | Dark board `#39332b`; boxes stay pale (`#e9e0cb`) with black text and black outlines, like the blue "Шаг 2 · код" card that looked right |

All three keep the color fills unchanged with black text, and every text pair is at least 8:1. **Dark 3 is the default:** the system dark setting and `<html data-theme="dark">` use it, and new pages should be designed against it. Dark 1 and Dark 2 stay in the CSS for comparison (`data-theme="dark-dim"` / `"dark-muted"`); once the decision is final, delete the unused blocks from section 1.

## 4. Typography

**Fonts.** Rubik (500–900) and JetBrains Mono (500, 700) cover Latin and Cyrillic. Chinese falls back to **Noto Sans SC** (500, 700, 900), then the system's PingFang SC / Microsoft YaHei.

| Role | Class | Size token | Weight | Line height | Case |
|---|---|---|---|---|---|
| Display (hero) | `.display` | `--fs-display` 42–84px | 900 | .95 | Sentence |
| Section title | `.title` | `--fs-title` 32–54px | 900 | 1 | Sentence |
| Question | `.question` | `--fs-question` 26–40px | 900 | 1.05 | Sentence |
| Panel heading | `.auth h3`, `.info h3` | `--fs-panel` 30px | 900 | 1.05 | Sentence |
| Card title | `.card h3` | `--fs-card` 22px | 900 | 1.1 | Sentence |
| Lead | `.lead` | `--fs-lead` 19px | 500 | 1.5 | Sentence |
| Body | (default) | `--fs-body` 16px | 500 | 1.5 | Sentence |
| Button | `.btn` | 16px | 800 | — | UPPERCASE (CSS) |
| Tag / meta | `.tag`, `.meta` | `--fs-label` 12px mono | 700 | 1 | UPPERCASE (CSS) |
| Big number | `.big-pct` | `--fs-number` 64px | 900 | 1 | — |

Headings use tight tracking (`--track-tight`, −.03em); uppercase mono labels use `--track-caps` (.06em).

**Writing.** Write every string in sentence case in HTML and translation files; uppercase comes only from CSS. That keeps translations clean, and Chinese has no case anyway. Russian: «ёлочки» quotes, a non-breaking space before ₽ and between a number and its unit (`14 500 ₽`, `4 этаж`), an em dash with spaces.

## 5. Lines, corners, shadows

| Token | Value | Use |
|---|---|---|
| `--line-w` | 3px | Box, button, input, tab, card outlines |
| `--line-w-thin` | 2px | Tags, chips, notes (dashed), facts dividers, toggle chips |
| `--r-xs` / `--r-sm` / `--r` / `--r-lg` / `--r-pill` | 6 / 8 / 10 / 12 / 999px | Chips & checkboxes / notes, photos, logo / boxes, buttons, inputs / headline highlight / tags |
| `--sh-sm` / `--sh` / `--sh-lg` | 3 / 5 / 8px down-right | Tabs, pager, toggles / boxes, buttons, options / hovered cards, toast |

## 6. Layout and spacing

- Container `.wrap`: max `--wrap` 1180px, side padding `--gutter` 20px (16px on phones).
- Sections: `--section-y` 56px top and bottom. Section header `.shead`: eyebrow tag + title, actions (tabs) on the right.
- Gaps: cards `--gap` 24px · steps 20px · options and button rows 14px · chips 6px · inside a box 16–24px.
- Breakpoints: **960px** (listing and auth stack; cards 2 columns; steps 2×2) and **640px** (everything single column, header nav hidden).

| | > 960px | 641–960px | ≤ 640px |
|---|---|---|---|
| Match cards | 3 columns | 2 | 1 |
| Steps | 4 | 2 | 1 |
| Breakdown tiles | 5 | 2 | 2 |
| Listing (gallery + info) | side by side | stacked | stacked |
| Quiz options | 2 | 2 | 1 |

## 7. Motion and hover

| What | How |
|---|---|
| Button hover | Lifts `--hover-lift` (2px) up-left; its shadow grows to match. Only on devices with a real pointer (`@media (hover: hover)`), so taps don't leave buttons stuck "lifted" |
| Button press | Sinks `--press-depth` (5px) into its shadow; shadow disappears. 80ms |
| Selected option or tab | Stays pressed in |
| Card hover | Lifts `--card-lift` (3px); shadow grows to 8px |
| Toast | Pops in with an overshoot, 0.4s |
| Ticker | Marquee, 26s per loop |

**Hover grace zone (NEW).** A button that moves on hover can slip out from under a cursor resting on its edge; it un-hovers, moves back, hovers again, and jitters. The fix works like hysteresis in a debounced input: there are two borders. To start hovering, the cursor must cross the real edge. Once hovered (or pressed), an invisible extension (`::before`) grows the hit area by `--hover-grace`, 6px past the edge. That's more than the 2px lift and the 5px press, so the button can't move out from under the cursor. To stop hovering, the cursor has to leave that bigger area. Tested: at 1px inside the right edge the old version flickered on and off; with the grace zone it stays hovered. The same applies to match cards and to pressing, so a click on the edge isn't lost when the button sinks. If you'd rather have no movement at all, set `--hover-lift: 0px` (and `--card-lift: 0px`).

**Reduced motion (NEW):** with `prefers-reduced-motion`, the ticker stops, the toast appears without the pop, and nothing moves on hover.

## 8. Components

All in `nsusosed.css`, all shown in the specimen. States come from ARIA attributes (`aria-pressed`, `aria-selected`, `aria-current`, `aria-invalid`, `aria-busy`, `disabled`), so scripts set attributes, not classes.

| Component | Markup | Variants and states |
|---|---|---|
| Box | `.box`, `.box.pad` | Any container; paint with a `.fill-*` class |
| Button | `<button class="btn">` or `<a class="btn">` | Primary (yellow), `.secondary` (surface), `.accent` (pink), `.dark` (inverted). Disabled; `aria-busy="true"` adds a spinner |
| Text button | `.linkbtn` | Small underlined action ("Изменить почту") |
| Tag | `.tag` | Eyebrows over titles, card badges, step labels |
| Meta / count | `.meta`, `.count` | Mono uppercase info lines |
| Chips | `.chips > .chip.match / .partial / .mismatch` | One per questionnaire topic on a match card |
| Note | `.note`, `.note.error`, `.note.success` | Dashed. Start with ⚠, ✕ or ✓ |
| Headline highlight | `<mark class="highlight">` | Yellow tilted block behind a key phrase |
| Header | `.site-header > .wrap > .logo + .site-nav + .btn` | Sticky. Current page: `aria-current="page"` |
| Ticker | `.ticker > div > span…` | Repeat items twice for a seamless loop; `aria-hidden="true"` |
| Tabs | `.tabs[role=tablist] > [role=tab][aria-selected]` | Selected: black with yellow text, pressed in |
| Checkbox | `<label class="check"><input type="checkbox"><span>…</span></label>` | Yellow with ✓ when checked |
| Text field | `<label class="field">Label<input>…<small>hint</small></label>` | Focus: pale yellow + shadow. Invalid: `aria-invalid="true"` + `<span class="error">` |
| Code input | `.code > input×6` | Focused cell yellow; `aria-invalid` on `.code` |
| Timer | `.timer > b` | Time in a black badge |
| Match card | `a.card.box > .top.fill-* (.tag + .pct) + .body (h3, .meta, .chips, .note)` | `.unfit`: gray, striped top, red "doesn't fit" badge |
| Pager | `.pager > a / span[aria-current=page]` | Current page yellow |
| Gallery | `.box.gallery > .main + .thumbs > button[aria-pressed]` | Selected thumbnail lifted with a yellow ring |
| Info panel | `.box.info > .tag + .score + .facts + .btn` | |
| Facts | `.facts > div > small + b` | Two-column labelled values in one outline |
| Contacts | `.contact-box` | Green; shown after "Показать контакты" |
| Breakdown | `.breakdown > div.match / .partial / .mismatch > small` | One tile per topic, with words |
| Questionnaire | `.box.quiz > .quiz-top + .question + .opts + .sub + .hard + .qnav` | Purple panel; progress `.prog > i.done / i.now / i` |
| Options | `.opts[data-choice=single] > button[aria-pressed]` | Chosen: yellow, pressed in, black dot |
| Toggle chips | `.tog > button[aria-pressed]` | Multi-select; on = pink |
| Slider | `.range > input[type=range] + output` | Script sets `--fill` on input |
| Hard condition | `.box.hard > .check` | Red panel |
| Steps | `.steps > .box > .n + h3 + p` | Number badge cycles yellow, pink, blue, green |
| Toast | `.toast[role=status] > b + text + button.close` | Green; `.error` red; phones: full width |
| Footer | `.site-footer` | Yellow band |
| Fills | `.fill-yellow / pink / blue / green / purple / orange / red` | Background + black text, instead of inline styles |

**Icons.** Text glyphs only: → ← ✓ ✕ ⚠ ★ ×. If real icons are needed later, use a heavy outline set (2–3px strokes) colored with `--text`.

## 9. States

| State | Look |
|---|---|
| Keyboard focus (NEW) | 3px outline in `--focus-ring`, 3px outside the element |
| Hover | Buttons and cards lift (with the grace zone); nav links get a yellow box |
| Pressed / selected | Moved into the shadow; yellow (single choice), pink (multi), black (tab) |
| Current page | `aria-current="page"`: yellow (nav, pager) |
| Disabled (NEW) | 50% opacity, no shadow, no movement |
| Busy (NEW) | `aria-busy="true"` on a button adds a small spinner |
| Invalid (NEW) | Field turns pink-red; red error chip under it |
| Warning / doesn't fit / success | `.note` / `.card.unfit` + `.note.error` / `.toast`, `.note.success`, `.contact-box` |

Not designed yet: loading skeletons, empty states ("Нет подходящего жилья"), photo upload, error pages, and the phone menu. Build them from boxes, notes and tags in the same style.

## 10. Phones

- One column, 16px gutters, nothing wider than the screen (`html, body { overflow-x: clip }` stops tilted elements from causing sideways scrolling).
- No overlapping decoration; anything with `.decor` is hidden at ≤ 640px. One clear card instead of a pile.
- Tap targets at least 44px (buttons 48px, tabs 44px, toggles 40px with spacing).
- The header nav is hidden at ≤ 640px. **The rewrite needs a phone menu** (menu button or bottom bar); D didn't have one.
- Toasts span the width with 16px margins.

## 11. Languages (RU / EN / 中文)

- Set `<html lang="ru">`, `"en"` or `"zh-CN"`; the CSS adjusts Chinese via `:lang(zh)`.
- Design for Russian: it's the longest. English is about 15–25% shorter; Chinese much shorter but taller per line.
- Chinese gets body line height 1.7, headings 1.25, no negative tracking, and side margin around the headline highlight (no spaces between words).
- No text inside images; every string comes from the translation files, in sentence case.

## 12. Accessibility

- Contrast: every text/background pair in the light theme and all three dark candidates is at least 7:1 (AAA), apart from disabled controls, which are faded on purpose. Fills are never text colors.
- Keyboard: every interactive element shows the focus outline; tabs, options and toggles are real `<button>`s with ARIA state.
- Meaning never comes from color alone: match tiles and chips carry words; warnings carry ⚠ / ✕.
- Decoration (ticker) is `aria-hidden="true"`.
- Respect `prefers-reduced-motion` and `prefers-color-scheme`.

## 13. Production notes

- **Strict CSP:** no inline `<style>`, `style="…"` or inline scripts. Color blocks with `.fill-*` classes. Setting a custom property from JS (`el.style.setProperty('--fill', '60%')`) is fine; CSP doesn't block that.
- **Fonts:** self-host WOFF2: Rubik 500–900 (or the variable font), JetBrains Mono 500 and 700, Latin + Cyrillic subsets, `font-display: swap`. Noto Sans SC is large (several MB per weight): load it only on the Chinese version, ideally subset, and preload nothing but Rubik 900.
- **Browser support:** cascade layers, `:is()`, `:lang()` and `@media (hover: hover)` work in every browser from 2022 on.

## 14. Do and don't

| Do | Don't |
|---|---|
| Black text on color fills | Colored text, gray text on colors |
| One meaning per color (green / yellow / red) | Red as decoration, yellow for errors |
| Hard shadows down-right | Blurred or colored soft shadows, gradients |
| 1–2 tilted elements per screen | Tilting body text, inputs, buttons or whole sections |
| Uppercase via CSS | Typing strings in capitals |
| One clean card on phones | Overlapping piles, spinning stickers |
| `.fill-*` classes | `style="background: …"` |
| A new color or size as a token in section 1 | One-off hex values or sizes in page CSS |

## 15. Working from this reference (people and AI assistants)

If you are building or changing the site's UI, follow these rules:

1. **Read this whole README first**, then skim `nsusosed.css` and open `specimen.html`.
2. **Link only `nsusosed.css`** for design. Copy it into the site (e.g. `frontend/css/nsusosed.css`) rather than rewriting it.
3. **Use the existing classes and markup patterns** from section 8 and the specimen. Most needs are a box with a tag, a title and a note.
4. **Never write raw colors, fonts or sizes** in page CSS or markup. Use tokens (`var(--…)`) and `.fill-*` classes. If something truly new is needed, add a token to section 1 of `nsusosed.css` and say so.
5. **Page-specific CSS goes in `@layer pages { … }`**, kept small: layout only.
6. **No inline styles or scripts** (strict CSP).
7. **Every new component goes in three places:** the components layer of `nsusosed.css`, `specimen.html`, and the table in section 8 here.
8. **Check both themes** (light, and dark = Dark 3) and a 375px-wide screen before calling a page done.
9. **For anything not designed yet** (phone menu, empty and loading states, photo upload, error pages), build it from existing pieces in the same style and flag it as a proposal; don't invent a new visual language.
10. **Don't bring back** the spinning sticker, overlapping decorations on phones, soft shadows or gradients.

Keep **NEW** markers until the dark theme and the new states have been reviewed on real pages, then drop them.

Open questions: the final dark theme (Dark 3 for now), the phone menu, empty and loading states, photo upload.

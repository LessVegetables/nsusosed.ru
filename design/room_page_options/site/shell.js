// The viewer: pick a layout and a case; the same page is shown at desktop and phone width.
const OPTS = {
  A: ['A · Now', 'The live page with today\'s fixes (full-width contacts button, new answer comparison). Gallery beside the info panel, then everything stacked full width.',
    ['Known problems: the info panel is short next to a tall gallery, 8 photos make two rows of thumbnails, the page is one long column, and the contacts button scrolls away.']],
  B: ['B · Sticky summary', 'Classic listing. Everything you read scrolls on the left; a summary card (score, topics, facts, contacts button) follows you on the right.',
    ['Contacts and the score are always on screen on desktop; on phones the button is pinned to the bottom.', 'Thumbnails are one scrolling row, so 2 or 20 photos take the same space. One photo: just the photo, no empty thumbnail row.', 'Smallest change from today.']],
  C: ['C · Photo mosaic', 'Photos lead, across the full width: one big and up to four small, "+N" opens the viewer. Title, fact tags and the price sit under it as a headline row.',
    ['With ONE photo the mosaic\'s empty half becomes the map, so a thin listing still looks complete.', 'Phones: a swipe row with the next photo peeking in.', 'Best when listings have good photos; crops portrait shots (the viewer shows them whole).']],
  D: ['D · People first', 'What only this site knows — will you get along — is the hero: the score block and resident cards take the wide column, big differences open. Photos, description and map are the side column.',
    ['Resident cards are wide, so differences sit in two columns instead of a long list.', 'Works well even with one weak photo.', 'Risk: people who want to see the room first have a smaller gallery.']],
  E: ['E · Bento', 'Every fact is its own sticker: photo tile, title, score, price, contacts. Closest to the landing page\'s look; the summary fits one screen.',
    ['Photo tile shows one photo with arrows and a counter, so the photo count never changes the layout.', 'Phones: tiles go two across (score next to price).', 'Loudest option; more color on screen.']],
  F: ['F · Tabs', 'The top is the whole summary; residents, description and map are tabs under it rather than one long scroll.',
    ['Shortest page, good on phones.', 'Risk: the map and description are hidden until tapped.']],
};
const state = { opt: 'E', kind: 'flat', photos: '5', gallery: 'thumbs', theme: 'light', ...Object.fromEntries(new URLSearchParams(location.hash.slice(1))) };
const CONTROLS = {
  opt: Object.entries(OPTS).map(([k, v]) => [k, v[0]]),
  kind: [['flat', 'Apartment · 3 residents'], ['dorm', 'Dorm · 2 residents']],
  photos: [['1', '1'], ['1p', '1 portrait'], ['2', '2'], ['3', '3'], ['4', '4'], ['5', '5'], ['8', '8']],
  gallery: [['auto', 'As designed'], ['thumbs', 'Main + thumbs'], ['mosaic', 'Mosaic'], ['strip', 'Film strip (uncropped)'], ['slide', 'One at a time']],
  theme: [['light', 'Light'], ['dark', 'Dark']],
};
function draw() {
  for (const [name, items] of Object.entries(CONTROLS)) {
    document.getElementById(`c-${name}`).replaceChildren(...items.map(([value, label]) => {
      const b = document.createElement('button');
      b.type = 'button'; b.role = 'tab'; b.textContent = label;
      b.setAttribute('aria-selected', String(state[name] === value));
      b.disabled = name === 'gallery' && state.opt === 'A';
      b.onclick = () => { state[name] = value; draw(); };
      return b;
    }));
  }
  const [title, text, points] = OPTS[state.opt];
  document.getElementById('note').innerHTML = `<h1>${title}</h1><p>${text}</p><ul>${points.map((p) => `<li>${p}</li>`).join('')}</ul>`;
  const id = `${state.kind}-${state.photos}`;
  const src = state.opt === 'A' ? `/room?id=${id}&theme=${state.theme}` : `/layout?opt=${state.opt}&id=${id}&gallery=${state.gallery}&theme=${state.theme}`;
  for (const f of ['if-d', 'if-p']) if (document.getElementById(f).getAttribute('src') !== src) document.getElementById(f).src = src;
  document.getElementById('open-d').href = src;
  document.documentElement.dataset.theme = state.theme;
  history.replaceState(null, '', `#${new URLSearchParams(state)}`);
  fit();
}
function fit() {
  const frame = document.getElementById('frame-d');
  const scale = Math.min(1, frame.clientWidth / 1280);
  const iframe = document.getElementById('if-d');
  iframe.style.transform = `scale(${scale})`;
  iframe.style.height = `${frame.clientHeight / scale}px`;
}
addEventListener('resize', fit);
draw();

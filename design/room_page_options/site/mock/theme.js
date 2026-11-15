// Scratchpad only: ?theme=dark|light on any page of the copy.
const theme = new URLSearchParams(location.search).get('theme');
if (theme) document.documentElement.dataset.theme = theme;

# nsusosed.ru

## UI and design

All UI work follows the design system in [`design/`](design/README.md). Before writing or changing any page, component or style, read `design/README.md` in full and follow its rules, especially section 15. In short:

- Link only `design/nsusosed.css` for styling (copy it into the site; don't rewrite it). Build from its classes and tokens; no raw colors, fonts or sizes in page CSS or markup.
- Page-specific CSS goes in `@layer pages { … }`. No inline styles or scripts (strict CSP).
- Check light and dark (dark = "Dark 3 · light cards") and a 375px-wide screen.

The current `frontend/` is going to be deleted and rewritten from scratch. Don't adapt the design to it. The new site has Russian, English and Chinese, and light and dark themes.

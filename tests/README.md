# Tests

| Folder | What | Needs |
|---|---|---|
| [`frontend/`](frontend/) | Unit tests of the frontend's plain logic: where people land (`routes.js`), storage, invite codes, autosave, translations | Node 22+, nothing to install |
| [`e2e/`](e2e/) | Browser tests: Chromium goes through the real pages against the real API, starting both itself | Python 3.12, Postgres, Playwright |
| [`../backend/tests/`](../backend/tests/) | The API (see [backend/README.md](../backend/README.md)) | Python 3.12, Postgres |

All three run on every push and pull request ([`.github/workflows/test.yml`](../.github/workflows/test.yml)).
Commands below are run from the repo root.

## Frontend unit tests

```
node --test 'tests/frontend/*.test.js'
```

`tests/frontend/env.js` stands in for the little of a browser the modules touch (`window`,
`document`, `localStorage`/`sessionStorage`); import it first in a new test file. The root
`package.json` has no dependencies: it only tells Node the `.js` files are ES modules.

## Browser tests

They need Playwright and a Chromium (about 700 MB together), so they get a venv of their own,
which can live anywhere (an external disk, say): the backend's venv stays small and works without it.
`E2E` below is that folder. Once:

```
python3.12 -m venv "$E2E/venv"
"$E2E/venv/bin/pip" install -r tests/e2e/requirements.txt
PLAYWRIGHT_BROWSERS_PATH="$E2E/ms-playwright" "$E2E/venv/bin/python" -m playwright install chromium
createdb nsusosed_e2e
```

Then:

```
PLAYWRIGHT_BROWSERS_PATH="$E2E/ms-playwright" E2E_DATABASE_URL="postgresql+asyncpg://localhost/nsusosed_e2e" \
  "$E2E/venv/bin/python" -m pytest tests/e2e
```

- The run starts its own API and `frontend/dev_server.py` on free ports, so whatever you have running on
  8000/8080 is left alone. It applies the migrations and **empties every table** of that database first:
  never point it at a database you care about.
- Login codes come from the API's log (`EMAIL_MODE=log`), as when you log in by hand.
- Add `--headed --slowmo 300` to watch, `--tracing retain-on-failure` to keep a trace of what failed
  (open it with `python -m playwright show-trace test-results/…/trace.zip`). In CI the traces of failed
  tests are attached to the run as `playwright-traces`.
- Without `PLAYWRIGHT_BROWSERS_PATH` the browser goes to `~/Library/Caches/ms-playwright`; `.playwright` (inside
  the repo) is ignored by git too.

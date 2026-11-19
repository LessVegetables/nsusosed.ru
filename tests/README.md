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

Once, into the backend's venv:

```
backend/.venv/bin/pip install -r tests/e2e/requirements.txt
backend/.venv/bin/python -m playwright install chromium
createdb nsusosed_e2e
```

Then:

```
E2E_DATABASE_URL="postgresql+asyncpg://localhost/nsusosed_e2e" backend/.venv/bin/python -m pytest tests/e2e
```

- The run starts its own API and `frontend/dev_server.py` on free ports, so whatever you have running on
  8000/8080 is left alone. It applies the migrations and **empties every table** of that database first:
  never point it at a database you care about.
- Login codes come from the API's log (`EMAIL_MODE=log`), as when you log in by hand.
- Add `--headed --slowmo 300` to watch, `--tracing retain-on-failure` to keep a trace of what failed
  (open it with `python -m playwright show-trace test-results/…/trace.zip`). In CI the traces of failed
  tests are attached to the run as `playwright-traces`.
- `PLAYWRIGHT_BROWSERS_PATH=.playwright` keeps the browser inside the repo (git ignores it) instead of
  `~/Library/Caches/ms-playwright`.

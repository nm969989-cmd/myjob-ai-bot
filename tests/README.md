# Offline UI test suites

These suites cover the two static interfaces in this repo:

| Suite | What it loads | What it protects |
| --- | --- | --- |
| `docs_page.test.js` | `docs/index.html` + `docs/data/snapshot.js` in jsdom | handler validity, filters, pagination, modal focus/Escape, tab ARIA, structured data |
| `docs_markup.test.js` | `docs/index.html` as text | viewport/zoom, meta description, canonical, Open Graph, JSON-LD validity, skip link, noscript |
| `templates.test.js` | `templates/miniapp.html` in jsdom with hostile job data | escaping, `javascript:` URL blocking, handler validity, a11y affordances |
| `test_dashboard_templates.py` | both Jinja/verbatim templates | template variable drift (StrictUndefined), escaping of scraped radar data, a11y, script parse |

## Running them

```sh
npm ci && npm test                                  # the three JS suites
python -m unittest tests.test_dashboard_templates   # the Python suite
```

No network access is needed. jsdom is stubbed so the CDN assets (Tailwind, Lucide,
Telegram WebApp) are never fetched, and `fetch` is replaced with a local stub.

## CI

The `.github/workflows/` directory is currently managed outside this branch, so the
workflow below is provided ready to paste. Dropping it in adds a check that runs the
suites above on every change to `docs/`, `templates/`, `tests/` or `package.json`:

```yaml
# .github/workflows/frontend-checks.yml
name: Static Dashboard Checks

on:
  push:
    branches: [main, master]
    paths:
      - 'docs/**'
      - 'templates/**'
      - 'tests/**'
      - 'package.json'
      - 'package-lock.json'
      - '.github/workflows/frontend-checks.yml'
  pull_request:
    paths:
      - 'docs/**'
      - 'templates/**'
      - 'tests/**'
      - 'package.json'
      - 'package-lock.json'
      - '.github/workflows/frontend-checks.yml'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: frontend-checks-${{ github.ref }}
  cancel-in-progress: true

jobs:
  frontend-checks:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Node.js 20
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'package-lock.json'

      - name: Install test dependencies
        run: npm ci

      - name: Run static dashboard tests
        run: npm test

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Jinja2
        run: python -m pip install --quiet jinja2

      - name: Run template render tests
        run: python -m unittest tests.test_dashboard_templates -v
```

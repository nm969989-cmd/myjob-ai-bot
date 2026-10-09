# AGENTS.md

Repository knowledge for agents working in this project.

## What this is

Two halves that share a job dataset:

- `main.py` — Flask + pyTelegramBotAPI bot. Searches the web, verifies vacancies,
  and publishes to a Telegram channel. Also exposes the dashboard.
- `tn-live-jobs/` — Node.js scraper plus a static job board in
  `tn-live-jobs/public/` (deployed via GitHub Pages).

`docs/` is a second static dashboard deployed by `.github/workflows/static.yml`.

## Commands

```bash
# Python
python -m pytest -q                     # full offline suite

# Node (run from tn-live-jobs/)
cd tn-live-jobs && npm ci
node --test test_priority_cities.js test_client.js
node src/cli.js --help
node src/cli.js --step=scrape           # full pipeline: scrape -> validate -> diff -> export -> report
npm run serve                           # preview the board at http://localhost:5173
```

`node src/cli.js <step>` accepts a bare step word (`scrape`, `validate`, `diff`,
`export`, `report`, `serve`). An unknown word exits `2`; it does not default to
running everything.

## Conventions and gotchas

- **No invented data.** A field that was not read off a real page is `null`, or
  the job is dropped. Do not backfill with guesses.
- **`verified: true` is the publication gate.** Only verified jobs reach
  `public/data/`. Unverified records stay in `data/jobs.json` for debugging.
- **Export has a safety guard.** If every source fails and the previous
  `data/jobs.json` had jobs, the export refuses to overwrite it.
- **Scraper politeness.** Requests to a single domain are serialised
  (`runExclusive`) and spaced by 1.5–3.5 s (`waitForTurn`) in
  `tn-live-jobs/src/scraper.js`. Parallelism is only safe across *different*
  domains. `SOURCE_CONCURRENCY` (default 3) exploits this; do not raise it by
  bypassing the per-domain chain.
- **`runWithConcurrency`** (`tn-live-jobs/src/concurrency.js`) is the shared
  bounded-parallel helper. It keeps input order and captures per-item failures as
  `{status, value|reason}` rather than rejecting the batch.
- **City list lives in two places.** `tn-live-jobs/src/config.js` (`CITIES`) and
  the Python radar (`job_radar.py`). `test_priority_cities.js` asserts they do
  not drift — update both together.
- **Dashboard filters are driven by the URL.** `public/app.js` validates every
  query value against the real `<select>` options (`readUrlParams`), and
  `populateFilterOptions()` must run first. Values are capitalised
  (`Chennai`, `Full-time`), not lower-cased.
- **SEO files are generated.** `src/export.js` `writeSeoFiles()` rewrites
  `public/sitemap.xml` and `public/robots.txt`. Edit the generator, not the
  committed output. The deployed URL is in `SITE_URL`.
- **`tn-live-jobs/public/index.html` has no build step.** It is served as-is; the
  CSS is already complete (animations, `prefers-reduced-motion`, responsive
  breakpoints, focus styles), so avoid redesigning it without cause.

## Tests in CI

`.github/workflows/verify.yml` runs the Python offline suite, the Playwright
browser tests, and the two Node test files on every pull request.

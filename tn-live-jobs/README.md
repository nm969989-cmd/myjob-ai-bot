# Tamil Nadu Live Jobs

Every 6 hours, this project searches the web for **real, open job vacancies in
Tamil Nadu, India**, re-opens every advert to prove it is still live, and
publishes the survivors to a mobile-friendly job board.

- **Live board:** `https://<your-github-username>.github.io/tn-live-jobs/`
- **Excel:** `data/jobs.csv`
- **Machine friendly:** `data/jobs.json` (everything) and `public/data/jobs.json` (verified only)

No invented data, ever. If the scraper did not read a title, company, salary,
date or URL off a real page, that value is `null` - or the job is dropped.

## Run it on your own machine

You need [Node.js 20](https://nodejs.org) (or newer).

```powershell
cd tn-live-jobs
npm install
npx playwright install --with-deps chromium   # one-time browser download
npm run scrape
```

`npm run scrape` does the whole pipeline: scrape → verify → diff → export → report.
Testing with a short run first is wise:

```powershell
$env:MAX_TOTAL_JOBS = "25"; $env:CITY = "Chennai"; npm run scrape
```

Preview the website locally:

```powershell
npm run serve            # then open http://localhost:5173
```

Individual steps (the workflow uses these):

```powershell
npm run step:scrape     # writes work/scraped.json
npm run step:validate   # re-opens every URL, writes work/validated.json
npm run step:diff       # compares against data/jobs.json, writes work/diff.json
npm run step:export     # writes data/* and public/data/*
npm run step:report     # writes report.md and prints the summary table
```

Extra knobs (same names work in `env:` blocks in CI):

| Variable              | What it does                                  |
| --------------------- | --------------------------------------------- |
| `QUERY=staff nurse`   | add one extra search keyword                  |
| `CITY=Madurai`        | search a single city instead of all ten       |
| `MAX_TOTAL_JOBS=25`   | cap the number of jobs for short test runs    |
| `ENABLE_TIER3=true`   | also try the optional Tier 3 source           |
| `SKIP_SPA_SITES=true` | skip slow JavaScript-only corporate sites     |
| `VALIDATE_CONCURRENCY=4` | how many different sites verify at once   |

## Put it on GitHub (Actions + Pages)

1. Create an empty repo on GitHub called `tn-live-jobs`.
2. Push this folder's content (see the commands below). Your live site will end up at
   `https://<your-github-username>.github.io/tn-live-jobs/`.
3. **Actions tab →** the first run appears automatically (runs on push plus every 6 hours
   via the `cron` in `.github/workflows/tn-jobs.yml`). To run by hand, open the
   `TN Live Jobs` workflow and press **Run workflow**; you can type an optional
   `query` and `city`.
4. **Settings → Pages →** under *Build and deployment*, choose **GitHub Actions**.
   (The workflow's `publish` job deploys `public/` via `actions/deploy-pages`.)
5. Open `https://<your-github-username>.github.io/tn-live-jobs/` and check for job cards.

```powershell
cd tn-live-jobs
git init -b main
git add .
git commit -m "jobs: first run"
git remote add origin https://github.com/<your-github-username>/tn-live-jobs.git
git push -u origin main
```

## How it works (plain English)

1. **Scrape** (`src/sources/*.js`) — Plain HTML/JSON sites are fetched with `fetch`;
   JavaScript-only career pages are opened in headless Chromium, which also lets
   us read the JSON those pages request for themselves. One polite queue: one
   request at a time per site, random 1.5–3.5 s pause, at most 2 attempts.
2. **Verify** (`src/validate.js`) — Every apply URL is re-opened in a fresh page.
   HTTP 400+ → dead. Login wall → kept but marked `login_required` (never
   published). Redirect to another company or a search page → rejected. Text with
   no job words (`apply`, `vacancy`, `qualification`, `apply now`, …) → rejected.
   Government notices (often PDFs) get an official-language word list plus a
   document check: an official PDF answering HTTP 200 counts as `live_document`.
3. **Diff** (`src/diff.js`) — A job id is the hash of its apply URL, so the same
   advert keeps the same id forever. New = id not seen last run.
4. **Export** (`src/export.js`) — Writes `data/jobs.json + jobs.csv + new-jobs.json
   + history.json + last-run.json` and verified-only `public/data/jobs.json
   (+ jobs.js)`. A safety guard refuses to overwrite good data when a run finds
   nothing.
5. **Report** (`src/report.js`) — Markdown summary per source + per check; the
   workflow appends it to the run summary and commits it as `report.md`.
6. **Website** (`public/`) — Plain HTML/CSS/JS. Verified jobs only, newest first,
   search, city/category filters, "Posted X days ago" labels.

`salary` and `posted_at` are `null` whenever the page did not clearly state them.
"4 days ago"-style ages become a real date (arithmetic, not guessing).

## What can differ on GitHub's servers

- **Playwright install is slower the first time** — the browser downloads on every
  fresh runner (~1–2 min). Packages are cached via `setup-node`'s npm cache.
- **Blocked sites may behave differently** — runner IPs sometimes get more (or
  less) bot protection than your home IP. The per-site table shows exactly which
  sites were blocked in each environment.
- **`npm ci` needs package-lock.json** — committed, so installs are exact.
- **Timeouts are capped** — the scrape job has `timeout-minutes: 45`, and the
  scraper stops requesting new pages after 15 minutes (`SCRAPE_BUDGET_MS`).

## File map

- `.github/workflows/tn-jobs.yml` — every-6-hours workflow + Pages deploy
- `package.json` — Node 20, cheerio, playwright, `npm run *` scripts
- `src/cli.js` — runs the five steps, or `serve` for local preview
- `src/config.js` — cities, categories, keywords, limits
- `src/util.js` — id hashing, city/category/salary/date readers
- `src/scraper.js` — polite fetcher, Playwright helpers, job-shape factory
- `src/sources/index.js` — which sources run (tiers)
- `src/sources/govt-tn.js` — tn.gov.in, TNPSC, employment portals
- `src/sources/company-careers.js` — Zoho, Freshersworld, TCS/Infosys/Wipro/HCL/Cognizant
- `src/sources/naukri.js`, `apna.js`, `indeed.js`, `linkedin.js` — Tier 2 portals
- `src/sources/internshala.js` — optional Tier 3
- `src/validate.js` — re-opens every URL, applies the live-job rules
- `src/diff.js` — new vs gone detection + run history
- `src/export.js` — writes `data/` + verified-only `public/data/`
- `src/report.js` — markdown summary table
- `public/` — the job board (`index.html`, `style.css`, `app.js`, generated `data/`)
- `data/` — committed results (`jobs.json/net/csv`, `new-jobs.json`, `history.json`, `last-run.json`)

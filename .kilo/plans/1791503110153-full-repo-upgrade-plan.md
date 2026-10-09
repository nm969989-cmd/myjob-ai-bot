# Full-Repository Upgrade Plan — nm969989-cmd/myjob-ai-bot

## Goal
Fix bugs and broken routes, modernize the UI (animations + responsive layouts), improve
performance/SEO/accessibility, preserve all existing content, assets, features and working
integrations, verify with tests, then land the work as a PR (never pushed to `main`).

## Confirmed decisions (from user)
- **D1 — Pages fix:** enable GitHub Pages (source: GitHub Actions) and assemble a *combined*
  artifact: `docs/*` at site root + `tn-live-jobs/public/*` under `/tn-live-jobs/`.
  Existing URLs (`https://nm969989-cmd.github.io/myjob-ai-bot/` and `.../tn-live-jobs/`) stay valid.
- **D2 — Delivery:** create a new branch, open a PR against `main`. No direct pushes to `main`.

## Current architecture (verified)
- **Python bot** (`main.py`, 8144 lines) + embedded Flask dashboard on port 7860. Modules:
  `bot_features.py`, `bot_optimizer.py`, `job_radar.py`, `job_discovery.py`,
  `enterprise_adapters.py`, `instahyre_engine.py`, `imap_handler.py`, `browser_use_applier.py`,
  `cloud_runner.py`, `generate_resume.py`.
- **Templates:** `templates/dashboard.html` rendered by `home()` via `render_template_string`
  with explicit context vars (main.py:4614-4736); `templates/miniapp.html` served raw
  (main.py:4771-4781).
- **GitHub Pages site:** `docs/index.html` — 319 KB single-file Telegram-style web app
  (embedded snapshot JSON + live SimplifyJobs merge, tabs: jobs / walk-ins / drives).
- **Node scraper:** `tn-live-jobs/` (cheerio + playwright) with static site
  `tn-live-jobs/public/` (index.html 290 ln, style.css 1196 ln, app.js 772 ln) — this is the
  "Live Job Board" linked from Telegram (main.py:7558, job_radar.py:2192, 2297).
- **CI:** `.github/workflows/job_bot.yml` (scheduled runs, auto-commits state files to main),
  `.github/workflows/static.yml` (deploys `./docs` to Pages).

## Confirmed defects
1. **Pages site is 404.** `/`, `/docs/`, and `/tn-live-jobs/` all return 404. `static.yml`
   uploads only `./docs` and only triggers on `docs/**`; Pages itself appears not enabled.
2. **Dashboard API calls all fail with 401.** `_enforce_dashboard_auth` (main.py:4369) requires
   `DASHBOARD_TOKEN` on every route except `_DASHBOARD_OPEN_PATHS` (main.py:4316 =
   `{"/", "/healthz", "/favicon.ico"}`), but `templates/dashboard.html` calls
   `api/status`, `api/radar`, `api/run_radar`, `api/instahyre`, … with **no token**, and
   `home()` never supplies one. Every widget/button is dead whenever `DASHBOARD_TOKEN` is set
   (required by CI and the Dockerfile/HF contract).
3. **XSS in dashboard table.** `home()` (main.py:4652-4681) interpolates CSV `title`, `url`,
   `status`, `notes` into HTML **unescaped** — inconsistent with the rest of the codebase,
   which uses `html.escape` everywhere (line 8 imports it).
4. **CSV header row rendered as a job.** `home()` (main.py:4647-4648) takes `rows[-10:]`
   without skipping the header; `api_miniapp_jobs` (main.py:4796) correctly uses `rows[1:]`.
5. **Mini-app unreachable from Telegram.** `/miniapp`, `/app`, `/api/miniapp/jobs` sit behind
   the token gate; the Telegram client can only pass `?token=`, which the bot never appends.
6. **`docs/index.html` gaps.** No meta description / OG / canonical / robots / sitemap /
   JSON-LD; **zero ARIA attributes**; `user-scalable=no` (WCAG 1.4.4 violation); unpinned CDN
   deps (`cdn.tailwindcss.com`, `unpkg.com/lucide@latest` — version-drift risk); Telegram SDK
   loaded on a plain website; single 319 KB HTML with ~200 KB inline snapshot JSON.
7. **`tn-live-jobs/public` gaps.** Duplicate data download (`jobs.js` script tag **and** an
   `app.js` fetch of `jobs.json`); only 1 media query; no `prefers-reduced-motion`; no OG/JSON-LD.
8. **Repo hygiene.** `graphify-out/graph.html` + `graph.json` (~1.9 MB) are tracked although
   gitignored. Unreferenced root HTML (`dashboard_FINAL.html`, `dashboard_pro.html`,
   `instahyre_login.html`, `instahyre_login_headful.html`) — **preserve, do not delete**.

## Task list (ordered)

### T1 — Baseline verification (run before any change)
```
python3 -m compileall -q .            # exclude graphify-out
python3 -m unittest test_job_discovery -v
python3 -m pytest test_careerops_integration.py -q -k "not network and not live and not adzuna and not scrape"
node --test tn-live-jobs/test_priority_cities.js
```
Record results. Do not modify tests that already pass.

### T2 — Fix dashboard auth without weakening security (`main.py` + `templates/dashboard.html`)
- Do **not** inject the secret token into server-rendered HTML (`/` is unauthenticated — it would leak).
- Add a small unlock panel in `dashboard.html`: if no token in `sessionStorage`/URL, prompt for it,
  store it, then attach `X-Admin-Token` to every API call.
- Introduce an `apiFetch()` wrapper and replace all raw `fetch('api/...')` calls
  (dashboard.html lines ~533-874). Append `?token=` to the three direct-navigation links
  (`api/download_log`, `api/download_profile`, `api/download_qa`, lines 395-397).
- Keep `_DASHBOARD_OPEN_PATHS` unchanged. Mini-app: rely on the existing `?token=` support in
  `_extract_dashboard_token` (main.py:4343) and have the Telegram `/board` handler append the
  token to the mini-app URL when `DASHBOARD_TOKEN` is set.

### T3 — Fix XSS + header row in `home()` (main.py:4638-4684)
- `html.escape()` CSV `title`, `url`, `status`, `notes` before interpolation (keep identical markup/badges).
- Skip the CSV header: `data_rows = rows[1:]`, then `reversed(data_rows[-10:])`.

### T4 — GitHub Pages combined site (`.github/workflows/static.yml`)
- Stage build: `docs/*` → `site/`, `tn-live-jobs/public/*` → `site/tn-live-jobs/`; upload `./site`;
  keep `actions/upload-pages-artifact@v3` + `actions/deploy-pages@v4`.
- Extend `on.push.paths` to include `tn-live-jobs/public/**`, `tn-live-jobs/data/**`, `docs/**`.
- Enable Pages with source "GitHub Actions" (one-time: `gh api` or user in Settings → Pages).
  Document the URL(s) in `README.md`.

### T5 — `docs/index.html` upgrade (surgical edits; preserve all JS features)
- Head: `<meta name="description">`, canonical, OG + Twitter tags, `theme-color`; keep the title.
- New files: `docs/robots.txt`, `docs/sitemap.xml` (include `/` and `/tn-live-jobs/`).
- JSON-LD (`application/ld+json`): `WebSite` + `JobPosting` list derived from the embedded snapshot.
- A11y: remove `user-scalable=no`; add `aria-label` to icon-only buttons (`refreshBtn`,
  `clearSearchBtn`, modal close), `role="tablist"`/`aria-selected` on nav, `aria-live` on toast
  and results, `:focus-visible` styles, and a `prefers-reduced-motion` block disabling the
  float/pulse animations.
- Animations: card entrance, tab cross-fade, modal spring — CSS-only, reduced-motion aware.
- Responsive: add real breakpoints (currently mobile-only widths); widen metrics grid at
  `sm`/`lg`; contain horizontal scroll for filter chips.
- Performance: pin CDN versions (`tailwindcss@3.4.x`, `lucide@<pinned>`); load the Telegram SDK
  only inside Telegram (`window.Telegram?.WebApp?.initData` check, otherwise defer); optionally
  move the inline snapshot to `docs/data/snapshot.js` (cacheable) — only if verified byte-safe.

### T6 — `tn-live-jobs/public` upgrade
- `index.html`: OG + Twitter meta, canonical, `JobPosting` JSON-LD; keep existing description.
- `app.js`: prefer `window.__TN_JOBS__` and skip the duplicate `jobs.json` fetch (halves data
  transfer); announce filter-result counts via `aria-live`; skeleton/empty-state polish.
- `style.css`: `prefers-reduced-motion`, additional breakpoints (768/1024 px), focus-visible
  outlines, subtle card/modal animations.
- Add `public/robots.txt` + `public/sitemap.xml`.

### T7 — `templates/dashboard.html` polish
- A11y: labels for icon-only controls, `aria-live` status text, focus-visible, reduced-motion.
- Animation: stat count-up + smooth progress-bar transition (CSS/JS, reduced-motion aware).
- Responsive: audit `md:`-only breakpoints and add `sm:` where layouts break.

### T8 — Repo hygiene (non-destructive)
- `git rm --cached graphify-out/graph.html graphify-out/graph.json` (already gitignored; files stay on disk).
- Leave legacy root HTML files in place; note them as legacy in README.

### T9 — Docs
- Update `README.md`: Pages URL(s), how to enable Pages, dashboard token flow, legacy-file note.

### T10 — Validation
- Re-run all T1 tests.
- Flask smoke test with temp `DASHBOARD_TOKEN` + dummy `TELEGRAM_TOKEN`:
  `GET /`, `/healthz`, `/api/status` (no token → 401; with token → 200), `/miniapp?token=…`,
  `/api/miniapp/jobs?token=…`; confirm the dashboard renders and all its assets resolve.
- `node --check` modified JS; tag-balance/HTML sanity check on both index.html files.
- Browser pass on both sites: console clean, responsive at 375/768/1440 px, animations,
  keyboard tab order, reduced-motion emulation.

### T11 — Git & PR
- `git checkout -b upgrade/ui-perf-seo-a11y` (from `origin/main`, fresh — the bot workflow
  auto-commits state files to `main`).
- Logical commits: `fix: dashboard auth token flow`, `fix: escape CSV values in dashboard table`,
  `fix: deploy combined Pages site`, `feat: modernize docs site UI/SEO/a11y`,
  `perf: avoid duplicate jobs data download`, `chore: untrack graphify artifacts`,
  `docs: README updates`.
- `git push -u origin <branch>` → `gh pr create --base main` with a change summary + test results.
- Never push to `main`.

## Risks
- Dashboard auth change alters UX — keep the gate, test 401/200 paths explicitly.
- `docs/index.html` is 319 KB of inline JS — edits must be surgical; keep snapshot data identical.
- Pages enablement is a one-time repo-settings action outside the PR.
- PR branch must start from fresh `origin/main` to avoid conflicts with the bot's auto-commits.

## Out of scope
- Splitting `main.py` into modules; replacing Tailwind CDN with a build pipeline; deleting
  legacy HTML files.

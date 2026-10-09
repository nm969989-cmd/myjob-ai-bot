---
title: Myjob Bot
emoji: 🏃
colorFrom: red
colorTo: pink
sdk: docker
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

## Regional discovery and walk-in cards

The first search/posting tier is **Tiruvannamalai, Vellore, Puducherry/Pondicherry, and Chennai**. All four cities share the preferred tier; relevance and freshness determine ordering within it. Other Tamil Nadu, India, and remote results remain available as fallbacks.

- `/search python` searches the preferred cities live through LinkedIn/Indeed (JobSpy) and Adzuna when its existing credentials are configured, even if cached listings already fill the result limit. It also reads the existing portal, government, company-careers, national-drive, and radar feeds.
- `/search python vellore`, `/search thiruannamalai`, `/search pondicherry`, and `/search chennai` constrain results to that city. Common Tiruvannamalai spellings and Pondicherry/Puducherry are aliases.
- `/jobspy <role>` uses the same regional search and fallback pipeline.
- `/tnjobs` and automated radar posting prioritize the four cities; Puducherry is included as a regional target without being described as part of Tamil Nadu.
- The separate `tn-live-jobs` scraper searches the preferred cities first across its supported portals and orders exported listings accordingly. Its feeds update when that scraper next runs; generated JSON/HTML has not been rewritten by this change.

Coverage is limited to supported sources, their available data, and their access/rate limits—not every website on the internet. Role/location searches are sent to the configured job portals. No extra AI service or new credential is required; Adzuna still needs `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. Priority live queries wait up to 25 seconds, reuse in-flight work, and cache completed source responses for 15 minutes. Other existing fallback sources have their own timeouts.

### Automatic Telegram searches

No manual `/search` is required for scheduled alerts:

- The continuously running bot performs its first scan 30 seconds after startup, then scans hourly by default. Set `AUTO_SEARCH_INTERVAL_MINUTES` to change the interval (15–1440 minutes). `/pause` stops new automatic radar scans; `/resume` enables them again. An in-progress scan may finish before the pause takes effect.
- On GitHub, the existing workflow runs at **11 AM and 7 PM IST**, on a code push, or when manually dispatched. GitHub schedules are best-effort and can be delayed. The cloud runner now searches the four preferred cities and sends the regional digest before the longer channel scans.
- Automatic alerts use `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` (GitHub repository secrets for Actions, or the bot's environment/saved authorized chat for the continuous service). Previously delivered links are filtered, and links are marked seen only after successful digest delivery.
- The Actions workflow persists the daily walk-in dispatch marker so a fresh runner does not resend the daily walk-in digest on every run. Private reminder/chat state is not committed.

The continuous service must be running for hourly searches and interactive reminder buttons; pushing to GitHub enables the scheduled Actions path but does not itself restart the separate Hugging Face service. Keep one interactive bot instance active to avoid Telegram polling conflicts. Running both search schedulers can duplicate alerts because their dedup state is stored separately.

### Walk-in actions

`/walkins` and automated walk-in alerts send one compact card per drive, with **Full details**, **Remind me**, employer-page, and Maps actions. Cards show source links, recorded retrieval/link-check timestamps, and an unconfirmed warning unless explicit employer-confirmation metadata exists. A live URL or a feed claiming to be “verified” does not prove the event is employer-confirmed. Existing undated saved drives are not treated as newly confirmed vacancies.

Reminders require a source-supplied `event_start` ISO datetime, or `walkin_date`/`event_date` (`YYYY-MM-DD`) plus `reporting_time` (`HH:MM`, 24-hour). A datetime without an offset is interpreted as IST. Relative phrases such as “Upcoming Saturday” are deliberately **not** resolved into guessed dates. Date-only listings show their date but cannot schedule a reminder until a reporting time is provided.

- **Remind me** schedules 24 hours before the event, or immediately if it is less than 24 hours away.
- **Add to calendar** exports an `.ics` event when an exact date/time is available.
- `/reminders` lists pending reminders; `/reminders cancel` cancels your pending reminders.
- The supervised delivery loop checks every 30 seconds and retries failed sends. Expired missed reminders are skipped. Telegram delivery is best-effort: an abrupt process crash immediately after a successful send but before saving delivery state can produce a duplicate after restart.

Private card/reminder state lives in the git-ignored `job_discovery_state.json`. Preserve this file on a persistent writable volume when deploying; process restarts preserve it, but ephemeral container replacement may not. Restart/redeploy the bot to activate the changed handlers and background worker. This change does not start or deploy the bot automatically.

### Offline validation

```sh
python -m unittest test_job_discovery -v
node --test tn-live-jobs/test_priority_cities.js
```

These tests mock portal calls and Telegram delivery. They do not submit applications or publish live Telegram messages.

## Development and quality checks

The project retains three independent entry points:

- `main.py`: Flask command center and Telegram bot, with Playwright application adapters, AI clients, email, Notion and Sheets integrations.
- `tn-live-jobs/`: Node scraper → verifier → diff → export → report, plus the static job board at `public/`.
- `docs/index.html`: GitHub Pages careers hub with saved jobs, walk-ins, drives, ATS matching and salary tools. The Pages workflow publishes `docs/`; the Node board is a separate preview.

Use **Python 3.11** (`.python-version`) and **Node 20+**. The Python Playwright version matches the Docker image; stealth is pinned to the API used by the existing adapters.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m unittest test_job_discovery test_careerops_integration test_dashboard -v
npm --prefix tn-live-jobs ci --ignore-scripts
npm --prefix tn-live-jobs test
npm --prefix tn-live-jobs run serve
# Separate Pages preview:
python -m http.server 5174 --directory docs
```

The offline tests use synthetic data and mocked portal responses. Pull requests run them without provider secrets. Browser-dependent scraping still needs `python -m playwright install chromium` (Python) or `npx playwright install chromium` from `tn-live-jobs` (Node), plus each runtime's OS dependencies.

### Dashboard access

Set `DASHBOARD_TOKEN` to a long random secret. Open `/?token=YOUR_TOKEN` over HTTPS once: the server redirects to a clean URL and issues an eight-hour signed, HttpOnly, SameSite=Strict cookie. API requests and downloads then use that cookie. Header-based clients can continue using `X-Admin-Token` or `Authorization: Bearer`. Cookie-authenticated POST requests require a matching `Origin`.

The application expects one trusted reverse proxy to overwrite `X-Forwarded-Proto`; it uses that scheme for Secure cookies and Origin validation. Do not expose the upstream HTTP listener directly in production. Local HTTP previews use cookies without Secure. Rotating the token invalidates existing sessions. `/` without credentials and `/healthz` return only service health, not private dashboard content. Only `/healthz` permits public cross-origin reads. Authenticated pages and APIs are not cached or indexed.

Open the administrative miniapp directly in its own browser origin. Telegram iframe authentication is not implemented; the public Pages hub remains the public job browsing surface. Live provider authentication, delivery and job submissions require a separate deployment smoke check.

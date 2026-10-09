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
- The separate `tn-live-jobs` scraper searches the preferred cities first across its supported portals and orders exported listings accordingly. Its search plan now covers **every** preferred city for each keyword before moving to the broader cities (previously a small page budget was spent on the first keyword alone), and it now recognises the same Tamil Nadu localities as the bot (Hosur, Kanchipuram, Dindigul, Karur, Nagercoil, Thoothukudi, Cuddalore, Ranipet, Sivakasi, Kumbakonam, Neyveli and more) — previously jobs in those cities were dropped or never searched. Its feeds update when that scraper next runs; generated JSON/HTML has not been rewritten by this change.

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

## Review and deployment checks

Use **Python 3.11** (the existing Actions runtime) and **Node 20+**. The pinned
JobSpy dependency set is not compatible with a clean Python 3.13 installation;
this upgrade intentionally does not replace JobSpy. `stealth_sync` requires the
legacy `playwright-stealth` API and its compatible setuptools range.

```sh
python -m pip install -r requirements.txt pytest
python -m pip check
python -m pytest test_careerops_integration.py test_job_discovery.py test_dashboard.py test_cloud_runner.py -q
cd tn-live-jobs && npm ci && cd ..
node --test tn-live-jobs/test_priority_cities.js tn-live-jobs/test_client.js
python -m playwright install --with-deps chromium
python -m pytest test_ui_browser.py -q
```

The browser suite uses local fixtures at 320px, 390px and 1440px and blocks
external requests. It checks search, saved jobs, keyboard modal focus, reduced
motion, horizontal overflow and dashboard API authentication. These checks do
not prove live portal access, Telegram delivery, AI credentials or deployment
health. `test_features_verify.py` remains a separate network/data-dependent
manual smoke script, not part of the offline suite.

Cloud runner exit codes: **0** = no recorded stage/delivery errors; **1** = a
caught stage or delivery error; **2** = missing Telegram delivery configuration.
Unavailable individual channels and budget skips remain nonfatal notes. An empty
successful search is not an error. Errors swallowed inside upstream source
functions cannot be inferred from these exit codes.

For browser dashboard access, open `/?token=<DASHBOARD_TOKEN>` over HTTPS. The
page forwards the token only to same-origin API calls; token-bearing URLs remain
sensitive (including browser history). Header/Bearer access is also supported.
Keep private dashboards out of search indexes; SEO metadata belongs on public
job pages, not the admin console.

### Deployment prerequisites still requiring owner action

- GitHub Pages: enable **Settings → Pages → Source → GitHub Actions** as a repository
  administrator before deploying. The workflow should not try to auto-enable
  Pages using its limited integration token.
- Hugging Face: the Space's own root README must contain `sdk: docker` and
  `app_port: 7860`, with this Dockerfile present. Updating GitHub alone does not
  update the separate Space or fix a Gradio SDK setting there.
- Rotate the previously exposed Telegram token through BotFather and update
  deployment secrets. A clean current tree does not revoke a token in history.
- Personal resume/contact data, captured login pages, generated graphs and old
  dashboard variants were intentionally preserved in this review. Decide which
  should be made private/removed in a separate approved cleanup. Do not reuse
  captured authentication sessions from public source control.
- The repository still needs an owner-selected root license; a subproject's
  `license` field does not license the entire application.

# Engineering search enhancement — UNVERIFIED draft

This is an opt-in, additive implementation, not a claim that more live jobs have been recovered. No Node/Python syntax checks, tests, live source run, Telegram delivery or deployment has been executed: the connected executor is unavailable. Keep the PR draft until the checks below pass. Main, existing workflows, deployment settings, applications and secrets must not be changed merely to test it.

## What is added

- `tn-live-jobs/src/engineering-search.js`: role aliases (software/developer/backend/full-stack/frontend/data/Python plus other engineering branches), explicit city aliases, approximate radius filtering, explainable freshness/source/evidence/skills/experience/branch ranking. Data entry is not a data-engineering alias. Unknown posting dates stay unknown; scraping today does not make an old posting fresh. Known experience below a stated minimum is penalized, not silently presented as eligible.
- Cross-source deduplication uses a canonical URL or an explicit employer+requisition identity. Tracking parameters are removed, job-id parameters retained. Different jobs with the same title are not merged merely for their title. Source URLs/check results remain in provenance.
- Bounded transient link retry queue: 429, 408, 5xx and network errors remain uncertain, with Retry-After and exponential delays. At most 200 queue entries, 20 due retries/run, three attempted checks per retained retry record and a seven-day retry window. Not-due/budget-deferred records do not consume attempts or continually postpone their existing due time. Queue overflow/exhaustion is explicitly uncertain. Missing from a scrape is not proof of closure; 404/410 or an explicit past deadline is closure evidence. Access denied is excluded, never bypassed/retried through another route. To reset exhausted state, an operator must review and remove only the affected record's retry_state/retry_attempts/retry_first_seen/retry_due fields from the engineering state; no automatic unlimited retry loop.
- `engineering.js`: bounded collection/revalidation and offline profile queries. Each run has an eight-minute budget, at most 100 ranked verification candidates and 1,000 retained engineering records. Verified means the permitted public page returned HTTP 200 with a matching job heading and responsibility/application evidence, not an employer eligibility guarantee. Unsupported HTML layouts/redirects remain uncertain.
- `engineering_telegram.py`: private owner-only `/esearch`, `/save_search`, `/searches`, `/remove_search`, `/engineering_profile`, `/refresh_search`; short digest separates verified/uncertain, shows source/posted date/check reason/fit and scan timestamp. At most four saved-search digests per cycle, round-robin among up to ten searches. Only rendered cards are acknowledged after successful delivery. Seen history is bounded to 1,000 IDs per search. Scans older than 48h are not advertised as currently verified. Saved searches require an initial engineering scan.
- `engineering_app.py`: opt-in launcher that reuses the existing bot, preserves existing commands and Flask application, and adds a scan thread without adding a second Telegram poller. Existing main.py is untouched. This integration itself still needs a real smoke test.
- Includes the same fetchText method/body transport fix and localhost regression test as draft PR #7. That fixes an observed implementation omission, but does not establish Workday permissions, recovery or actual vacancy counts.

## Preset and privacy

Default cities: Tiruvannamalai, Vellore, Puducherry/Pondicherry and Chennai. Default roles: software engineer/developer, backend, full-stack, data engineer and Python. This is a **default software/data search**, not an inferred personal profile. Branch, skills and experience remain unknown; radius is 0 km until the owner changes it. Other engineering roles can be selected with saved searches. A stated branch earns a small relevance bonus only when the listing mentions it; it does not prove qualification eligibility.

After rollout, examples (replace example values with the owner's answers):

```
/engineering_profile branch=computer science;skills=python,sql;experience=unknown;radius=0
/save_search backend Chennai | backend | Chennai
/esearch data | Vellore
/searches
/remove_search backend Chennai
```

Supported location evidence additionally includes Chengalpattu, Sriperumbudur, Ranipet and Tirupattur. Radius is approximate straight-line distance between city centres, not commute/travel time or geocoded addresses. Unknown locations are excluded rather than guessed. Collection is finite: radius searches can only find locations actually ingested; HCL/Wipro search pages are queried in the four default cities and may omit suburbs.

Private profile/saved-search/seen state defaults to `~/.myjob-search/state.json`, outside the checkout; set `ENGINEERING_STATE_DIR` to a private persistent volume outside the repository. Files are written mode 0600 with atomic replace. Do not commit this directory or put it under public/data, workspace data persisted to Git, or the checkout. One process/writer is supported (the lock is thread-local, not an inter-process lock). Ephemeral CI needs a private state store to avoid repeated notifications; no CI digest is enabled here. Telegram credentials are read only from existing environment/secret configuration and never written by this feature.

## Sources and limits

1. HCLTech/Wipro: transparent `MyJobSearch/1.0` reads of public search/job pages, current robots required (fail closed when unavailable/disallowed). Four search pages and twelve detail links per employer; 1.5s spacing per host, 15s request timeout and 2MB response cap. Only fixed HTTPS public-route allowlists; no login, private services, account endpoint, browser stealth, CAPTCHA solver or redirect following. HCL's JS search may expose no parsable links. Robots compliance is not a blanket automation license: the operator must review current terms/permission before a live rollout, and disable a source if permission is denied.
2. SmartRecruiters: public postings of Freshworks, BoschGroup and AveryDennison, four pages of 100 per employer, never internal postings or authenticated private API. Official overview: https://developers.smartrecruiters.com/docs/posting-api describes access to previously public postings; no API key/OAuth token is used. Public detail pages still require current robots and matching evidence. Listing retrieval and successful live revalidation are separate; coverage is unverified here.
3. Cognizant, Naukri, Indeed and Workday CXS are excluded from this new collection path until a permitted automated route is verified. Use employer/native alerts or manual review rather than bypass. Cognizant's inspected robots excludes GPTBot. No new government feed is claimed because the investigated failures did not establish a working permitted feed.

This does **not** rewrite or certify the legacy collector's entire source policy. Existing legacy routines/workflows remain unchanged. Review them separately before deployment if disabling legacy collection is required. Diagnostic evidence: [draft PR #5](https://github.com/nm969989-cmd/myjob-ai-bot/pull/5), original [run](https://github.com/nm969989-cmd/myjob-ai-bot/actions/runs/37864506137), original [job log](https://github.com/nm969989-cmd/myjob-ai-bot/actions/runs/37864506137/job/113607908910).

## Additive outputs and activation

Existing `npm run scrape`, legacy data/jobs.json, history, report and website outputs are untouched by the engineering mode. No workflow, Dockerfile or main.py entrypoint is changed. New scripts:

```
cd tn-live-jobs
npm run engineering:refresh        # NETWORK: do not use as an offline test
npm run engineering:test           # localhost/fixtures only
```

New files after a real refresh: `data/engineering-matches.json`, `data/engineering-retry-queue.json`, `data/engineering-report.md` and `public/data/engineering-matches.json` (verified default matches only, with timestamp). They do not contain the private owner's preset. Public website integration is not enabled in this draft. The existing workflow does not invoke the engineering refresh; merely merging these files would not activate it.

After tests and source-policy review, a consenting operator can stop the existing poller and launch `python engineering_app.py` instead of `python main.py`, with the existing Telegram token and a positive private `TELEGRAM_CHAT_ID`, Node >=20, npm dependencies and a private persistent state volume. Do not run both, and do not run the standalone companion poller at the same time. The standalone companion is optional for an isolated bot only; it does not provide legacy commands. Roll back by stopping the enhancement launcher and restoring the existing main.py entrypoint. No production bot or Telegram message has been started/sent in implementing this draft.

## Required verification before ready/merge

Run from an accessible checkout; all commands in this block are offline except dependency installation. None has been run by the author. Check the exact branch head first, keep production bot credentials out of the test environment, and capture exit codes without `|| true` masking.

```sh
git fetch origin main enhance/engineering-search-digests
git switch --detach origin/enhance/engineering-search-digests
git rev-parse HEAD
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
cd tn-live-jobs
node --version
npm ci
node --check src/scraper.js
node --check src/engineering-search.js
node --check src/sources/engineering-public.js
node --check src/engineering.js
node --check test_engineering_search.js
node --check test_http_transport.js
npm run engineering:test
node --test test_priority_cities.js
cd ..
python -m py_compile engineering_telegram.py engineering_app.py test_engineering_telegram.py
python -m unittest test_engineering_telegram -v
python -m unittest test_job_discovery -v
pytest test_careerops_integration.py -k 'not network and not live and not adzuna and not scrape'
```

Then review source terms/robots, run one bounded read-only `engineering:refresh`, inspect actual source_status/verified/uncertain/retry evidence, check independent fixture/existing-suite failures and confirm that legacy outputs are unchanged. Verify retry due times across multiple scans, source outages do not turn uncertain jobs live, and personal details never reach Git/public output. Finally use an isolated test bot/private chat to check new commands, digest dedupe/failed-send handling and legacy commands with exactly one poller. Do not use workflow_dispatch/production bot as a transport unit test. Live search improvement is established only by those results, not by PR creation.

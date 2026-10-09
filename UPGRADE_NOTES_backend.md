# Backend Audit — myjob-ai-bot (`cline/1q8j1vf8`)

Scope audited: `main.py`, `bot_optimizer.py`, `cloud_runner.py`, `job_discovery.py`,
`bot_features.py`, `enterprise_adapters.py`, `imap_handler.py`, `instahyre_engine.py`,
`generate_resume.py`, `browser_use_applier.py`, `test_*.py`.
No docs/, templates/, tn-live-jobs/, .github/ or JSON/txt data files were touched.
No new dependencies were added. Nothing that hits the live network, Telegram or job
applications was executed.

## Verification (all run offline from `/workspace`)

| # | Command | Result |
|---|---------|--------|
| 1 | `python3 -m py_compile main.py bot_optimizer.py cloud_runner.py job_discovery.py bot_features.py enterprise_adapters.py imap_handler.py instahyre_engine.py generate_resume.py browser_use_applier.py test_backend_hardening.py` | `PY_COMPILE_OK` (exit 0) |
| 2 | `python3 -m unittest test_job_discovery -v` | `Ran 31 tests ... OK` |
| 3 | `python3 -m pytest test_careerops_integration.py -q -k "not network and not live and not adzuna and not scrape"` | `4 passed, 1 deselected` |
| 4 | `python3 -m unittest test_backend_hardening -v` | `Ran 7 tests ... OK` (new regression suite) |
| 5 | `python3 -m flake8 --select=F821,F811,E999 <all scope files>` | only `F811` redefinition false-positives remain; **no `F821`, no `E999`** |
| 6 | `python3 -c "import main; print('/' in main._DASHBOARD_OPEN_PATHS)"` | `MAIN_IMPORT_OK`, `root_open=False`, `healthz_open=True` |
| 7 | standalone concurrency repro of the old `save_applied_job` | `expected 40 saved 3 LOST 37` |

Note: `import main` **failed before this audit** with
`ImportError: cannot import name 'stealth_sync' from 'playwright_stealth'`; it succeeds now.

---

## Findings

### F1 — `main.py:6852` (was 6811) — undefined name `chat_id` (REAL, FIXED)
* **Wrong:** inside the `/apply` handler `manual_apply()` -> nested `run()` closure, the
  browser-use **dry-run** completion notice called `bot.send_message(chat_id, ...)`. `chat_id`
  is not defined in `run()`, not in `manual_apply()` and not at module scope.
* **Root cause:** copy/paste from the sibling `handle_apply_callback()` handler, which *does*
  define `chat_id = call.message.chat.id`. In `manual_apply()` the surrounding
  `try/except Exception: pass` swallowed the resulting `NameError`.
* **Impact:** the user never receives the "Dry run complete — not submitted" message; the
  failure is silent (no log line).
* **Verdict:** real bug (`flake8` F821).
* **Fix:** `bot.send_message(message.chat.id, ...)` (matches every other send in that closure).
* **Verify:** item 5 (F821 gone), item 1.

### F2 — `main.py:4348`, `4402-4435` — unauthenticated `/` leaked the whole dashboard (REAL, FIXED)
* **Wrong:** `_DASHBOARD_OPEN_PATHS` contained `"/"`, and `_enforce_dashboard_auth()` returns
  `None` (allow) for any path in that set. But the `"/"` route is `home()`, which renders
  `templates/dashboard.html` with the applied-jobs log (job titles + URLs), the saved chat id,
  profile stats, the monitored-channel list, the Notion URL and the resume filename.
* **Root cause:** the open-path allow-list was written assuming `"/"` was a harmless landing
  page, but the route behind it serves the full dashboard. The same hole existed when
  `DASHBOARD_TOKEN` was unset (the "fail closed" branch also allowed open paths).
* **Impact:** anyone who can reach the host (server binds `0.0.0.0:7860`) reads private job/
  profile/chat data with no token.
* **Verdict:** real security bug (info disclosure); directly contradicts the code comment
  "None of these expose job, profile, credential or browser data."
* **Fix:** removed `"/"` from `_DASHBOARD_OPEN_PATHS`; unauthenticated `"/"` now returns the
  harmless `_dashboard_health_response()` JSON in both the token-set and token-unset branches,
  so the hosting platform's root health probe still gets HTTP 200 while the dashboard is only
  served to callers presenting `X-Admin-Token` / `Authorization: Bearer` / `?token=`.
* **Verify:** item 6 + `test_backend_hardening.DashboardAuthTests` (items 4).

### F3 — `main.py:549` (`save_applied_job`) — non-atomic dedup read-modify-write (REAL, FIXED)
* **Wrong:** `save_applied_job()` did `load_applied_jobs()` then `safe_save_json(...)` as two
  separate `file_lock` acquisitions. Two apply threads could both read the same set `{A}`,
  each add its own URL, and the second write clobbered the first.
* **Root cause:** the read-modify-write was not performed under a single lock even though
  `browser_use_applier._record_applied_job()` explicitly relies on `main.save_applied_job()`
  being atomic (its docstring claims it "holds file_lock and uses the atomic tmp+os.replace
  write").
* **Impact:** lost dedup entries -> the same job can be re-applied in a later cycle
  (duplicate applications).
* **Verdict:** real concurrency/state bug. Reproduced: the old logic lost **37 of 40**
  concurrent additions (item 7).
* **Fix:** `file_lock` is now `threading.RLock()` and `save_applied_job()` holds it across the
  whole read-modify-write; it also ignores empty URLs. `safe_load_json`/`safe_save_json`
  re-acquire the same reentrant lock on the same thread, so no deadlock.
* **Verify:** items 1, 2, 4, 7.

### F4 — `main.py:4523, 4907, 4928, 5000, 5049` — `request.json` can be `None` (REAL, FIXED)
* **Wrong:** `/api/live_action`, `/api/manual_apply`, `/api/update_profile`, `/api/add_channel`
  and `/api/mark_crm` did `data = request.json` and then `data.get(...)`. When a client posts
  without a JSON body / `Content-Type: application/json`, Flask returns `None` and `.get`
  raises `AttributeError` -> HTTP 500.
* **Root cause:** no `None` guard on the parsed body (other routes such as `/api/instahyre`
  already used `request.get_json(silent=True) or {}`).
* **Verdict:** real robustness bug (unhandled `None` on realistic input).
* **Fix:** `data = request.get_json(silent=True) or {}` for all five routes.
* **Verify:** item 4 (`test_json_endpoint_tolerates_missing_body`), item 1.

### F5 — `main.py:5017, 5029` — case-sensitive upload extension check (REAL, FIXED)
* **Wrong:** `/api/upload_resume` required `file.filename.endswith('.pdf')` and
  `/api/upload_auth` required `.endswith('.json')`. A file named `Resume.PDF` / `AUTH.JSON`
  was rejected as "Invalid file type".
* **Verdict:** real (minor) usability bug.
* **Fix:** compare `file.filename.lower().endswith(...)`.
* **Verify:** item 1.

### F6 — `main.py:20`, `instahyre_engine.py:8` — `playwright_stealth.stealth_sync` removed in 2.x (REAL, FIXED)
* **Wrong:** both modules did `from playwright_stealth import stealth_sync` at import time.
  `requirements.txt` pins `playwright-stealth>=1.0.6` (no upper bound), so a fresh
  `pip install -r requirements.txt` installs **2.0.3**, where the module-level `stealth_sync`
  helper was replaced by `Stealth().apply_stealth_sync(page_or_context)`.
* **Root cause:** unpinned upper version + hard import of a renamed symbol.
* **Impact:** `ImportError` at import time takes down the entire bot and the CI/cloud path
  (`cloud_runner` does `from main import scrape_single_channel`). Reproduced in this
  environment: `import main` failed with
  `ImportError: cannot import name 'stealth_sync' from 'playwright_stealth'`.
* **Verdict:** real, high-severity.
* **Fix:** version-tolerant shim in both files: try `stealth_sync` (1.x); otherwise use
  `Stealth().apply_stealth_sync(target)` (2.x, signature accepts Page **or** BrowserContext);
  final fallback is a no-op so the bot degrades instead of failing to start. `requirements.txt`
  was **not** edited (out of scope / "do not add dependencies").
* **Verify:** item 6 (`import main` and `import instahyre_engine` now succeed), item 4
  (`StealthCompatTests`), item 1.

---

## Findings examined and deliberately NOT changed

* **`main.py:231 is_authorized()` returns `True` when no admin id is configured** — this is the
  documented first-run bootstrap (the first chat to message the bot becomes the owner, then
  `save_chat_id` locks it). Changing it could lock the legitimate owner out of a fresh deploy.
  Flagged for awareness only; production sets `TELEGRAM_CHAT_ID`.
* **Unbounded in-memory caches** — `bot_optimizer._LINK_ALIVE_CACHE`, `_SHARED_GAP_STORE`,
  `_SHARED_EMAIL_STORE` (the latter two are already capped at 500) grow for the process
  lifetime. Low impact for a long-running bot; changing eviction could alter cache hit
  behaviour, so left alone.
* **Pervasive broad `except Exception: pass` / bare `except:`** (e.g. `main.py` handler bodies,
  `instahyre_engine.py:519`, `bot_features.py`). These hide errors but rewriting them risks
  changing long-standing control flow; only the one bug they actually masked (F1) was fixed.
* **`imap_handler.get_latest_otp()`** never marks a matched-but-codeless email as seen, so it is
  re-read each poll until timeout. Behavioural, not a crash; left as-is.
* **`bot_features.check_for_interviews()`** decodes message parts without `errors="ignore"` and
  writes `temp_email.html` into the CWD per interview email. Both are contained by the outer
  `try/except`; not fixed to avoid touching working email flows.
* **`cloud_runner.py:154,189` unused locals and `:81` unused `global`s** — dead code only.
* **Dashboard XSS surface** — `render_template_string` interpolates `recent_jobs_html`,
  `channels_html` and `HANDOFF_URL`. With F2 fixed these are now auth-gated; hardening the
  template interpolation is a larger, cross-cutting change left out of this surgical pass.
* **`/api/live_action` still 500s on a missing `x`/`y` key** — contained by its own
  `try/except` and only reachable by an authenticated caller; left as-is.
* **`subprocess.run(["python", "generate_resume.py"])`** in `/api/regenerate_resume` — no
  user-controlled arguments, so no command-injection risk. No change needed.
* **Token handling is sound** — `hmac.compare_digest` is used for the dashboard token, and the
  Telegram side is gated by `admin_only`. No change needed.

## False positives reported by `flake8 --select=F821,F811,E999` (no change made)

* `main.py:356` re-import of `InlineKeyboardMarkup/Button`, `ForceReply` inside the
  `if TELEGRAM_TOKEN:` block; `main.py:698` local `import base64`; `main.py:4901`
  re-import of `request/send_file/jsonify`; `main.py:5962/6530/6964` local handler imports of
  `get_walkin_drives`/`format_walkins_report`/`format_skill_gap_report`/`get_gap_cache`;
  `bot_optimizer.py:356` re-import of `json`. All are re-imports/local imports of already
  imported names — harmless shadowing, not undefined names.
* `F541` (f-string without placeholders), `F824` (unused `global`/`nonlocal`),
  `F841` (unused locals), `F401` (unused imports) — cosmetic / dead code, left untouched to
  keep the diff surgical.

## Files changed

* `main.py` — F1, F2, F3, F4, F5, F6
* `instahyre_engine.py` — F6
* `test_backend_hardening.py` — **new** offline regression suite (7 tests)
* `UPGRADE_NOTES_backend.md` — this report

Unrelated working-tree changes under `docs/`, `tn-live-jobs/` and a new `tests/` directory were
present in the checkout (not produced by this audit) and were intentionally **not** staged or
committed.

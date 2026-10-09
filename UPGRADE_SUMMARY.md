# Repository upgrade summary — `myjob-ai-bot`

Branch: **`cline/1q8j1vf8`** (from `main` @ `ea62237`) · 5 commits · 28 files changed
Every change is additive or a targeted fix: **no feature, page, asset or integration was removed**,
and `main` was never written to.

Detailed per-area reports live in [`UPGRADE_NOTES_backend.md`](UPGRADE_NOTES_backend.md) and
[`UPGRADE_NOTES_tnlive.md`](UPGRADE_NOTES_tnlive.md).

---

## 1. What the project actually is

| Layer | Details |
| --- | --- |
| Telegram bot | `main.py` (8.1k lines) — pyTelegramBotAPI handlers, Playwright mass-apply engine, IMAP reply reader, Gemini/Groq AI, Notion CRM |
| Optimiser / radar | `bot_optimizer.py` (4.6k), `job_radar.py` (2.4k), `job_discovery.py`, `enterprise_adapters.py`, `instahyre_engine.py`, `browser_use_applier.py` |
| Cloud entry point | `cloud_runner.py` — what GitHub Actions and Hugging Face run |
| Flask control panel | `main.py` routes → `templates/dashboard.html` (Jinja) on port 7860 |
| Telegram Mini App | `templates/miniapp.html`, served verbatim at `/miniapp` + `/app` |
| Public GitHub Pages board | `docs/index.html` (Tailwind CDN, 233-row embedded snapshot) |
| Second product | `tn-live-jobs/` — Node 20 scraper → verifier → exporter + its own static board under `public/` |
| CI | `.github/workflows/job_bot.yml` (scrape + bot cycle, 11:00 & 19:00 IST) and `static.yml` (Pages deploy of `docs/`) |
| Data | `unified_jobs.json`, `national_drives.json`, `tn_jobs_cache.json`, `walkin_drives.json`, radar/dedup state files |

The runtime dependency chain is pinned in `requirements.txt`, with `browser-use` deliberately
excluded (markdownify conflict, documented in the file).

---

## 2. Bugs found and fixed

Everything below was reproduced before the fix and re-verified after it.

### 2.1 `docs/index.html` — 23 card buttons were dead on the live site

Card handlers were assembled as
`onclick="populateATSMatcher('${escapeHtml(j.role)}', …)"`. `escapeHtml()` produces `&#39;`,
but the HTML parser decodes that back to `'` **before** the handler is compiled, and raw
newlines from multi-line descriptions survive too. Result: `SyntaxError` on click.

* Measured on the previous revision: **23 of the rendered handlers fail to compile**, e.g.
  `populateATSMatcher('Vendor Consultant…', 'ADCI - BLR 14 SEZ - F07', 'About Amazon.com … Earth's most customer-centric …')`
  → `SyntaxError: missing ) after argument list`.
* 6 of the 233 bundled jobs contain apostrophes in their description, so this was live breakage,
  not a theoretical one.
* Fixed by moving the values into `data-*` attributes (`atsFromEl(this)`), which is escape-safe
  by construction.

### 2.2 `docs/index.html` — city filter crashed in Safari

`filterWalkinsCity()` read the non-standard global `window.event`. Safari does not provide it,
so tapping Chennai/Coimbatore threw `ReferenceError` and did nothing. The element is now passed
from the markup.

### 2.3 `docs/index.html` — modal bypassed the URL scheme check

The details modal assigned the raw scraped URL to `href` (`applyBtn.href = applyUrl`), skipping
the `safeUrl()` check that every other link goes through — a `javascript:` URL from the feed
would have executed on click. It now goes through `safeUrl()` and disables itself when no
`https` link was published.

### 2.4 `templates/miniapp.html` — injection in the apply buttons

`openApplyLink('${job.link}', event)` interpolated the scraped URL raw into an inline handler:
a link containing a quote broke the handler, and `javascript:alert(1)` was offered as a
working Apply button (reproduced). URLs now travel via `data-*` attributes, are scheme-checked
before opening, and an unusable link renders as a disabled *Link unavailable* control.

### 2.5 `templates/dashboard.html` — stored XSS in the radar feed

The radar list built markup with `${j.title}`, `${j.company}`, `${j.location}`,
`${j.description}` and `href="${j.link}"` straight from scraped LinkedIn/Indeed/Adzuna pages
into `innerHTML` — inside the operator's **authenticated** dashboard. All fields are now
escaped, links are scheme-checked, and a card without a usable link renders as plain text.
`logToConsole()` was also rebuilt to append DOM nodes instead of markup.

### 2.6 Backend (`main.py`, `instahyre_engine.py`)

| ID | Location | Bug | Fix |
| --- | --- | --- | --- |
| F1 | `main.py` `/apply` dry-run | `bot.send_message(chat_id, …)` used an **undefined** `chat_id`; the surrounding `except: pass` swallowed the `NameError`, so the dry-run notice was never delivered | use `message.chat.id` |
| F2 | `_DASHBOARD_OPEN_PATHS` | `"/"` was unauthenticated, and that route renders the **full** dashboard (job URLs, applied-jobs log, chat id, profile stats, channel list, Notion URL) | removed `"/"` from the allow-list; unauthenticated `"/"` now returns the harmless health JSON so the hosting health probe still gets 200 |
| F3 | `save_applied_job()` | read-modify-write spanned two lock acquisitions; concurrent apply threads clobbered each other. Reproduced: **37 of 40** concurrent additions lost, which means duplicate applications later | one reentrant lock (`RLock`) held across the whole operation |
| F4 | 5 JSON routes | `request.json` is `None` without a JSON body → `AttributeError` → HTTP 500 | `request.get_json(silent=True) or {}` |
| F5 | resume/auth upload | `endswith('.pdf')` rejected `Resume.PDF` | case-insensitive check |
| F6 | `main.py`, `instahyre_engine.py` | `from playwright_stealth import stealth_sync` — removed in playwright-stealth 2.x, while `requirements.txt` pins only `>=1.0.6`. A fresh install pulls 2.0.3 and **`import main` fails**, taking the bot and `cloud_runner` down | version-tolerant shim (1.x symbol → 2.x `Stealth().apply_stealth_sync()` → no-op) |

### 2.7 `tn-live-jobs/` (Node)

* `util.js` `unescapeEntities()` decoded `&amp;` first, so `&amp;lt;` became real `<` markup —
  reordered to the standard last position.
* `export.js`: job titles beginning with `=`, `+`, `-`, `@` were written as live spreadsheet
  formulas (CSV injection from scraped pages) → neutralised with a leading apostrophe.
* `export.js`: the board's footer links to `./data/jobs.csv` but only `data/jobs.csv` was ever
  written — a **404 download**; `public/data/jobs.csv` is now exported too.
* `cli.js` `runServe()`: `decodeURIComponent` on an unvalidated URL crashed the whole preview
  server on `/%ZZ`; the traversal guard used a bare `startsWith(PUBLIC_DIR)`, so
  `/../package.json` escaped the public root → now `path.resolve()` + separator-aware check, and a
  malformed escape returns 400.
* `cli.js` `runValidate()`: browser/context were only closed on the happy path → `try/finally`.
* `report.js`: the diff reader preferred a key (`newJobs`) that the CLI never writes, and the
  `removed` branch had no fallback → explicit `new`/`removed` handling.
* `public/app.js`: experience filter fix, `safeUrl()` allow-list, modal focus trap + restore.

---

## 3. UI: animations, responsiveness

* **docs board**: staggered card entrance (`--i` + `cardIn` keyframes), tab cross-fade, modal sheet
  animation, skeleton fallback when the snapshot can't load, hover lift restricted to pointer
  devices, animated stat counters, `viewport-fit=cover` + safe-area padding for the fixed bottom nav.
* **mini app**: staggered card entrance, skeleton retained, `safe-bottom` padding so the fixed bar
  clears the iOS home indicator.
* **command centre**: staggered radar cards, kept the existing glass/orb system, replaced the
  third-party texture PNG with an equivalent pure-CSS weave.
* **tn-live-jobs board**: 180 lines of new CSS — smoother transitions, skeleton loading, responsive
  breakpoints, higher-contrast text.
* Every animation is wrapped in `@media (prefers-reduced-motion: reduce)`; nothing animates for
  users who ask their OS not to.

---

## 4. Performance, SEO, accessibility

**Performance**

* `docs/index.html`: the 224 KB inline job snapshot moved to `docs/data/snapshot.js` — the document
  drops from **319,407 → 115,482 bytes** (−64%) and the payload is now cacheable on its own.
  Content is byte-identical (233 rows verified).
* Feed renders in pages of 40 with a *Show N more* control instead of building every matching card;
  search input is debounced (140 ms) instead of re-rendering on each keystroke.
* Removed the `transparenttextures.com` request from the dashboard; preconnects added for fonts/CDN.

**SEO**

* `docs/index.html`: meta description, canonical, `robots`, `theme-color`, Open Graph + Twitter tags,
  static `WebSite`/`Organization` JSON-LD, a runtime `ItemList` built only from real rows (no
  invented dates or salaries), and a `<noscript>` summary that crawlers and JS-off users can read.
* `tn-live-jobs`: canonical/OG/Twitter tags, `JobPosting` structured data derived from the existing
  rows (absent fields are omitted, not guessed), non-blocking font loading.
* Both app UIs are now `noindex, nofollow` — they are authenticated tools, not public content.

**Accessibility**

* Pinch-zoom is no longer blocked (`user-scalable=no` / `maximum-scale=1` removed) — WCAG 1.4.4.
* Skip links, `:focus-visible` rings, real `tablist`/`tab`/`tabpanel` semantics with `aria-selected`.
* Dialogs use `role="dialog" aria-modal="true"`, trap Tab, close on `Escape`, and restore focus.
* `aria-pressed` on every filter/save toggle, `aria-live` status regions, `role="log"` console,
  `role="progressbar"` on the countdown, `aria-label`s on all icon-only buttons, and decorative
  Lucide icons hidden from screen readers.

---

## 5. Preserved content, assets and integrations

* All 233 bundled job rows, walk-in/drive cards, saved-jobs `localStorage` key, CSV export, ATS
  matcher, in-hand salary calculator, cold-pitch generator, Telegram WebApp buttons, share targets
  and filter/tab behaviour are intact — the new regression tests assert they still work.
* `dashboard_FINAL.html` and `dashboard_pro.html` (orphaned duplicates that nothing references)
  were left untouched rather than deleted.
* No dependency was added to the runtime: `jsdom` is a devDependency for tests only, and
  `requirements.txt` is unchanged.
* All generated data files, the Pages deploy workflow, the bot workflow and every credential
  contract (`.env.example` names, `DASHBOARD_TOKEN`, secrets) are unchanged.

---

## 6. Test results (all offline, no network, no Telegram, no applications)

| Suite | Command | Result |
| --- | --- | --- |
| Docs board (jsdom) | `npm test` → `tests/docs_page.test.js` | 10 pass |
| Docs markup/SEO | `tests/docs_markup.test.js` | 6 pass |
| Mini app (jsdom, hostile data) | `tests/templates.test.js` | 5 pass |
| Templates (Jinja) | `python -m unittest tests.test_dashboard_templates` | 9 pass |
| Bot regression suites | `python -m unittest test_job_discovery test_backend_hardening` | 38 pass |
| CareerOps integration | `python -m pytest test_careerops_integration.py -k "not network and not live and not adzuna and not scrape"` | 4 pass |
| TN Live Jobs | `node --test tn-live-jobs/test_priority_cities.js` | 21 pass (4 pre-existing + 17 new) |
| Compile | `python3 -m py_compile` on all modules | clean |
| Syntax | `node --check` on every JS file (19 files) | clean |
| `import main` | was `ImportError` on a fresh install | now succeeds |

**Regression value:** running the new suites against the previous revision fails **7/10 docs-board
checks, 4/5 mini-app checks and 4/9 template checks** — they reproduce the bugs above rather than
just describing them.

---

## 7. Every modified file

| File | Change | Why |
| --- | --- | --- |
| `main.py` | M (+75/−18) | F1 undefined `chat_id`, F2 dashboard auth hole, F3 atomic dedup, F4 JSON guards, F5 case-insensitive uploads, F6 stealth compat |
| `instahyre_engine.py` | M (+19/−1) | F6 stealth compat |
| `docs/index.html` | M (+639/−276) | 3 bug fixes, pagination, debounce, a11y, SEO, animations, external snapshot |
| `docs/data/snapshot.js` | A | The 233-row snapshot, moved out of the HTML verbatim |
| `templates/dashboard.html` | M | radar XSS fix, safer console logger, noindex, a11y, CSS weave instead of the texture CDN |
| `templates/miniapp.html` | M | apply-button injection fix, scheme checks, zoom, a11y, animations |
| `tn-live-jobs/src/util.js` | M | entity double-decode |
| `tn-live-jobs/src/export.js` | M | CSV injection guard + missing `public/data/jobs.csv` |
| `tn-live-jobs/src/cli.js` | M | browser leak, traversal, malformed-URI crash |
| `tn-live-jobs/src/report.js` | M | diff key robustness |
| `tn-live-jobs/public/app.js` | M | experience filter, `safeUrl`, focus trap, live region, JSON-LD |
| `tn-live-jobs/public/index.html` | M | canonical/OG, skeleton, a11y wiring, non-blocking fonts |
| `tn-live-jobs/public/style.css` | M | responsive + contrast + animation layer, reduced motion |
| `tn-live-jobs/package.json` | M | `npm test` script |
| `tn-live-jobs/test_priority_cities.js` | M | +17 offline tests |
| `test_backend_hardening.py` | A | 7 regression tests for F1–F6 |
| `tests/docs_page.test.js` | A | 10 jsdom checks for the public board |
| `tests/docs_markup.test.js` | A | 6 SEO/a11y/markup checks |
| `tests/templates.test.js` | A | 5 jsdom checks for the mini app with hostile data |
| `tests/test_dashboard_templates.py` | A | 9 Jinja render/escaping/parse checks |
| `tests/README.md` | A | how to run the suites + ready-to-paste CI snippet |
| `tests/__init__.py` | A | package marker for `python -m unittest tests.…` |
| `package.json` | A | test harness (`npm test`), jsdom devDependency |
| `package-lock.json` | A | locks the test harness |
| `.gitignore` | M | ignore root `node_modules/` |
| `README.md` | M | document the new offline suites |
| `UPGRADE_NOTES_backend.md` | A | full backend audit trail |
| `UPGRADE_NOTES_tnlive.md` | A | full TN Live Jobs audit trail |

---

## 8. Behaviour changes you should know about before merging

1. **`/` on the Flask dashboard now requires the token.** It returns the health JSON to
   unauthenticated callers instead of the full dashboard. `/healthz` is unchanged, so hosting
   health probes stay green — but if you were opening the panel without `?token=…`, you will now
   need it. (This is what `.env.example` already documents: “the dashboard refuses every route”.)
2. **`docs/index.html` now loads `docs/data/snapshot.js`** — keep the two files together when
   copying the page; the Pages workflow already uploads the whole `docs/` folder.
3. **A card with no `https` link now shows “Link unavailable”** instead of a dead button.
4. `save_applied_job("")` is a no-op instead of storing an empty entry.

---

## 9. Not done, and why

* **No browser-level visual pass.** Chromium cannot launch in this sandbox (missing `libglib`,
  no root), so screenshots/pixel checks were not possible. Layout was verified structurally in
  jsdom (rendered DOM, class names, ARIA wiring) — worth one manual look before merging.
* **Live network paths were not exercised** (`/search`, JobSpy, Adzuna, Telegram sends) — that
  needs your credentials and would publish real messages. All new tests are offline by design.
* **Tailwind’s CDN compiler is still used** on all three UIs. Moving to a build step would cut
  runtime cost further but is a larger change than “don’t rebuild the project from scratch”.
* **`dashboard_FINAL.html` / `dashboard_pro.html`** are unused duplicates and were deliberately
  left in place pending your decision.

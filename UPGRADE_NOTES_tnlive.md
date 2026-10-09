# TN Live Jobs — audit, bug fixes, UI/SEO/a11y upgrade

**Scope:** files under `tn-live-jobs/` only (`src/*.js`, `src/sources/*.js`,
`public/index.html`, `public/app.js`, `public/style.css`, `test_priority_cities.js`,
`package.json`). No root Python files, `docs/`, `templates/`, `.github/` or generated
data JSON were touched.
**Branch:** `cline/1q8j1vf8` · **Node:** v24.21.0 · **New runtime dependencies:** none.

---

## 1. Verification summary

| Check | Command | Result |
| --- | --- | --- |
| Syntax of every JS file | `for f in src/*.js src/sources/*.js public/app.js test_priority_cities.js; do node --check "$f"; done` | **19/19 OK** |
| Offline test suite | `node --test tn-live-jobs/test_priority_cities.js` | **21 pass / 0 fail** (4 pre-existing + 17 added) |
| npm test script | `npm test` (new) | runs the same suite |
| HTML sanity | id uniqueness + tag-balance script | 56 ids, **0 duplicates**, all tags balanced |
| app.js <-> index.html wiring | every `getElementById(...)` id resolved against the HTML | **53/53 present** |
| CSS integrity | brace balance + feature grep | 180 `{` / 180 `}`; `focus-visible` + `prefers-reduced-motion` present |
| Preview server hardening | real `runServe()` extracted and driven over HTTP | **7/7 PASS** (`/`->200, `/style.css`->200, `/../package.json`->403, `/%2e%2e/package.json`->403, `/..%2f..%2fpackage.json`->403, `/%ZZ`->400, missing->404) |

> Note: `playwright` is not installed in this sandbox, so the scraping/verification CLI
> steps (`npm run scrape` etc.) cannot be executed here. All new tests are fully offline
> and stub the DOM for the browser code.

---

## 2. Backend bug fixes

### 2.1 `src/util.js` — `unescapeEntities()` double-decoded entities
- **What:** moved the `&amp;` -> `&` replacement to the **end** of the chain (after `&lt;`/`&gt;`).
- **Why:** decoding `&amp;` first turned the literal text `&amp;lt;` into `&lt;` and then into
  `<`, i.e. text a page intended to *display* as markup became real markup. `&amp;` last is the
  standard correct order.
- **Evidence:** new test `unescapeEntities does not double-decode a literal &amp;lt;`
  asserts `'&amp;lt;tag&gt;'` -> `'&lt;tag>'`.

### 2.2 `src/export.js` — CSV formula injection + broken public CSV link
- **What:** `csvCell()` now prefixes any cell starting with `= + - @ TAB CR` with an
  apostrophe before the existing quote-escaping. `writeOutputs()` now also writes the
  verified jobs to `public/data/jobs.csv`.
- **Why (injection):** job titles/companies come from scraped third-party pages. A title
  like `=cmd|' /C calc'!A0` would execute as a formula when the CSV is opened in Excel /
  LibreOffice. Prefixing keeps it inert plain text.
- **Why (link):** `public/index.html` footer links to `./data/jobs.csv`, but the export only
  wrote `data/jobs.csv` (project root) — the download link on the board was a **404**. The
  board now ships `public/data/jobs.csv` (verified jobs only, consistent with `public/data/`).
- **Evidence:** new tests `CSV export quotes separators and neutralises spreadsheet formulas`
  and `CSV export keeps every job on its own row`.

### 2.3 `src/cli.js` — browser/handle leak + preview-server traversal & crash
- **What (leak):** `runValidate()` now wraps `validateJobs()` in `try { … } finally { … }` so
  `context.close()` and `scraper.closeBrowser()` always run.
- **Why:** previously, if `validateJobs()` threw, the close calls were skipped, leaking a
  Chromium process and its file handles for the rest of the run.
- **What (security):** `runServe()` now
  1. wraps `decodeURIComponent` in try/catch (a malformed `%` escape such as `/%ZZ` threw an
     uncaught `URIError` and **crashed the whole server**), and
  2. resolves the request path with `path.resolve()` and checks
     `target === PUBLIC_DIR || target.startsWith(PUBLIC_DIR + path.sep)`.
- **Why:** the old `target.startsWith(PUBLIC_DIR)` check is prefix-based, so `/../package.json`
  resolved to `/workspace/tn-live-jobs/package.json`, and a sibling folder named `public-secret`
  would also have matched — a **path-traversal** hole in the local preview server.
- **Evidence:** extracted the real `runServe()` function and drove it over HTTP -> 7/7 PASS
  (traversal now 403, malformed escape now 400 instead of crashing).

### 2.4 `src/report.js` — diff key handling made explicit/robust
- **What:** `const newList = d.new || d.newJobs || []` and
  `const removedList = d.removed || d.removedJobs || []`.
- **Why:** the CLI writes the diff payload with the keys `new` / `removed`, while the reader
  preferred the (never-present) `newJobs`; the `removed` branch had no fallback. It worked by
  accident; it is now explicit and tolerant of either key shape.
- **Evidence:** new test `report renders new and gone sections from the CLI diff payload keys`
  asserts the `New this run (1)` **and** `Gone since last run (1)` sections render.

---

## 3. Frontend UI/UX, accessibility

### 3.1 `public/index.html`
- **SEO/head:** added `robots`, `theme-color` (light/dark), `canonical`, full Open Graph
  (`og:type/site_name/title/description/locale/url`) and Twitter card tags; added a
  `application/ld+json` script (`#jobsJsonLd`) populated at runtime.
- **Performance:** the Google Fonts stylesheet is now `rel="preload" as="style"` plus a
  non-blocking `media="print" onload="this.media='all'"` link with a `<noscript>` fallback, so
  text paints immediately with the system fallback font instead of blocking first render.
- **Accessibility:**
  - keyboard **skip link** to the listings;
  - `role="search"` wrapper + `aria-describedby` hint for the search box;
  - quick chips changed from a misleading `role="radiogroup"` (no radios) to `role="group"`
    with real `aria-pressed` state;
  - the huge `#list` grid no longer carries `aria-live` (which made screen readers read every
    card); a dedicated visually-hidden `#srStatus` live region announces result counts instead;
  - `#list` exposes `aria-busy` while loading;
  - the dialog has `aria-labelledby`/`aria-describedby`; the theme-toggle and bookmark buttons
    expose `aria-pressed`;
  - a `<noscript>` note offers the raw JSON/CSV.
- **Bug fix:** footer "Download CSV (Excel)" now points at a file the export actually writes
  (see 2.2).

### 3.2 `public/style.css`
- **Contrast (WCAG AA):** darkened light-theme `--text-muted` (`#64748b`->`#52606f`) and
  `--text-subtle` (`#94a3b8`->`#5a6b80`), and lightened dark-theme tokens (`--text-muted`
  `#94a3b8`->`#a9b6c8`, `--text-subtle` `#64748b`->`#8b9bb4`); the old subtle greys were
  about 2.6:1 on the page background.
- **Focus:** one consistent `:focus-visible` ring for links, buttons, inputs, selects and
  `[tabindex]`; `.skip-link` styling.
- **Motion:** card entrance keyframe (`cardIn`) + shimmer skeleton, all disabled under
  `@media (prefers-reduced-motion: reduce)` (which also forces `scroll-behavior:auto` and drops
  the hover transform).
- **Layout stability:** `.cards { min-height: 240px; align-content: start }` plus skeleton cards
  reserve space so the footer does not jump while data loads.
- **Touch targets:** icon-only buttons (`.btn-theme`, `.modal-close`, `.btn-bookmark`) get a
  40x40px minimum.
- **Responsive:** extra 900px (auto-fill 280px) and 560px (single column, single-column filters,
  full-width toast) breakpoints; `.sr-only`, `.noscript-note` utilities.
- **State styling:** `.chip[aria-pressed="true"]` mirrors the visual active chip.
- Existing dark/light theme, search, filters, CSV/export and every existing class are preserved.

### 3.3 `public/app.js`
- **Bug fix — experience filter:** `matchesExperience()` used loose digit regexes
  (`/1|2|3\s*years?/`), so a "10 years" job matched the **1–3 Years** filter. Added
  `experienceYears()` (reads the first real number, treats fresher/0 as 0) and ranges:
  fresher -> `is_fresher` or 0 yrs; mid -> 1–3; senior -> >=3.
- **Security — URL sanitising:** new `safeUrl()` only allows `http(s)://`, otherwise `#`. Used
  for card "Apply Now" hrefs, the modal Apply button and all share/copy actions. Previously a
  tampered data file could inject a `javascript:` URL into an `href`.
- **Accessibility — dialog focus management:** opening a card stores the trigger, moves focus to
  the close button, traps `Tab`/`Shift+Tab` inside the dialog, and restores focus to the trigger
  on close.
- **Accessibility — state:** theme toggle, bookmark button and quick chips expose `aria-pressed`;
  a new `announce()` helper writes filter-result counts to `#srStatus`.
- **UX — loading:** `renderSkeleton()` paints six shimmer placeholders and sets `aria-busy` while
  `jobs.json` is fetched; boot is wrapped in try/catch so a fetch failure degrades to the empty
  state instead of an unhandled rejection.
- **SEO:** `updateSeoMeta()` sets canonical + `og:url` from `location` and generates a schema.org
  `ItemList` of up to 50 `JobPosting` entries (title, dates, employment type, organisation, TN
  location, sanitised URL) from the already-loaded jobs — no extra request.
- **Keyboard:** the `/` shortcut no longer hijacks typing inside inputs/selects/textareas.
- **Robustness:** header count guard avoids "undefined live verified jobs"; `highlightText()` no
  longer reuses a global `/g` regex with `.test()` (stateful `lastIndex` — a latent fragility);
  share popups add `noopener`.

---

## 4. Tests added (`tn-live-jobs/test_priority_cities.js`)

The existing 4 tests were kept unchanged. 17 new offline tests were added:

- CSV: quote/separator escaping, formula neutralisation, BOM, one row per job.
- Diff/history: `computeDiff` new/kept/removed, `appendHistory` 500-run cap, `readJobFile` on a
  missing file.
- Report: renders `new` **and** `removed` sections from the CLI diff payload.
- Util: `unescapeEntities` (no double-decode), `cleanUrl`/`jobId` stability, `registrableDomain`
  multi-part `.gov.in`, `timestampToIsoDate` (s/ms/garbage), `detectExperience`, `isFresher`,
  `detectDeadline`, `cleanSummary`.
- Frontend (`public/app.js` loaded in a minimal `node:vm` DOM sandbox — no new dependency):
  the fixed experience filter, HTML-escaping search highlighting, and `safeUrl` scheme allow-list.

Result: `node --test tn-live-jobs/test_priority_cities.js` -> **21 pass / 0 fail**.

---

## 5. Suspected bugs found but NOT fixed (flagged for the owner)

1. **`src/export.js` safety guard is narrower than its comment.** It only refuses to overwrite
   when `rawScrapedCount === 0`. If sources return records but *all* fail verification, the good
   `public/data/jobs.json` is replaced by an empty list. Left alone because the opposite
   behaviour would keep stale/expired jobs on the board forever — it needs a product decision
   (e.g. also require that no source reported `ok`).
2. **`src/validate.js` `SEARCH_URL` misses trailing-slash search URLs.** The `jobs-in-[a-z-]+$`
   alternative does not match `/jobs-in-chennai/` (trailing `/`), so some "redirected to a search
   page" cases may still be marked verified. Not reproducible offline.
3. **`src/scraper.js` maps are never pruned** (`domainChains`, `domainLastUsedAt`, `deadDomains`).
   Bounded per run in practice, but unbounded for a very long-lived process.
4. **`src/util.js` `detectSalary` can capture partial matches** (e.g. a bare number followed by
   "month"); a data-quality risk only — left unchanged so published values are not altered.
5. **`src/sources/*` scraping correctness is unverified** — Indeed/Naukri/apna/LinkedIn/
   Internshala selectors depend on live HTML and a headless browser, neither available offline.
6. **No `og:image`.** A real social preview image needs a binary/generated asset, which is
   outside the allowed scope; the card type is `summary` for now.
7. **`src/cli.js` `parseArgs` only accepts `--step=value`**, not `--step value`. Left as-is to
   avoid changing the documented interface.
8. **`highlightText` fragility** (global regex + `.test()`) was *hardened*, but no input was
   found where the old code produced a visibly wrong highlight — it worked by accident. Listed
   for transparency rather than as a confirmed user-visible bug.

---

## 6. Files changed

```
tn-live-jobs/src/util.js                    entity decoding order
tn-live-jobs/src/export.js                  CSV injection guard + public/data/jobs.csv
tn-live-jobs/src/cli.js                     try/finally browser close + safe preview server
tn-live-jobs/src/report.js                  diff key robustness
tn-live-jobs/public/index.html              SEO meta, JSON-LD, a11y, no-CLS loading, fixed CSV link
tn-live-jobs/public/style.css               contrast, focus-visible, reduced-motion, skeleton, responsive
tn-live-jobs/public/app.js                  filter bug, URL sanitising, focus trap, live region, JSON-LD
tn-live-jobs/test_priority_cities.js        +17 offline tests (21 total)
tn-live-jobs/package.json                   added "test" script
UPGRADE_NOTES_tnlive.md                     this report
```

No runtime dependencies were added; all existing features (dark/light theme, search, quick
chips, filters, sort, save/bookmark, share, CSV/JSON export, load-more, URL sync) are intact.

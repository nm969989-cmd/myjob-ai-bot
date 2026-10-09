# 1. OBJECTIVE

Enhance the job search so it returns higher-quality matches **and** lets the
user pull more results on demand. Deliver this incrementally, "one by one":

1. Improve match quality of the Telegram bot's multi-source search.
2. Add a "Search More / Next Page" action so the bot can show results beyond the
   current hard cap of 6.
3. Enhance the static web job board's search experience.

The problem, in operational terms: the bot's `/search` and `/jobspy` commands
call `search_jobs_multi_source(query, limit=6)` and can never show more than 6
results, and there is no way to page past them. Matching is also rigid (exact
substring synonyms, no typo tolerance, no automatic fallback), so a slightly
misspelled or narrow query can return nothing. The static board already has
search + "Load More" but its search can be strengthened.

# 2. CONTEXT SUMMARY

Two independent search surfaces share a job dataset.

**A. Telegram bot**
- `bot_optimizer.py`
  - `search_jobs_multi_source(query, limit=6)` (approx L3190): fans out across
    preferred-city live search, saved walk-ins, national drives, scraped TN jobs,
    TN radar cache, live Adzuna, live JobSpy, and SimplifyJobs; dedupes via
    `canonical_link`, ranks with `calc_relevance`, and finally
    `rank_jobs(...)` then slices `[:limit]`.
  - `format_search_results_report(query, results)` (approx L3476): builds the
    HTML cards and the `InlineKeyboardMarkup`. Current buttons include
    "🔄 Refresh Search" (`callback_data=f"search:{query}"`) but no paging.
  - `fetch_jobspy_live_search` (L3079), `fetch_live_adzuna_search`
    (approx L3020), `fetch_simplify_jobs`, `get_walkin_drives`,
    `get_national_drives`, `get_tn_scraped_live_jobs`.
- `main.py`
  - `/search` + `/find` → `handle_search_command` (L7307).
  - `search:` callback → `handle_search_callback` (L6237).
  - `jobspy:` callback → `handle_jobspy_callback` (L6051).
  - `/jobspy`,`/livejobs`,`/spy`,`/glassdoor` → `handle_jobspy_command` (L7173).
- `job_discovery.py`
  - `PRIORITY_CITIES` (L16) and `PRIORITY_LABEL` (L22).
  - `priority_city`, `city_matches`, `canonical_link`, `rank_jobs` (L54).
  - `fetch_priority_search(query, fetchers, limit=8, timeout=25)` (L302): queries
    each preferred city, caches in-flight work via `_SEARCH_TASKS`.

**B. Static web board** (`tn-live-jobs/public/`)
- `app.js`: `PAGE_SIZE = 24`, `state.visibleCount`, `matchesSearch` (L195,
  "every token must be present"), `searchHaystack` (L174), `applyFilters`
  (L241), `renderListOnly` (L434), and an existing **Load More** button
  (`els.loadMoreBtn`, L711). `index.html` has the markup (`#loadMoreBtn`).
- `index.html` has no build step (per AGENTS.md) — edit source directly.

**Constraints / conventions (from AGENTS.md)**
- **No invented data.** Never backfill a field with a guess; `null` or drop.
- `verified: true` is the publication gate for the board's `public/data/`.
- City list lives in two places — `tn-live-jobs/src/config.js` and
  `job_radar.py`; `test_priority_cities.js` asserts they don't drift.
- Dashboard filter values are capitalised (`Chennai`, `Full-time`).
- `index.html` has no build step and its CSS/HTML is considered complete — avoid
  redesigning without cause.
- Tests are offline by design ("no real scraping, applications, or Telegram
  sends" per `test_job_discovery.py`); `pytest -q` runs the suite.
- `python-jobspy==1.1.82` is pinned; `browser-use` is deliberately excluded.

# 3. APPROACH OVERVIEW

Work in three incremental, independently shippable phases (one by one), each
verified before moving on.

- **Phase 1 — better matching (bot).** Extend `calc_relevance` and token
  handling in `search_jobs_multi_source`: broaden the `SYNONYMS` table, add
  light typo tolerance (e.g. difflib close-match on tokens), give preferred-city
  hits and title matches more weight, and add an automatic relaxation fallback
  when a query yields zero results (retry with the primary token / a broader
  synonym). Keep the "no invented data" rule: only re-rank existing items, never
  fabricate fields.
- **Phase 2 — pagination / "Search More" (bot).** Thread a page/offset through
  the search so the bot can show results 1–6, then 7–12, etc., via a
  **"➡️ Search More"** inline button. Because `search_jobs_multi_source`
  currently fetches a bounded candidate set and slices, the plan is to fetch a
  larger candidate pool (e.g. `limit * (page+1) + buffer`), rank once, then
  return a slice plus metadata (total available, next page present/absent). The
  report formatter renders a "Search More" button carrying `query` and `page`.
- **Phase 3 — web board (app.js/index.html).** Strengthen `matchesSearch` to
  be more forgiving (token synonyms/near-match, "any-token" fallback ranking),
  and improve the empty-state / load-more UX. The board already has paging; this
  phase improves quality, not pagination.

Rationale: the bot is where "search more" is genuinely missing, so phases 1–2
target it; phase 3 covers the other search surface requested by "do all".

Alternatives considered:
- Persisting a server-side result cache keyed by chat/query (like
  `_SEARCH_TASKS`) to serve pages. Rejected as primary approach because it adds
  state/eviction complexity; re-querying with a bigger pool is simpler and
  matches the existing stateless style. (A short-lived cache may still be used
  to keep paging fast — see Step 4 note.)
- Redesigning the board's search UI. Rejected — AGENTS.md says the board UI is
  intentionally complete and has no build step.

# 4. IMPLEMENTATION STEPS

## Phase 1 — Improve bot match quality

**Step 1. Broaden synonym & alias coverage**
- Goal: more queries match relevant jobs (e.g. `frontend`, `backend`, `qa`,
  `sde`, city aliases already partly covered).
- Method: expand the `SYNONYMS` dict in `search_jobs_multi_source`; keep the
  existing `PRIORITY_CITIES` alias injection. Add common role families
  (full-stack, devops, testing, support, etc.) without inventing job data.
- Reference: `bot_optimizer.py` `search_jobs_multi_source` (L3208–3224).

**Step 2. Add typo tolerance and smarter weighting**
- Goal: `pyhton` still finds Python roles; title/company/city matches outrank
  incidental description hits.
- Method: in `calc_relevance` (L3235), add a close-match pass using
  `difflib.get_close_matches` (or a small Levenshtein) against the haystack
  tokens, awarding a smaller score than exact matches. Keep existing exact-match
  weights (company 40 / title 30 / location 15 / general 5 / synonym 3).
- Reference: `bot_optimizer.py` `calc_relevance`.

**Step 3. Automatic relaxation fallback for empty results**
- Goal: a too-narrow or misspelled query returns *something* useful instead of
  the "no matching listings" card.
- Method: if `matches` is empty (or below a threshold) after all sources, retry
  once with a relaxed token set (drop the least-specific token, or use the
  primary token only), and mark the report as relaxed. Do not fabricate fields.
- Reference: `search_jobs_multi_source` tail (after L3452) and the no-results
  branch of `format_search_results_report` (L3534).

## Phase 2 — "Search More" pagination for the bot

**Step 4. Add page/offset parameters to the search**
- Goal: the search can return a chosen page of the ranked candidate set, and
  report whether more results exist.
- Method: add `page: int = 0` (and keep `limit`) to `search_jobs_multi_source`.
  Fetch a larger candidate pool for high pages (e.g.
  `pool = limit * (page + 1) + buffer`), dedupe/rank once with existing
  `rank_jobs`, then return the slice for that page. To keep paging fast and
  consistent, optionally cache the ranked pool briefly (short TTL keyed by
  query) and slice from it on subsequent pages. Return page metadata alongside
  the slice (e.g. via a small result object or a sentinel key) so the formatter
  knows if a next page exists.
- Reference: `bot_optimizer.py` `search_jobs_multi_source` (L3190, final
  `return rank_jobs(...)[:limit]` at L3462).

**Step 5. Render a "➡️ Search More" button**
- Goal: users can load the next batch from the results keyboard.
- Method: extend `format_search_results_report(query, results, page=0,
  has_more=False)` to append a row
  `InlineKeyboardButton("➡️ Search More", callback_data=f"search_more:{query}:{page+1}")`
  when `has_more`. Keep existing rows. Ensure `callback_data` length stays within
  Telegram's 64-byte limit (truncate/hash long queries, mirroring the existing
  `url_hash` pattern at L3498).
- Reference: `bot_optimizer.py` `format_search_results_report` (L3476–3532).

**Step 6. Wire the new callback in main.py**
- Goal: pressing "Search More" fetches and appends the next page.
- Method: add a `search_more:` callback handler that parses `query` and `page`,
  calls `search_jobs_multi_source(query, page=page)`, and sends the next chunk
  with its own "Search More" button (and a "⬅️ Dashboard" row). Also pass
  `page`/`has_more` from the existing `/search`, `jobspy:`, and `/jobspy`
  handlers so their first page already offers "Search More".
- Reference: `main.py` `handle_search_command` (L7307), `handle_search_callback`
  (L6237), `handle_jobspy_callback` (L6051), `handle_jobspy_command` (L7173).

## Phase 3 — Enhance the static web board search

**Step 7. Make board search more forgiving and rank matches**
- Goal: partial/near matches surface, and stronger matches sort first.
- Method: in `app.js`, keep `matchesSearch` as the strict gate but add an
  "any-token" or close-match fallback and a lightweight relevance sort used when
  a query is present. Preserve tokenized highlighting (`highlightText`).
  Do not touch capitalisation/URL-param rules from AGENTS.md.
- Reference: `tn-live-jobs/public/app.js` `matchesSearch` (L195),
  `searchHaystack` (L174), `applyFilters` (L241).

**Step 8. Improve board empty-state and "load more" affordance**
- Goal: clearer guidance when nothing matches, and obvious paging.
- Method: refine the empty-state copy/suggestions and ensure the existing
  "Load More Jobs (N remaining)" button remains correct after the new ranking.
  `index.html` has no build step — edit source directly and keep the existing
  class/markup structure.
- Reference: `tn-live-jobs/public/index.html` (`#empty`, `#loadMoreWrap`),
  `app.js` `renderListOnly` (L434) and the `loadMoreBtn` handler (L711).

# 5. TESTING AND VALIDATION

All tests are offline; do not hit real sources or Telegram.

**Automated**
- `python -m pytest -q` must stay green. Extend `test_job_discovery.py`
  (unittest style, mocks/patches) with new cases:
  - `calc_relevance`/matching: a misspelled token (`pyhton`) still scores a
    Python job above an unrelated job.
  - Synonym expansion returns a relevant job for a query that only matches via
    a synonym.
  - Fallback: a nonsense query still yields relaxed results, and fields are not
    fabricated (no guessed values).
  - Pagination: `search_jobs_multi_source(query, page=0)` and `page=1` return
    disjoint slices of one ranked list; `has_more` is `True` when more exist and
    `False` on the last page.
  - `format_search_results_report(..., has_more=True)` includes a
    `search_more:` button; `has_more=False` omits it. Assert `callback_data`
    length ≤ 64 bytes for a long query.
- Node board tests: `cd tn-live-jobs && node --test test_priority_cities.js
  test_client.js` must stay green (board is browser-tested via Playwright in CI).
- `node src/cli.js --help` / an unknown word still exits `2` (unchanged).

**Manual**
- Bot: `/search python` shows page 1 with a "➡️ Search More" button; tapping it
  shows the next, non-overlapping batch; the button disappears on the last page.
  `/search pyhton` (typo) returns Python roles. A nonsense query returns a
  relaxed result set rather than the empty card.
- Web board: run `cd tn-live-jobs && npm run serve` (http://localhost:5173);
  confirm search still highlights terms, near/partial matches appear, "Load
  More Jobs (N remaining)" counts are correct, and the empty state shows the
  improved guidance. Confirm no console errors and filters/URL sync still work.

**Success looks like**
- Bot search quality improves (typo/narrow queries still return relevant jobs),
  and users can page through beyond 6 results with "Search More".
- Board search is more forgiving without regressing existing filters, sort,
  highlighting, or paging.
- No invented data; all existing and new offline tests pass.

# Engineering-search optimization — draft, not runtime-verified

This change is stacked on `enhance/engineering-search-digests` at `f8b00ca3b2e93fb8c0ffbcb09d7ae40dddb70fd7` (PR #8), not on deployed main. It does not enable engineering mode, merge anything, change the existing website, or replace the current bot. Baseline main was `85bac8bee153de2d94ccbc8036349680a352c1a6`.

## Implemented changes and honest cost accounting

1. **Compile matching once per rank call.** Profile validation, role-alias expansion, branch/skill needles and supported-city distances are compiled once for a non-empty candidate set, rather than once for every unique job. Job title and description/skills text are normalized once each. Scoring weights, reason order, eligibility uncertainty, city-radius semantics, evidence gates and tie-breaks are unchanged. This reduces repeated normalization work, not the complexity of sorting (`O(n log n)`). Single-job `score()` remains compatible; compilation can cost more for tiny inputs. A 2,000-record fixture compares scores/order against an independent slow reference, but that test has not yet run.

2. **One Node query process and scan-file read per digest rotation.** Up to four saved searches use `--query-batch` over stdin, reading the same engineering snapshot once. Previously dispatch called `--query` separately for each search: four processes and four JSON reads for a four-search rotation. Single-query commands remain supported. Each result retains its own preset, ranking and validation error; Python processes results in saved-search order. A run-level subprocess failure sends nothing; a later profile error still allows earlier successful sends to be acknowledged. The 80-second batch timeout is bounded like the previous four 20-second calls, not a benchmarked latency improvement. No profile data is put on argv. No cross-owner cache is added.

3. **Bounded run-local public GET reuse.** Collection and verification share an exact-URL read cache for successful HTTP 200 responses only, for at most 10 seconds, 32 entries and 8 MB of response bodies. A repeated detail URL within that horizon can use one network request instead of two; outside the horizon it is fetched again. Production collection/verification stay serial; matching in-flight URLs are coalesced without introducing new host concurrency. The allowlist is checked on every call, including cache hits; network misses still go through the existing robots check, host delay, manual-redirect handling, response-size limit and timeouts. Failures, redirects and over-budget bodies are never cached. Deadline-expired calls cannot use the cache. Verification keeps the original response-fetch timestamp and reruns the existing strict heading/application/CAPTCHA checks. A page can change within the 10-second snapshot window; this is a deliberately bounded freshness trade-off, not a claim of continuous live validity. Cache hit rate and saved network time are unknown. Cache lifetime ends with the refresh invocation, not persisted state.

4. **Avoid byte-identical engineering JSON rewrites.** A narrowly scoped writer preserves the existing JSON format and every supplied record, skips a write only when serialized bytes exactly match disk, and otherwise writes a uniquely named same-directory temporary file and atomically renames it. This prevents partial JSON reads during a refresh. It still serializes and reads existing bytes; it is not an incremental database. Timestamped match/public payloads normally change and still write. An unchanged empty retry queue can avoid a rewrite. Private state remains on the original atomic 0600 path; no state, reminders, histories, retry entries or alerts are pruned by this change.

## Reviewed but intentionally not changed

- Legacy Node collection already shares a browser/context within its scrape stage, and validation already has concurrency 4. Engineering reads remain serial with 1.5-second host pacing, 15-second request timeouts and an eight-minute refresh budget. Adding parallel requests without a per-host scheduler would risk violating pacing; no browser-per-job speedup is claimed. Closed/seen records are not permanently skipped: seen is a delivery acknowledgement, not proof of closure, and rediscovered jobs still need fresh evidence. Existing retry exhaustion/deferral policies are unchanged.
- Dedupe is already map-based. Its identity/provenance algorithm and all historical/state schemas remain unchanged. Sorting remains bounded by existing candidate caps; no lossy truncation is introduced for speed.
- Python dashboard review found `/api/radar` loads its result JSON per request, mini-app aggregation reads local job records, and dashboard template reads happen per request. Private applied/profile loaders already have mtime caches. Whole HTTP-response caching could stale queue/pause/handoff/authorization state, so it is not added without execution and invalidation tests. The engineering saved-search computation is batched instead. This does **not** optimize every dashboard route.
- Scheduling keeps the existing lock, one poller, minimum 15-minute engineering interval and sleep after each cycle. Legacy cloud stages, follow-ups and radar cards are retained. Telegram engineering messages already use short digests; computation is batched, not delivery semantics. Seen state is persisted immediately after each successful send, never after a whole batch. Apply/share inline controls in the legacy radar are untouched.
- Current `.github/workflows/job_bot.yml` already caches pip, npm downloads and Playwright browsers; Pages is already path-filtered. No redundant cache installation is proposed. `npm ci` remains necessary to restore dependencies (the npm cache is not node_modules). Checkout uses full history for the existing rebase/push stage, so shallow checkout is not changed blindly. Chromium system dependencies on cache hits deserve a separate correctness check, not deletion. No workflow files are changed: the connected GitHub credential lacks the `workflow` scope, and the existing privacy/state-persistence review is still unresolved. No CI-minute savings are claimed.

## Verification status

**Verified by source inspection / GitHub receipts:** implementation scope, existing cache/browser behavior, additive opt-in wiring, and reviewable branch publication (see PR). Static call counts support the four-to-one process/read reduction; these are not executed benchmark results.

**Not verified:** Node/Python syntax execution, any unit test, measured runtime/RSS improvement, live source coverage, Telegram delivery, dashboard invalidation, Hugging Face launch or Actions integration. The Cloud Workspace shell/runner fails before commands produce output. Do not label this change production-ready or claim a percentage speedup. No live messages or applications were sent for optimization testing.

## Exact checks after runner recovery (from repository root)

Use Node >=20 and Python 3.11 with the repository dependencies in an isolated environment. None of the following commands were run here:

```sh
(cd tn-live-jobs && npm ci && npm run engineering:test)
node --test tn-live-jobs/test_priority_cities.js
python -m py_compile engineering_telegram.py engineering_app.py test_engineering_telegram.py test_engineering_optimization.py
python -m unittest test_engineering_telegram test_engineering_optimization test_job_discovery -v
python -m pytest test_careerops_integration.py -q -k 'not network and not live and not adzuna and not scrape'
```

No `|| true`: failures are failures. For an offline before/after ranking measurement, retain the baseline independently of the working tree:

```sh
BASE=$(mktemp -d)
git show f8b00ca3b2e93fb8c0ffbcb09d7ae40dddb70fd7:tn-live-jobs/src/engineering-search.js > "$BASE/before.cjs"
node --expose-gc tn-live-jobs/benchmark_engineering.js "$BASE/before.cjs"
BENCH_SIZES=1000,10000,50000 node --expose-gc tn-live-jobs/benchmark_engineering.js "$BASE/before.cjs"
rm -rf "$BASE"
```

The benchmark first asserts baseline/optimized output equality, then warms both, alternates order for five timings, and prints median milliseconds, Node/platform and final process RSS. Final RSS is **not** isolated per-version peak memory; use separate processes with `/usr/bin/time -v` if peak memory comparison is needed. Record actual numbers before deciding the CPU optimization helps at production sizes.

The offline Node/Python fixtures also check cache expiry/capacity, failure non-caching, same-URL coalescing, original verification timestamps, identical-file write avoidance, one subprocess per four-profile batch, errors and successful-send-only acknowledgements. They are assertions to run, not passing-test claims.

Only after offline checks pass: run one bounded refresh on an isolated checkout with permitted public sources and inspect integrity/retry output; do not widen routes to make a test pass. Compare `meta.duration_seconds`, record counts, evidence timestamps and source status between baseline and optimized runs, noting that live listings/network timing can change. For Telegram, use an explicitly configured private test bot/chat and temporary private state; verify repeated-scan quietness, integrity upgrades and partial-send recovery. Do not test by sending messages through the owner's production bot or submitting applications. Restore/retain opt-in configuration and review PR #8 separately before any rollout.
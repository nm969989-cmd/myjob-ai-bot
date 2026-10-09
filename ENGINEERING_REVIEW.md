# Engineering-search review and activation gates

This opt-in feature is not activated by merging a draft. The existing production main.py, Docker entrypoint and workflows are unchanged.

## Substantive hardening

- Node commands resolve the operator-installed executable to an absolute path, use a fixed checkout script and a closed option set, and pass profiles as JSON stdin with shell=False. PATH, Node and the checkout must remain operator-owned, not writable by chat users. Missing Node fails closed.
- Public reads validate exact HTTPS hosts and public routes before fetch, reject credentials/ports, and do not follow redirects. This is a restricted source reader, not a general URL proxy. Source failures remain uncertain, not evidence of closure.
- Robots patterns no longer construct regular expressions. A literal wildcard matcher has a shared 262144-step budget. Policies over 65536 characters and paths over 8192 characters fail closed; pathological matching throws and excludes the source. These caps intentionally tighten behavior for oversized/adversarial policies.
- Profile validation, scoring components and save-search handling are split into focused helpers. Scoring reason order and normal profile validation order are retained; regression tests still require execution.
- Non-object private state raises TypeError and is preserved rather than overwritten (previously ValueError). Tests cover this safety boundary.
- Input JSON reads are restricted to fixed engineering output filenames. Report filenames are fixed operator-owned checkout paths.

## Deliberate design findings, not checker suppressions

Binding Flask to 0.0.0.0:7860 is needed for the Hugging Face reverse-proxy/container ingress. Changing to loopback would break ingress. A production proxy/access-control review is still required; do not expose the Flask development server directly to an untrusted network.

subprocess import and invocation remain necessary. Resolving a fixed executable, shell=False, fixed options and JSON stdin address command construction; a generic static rule may still flag any subprocess call. This is not a claim that arbitrary operator configuration is safe.

Broad Exception handlers are external SDK/source command or scheduler boundaries, where failures have no closed taxonomy. They record/report failure without tokens/stdout and do not catch BaseException. Failed Telegram cards are not acknowledged. The broad handlers are intentionally retained rather than suppressing the checker or losing failure recovery.

Filesystem paths are dynamic values but not chat/URL-selected production paths. Atomic writer temporary names and mkdtemp test fixtures are inherently dynamic. Generic filesystem rules may still flag them. The checkout/state directories must be trusted and private; these comments do not prove symlink resistance.

On the optimization branch, the benchmark uses a literal checked-in baseline module rather than requiring an arbitrary CLI path. The optional baseline-path argument is intentionally rejected. Use `node --expose-gc tn-live-jobs/benchmark_engineering.js`; BENCH_SIZES selects sizes. The baseline preserves old scoring code for independent equality checks, so original complexity/style findings in that fixture may remain.

## Verification and CI boundary

No Python/Node test or benchmark execution is claimed for these edits. The available shell runner failed before producing output. Existing check services can analyze pushed draft heads, but static checks are not runtime verification.

Dispatching the existing Verify workflow for both engineering branches returned HTTP 422: `Workflow does not have 'workflow_dispatch' trigger`. This is trigger/configuration validation, not an observed permissions denial. Verify is absent on main and these feature branches. Production job_bot dispatch runs live scraping, Telegram/secrets and main pushes; Pages dispatch deploys docs. Neither is a safe substitute for isolated tests.

The current GitHub credential has repo access but lacks workflow scope for workflow-file writes. An owner must apply a reviewed isolated-test workflow, authorize workflow scope for that specific change, or provide a working isolated runner. Do not disguise workflow changes as hooks or change another PR's workflow.

## Production finish line (owner action after tests pass)

1. Run engineering Node tests (including fetch transport), Python telegram/optimization tests, existing offline regression checks and the deterministic benchmark/equality assertions. Confirm actual timing before claiming speedup.
2. Review robots/source permissions and perform a bounded isolated refresh. Inspect engineering matches, retry queue and source_status. Blocked sources remain blocked; no recovered coverage is implied by code changes.
3. Use a separate test bot/private chat to verify saved profiles/searches, refresh, digest limits, failed-send retries and existing legacy commands. Keep test state outside the checkout, permissions 0600, one writer.
4. Resolve Hugging Face Docker/hardware compatibility. Configure Node >=20, npm/Python dependencies, positive private TELEGRAM_CHAT_ID, existing bot token, DASHBOARD_TOKEN and persistent private ENGINEERING_STATE_DIR.
5. Stop the old bot poller and explicitly launch `python engineering_app.py` instead of `python main.py`. Never run both launchers or a companion poller on the same token. This operator entrypoint change is not performed by these draft commits.
6. Observe one refresh/digest cycle before production acceptance. Roll back by stopping the new launcher and restoring main.py. No automatic applications are submitted.

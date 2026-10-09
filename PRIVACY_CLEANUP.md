# Privacy cleanup: review and deployment notes

This cleanup removes personal/local artifacts from the proposed branch's current tree. It does not erase earlier commits, forks, caches or the separate Hugging Face repository. Do not treat it as token revocation or a complete secret-history audit.

## Removed files

- `resume.pdf`: the owner's personal resume. Supply your own resume privately through the authenticated dashboard/Telegram upload path or private deployment storage. A fresh checkout will show a missing resume until you provide one.
- `qa_memory.json`: saved screening answers. Existing code supports creating/loading local QA memory, but see the merge blocker below.
- `instahyre_login.html`, `instahyre_login_headful.html`: captured login pages, not required application source. Do not reuse captured public authentication/session material.
- `dashboard_FINAL.html`, `dashboard_pro.html`: retired root dashboard copies. The active Flask dashboard remains `templates/dashboard.html`; the public Pages app remains `docs/index.html` and the TN client remains `tn-live-jobs/public/`.
- `graphify-out/`: generated report, graph HTML/JSON, manifest, cost data and analysis memory notes. Regenerate privately when needed.
- `jobskull.txt`, `mphasis_text.txt`, `wipro_html.txt`: scratch extraction captures, not active application source.

## Retained and changed

`generate_resume.py` is retained because the dashboard invokes it. Personal contact/profile literals and career claims are replaced by obvious example placeholders; the PDF-building logic is preserved. This template does not read `profile.json`. Replace placeholders with your own verified data before generating a real resume. Never submit the example output. Keep personalized copies and PDFs private.

`.gitignore` now ignores the resume, QA memory, captured login pages, all Graphify output, scratch extracts and retired dashboard copies. Public job feeds, dedup state and their consumer paths are deliberately unchanged; deleting those would break existing feeds or reset alert behavior.

## Merge blocker: QA can be republished by Actions

The current `job_bot.yml` still explicitly uses `git add -f` on `qa_memory.json`. The optimizer can regenerate seeded QA when the file is absent. `.gitignore` does not override force-add. Therefore this cleanup alone does NOT keep QA private after a cloud run. Before merging, remove QA from that workflow's persistence list and verify the seeded answers/profile behavior. Those workflow/runtime changes are excluded here: the GitHub credential currently lacks `workflow` scope and the execution environment cannot run the required project checks. Do not use this draft as confirmation that privacy is fully fixed.

## Validation and remaining owner actions

Reference checks were text-only against GitHub source: the Python runtime modules and workflow files were inspected; the Flask dashboard and upload paths still refer to local resume/QA files and the retained generator. No Python, Node, browser, dependency or syntax checks were executed for this cleanup because the available shell fails before output. Prior passing checks apply to the earlier upgrade, not this branch. Re-run the README's offline checks when an executor is available.

Confirm Telegram token rotation via BotFather and update deployment secrets; this PR neither uses nor rotates the exposed token. Deploy separately to Hugging Face using Docker-compatible hardware, and remove equivalent public personal artifacts from that separate repository as well. Do not upload personal resumes into a public Space's source repository. History rewriting, credential revocation, license selection and any behavioral profile/QA changes require separate handling.

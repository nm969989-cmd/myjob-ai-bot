# Graph Report - Telegram_Job_Bot  (2026-09-30)

## Corpus Check
- 49 files · ~147,018 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 769 nodes · 1942 edges · 40 communities (36 shown, 4 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 116 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- job_radar.py
- save_chat_id
- bot_optimizer.py
- run_playwright_apply
- main.py
- load_chat_id
- instahyre_engine.py
- scrape_single_channel
- bot_features.py
- cloud_runner.py
- enterprise_adapters.py
- safe_load_json
- api_instahyre
- job_monitor_loop
- ResumePDF
- Reporting a Vulnerability
- 🚀 GitHub Actions 24/7 Cloud Automation Guide
- 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)
- Q: Why does run_playwright_apply connect across 4 separate communities?
- bypass_blog_redirect
- is_social_or_promo_link
- LoggerWriter
- enforce_bot_security_profile
- FPDF
- README.md
- TN Job Pipeline (ref_fs / countJobsBySource() / runReport())
- Module 26: export.js
- Module 27: api_force_scan()
- Module 28: generate_resume.py
- Module 29: SECURITY.md
- TN Job Pipeline (_tn_sort_key() / Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized… / Safely converts any date representation (YYYY-MM-DD, ISO string, RFC 2822, unix…)
- Module 31: GITHUB_ACTIONS_GUIDE.md
- TN Job Pipeline (HUGGING_FACE_DEPLOY_GUIDE.md / 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot) / 🚀 Step 1: Push Code to Hugging Face Space)
- Module 33: FPDF
- Module 34: query_20260928_193829_a1d41896_why_does_run_playwright_apply_connect_across_4_sep.md
- Telegram Bot Engine (wrapper() / get_authorized_chat_ids() / is_authorized())
- Module 36: LoggerWriter
- Module 37: FPDF

## God Nodes (most connected - your core abstractions)
1. `save_chat_id()` - 46 edges
2. `tidy()` - 41 edges
3. `admin_only()` - 39 edges
4. `makeJob()` - 33 edges
5. `run_all_tests()` - 31 edges
6. `registrableDomain()` - 27 edges
7. `run_playwright_apply()` - 25 edges
8. `fetchText()` - 25 edges
9. `run_radar()` - 24 edges
10. `scrape_single_channel()` - 24 edges

## Surprising Connections (you probably didn't know these)
- `run_all_tests()` --calls--> `get_watchdog_subscriptions()`  [EXTRACTED]
  test_features_verify.py → bot_optimizer.py
- `run_all_tests()` --calls--> `format_tamil_nadu_telegram_digest()`  [EXTRACTED]
  test_features_verify.py → job_radar.py
- `run_all_tests()` --calls--> `get_tamil_nadu_jobs()`  [EXTRACTED]
  test_features_verify.py → job_radar.py
- `scan_for_interview_invites()` --calls--> `get_gemini_client()`  [EXTRACTED]
  imap_handler.py → main.py
- `run_playwright_apply()` --calls--> `record_learned_qa()`  [EXTRACTED]
  main.py → bot_optimizer.py

## Import Cycles
- None detected.

## Communities (40 total, 4 thin omitted)

### Community 0 - "job_radar.py"
Cohesion: 0.06
Nodes (70): add_watchdog_subscription(), calculate_skill_match_score(), check_job_against_watchdogs(), dispatch_walkin_alerts(), extract_eligible_batch(), extract_experience_level(), extract_hr_email(), extract_job_salary() (+62 more)

### Community 1 - "save_chat_id"
Cohesion: 0.09
Nodes (46): get_watchdog_subscriptions(), Retrieves all active keyword subscriptions with mtime memory caching., callback_query_handler, admin_only(), api_update_profile(), command_scan_inbox(), handle_alertme_command(), handle_alerts_callback() (+38 more)

### Community 2 - "bot_optimizer.py"
Cohesion: 0.07
Nodes (42): base64, bs4, flask, google, groq, io, api_add_channel(), api_download_log() (+34 more)

### Community 3 - "run_playwright_apply"
Cohesion: 0.06
Nodes (40): apply_regex_fallback(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.…, ai_fix_selector(), api_manual_apply(), run(), _bezier_mouse_move() (+32 more)

### Community 4 - "main.py"
Cohesion: 0.16
Nodes (35): cheerio, makeJob(), scrape(), cleanFreshersworldTitle(), jobFromCandidate(), parseFreshersworldCard(), cheerio, { fetchText, makeJob } (+27 more)

### Community 5 - "load_chat_id"
Cohesion: 0.07
Nodes (35): tn_live_jobs_src_config_http_timeout_ms, tn_live_jobs_src_config_max_attempts, tn_live_jobs_src_config_max_delay_ms, tn_live_jobs_src_config_min_delay_ms, tn_live_jobs_src_config_render_timeout_ms, buildHeaders(), captureJsonFromPage(), { chromium } (+27 more)

### Community 6 - "instahyre_engine.py"
Cohesion: 0.13
Nodes (27): applyFilters(), attachEvents(), closeJobModal(), createCardHtml(), daysAgo(), els, escapeHtml(), fmtDate() (+19 more)

### Community 7 - "scrape_single_channel"
Cohesion: 0.13
Nodes (31): _api_request(), classify_location(), clean_html(), _get_radar_session(), get_tamil_nadu_jobs(), _fetch_channel_tn(), is_social_or_promo_link(), _keyword_match() (+23 more)

### Community 8 - "bot_features.py"
Cohesion: 0.14
Nodes (27): enrichJobRecord(), fetchJson(), tn_live_jobs_src_scraper_log, { fetchJson, makeJob, markDomainDead }, isTamilNaduLocation(), scrape(), scrapeSmartRecruitersCompany(), SMART_RECRUITERS_COMPANIES (+19 more)

### Community 9 - "cloud_runner.py"
Cohesion: 0.08
Nodes (23): ref_http, { buildReport, writeReport }, config, DATA_DIR, DIFF_FILE, fs, HELP, http (+15 more)

### Community 10 - "enterprise_adapters.py"
Cohesion: 0.11
Nodes (18): email, execute_greenhouse_adapter(), execute_lever_adapter(), execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Saves generated credentials to a secure local vault. (+10 more)

### Community 11 - "safe_load_json"
Cohesion: 0.10
Nodes (22): Exception, analyze_form_with_gemini(), api_debug_bot(), api_rotate_key(), application_worker(), auto_bug_fixer(), check_job_match(), cleanup_system_resources() (+14 more)

### Community 12 - "api_instahyre"
Cohesion: 0.09
Nodes (21): playwright, dependencies, cheerio, playwright, description, engines, node, license (+13 more)

### Community 13 - "job_monitor_loop"
Cohesion: 0.13
Nodes (20): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+12 more)

### Community 14 - "ResumePDF"
Cohesion: 0.15
Nodes (19): api_status(), daily_report_loop(), handle_button(), is_sleep_time(), load_applied_jobs(), load_channel_status(), load_retry_queue(), load_stats() (+11 more)

### Community 15 - "Reporting a Vulnerability"
Cohesion: 0.11
Nodes (17): CATEGORIES, CITIES, CITY_ALIASES, tn_live_jobs_src_config_enable_tier3, SEARCH_KEYWORDS, ALL_SOURCES, apna, companyCareers (+9 more)

### Community 16 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.16
Nodes (12): CoverLetterPDF, generate_dynamic_cover_letter(), FPDF, _sanitize_latin1(), sync_to_notion(), email_header, email_message, get_latest_otp() (+4 more)

### Community 17 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
Cohesion: 0.18
Nodes (16): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, csv, datetime, dotenv, functools, html, escape_md(), 📡 JOB RADAR — Multi-Platform Job Finder (India & Tamil Nadu Priority Engine)… (+8 more)

### Community 18 - "Q: Why does run_playwright_apply connect across 4 separate communities?"
Cohesion: 0.13
Nodes (15): ref_crypto, tn_live_jobs_src_config_default_category, APNA_CATEGORIES, { fetchText, makeJob }, parseApnaPayload(), {
  tidy,
  clip,
  slugifyValue,
  registrableDomain,
  detectCity,
  detectEmploymentType,
  detectExperience,
  unescapeJsonInScript,
}, { CITY_ALIASES, CATEGORIES, DEFAULT_CATEGORY }, cleanUrl() (+7 more)

### Community 19 - "bypass_blog_redirect"
Cohesion: 0.15
Nodes (17): createNoteCollector(), dropStaleTnpscNotices(), ensureWorkDir(), main(), parseArgs(), readNumber(), resolveCities(), resolveKeywords() (+9 more)

### Community 20 - "is_social_or_promo_link"
Cohesion: 0.29
Nodes (16): fetchText(), markDomainDead(), cheerio, clipTitle(), collectGovLinks(), DISTRICT_SITES, { fetchText, makeJob, markDomainDead }, govJobFromLink() (+8 more)

### Community 21 - "LoggerWriter"
Cohesion: 0.19
Nodes (15): ref_path, readWorkFile(), runAll(), runDiff(), runExport(), appendHistory(), computeDiff(), fs (+7 more)

### Community 22 - "enforce_bot_security_profile"
Cohesion: 0.16
Nodes (15): apply_rag_memory_fallback(), get_seeded_qa_memory(), Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions…, record_learned_qa(), clear_qa(), handle_qa_button() (+7 more)

### Community 23 - "FPDF"
Cohesion: 0.20
Nodes (14): dispatch_tamil_nadu_alerts(), format_tamil_nadu_telegram_digest(), load_seen_jobs(), mark_seen(), normalize_job_url(), Uses python-jobspy for Chennai, Coimbatore, Tamil Nadu & Bangalore India jobs., Formats recently posted Tamil Nadu jobs into clean, high-aesthetic HTML chunks…, Sweeps and directly dispatches Tamil Nadu job cards to the given or configured… (+6 more)

### Community 24 - "README.md"
Cohesion: 0.22
Nodes (13): cheerio, COMPANY_NAMES, {
  fetchText,
  fetchJson,
  makeJob,
  renderCapture,
  findJobObjects,
  markDomainDead,
}, jobPostingsFromLdJson(), locationFromLdJson(), salaryFromLdJson(), scrape(), scrapeFreshersworld() (+5 more)

### Community 25 - "TN Job Pipeline (ref_fs / countJobsBySource() / runReport())"
Cohesion: 0.21
Nodes (11): ref_fs, countJobsBySource(), runReport(), buildReport(), { clip }, { ensureDir }, escapeCell(), fs (+3 more)

### Community 26 - "Module 26: export.js"
Cohesion: 0.29
Nodes (11): CSV_COLUMNS, csvCell(), ensureDir(), fs, { log }, path, sortJobs(), toCsv() (+3 more)

### Community 27 - "Module 27: api_force_scan()"
Cohesion: 0.22
Nodes (8): api_force_scan(), _run(), api_instahyre(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan., Triggers the Instahyre mass-applier engine from the dashboard.

### Community 28 - "Module 28: generate_resume.py"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 29 - "Module 29: SECURITY.md"
Cohesion: 0.25
Nodes (7): 1. Private Disclosure, 2. What to Include, 3. Response Process, Best Practices for Deployments, Reporting a Vulnerability, Security Policy, Supported Versions

### Community 30 - "TN Job Pipeline (_tn_sort_key() / Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized… / Safely converts any date representation (YYYY-MM-DD, ISO string, RFC 2822, unix…)"
Cohesion: 0.29
Nodes (7): _tn_sort_key(), Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized…, Safely converts any date representation (YYYY-MM-DD, ISO string, RFC 2822, unix…, _priority_sort_key(), safe_date_timestamp(), send_radar_telegram(), _format_section()

### Community 31 - "Module 31: GITHUB_ACTIONS_GUIDE.md"
Cohesion: 0.33
Nodes (5): 🚀 GitHub Actions 24/7 Cloud Automation Guide, 📌 Repository Information, 🔑 Step 1: Set Up Encrypted Secrets on GitHub, 🚀 Step 2: Push the Enhanced Code to GitHub, ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

### Community 32 - "TN Job Pipeline (HUGGING_FACE_DEPLOY_GUIDE.md / 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot) / 🚀 Step 1: Push Code to Hugging Face Space)"
Cohesion: 0.33
Nodes (5): 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot), 🚀 Step 1: Push Code to Hugging Face Space, 🔑 Step 2: Configure Space Secrets, ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot), 📱 Step 4: Verify in Telegram

### Community 33 - "Module 33: FPDF"
Cohesion: 0.40
Nodes (4): FPDF, generate_dynamic_resume(), Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF., ResumePDF

### Community 34 - "Module 34: query_20260928_193829_a1d41896_why_does_run_playwright_apply_connect_across_4_sep.md"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Why does run_playwright_apply connect across 4 separate communities?, Source Nodes

### Community 35 - "Telegram Bot Engine (wrapper() / get_authorized_chat_ids() / is_authorized())"
Cohesion: 0.40
Nodes (5): wrapper(), get_authorized_chat_ids(), is_authorized(), Returns all authorized admin Telegram IDs (from env, saved file, and memory)…, Verifies whether the given Telegram User ID or Chat ID is an authorized admin.

## Knowledge Gaps
- **129 isolated node(s):** `1. Private Disclosure`, `2. What to Include`, `3. Response Process`, `Best Practices for Deployments`, `Supported Versions` (+124 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 310 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `FPDF` to `job_radar.py`, `bot_optimizer.py`, `scrape_single_channel`, `safe_load_json`, `🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)`, `Module 27: api_force_scan()`, `TN Job Pipeline (_tn_sort_key() / Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized… / Safely converts any date representation (YYYY-MM-DD, ISO string, RFC 2822, unix…)`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `cheerio` connect `main.py` to `README.md`, `api_instahyre`, `is_social_or_promo_link`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Why does `tidy()` connect `main.py` to `load_chat_id`, `bot_features.py`, `cloud_runner.py`, `Q: Why does run_playwright_apply connect across 4 separate communities?`, `bypass_blog_redirect`, `is_social_or_promo_link`, `README.md`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **What connects `1. Private Disclosure`, `2. What to Include`, `3. Response Process` to the rest of the system?**
  _129 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.056140350877192984 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.09183673469387756 - nodes in this community are weakly interconnected._
- **Should `bot_optimizer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0708245243128964 - nodes in this community are weakly interconnected._
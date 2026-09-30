# Graph Report - Telegram_Job_Bot  (2026-10-01)

## Corpus Check
- 49 files · ~147,018 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 819 nodes · 1970 edges · 47 communities (45 shown, 2 thin omitted)
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
- Module 38: README.md
- TN Job Pipeline (jobs.js)
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45

## God Nodes (most connected - your core abstractions)
1. `save_chat_id()` - 49 edges
2. `admin_only()` - 41 edges
3. `tidy()` - 41 edges
4. `run_playwright_apply()` - 35 edges
5. `makeJob()` - 33 edges
6. `registrableDomain()` - 27 edges
7. `scrape_single_channel()` - 26 edges
8. `fetchText()` - 25 edges
9. `run_radar()` - 24 edges
10. `detectCity()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `run_instahyre_mass_apply()`  [EXTRACTED]
  main.py → instahyre_engine.py
- `run_playwright_apply()` --calls--> `minify_form_html()`  [EXTRACTED]
  main.py → bot_optimizer.py
- `run_playwright_apply()` --calls--> `apply_regex_fallback()`  [EXTRACTED]
  main.py → bot_optimizer.py
- `load_qa_memory()` --calls--> `get_seeded_qa_memory()`  [EXTRACTED]
  main.py → bot_optimizer.py
- `run_playwright_apply()` --calls--> `record_learned_qa()`  [EXTRACTED]
  main.py → bot_optimizer.py

## Import Cycles
- None detected.

## Communities (47 total, 2 thin omitted)

### Community 0 - "job_radar.py"
Cohesion: 0.06
Nodes (57): base64, bs4, Exception, flask, google, groq, io, analyze_form_with_gemini() (+49 more)

### Community 1 - "save_chat_id"
Cohesion: 0.16
Nodes (35): cheerio, makeJob(), scrape(), cleanFreshersworldTitle(), jobFromCandidate(), parseFreshersworldCard(), cheerio, { fetchText, makeJob } (+27 more)

### Community 2 - "bot_optimizer.py"
Cohesion: 0.07
Nodes (35): tn_live_jobs_src_config_http_timeout_ms, tn_live_jobs_src_config_max_attempts, tn_live_jobs_src_config_max_delay_ms, tn_live_jobs_src_config_min_delay_ms, tn_live_jobs_src_config_render_timeout_ms, buildHeaders(), captureJsonFromPage(), { chromium } (+27 more)

### Community 3 - "run_playwright_apply"
Cohesion: 0.08
Nodes (36): check_for_interviews(), check_job_against_watchdogs(), generate_linkedin_outreach_note(), Checks if a job dictionary matches any active keyword subscriptions., Checks if a job dictionary matches any active keyword subscriptions., Generates a personalized, professional LinkedIn connection note (<= 300…, Generates a personalized, professional LinkedIn connection note (<= 300…, get_channel_session() (+28 more)

### Community 4 - "main.py"
Cohesion: 0.12
Nodes (34): admin_only(), api_update_profile(), command_scan_inbox(), handle_auto_apply(), handle_match_command(), load_last_job(), load_profile(), pause_bot() (+26 more)

### Community 5 - "load_chat_id"
Cohesion: 0.10
Nodes (32): get_email_cache(), get_note_cache(), get_prep_cache(), _get_probe_session(), is_job_link_alive(), bot_optimizer.py — Efficiency Module for the Autonomous Job Bot Features: 1.…, Ultra-fast, non-blocking probe to verify if a job URL is live and accepting…, Ultra-fast, non-blocking probe to verify if a job URL is live and accepting… (+24 more)

### Community 6 - "instahyre_engine.py"
Cohesion: 0.13
Nodes (27): applyFilters(), attachEvents(), closeJobModal(), createCardHtml(), daysAgo(), els, escapeHtml(), fmtDate() (+19 more)

### Community 7 - "scrape_single_channel"
Cohesion: 0.06
Nodes (30): fetch_live_adzuna_search(), format_deadlines_radar_report(), format_national_drives_report(), format_single_drive_detail(), get_all_drive_deadlines(), get_national_drives(), get_tn_scraped_live_jobs(), get_urgent_deadlines_summary() (+22 more)

### Community 8 - "bot_features.py"
Cohesion: 0.14
Nodes (27): enrichJobRecord(), fetchJson(), tn_live_jobs_src_scraper_log, { fetchJson, makeJob, markDomainDead }, isTamilNaduLocation(), scrape(), scrapeSmartRecruitersCompany(), SMART_RECRUITERS_COMPANIES (+19 more)

### Community 9 - "cloud_runner.py"
Cohesion: 0.14
Nodes (29): _api_request(), classify_location(), clean_html(), _get_radar_session(), _fetch_channel_tn(), is_social_or_promo_link(), _keyword_match(), _make_job() (+21 more)

### Community 10 - "enterprise_adapters.py"
Cohesion: 0.08
Nodes (26): sync_to_notion(), dispatch_walkin_alerts(), format_single_walkin_detail(), format_walkins_report(), get_walkin_drives(), Retrieves verified Tamil Nadu walk-in drives from walkin_drives.json with mtime…, Formats verified Tamil Nadu walk-in drives into high-aesthetic HTML chunks for…, Retrieves verified Tamil Nadu walk-in drives from walkin_drives.json with mtime… (+18 more)

### Community 11 - "safe_load_json"
Cohesion: 0.09
Nodes (24): calculate_skill_match_score(), extract_eligible_batch(), extract_experience_level(), extract_hr_email(), extract_job_salary(), format_eligibility_badge(), match_job_compatibility(), Analyzes job description text or fetches live URL content, then computes: 1.… (+16 more)

### Community 12 - "api_instahyre"
Cohesion: 0.11
Nodes (24): dispatch_tamil_nadu_alerts(), _filter_and_paginate_tn_jobs(), get_tamil_nadu_jobs(), _tn_sort_key(), load_seen_jobs(), mark_seen(), normalize_job_url(), Uses python-jobspy for Chennai, Coimbatore, Tamil Nadu & Bangalore India jobs. (+16 more)

### Community 13 - "job_monitor_loop"
Cohesion: 0.08
Nodes (23): ref_http, { buildReport, writeReport }, config, DATA_DIR, DIFF_FILE, fs, HELP, http (+15 more)

### Community 14 - "ResumePDF"
Cohesion: 0.13
Nodes (21): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+13 more)

### Community 15 - "Reporting a Vulnerability"
Cohesion: 0.09
Nodes (21): playwright, dependencies, cheerio, playwright, description, engines, node, license (+13 more)

### Community 16 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.11
Nodes (17): CATEGORIES, CITIES, CITY_ALIASES, tn_live_jobs_src_config_enable_tier3, SEARCH_KEYWORDS, ALL_SOURCES, apna, companyCareers (+9 more)

### Community 17 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
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

### Community 18 - "Q: Why does run_playwright_apply connect across 4 separate communities?"
Cohesion: 0.12
Nodes (17): format_search_results_report(), generate_cold_email_pitch(), generate_fast_interview_cheat_sheet(), Generates a high-yield, 3-question technical interview preparation cheat sheet…, Generates a high-yield, 3-question technical interview preparation cheat sheet…, Generates a high-converting, personalized 3-paragraph cold email pitch tailored…, Formats search results into Telegram HTML cards and builds interactive filter…, Formats search results into Telegram HTML cards and builds interactive filter… (+9 more)

### Community 19 - "bypass_blog_redirect"
Cohesion: 0.15
Nodes (17): createNoteCollector(), dropStaleTnpscNotices(), ensureWorkDir(), main(), parseArgs(), readNumber(), resolveCities(), resolveKeywords() (+9 more)

### Community 20 - "is_social_or_promo_link"
Cohesion: 0.29
Nodes (16): fetchText(), markDomainDead(), cheerio, clipTitle(), collectGovLinks(), DISTRICT_SITES, { fetchText, makeJob, markDomainDead }, govJobFromLink() (+8 more)

### Community 21 - "LoggerWriter"
Cohesion: 0.17
Nodes (13): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), email, email_header (+5 more)

### Community 22 - "enforce_bot_security_profile"
Cohesion: 0.19
Nodes (15): ref_path, readWorkFile(), runAll(), runDiff(), runExport(), appendHistory(), computeDiff(), fs (+7 more)

### Community 23 - "FPDF"
Cohesion: 0.14
Nodes (14): add_watchdog_subscription(), get_watchdog_subscriptions(), Retrieves all active keyword subscriptions with mtime memory caching., Adds a custom keyword subscription for the user. Returns updated list., Removes a keyword subscription for the user. Returns updated list., Retrieves all active keyword subscriptions with mtime memory caching., Adds a custom keyword subscription for the user. Returns updated list., Removes a keyword subscription for the user. Returns updated list. (+6 more)

### Community 24 - "README.md"
Cohesion: 0.16
Nodes (14): api_status(), daily_report_loop(), is_sleep_time(), load_channel_status(), load_retry_queue(), load_weekly_stats(), Live stats for dashboard widgets., Live stats for dashboard widgets. (+6 more)

### Community 25 - "TN Job Pipeline (ref_fs / countJobsBySource() / runReport())"
Cohesion: 0.22
Nodes (13): cheerio, COMPANY_NAMES, {
  fetchText,
  fetchJson,
  makeJob,
  renderCapture,
  findJobObjects,
  markDomainDead,
}, jobPostingsFromLdJson(), locationFromLdJson(), salaryFromLdJson(), scrape(), scrapeFreshersworld() (+5 more)

### Community 26 - "Module 26: export.js"
Cohesion: 0.17
Nodes (12): api_force_scan(), _run(), api_instahyre(), _run(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers a fresh Job Radar scan in a background thread. (+4 more)

### Community 27 - "Module 27: api_force_scan()"
Cohesion: 0.21
Nodes (11): ref_fs, countJobsBySource(), runReport(), buildReport(), { clip }, { ensureDir }, escapeCell(), fs (+3 more)

### Community 28 - "Module 28: generate_resume.py"
Cohesion: 0.29
Nodes (11): CSV_COLUMNS, csvCell(), ensureDir(), fs, { log }, path, sortJobs(), toCsv() (+3 more)

### Community 29 - "Module 29: SECURITY.md"
Cohesion: 0.18
Nodes (8): execute_greenhouse_adapter(), execute_lever_adapter(), execute_smartrecruiters_adapter(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).…, Finds the valid resume path across OS platforms, case variations, profile…, Automated application adapter for SmartRecruiters (jobs.smartrecruiters.com /…, resolve_resume_path()

### Community 30 - "TN Job Pipeline (_tn_sort_key() / Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized… / Safely converts any date representation (YYYY-MM-DD, ISO string, RFC 2822, unix…)"
Cohesion: 0.20
Nodes (9): ai_fix_selector(), human_type(), Types text with human realism: burst speed, micro-pauses, occasional…, Types text with human realism: burst speed, micro-pauses, occasional…, Navigates to the job_url, takes a screenshot, extracts form HTML, sends to…, Navigates to the job_url, takes a screenshot, extracts form HTML, sends to…, When a selector fails, asks Gemini/Groq to suggest an alternative selector by…, When a selector fails, asks Gemini/Groq to suggest an alternative selector by… (+1 more)

### Community 31 - "Module 31: GITHUB_ACTIONS_GUIDE.md"
Cohesion: 0.22
Nodes (10): api_manual_apply(), run(), bypass_blog_redirect(), clean_tracking_params(), manual_apply(), run(), Strips Google Analytics/Social Media tracking parameters to keep URLs clean and…, Strips Google Analytics/Social Media tracking parameters to keep URLs clean and… (+2 more)

### Community 32 - "TN Job Pipeline (HUGGING_FACE_DEPLOY_GUIDE.md / 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot) / 🚀 Step 1: Push Code to Hugging Face Space)"
Cohesion: 0.22
Nodes (9): apply_rag_memory_fallback(), get_seeded_qa_memory(), Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions…, Evaluates form fields via comprehensive DOM inspection. Matches questions… (+1 more)

### Community 33 - "Module 33: FPDF"
Cohesion: 0.25
Nodes (8): execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Saves generated credentials to a secure local vault., Generates a highly secure password that passes all enterprise checks., Advanced Workday adapter. Handles Apply, account creation, OTP email…, Logs into Gmail via IMAP and fetches the latest 6-digit OTP or magic link.…, save_to_vault()

### Community 34 - "Module 34: query_20260928_193829_a1d41896_why_does_run_playwright_apply_connect_across_4_sep.md"
Cohesion: 0.36
Nodes (8): clear_qa(), handle_qa_button(), load_pending_qa(), load_qa_memory(), save_answer(), _save_inline_answer(), save_qa_memory(), show_qa_memory()

### Community 35 - "Telegram Bot Engine (wrapper() / get_authorized_chat_ids() / is_authorized())"
Cohesion: 0.29
Nodes (6): FPDF, generate_dynamic_resume(), FPDF, Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF., Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF., ResumePDF

### Community 36 - "Module 36: LoggerWriter"
Cohesion: 0.29
Nodes (7): wrapper(), get_authorized_chat_ids(), is_authorized(), Returns all authorized admin Telegram IDs (from env, saved file, and memory)…, Returns all authorized admin Telegram IDs (from env, saved file, and memory)…, Verifies whether the given Telegram User ID or Chat ID is an authorized admin., Verifies whether the given Telegram User ID or Chat ID is an authorized admin.

### Community 37 - "Module 37: FPDF"
Cohesion: 0.33
Nodes (6): format_oa_report(), get_company_oa_info(), Formats the company Online Assessment (OA) syllabus and pattern card for…, Formats the company Online Assessment (OA) syllabus and pattern card for…, handle_oa_callback(), handle_oa_command()

### Community 38 - "Module 38: README.md"
Cohesion: 0.33
Nodes (6): _bezier_mouse_move(), human_mimicry(), FEATURE 2 — Ghost Cursor: Move mouse along a cubic Bezier curve with random…, FEATURE 2 — Ghost Cursor: Move mouse along a cubic Bezier curve with random…, Multi-layer human simulation: Bezier mouse paths, reading scroll, micro-pauses,…, Multi-layer human simulation: Bezier mouse paths, reading scroll, micro-pauses,…

### Community 39 - "TN Job Pipeline (jobs.js)"
Cohesion: 0.33
Nodes (6): fetch_target_page_job_meta(), is_social_or_promo_link(), Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…, Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…

### Community 40 - "Community 40"
Cohesion: 0.40
Nodes (4): generate_market_analytics_report(), Aggregates application logs, radar cache, and QA memory into a high-visibility,…, Aggregates application logs, radar cache, and QA memory into a high-visibility,…, send_career_analytics()

### Community 41 - "Community 41"
Cohesion: 0.50
Nodes (3): minify_form_html(), Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.…, Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.…

### Community 42 - "Community 42"
Cohesion: 0.50
Nodes (3): check_job_match(), Strictly filters for FRESHER / ENTRY-LEVEL ENGINEERING jobs only. Returns…, Strictly filters for FRESHER / ENTRY-LEVEL ENGINEERING jobs only. Returns…

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): apply_regex_fallback(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…

### Community 45 - "Community 45"
Cohesion: 0.67
Nodes (3): Uses Gemini Vision to analyze the current page state. Returns: 'success',…, Uses Gemini Vision to analyze the current page state. Returns: 'success',…, verify_page_with_ai()

## Knowledge Gaps
- **113 isolated node(s):** `name`, `version`, `private`, `description`, `license` (+108 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 360 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `api_instahyre` to `job_radar.py`, `load_chat_id`, `cloud_runner.py`, `enterprise_adapters.py`, `safe_load_json`, `Module 26: export.js`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `get_tamil_nadu_jobs()` connect `api_instahyre` to `job_radar.py`, `run_playwright_apply`, `main.py`, `load_chat_id`, `scrape_single_channel`, `cloud_runner.py`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `ResumePDF` to `job_radar.py`, `Module 26: export.js`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _113 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.056107539450613676 - nodes in this community are weakly interconnected._
- **Should `bot_optimizer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07207207207207207 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.07777777777777778 - nodes in this community are weakly interconnected._
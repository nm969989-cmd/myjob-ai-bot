# Graph Report - Telegram_Job_Bot  (2026-10-01)

## Corpus Check
- 64 files · ~173,303 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 5 file(s) not represented in the graph (top: (none) 2, .example 1, .csv 1)

## Summary
- 815 nodes · 2157 edges · 42 communities (40 shown, 2 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 119 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Walkin GPS & Venue Navigation
- SimplifyJobs Fresher Ingestion
- JobSpy Multi-Board Live Search
- Enterprise Application Engine
- Headless DOM Scraper Engine
- Web Dashboard & Real-Time Filters
- Tamil Nadu Portal Web Scrapers
- Walkin GPS & Venue Navigation
- ATS Resume & Skill Gap Matcher
- Scraper Network Runtime Config
- Instahyre Playwright Automation
- Instahyre Playwright Automation
- Job Batch Data Pipeline
- Headless DOM Scraper Engine
- JobSpy Multi-Board Live Search
- Main Get Channel Session Cluster
- Job Batch Data Pipeline
- Tamil Nadu Portal Web Scrapers
- Job Batch Data Pipeline
- Walkin GPS & Venue Navigation
- Instahyre Playwright Automation
- Main Api Status Cluster
- JobSpy Multi-Board Live Search
- Bot Optimizer Apply Rag  Cluster
- Cloud Runner & Scheduled Execution
- Job Batch Data Pipeline
- Tn Live Jobs Src Export Cluster
- Tn Live Jobs Src Scraper Cluster
- Enterprise Application Engine
- Bot Optimizer Extract El Cluster
- National Drives & Cutoffs
- Main Api Manual Apply Cluster
- Bot Features Cluster
- Bot Features Check For I Cluster
- Generate Resume Cluster
- Instahyre Playwright Automation
- Bot Optimizer Format Nat Cluster
- Tamil Nadu Portal Web Scrapers
- Main Api Miniapp Jobs Cluster
- Main Generate Dynamic Re Cluster
- Main Loggerwriter Cluster

## God Nodes (most connected - your core abstractions)
1. `save_chat_id()` - 57 edges
2. `admin_only()` - 45 edges
3. `tidy()` - 42 edges
4. `run_playwright_apply()` - 35 edges
5. `makeJob()` - 34 edges
6. `run_all_tests()` - 31 edges
7. `run_radar()` - 27 edges
8. `scrape_single_channel()` - 27 edges
9. `registrableDomain()` - 27 edges
10. `fetchText()` - 25 edges

## Surprising Connections (you probably didn't know these)
- `_bg_scan()` --calls--> `scan_for_interview_invites()`  [EXTRACTED]
  main.py → imap_handler.py
- `run_playwright_apply()` --calls--> `wait_for_otp()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `sync_to_notion()`  [EXTRACTED]
  main.py → bot_features.py
- `scrape_single_channel()` --calls--> `sync_to_notion()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `record_learned_qa()`  [EXTRACTED]
  main.py → bot_optimizer.py

## Import Cycles
- None detected.

## Communities (42 total, 2 thin omitted)

### Community 0 - "Walkin GPS & Venue Navigation"
Cohesion: 0.06
Nodes (78): find_nearby_walkin_drives(), format_nearby_walkins_report(), format_simplify_jobs_report(), generate_cold_email_pitch(), geocode_location_text(), get_walkin_checklist_text(), get_watchdog_subscriptions(), haversine_distance_km() (+70 more)

### Community 1 - "SimplifyJobs Fresher Ingestion"
Cohesion: 0.06
Nodes (72): extract_hr_email(), extract_job_salary(), fetch_simplify_jobs(), Fetches real-time tech fresher and new grad job listings from the official…, Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, store_email_cache(), store_note_cache() (+64 more)

### Community 2 - "JobSpy Multi-Board Live Search"
Cohesion: 0.11
Nodes (50): cheerio, makeJob(), renderCapture(), scrape(), cheerio, cleanFreshersworldTitle(), COMPANY_NAMES, {
  fetchText,
  fetchJson,
  makeJob,
  renderCapture,
  findJobObjects,
  markDomainDead,
} (+42 more)

### Community 3 - "Enterprise Application Engine"
Cohesion: 0.08
Nodes (38): base64, bs4, csv, enterprise_adapters, flask, google, groq, io (+30 more)

### Community 4 - "Headless DOM Scraper Engine"
Cohesion: 0.07
Nodes (34): tn_live_jobs_src_config_http_timeout_ms, tn_live_jobs_src_config_max_attempts, tn_live_jobs_src_config_max_delay_ms, tn_live_jobs_src_config_min_delay_ms, tn_live_jobs_src_config_render_timeout_ms, buildHeaders(), captureJsonFromPage(), { chromium } (+26 more)

### Community 5 - "Web Dashboard & Real-Time Filters"
Cohesion: 0.13
Nodes (27): applyFilters(), attachEvents(), closeJobModal(), createCardHtml(), daysAgo(), els, escapeHtml(), fmtDate() (+19 more)

### Community 6 - "Tamil Nadu Portal Web Scrapers"
Cohesion: 0.13
Nodes (27): ref_crypto, enrichJobRecord(), tn_live_jobs_src_config_default_category, tn_live_jobs_src_scraper_log, { CITY_ALIASES, CATEGORIES, DEFAULT_CATEGORY }, cleanSummary(), cleanUrl(), crypto (+19 more)

### Community 7 - "Walkin GPS & Venue Navigation"
Cohesion: 0.13
Nodes (23): check_job_against_watchdogs(), dispatch_walkin_alerts(), format_oa_report(), format_single_walkin_detail(), format_walkins_report(), generate_linkedin_outreach_note(), generate_market_analytics_report(), get_company_oa_info() (+15 more)

### Community 8 - "ATS Resume & Skill Gap Matcher"
Cohesion: 0.12
Nodes (16): analyze_jd_skill_gap(), calculate_skill_match_score(), check_ats_liveness_api(), format_skill_gap_report(), get_gap_cache(), _get_probe_session(), is_job_link_alive(), Ultra-fast, non-blocking probe to verify if a job URL is live and accepting… (+8 more)

### Community 9 - "Scraper Network Runtime Config"
Cohesion: 0.08
Nodes (23): ref_http, { buildReport, writeReport }, config, DATA_DIR, DIFF_FILE, fs, HELP, http (+15 more)

### Community 10 - "Instahyre Playwright Automation"
Cohesion: 0.09
Nodes (21): generate_dynamic_cover_letter(), generate_interview_prep(), send_cold_email_if_found(), apply_regex_fallback(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.…, get_latest_otp() (+13 more)

### Community 11 - "Instahyre Playwright Automation"
Cohesion: 0.12
Nodes (22): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+14 more)

### Community 12 - "Job Batch Data Pipeline"
Cohesion: 0.10
Nodes (22): sync_to_notion(), Exception, scan_for_interview_invites(), analyze_form_with_gemini(), api_debug_bot(), api_rotate_key(), api_scan_inbox(), api_telegram_test() (+14 more)

### Community 13 - "Headless DOM Scraper Engine"
Cohesion: 0.09
Nodes (21): playwright, dependencies, cheerio, playwright, description, engines, node, license (+13 more)

### Community 14 - "JobSpy Multi-Board Live Search"
Cohesion: 0.11
Nodes (17): CATEGORIES, CITIES, CITY_ALIASES, tn_live_jobs_src_config_enable_tier3, SEARCH_KEYWORDS, ALL_SOURCES, apna, companyCareers (+9 more)

### Community 15 - "Main Get Channel Session Cluster"
Cohesion: 0.18
Nodes (17): get_channel_session(), handle_button(), load_applied_jobs(), manual_radar_scan(), Scrapes one Telegram public channel and triggers applications for new jobs.…, Loops through all TARGET_CHANNELS and scrapes each one for new engineering…, Dedicated Radar Scan: 1. Scrapes the configured Telegram channel. 2. Fetches…, Saves details of the most recent application attempt. (+9 more)

### Community 16 - "Job Batch Data Pipeline"
Cohesion: 0.15
Nodes (17): createNoteCollector(), dropStaleTnpscNotices(), ensureWorkDir(), main(), parseArgs(), readNumber(), resolveCities(), resolveKeywords() (+9 more)

### Community 17 - "Tamil Nadu Portal Web Scrapers"
Cohesion: 0.29
Nodes (16): fetchText(), markDomainDead(), cheerio, clipTitle(), collectGovLinks(), DISTRICT_SITES, { fetchText, makeJob, markDomainDead }, govJobFromLink() (+8 more)

### Community 18 - "Job Batch Data Pipeline"
Cohesion: 0.19
Nodes (15): ref_path, readWorkFile(), runAll(), runDiff(), runExport(), appendHistory(), computeDiff(), fs (+7 more)

### Community 19 - "Walkin GPS & Venue Navigation"
Cohesion: 0.14
Nodes (14): add_watchdog_subscription(), estimate_commute_time(), generate_fast_interview_cheat_sheet(), get_email_cache(), get_note_cache(), get_prep_cache(), bot_optimizer.py — Efficiency Module for the Autonomous Job Bot Features: 1.…, Generates a high-yield, 3-question technical interview preparation cheat sheet… (+6 more)

### Community 20 - "Instahyre Playwright Automation"
Cohesion: 0.19
Nodes (13): email, execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Saves generated credentials to a secure local vault., Generates a highly secure password that passes all enterprise checks., Advanced Workday adapter. Handles Apply, account creation, OTP email…, Logs into Gmail via IMAP and fetches the latest 6-digit OTP or magic link.… (+5 more)

### Community 21 - "Main Api Status Cluster"
Cohesion: 0.15
Nodes (15): api_status(), daily_report_loop(), get_authorized_chat_ids(), home(), is_sleep_time(), load_channel_status(), load_last_job(), load_retry_queue() (+7 more)

### Community 22 - "JobSpy Multi-Board Live Search"
Cohesion: 0.16
Nodes (12): fetch_jobspy_live_search(), fetch_live_adzuna_search(), format_search_results_report(), get_tn_scraped_live_jobs(), Loads verified and live scraped job records from the tn-live-jobs engine…, Fetches 100% real, freshly posted job opportunities directly from Adzuna India…, Queries python-jobspy across LinkedIn, Indeed India, and Google Jobs for…, Performs comprehensive search across all real-data pipelines: 1. Verified Walk-… (+4 more)

### Community 23 - "Bot Optimizer Apply Rag  Cluster"
Cohesion: 0.20
Nodes (12): apply_rag_memory_fallback(), get_seeded_qa_memory(), Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions…, record_learned_qa(), handle_qa_button(), load_pending_qa() (+4 more)

### Community 24 - "Cloud Runner & Scheduled Execution"
Cohesion: 0.20
Nodes (9): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, run_cloud(), datetime, dotenv, escape_md(), json, os, random (+1 more)

### Community 25 - "Job Batch Data Pipeline"
Cohesion: 0.21
Nodes (11): ref_fs, countJobsBySource(), runReport(), buildReport(), { clip }, { ensureDir }, escapeCell(), fs (+3 more)

### Community 26 - "Tn Live Jobs Src Export Cluster"
Cohesion: 0.29
Nodes (11): CSV_COLUMNS, csvCell(), ensureDir(), fs, { log }, path, sortJobs(), toCsv() (+3 more)

### Community 27 - "Tn Live Jobs Src Scraper Cluster"
Cohesion: 0.32
Nodes (11): fetchJson(), { fetchJson, makeJob, markDomainDead }, isTamilNaduLocation(), scrape(), scrapeSmartRecruitersCompany(), scrapeWorkdayCompany(), SMART_RECRUITERS_COMPANIES, {
  tidy,
  detectCity,
  detectCategory,
  detectSkills,
  detectEducation,
  detectExperience,
  isFresher,
  cleanSummary,
  relativeDateToIso,
} (+3 more)

### Community 28 - "Enterprise Application Engine"
Cohesion: 0.18
Nodes (8): execute_greenhouse_adapter(), execute_lever_adapter(), execute_smartrecruiters_adapter(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).…, Finds the valid resume path across OS platforms, case variations, profile…, Automated application adapter for SmartRecruiters (jobs.smartrecruiters.com /…, resolve_resume_path()

### Community 29 - "Bot Optimizer Extract El Cluster"
Cohesion: 0.22
Nodes (10): extract_eligible_batch(), extract_experience_level(), format_eligibility_badge(), match_job_compatibility(), Analyzes job description text or fetches live URL content, then computes: 1.…, Extracts graduation batch year(s) from unstructured job text, titles, or…, Extracts candidate experience requirement from unstructured job text. Handles…, Combines batch and experience into a clean, modern Telegram card line. (+2 more)

### Community 30 - "National Drives & Cutoffs"
Cohesion: 0.22
Nodes (8): format_deadlines_radar_report(), get_all_drive_deadlines(), get_urgent_deadlines_summary(), parse_drive_deadline(), Parses a mass drive's deadline and computes days and hours remaining.…, Parses and returns all mass drive deadlines sorted by urgency: Critical (<=4…, Generates Telegram-ready HTML cards for National Mass Drive deadlines with…, Returns a concise 1-screen summary of drives closing within 10 days for quick…

### Community 31 - "Main Api Manual Apply Cluster"
Cohesion: 0.25
Nodes (9): api_manual_apply(), run(), bypass_blog_redirect(), clean_tracking_params(), log_job(), run(), Logs every job action, updates daily stats, and triggers Google Sheets Webhook., Strips Google Analytics/Social Media tracking parameters to keep URLs clean and… (+1 more)

### Community 32 - "Bot Features Cluster"
Cohesion: 0.32
Nodes (6): CoverLetterPDF, FPDF, _sanitize_latin1(), email_header, email_message, smtplib

### Community 33 - "Bot Features Check For I Cluster"
Cohesion: 0.25
Nodes (8): check_for_interviews(), cleanup_system_resources(), job_monitor_loop(), Kills orphaned browser processes and cleans cache to prevent resource leaks., Monitors and automatically restarts background threads if they crash., run_telegram_polling(), save_stats(), thread_supervisor()

### Community 34 - "Generate Resume Cluster"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 35 - "Instahyre Playwright Automation"
Cohesion: 0.25
Nodes (8): api_force_scan(), _run(), api_instahyre(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan., Triggers the Instahyre mass-applier engine from the dashboard.

### Community 36 - "Bot Optimizer Format Nat Cluster"
Cohesion: 0.33
Nodes (6): format_national_drives_report(), format_single_drive_detail(), get_national_drives(), Loads national mass drives from disk or initializes with verified seeds with…, Formats verified national mass drives into Telegram-ready HTML chunks. Supports…, Returns an ultra-detailed breakdown card for a specific national mega drive,…

### Community 37 - "Tamil Nadu Portal Web Scrapers"
Cohesion: 0.40
Nodes (5): APNA_CATEGORIES, { fetchText, makeJob }, parseApnaPayload(), {
  tidy,
  clip,
  slugifyValue,
  registrableDomain,
  detectCity,
  detectEmploymentType,
  detectExperience,
  unescapeJsonInScript,
}, unescapeJsonInScript()

### Community 38 - "Main Api Miniapp Jobs Cluster"
Cohesion: 0.40
Nodes (5): api_miniapp_jobs(), fetch_target_page_job_meta(), is_social_or_promo_link(), Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…

### Community 39 - "Main Generate Dynamic Re Cluster"
Cohesion: 0.40
Nodes (4): generate_dynamic_resume(), FPDF, Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF., ResumePDF

## Knowledge Gaps
- **114 isolated node(s):** `name`, `version`, `private`, `description`, `license` (+109 more)
  These have ≤1 connection - possible missing edges. (Counts symbols only; 311 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `SimplifyJobs Fresher Ingestion` to `Enterprise Application Engine`, `Instahyre Playwright Automation`, `ATS Resume & Skill Gap Matcher`, `Job Batch Data Pipeline`, `Cloud Runner & Scheduled Execution`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `SimplifyJobs Fresher Ingestion` to `Enterprise Application Engine`, `Job Batch Data Pipeline`, `Bot Optimizer Extract El Cluster`, `Main Api Miniapp Jobs Cluster`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `Instahyre Playwright Automation` to `Enterprise Application Engine`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **What connects `name`, `version`, `private` to the rest of the system?**
  _114 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Walkin GPS & Venue Navigation` be split into smaller, more focused modules?**
  _Cohesion score 0.05744888023369036 - nodes in this community are weakly interconnected._
- **Should `SimplifyJobs Fresher Ingestion` be split into smaller, more focused modules?**
  _Cohesion score 0.06479081821547575 - nodes in this community are weakly interconnected._
- **Should `JobSpy Multi-Board Live Search` be split into smaller, more focused modules?**
  _Cohesion score 0.11245791245791245 - nodes in this community are weakly interconnected._
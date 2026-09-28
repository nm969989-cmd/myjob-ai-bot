# Graph Report - Telegram_Job_Bot  (2026-09-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 423 nodes · 1026 edges · 25 communities (21 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bac27ece`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- bot_features.py
- save_chat_id
- run_playwright_apply
- bot_optimizer.py
- scrape_single_channel
- classify_location
- route
- main.py
- run_radar
- _make_job
- job_radar.py
- scrape_telegram_channel
- load_chat_id
- api_instahyre
- ResumePDF
- Reporting a Vulnerability
- job_monitor_loop
- 🚀 GitHub Actions 24/7 Cloud Automation Guide
- 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)
- Q: Why does run_playwright_apply connect across 4 separate communities?
- is_social_or_promo_link
- LoggerWriter
- calculate_skill_match_score
- FPDF

## God Nodes (most connected - your core abstractions)
1. `save_chat_id()` - 35 edges
2. `run_playwright_apply()` - 34 edges
3. `admin_only()` - 33 edges
4. `run_radar()` - 24 edges
5. `scrape_single_channel()` - 23 edges
6. `run_all_tests()` - 22 edges
7. `_make_job()` - 17 edges
8. `classify_location()` - 15 edges
9. `handle_button()` - 14 edges
10. `load_chat_id()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `run_instahyre_mass_apply()`  [EXTRACTED]
  main.py → instahyre_engine.py
- `Detects if a URL is a social media link, channel promo, parked domain, or non-…` --rationale_for--> `is_social_or_promo_link()`  [EXTRACTED]
  main.py → job_radar.py
- `run_playwright_apply()` --calls--> `generate_dynamic_cover_letter()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `execute_workday_adapter()`  [EXTRACTED]
  main.py → enterprise_adapters.py
- `run_playwright_apply()` --calls--> `sync_to_notion()`  [EXTRACTED]
  main.py → bot_features.py

## Import Cycles
- None detected.

## Communities (25 total, 4 thin omitted)

### Community 0 - "bot_features.py"
Cohesion: 0.06
Nodes (50): CoverLetterPDF, generate_dynamic_cover_letter(), FPDF, Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, _sanitize_latin1(), sync_to_notion(), wait_for_otp(), email (+42 more)

### Community 1 - "save_chat_id"
Cohesion: 0.08
Nodes (55): generate_fast_interview_cheat_sheet(), generate_market_analytics_report(), Generates a high-yield, 3-question technical interview preparation cheat sheet…, Aggregates application logs, radar cache, and QA memory into a high-visibility,…, callback_query_handler, admin_only(), wrapper(), clear_qa() (+47 more)

### Community 2 - "run_playwright_apply"
Cohesion: 0.05
Nodes (40): generate_interview_prep(), send_cold_email_if_found(), apply_rag_memory_fallback(), apply_regex_fallback(), get_seeded_qa_memory(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Loads qa_memory from disk, auto-seeding with standard defaults if missing or… (+32 more)

### Community 3 - "bot_optimizer.py"
Cohesion: 0.12
Nodes (32): dispatch_walkin_alerts(), extract_eligible_batch(), format_deadlines_radar_report(), format_national_drives_report(), format_single_drive_detail(), format_single_walkin_detail(), format_walkins_report(), get_all_drive_deadlines() (+24 more)

### Community 4 - "scrape_single_channel"
Cohesion: 0.09
Nodes (27): generate_linkedin_outreach_note(), Generates a personalized, professional LinkedIn connection note (<= 300…, api_manual_apply(), run(), bypass_blog_redirect(), check_job_match(), clean_tracking_params(), get_channel_session() (+19 more)

### Community 5 - "classify_location"
Cohesion: 0.14
Nodes (24): _api_request(), classify_location(), clean_html(), _get_radar_session(), _keyword_match(), Queries RemoteOK API — strictly filtering for India & unrestricted Worldwide…, Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized…, Robust HTTP request helper with persistent connection pooling. (+16 more)

### Community 6 - "route"
Cohesion: 0.09
Nodes (23): api_add_channel(), api_download_log(), api_download_profile(), api_download_qa(), api_health_check(), api_mark_crm(), api_pause(), api_radar() (+15 more)

### Community 7 - "main.py"
Cohesion: 0.10
Nodes (20): base64, bs4, csv, flask, google, groq, io, enforce_bot_security_profile() (+12 more)

### Community 8 - "run_radar"
Cohesion: 0.15
Nodes (16): dispatch_tamil_nadu_alerts(), format_tamil_nadu_telegram_digest(), get_tamil_nadu_jobs(), load_seen_jobs(), mark_seen(), normalize_job_url(), Uses python-jobspy for Chennai, Coimbatore, Tamil Nadu & Bangalore India jobs., Retrieves recently posted engineering and tech jobs in Tamil Nadu (Chennai,… (+8 more)

### Community 9 - "_make_job"
Cohesion: 0.18
Nodes (17): extract_experience_level(), extract_hr_email(), extract_job_salary(), format_eligibility_badge(), Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, Extracts candidate experience requirement from unstructured job text. Handles…, Combines batch and experience into a clean, modern Telegram card line. (+9 more)

### Community 10 - "job_radar.py"
Cohesion: 0.26
Nodes (11): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, datetime, dotenv, functools, html, escape_md(), 📡 JOB RADAR — Multi-Platform Job Finder (India & Tamil Nadu Priority Engine)…, random (+3 more)

### Community 11 - "scrape_telegram_channel"
Cohesion: 0.20
Nodes (11): api_status(), daily_report_loop(), is_sleep_time(), load_retry_queue(), load_weekly_stats(), Loops through all TARGET_CHANNELS and scrapes each one for new engineering…, Live stats for dashboard widgets., Returns True between 11 PM and 6 AM IST — bot rests to avoid bot-detection. (+3 more)

### Community 12 - "load_chat_id"
Cohesion: 0.22
Nodes (10): analyze_form_with_gemini(), api_debug_bot(), api_rotate_key(), api_telegram_test(), get_groq_client(), load_chat_id(), Sends a test message to Telegram to verify bot connectivity., Uses Gemini API to map form fields to the user's profile data, leveraging both… (+2 more)

### Community 13 - "api_instahyre"
Cohesion: 0.22
Nodes (9): api_force_scan(), _run(), api_instahyre(), _run(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan. (+1 more)

### Community 14 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 15 - "Reporting a Vulnerability"
Cohesion: 0.25
Nodes (7): 1. Private Disclosure, 2. What to Include, 3. Response Process, Best Practices for Deployments, Reporting a Vulnerability, Security Policy, Supported Versions

### Community 16 - "job_monitor_loop"
Cohesion: 0.29
Nodes (7): check_for_interviews(), cleanup_system_resources(), job_monitor_loop(), Kills orphaned browser processes and cleans cache to prevent resource leaks., Monitors and automatically restarts background threads if they crash., run_telegram_polling(), thread_supervisor()

### Community 17 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.33
Nodes (5): 🚀 GitHub Actions 24/7 Cloud Automation Guide, 📌 Repository Information, 🔑 Step 1: Set Up Encrypted Secrets on GitHub, 🚀 Step 2: Push the Enhanced Code to GitHub, ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

### Community 18 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
Cohesion: 0.33
Nodes (5): 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot), 🚀 Step 1: Push Code to Hugging Face Space, 🔑 Step 2: Configure Space Secrets, ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot), 📱 Step 4: Verify in Telegram

### Community 19 - "Q: Why does run_playwright_apply connect across 4 separate communities?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Why does run_playwright_apply connect across 4 separate communities?, Source Nodes

### Community 20 - "is_social_or_promo_link"
Cohesion: 0.40
Nodes (5): api_miniapp_jobs(), fetch_target_page_job_meta(), is_social_or_promo_link(), Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…

## Knowledge Gaps
- **16 isolated node(s):** `1. Private Disclosure`, `2. What to Include`, `3. Response Process`, `Best Practices for Deployments`, `Supported Versions` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 161 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `run_radar` to `bot_features.py`, `bot_optimizer.py`, `classify_location`, `main.py`, `_make_job`, `job_radar.py`, `api_instahyre`, `calculate_skill_match_score`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `bot_features.py` to `api_instahyre`, `main.py`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `classify_location` to `scrape_single_channel`, `main.py`, `run_radar`, `_make_job`, `job_radar.py`, `is_social_or_promo_link`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `1. Private Disclosure`, `2. What to Include`, `3. Response Process` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `bot_features.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05639097744360902 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.07957393483709273 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.047474747474747475 - nodes in this community are weakly interconnected._
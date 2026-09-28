# Graph Report - Telegram_Job_Bot  (2026-09-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 433 nodes · 1068 edges · 23 communities (19 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `1079ee88`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- job_radar.py
- bot_optimizer.py
- save_chat_id
- bot_features.py
- main.py
- run_playwright_apply
- instahyre_engine.py
- scrape_single_channel
- load_stats
- load_chat_id
- safe_load_json
- api_instahyre
- ResumePDF
- Reporting a Vulnerability
- 🚀 GitHub Actions 24/7 Cloud Automation Guide
- 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)
- Q: Why does run_playwright_apply connect across 4 separate communities?
- is_social_or_promo_link
- thread_supervisor
- LoggerWriter
- enforce_bot_security_profile
- FPDF

## God Nodes (most connected - your core abstractions)
1. `save_chat_id()` - 38 edges
2. `admin_only()` - 35 edges
3. `run_playwright_apply()` - 34 edges
4. `run_all_tests()` - 25 edges
5. `run_radar()` - 24 edges
6. `scrape_single_channel()` - 23 edges
7. `_make_job()` - 17 edges
8. `get_tamil_nadu_jobs()` - 16 edges
9. `classify_location()` - 15 edges
10. `extract_structured_channel_job_details()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `run_instahyre_mass_apply()`  [EXTRACTED]
  main.py → instahyre_engine.py
- `_make_job()` --calls--> `extract_eligible_batch()`  [EXTRACTED]
  job_radar.py → bot_optimizer.py
- `_make_job()` --calls--> `extract_experience_level()`  [EXTRACTED]
  job_radar.py → bot_optimizer.py
- `api_miniapp_jobs()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `check_job_match()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py

## Import Cycles
- None detected.

## Communities (23 total, 4 thin omitted)

### Community 0 - "job_radar.py"
Cohesion: 0.07
Nodes (64): extract_hr_email(), extract_job_salary(), format_eligibility_badge(), Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, Combines batch and experience into a clean, modern Telegram card line., GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, csv (+56 more)

### Community 1 - "bot_optimizer.py"
Cohesion: 0.07
Nodes (52): calculate_skill_match_score(), dispatch_walkin_alerts(), extract_eligible_batch(), extract_experience_level(), format_deadlines_radar_report(), format_national_drives_report(), format_search_results_report(), format_single_drive_detail() (+44 more)

### Community 2 - "save_chat_id"
Cohesion: 0.09
Nodes (50): callback_query_handler, admin_only(), wrapper(), clear_qa(), command_scan_inbox(), handle_auto_apply(), handle_button(), handle_drive_detail_callback() (+42 more)

### Community 3 - "bot_features.py"
Cohesion: 0.07
Nodes (38): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), sync_to_notion(), dotenv (+30 more)

### Community 4 - "main.py"
Cohesion: 0.09
Nodes (34): base64, bs4, flask, google, groq, io, api_add_channel(), api_download_log() (+26 more)

### Community 5 - "run_playwright_apply"
Cohesion: 0.06
Nodes (32): apply_rag_memory_fallback(), apply_regex_fallback(), get_seeded_qa_memory(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions… (+24 more)

### Community 6 - "instahyre_engine.py"
Cohesion: 0.12
Nodes (22): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+14 more)

### Community 7 - "scrape_single_channel"
Cohesion: 0.18
Nodes (16): get_channel_session(), load_applied_jobs(), manual_radar_scan(), Scrapes one Telegram public channel and triggers applications for new jobs.…, Loops through all TARGET_CHANNELS and scrapes each one for new engineering…, Dedicated Radar Scan: 1. Scrapes the configured Telegram channel. 2. Fetches…, Saves details of the most recent application attempt., safe_save_json() (+8 more)

### Community 8 - "load_stats"
Cohesion: 0.16
Nodes (14): check_for_interviews(), api_manual_apply(), run(), bypass_blog_redirect(), clean_tracking_params(), home(), job_monitor_loop(), load_stats() (+6 more)

### Community 9 - "load_chat_id"
Cohesion: 0.17
Nodes (12): analyze_form_with_gemini(), api_debug_bot(), api_rotate_key(), api_telegram_test(), check_job_match(), get_groq_client(), load_chat_id(), Strictly filters for FRESHER / ENTRY-LEVEL ENGINEERING jobs only. Returns… (+4 more)

### Community 10 - "safe_load_json"
Cohesion: 0.17
Nodes (13): api_status(), daily_report_loop(), get_authorized_chat_ids(), is_sleep_time(), load_channel_status(), load_last_job(), load_retry_queue(), load_weekly_stats() (+5 more)

### Community 11 - "api_instahyre"
Cohesion: 0.22
Nodes (9): api_force_scan(), _run(), api_instahyre(), _run(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan. (+1 more)

### Community 12 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 13 - "Reporting a Vulnerability"
Cohesion: 0.25
Nodes (7): 1. Private Disclosure, 2. What to Include, 3. Response Process, Best Practices for Deployments, Reporting a Vulnerability, Security Policy, Supported Versions

### Community 14 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.33
Nodes (5): 🚀 GitHub Actions 24/7 Cloud Automation Guide, 📌 Repository Information, 🔑 Step 1: Set Up Encrypted Secrets on GitHub, 🚀 Step 2: Push the Enhanced Code to GitHub, ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

### Community 15 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
Cohesion: 0.33
Nodes (5): 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot), 🚀 Step 1: Push Code to Hugging Face Space, 🔑 Step 2: Configure Space Secrets, ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot), 📱 Step 4: Verify in Telegram

### Community 16 - "Q: Why does run_playwright_apply connect across 4 separate communities?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Why does run_playwright_apply connect across 4 separate communities?, Source Nodes

### Community 17 - "is_social_or_promo_link"
Cohesion: 0.40
Nodes (5): api_miniapp_jobs(), fetch_target_page_job_meta(), is_social_or_promo_link(), Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…

### Community 18 - "thread_supervisor"
Cohesion: 0.40
Nodes (5): cleanup_system_resources(), Kills orphaned browser processes and cleans cache to prevent resource leaks., Monitors and automatically restarts background threads if they crash., run_telegram_polling(), thread_supervisor()

## Knowledge Gaps
- **16 isolated node(s):** `1. Private Disclosure`, `2. What to Include`, `3. Response Process`, `Best Practices for Deployments`, `Supported Versions` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 166 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `job_radar.py` to `bot_features.py`, `bot_optimizer.py`, `api_instahyre`, `main.py`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `instahyre_engine.py` to `api_instahyre`, `main.py`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `job_radar.py` to `is_social_or_promo_link`, `main.py`, `load_chat_id`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **What connects `1. Private Disclosure`, `2. What to Include`, `3. Response Process` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07067603160667252 - nodes in this community are weakly interconnected._
- **Should `bot_optimizer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07138535995160314 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.09490196078431372 - nodes in this community are weakly interconnected._
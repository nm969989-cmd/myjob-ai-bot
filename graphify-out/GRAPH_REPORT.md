# Graph Report - Telegram_Job_Bot  (2026-09-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 422 nodes · 1022 edges · 30 communities (26 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 28 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `edae0aeb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- bot_optimizer.py
- run_radar
- save_chat_id
- main.py
- instahyre_engine.py
- scrape_single_channel
- load_chat_id
- imap_handler.py
- run_playwright_apply
- job_radar.py
- enterprise_adapters.py
- bot_features.py
- analyze_form_with_gemini
- api_instahyre
- job_monitor_loop
- execute_greenhouse_adapter
- ResumePDF
- Reporting a Vulnerability
- bypass_blog_redirect
- get_seeded_qa_memory
- os
- 🚀 GitHub Actions 24/7 Cloud Automation Guide
- 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)
- generate_dynamic_resume
- Q: Why does run_playwright_apply connect across 4 separate communities?
- _bezier_mouse_move
- LoggerWriter
- enforce_bot_security_profile
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
9. `extract_structured_channel_job_details()` - 14 edges
10. `get_tamil_nadu_jobs()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `run_instahyre_mass_apply()`  [EXTRACTED]
  main.py → instahyre_engine.py
- `run_radar()` --calls--> `calculate_skill_match_score()`  [EXTRACTED]
  job_radar.py → bot_optimizer.py
- `scrape_single_channel()` --calls--> `calculate_skill_match_score()`  [EXTRACTED]
  main.py → bot_optimizer.py
- `radar_loop()` --calls--> `dispatch_walkin_alerts()`  [EXTRACTED]
  main.py → bot_optimizer.py
- `run_radar()` --calls--> `extract_hr_email()`  [EXTRACTED]
  job_radar.py → bot_optimizer.py

## Import Cycles
- None detected.

## Communities (30 total, 4 thin omitted)

### Community 0 - "bot_optimizer.py"
Cohesion: 0.08
Nodes (53): calculate_skill_match_score(), dispatch_walkin_alerts(), extract_eligible_batch(), extract_experience_level(), extract_hr_email(), extract_job_salary(), format_deadlines_radar_report(), format_eligibility_badge() (+45 more)

### Community 1 - "run_radar"
Cohesion: 0.08
Nodes (48): _api_request(), classify_location(), clean_html(), dispatch_tamil_nadu_alerts(), get_tamil_nadu_jobs(), _fetch_channel_tn(), is_social_or_promo_link(), _keyword_match() (+40 more)

### Community 2 - "save_chat_id"
Cohesion: 0.10
Nodes (46): callback_query_handler, admin_only(), wrapper(), clear_qa(), command_scan_inbox(), handle_auto_apply(), handle_drive_detail_callback(), handle_interview_prep_callback() (+38 more)

### Community 3 - "main.py"
Cohesion: 0.09
Nodes (33): base64, bs4, flask, google, groq, io, api_add_channel(), api_download_log() (+25 more)

### Community 4 - "instahyre_engine.py"
Cohesion: 0.12
Nodes (22): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+14 more)

### Community 5 - "scrape_single_channel"
Cohesion: 0.14
Nodes (21): api_update_profile(), get_channel_session(), handle_button(), load_applied_jobs(), load_profile(), log_job(), manual_radar_scan(), Logs every job action, updates daily stats, and triggers Google Sheets Webhook. (+13 more)

### Community 6 - "load_chat_id"
Cohesion: 0.13
Nodes (19): api_debug_bot(), api_status(), api_telegram_test(), daily_report_loop(), get_authorized_chat_ids(), home(), is_sleep_time(), load_channel_status() (+11 more)

### Community 7 - "imap_handler.py"
Cohesion: 0.18
Nodes (13): sync_to_notion(), Exception, get_latest_otp(), Connects to Gmail, waits for a new email containing the search_term (e.g.…, scan_for_interview_invites(), api_scan_inbox(), application_worker(), auto_bug_fixer() (+5 more)

### Community 8 - "run_playwright_apply"
Cohesion: 0.14
Nodes (12): apply_regex_fallback(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.…, ai_fix_selector(), human_type(), Types text with human realism: burst speed, micro-pauses, occasional…, Navigates to the job_url, takes a screenshot, extracts form HTML, sends to… (+4 more)

### Community 9 - "job_radar.py"
Cohesion: 0.20
Nodes (12): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, csv, datetime, functools, html, escape_md(), 📡 JOB RADAR — Multi-Platform Job Finder (India & Tamil Nadu Priority Engine)…, json (+4 more)

### Community 10 - "enterprise_adapters.py"
Cohesion: 0.19
Nodes (12): execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Saves generated credentials to a secure local vault., Generates a highly secure password that passes all enterprise checks., Advanced Workday adapter. Handles Apply, account creation, OTP email…, Logs into Gmail via IMAP and fetches the latest 6-digit OTP or magic link.…, save_to_vault() (+4 more)

### Community 11 - "bot_features.py"
Cohesion: 0.25
Nodes (9): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), email_header, email_message (+1 more)

### Community 12 - "analyze_form_with_gemini"
Cohesion: 0.22
Nodes (8): analyze_form_with_gemini(), api_rotate_key(), check_job_match(), get_groq_client(), Strictly filters for FRESHER / ENTRY-LEVEL ENGINEERING jobs only. Returns…, Uses Gemini API to map form fields to the user's profile data, leveraging both…, rotate_gemini_key(), rotate_groq_key()

### Community 13 - "api_instahyre"
Cohesion: 0.22
Nodes (9): api_force_scan(), _run(), api_instahyre(), _run(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan. (+1 more)

### Community 14 - "job_monitor_loop"
Cohesion: 0.25
Nodes (8): check_for_interviews(), cleanup_system_resources(), job_monitor_loop(), Kills orphaned browser processes and cleans cache to prevent resource leaks., Monitors and automatically restarts background threads if they crash., run_telegram_polling(), save_stats(), thread_supervisor()

### Community 15 - "execute_greenhouse_adapter"
Cohesion: 0.25
Nodes (6): execute_greenhouse_adapter(), execute_lever_adapter(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).…, Finds the valid resume path across OS platforms, case variations, profile…, resolve_resume_path()

### Community 16 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 17 - "Reporting a Vulnerability"
Cohesion: 0.25
Nodes (7): 1. Private Disclosure, 2. What to Include, 3. Response Process, Best Practices for Deployments, Reporting a Vulnerability, Security Policy, Supported Versions

### Community 18 - "bypass_blog_redirect"
Cohesion: 0.29
Nodes (7): api_manual_apply(), run(), bypass_blog_redirect(), clean_tracking_params(), run(), Strips Google Analytics/Social Media tracking parameters to keep URLs clean and…, Intelligently finds the real company application link inside ad-heavy…

### Community 19 - "get_seeded_qa_memory"
Cohesion: 0.33
Nodes (6): apply_rag_memory_fallback(), get_seeded_qa_memory(), Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions…, record_learned_qa()

### Community 20 - "os"
Cohesion: 0.33
Nodes (4): dotenv, email, imaplib, os

### Community 21 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.33
Nodes (5): 🚀 GitHub Actions 24/7 Cloud Automation Guide, 📌 Repository Information, 🔑 Step 1: Set Up Encrypted Secrets on GitHub, 🚀 Step 2: Push the Enhanced Code to GitHub, ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

### Community 22 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
Cohesion: 0.33
Nodes (5): 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot), 🚀 Step 1: Push Code to Hugging Face Space, 🔑 Step 2: Configure Space Secrets, ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot), 📱 Step 4: Verify in Telegram

### Community 23 - "generate_dynamic_resume"
Cohesion: 0.40
Nodes (4): FPDF, generate_dynamic_resume(), Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF., ResumePDF

### Community 24 - "Q: Why does run_playwright_apply connect across 4 separate communities?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Why does run_playwright_apply connect across 4 separate communities?, Source Nodes

### Community 25 - "_bezier_mouse_move"
Cohesion: 0.50
Nodes (4): _bezier_mouse_move(), human_mimicry(), FEATURE 2 — Ghost Cursor: Move mouse along a cubic Bezier curve with random…, Multi-layer human simulation: Bezier mouse paths, reading scroll, micro-pauses,…

## Knowledge Gaps
- **16 isolated node(s):** `1. Private Disclosure`, `2. What to Include`, `3. Response Process`, `Best Practices for Deployments`, `Supported Versions` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 161 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `run_radar` to `bot_optimizer.py`, `main.py`, `imap_handler.py`, `job_radar.py`, `api_instahyre`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `instahyre_engine.py` to `main.py`, `api_instahyre`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `run_radar` to `bot_optimizer.py`, `job_radar.py`, `main.py`, `analyze_form_with_gemini`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **What connects `1. Private Disclosure`, `2. What to Include`, `3. Response Process` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `bot_optimizer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0750151240169389 - nodes in this community are weakly interconnected._
- **Should `run_radar` be split into smaller, more focused modules?**
  _Cohesion score 0.07510204081632653 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.09898242368177614 - nodes in this community are weakly interconnected._
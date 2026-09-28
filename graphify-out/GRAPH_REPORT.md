# Graph Report - Telegram_Job_Bot  (2026-09-28)

## Corpus Check
- 17 files · ~73,173 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 2, .example 1)

## Summary
- 391 nodes · 915 edges · 21 communities (17 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `aba0e7de`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- job_radar.py
- save_chat_id
- bot_optimizer.py
- run_playwright_apply
- main.py
- scrape_single_channel
- bot_features.py
- load_chat_id
- daily_report_loop
- ResumePDF
- analyze_form_with_gemini
- api_instahyre
- api_radar
- get_gemini_client
- LoggerWriter
- Reporting a Vulnerability
- 🚀 GitHub Actions 24/7 Cloud Automation Guide
- 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)
- enforce_bot_security_profile
- is_social_or_promo_link

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 34 edges
2. `save_chat_id()` - 32 edges
3. `admin_only()` - 31 edges
4. `run_radar()` - 24 edges
5. `scrape_single_channel()` - 23 edges
6. `classify_location()` - 15 edges
7. `load_chat_id()` - 14 edges
8. `run_instahyre_mass_apply()` - 13 edges
9. `safe_load_json()` - 13 edges
10. `run_all_tests()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `_run()` --calls--> `run_instahyre_mass_apply()`  [EXTRACTED]
  main.py → instahyre_engine.py
- `run_playwright_apply()` --calls--> `generate_dynamic_cover_letter()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `wait_for_otp()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `sync_to_notion()`  [EXTRACTED]
  main.py → bot_features.py
- `scrape_single_channel()` --calls--> `sync_to_notion()`  [EXTRACTED]
  main.py → bot_features.py

## Import Cycles
- None detected.

## Communities (21 total, 4 thin omitted)

### Community 0 - "job_radar.py"
Cohesion: 0.10
Nodes (47): extract_hr_email(), extract_job_salary(), Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, functools, _api_request(), classify_location(), clean_html() (+39 more)

### Community 1 - "save_chat_id"
Cohesion: 0.09
Nodes (48): callback_query_handler, admin_only(), wrapper(), clear_qa(), command_scan_inbox(), get_authorized_chat_ids(), handle_auto_apply(), handle_interview_prep_callback() (+40 more)

### Community 2 - "bot_optimizer.py"
Cohesion: 0.08
Nodes (37): apply_rag_memory_fallback(), calculate_skill_match_score(), format_deadlines_radar_report(), format_national_drives_report(), format_single_drive_detail(), generate_fast_interview_cheat_sheet(), generate_linkedin_outreach_note(), generate_market_analytics_report() (+29 more)

### Community 3 - "run_playwright_apply"
Cohesion: 0.06
Nodes (30): generate_interview_prep(), send_cold_email_if_found(), apply_regex_fallback(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.…, execute_greenhouse_adapter(), execute_lever_adapter() (+22 more)

### Community 4 - "main.py"
Cohesion: 0.09
Nodes (33): base64, bs4, flask, google, groq, io, api_add_channel(), api_download_log() (+25 more)

### Community 5 - "scrape_single_channel"
Cohesion: 0.08
Nodes (34): check_for_interviews(), run(), bypass_blog_redirect(), check_job_match(), clean_tracking_params(), extract_structured_channel_job_details(), get_channel_session(), handle_button() (+26 more)

### Community 6 - "bot_features.py"
Cohesion: 0.05
Nodes (52): CoverLetterPDF, generate_dynamic_cover_letter(), FPDF, Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, _sanitize_latin1(), wait_for_otp(), GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, csv (+44 more)

### Community 7 - "load_chat_id"
Cohesion: 0.22
Nodes (9): Exception, api_debug_bot(), api_telegram_test(), application_worker(), auto_bug_fixer(), home(), load_chat_id(), Feed error to Gemini and send the AI fix directly to Telegram. (+1 more)

### Community 8 - "daily_report_loop"
Cohesion: 0.15
Nodes (13): api_status(), cleanup_system_resources(), daily_report_loop(), is_sleep_time(), load_retry_queue(), load_weekly_stats(), Live stats for dashboard widgets., Returns True between 11 PM and 6 AM IST — bot rests to avoid bot-detection. (+5 more)

### Community 9 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 10 - "analyze_form_with_gemini"
Cohesion: 0.50
Nodes (4): analyze_form_with_gemini(), get_groq_client(), Uses Gemini API to map form fields to the user's profile data, leveraging both…, rotate_groq_key()

### Community 11 - "api_instahyre"
Cohesion: 0.22
Nodes (9): api_force_scan(), _run(), api_instahyre(), _run(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan. (+1 more)

### Community 13 - "get_gemini_client"
Cohesion: 0.25
Nodes (9): sync_to_notion(), scan_for_interview_invites(), api_rotate_key(), api_scan_inbox(), _bg_scan(), get_gemini_client(), radar_loop(), Background thread that runs the Job Radar scan every 6 hours and sends results… (+1 more)

### Community 16 - "Reporting a Vulnerability"
Cohesion: 0.25
Nodes (7): 1. Private Disclosure, 2. What to Include, 3. Response Process, Best Practices for Deployments, Reporting a Vulnerability, Security Policy, Supported Versions

### Community 17 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.33
Nodes (5): 🚀 GitHub Actions 24/7 Cloud Automation Guide, 📌 Repository Information, 🔑 Step 1: Set Up Encrypted Secrets on GitHub, 🚀 Step 2: Push the Enhanced Code to GitHub, ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

### Community 18 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
Cohesion: 0.33
Nodes (5): 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot), 🚀 Step 1: Push Code to Hugging Face Space, 🔑 Step 2: Configure Space Secrets, ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot), 📱 Step 4: Verify in Telegram

### Community 20 - "is_social_or_promo_link"
Cohesion: 0.40
Nodes (5): api_miniapp_jobs(), fetch_target_page_job_meta(), is_social_or_promo_link(), Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…

## Knowledge Gaps
- **13 isolated node(s):** `📌 Repository Information`, `🔑 Step 1: Set Up Encrypted Secrets on GitHub`, `🚀 Step 2: Push the Enhanced Code to GitHub`, `⚡ Step 3: Trigger a Manual Test Run in GitHub Actions`, `🚀 Step 1: Push Code to Hugging Face Space` (+8 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 147 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `job_radar.py` to `bot_optimizer.py`, `main.py`, `bot_features.py`, `api_instahyre`, `get_gemini_client`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `job_radar.py` to `scrape_single_channel`, `main.py`, `is_social_or_promo_link`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `bot_features.py` to `api_instahyre`, `main.py`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **What connects `📌 Repository Information`, `🔑 Step 1: Set Up Encrypted Secrets on GitHub`, `🚀 Step 2: Push the Enhanced Code to GitHub` to the rest of the system?**
  _13 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10119047619047619 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.09268707482993198 - nodes in this community are weakly interconnected._
- **Should `bot_optimizer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08246225319396051 - nodes in this community are weakly interconnected._
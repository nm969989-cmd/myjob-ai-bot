# Graph Report - Telegram_Job_Bot  (2026-09-29)

## Corpus Check
- 18 files · ~74,069 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 3 file(s) not represented in the graph (top: (none) 2, .example 1)

## Summary
- 402 nodes · 943 edges · 24 communities (20 shown, 4 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 26 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b83d383f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- scrape_single_channel
- run_radar
- bot_features.py
- save_chat_id
- bot_optimizer.py
- main.py
- instahyre_engine.py
- load_chat_id
- api_instahyre
- ResumePDF
- Reporting a Vulnerability
- get_gemini_client
- 🚀 GitHub Actions 24/7 Cloud Automation Guide
- 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)
- run_playwright_apply
- job_radar.py
- LoggerWriter
- api_radar
- enforce_bot_security_profile
- execute_workday_adapter
- analyze_form_with_gemini
- Q: Why does run_playwright_apply connect across 4 separate communities?
- is_social_or_promo_link

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 34 edges
2. `save_chat_id()` - 32 edges
3. `admin_only()` - 31 edges
4. `run_radar()` - 24 edges
5. `scrape_single_channel()` - 23 edges
6. `run_all_tests()` - 16 edges
7. `classify_location()` - 15 edges
8. `_make_job()` - 15 edges
9. `load_chat_id()` - 14 edges
10. `extract_structured_channel_job_details()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `_bg_scan()` --calls--> `scan_for_interview_invites()`  [EXTRACTED]
  main.py → imap_handler.py
- `_run()` --calls--> `run_instahyre_mass_apply()`  [EXTRACTED]
  main.py → instahyre_engine.py
- `run_playwright_apply()` --calls--> `generate_dynamic_cover_letter()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `generate_interview_prep()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `send_cold_email_if_found()`  [EXTRACTED]
  main.py → bot_features.py

## Import Cycles
- None detected.

## Communities (24 total, 4 thin omitted)

### Community 0 - "scrape_single_channel"
Cohesion: 0.08
Nodes (40): check_for_interviews(), run(), api_status(), bypass_blog_redirect(), clean_tracking_params(), daily_report_loop(), get_channel_session(), handle_button() (+32 more)

### Community 1 - "run_radar"
Cohesion: 0.10
Nodes (35): _api_request(), classify_location(), clean_html(), _keyword_match(), load_seen_jobs(), mark_seen(), normalize_job_url(), Uses python-jobspy for Chennai, Coimbatore, Tamil Nadu & Bangalore India jobs. (+27 more)

### Community 2 - "bot_features.py"
Cohesion: 0.18
Nodes (14): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), email, email_header (+6 more)

### Community 3 - "save_chat_id"
Cohesion: 0.09
Nodes (47): callback_query_handler, admin_only(), wrapper(), clear_qa(), command_scan_inbox(), _bg_scan(), get_authorized_chat_ids(), handle_auto_apply() (+39 more)

### Community 4 - "bot_optimizer.py"
Cohesion: 0.08
Nodes (47): calculate_skill_match_score(), extract_eligible_batch(), extract_experience_level(), extract_hr_email(), extract_job_salary(), format_deadlines_radar_report(), format_eligibility_badge(), format_national_drives_report() (+39 more)

### Community 5 - "main.py"
Cohesion: 0.09
Nodes (33): base64, bs4, flask, google, groq, io, api_add_channel(), api_download_log() (+25 more)

### Community 6 - "instahyre_engine.py"
Cohesion: 0.12
Nodes (22): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+14 more)

### Community 7 - "load_chat_id"
Cohesion: 0.22
Nodes (9): Exception, api_debug_bot(), api_telegram_test(), application_worker(), auto_bug_fixer(), home(), load_chat_id(), Feed error to Gemini and send the AI fix directly to Telegram. (+1 more)

### Community 8 - "api_instahyre"
Cohesion: 0.22
Nodes (9): api_force_scan(), _run(), api_instahyre(), _run(), api_run_radar(), _run(), Triggers a fresh Job Radar scan in a background thread., Triggers an immediate Telegram channel scan. (+1 more)

### Community 9 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 10 - "Reporting a Vulnerability"
Cohesion: 0.25
Nodes (7): 1. Private Disclosure, 2. What to Include, 3. Response Process, Best Practices for Deployments, Reporting a Vulnerability, Security Policy, Supported Versions

### Community 11 - "get_gemini_client"
Cohesion: 0.20
Nodes (11): sync_to_notion(), scan_for_interview_invites(), api_scan_inbox(), cleanup_system_resources(), get_gemini_client(), radar_loop(), Background thread that runs the Job Radar scan every 6 hours and sends results…, Kills orphaned browser processes and cleans cache to prevent resource leaks. (+3 more)

### Community 12 - "🚀 GitHub Actions 24/7 Cloud Automation Guide"
Cohesion: 0.33
Nodes (5): 🚀 GitHub Actions 24/7 Cloud Automation Guide, 📌 Repository Information, 🔑 Step 1: Set Up Encrypted Secrets on GitHub, 🚀 Step 2: Push the Enhanced Code to GitHub, ⚡ Step 3: Trigger a Manual Test Run in GitHub Actions

### Community 13 - "🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot)"
Cohesion: 0.33
Nodes (5): 🤖 Hugging Face Cloud Deployment Guide (Telegram Job Bot), 🚀 Step 1: Push Code to Hugging Face Space, 🔑 Step 2: Configure Space Secrets, ⏰ Step 3: Keep the Bot Online 24/7 (UptimeRobot), 📱 Step 4: Verify in Telegram

### Community 14 - "run_playwright_apply"
Cohesion: 0.05
Nodes (35): apply_rag_memory_fallback(), apply_regex_fallback(), get_seeded_qa_memory(), minify_form_html(), Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.…, Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions… (+27 more)

### Community 15 - "job_radar.py"
Cohesion: 0.15
Nodes (15): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, csv, datetime, dotenv, functools, html, escape_md(), 📡 JOB RADAR — Multi-Platform Job Finder (India & Tamil Nadu Priority Engine)… (+7 more)

### Community 19 - "execute_workday_adapter"
Cohesion: 0.25
Nodes (8): execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Saves generated credentials to a secure local vault., Generates a highly secure password that passes all enterprise checks., Advanced Workday adapter. Handles Apply, account creation, OTP email…, Logs into Gmail via IMAP and fetches the latest 6-digit OTP or magic link.…, save_to_vault()

### Community 21 - "analyze_form_with_gemini"
Cohesion: 0.33
Nodes (6): analyze_form_with_gemini(), api_rotate_key(), get_groq_client(), Uses Gemini API to map form fields to the user's profile data, leveraging both…, rotate_gemini_key(), rotate_groq_key()

### Community 22 - "Q: Why does run_playwright_apply connect across 4 separate communities?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Why does run_playwright_apply connect across 4 separate communities?, Source Nodes

### Community 23 - "is_social_or_promo_link"
Cohesion: 0.40
Nodes (5): api_miniapp_jobs(), fetch_target_page_job_meta(), is_social_or_promo_link(), Detects if a URL is a social media link, channel promo, parked domain, or non-…, Fetches title, h1, and key meta from the actual destination webpage. Inspects…

## Knowledge Gaps
- **16 isolated node(s):** `📌 Repository Information`, `🔑 Step 1: Set Up Encrypted Secrets on GitHub`, `🚀 Step 2: Push the Enhanced Code to GitHub`, `⚡ Step 3: Trigger a Manual Test Run in GitHub Actions`, `🚀 Step 1: Push Code to Hugging Face Space` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 154 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `run_radar` to `bot_optimizer.py`, `main.py`, `api_instahyre`, `get_gemini_client`, `job_radar.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `run_radar` to `is_social_or_promo_link`, `bot_optimizer.py`, `main.py`, `job_radar.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `instahyre_engine.py` to `api_instahyre`, `main.py`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **What connects `📌 Repository Information`, `🔑 Step 1: Set Up Encrypted Secrets on GitHub`, `🚀 Step 2: Push the Enhanced Code to GitHub` to the rest of the system?**
  _16 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `scrape_single_channel` be split into smaller, more focused modules?**
  _Cohesion score 0.07948717948717948 - nodes in this community are weakly interconnected._
- **Should `run_radar` be split into smaller, more focused modules?**
  _Cohesion score 0.0990990990990991 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.09308510638297872 - nodes in this community are weakly interconnected._
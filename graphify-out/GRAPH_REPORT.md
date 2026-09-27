# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 301 nodes · 703 edges · 14 communities (11 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7bb69826`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- job_radar.py
- run_playwright_apply
- admin_only
- scrape_single_channel
- safe_load_json
- enterprise_adapters.py
- ResumePDF
- get_seeded_qa_memory
- format_national_drives_report
- generate_fast_interview_cheat_sheet
- LoggerWriter
- FPDF

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 32 edges
2. `admin_only()` - 29 edges
3. `save_chat_id()` - 29 edges
4. `scrape_single_channel()` - 23 edges
5. `run_radar()` - 22 edges
6. `classify_location()` - 15 edges
7. `load_chat_id()` - 14 edges
8. `safe_load_json()` - 13 edges
9. `_make_job()` - 12 edges
10. `_scan_single_channel_radar()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `api_scan_inbox()` --calls--> `scan_for_interview_invites()`  [INFERRED]
  main.py → imap_handler.py
- `run_playwright_apply()` --calls--> `get_latest_otp()`  [INFERRED]
  main.py → imap_handler.py
- `api_miniapp_jobs()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `check_job_match()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `extract_structured_channel_job_details()` --calls--> `calculate_skill_match_score()`  [EXTRACTED]
  main.py → bot_optimizer.py

## Import Cycles
- None detected.

## Communities (14 total, 2 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.06
Nodes (57): FPDF, analyze_form_with_gemini(), api_add_channel(), api_debug_bot(), api_download_log(), api_download_profile(), api_download_qa(), api_force_scan() (+49 more)

### Community 1 - "job_radar.py"
Cohesion: 0.09
Nodes (50): calculate_skill_match_score(), extract_hr_email(), extract_job_salary(), is_job_link_alive(), bot_optimizer.py — Efficiency Module for the Autonomous Job Bot Features: 1.…, Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, Computes an ATS-style skill match score (0-100%) by comparing keywords found in… (+42 more)

### Community 2 - "run_playwright_apply"
Cohesion: 0.07
Nodes (40): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, _sanitize_latin1(), send_cold_email_if_found(), wait_for_otp() (+32 more)

### Community 3 - "admin_only"
Cohesion: 0.12
Nodes (40): admin_only(), clear_qa(), command_scan_inbox(), get_authorized_chat_ids(), handle_auto_apply(), handle_qa_button(), is_authorized(), load_pending_qa() (+32 more)

### Community 4 - "scrape_single_channel"
Cohesion: 0.08
Nodes (35): sync_to_notion(), generate_linkedin_outreach_note(), generate_market_analytics_report(), Generates a personalized, professional LinkedIn connection note (<= 300…, Aggregates application logs, radar cache, and QA memory into a high-visibility,…, Exception, get_latest_otp(), Connects to Gmail, waits for a new email containing the search_term (e.g.… (+27 more)

### Community 5 - "safe_load_json"
Cohesion: 0.10
Nodes (25): check_for_interviews(), api_status(), cleanup_system_resources(), daily_report_loop(), is_sleep_time(), job_monitor_loop(), load_channel_status(), load_last_job() (+17 more)

### Community 6 - "enterprise_adapters.py"
Cohesion: 0.18
Nodes (14): execute_greenhouse_adapter(), execute_lever_adapter(), execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Saves generated credentials to a secure local vault., Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).… (+6 more)

### Community 7 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 8 - "get_seeded_qa_memory"
Cohesion: 0.33
Nodes (6): apply_rag_memory_fallback(), get_seeded_qa_memory(), Loads qa_memory from disk, auto-seeding with standard defaults if missing or…, Persists newly encountered and answered questions into the local memory…, Evaluates form fields via comprehensive DOM inspection. Matches questions…, record_learned_qa()

### Community 9 - "format_national_drives_report"
Cohesion: 0.50
Nodes (4): format_national_drives_report(), get_national_drives(), Loads national mass drives from disk or initializes with verified seeds., Formats verified national mass drives into Telegram-ready HTML chunks.…

### Community 10 - "generate_fast_interview_cheat_sheet"
Cohesion: 0.50
Nodes (4): generate_fast_interview_cheat_sheet(), Generates a high-yield, 3-question technical interview preparation cheat sheet…, callback_query_handler, handle_interview_prep_callback()

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `job_radar.py` to `main.py`, `scrape_single_channel`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `run_playwright_apply()` connect `run_playwright_apply` to `main.py`, `admin_only`, `scrape_single_channel`, `safe_load_json`, `enterprise_adapters.py`, `get_seeded_qa_memory`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `job_radar.py` to `main.py`, `scrape_single_channel`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05875706214689266 - nodes in this community are weakly interconnected._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09433962264150944 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.06533776301218161 - nodes in this community are weakly interconnected._
- **Should `admin_only` be split into smaller, more focused modules?**
  _Cohesion score 0.11666666666666667 - nodes in this community are weakly interconnected._
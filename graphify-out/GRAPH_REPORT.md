# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 286 nodes · 658 edges · 12 communities (9 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `631556c1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- job_radar.py
- run_playwright_apply
- admin_only
- scrape_single_channel
- bot_optimizer.py
- get_gemini_client
- enterprise_adapters.py
- ResumePDF
- LoggerWriter
- FPDF

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 32 edges
2. `admin_only()` - 27 edges
3. `save_chat_id()` - 26 edges
4. `scrape_single_channel()` - 21 edges
5. `run_radar()` - 18 edges
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
- `extract_structured_channel_job_details()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py

## Import Cycles
- None detected.

## Communities (12 total, 2 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.06
Nodes (57): FPDF, analyze_form_with_gemini(), api_add_channel(), api_debug_bot(), api_download_log(), api_download_profile(), api_download_qa(), api_force_scan() (+49 more)

### Community 1 - "job_radar.py"
Cohesion: 0.12
Nodes (41): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, _api_request(), classify_location(), clean_html(), escape_md(), is_social_or_promo_link(), _keyword_match(), load_seen_jobs() (+33 more)

### Community 2 - "run_playwright_apply"
Cohesion: 0.07
Nodes (36): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, _sanitize_latin1(), send_cold_email_if_found(), wait_for_otp() (+28 more)

### Community 3 - "admin_only"
Cohesion: 0.12
Nodes (39): callback_query_handler, admin_only(), clear_qa(), command_scan_inbox(), get_authorized_chat_ids(), handle_auto_apply(), handle_qa_button(), is_authorized() (+31 more)

### Community 4 - "scrape_single_channel"
Cohesion: 0.10
Nodes (34): check_for_interviews(), api_status(), daily_report_loop(), handle_button(), is_sleep_time(), job_monitor_loop(), load_applied_jobs(), load_channel_status() (+26 more)

### Community 5 - "bot_optimizer.py"
Cohesion: 0.10
Nodes (23): apply_rag_memory_fallback(), apply_regex_fallback(), extract_hr_email(), extract_job_salary(), generate_linkedin_outreach_note(), get_seeded_qa_memory(), minify_form_html(), bot_optimizer.py — Efficiency Module for the Autonomous Job Bot Features: 1.… (+15 more)

### Community 6 - "get_gemini_client"
Cohesion: 0.15
Nodes (16): sync_to_notion(), Exception, get_latest_otp(), Connects to Gmail, waits for a new email containing the search_term (e.g.…, scan_for_interview_invites(), application_worker(), auto_bug_fixer(), cleanup_system_resources() (+8 more)

### Community 7 - "enterprise_adapters.py"
Cohesion: 0.18
Nodes (14): execute_greenhouse_adapter(), execute_lever_adapter(), execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Saves generated credentials to a secure local vault., Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).… (+6 more)

### Community 8 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `job_radar.py` to `main.py`, `get_gemini_client`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `run_playwright_apply()` connect `run_playwright_apply` to `main.py`, `admin_only`, `scrape_single_channel`, `bot_optimizer.py`, `get_gemini_client`, `enterprise_adapters.py`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `job_radar.py` to `main.py`, `bot_optimizer.py`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05875706214689266 - nodes in this community are weakly interconnected._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11960132890365449 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.07422402159244265 - nodes in this community are weakly interconnected._
- **Should `admin_only` be split into smaller, more focused modules?**
  _Cohesion score 0.11605937921727395 - nodes in this community are weakly interconnected._
# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 283 nodes · 662 edges · 10 communities (8 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `980d6dc7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- job_radar.py
- admin_only
- run_playwright_apply
- scrape_single_channel
- instahyre_engine.py
- enterprise_adapters.py
- ResumePDF
- LoggerWriter

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
- `api_miniapp_jobs()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `check_job_match()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `radar_loop()` --calls--> `run_radar()`  [EXTRACTED]
  main.py → job_radar.py
- `run_playwright_apply()` --calls--> `get_latest_otp()`  [INFERRED]
  main.py → imap_handler.py

## Import Cycles
- None detected.

## Communities (10 total, 1 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.06
Nodes (57): analyze_form_with_gemini(), api_add_channel(), api_debug_bot(), api_download_log(), api_download_profile(), api_download_qa(), api_force_scan(), api_health_check() (+49 more)

### Community 1 - "job_radar.py"
Cohesion: 0.09
Nodes (50): extract_hr_email(), extract_job_salary(), bot_optimizer.py — Efficiency Module for the Autonomous Job Bot Features: 1.…, Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, _api_request(), classify_location(), clean_html() (+42 more)

### Community 2 - "admin_only"
Cohesion: 0.11
Nodes (45): callback_query_handler, admin_only(), clear_qa(), command_scan_inbox(), get_authorized_chat_ids(), handle_auto_apply(), handle_button(), handle_qa_button() (+37 more)

### Community 3 - "run_playwright_apply"
Cohesion: 0.07
Nodes (37): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), sync_to_notion(), apply_rag_memory_fallback() (+29 more)

### Community 4 - "scrape_single_channel"
Cohesion: 0.07
Nodes (37): check_for_interviews(), generate_linkedin_outreach_note(), Generates a personalized, professional LinkedIn connection note (<= 300…, GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, escape_md(), api_status(), cleanup_system_resources(), daily_report_loop() (+29 more)

### Community 5 - "instahyre_engine.py"
Cohesion: 0.15
Nodes (18): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+10 more)

### Community 6 - "enterprise_adapters.py"
Cohesion: 0.18
Nodes (14): execute_greenhouse_adapter(), execute_lever_adapter(), execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Saves generated credentials to a secure local vault., Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).… (+6 more)

### Community 7 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `job_radar.py` to `main.py`, `run_playwright_apply`, `scrape_single_channel`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `job_radar.py` to `main.py`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `instahyre_engine.py` to `main.py`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05875706214689266 - nodes in this community are weakly interconnected._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0942684766214178 - nodes in this community are weakly interconnected._
- **Should `admin_only` be split into smaller, more focused modules?**
  _Cohesion score 0.10606060606060606 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.07051282051282051 - nodes in this community are weakly interconnected._
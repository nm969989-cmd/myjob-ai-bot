# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 296 nodes · 690 edges · 12 communities (9 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b147e6cd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- job_radar.py
- run_playwright_apply
- admin_only
- scrape_single_channel
- safe_load_json
- instahyre_engine.py
- handle_button
- ResumePDF
- LoggerWriter
- FPDF

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 32 edges
2. `admin_only()` - 28 edges
3. `save_chat_id()` - 28 edges
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
- `api_miniapp_jobs()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `check_job_match()` --calls--> `classify_location()`  [EXTRACTED]
  main.py → job_radar.py
- `extract_structured_channel_job_details()` --calls--> `calculate_skill_match_score()`  [EXTRACTED]
  main.py → bot_optimizer.py
- `scrape_single_channel()` --calls--> `calculate_skill_match_score()`  [EXTRACTED]
  main.py → bot_optimizer.py

## Import Cycles
- None detected.

## Communities (12 total, 2 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.06
Nodes (57): FPDF, analyze_form_with_gemini(), api_add_channel(), api_debug_bot(), api_download_log(), api_download_profile(), api_download_qa(), api_force_scan() (+49 more)

### Community 1 - "job_radar.py"
Cohesion: 0.09
Nodes (50): calculate_skill_match_score(), extract_hr_email(), extract_job_salary(), is_job_link_alive(), bot_optimizer.py — Efficiency Module for the Autonomous Job Bot Features: 1.…, Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, Computes an ATS-style skill match score (0-100%) by comparing keywords found in… (+42 more)

### Community 2 - "run_playwright_apply"
Cohesion: 0.06
Nodes (44): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), apply_rag_memory_fallback(), apply_regex_fallback() (+36 more)

### Community 3 - "admin_only"
Cohesion: 0.12
Nodes (39): admin_only(), clear_qa(), command_scan_inbox(), get_authorized_chat_ids(), handle_auto_apply(), handle_qa_button(), is_authorized(), load_pending_qa() (+31 more)

### Community 4 - "scrape_single_channel"
Cohesion: 0.11
Nodes (26): sync_to_notion(), generate_linkedin_outreach_note(), Generates a personalized, professional LinkedIn connection note (<= 300…, Exception, scan_for_interview_invites(), application_worker(), auto_bug_fixer(), extract_structured_channel_job_details() (+18 more)

### Community 5 - "safe_load_json"
Cohesion: 0.10
Nodes (25): check_for_interviews(), api_status(), cleanup_system_resources(), daily_report_loop(), is_sleep_time(), job_monitor_loop(), load_channel_status(), load_last_job() (+17 more)

### Community 6 - "instahyre_engine.py"
Cohesion: 0.15
Nodes (18): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+10 more)

### Community 7 - "handle_button"
Cohesion: 0.22
Nodes (11): generate_fast_interview_cheat_sheet(), generate_market_analytics_report(), Generates a high-yield, 3-question technical interview preparation cheat sheet…, Aggregates application logs, radar cache, and QA memory into a high-visibility,…, callback_query_handler, handle_button(), handle_interview_prep_callback(), load_applied_jobs() (+3 more)

### Community 8 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `job_radar.py` to `main.py`, `scrape_single_channel`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Why does `run_playwright_apply()` connect `run_playwright_apply` to `main.py`, `admin_only`, `scrape_single_channel`, `safe_load_json`, `instahyre_engine.py`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `job_radar.py` to `main.py`, `scrape_single_channel`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05875706214689266 - nodes in this community are weakly interconnected._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09433962264150944 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.056429232192414434 - nodes in this community are weakly interconnected._
- **Should `admin_only` be split into smaller, more focused modules?**
  _Cohesion score 0.11875843454790823 - nodes in this community are weakly interconnected._
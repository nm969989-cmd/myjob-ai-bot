# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 307 nodes · 730 edges · 12 communities (9 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `34854541`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- main.py
- job_radar.py
- run_playwright_apply
- save_chat_id
- scrape_single_channel
- safe_load_json
- bot_optimizer.py
- instahyre_engine.py
- ResumePDF
- LoggerWriter
- FPDF

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 32 edges
2. `save_chat_id()` - 30 edges
3. `admin_only()` - 29 edges
4. `scrape_single_channel()` - 23 edges
5. `run_radar()` - 21 edges
6. `load_chat_id()` - 14 edges
7. `classify_location()` - 14 edges
8. `safe_load_json()` - 13 edges
9. `_make_job()` - 12 edges
10. `_scan_single_channel_radar()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `api_miniapp_jobs()` --calls--> `classify_location()`  [INFERRED]
  main.py → job_radar.py
- `api_scan_inbox()` --calls--> `scan_for_interview_invites()`  [INFERRED]
  main.py → imap_handler.py
- `check_job_match()` --calls--> `classify_location()`  [INFERRED]
  main.py → job_radar.py
- `extract_structured_channel_job_details()` --calls--> `classify_location()`  [INFERRED]
  main.py → job_radar.py
- `radar_loop()` --calls--> `run_radar()`  [INFERRED]
  main.py → job_radar.py

## Import Cycles
- None detected.

## Communities (12 total, 2 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.06
Nodes (57): FPDF, analyze_form_with_gemini(), api_add_channel(), api_debug_bot(), api_download_log(), api_download_profile(), api_download_qa(), api_force_scan() (+49 more)

### Community 1 - "job_radar.py"
Cohesion: 0.11
Nodes (45): extract_hr_email(), extract_job_salary(), Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, _api_request(), classify_location(), clean_html() (+37 more)

### Community 2 - "run_playwright_apply"
Cohesion: 0.07
Nodes (38): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), apply_regex_fallback(), minify_form_html() (+30 more)

### Community 3 - "save_chat_id"
Cohesion: 0.12
Nodes (39): callback_query_handler, admin_only(), clear_qa(), command_scan_inbox(), handle_auto_apply(), handle_drive_detail_callback(), handle_interview_prep_callback(), handle_qa_button() (+31 more)

### Community 4 - "scrape_single_channel"
Cohesion: 0.11
Nodes (29): sync_to_notion(), Exception, scan_for_interview_invites(), application_worker(), auto_bug_fixer(), extract_structured_channel_job_details(), fetch_target_page_job_meta(), get_gemini_client() (+21 more)

### Community 5 - "safe_load_json"
Cohesion: 0.09
Nodes (29): check_for_interviews(), api_status(), cleanup_system_resources(), daily_report_loop(), get_authorized_chat_ids(), is_authorized(), is_sleep_time(), job_monitor_loop() (+21 more)

### Community 6 - "bot_optimizer.py"
Cohesion: 0.13
Nodes (25): apply_rag_memory_fallback(), calculate_skill_match_score(), format_national_drives_report(), format_single_drive_detail(), generate_fast_interview_cheat_sheet(), generate_linkedin_outreach_note(), generate_market_analytics_report(), get_national_drives() (+17 more)

### Community 7 - "instahyre_engine.py"
Cohesion: 0.15
Nodes (18): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+10 more)

### Community 8 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_playwright_apply()` connect `run_playwright_apply` to `main.py`, `save_chat_id`, `scrape_single_channel`, `safe_load_json`, `bot_optimizer.py`, `instahyre_engine.py`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `run_radar()` connect `job_radar.py` to `scrape_single_channel`, `bot_optimizer.py`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `extract_hr_email()` connect `job_radar.py` to `main.py`, `scrape_single_channel`, `bot_optimizer.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05875706214689266 - nodes in this community are weakly interconnected._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1091581868640148 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.06585365853658537 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.12280701754385964 - nodes in this community are weakly interconnected._
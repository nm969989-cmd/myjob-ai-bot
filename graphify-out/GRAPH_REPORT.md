# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 316 nodes · 758 edges · 21 communities (14 shown, 6 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `70eca7ba`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- job_radar.py
- save_chat_id
- bot_optimizer.py
- run_playwright_apply
- main.py
- scrape_single_channel
- instahyre_engine.py
- enterprise_adapters.py
- daily_report_loop
- ResumePDF
- analyze_form_with_gemini
- load_chat_id
- generate_dynamic_resume
- bypass_blog_redirect
- LoggerWriter
- api_force_scan
- api_radar
- api_run_radar
- enforce_bot_security_profile
- FPDF

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 32 edges
2. `save_chat_id()` - 31 edges
3. `admin_only()` - 30 edges
4. `scrape_single_channel()` - 23 edges
5. `run_radar()` - 21 edges
6. `classify_location()` - 14 edges
7. `load_chat_id()` - 14 edges
8. `safe_load_json()` - 13 edges
9. `run_all_tests()` - 13 edges
10. `_make_job()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `api_miniapp_jobs()` --calls--> `classify_location()`  [INFERRED]
  main.py → job_radar.py
- `check_job_match()` --calls--> `classify_location()`  [INFERRED]
  main.py → job_radar.py
- `radar_loop()` --calls--> `run_radar()`  [INFERRED]
  main.py → job_radar.py
- `api_scan_inbox()` --calls--> `scan_for_interview_invites()`  [INFERRED]
  main.py → imap_handler.py
- `extract_structured_channel_job_details()` --calls--> `classify_location()`  [INFERRED]
  main.py → job_radar.py

## Import Cycles
- None detected.

## Communities (21 total, 6 thin omitted)

### Community 0 - "job_radar.py"
Cohesion: 0.10
Nodes (49): calculate_skill_match_score(), extract_hr_email(), extract_job_salary(), Extracts CTC, package, salary, or internship stipend from unstructured text.…, Extracts recruiter or HR email address from unstructured job postings. Filters…, Computes an ATS-style skill match score (0-100%) by comparing keywords found in…, GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, _api_request() (+41 more)

### Community 1 - "save_chat_id"
Cohesion: 0.10
Nodes (46): admin_only(), clear_qa(), command_scan_inbox(), get_authorized_chat_ids(), handle_auto_apply(), handle_qa_button(), is_authorized(), load_channel_status() (+38 more)

### Community 2 - "bot_optimizer.py"
Cohesion: 0.10
Nodes (35): apply_rag_memory_fallback(), format_deadlines_radar_report(), format_national_drives_report(), format_single_drive_detail(), generate_fast_interview_cheat_sheet(), generate_linkedin_outreach_note(), generate_market_analytics_report(), get_all_drive_deadlines() (+27 more)

### Community 3 - "run_playwright_apply"
Cohesion: 0.08
Nodes (33): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, _sanitize_latin1(), send_cold_email_if_found(), sync_to_notion(), apply_regex_fallback() (+25 more)

### Community 4 - "main.py"
Cohesion: 0.13
Nodes (25): api_add_channel(), api_download_log(), api_download_profile(), api_download_qa(), api_health_check(), api_mark_crm(), api_miniapp_jobs(), api_pause() (+17 more)

### Community 5 - "scrape_single_channel"
Cohesion: 0.11
Nodes (26): check_for_interviews(), fetch_target_page_job_meta(), is_sleep_time(), is_social_or_promo_link(), job_monitor_loop(), load_applied_jobs(), log_job(), manual_radar_scan() (+18 more)

### Community 6 - "instahyre_engine.py"
Cohesion: 0.15
Nodes (18): Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, wait_for_otp(), coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes() (+10 more)

### Community 7 - "enterprise_adapters.py"
Cohesion: 0.18
Nodes (14): execute_greenhouse_adapter(), execute_lever_adapter(), execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Highly specialized adapter for Lever (jobs.lever.co). Lever is a predictable…, Saves generated credentials to a secure local vault., Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).… (+6 more)

### Community 8 - "daily_report_loop"
Cohesion: 0.18
Nodes (11): api_status(), cleanup_system_resources(), daily_report_loop(), load_retry_queue(), load_weekly_stats(), Live stats for dashboard widgets., Sends a daily summary at 9 AM and a weekly report every Monday., Kills orphaned browser processes and cleans cache to prevent resource leaks. (+3 more)

### Community 9 - "ResumePDF"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

### Community 10 - "analyze_form_with_gemini"
Cohesion: 0.25
Nodes (8): analyze_form_with_gemini(), api_rotate_key(), check_job_match(), get_groq_client(), Strictly filters for FRESHER / ENTRY-LEVEL ENGINEERING jobs only. Returns…, Uses Gemini API to map form fields to the user's profile data, leveraging both…, rotate_gemini_key(), rotate_groq_key()

### Community 11 - "load_chat_id"
Cohesion: 0.29
Nodes (7): api_debug_bot(), api_instahyre(), api_telegram_test(), home(), load_chat_id(), Sends a test message to Telegram to verify bot connectivity., Triggers the Instahyre mass-applier engine from the dashboard.

### Community 12 - "generate_dynamic_resume"
Cohesion: 0.40
Nodes (4): FPDF, generate_dynamic_resume(), Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF., ResumePDF

### Community 13 - "bypass_blog_redirect"
Cohesion: 0.40
Nodes (5): api_manual_apply(), bypass_blog_redirect(), clean_tracking_params(), Strips Google Analytics/Social Media tracking parameters to keep URLs clean and…, Intelligently finds the real company application link inside ad-heavy…

## Knowledge Gaps
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_playwright_apply()` connect `run_playwright_apply` to `save_chat_id`, `bot_optimizer.py`, `main.py`, `scrape_single_channel`, `instahyre_engine.py`, `enterprise_adapters.py`, `analyze_form_with_gemini`, `load_chat_id`, `generate_dynamic_resume`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `run_radar()` connect `job_radar.py` to `bot_optimizer.py`, `run_playwright_apply`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `extract_hr_email()` connect `job_radar.py` to `bot_optimizer.py`, `main.py`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Should `job_radar.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0988235294117647 - nodes in this community are weakly interconnected._
- **Should `save_chat_id` be split into smaller, more focused modules?**
  _Cohesion score 0.10338164251207729 - nodes in this community are weakly interconnected._
- **Should `bot_optimizer.py` be split into smaller, more focused modules?**
  _Cohesion score 0.1021021021021021 - nodes in this community are weakly interconnected._
- **Should `run_playwright_apply` be split into smaller, more focused modules?**
  _Cohesion score 0.08095238095238096 - nodes in this community are weakly interconnected._
# Graph Report - Telegram_Job_Bot  (2026-09-27)

## Corpus Check
- 30 files · ~61,503 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 272 nodes · 631 edges · 11 communities (9 shown, 1 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 17 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Web API & Redirect Bypass
- AI Playwright Form Automation
- Multi-Platform Job Radar
- Telegram Bot Command UI
- Channel Scraper & Job Dispatcher
- Supervisor & Polling Lifecycle
- Instahyre Engine & Mimicry
- Enterprise ATS Adapters
- PDF Resume Generation
- Stream Logging Subsystem

## God Nodes (most connected - your core abstractions)
1. `run_playwright_apply()` - 31 edges
2. `admin_only()` - 27 edges
3. `save_chat_id()` - 26 edges
4. `scrape_single_channel()` - 20 edges
5. `run_radar()` - 17 edges
6. `classify_location()` - 15 edges
7. `load_chat_id()` - 14 edges
8. `safe_load_json()` - 13 edges
9. `run_instahyre_mass_apply()` - 11 edges
10. `safe_save_json()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `run_instahyre_mass_apply()` --calls--> `wait_for_otp()`  [EXTRACTED]
  instahyre_engine.py → bot_features.py
- `scrape_single_channel()` --calls--> `sync_to_notion()`  [EXTRACTED]
  main.py → bot_features.py
- `run_playwright_apply()` --calls--> `execute_lever_adapter()`  [EXTRACTED]
  main.py → enterprise_adapters.py
- `run_playwright_apply()` --calls--> `execute_greenhouse_adapter()`  [EXTRACTED]
  main.py → enterprise_adapters.py
- `run_playwright_apply()` --calls--> `execute_workday_adapter()`  [EXTRACTED]
  main.py → enterprise_adapters.py

## Import Cycles
- None detected.

## Communities (11 total, 1 thin omitted)

### Community 0 - "Web API & Redirect Bypass"
Cohesion: 0.06
Nodes (56): analyze_form_with_gemini(), api_add_channel(), api_debug_bot(), api_download_log(), api_download_profile(), api_download_qa(), api_force_scan(), api_health_check() (+48 more)

### Community 1 - "AI Playwright Form Automation"
Cohesion: 0.07
Nodes (38): CoverLetterPDF, generate_dynamic_cover_letter(), generate_interview_prep(), FPDF, Actively listens to the Gmail inbox for a new verification code/OTP. Extracts…, _sanitize_latin1(), send_cold_email_if_found(), sync_to_notion() (+30 more)

### Community 2 - "Multi-Platform Job Radar"
Cohesion: 0.12
Nodes (40): GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine. Optimized for…, _api_request(), classify_location(), clean_html(), escape_md(), is_social_or_promo_link(), _keyword_match(), load_seen_jobs() (+32 more)

### Community 3 - "Telegram Bot Command UI"
Cohesion: 0.11
Nodes (40): callback_query_handler, admin_only(), clear_qa(), command_scan_inbox(), handle_auto_apply(), handle_qa_button(), home(), load_channel_status() (+32 more)

### Community 4 - "Channel Scraper & Job Dispatcher"
Cohesion: 0.11
Nodes (27): check_for_interviews(), extract_structured_channel_job_details(), fetch_target_page_job_meta(), handle_button(), is_social_or_promo_link(), job_monitor_loop(), load_applied_jobs(), log_job() (+19 more)

### Community 5 - "Supervisor & Polling Lifecycle"
Cohesion: 0.12
Nodes (18): api_status(), cleanup_system_resources(), daily_report_loop(), get_authorized_chat_ids(), is_authorized(), is_sleep_time(), load_retry_queue(), load_weekly_stats() (+10 more)

### Community 6 - "Instahyre Engine & Mimicry"
Cohesion: 0.17
Nodes (16): coffee_break(), human_distraction(), human_mouse_wandering(), human_scroll(), human_text_highlighting(), human_typing_with_mistakes(), Simulates a human scrolling up and down the page while reading., Autonomous engine to log into Instahyre and mass-apply to jobs using human-… (+8 more)

### Community 7 - "Enterprise ATS Adapters"
Cohesion: 0.19
Nodes (12): execute_greenhouse_adapter(), execute_lever_adapter(), execute_workday_adapter(), fetch_otp_from_email(), generate_secure_password(), Saves generated credentials to a secure local vault., Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).…, Generates a highly secure password that passes all enterprise checks. (+4 more)

### Community 8 - "PDF Resume Generation"
Cohesion: 0.32
Nodes (4): build_resume(), FPDF, Generate a professional PDF resume from profile.json using fpdf2. Run: python…, ResumePDF

## Knowledge Gaps
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_radar()` connect `Multi-Platform Job Radar` to `Web API & Redirect Bypass`, `AI Playwright Form Automation`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `classify_location()` connect `Multi-Platform Job Radar` to `Web API & Redirect Bypass`, `Channel Scraper & Job Dispatcher`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `run_instahyre_mass_apply()` connect `Instahyre Engine & Mimicry` to `Web API & Redirect Bypass`, `AI Playwright Form Automation`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Should `Web API & Redirect Bypass` be split into smaller, more focused modules?**
  _Cohesion score 0.05902980713033314 - nodes in this community are weakly interconnected._
- **Should `AI Playwright Form Automation` be split into smaller, more focused modules?**
  _Cohesion score 0.06968641114982578 - nodes in this community are weakly interconnected._
- **Should `Multi-Platform Job Radar` be split into smaller, more focused modules?**
  _Cohesion score 0.1207897793263647 - nodes in this community are weakly interconnected._
- **Should `Telegram Bot Command UI` be split into smaller, more focused modules?**
  _Cohesion score 0.1141025641025641 - nodes in this community are weakly interconnected._
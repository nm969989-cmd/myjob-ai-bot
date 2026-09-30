---
type: "query"
date: "2026-09-30T17:57:42.815523+00:00"
question: "Why does run_radar connect across 7 separate communities?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_radar()", "is_job_link_alive()", "send_radar_telegram()"]
---

# Q: Why does run_radar connect across 7 separate communities?

## Answer

run_radar() in job_radar.py:L1379 acts as the master dispatch orchestrator connecting 7 platforms (Adzuna, Unstop, Foundit, Remotive, Jobicy, Arbeitnow, RemoteOK), enrichers in bot_optimizer.py (is_job_link_alive, extract_job_salary, calculate_skill_match_score), deduplication state (load_seen_jobs, mark_seen), and the TN Job Pipeline (send_radar_telegram, _priority_sort_key).

## Outcome

- Signal: useful

## Source Nodes

- run_radar()
- is_job_link_alive()
- send_radar_telegram()
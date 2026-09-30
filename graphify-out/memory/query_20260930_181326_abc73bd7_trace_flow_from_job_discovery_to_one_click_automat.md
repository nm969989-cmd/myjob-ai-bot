---
type: "query"
date: "2026-09-30T18:13:26.794048+00:00"
question: "Trace flow from job discovery to one-click automatic application"
contributor: "graphify"
outcome: "useful"
source_nodes: ["run_radar()", "run_playwright_apply()", "minify_form_html()", "analyze_form_with_gemini()"]
---

# Q: Trace flow from job discovery to one-click automatic application

## Answer

Jobs discovered by run_radar() in job_radar.py are sent to Telegram with 1-click apply buttons. Tapping the button routes to application_worker() which executes run_playwright_apply() in main.py. The pipeline applies human_mimicry and bezier mouse moves, generates dynamic ATS-tailored PDFs via generate_dynamic_resume(), minifies the form HTML via minify_form_html(), resolves screening questions using qa_memory and analyze_form_with_gemini(), submits, and confirms via verify_page_with_ai().

## Outcome

- Signal: useful

## Source Nodes

- run_radar()
- run_playwright_apply()
- minify_form_html()
- analyze_form_with_gemini()
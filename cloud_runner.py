# -*- coding: utf-8 -*-
"""
GitHub Actions Cloud Runner — High-Speed 100% Cloud Job Engine.
Optimized for GitHub Actions execution with intelligent timeouts, multi-platform radar,
channel scraper, auto-applying via Playwright, and real-time Telegram status reports.
"""
import os
import sys
import time
import json
import re
from datetime import datetime
from dotenv import load_dotenv

# Mark script start time
START_TIME = time.time()
MAX_EXECUTION_SECONDS = 3 * 60  # 3-minute soft budget so GitHub Actions completes quickly

# Ensure environment is loaded
load_dotenv(override=True)

# Ensure UTF-8 output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

print("=" * 60)
print(f"🚀 GITHUB ACTIONS CLOUD RUNNER — {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 60)

import telebot
from job_radar import run_radar, escape_md

# Load credentials with smart fallbacks
token = os.getenv("TELEGRAM_TOKEN", "").strip() or "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4"
chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not chat_id and os.path.exists("chat_id.json"):
    try:
        with open("chat_id.json", "r") as f:
            data = json.load(f)
            chat_id = str(data.get("chat_id", "7607565831")).strip()
    except Exception:
        pass

if not chat_id:
    chat_id = "7607565831"

bot = telebot.TeleBot(token, parse_mode=None)

radar_jobs_count = 0
channels_scanned = 0
channel_jobs_found = 0
channel_attempts = 0
follow_up_count = 0

# -------------------------------------------------------------
# STEP 1: Multi-Platform Job Radar Scan
# -------------------------------------------------------------
print("\n📡 [1/3] Running Multi-Platform Job Radar...")
try:
    new_radar_jobs = run_radar()
    radar_jobs_count = len(new_radar_jobs) if new_radar_jobs else 0
    print(f"✅ Job Radar scan finished. Found {radar_jobs_count} new opportunities.")
except Exception as e:
    print(f"⚠️ Radar Scan error: {e}")

# -------------------------------------------------------------
# STEP 2: Telegram Channel Scrape & Playwright Auto-Apply
# -------------------------------------------------------------
print("\n📢 [2/3] Scraping Telegram Channels & Auto-Applying...")
try:
    from main import scrape_single_channel, load_applied_jobs, TARGET_CHANNELS
    
    applied_jobs = load_applied_jobs()
    target_channel_env = os.getenv("TARGET_CHANNEL", "JobSkull").strip()
    channels_to_scan = list(dict.fromkeys([target_channel_env] + list(TARGET_CHANNELS)))
    
    for ch in channels_to_scan:
        # Check time budget: if remaining time is low, exit early to allow logs and notifications
        elapsed = time.time() - START_TIME
        if elapsed > MAX_EXECUTION_SECONDS:
            print(f"⏱️ Time budget reached ({int(elapsed)}s). Concluding channel scans gracefully.")
            break
            
        if ch:
            clean_ch = ch.replace("@", "").strip()
            print(f"  🔍 Checking @{clean_ch}...")
            try:
                found, attempts = scrape_single_channel(clean_ch, applied_jobs, chat_id, max_jobs=2)
                channels_scanned += 1
                channel_jobs_found += (found or 0)
                channel_attempts += (attempts or 0)
                if channel_attempts >= 4:
                    print("  🎯 Reached max applications limit for this cycle. Moving to summary.")
                    break
            except Exception as ch_err:
                print(f"  ⚠️ Error scanning @{clean_ch}: {ch_err}")
                
except Exception as e:
    print(f"⚠️ Channel Scraper error: {e}")

# -------------------------------------------------------------
# STEP 3: Check Follow-up Reminders (Ghosting Preventer)
# -------------------------------------------------------------
print("\n👻 [3/3] Checking for 7-day follow-up applications...")
try:
    if os.path.exists("applied_jobs_log.csv") and chat_id:
        import csv
        with open("applied_jobs_log.csv", "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        
        now = datetime.now()
        follow_ups = []
        for i in range(1, len(rows)):
            row = rows[i]
            if len(row) >= 4 and "Applied" in row[3] and "Followed Up" not in row[3]:
                date_str = row[0][:10]
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if (now - dt).days == 7:
                        follow_ups.append((i, row[1], row[2]))
                except Exception:
                    pass
                
        if follow_ups:
            follow_up_count = len(follow_ups)
            msg = f"👻 *GHOSTING PREVENTER ALERT*\nIt has been 7 days since you applied to {follow_up_count} jobs.\n\n"
            for idx, job_title, url in follow_ups[:8]:
                msg += f"💼 *{escape_md(job_title[:35])}*\n🔗 [Job Link]({url})\n"
                if len(rows[idx]) >= 5:
                    rows[idx][4] = "Followed Up"
                else:
                    rows[idx].append("Followed Up")
            msg += "\n📝 _Consider reaching out to the recruiter on LinkedIn or sending a quick follow-up email!_"
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown", disable_web_page_preview=True)
                with open("applied_jobs_log.csv", "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            except Exception as tg_e:
                print(f"⚠️ Failed to send ghosting alert: {tg_e}")
except Exception as e:
    print(f"⚠️ Follow-up check error: {e}")

# -------------------------------------------------------------
# STEP 4: Cloud Status Update to Telegram (Always sent!)
# -------------------------------------------------------------
total_elapsed = int(time.time() - START_TIME)
print(f"\n📊 Cycle summary: Duration={total_elapsed}s, Radar={radar_jobs_count}, Channels={channels_scanned}, New={channel_jobs_found}, Applied={channel_attempts}")

try:
    status_msg = (
        f"☁️ *GitHub Actions Cloud Cycle Complete*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Time: {datetime.now().strftime('%d %b %Y, %I:%M %p UTC')}\n"
        f"⏱️ Duration: *{total_elapsed}s*\n"
        f"📡 Radar Jobs Found: *{radar_jobs_count}*\n"
        f"📢 Channels Scanned: *{channels_scanned}*\n"
        f"🎯 Auto-Applied Attempts: *{channel_attempts}*\n"
        f"👻 7-Day Follow-ups: *{follow_up_count}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 _100% Cloud Autonomous (No PC Required)_"
    )
    bot.send_message(chat_id, status_msg, parse_mode="Markdown", disable_web_page_preview=True)
    print("✅ Status summary sent to Telegram.")
except Exception as e:
    print(f"⚠️ Failed to send status summary: {e}")

print("\n" + "=" * 60)
print(f"✅ GITHUB ACTIONS CYCLE COMPLETE in {total_elapsed}s! Exiting cleanly.")
print("=" * 60)
sys.exit(0)

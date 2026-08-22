# -*- coding: utf-8 -*-
"""
GitHub Actions Cloud Runner — High Performance Single-Run Automation.
Runs every cycle in GitHub Actions (16GB RAM Runner), processes new jobs, applies, and exits cleanly.
"""
import os
import sys
import time
import json
import re
from datetime import datetime
from dotenv import load_dotenv

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

# Import bot modules
from job_radar import run_radar, escape_md
import telebot

# Load secrets from environment
token = os.getenv("TELEGRAM_TOKEN", "").strip()
chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
target_channel = os.getenv("TARGET_CHANNEL", "JobSkull").strip()

if not token:
    print("❌ ERROR: TELEGRAM_TOKEN secret is missing in GitHub Actions!")
    sys.exit(1)

if not chat_id and os.path.exists("chat_id.json"):
    try:
        with open("chat_id.json", "r") as f:
            data = json.load(f)
            chat_id = data.get("chat_id")
    except Exception:
        pass

bot = telebot.TeleBot(token, parse_mode=None)

# -------------------------------------------------------------
# STEP 1: Multi-Platform Job Radar Scan
# -------------------------------------------------------------
print("\n📡 [1/3] Running Multi-Platform Job Radar...")
try:
    new_radar_jobs = run_radar()
    print(f"✅ Job Radar scan finished. Found {len(new_radar_jobs)} new opportunities.")
except Exception as e:
    print(f"⚠️ Radar Scan error: {e}")

# -------------------------------------------------------------
# STEP 2: Telegram Channel Scrape & Ad-Bypass
# -------------------------------------------------------------
print(f"\n📢 [2/3] Scraping Telegram Channel: @{target_channel}...")
try:
    from main import check_telegram_channel, TARGET_CHANNELS
    
    channels_to_scan = list(set([target_channel] + list(TARGET_CHANNELS)))
    for ch in channels_to_scan:
        if ch:
            print(f"  🔍 Checking @{ch.replace('@', '')}...")
            try:
                check_telegram_channel(ch.replace("@", ""))
            except Exception as ch_err:
                print(f"  ⚠️ Error scanning @{ch}: {ch_err}")
                
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
                except:
                    pass
                
        if follow_ups:
            msg = f"👻 *GHOSTING PREVENTER ALERT*\nIt has been 7 days since you applied to {len(follow_ups)} jobs.\n\n"
            for idx, job_title, url in follow_ups[:8]:
                msg += f"💼 *{escape_md(job_title[:35])}*\n🔗 [Job Link]({url})\n"
                if len(rows[idx]) >= 5:
                    rows[idx][4] = "Followed Up"
                else:
                    rows[idx].append("Followed Up")
            msg += "\n📝 _Consider reaching out to the recruiter on LinkedIn or sending a quick follow-up email!_"
            try:
                bot.send_message(chat_id, msg, parse_mode="Markdown", disable_web_page_preview=True)
                # Save updated follow-up status
                with open("applied_jobs_log.csv", "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            except Exception as tg_e:
                print(f"⚠️ Failed to send ghosting alert: {tg_e}")
except Exception as e:
    print(f"⚠️ Follow-up check error: {e}")

print("\n" + "=" * 60)
print("✅ GITHUB ACTIONS CYCLE COMPLETE! Exiting cleanly.")
print("=" * 60)
sys.exit(0)

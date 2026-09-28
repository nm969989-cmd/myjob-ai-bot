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
import random
from datetime import datetime
from dotenv import load_dotenv

# Mark script start time
START_TIME = time.time()
MAX_EXECUTION_SECONDS = 12 * 60  # 12-minute budget (well within GitHub Actions 20-min timeout)

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

# Load credentials with smart sanitization
_raw_token = os.getenv("TELEGRAM_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
token = str(_raw_token).strip().strip('"').strip("'")
if token.lower().startswith("bot"):
    token = token[3:]

_raw_chat = os.getenv("TELEGRAM_CHAT_ID", "")
chat_id = str(_raw_chat).strip().strip('"').strip("'")
if not chat_id and os.path.exists("chat_id.json"):
    try:
        with open("chat_id.json", "r") as f:
            data = json.load(f)
            chat_id = str(data.get("chat_id", "")).strip()
    except Exception:
        pass

bot = telebot.TeleBot(token, parse_mode=None) if token else None

radar_jobs_count = 0
channels_scanned = 0
channel_jobs_found = 0
channel_attempts = 0
follow_up_count = 0
new_radar_jobs = []

# -------------------------------------------------------------
# STEP 1: Multi-Platform Job Radar Scan & Direct Telegram Dispatch
# -------------------------------------------------------------
print("\n📡 [1/3] Running Multi-Platform Job Radar...")
try:
    from main import load_applied_jobs, save_applied_job, load_profile
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    import html
    import urllib.parse

    applied_jobs = load_applied_jobs()
    profile = load_profile()

    new_radar_jobs = run_radar() or []
    radar_jobs_count = len(new_radar_jobs)
    print(f"✅ Job Radar scan finished. Found {radar_jobs_count} new opportunities.")

    # Dispatch top fresh radar opportunities directly to Telegram
    if new_radar_jobs and bot and chat_id:
        radar_alerts_sent = 0
        print("🚀 Dispatching top verified Radar opportunities to Telegram...")
        for job in new_radar_jobs:
            if radar_alerts_sent >= 5:  # Send up to 5 top fresh opportunities per cycle
                break
            j_link = job.get("link") or job.get("raw_link")
            if not j_link or j_link in applied_jobs:
                continue

            try:
                import main
                unwrapped = main.bypass_blog_redirect(j_link)
                if unwrapped:
                    j_link = unwrapped
            except Exception:
                pass

            j_title = str(job.get("title", "Software Engineer")).strip()
            j_company = str(job.get("company", "Verified Company")).strip()
            j_location = str(job.get("location", "India (PAN India)")).strip()
            j_source = str(job.get("source", "Multi-Platform Radar")).strip()
            is_tn = job.get("is_tamil_nadu", False)

            banner = "🌟 <b>TAMIL NADU PRIORITY</b> 🇮🇳" if is_tn else "📡 <b>VERIFIED RADAR MATCH</b> 🇮🇳"

            share_text = urllib.parse.quote(f"🚀 Job Alert: {j_company} - {j_title}\nApply Link: {j_link}")
            share_url = f"https://t.me/share/url?url={urllib.parse.quote(j_link)}&text={share_text}"

            card = (
                f"{banner}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏢 <b>{html.escape(j_company)}</b> • <i>{html.escape(j_title)}</i>\n\n"
                f"📍 <b>Location:</b> {html.escape(j_location)}\n"
                f"📡 <b>Platform:</b> {html.escape(j_source)}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )

            kb = InlineKeyboardMarkup()
            kb.row(
                InlineKeyboardButton("🚀 Direct Apply (Official)", url=j_link)
            )
            kb.row(
                InlineKeyboardButton("📤 Share Alert", url=share_url)
            )

            try:
                bot.send_message(chat_id, card, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
                applied_jobs.add(j_link)
                save_applied_job(j_link)
                radar_alerts_sent += 1
                channel_jobs_found += 1
                print(f"  [Radar Alert Sent] {j_company} - {j_title}")
                time.sleep(1.5)
            except Exception as send_err:
                print(f"  ⚠️ Failed to send radar job: {send_err}")
except Exception as e:
    print(f"⚠️ Radar Scan error: {e}")

# -------------------------------------------------------------
# STEP 2: Telegram Channel Scrape & Direct Link Extraction
# -------------------------------------------------------------
print("\n📢 [2/3] Scraping Telegram Channels & Extracting Direct Links...")
try:
    from main import scrape_single_channel, load_applied_jobs, TARGET_CHANNELS

    applied_jobs = load_applied_jobs()
    priority_channels = ["KickCharm", "OffCampusJobs4u", "Freshershunt", "fresheroffcampus", "JobSkull", "Foundthejob", "chennaijobsofficial", "tech_jobs_india", "freshersvoice", "engineering_jobs_india", "placementjobs", "DailyJobs4You", "jobopenings_india"]
    
    # Shuffle priority channels so no single slow channel blocks others
    random.shuffle(priority_channels)
    raw_env_channels = os.getenv("TARGET_CHANNEL", "")
    env_channels = [c.strip().replace("@", "") for c in raw_env_channels.split(",") if c.strip()]
    channels_to_scan = list(dict.fromkeys(priority_channels + env_channels + list(TARGET_CHANNELS)))

    for ch in channels_to_scan:
        # Check overall time budget
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
print(f"\n📊 Cycle summary: Duration={total_elapsed}s, Radar={radar_jobs_count}, Channels={channels_scanned}, Direct Alerts={channel_jobs_found}")

try:
    tn_radar_count = sum(1 for j in new_radar_jobs if j.get('is_tamil_nadu', False)) if new_radar_jobs else 0
    status_msg = (
        f"☁️ *GitHub Actions Cloud Cycle Complete*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🕒 Time: {datetime.now().strftime('%d %b %Y, %I:%M %p UTC')}\n"
        f"⏱️ Duration: *{total_elapsed}s*\n"
        f"📡 Radar Jobs (India): *{radar_jobs_count}*\n"
        f"🌟 Tamil Nadu Priority: *{tn_radar_count}* jobs\n"
        f"📢 Channels Scanned: *{channels_scanned}*\n"
        f"🚀 Direct Job Alerts Sent: *{channel_jobs_found}*\n"
        f"👻 7-Day Follow-ups: *{follow_up_count}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 _Search & Direct Link Extraction Mode Active_"
    )
    if bot and chat_id:
        bot.send_message(chat_id, status_msg, parse_mode="Markdown", disable_web_page_preview=True)
        print("✅ Status summary sent to Telegram.")
except Exception as e:
    print(f"⚠️ Failed to send status summary: {e}")

print("\n" + "=" * 60)
print(f"✅ GITHUB ACTIONS CYCLE COMPLETE in {total_elapsed}s! Exiting cleanly.")
print("=" * 60)
sys.exit(0)

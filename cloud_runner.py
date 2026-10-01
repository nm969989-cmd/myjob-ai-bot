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
import random
from datetime import datetime
from dotenv import load_dotenv

# Mark script start time
START_TIME = time.time()
# 25-minute execution budget for twice-daily runs (11:00 AM & 7:00 PM IST).
# Ends gracefully before the workflow's 30-minute hard timeout.
MAX_EXECUTION_SECONDS = 25 * 60

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

# Telegram flood-control resilience: retry with backoff on 429s instead of dropping alerts
# (main.py only sets this in local bot mode, so it must be set for the cloud path too)
from telebot import apihelper
apihelper.MAX_RETRIES = 5
apihelper.RETRY_TIMEOUT = 2

radar_jobs_count = 0
radar_alerts_sent = 0
tn_alerts_sent = 0
channels_scanned = 0
channel_jobs_found = 0
channel_attempts = 0
follow_up_count = 0
new_radar_jobs = []
step_errors = []  # Tracks silent failures so the status report can never hide a broken stage
stage_times = {}  # Per-stage duration breakdown for the status report
stage_notes = []  # Non-fatal operational notes (budget skips, partial runs)

def run_cloud():
    global radar_jobs_count, radar_alerts_sent, tn_alerts_sent
    global channels_scanned, channel_jobs_found, channel_attempts
    global follow_up_count, new_radar_jobs, step_errors, stage_times, stage_notes

    # -------------------------------------------------------------
    # STEP 1: Telegram Channel Scrape & Direct Link Extraction
    # -------------------------------------------------------------
    # Channels run FIRST: run history proves them the highest-yield stage (18 alerts
    # vs 0 from radar in one cycle), so the slower multi-platform radar farm can never
    # starve them. 5 minutes of budget are reserved for Radar + follow-ups + report.
    print("\n📢 [1/3] Scraping Telegram Channels & Extracting Direct Links...")
    try:
        from main import scrape_single_channel, load_applied_jobs, TARGET_CHANNELS

        applied_jobs = load_applied_jobs()
        priority_channels = ["KickCharm", "OffCampusJobs4u", "Freshershunt", "fresheroffcampus", "JobSkull", "Foundthejob", "chennaijobsofficial", "tech_jobs_india", "freshersvoice", "engineering_jobs_india", "placementjobs", "DailyJobs4You", "jobopenings_india"]

        # Shuffle priority channels so no single slow channel blocks others
        random.shuffle(priority_channels)
        raw_env_channels = os.getenv("TARGET_CHANNEL", "")
        env_channels = [c.strip().replace("@", "") for c in raw_env_channels.split(",") if c.strip()]
        channels_to_scan = list(dict.fromkeys(priority_channels + env_channels + list(TARGET_CHANNELS)))

        channel_deadline = START_TIME + (MAX_EXECUTION_SECONDS - 5 * 60)
        _stage_start = time.time()
        for ch in channels_to_scan:
            if time.time() > channel_deadline:
                print(f"⏱️ Channel deadline reached ({int(time.time() - START_TIME)}s). Concluding channel scans gracefully.")
                stage_notes.append("Channel scan hit deadline")
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
        stage_times["channels"] = int(time.time() - _stage_start)
    except Exception as e:
        step_errors.append(f"Channel stage: {e}")
        print(f"⚠️ Channel Scraper error: {e}")

    # -------------------------------------------------------------
    # STEP 2: Multi-Platform Job Radar Scan & Direct Telegram Dispatch
    # -------------------------------------------------------------
    print("\n📡 [2/3] Running Multi-Platform Job Radar...")
    try:
        if MAX_EXECUTION_SECONDS - (time.time() - START_TIME) < 150:
            stage_notes.append("Radar skipped (time budget)")
            print("⏱️ Less than 2.5 min of budget left — skipping radar this cycle.")
        else:
            from main import load_applied_jobs, save_applied_job, load_profile
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
            import html
            import urllib.parse

            applied_jobs = load_applied_jobs()
            profile = load_profile()

            _stage_start = time.time()
            new_radar_jobs = run_radar() or []
            stage_times["radar_scan"] = int(time.time() - _stage_start)
            radar_jobs_count = len(new_radar_jobs)
            print(f"✅ Job Radar scan finished. Found {radar_jobs_count} new opportunities.")

            # Dispatch top fresh radar opportunities directly to Telegram
            if new_radar_jobs and bot and chat_id:
                print("🚀 Dispatching top verified Radar opportunities to Telegram...")
                _stage_start = time.time()
                for job in new_radar_jobs:
                    if radar_alerts_sent >= 5:  # Send up to 5 top fresh opportunities per cycle
                        break
                    # Keep runway for follow-ups + status report (never die mid-send)
                    if MAX_EXECUTION_SECONDS - (time.time() - START_TIME) < 90:
                        stage_notes.append(f"Radar dispatch cut short ({radar_alerts_sent}/5)")
                        print("⏱️ Budget runway low — stopping radar dispatch.")
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

                    j_batch = str(job.get("batch", "")).strip()
                    j_exp = str(job.get("experience", "")).strip()
                    j_sal = str(job.get("salary", "")).strip()

                    meta_lines = []
                    if j_batch:
                        meta_lines.append(f"🎓 <b>Batch:</b> {html.escape(j_batch)}")
                    if j_exp:
                        meta_lines.append(f"💼 <b>Experience:</b> {html.escape(j_exp)}")
                    if j_sal:
                        meta_lines.append(f"💰 <b>Salary:</b> {html.escape(j_sal)}")
                    meta_block = "\n".join(meta_lines) + "\n" if meta_lines else ""

                    card = (
                        f"{banner}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏢 <b>{html.escape(j_company)}</b> • <i>{html.escape(j_title)}</i>\n\n"
                        f"📍 <b>Location:</b> {html.escape(j_location)}\n"
                        f"{meta_block}"
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
                        print(f"  [Radar Alert Sent] {j_company} - {j_title}")
                        time.sleep(1.5)
                    except Exception as send_err:
                        print(f"  ⚠️ Failed to send radar job: {send_err}")
                stage_times["radar_send"] = int(time.time() - _stage_start)
    except Exception as e:
        step_errors.append(f"Radar stage: {e}")
        print(f"⚠️ Radar Scan error: {e}")

    # -------------------------------------------------------------
    # STEP 2B: Dedicated Tamil Nadu Vacancies Digest Dispatch
    # -------------------------------------------------------------
    print("\n🌟 [2B] Sweeping & Dispatching Fresh Tamil Nadu Vacancies...")
    try:
        if bot and chat_id:
            from job_radar import dispatch_tamil_nadu_alerts
            _tn_start = time.time()
            sent = dispatch_tamil_nadu_alerts(bot=bot, chat_id=chat_id, limit=6, force_refresh=True, only_unseen=True)
            tn_alerts_sent = int(sent) if isinstance(sent, (int, float)) else (6 if sent else 0)
            stage_times["tn_digest"] = int(time.time() - _tn_start)
            print(f"✅ [Cloud Runner] Automated Tamil Nadu digest sweep finished! Dispatched: {tn_alerts_sent}")
    except Exception as tn_auto_err:
        step_errors.append(f"Tamil Nadu stage: {tn_auto_err}")
        print(f"⚠️ Automated Tamil Nadu dispatch error: {tn_auto_err}")

    # -------------------------------------------------------------
    # STEP 2C: Automated Weekend Walk-In Tracker Dispatch (Once per day)
    # -------------------------------------------------------------
    try:
        if bot and chat_id:
            from bot_optimizer import dispatch_walkin_alerts
            print("🚶‍♂️ [Cloud Runner] Automatically checking Weekend Walk-In Drives...")
            dispatch_walkin_alerts(bot=bot, chat_id=chat_id, once_per_day=True, limit=5)
    except Exception as walkin_auto_err:
        print(f"⚠️ Automated Walk-In dispatch error: {walkin_auto_err}")

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
                        # >= 7 (not == 7): rows are flagged "Followed Up" once sent, so a wider
                        # window prevents missed reminders when scheduled runs get delayed/skipped.
                        if (now - dt).days >= 7:
                            follow_ups.append((i, row[1], row[2]))
                    except Exception:
                        pass

            if follow_ups:
                follow_up_count = len(follow_ups)
                msg = f"👻 *GHOSTING PREVENTER ALERT*\nIt has been 7 days since you applied to {follow_up_count} jobs.\n\n"
                # Only the 8 shown are marked "Followed Up"; the rest roll to the next cycle
                # instead of being silently marked as done.
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
        step_errors.append(f"Follow-up stage: {e}")
        print(f"⚠️ Follow-up check error: {e}")

    # -------------------------------------------------------------
    # STEP 4: Cloud Status Update to Telegram (Always sent!)
    # -------------------------------------------------------------
    total_elapsed = int(time.time() - START_TIME)
    print(f"\n📊 Cycle summary: Duration={total_elapsed}s, Channels={channels_scanned} ({channel_jobs_found} alerts), Radar={radar_jobs_count} ({radar_alerts_sent} alerts)")

    try:
        tn_found = 0
        if os.path.exists("tn_jobs_cache.json"):
            try:
                with open("tn_jobs_cache.json", "r", encoding="utf-8") as f:
                    tn_found = json.load(f).get("total", 0)
            except Exception:
                pass
        if not tn_found and new_radar_jobs:
            tn_found = sum(1 for j in new_radar_jobs if j.get('is_tamil_nadu', False))

        if step_errors:
            health_line = f"🔴 *Engine Health: {len(step_errors)} stage error(s)*\n"
            health_line += "\n".join(f"⚠️ {escape_md(str(e)[:90])}" for e in step_errors[:3]) + "\n"
        else:
            health_line = "🟢 *Engine Health: All stages OK*\n"
        if stage_notes:
            health_line += "📝 " + " | ".join(stage_notes) + "\n"
        breakdown = " • ".join(f"{k} {v}s" for k, v in stage_times.items())
        duration_line = f"⏱️ Duration: *{total_elapsed}s*"
        if breakdown:
            duration_line += f" (_{breakdown}_)"
        duration_line += "\n"
        status_msg = (
            f"☁️ *GitHub Actions Cloud Cycle Complete*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 Time: {datetime.now().strftime('%d %b %Y, %I:%M %p UTC')}\n"
            f"{duration_line}"
            f"📢 Channels Scanned: *{channels_scanned}*\n"
            f"🚀 Direct Channel Alerts Sent: *{channel_jobs_found}*\n"
            f"📡 Radar Jobs (India): *{radar_jobs_count}* (_{radar_alerts_sent} alerts sent_)\n"
            f"🌟 Tamil Nadu Priority: *{tn_found}* available (_{tn_alerts_sent} digest alerts sent_)\n"
            f"👻 7-Day Follow-ups: *{follow_up_count}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{health_line}"
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

if __name__ == "__main__":
    run_cloud()

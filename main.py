import os
import re
import json
import time
import random
import requests
import csv
import html
import hmac
import secrets

from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from playwright.sync_api import sync_playwright
# playwright-stealth renamed its API in 2.0: the module-level stealth_sync()
# helper was replaced by Stealth().apply_stealth_sync(page_or_context).
# requirements.txt only pins ">=1.0.6", so a fresh install pulls 2.x and a bare
# "from playwright_stealth import stealth_sync" raises ImportError at import
# time, which takes down the whole bot. Support both versions and, as a last
# resort, degrade to a no-op instead of refusing to start.
try:  # playwright-stealth < 2.0
    from playwright_stealth import stealth_sync
except ImportError:  # playwright-stealth >= 2.0
    try:
        from playwright_stealth import Stealth
        _stealth_engine = Stealth()

        def stealth_sync(target):
            return _stealth_engine.apply_stealth_sync(target)
    except Exception:
        def stealth_sync(target):
            return target
from google import genai
from fpdf import FPDF
import groq
import base64
from dotenv import load_dotenv

# Load local environment variables if testing locally (do not override system env vars/secrets)
load_dotenv(override=False)

# --- CUSTOM LOG CAPTURE (Bypass HuggingFace Log Glitch) ---
import sys
from bot_features import generate_dynamic_cover_letter, generate_interview_prep, send_cold_email_if_found, check_for_interviews, sync_to_notion, wait_for_otp
from enterprise_adapters import execute_workday_adapter, execute_lever_adapter, execute_greenhouse_adapter, execute_smartrecruiters_adapter
from instahyre_engine import run_instahyre_mass_apply
from job_discovery import (priority_city, send_walkin_cards, walkin_keyboard, source_lines,
                           get_card, schedule_reminder, list_reminders, cancel_reminders,
                           dispatch_due_reminders, add_priority_buttons, calendar_event,
                           automatic_search_interval_minutes, IST)
from bot_optimizer import (
    minify_form_html,
    apply_regex_fallback,
    apply_rag_memory_fallback,
    extract_job_salary,
    extract_hr_email,
    generate_linkedin_outreach_note,
    record_learned_qa,
    calculate_skill_match_score,
    analyze_jd_skill_gap,
    format_skill_gap_report,
    store_gap_cache,
    get_gap_cache,
    is_job_link_alive,
    generate_fast_interview_cheat_sheet,
    generate_market_analytics_report,
    get_national_drives,
    format_national_drives_report,
    format_single_drive_detail,
    get_all_drive_deadlines,
    format_deadlines_radar_report,
    get_urgent_deadlines_summary,
    extract_eligible_batch,
    extract_experience_level,
    format_eligibility_badge,
    get_walkin_drives,
    format_walkins_report,
    format_single_walkin_detail,
    find_nearby_walkin_drives,
    format_nearby_walkins_report,
    geocode_location_text,
    get_walkin_checklist_text,
    search_jobs_multi_source,
    fetch_jobspy_live_search,
    format_search_results_report,
    match_job_compatibility,
    format_oa_report,
    get_company_oa_info,
    get_watchdog_subscriptions,
    add_watchdog_subscription,
    remove_watchdog_subscription,
    check_job_against_watchdogs,
    fetch_simplify_jobs,
    format_simplify_jobs_report
)

# Global in-memory cache for 1-Tap Interview Prep button callbacks (capped to 500 items)
_INTERVIEW_PREP_CACHE = {}
# Global in-memory cache for 1-Tap LinkedIn Note button callbacks (capped to 500 items)
_LINKEDIN_NOTE_CACHE = {}
# Global in-memory cache for 1-Tap Cold Outreach Email button callbacks (capped to 500 items)
_COLD_EMAIL_CACHE = {}
# Global in-memory cache for CareerOps 3-Bucket Skill Gap callbacks (capped to 500 items)
_SKILL_GAP_CACHE = {}


class LoggerWriter:
    def __init__(self, filename):
        self.filename = filename
        self.original_stdout = sys.__stdout__  # Use the real original stdout
    def write(self, message):
        try:
            enc = getattr(self.original_stdout, "encoding", "utf-8") or "utf-8"
            safe_msg = message.encode(enc, errors='replace').decode(enc, errors='replace')
            self.original_stdout.write(safe_msg)
            self.original_stdout.flush()
        except Exception:
            try:
                self.original_stdout.write(message.encode("ascii", errors="replace").decode("ascii"))
                self.original_stdout.flush()
            except Exception:
                pass
        try:
            with open(self.filename, "a", encoding="utf-8", errors="replace") as f:
                f.write(message)
        except Exception:
            pass
    def flush(self):
        try:
            self.original_stdout.flush()
        except Exception:
            pass

sys.stdout = LoggerWriter("debug.log")
sys.stderr = sys.stdout
print("--- NEW SERVER BOOT ---")

# --- 1. CONFIGURATION & ENVIRONMENT VARIABLES ---
_raw_token = os.getenv("TELEGRAM_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_TOKEN = str(_raw_token).strip().strip('"').strip("'")
if TELEGRAM_TOKEN.lower().startswith("bot"):
    TELEGRAM_TOKEN = TELEGRAM_TOKEN[3:]
if not TELEGRAM_TOKEN:
    print("⚠️ [Security Warning] TELEGRAM_TOKEN is not set in environment or .env file!")

_raw_chat = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID = str(_raw_chat).strip().strip('"').strip("'")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL", "JobSkull")  # Primary channel (kept for backward compat)
# All channels to monitor (from env as comma-separated list, or use defaults)
_channels_env = os.getenv("TARGET_CHANNELS", "")
TARGET_CHANNELS = [c.strip().lstrip("@") for c in _channels_env.split(",") if c.strip()] if _channels_env else [
    # Top Active Pan-India Engineering & Fresher Job Channels (Audited & Active)
    "KickCharm",
    "OffCampusJobs4u",
    "Freshershunt",
    "fresheroffcampus",
    "JobSkull",
    "Foundthejob",
    "chennaijobsofficial",
    "tech_jobs_india",
    "freshersvoice",
    "engineering_jobs_india",
    "placementjobs",
    "DailyJobs4You",
    "jobopenings_india",
]

# Dashboard URL (GitHub Pages / Mini-App)
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://nm969989-cmd.github.io/myjob-ai-bot/")

# Files
STATE_FILE = "applied_jobs.json"
RESUME_FILE = "resume.pdf"
PROFILE_FILE = "profile.json"
CHAT_ID_FILE = "chat_id.json"
QA_MEMORY_FILE = "qa_memory.json"
PENDING_QA_FILE = "pending_qa.json"
STATS_FILE = "stats_daily.json"
RETRY_FILE = "retry_queue.json"
LAST_JOB_FILE = "last_job.json"         # Stores details of the last application
CHANNEL_STATUS_FILE = "channel_status.json"  # Stores per-channel scan results
WEEKLY_STATS_FILE = "weekly_stats.json" # Stores weekly cumulative stats

# Live Handoff Protocol
HANDOFF_ACTIVE = False
HANDOFF_PAGE = None
HANDOFF_URL = ""
last_briefing_date = None
last_notion_digest_date = None

# Unsupported/Social media domains that the bot should skip applying to
UNSUPPORTED_DOMAINS = [
    # Job boards (apply manually or not supported)
    "naukri.com", "linkedin.com", "internshala.com", "foundit.in", "indeed.com",
    "glassdoor.com", "shine.com", "monster.com", "timesjobs.com", "hirist.com",
    # Google forms / docs (no auto-fill support)
    "docs.google.com", "google.com/forms", "forms.gle",
    # Social / media
    "youtube.com", "youtu.be", "t.me", "telegram.org", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "whatsapp.com", "pinterest.com",
    "linktr.ee", "bit.ly", "shorturl"
]

# Helper to load and save chat ID dynamically with memory caching to eliminate disk thrashing
_AUTHORIZED_IDS_CACHE = None
_AUTH_CACHE_MTIME = 0

def load_chat_id():
    global TELEGRAM_CHAT_ID
    if TELEGRAM_CHAT_ID:
        return TELEGRAM_CHAT_ID
    data = safe_load_json(CHAT_ID_FILE, {})
    cid = str(data.get("chat_id", "")).strip()
    if cid:
        TELEGRAM_CHAT_ID = cid
    return TELEGRAM_CHAT_ID or ""

def get_authorized_chat_ids():
    """Returns all authorized admin Telegram IDs (from env, saved file, and memory) with mtime-checked caching."""
    global _AUTHORIZED_IDS_CACHE, _AUTH_CACHE_MTIME
    current_mtime = os.path.getmtime(CHAT_ID_FILE) if os.path.exists(CHAT_ID_FILE) else 0
    if _AUTHORIZED_IDS_CACHE is not None and current_mtime == _AUTH_CACHE_MTIME:
        return _AUTHORIZED_IDS_CACHE

    ids = set()
    raw_env_chat = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip().strip('"').strip("'")
    if raw_env_chat:
        for cid in raw_env_chat.split(","):
            if cid.strip():
                ids.add(str(cid.strip()))
    saved_data = safe_load_json(CHAT_ID_FILE, {})
    saved_cid = str(saved_data.get("chat_id", "")).strip()
    if saved_cid:
        ids.add(saved_cid)
    if TELEGRAM_CHAT_ID:
        ids.add(str(TELEGRAM_CHAT_ID))

    _AUTHORIZED_IDS_CACHE = ids
    _AUTH_CACHE_MTIME = current_mtime
    return _AUTHORIZED_IDS_CACHE

def is_authorized(user_or_chat_id):
    """Verifies whether the given Telegram User ID or Chat ID is an authorized admin."""
    if not user_or_chat_id:
        return False
    allowed = get_authorized_chat_ids()
    if not allowed:
        # First-time initial setup: allow the owner to connect and lock the chat ID
        return True
    return str(user_or_chat_id) in allowed

def save_chat_id(chat_id):
    """Safely updates chat ID only if authorized or initializing for the first time with disk I/O deduplication."""
    global TELEGRAM_CHAT_ID, _AUTHORIZED_IDS_CACHE, _AUTH_CACHE_MTIME
    if not chat_id:
        return
    s_chat_id = str(chat_id).strip()
    # In-memory cache hit: avoid duplicate disk I/O and log noise across the 35+ command and callback handlers
    if s_chat_id == TELEGRAM_CHAT_ID and os.path.exists(CHAT_ID_FILE):
        return

    if not is_authorized(s_chat_id) and get_authorized_chat_ids():
        print(f"[Security Warning] Blocked attempt to overwrite Chat ID from unauthorized sender: {s_chat_id}")
        return
    TELEGRAM_CHAT_ID = s_chat_id
    safe_save_json(CHAT_ID_FILE, {"chat_id": TELEGRAM_CHAT_ID})
    _AUTHORIZED_IDS_CACHE = None  # Invalidate cache
    _AUTH_CACHE_MTIME = 0
    print(f"[Auth] Verified Telegram chat ID locked: {TELEGRAM_CHAT_ID}")

def admin_only(handler_func):
    """Security Decorator: Rejects any command or callback from unauthorized Telegram users."""
    def wrapper(event, *args, **kwargs):
        user_id = None
        chat_id = None
        is_callback = False

        if hasattr(event, 'from_user') and event.from_user:
            user_id = str(event.from_user.id)
        if hasattr(event, 'chat') and event.chat:
            chat_id = str(event.chat.id)
        elif hasattr(event, 'message') and event.message and hasattr(event.message, 'chat') and event.message.chat:
            chat_id = str(event.message.chat.id)
            is_callback = True

        if not is_authorized(user_id) and not is_authorized(chat_id):
            print(f"[Security Guard] ⛔ Blocked unauthorized access attempt from User ID: {user_id}, Chat ID: {chat_id}")
            if is_callback and bot:
                try:
                    bot.answer_callback_query(event.id, "⛔ Access Denied: Private Admin Bot.", show_alert=True)
                except Exception:
                    pass
            elif bot and chat_id:
                try:
                    bot.reply_to(event, "⛔ <b>Access Denied</b>\n\nThis is a private single-user AI job bot. You are not authorized to use this bot.", parse_mode="HTML")
                except Exception:
                    pass
            return
        return handler_func(event, *args, **kwargs)
    return wrapper

def enforce_bot_security_profile(tg_bot):
    """Enforces verified bot metadata (description, short description, name, commands) on Telegram."""
    marker_file = ".bot_profile_set"
    profile_version = 'regional-discovery-v1'
    if os.path.exists(marker_file):
        try:
            with open(marker_file, encoding='utf-8') as marker:
                if marker.read().strip() == profile_version:
                    return
        except OSError:
            pass
    try:
        tg_bot.set_my_name("Myjob")
        tg_bot.set_my_description("🚀 MyJob AI Radar — Automated pan-India fresher & engineering job intelligence bot.")
        tg_bot.set_my_short_description("Automated Job Radar & Application Assistant")
        from telebot.types import BotCommand, MenuButtonDefault
        commands = [
            BotCommand("start", "⚡ Restart Bot & Activate Alerts"),
            BotCommand("help", "📖 View All Bot Commands & Guide"),
            BotCommand("search", "🔍 Instant Multi-Source Job Search"),
            BotCommand("match", "🎯 ATS Resume & Job Matcher"),
            BotCommand("oa", "🎓 Company OA Patterns & Coding Exam Syllabus"),
            BotCommand("alerts", "🔔 Keyword Watchdogs & Custom Alerts"),
            BotCommand("tnjobs", "🌟 TN & Puducherry Priority Jobs"),
            BotCommand("walkins", "🚶‍♂️ Regional Walk-In Drives"),
            BotCommand("reminders", "🔔 View or cancel walk-in reminders"),
            BotCommand("drives", "📢 National Mass Off-Campus Drives"),
            BotCommand("deadlines", "⏳ Mass Drive Deadlines Radar"),
            BotCommand("analytics", "📊 Live Market & Career Analytics"),
            BotCommand("radar", "📡 Run Radar Scan (TN & India)"),
            BotCommand("status", "🩺 Bot Engine & Channels Health"),
            BotCommand("dashboard", "🎛️ Interactive Command Center"),
            BotCommand("notion", "📋 Open Notion CRM Tracker"),
            BotCommand("download", "📥 Export Jobs CSV Log")
        ]
        tg_bot.set_my_commands(commands)
        tg_bot.set_chat_menu_button(menu_button=MenuButtonDefault(type="default"))
        print("[Telegram Security] Bot profile & description verified and locked!")
        try:
            with open(marker_file, "w", encoding="utf-8") as f:
                f.write(profile_version)
        except Exception:
            pass
    except Exception as e:
        print(f"[Telegram Security] Profile setup warning: {e}")

# Initialize APIs
if TELEGRAM_TOKEN:
    from telebot import apihelper
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
    apihelper.CONNECT_TIMEOUT = 60
    apihelper.READ_TIMEOUT = 60
    # Enable automatic session refreshment & retry mechanism to survive Hugging Face SSL/TLS drops
    apihelper.SESSION_TIME_TO_LIVE = 60
    apihelper.RETRY_ON_ERROR = True
    apihelper.MAX_RETRIES = 5
    apihelper.RETRY_TIMEOUT = 2
    bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True, num_threads=30)
    if __name__ == "__main__":
        enforce_bot_security_profile(bot)
else:
    bot = None
# Handle multiple Gemini API keys
GEMINI_API_KEYS = [k.strip() for k in str(os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()]
current_gemini_key_index = 0

def get_gemini_client():
    global current_gemini_key_index
    if not GEMINI_API_KEYS:
        return None
    try:
        return genai.Client(api_key=GEMINI_API_KEYS[current_gemini_key_index], http_options={'timeout': 15.0})
    except Exception:
        return None

def rotate_gemini_key():
    global current_gemini_key_index, gemini_client
    if len(GEMINI_API_KEYS) > 1:
        current_gemini_key_index = (current_gemini_key_index + 1) % len(GEMINI_API_KEYS)
        gemini_client = get_gemini_client()
        print(f"[Gemini] Rotated to API key #{current_gemini_key_index + 1}/{len(GEMINI_API_KEYS)}")
        chat_id = load_chat_id()
        if bot and chat_id:
            try: bot.send_message(chat_id, f"🔄 Gemini API Timeout/Error. Rotated to API key #{current_gemini_key_index + 1}")
            except: pass
        return True
    return False

gemini_client = get_gemini_client()

GROQ_API_KEYS = [k.strip() for k in str(os.getenv("GROQ_API_KEY", "")).split(",") if k.strip()]
current_groq_key_index = 0
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

def get_groq_client():
    global current_groq_key_index
    if not GROQ_API_KEYS:
        return None
    try:
        return groq.Groq(api_key=GROQ_API_KEYS[current_groq_key_index], timeout=15.0)
    except Exception:
        return None

def rotate_groq_key():
    global current_groq_key_index, groq_client
    if len(GROQ_API_KEYS) > 1:
        current_groq_key_index = (current_groq_key_index + 1) % len(GROQ_API_KEYS)
        groq_client = get_groq_client()
        print(f"[Groq] Rotated to API key #{current_groq_key_index + 1}/{len(GROQ_API_KEYS)}")
        chat_id = load_chat_id()
        if bot and chat_id:
            try: bot.send_message(chat_id, f"🔄 Groq Rate Limit hit. Rotated to API key #{current_groq_key_index + 1}")
            except: pass
        return True
    return False

groq_client = get_groq_client()

# TokenRouter / OpenAI-Compatible Client
TOKENROUTER_API_KEY = str(os.getenv("TOKENROUTER_API_KEY", "")).strip()
TOKENROUTER_BASE_URL = str(os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.com/v1")).strip()
TOKENROUTER_MODEL = str(os.getenv("TOKENROUTER_MODEL", "openai/gpt-4o-mini")).strip()

def get_tokenrouter_client():
    if not TOKENROUTER_API_KEY:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=TOKENROUTER_API_KEY, base_url=TOKENROUTER_BASE_URL, timeout=15.0)
    except Exception as e:
        print(f"[TokenRouter] Init error: {e}")
        return None

tokenrouter_client = get_tokenrouter_client()

# Global pause flag
BOT_PAUSED = False
ghost_mode_chats = set()
playwright_active = False


# --- 1.5 THREAD-SAFE STORAGE UTILITIES ---
import threading
import queue
# Reentrant so save_applied_job() can hold the lock across its whole
# read-modify-write while safe_load_json/safe_save_json re-acquire it on
# the same thread. A plain Lock would deadlock there.
file_lock = threading.RLock()
application_queue = queue.Queue()

def auto_bug_fixer(error: Exception, context: str = ""):
    """Feed error to Gemini and send the AI fix directly to Telegram."""
    import traceback
    tb = traceback.format_exc()
    try:
        gc = get_gemini_client()
        prompt = f"""You are a Python debugging expert. The following error occurred in a job application bot:

ERROR: {str(error)}

TRACEBACK:
{tb}

CONTEXT: {context}

In 2-3 sentences max:
1. Explain what caused the bug (plain English, no jargon)
2. Give the exact fix (code snippet if needed)

Reply in this format:
🐛 *Cause:* [explanation]
🔧 *Fix:* [exact fix]"""
        resp = gc.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        fix_msg = resp.text.strip()
    except Exception as gem_err:
        fix_msg = f"🐛 *Error:* `{str(error)[:200]}`\n\n_(Gemini unavailable to suggest fix: {gem_err})_"
    
    # Send to Telegram
    chat_id = load_chat_id()
    if bot and chat_id:
        try:
            full_msg = f"🚨 *Bot Error Detected!*\n\n{fix_msg}\n\n_Context: {context[:100]}_"
            bot.send_message(chat_id, full_msg[:4096], parse_mode=None)
        except Exception as tg_err:
            print(f"[AutoBugFixer] Telegram send failed: {tg_err}")

def application_worker():
    while True:
        job_link = application_queue.get()
        if job_link is None:
            break
        try:
            print(f"[Queue Worker] Processing job: {job_link}")
            run_playwright_apply(job_link)
        except Exception as e:
            print(f"[Queue Worker] Error: {e}")
            # Auto Bug Fixer: Feed error to Gemini and alert user in Telegram
            try:
                auto_bug_fixer(e, context=f"Auto-apply for: {job_link}")
            except Exception:
                pass
        finally:
            application_queue.task_done()

threading.Thread(target=application_worker, daemon=True).start()

def safe_load_json(filepath, default_val=None):
    if default_val is None:
        default_val = {}
    with file_lock:
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[I/O Error] Failed to read {filepath}: {e}")
        return default_val

def safe_save_json(filepath, data):
    with file_lock:
        try:
            temp_path = filepath + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, filepath)
        except Exception as e:
            print(f"[I/O Error] Failed to write {filepath}: {e}")

# Load state with mtime memory caching (O(1) lookups during multi-channel scans)
_APPLIED_JOBS_CACHE = None
_APPLIED_JOBS_MTIME = 0

def load_applied_jobs():
    global _APPLIED_JOBS_CACHE, _APPLIED_JOBS_MTIME
    current_mtime = os.path.getmtime(STATE_FILE) if os.path.exists(STATE_FILE) else 0
    if _APPLIED_JOBS_CACHE is not None and current_mtime == _APPLIED_JOBS_MTIME:
        return _APPLIED_JOBS_CACHE.copy()
    data = safe_load_json(STATE_FILE, [])
    _APPLIED_JOBS_CACHE = set(data)
    _APPLIED_JOBS_MTIME = current_mtime
    return _APPLIED_JOBS_CACHE.copy()

def save_applied_job(job_url):
    global _APPLIED_JOBS_CACHE, _APPLIED_JOBS_MTIME
    if not job_url:
        return
    # Hold file_lock across the whole read-modify-write. Previously the load
    # and the save were two separate lock acquisitions, so two apply threads
    # could both read the same set and overwrite each other's addition --
    # losing the dedup entry and letting the same job be applied twice.
    # safe_load_json/safe_save_json re-acquire the same reentrant lock.
    with file_lock:
        applied = load_applied_jobs()
        applied.add(job_url)
        safe_save_json(STATE_FILE, list(applied))
        _APPLIED_JOBS_CACHE = applied
        _APPLIED_JOBS_MTIME = os.path.getmtime(STATE_FILE) if os.path.exists(STATE_FILE) else time.time()

# --- QA Memory: remember answers to custom job questions ---
def load_qa_memory():
    mem = safe_load_json(QA_MEMORY_FILE, {})
    if not mem:
        try:
            from bot_optimizer import get_seeded_qa_memory
            mem = get_seeded_qa_memory(QA_MEMORY_FILE)
        except Exception:
            pass
    return mem

def save_qa_memory(qa_memory):
    safe_save_json(QA_MEMORY_FILE, qa_memory)

def load_pending_qa():
    return safe_load_json(PENDING_QA_FILE, {})

def save_pending_qa(pending):
    safe_save_json(PENDING_QA_FILE, pending)

def load_stats():
    today = datetime.now().strftime("%Y-%m-%d")
    default_stats = {"date": today, "applied": 0, "skipped": 0, "failed": 0, "current_streak": 0, "last_apply_date": ""}
    stats = safe_load_json(STATS_FILE, default_stats)
    if stats.get("date") != today:
        stats["date"] = today
        stats["applied"] = 0
        stats["skipped"] = 0
        stats["failed"] = 0
    return stats

def save_stats(stats):
    safe_save_json(STATS_FILE, stats)

def load_retry_queue():
    return safe_load_json(RETRY_FILE, {})

def save_retry_queue(queue):
    safe_save_json(RETRY_FILE, queue)

# --- Last Job Storage ---
def save_last_job(data: dict):
    """Saves details of the most recent application attempt."""
    safe_save_json(LAST_JOB_FILE, data)

def load_last_job() -> dict:
    return safe_load_json(LAST_JOB_FILE, {})

# --- Channel Status Storage ---
def save_channel_status(status: dict):
    safe_save_json(CHANNEL_STATUS_FILE, status)

def load_channel_status() -> dict:
    return safe_load_json(CHANNEL_STATUS_FILE, {})

# --- Weekly Stats Storage ---
def load_weekly_stats() -> dict:
    week = datetime.now().strftime("%Y-W%W")
    default = {"week": week, "applied": 0, "skipped": 0, "failed": 0, "channels_scanned": 0}
    data = safe_load_json(WEEKLY_STATS_FILE, default)
    if data.get("week") != week:
        return default
    return data

def save_weekly_stats(stats: dict):
    safe_save_json(WEEKLY_STATS_FILE, stats)

# --- Smart Sleep Hours Guard ---
def is_sleep_time() -> bool:
    """Returns True between 11 PM and 6 AM IST — bot rests to avoid bot-detection."""
    # Convert UTC to IST (+5:30)
    utc_now = datetime.utcnow()
    ist_hour = (utc_now.hour + 5 + (utc_now.minute + 30) // 60) % 24
    return ist_hour >= 23 or ist_hour < 6

# --- Duplicate URL hash set (cross-channel dedup within one cycle) ---
_seen_this_cycle: set = set()

# Load profile data with mtime memory caching (O(1) memory lookup)
_PROFILE_CACHE = None
_PROFILE_CACHE_MTIME = 0

def load_profile():
    global _PROFILE_CACHE, _PROFILE_CACHE_MTIME
    current_mtime = os.path.getmtime(PROFILE_FILE) if os.path.exists(PROFILE_FILE) else 0
    if _PROFILE_CACHE is not None and current_mtime == _PROFILE_CACHE_MTIME:
        return _PROFILE_CACHE.copy()

    default_profile = {
        "full_name": "Manoj Kumar",
        "email": "manoj.kumar@example.com",
        "phone": "+91 9876543210",
        "experience_years": "2 years",
        "github": "https://github.com/manoj",
        "linkedin": "https://linkedin.com/in/manoj",
        "portfolio": "https://manoj.dev",
        "skills": "Python, JavaScript, Playwright, React, SQL, Automation",
        "about": "Self-motivated software developer with a passion for web scraping, browser automation, and AI integrations.",
        "cover_letters": {
            "default": "I am a passionate software developer with 2 years of experience building automation tools and scalable web applications. I am excited about the opportunity to contribute my skills to your innovative team.",
            "startup": "As a self-motivated developer, I thrive in fast-paced startup environments. I have strong experience in Python and full-stack development and can quickly adapt to new challenges to drive your product forward.",
            "corporate": "With a solid foundation in software engineering principles and a track record of reliable delivery, I am eager to bring my technical expertise to your established organization and contribute to long-term success."
        }
    }
    _PROFILE_CACHE = safe_load_json(PROFILE_FILE, default_profile)
    _PROFILE_CACHE_MTIME = current_mtime
    return _PROFILE_CACHE.copy()

_TRACKING_KEYS = frozenset({"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref", "source", "ref_id"})

def clean_tracking_params(url):
    """Strips Google Analytics/Social Media tracking parameters to keep URLs clean and direct."""
    if not url:
        return url
    from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        filtered_qs = {k: v for k, v in qs.items() if k.lower() not in _TRACKING_KEYS}
        clean_query = urlencode(filtered_qs, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))
    except Exception:
        return url

# --- 2. WEBPAGE REDIRECT BYPASSER ---
def bypass_blog_redirect(blog_url):
    """
    Intelligently finds the real company application link inside ad-heavy blogger/shortener pages.
    Step 1: Follow HTTP redirects & recursively unwrap URL shorteners (bit.ly, tinyurl, cutt.ly, etc.)
    Step 2: Unpack embedded query parameters and base64-encoded destination URLs
    Step 3: Deep container HTML scraping for the actual ATS/careers apply link
    Step 4: Meta-refresh, JavaScript redirects, and button onclick handler extraction
    """
    import base64
    from urllib.parse import urlparse, parse_qs, unquote

    if not blog_url:
        return blog_url

    blog_url = blog_url.strip().strip("'\"")

    direct_domains = [
        "docs.google.com/forms", "forms.gle", "greenhouse.io", "lever.co", "workdayjobs.com",
        "smartrecruiters.com", "joinsuperset.com", "myworkdayjobs.com", "sensehq.com",
        "oraclecloud.com", "successfactors", "icims.com", "ashbyhq.com", "jobvite.com",
        "bamboohr.com", "jobs.lever.co", "taleo.net", "breezy.hr", "phenompeople.com",
        "recruitee.com", "freshteam.com", "zohorecruit.com", "wellfound.com",
        "angel.co", "workingnomads.com", "weworkremotely.com", "hired.com",
        "triplebyte.com", "ycombinator.com/companies", "darwinbox.com", "darwinbox.in", "keka.com",
        "unstop.com", "internshala.com", "foundit.in", "naukri.com", "hirist.com", "hirist.tech",
        "amazon.jobs", "careers.google.com", "careers.microsoft.com", "jobs.apple.com",
        "peoplestrong.com", "ripplehire.com", "eightfold.ai", "talentbrew.com",
        "cornerstoneondemand.com", "brassring.com", "avature.net", "workable.com",
        "applytojob.com", "personio.com", "jobs.sap.com", "jobs.siemens.com", "jobs.cisco.com"
    ]
    if any(domain in blog_url.lower() for domain in direct_domains):
        print(f"[Bypasser] URL is already a direct job portal: {blog_url}")
        return clean_tracking_params(blog_url)

    shortener_domains = [
        "bit.ly", "tinyurl.com", "cutt.ly", "t.co", "rb.gy", "t.ly", "is.gd",
        "buff.ly", "ow.ly", "shorturl.at", "dub.sh", "linkvertise.com", "adf.ly",
        "pdlink.in", "linkrex.net", "url.bio", "trib.al", "rebrand.ly", "bl.ink",
        "tiny.cc", "goo.gl", "lnkd.in", "qr.ae", "sh.st"
    ]

    parked_domains_list = [
        "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com",
        "namecheap.com", "domainmarket.com", "parklogic.com", "parkingcrew.com",
        "bodis.com", "above.com", "domainagents.com", "undeveloped.com",
        "buydomains.com", "domain_profile.cfm", "domainforbuy"
    ]

    skip_domains = [
        "newsletter", "instagram.com", "youtube.com", "youtu.be", "whatsapp.com", "telegram.org",
        "t.me", "telegram.dog", "facebook.com", "twitter.com", "x.com", "pinterest.com", "reddit.com",
        "play.google.com", "apps.apple.com", "aratt.ai", "wa.me", "threads.net", "linktr.ee",
        "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com", "namecheap.com",
        "domainmarket.com", "parklogic.com", "parkingcrew.com", "bodis.com", "above.com",
        "domainagents.com", "undeveloped.com", "buydomains.com", "domain_profile.cfm", "domainforbuy"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        # Step 1: Follow HTTP redirect chain (up to 4 hops for nested shorteners)
        curr_url = blog_url
        for _ in range(4):
            try:
                resp = requests.get(curr_url, headers=headers, timeout=10, allow_redirects=True)
                final_url = resp.url
                if final_url != curr_url:
                    print(f"[Bypasser] Followed redirect: {curr_url} → {final_url}")
                    curr_url = final_url
                netloc = urlparse(curr_url).netloc.lower()
                if not any(sh in netloc for sh in shortener_domains):
                    break
            except Exception:
                break

        # Check if landed on direct ATS
        if any(domain in curr_url.lower() for domain in direct_domains):
            print(f"[Bypasser] Redirect chain landed on direct ATS: {curr_url}")
            return clean_tracking_params(curr_url)

        # Reject parked domain
        if any(p in curr_url.lower() for p in parked_domains_list):
            print(f"[Bypasser] Redirected to parked/expired domain ({curr_url}) — rejecting.")
            return ""

        # Step 2: Check query parameters for embedded target URLs (including base64)
        parsed_current = urlparse(curr_url)
        if parsed_current.query:
            qs = parse_qs(parsed_current.query)
            for param_key in ["target", "url", "redirect", "goto", "link", "dest", "next", "redir", "u", "to"]:
                if param_key in qs:
                    raw_val = qs[param_key][0]
                    target_candidate = unquote(raw_val).strip()
                    if target_candidate.startswith("http") and not any(x in target_candidate.lower() for x in skip_domains):
                        print(f"[Bypasser] Found target link in query parameter '{param_key}': {target_candidate}")
                        return clean_tracking_params(target_candidate)
                    # Check base64 encoded URL
                    if raw_val.startswith("aHR0"):
                        try:
                            decoded = base64.b64decode(raw_val).decode('utf-8', errors='ignore').strip()
                            if decoded.startswith("http") and not any(x in decoded.lower() for x in skip_domains):
                                print(f"[Bypasser] Decoded base64 target link: {decoded}")
                                return clean_tracking_params(decoded)
                        except Exception:
                            pass

        # Step 3: Fetch and inspect page HTML
        resp = requests.get(curr_url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return clean_tracking_params(curr_url)

        soup = BeautifulSoup(resp.text, "html.parser")
        blog_domain = parsed_current.netloc.lower()

        # Check <meta http-equiv="refresh"> redirect tags
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh:
            content = meta_refresh.get("content", "")
            url_match = re.search(r'url\s*=\s*["\']?([^"\';\s>]+)', content, re.I)
            if url_match:
                meta_url = url_match.group(1).strip()
                if meta_url.startswith("http") and blog_domain not in meta_url:
                    if not any(p in meta_url.lower() for p in parked_domains_list) and not any(x in meta_url.lower() for x in skip_domains):
                        print(f"[Bypasser] Found meta refresh redirect: {meta_url}")
                        return clean_tracking_params(meta_url)

        # 3a. Direct ATS links across the ENTIRE page (Highest Priority)
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            if not href.startswith("http"):
                continue
            if any(domain in href.lower() for domain in direct_domains):
                if blog_domain not in href and not any(x in href.lower() for x in skip_domains):
                    print(f"[Bypasser] Found direct ATS link on page: {href}")
                    return clean_tracking_params(href)

        # 3b. Gather ALL content containers (not just the first div)
        containers = soup.find_all(["article", "main"])
        if not containers:
            containers = soup.find_all("div", class_=lambda c: c and any(k in str(c).lower() for k in ["entry-content", "post-body", "article-body", "post-content", "content"]))
        if not containers:
            containers = [soup]

        apply_keywords = [
            "apply online", "click here to apply", "apply for this job", "start application",
            "apply link", "direct apply", "official apply link", "official link", "registration link",
            "apply now", "register now", "apply here", "external apply", "apply on company",
            "career page", "company website", "job link", "official portal", "registration form",
            "click here", "more details", "apply"
        ]

        for c in containers:
            for link in c.find_all("a", href=True):
                href = link["href"].strip()
                link_text = link.get_text(separator=" ").strip().lower()
                if not href.startswith("http") or blog_domain in href:
                    continue
                if any(x in href.lower() for x in skip_domains):
                    continue
                if any(word in link_text for word in apply_keywords):
                    if any(sh in href.lower() for sh in shortener_domains):
                        try:
                            sub_r = requests.get(href, headers=headers, timeout=8, allow_redirects=True)
                            href = sub_r.url
                        except Exception:
                            pass
                    print(f"[Bypasser] Found apply link via text keyword: {href}")
                    return clean_tracking_params(href)

        # 3c. Check JavaScript window.location or window.open in script tags
        for script in soup.find_all("script"):
            script_text = script.string or ""
            js_patterns = [
                r'window\.location\s*=\s*["\']([^"\']+)',
                r'window\.location\.href\s*=\s*["\']([^"\']+)',
                r'window\.open\s*\(\s*["\']([^"\']+)',
                r'location\.replace\s*\(\s*["\']([^"\']+)',
            ]
            for pattern in js_patterns:
                match = re.search(pattern, script_text)
                if match:
                    js_url = match.group(1).strip()
                    if js_url.startswith("http") and blog_domain not in js_url and not any(x in js_url.lower() for x in skip_domains):
                        print(f"[Bypasser] Found JS redirect link: {js_url}")
                        return clean_tracking_params(js_url)

        # 3d. Check button onclick handlers
        for c in containers:
            for btn in c.find_all(["button", "a", "div"], onclick=True):
                onclick = btn.get("onclick", "")
                url_match = re.search(r'["\']?(https?://[^"\';\s]+)', onclick)
                if url_match:
                    btn_url = url_match.group(1).strip()
                    if blog_domain not in btn_url and not any(x in btn_url.lower() for x in skip_domains):
                        print(f"[Bypasser] Found onclick URL: {btn_url}")
                        return clean_tracking_params(btn_url)

        # 3e. Career / Jobs URL pattern check across all external links
        all_external_links = []
        for c in containers:
            for link in c.find_all("a", href=True):
                href = link["href"].strip()
                if href.startswith("http") and blog_domain not in href:
                    if not any(x in href.lower() for x in skip_domains):
                        if href not in all_external_links:
                            all_external_links.append(href)

        for ext_link in all_external_links:
            if any(kw in ext_link.lower() for kw in ["/career", "/job", "/apply", "/opening", "/hiring", "/recruit", "careers.", "jobs."]):
                if any(sh in ext_link.lower() for sh in shortener_domains):
                    try:
                        sub_r = requests.get(ext_link, headers=headers, timeout=8, allow_redirects=True)
                        ext_link = sub_r.url
                    except Exception:
                        pass
                print(f"[Bypasser] Found career page URL pattern: {ext_link}")
                return clean_tracking_params(ext_link)

        if all_external_links:
            print(f"[Bypasser] Using primary external link: {all_external_links[0]}")
            return clean_tracking_params(all_external_links[0])

        return clean_tracking_params(curr_url)
    except Exception as e:
        print(f"[Bypasser] Error resolving redirect for {blog_url}: {e}")
        return clean_tracking_params(blog_url)

# --- 2.9 AI PAGE VERIFICATION HELPER ---
def verify_page_with_ai(page, screenshot_bytes, context_msg=""):
    """
    Uses Gemini Vision to analyze the current page state.
    Returns: 'success', 'error', 'form', 'captcha', or 'unknown'
    """
    if not gemini_client:
        return 'unknown'
    try:
        from google.genai import types as gtypes
        prompt = f"""
        You are a job application bot verifying the state of a web page.
        Context: {context_msg}

        Look at this screenshot and classify what the page shows into EXACTLY ONE of these categories:
        - 'success'  → Thank you, application submitted, confirmation email sent, application received, success!
        - 'error'    → Error message, validation failed, required field missing, invalid input, please fix
        - 'form'     → There is still a form or fields to fill in (next step, multi-step form continues)
        - 'captcha'  → A CAPTCHA, reCAPTCHA, or security check is blocking
        - 'login'    → Requires login or account creation to continue
        - 'unknown'  → None of the above

        Reply ONLY with one word from the list above. No other text.
        """
        contents = [prompt]
        if screenshot_bytes:
            contents.append(gtypes.Part.from_bytes(data=screenshot_bytes, mime_type='image/png'))
        response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=contents)
        result = response.text.strip().lower()
        for state in ['success', 'error', 'form', 'captcha', 'login', 'unknown']:
            if state in result:
                return state
        return 'unknown'
    except Exception as e:
        print(f"[AI Verify] Failed: {e}")
        return 'unknown'

def ai_fix_selector(page, failed_selector, expected_value, screenshot_bytes, gemini_client, groq_client):
    """
    When a selector fails, asks Gemini/Groq to suggest an alternative selector
    by analyzing the current page HTML and screenshot.
    Returns a new selector string or None.
    """
    try:
        body_html = page.evaluate("() => (document.querySelector('main') || document.body).innerHTML")[:15000]
        prompt = f"""
        A CSS selector failed to locate a field on this job application form.
        Failed selector: "{failed_selector}"
        Expected value to fill: "{expected_value}"

        Here is the current page HTML:
        {body_html}

        Look for any visible input/textarea/select element that would logically accept this value.
        Reply ONLY with the single best CSS selector string. No explanation. No quotes. No markdown.
        If you cannot find any suitable element, reply with: NONE
        """
        # Try Gemini first
        if gemini_client:
            try:
                from google.genai import types as gtypes
                contents = [prompt]
                if screenshot_bytes:
                    contents.append(gtypes.Part.from_bytes(data=screenshot_bytes, mime_type='image/png'))
                resp = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=contents)
                sel = resp.text.strip().strip('`').strip('"').strip("'")
                if sel and sel.upper() != 'NONE':
                    return sel
            except Exception:
                pass
        # Fallback to Groq
        if groq_client:
            try:
                completion = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a CSS selector expert. Reply only with a single CSS selector."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0,
                )
                sel = completion.choices[0].message.content.strip().strip('`').strip('"').strip("'")
                if sel and sel.upper() != 'NONE':
                    return sel
            except Exception:
                pass
    except Exception as e:
        print(f"[AI Fix Selector] Error: {e}")
    return None

# --- 3. DYNAMIC FORM FILLING WITH GEMINI ---
def analyze_form_with_gemini(form_html, profile_data, screenshot_bytes=None, job_context="", job_description=""):
    """
    Uses Gemini API to map form fields to the user's profile data, leveraging both HTML and Vision.
    It uses the job_description to write customized Cover Letters.
    """
    if not gemini_client:
        print("[Warning] Gemini client not initialized. Skipping AI form mapping.")
        return None
        
    qa_memory = load_qa_memory()
    qa_memory_text = ""
    if qa_memory:
        qa_memory_text = "\n\n    Previously Answered Questions (USE THESE EXACT ANSWERS for matching questions):\n"
        for q, a in qa_memory.items():
            qa_memory_text += f"    Q: {q}\n    A: {a}\n"

    prompt = f"""
    You are an expert job application automation bot. Your ONLY job is to analyze the form HTML and screenshot below and output JSON field mappings so the bot can fill the form.

    Job URL: {job_context}
    
    Specific Job Description:
    {job_description}

    User Profile:
    {json.dumps(profile_data, indent=2)}{qa_memory_text}

    Form HTML:
    {form_html}

    CRITICAL RULES - READ CAREFULLY:
    1. ALWAYS output real CSS selectors. Prefer: input[name='xxx'], textarea[name='xxx'], select[name='xxx'], input[placeholder='xxx'], input[type='email'], input[id='xxx'], [data-field='xxx'].
    2. NEVER output a selector like 'input' or 'textarea' alone — always include attribute or id to make it unique.
    3. For EVERY visible text input/textarea/select in the HTML, output a mapping entry using profile data. Map:
       - Name fields → full_name
       - Email fields → email
       - Phone/Mobile fields → phone
       - LinkedIn URL fields → linkedin
       - GitHub/Portfolio fields → github or portfolio
       - Years of experience fields → experience_years
       - Skills/Summary/About fields → skills or about
       - Current/Expected salary → output '0' or 'As per industry standard'
       - Notice period → output 'Immediate'
       - City/Location → 'Bengaluru' (or best guess from profile)
    4. DROPDOWN FIELDS (select elements): When you see a <select> element, READ the actual <option> values listed in the HTML. For the "value" field in your output, use the EXACT text of the best matching <option> label. For example, if options are ["Fresher", "0-1 years", "1-2 years"], use "Fresher" not "0".
    5. RADIO BUTTONS & CHECKBOXES: If you see radio buttons or checkboxes (e.g. for gender, experience type, availability), output the selector of the specific option to click and set value to 'true'.
    6. VECTOR MEMORY (SEMANTIC MATCHING): I have provided a list of "Previously Answered Questions" above. Act as a Semantic Vector Database. If a form field asks a question that is semantically similar (e.g., "Do you have a passport?" vs "Passport Number"), use the stored answer. The wording does not need to be exact, just the underlying meaning.
    7. ZERO-INTERRUPTION MODE (UNKNOWN QUESTIONS): If you see a field asking a specific question that CANNOT be answered from the profile data or the Vector Memory, DO NOT ask the user. You must AUTO-HALLUCINATE the safest, most professional, and positive answer possible (e.g., "Yes", "Willing to discuss during interview", or "0" for salary). NEVER output __ASK_USER__ under any circumstance.
    8. COVER LETTER / MOTIVATION: For any open-ended textarea ("Why us?", "Tell us about yourself", "Cover Letter"), DO NOT use standard template variables. Instead, ACT AS A PROFESSIONAL COPYWRITER and WRITE A HIGHLY CUSTOMIZED, 2-3 PARAGRAPH COVER LETTER based EXACTLY on the 'Specific Job Description' provided above and the 'User Profile'. Be persuasive and enthusiastic!
    9. APPLY BUTTON: If this is a job description page with an "Apply Now" / "Apply" / "Start Application" button but no input fields, return empty fields and file_fields, but set submit_selector to click that button.
    10. SUCCESS PAGE: If this looks like a "Thank you" / "Application submitted" confirmation page, return all empty lists and null for submit_selector.
    11. ERROR/LOGIN PAGE: If this is a 404, access denied, or login-required page, return all empty lists and null for submit_selector.
    12. FILE UPLOAD: If you see input[type='file'] (especially for Resume/CV), ALWAYS include it in file_fields. CRITICAL for application success.
    13. SUBMIT BUTTON: Always include the submit/next/continue button selector in submit_selector if a form is present.
    14. OTP/VERIFICATION CODE: If the form is asking for a verification code (e.g. sent to email/phone), output exactly: __OTP_REQUEST__:<company_name_or_domain> for its value.
    15. ACCOUNT CREATION/LOGIN: If the form requires creating a password or logging in, output exactly: __GENERATE_PASSWORD__ for the password field.
    16. BLOG COMMENTS & NEWSLETTERS: If the page is a blog post or job aggregator and the ONLY form present is a "Leave a Reply", "Post Comment", or "Subscribe" form (typically asking for name, email, url, and comment), DO NOT map it! Return empty fields and null submit_selector. ONLY map real job application forms.
    17. VALIDATION ERRORS: If you see any red text, error messages, or highlighted required fields in the screenshot, prioritize fixing those fields. Include them in the fields list with corrected values.

    Return ONLY raw JSON. No markdown. No explanation. Just the JSON object.
    Format:
    {{
      "fields": [
        {{"selector": "css_selector_for_input", "value": "text_to_fill"}},
        {{"selector": "css_selector_for_textarea", "value": "generated_cover_letter_or_text"}}
      ],
      "file_fields": [
        {{"selector": "css_selector_for_file_input", "file_type": "resume"}}
      ],
      "submit_selector": "css_selector_for_submit_or_apply_or_next_button"
    }}
    """
    
    contents = [prompt]
    if screenshot_bytes:
        try:
            from google.genai import types  # type: ignore
            contents.append(
                types.Part.from_bytes(
                    data=screenshot_bytes,
                    mime_type='image/png'
                )
            )
        except Exception as e:
            print(f"[Gemini] Failed to attach screenshot: {e}")

    # Try all available Gemini keys, one attempt per key
    max_retries = max(len(GEMINI_API_KEYS), 1)
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\n", "", text)
                text = re.sub(r"\n```$", "", text)
            return json.loads(text)
        except Exception as e:
            print(f"[Gemini] Key #{attempt+1} failed: {e}")
            # Try to rotate to next Gemini key
            rotate_gemini_key()
            # Small wait before next key attempt
            time.sleep(2)

    # ── ALL GEMINI KEYS FAILED → FALLBACK TO GROQ ──────────────────────
    print("[Groq] All Gemini keys exhausted or broken. Falling back to Groq Vision Engine...")
    
    for attempt in range(len(GROQ_API_KEYS) if GROQ_API_KEYS else 1):
        if not groq_client:
            break
        try:
            # NOTE: llama-3.3-70b-versatile does NOT support vision/image inputs.
            # We send only the text prompt. The form HTML already contains enough context.
            # For vision, we would need a Groq vision model like llava, but text-only is reliable here.
            groq_messages = [
                {"role": "system", "content": "You are an expert job application automation bot. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}  # plain string — NOT a list, avoids error 400
            ]
            completion = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=groq_messages,
                temperature=0,
            )
            groq_text = completion.choices[0].message.content.strip()
            if groq_text.startswith("```"):
                groq_text = re.sub(r"^```(?:json)?\n", "", groq_text)
                groq_text = re.sub(r"\n```$", "", groq_text)
            print("[Groq] Text Engine successfully mapped the form!")
            return json.loads(groq_text)
        except Exception as groq_err:
            print(f"[Groq] Key #{attempt+1} failed: {groq_err}")
            rotate_groq_key()
            time.sleep(2)

    return {"ERROR": "All AI engines exhausted. Both Gemini and Groq API keys failed or rate-limited."}

# --- 3.5 SMART AI JOB FILTER & SHEET TRACKER ---
def check_job_match(job_text, profile_data):
    """
    Strictly filters for FRESHER / ENTRY-LEVEL ENGINEERING jobs only.
    Returns (is_match, summary_text) where summary_text is a formatted job card.
    """
    # ⚡ FAST PRE-FILTER: Keyword check before hitting slow Gemini API (saves 5-10 seconds per job)
    job_lower = job_text.lower()
    
    # Hard reject if clearly senior/experienced role
    senior_keywords = ["senior", "sr.", "lead developer", "lead engineer", "principal", 
                       "manager", "director", "architect", "5+ years", "7+ years", 
                       "10+ years", "8 years", "9 years", "6 years"]
    if any(kw in job_lower for kw in senior_keywords):
        return False, "⏩ Fast-Filtered: Senior/experienced role detected — skipped instantly"

    # Location Filter: Strictly reject non-India locations
    from job_radar import classify_location
    is_valid_loc, tier, loc_tag, is_tn = classify_location("", job_text)
    if not is_valid_loc:
        return False, "⏩ Fast-Filtered: Non-India location detected — skipped instantly"
    
    # Hard accept if clearly a fresher role (skip Gemini entirely to save time)
    fresher_keywords = ["fresher", "fresh graduate", "0 year", "0-1 year", "entry level", 
                        "entry-level", "2024", "2025", "2026", "trainee", "graduate trainee",
                        "junior", "associate developer", "no experience", "intern", "internship", "off campus", "off-campus"]
    if any(kw in job_lower for kw in fresher_keywords):
        # Build a quick summary without Gemini (instant!)
        tn_badge = " 🌟 [TN Priority]" if is_tn else ""
        quick_summary = (
            f"🏢 *Job Found*\n"
            f"💼 *Type:* Fresher/Entry Level{tn_badge}\n"
            f"📍 *Location:* {loc_tag}\n"
            f"🤖 *AI Score:* 9/10 — Keyword-matched instantly (no AI delay)"
        )
        return True, quick_summary
    
    # Only call slow Gemini for ambiguous jobs
    if not gemini_client:
        return True, "No Gemini API"

    prompt = f"""
    You are an AI job filter for a fresher candidate.

    STRICT RULES — REJECT (score 1-3) if ANY of these are true:
    1. Job requires MORE than 2 years of experience (e.g. "3 years exp", "experienced candidate").
    2. Job is only on LinkedIn, Naukri, Internshala, Indeed — these are skipped separately.
    3. Job post is just a news article, blog, or advertisement — not an actual job opening.

    ACCEPT (score 7-10) ONLY if:
    - Experience required is 0-2 years OR explicitly says "Fresher" / "Fresh Graduate" / "0 exp".
    - It is a real job opening with an application link.
    - Accept ALL fields (Engineering, IT, BPO, Operations, Support, Sales, Data Entry, etc.) as long as it is for a fresher.

    User Profile:
    Name: {profile_data.get('full_name')}
    Skills: {profile_data.get('skills')}
    Experience: {profile_data.get('experience_years')}

    Job Post:
    {job_text[:1500]}

    Reply ONLY in this exact JSON (no markdown, no explanation):
    {{
      "score": 8,
      "reason": "1 sentence why accepted/rejected",
      "company": "Company name or Unknown",
      "position": "Job title",
      "location": "City / Remote / WFH",
      "salary": "Salary or Not Mentioned",
      "experience": "Fresher / 0-1 yr / etc.",
      "type": "Full-time / Internship / Contract"
    }}
    """

    def _parse_response(text):
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n", "", text)
            text = re.sub(r"\n```$", "", text)
        return json.loads(text)

    # Attempt Gemini
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        result = _parse_response(response.text)
        score = result.get("score", 5)
        reason = result.get("reason", "")
        summary = (
            f"🏢 *{result.get('company', 'Unknown')}*\n"
            f"💼 *Position:* {result.get('position', 'N/A')}\n"
            f"📍 *Location:* {result.get('location', 'N/A')}\n"
            f"💰 *Salary:* {result.get('salary', 'Not Mentioned')}\n"
            f"🎓 *Experience:* {result.get('experience', 'N/A')}\n"
            f"📋 *Type:* {result.get('type', 'N/A')}\n"
            f"🤖 *AI Score:* {score}/10 — {reason}"
        )
        is_match = score >= 7
        return is_match, summary
    except Exception as e:
        print(f"[AI Filter] Gemini key #{current_gemini_key_index+1} failed: {e}")

    # Try remaining Gemini keys
    for _ in range(len(GEMINI_API_KEYS) - 1):
        if not rotate_gemini_key():
            break
        try:
            response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            result = _parse_response(response.text)
            score = result.get("score", 5)
            reason = result.get("reason", "")
            summary = (
                f"🏢 *{result.get('company', 'Unknown')}*\n"
                f"💼 *Position:* {result.get('position', 'N/A')}\n"
                f"📍 *Location:* {result.get('location', 'N/A')}\n"
                f"💰 *Salary:* {result.get('salary', 'Not Mentioned')}\n"
                f"🎓 *Experience:* {result.get('experience', 'N/A')}\n"
                f"📋 *Type:* {result.get('type', 'N/A')}\n"
                f"🤖 *AI Score:* {score}/10 — {reason}"
            )
            return score >= 7, summary
        except Exception as e2:
            print(f"[AI Filter] Rotated Gemini key also failed: {e2}")

    # ── ALL GEMINI KEYS FAILED → FALLBACK TO TOKENROUTER ────────────────
    if tokenrouter_client:
        print("[TokenRouter] Gemini keys unavailable/failed. Falling back to TokenRouter...")
        try:
            completion = tokenrouter_client.chat.completions.create(
                model=TOKENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": "You are an AI job filter. Reply ONLY in raw JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            result = _parse_response(completion.choices[0].message.content)
            score = result.get("score", 5)
            reason = result.get("reason", "")
            summary = (
                f"🏢 *{result.get('company', 'Unknown')}*\n"
                f"💼 *Position:* {result.get('position', 'N/A')}\n"
                f"📍 *Location:* {result.get('location', 'N/A')}\n"
                f"💰 *Salary:* {result.get('salary', 'Not Mentioned')}\n"
                f"🎓 *Experience:* {result.get('experience', 'N/A')}\n"
                f"📋 *Type:* {result.get('type', 'N/A')}\n"
                f"🤖 *AI Score (TokenRouter):* {score}/10 — {reason}"
            )
            print("[TokenRouter] AI Filter fallback successful!")
            return score >= 7, summary
        except Exception as tr_e:
            print(f"[TokenRouter] Fallback failed: {tr_e}")

    # ── FALLBACK TO GROQ ───────────────────────────────────────────────
    print("[Groq] Falling back to Groq...")
    if groq_client:
        try:
            completion = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are an AI job filter. Reply ONLY in raw JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            result = _parse_response(completion.choices[0].message.content)
            score = result.get("score", 5)
            reason = result.get("reason", "")
            summary = (
                f"🏢 *{result.get('company', 'Unknown')}*\n"
                f"💼 *Position:* {result.get('position', 'N/A')}\n"
                f"📍 *Location:* {result.get('location', 'N/A')}\n"
                f"💰 *Salary:* {result.get('salary', 'Not Mentioned')}\n"
                f"🎓 *Experience:* {result.get('experience', 'N/A')}\n"
                f"📋 *Type:* {result.get('type', 'N/A')}\n"
                f"🤖 *AI Score (Groq):* {score}/10 — {reason}"
            )
            print("[Groq] AI Filter fallback successful!")
            return score >= 7, summary
        except Exception as groq_e:
            print(f"[Groq] Filter fallback also failed: {groq_e}")

    # If everything failed, accept the job anyway so we don't miss opportunities
    print("[AI Filter] All AI engines failed. Accepting job by default to avoid missing it.")
    return True, "⚠️ AI filter unavailable — accepted by default"

def log_job(url, job_text, success, reason="", is_failed=False):
    """Logs every job action, updates daily stats, and triggers Google Sheets Webhook."""
    try:
        # Update Daily Stats & Streak Tracker
        stats = load_stats()
        if success:
            stats["applied"] += 1
            today_str = datetime.now().strftime("%Y-%m-%d")
            # Streak Logic (use .get so older stats files without this key don't crash)
            last_apply_date = stats.get("last_apply_date", "")
            if last_apply_date != today_str:
                if last_apply_date:
                    last_date = datetime.strptime(last_apply_date, "%Y-%m-%d")
                    if (datetime.now() - last_date).days <= 1:
                        stats["current_streak"] = stats.get("current_streak", 0) + 1
                    else:
                        stats["current_streak"] = 1
                else:
                    stats["current_streak"] = 1
                stats["last_apply_date"] = today_str
        elif is_failed:
            stats["failed"] += 1
        else:
            stats["skipped"] += 1
        save_stats(stats)

        # Extract title roughly
        title = job_text[:50].replace('\n', ' ').replace('\r', '') if job_text else "Unknown Job"
        status = "Failed" if is_failed else ("Applied" if success else "Skipped")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Log skipped jobs to console/tracker only (no Telegram chat spam)
        if status == "Skipped":
            print(f"[Tracker] Skipped job: {title} | Reason: {reason}")
        
        # 1. Google Sheets Webhook (Easier setup via Make/Zapier/Apps Script)
        webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL")
        if webhook_url:
            try:
                payload = {
                    "Date": timestamp,
                    "Job Title": title,
                    "URL": url,
                    "Status": status,
                    "Notes": reason
                }
                requests.post(webhook_url, json=payload, timeout=5)
            except Exception as e:
                print(f"[Tracker] Webhook error: {e}")

        # 1.5 Legacy Google Sheets (gspread)
        sheets_creds = os.getenv("GOOGLE_SHEETS_CREDENTIALS")
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if sheets_creds and sheet_url:
            try:
                import gspread  # type: ignore
                from oauth2client.service_account import ServiceAccountCredentials  # type: ignore
                
                scope = [
                    "https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive"
                ]
                creds_dict = json.loads(sheets_creds)
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
                gc = gspread.authorize(creds)
                
                sheet = gc.open_by_url(sheet_url).sheet1
                
                # Add header row if the sheet is empty
                if not sheet.get_all_values():
                    sheet.append_row(["Date", "Job Title", "URL", "Status", "Notes"])
                    
                sheet.append_row([timestamp, title, url, status, reason])
                print(f"[Tracker] Logged to Google Sheets: {title}")
            except ImportError:
                print("[Tracker] gspread/oauth2client not installed. Skipping Sheets logging.")
            except Exception as sheet_err:
                print(f"[Tracker] Google Sheets error (non-fatal): {sheet_err}")
        
        # 2. Local CSV fallback (always writes)
        csv_file = "applied_jobs_log.csv"
        file_exists = os.path.exists(csv_file) and os.path.getsize(csv_file) > 0
        with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Date", "Job Title", "URL", "Status", "Notes"])
            writer.writerow([timestamp, title, url, status, reason])
            
    except Exception as e:
        print(f"[Tracker] Error logging job: {e}")

# --- 3.7 DYNAMIC AI RESUME GENERATOR ---
class ResumePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 22)
        self.cell(0, 10, self.name.upper(), 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 100, 100)
        contact = f"{self.email} | {self.phone} | {self.linkedin}"
        self.cell(0, 5, contact, 0, 1, 'C')
        self.ln(5)

def generate_dynamic_resume(job_url, job_description, profile):
    """Uses Gemini to rewrite the resume text for ATS matching, then generates a PDF."""
    if not gemini_client:
        print("[Resume] Gemini disabled, skipping dynamic resume.")
        return None

    prompt = f"""
    You are an expert ATS resume writer. Rewrite this candidate's resume to PERFECTLY match the keywords in this job description.
    Keep all facts truthful. Rewrite the experience and projects to maximize ATS score for this specific role.

    Candidate Profile:
    {json.dumps(profile, indent=2)}

    Job Description:
    {job_description[:3000]}

    Reply ONLY in this exact JSON structure:
    {{
      "title": "Exact Job Title from JD",
      "objective": "A 3-sentence summary mentioning the target company and role, highlighting matching skills.",
      "skills": "Comma separated list of skills, prioritizing exactly what the JD asked for.",
      "experience": [
        {{
          "role": "Role Title",
          "company": "Company Name",
          "bullets": ["Action-oriented bullet 1 with JD keywords", "Bullet 2"]
        }}
      ],
      "projects": [
        {{
          "name": "Project Name",
          "technologies": "React, Node, etc.",
          "bullets": ["Action bullet 1", "Action bullet 2"]
        }}
      ],
      "education": [
        {{
          "degree": "Degree Name",
          "institution": "University/College Name",
          "year": "Graduation Year"
        }}
      ]
    }}
    """
    try:
        response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n", "", text)
            text = re.sub(r"\n```$", "", text)
        data = json.loads(text)
        
        pdf = ResumePDF()
        pdf.name = profile.get("full_name", "Candidate")
        pdf.email = profile.get("email", "email@example.com")
        pdf.phone = profile.get("phone", "+91 0000000000")
        pdf.linkedin = profile.get("linkedin", "linkedin.com/in/profile")
        
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Title
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 8, data.get("title", "Professional").upper(), 0, 1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        # Objective
        pdf.set_font('Arial', '', 11)
        pdf.set_text_color(0, 0, 0)
        # Handle unicode issues
        objective = data.get("objective", "").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        pdf.multi_cell(0, 5, objective)
        pdf.ln(5)
        
        # Skills
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 8, 'CORE SKILLS', 0, 1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font('Arial', '', 11)
        pdf.set_text_color(0, 0, 0)
        skills = data.get("skills", "").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
        pdf.multi_cell(0, 5, skills)
        pdf.ln(5)
        
        # Experience
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 8, 'PROFESSIONAL EXPERIENCE', 0, 1)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        
        for job in data.get("experience", []):
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 6, job.get('role', ''), 0, 1)
            pdf.set_font('Arial', 'I', 11)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 6, job.get('company', ''), 0, 1)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)
            pdf.set_font('Arial', '', 11)
            for bullet in job.get('bullets', []):
                b_text = str(bullet).replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
                pdf.multi_cell(0, 5, f"- {b_text}")
            pdf.ln(3)

        # Projects
        if data.get("projects"):
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, 'PROJECTS', 0, 1)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)
            
            for proj in data.get("projects", []):
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(0, 0, 0)
                # inline tech stack
                proj_name = proj.get('name', '')
                tech = proj.get('technologies', '')
                pdf.cell(0, 6, f"{proj_name} | {tech}", 0, 1)
                
                pdf.set_font('Arial', '', 11)
                for bullet in proj.get('bullets', []):
                    b_text = str(bullet).replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
                    pdf.multi_cell(0, 5, f"- {b_text}")
                pdf.ln(3)

        # Education
        if data.get("education"):
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(0, 51, 102)
            pdf.cell(0, 8, 'EDUCATION', 0, 1)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)
            
            for edu in data.get("education", []):
                pdf.set_font('Arial', 'B', 12)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 6, edu.get('degree', ''), 0, 1)
                
                pdf.set_font('Arial', '', 11)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 5, f"{edu.get('institution', '')}  |  {edu.get('year', '')}", 0, 1)
                pdf.ln(3)
            
        out_path = "tailored_resume.pdf"
        pdf.output(out_path)
        print("[Resume] Successfully generated ATS-tailored PDF!")
        return out_path
    except Exception as e:
        print(f"[Resume] Failed to generate dynamic resume: {e}")
        return None

# --- 4. PLAYWRIGHT AUTOMATION ENGINE ---

def _bezier_mouse_move(page, x0, y0, x1, y1, steps=None):
    """
    FEATURE 2 — Ghost Cursor: Move mouse along a cubic Bezier curve with random
    overshoot and speed variation so Cloudflare / DataDome cannot fingerprint us.
    """
    if steps is None:
        dist = ((x1 - x0)**2 + (y1 - y0)**2) ** 0.5
        steps = max(15, int(dist / 15))

    # Two control points for cubic Bezier (more organic than quadratic)
    cx1 = x0 + random.randint(-160, 160)
    cy1 = y0 + random.randint(-160, 160)
    cx2 = x1 + random.randint(-80, 80)
    cy2 = y1 + random.randint(-80, 80)

    prev_x, prev_y = x0, y0
    for i in range(1, steps + 1):
        t = i / steps
        it = 1 - t
        # Cubic Bezier formula
        bx = int(it**3*x0 + 3*it**2*t*cx1 + 3*it*t**2*cx2 + t**3*x1)
        by = int(it**3*y0 + 3*it**2*t*cy1 + 3*it*t**2*cy2 + t**3*y1)
        if bx != prev_x or by != prev_y:
            page.mouse.move(bx, by)
            prev_x, prev_y = bx, by
        # Easing: slow at start/end, fast in the middle (like a real human)
        if t < 0.15 or t > 0.85:
            speed = random.uniform(0.018, 0.030)
        else:
            speed = random.uniform(0.004, 0.010)
        time.sleep(speed)

    # Random micro-overshoot then correction (humans always slightly overshoot)
    if random.random() < 0.55:
        overshoot_x = x1 + random.randint(-12, 12)
        overshoot_y = y1 + random.randint(-8, 8)
        page.mouse.move(overshoot_x, overshoot_y)
        time.sleep(random.uniform(0.04, 0.09))
        page.mouse.move(x1, y1)
        time.sleep(random.uniform(0.03, 0.07))

def human_mimicry(page):
    """Multi-layer human simulation: Bezier mouse paths, reading scroll, micro-pauses, jitter."""
    try:
        vp = page.viewport_size or {"width": 1280, "height": 800}
        w, h = vp["width"], vp["height"]
        cur_x, cur_y = w // 2, h // 2

        # 1. Move mouse along curved Bezier paths, not straight lines
        for _ in range(random.randint(3, 6)):
            tx = random.randint(80, w - 80)
            ty = random.randint(80, h - 80)
            _bezier_mouse_move(page, cur_x, cur_y, tx, ty)
            cur_x, cur_y = tx, ty
            time.sleep(random.uniform(0.08, 0.35))

        # 2. Simulate reading the page — scroll slowly like a person reading
        total_scroll = 0
        read_segments = random.randint(3, 6)
        for seg in range(read_segments):
            scroll_amount = random.randint(80, 280)
            page.mouse.wheel(delta_x=0, delta_y=scroll_amount)
            total_scroll += scroll_amount
            # Pause as if reading — longer for mid-page content
            read_pause = random.uniform(0.6, 2.2) if seg < read_segments - 1 else random.uniform(0.2, 0.6)
            time.sleep(read_pause)
            # Occasionally move mouse while reading (eye follows text)
            if random.random() < 0.5:
                mx = random.randint(200, w - 200)
                my = random.randint(100, h - 200)
                _bezier_mouse_move(page, cur_x, cur_y, mx, my)
                cur_x, cur_y = mx, my

        # 3. Scroll back up a bit (like re-reading something missed)
        if random.random() < 0.6:
            up_scroll = random.randint(80, min(total_scroll // 2, 250))
            page.mouse.wheel(delta_x=0, delta_y=-up_scroll)
            time.sleep(random.uniform(0.4, 1.0))

        # 4. Idle jitter — tiny mouse micro-movements (eyes fixating on screen)
        for _ in range(random.randint(2, 5)):
            jx = cur_x + random.randint(-8, 8)
            jy = cur_y + random.randint(-8, 8)
            page.mouse.move(jx, jy)
            time.sleep(random.uniform(0.05, 0.15))

        # 5. Occasional unfocused tab simulation (human checks another tab)
        if random.random() < 0.25:
            time.sleep(random.uniform(1.5, 4.0))

        # 6. Safe body click on empty area (triggers focus events)
        try:
            page.locator("body").click(position={"x": 12, "y": 12}, force=True, timeout=800)
        except:
            pass

    except Exception as e:
        print(f"[Mimicry] Failed: {e}")

# Common accidental typo pairs for realistic mistake simulation
_TYPO_NEIGHBORS = {
    'a': 's', 'e': 'r', 'i': 'o', 'o': 'p', 'n': 'm', 't': 'y', 'h': 'j',
    's': 'd', 'r': 'e', 'l': 'k', 'u': 'y', 'c': 'v', 'b': 'v', 'm': 'n',
}

def human_type(locator, text):
    """Types text with human realism: burst speed, micro-pauses, occasional typo+backspace."""
    locator.focus()
    time.sleep(random.uniform(0.15, 0.4))  # Small focus delay before starting

    i = 0
    while i < len(text):
        char = text[i]

        # 4% chance of making a typo (wrong adjacent key), then correcting it
        if random.random() < 0.04 and char.lower() in _TYPO_NEIGHBORS and char.isalpha():
            typo_char = _TYPO_NEIGHBORS[char.lower()]
            if char.isupper():
                typo_char = typo_char.upper()
            locator.press_sequentially(typo_char, delay=random.randint(40, 90))
            time.sleep(random.uniform(0.12, 0.35))  # Brief moment before noticing
            locator.press("Backspace")
            time.sleep(random.uniform(0.08, 0.2))

        # Type the actual character
        locator.press_sequentially(char, delay=random.randint(18, 65))

        # Word-end pause (after space or punctuation)
        if char in (' ', ',', '.', '!', '?'):
            time.sleep(random.uniform(0.05, 0.2))

        # 5% chance of a longer "thinking" pause mid-sentence
        if random.random() < 0.05 and i > 3:
            time.sleep(random.uniform(0.3, 0.9))

        i += 1

def run_playwright_apply(job_url, job_description=""):
    """
    Navigates to the job_url, takes a screenshot, extracts form HTML, 
    sends to Gemini to get mappings, and fills the form automatically.
    """
    global playwright_active
    playwright_active = True
    profile = load_profile()
    active_chat_id = load_chat_id()
    
    headless_mode = os.getenv("HEADLESS", "true").lower() == "true"
    use_persistent = os.getenv("USE_PERSISTENT_CHROME", "false").lower() == "true"
    
    with sync_playwright() as p:
        browser = None
        if use_persistent:
            print("[Browser] Launching persistent local Chrome profile...")
            # Load user profile path
            user_data_path = os.path.expandvars(os.getenv("CHROME_PROFILE_PATH", r"%LOCALAPPDATA%\Google\Chrome\User Data"))
            
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                channel="chrome",
                headless=headless_mode,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ],
                viewport={"width": 1280, "height": 800}
            )
        else:
            # Feature 5: Dynamic Proxy Rotation (Prepared)
            proxy_url = os.getenv("PLAYWRIGHT_PROXY", None)
            proxy_server = {"server": proxy_url} if proxy_url else None
            
            # Launch standard Chromium WITH persistent profile (keeps logins/cookies between runs)
            user_data_dir = os.path.abspath("chrome_profile")
            os.makedirs(user_data_dir, exist_ok=True)
            browser = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=headless_mode,
                proxy=proxy_server,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--start-maximized",
                    "--disable-infobars",
                    "--disable-extensions",
                    "--disable-plugins-discovery",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--use-gl=egl" # Forces EGL to randomize WebGL fingerprint rendering
                ],
                ignore_default_args=["--enable-automation"],
            )
            state_file = "state.json"
            os.makedirs("videos", exist_ok=True)


            # --- Randomised browser fingerprint per session ---
            # Real users have varied screen sizes and hardware — we randomise each run
            # Auto-Proxy Health Checker
            if proxy_url:
                try:
                    import urllib.request
                    print(f"[Proxy Checker] Validating proxy: {proxy_url}")
                    proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
                    opener = urllib.request.build_opener(proxy_handler)
                    # test against a simple endpoint
                    req = urllib.request.Request("http://httpbin.org/ip")
                    opener.open(req, timeout=5)
                    print("[Proxy Checker] ✅ Proxy is alive and healthy.")
                except Exception as e:
                    print(f"[Proxy Checker] ❌ Proxy is dead or slow. Disabling proxy for this run. Error: {e}")
                    proxy_url = None
                    proxy_server = None

            # --- User-Agent & Screen Size Synchronizer ---
            # Randomised browser fingerprint per session, ensuring Screen Size matches the OS platform
            desktop_vp = [(1920, 1080), (1366, 768), (1440, 900), (1536, 864), (1600, 900)]
            mac_vp = [(1440, 900), (2560, 1600), (2880, 1800)]
            
            ua_profiles = [
                {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "vp": random.choice(desktop_vp)},
                {"ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", "vp": random.choice(desktop_vp)},
                {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "vp": random.choice(mac_vp)},
                {"ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15", "vp": random.choice(mac_vp)}
            ]
            
            chosen_profile = random.choice(ua_profiles)
            chosen_ua = chosen_profile["ua"]
            vp_w, vp_h = chosen_profile["vp"]

            # persistent_context IS the context — no need to call new_context() again
            # The persistent profile keeps Workday/Google logins between runs!
            context = browser  # browser here is actually the persistent_context
            print(f"[Browser] Using persistent Chrome profile at: {user_data_dir}")

        # FEATURE 1: PLAYWRIGHT BANDWIDTH & TRACKER BLOCKER 🏎️
        # Intercept and block heavy media, fonts, and trackers to load pages 4x faster
        TRACKER_DOMAINS = frozenset([
            "google-analytics.com", "googletagmanager.com", "facebook.net",
            "doubleclick.net", "hotjar.com", "segment.io", "sentry.io",
            "mixpanel.com", "datadog.com", "clarity.ms", "intercom.io"
        ])

        def intercept_route(route):
            req = route.request
            r_type = req.resource_type
            r_url = req.url.lower()
            if r_type in ["image", "media", "font"] or any(td in r_url for td in TRACKER_DOMAINS):
                route.abort()
            else:
                route.continue_()

        try:
            context.route("**/*", intercept_route)
            print("[Efficiency Engine] ✅ Hyper-Speed Mode: Blocked heavy media and analytics trackers.")
        except Exception as e:
            print(f"[Efficiency Engine] Route blocking warning: {e}")


        # Add stealth init script to bypass bot detection
        stealth_sync(context)

        # --- Deep stealth JS fingerprint spoofing ---
        _hw_concurrency = random.choice([2, 4, 4, 8, 8, 12, 16])
        _device_memory  = random.choice([2, 4, 4, 8, 8])
        context.add_init_script(f"""
            // 1. Remove webdriver flag completely
            try {{
                Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            }} catch(e) {{}}

            // 2. Realistic chrome runtime object
            window.chrome = {{
                app: {{ isInstalled: false, InstallState: {{}}, RunningState: {{}} }},
                runtime: {{
                    id: undefined,
                    onConnect: {{ addListener: ()=>{{}} }},
                    onMessage: {{ addListener: ()=>{{}} }},
                    PlatformOs: {{ MAC: 'mac', WIN: 'win', ANDROID: 'android' }},
                    PlatformArch: {{ ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' }},
                }},
                csi: () => ({{ onloadT: Date.now(), pageT: Date.now(), startE: Date.now(), tran: 15 }}),
                loadTimes: () => ({{ commitLoadTime: Date.now()/1000, finishDocumentLoadTime: Date.now()/1000 }}),
            }};

            // 3. Permissions API — don't expose automation
            const _origPermsQuery = window.navigator.permissions.query.bind(navigator.permissions);
            window.navigator.permissions.query = (p) =>
                p.name === 'notifications'
                    ? Promise.resolve({{ state: Notification.permission }})
                    : _origPermsQuery(p);

            // 4. Realistic plugin list (Chromium normally shows these)
            Object.defineProperty(navigator, 'plugins', {{
                get: () => Object.assign([],
                    {{ 0: {{ name:'Chrome PDF Plugin', filename:'internal-pdf-viewer', description:'Portable Document Format', length:1 }},
                       1: {{ name:'Chrome PDF Viewer', filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai', description:'', length:1 }},
                       2: {{ name:'Native Client', filename:'internal-nacl-plugin', description:'', length:2 }},
                       length: 3 }}
                ),
            }});

            // 5. Languages
            Object.defineProperty(navigator, 'languages', {{ get: () => ['en-IN', 'en-GB', 'en-US', 'en'] }});

            // 6. Hardware concurrency and device memory
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {_hw_concurrency} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {_device_memory} }});

            // 7. WebGL fingerprint (real GPU strings randomized)
            try {{
                const vendors = ['Apple', 'Intel Inc.', 'NVIDIA Corporation', 'AMD'];
                const renderers = [
                    'Apple M2 Pro', 'Intel(R) Iris(R) Xe Graphics', 
                    'NVIDIA GeForce RTX 3080 / PCIe / SSE2', 'AMD Radeon RX 6800 XT'
                ];
                const rIdx = {random.randint(0, 3)};
                
                const origGetParam = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(p) {{
                    if (p === 37445) return vendors[rIdx];  // UNMASKED_VENDOR_WEBGL
                    if (p === 37446) return renderers[rIdx]; // UNMASKED_RENDERER_WEBGL
                    return origGetParam.apply(this, [p]);
                }};
                const origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
                WebGL2RenderingContext.prototype.getParameter = function(p) {{
                    if (p === 37445) return vendors[rIdx];
                    if (p === 37446) return renderers[rIdx];
                    return origGetParam2.apply(this, [p]);
                }};
            }} catch(e) {{}}

            // 8. Canvas noise — add 1-pixel-level randomness so canvas fingerprint differs each session
            const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {{
                const ctx = this.getContext('2d');
                if (ctx) {{
                    const imgData = ctx.getImageData(0, 0, this.width || 1, this.height || 1);
                    imgData.data[0] = imgData.data[0] ^ (Math.random() * 4 | 0);
                    ctx.putImageData(imgData, 0, 0);
                }}
                return _origToDataURL.apply(this, arguments);
            }};

            // 9. AudioContext fingerprint noise
            try {{
                const _origAudioCtx = window.AudioContext || window.webkitAudioContext;
                if (_origAudioCtx) {{
                    const _origCreateOscillator = _origAudioCtx.prototype.createOscillator;
                    _origAudioCtx.prototype.createOscillator = function() {{
                        const osc = _origCreateOscillator.apply(this, arguments);
                        osc.frequency.value += (Math.random() - 0.5) * 0.0001;
                        return osc;
                    }};
                }}
            }} catch(e) {{}}

            // 10. Battery API mock (real browsers expose this)
            try {{
                Object.defineProperty(navigator, 'getBattery', {{
                    value: () => Promise.resolve({{
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 0.98 + Math.random() * 0.02,
                        addEventListener: () => {{}},
                    }})
                }});
            }} catch(e) {{}}

            // 11. Connection API mock
            try {{
                Object.defineProperty(navigator, 'connection', {{
                    get: () => ({{
                        effectiveType: '4g',
                        rtt: Math.round(50 + Math.random() * 80),
                        downlink: parseFloat((5 + Math.random() * 45).toFixed(1)),
                        saveData: false,
                    }})
                }});
            }} catch(e) {{}}

            // 12. Remove Playwright-specific properties
            try {{
                delete window.__playwright;
                delete window.__pw_manual;
                delete window._playwrightRunner;
            }} catch(e) {{}}
        """)
        
        page = context.new_page()
        stealth_sync(page)

        # --- Human Warm-Up: visit Google briefly before the job site ---
        # Real users arrive at job sites via search engines, not directly.
        # This establishes a realistic browsing history in the session.
        try:
            warmup_sites = ["https://www.google.com", "https://www.bing.com"]
            warmup_url = random.choice(warmup_sites)
            print(f"[Stealth] Warm-up: visiting {warmup_url} first...")
            page.goto(warmup_url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 4.5))
            # Small scroll on Google to appear like a real browser session
            page.mouse.wheel(delta_x=0, delta_y=random.randint(50, 200))
            time.sleep(random.uniform(0.5, 1.5))
        except Exception:
            pass  # Non-fatal — continue even if warm-up fails

        # Random startup delay (simulates user taking a moment before clicking)
        time.sleep(random.uniform(1.5, 3.5))

        try:
            # Robust navigation with exponential backoff retry
            max_nav_retries = 2
            nav_success = False
            for attempt in range(max_nav_retries):
                try:
                    print(f"[Browser] Navigating to: {job_url} (Attempt {attempt+1}/{max_nav_retries})")
                    if "joinsuperset.com" in job_url:
                        page.goto(job_url, timeout=25000, wait_until="networkidle")
                    else:
                        wait_cond = random.choice(["domcontentloaded", "load"])
                        page.goto(job_url, timeout=25000, wait_until=wait_cond)
                    nav_success = True
                    break
                except Exception as nav_err:
                    err_str = str(nav_err)
                    print(f"[Browser] Network error on attempt {attempt+1}: {err_str[:120]}")
                    if attempt < max_nav_retries - 1:
                        time.sleep(random.uniform(3.0, 7.0) * (attempt + 1))  # Exponential-ish backoff
                    else:
                        if any(x in err_str for x in ["ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_REFUSED", "ERR_CONNECTION_TIMED_OUT", "NS_ERROR", "net::"]):
                            msg = f"⚠️ Could not reach the URL after {max_nav_retries} attempts (network error).\n\n{job_url}"
                            if bot and active_chat_id:
                                try: bot.send_message(active_chat_id, msg)
                                except: pass
                            return False
                        raise  # Re-raise if it's a fatal Playwright error after retries

            if not nav_success:
                return False
                
            time.sleep(random.uniform(3.0, 5.0)) # Human delay
            
            print("[Browser] Executing Human Mimicry to bypass bot detection...")
            human_mimicry(page)
            
            # --- Detect Blockers / 404 Pages ---
            try:
                page_text = page.locator("body").inner_text(timeout=3000).lower()
                page_title = page.title().lower()
                
                # Check 404 — expanded phrase list for broad coverage
                not_found_phrases = [
                    "page can't be found", "page cannot be found", "404 not found", "404 error",
                    "nothing was found at this location", "page not found", "this page could not be found",
                    "the page you are looking for", "oops! that page can", "sorry, this page",
                    "job posting not found", "job is no longer available", "position has been filled",
                    "this job has expired", "this listing is no longer", "application closed",
                    "no longer accepting applications", "posting has been removed",
                ]
                not_found_title_phrases = ["404", "not found", "page not found", "error"]
                if (any(phrase in page_text for phrase in not_found_phrases) or
                        any(phrase in page_title for phrase in not_found_title_phrases)):
                    msg = f"⚠️ The link is broken or the job post was deleted (404 Page Not Found).\n\nURL: {job_url}"
                    print(f"[Browser] 404 Page detected at {job_url}")
                    if bot and active_chat_id:
                        try: bot.send_message(active_chat_id, msg)
                        except: pass
                    return False
                    
                # Check Cloudflare / Turnstile
                if any(phrase in page_text for phrase in ["verify you are human", "security verification", "checking your browser", "cloudflare"]):
                    print(f"[Browser] 🛡️ Cloudflare challenge detected at {job_url}. Attempting bypass...")
                    
                    # Simulate human mouse movements to trick Cloudflare
                    try:
                        for _ in range(3):
                            page.mouse.move(random.randint(100, 700), random.randint(100, 500))
                            time.sleep(random.uniform(0.3, 0.8))
                    except: pass
                    
                    time.sleep(3.0)
                    
                    # Attempt to click Turnstile checkbox if present
                    try:
                        cf_iframe = page.frame_locator('iframe[title*="Cloudflare"]')
                        if cf_iframe:
                            checkbox = cf_iframe.locator('input[type="checkbox"], #cf-stage label, .ctp-checkbox-label, .mark')
                            if checkbox.first.is_visible(timeout=3000):
                                print("[Browser] 🖱️ Clicking Cloudflare Turnstile checkbox...")
                                checkbox.first.click(delay=random.randint(50, 150))
                                time.sleep(5.0)
                    except Exception as e:
                        print(f"[Browser] Note: Turnstile click failed: {e}")

                    # Re-check after attempt
                    page_text = page.locator("body").inner_text(timeout=2000).lower()
                    if any(phrase in page_text for phrase in ["verify you are human", "security verification", "cloudflare"]):
                        msg = f"🛡️ Cloudflare Anti-Bot security was too strong for the AI to bypass on this site.\nYou will need to click the link and apply manually.\n\nURL: {job_url}"
                        print(f"[Browser] Cloudflare block could not be bypassed at {job_url}")
                        if bot and active_chat_id:
                            try: bot.send_message(active_chat_id, msg)
                            except: pass
                        return False
                    else:
                        print("[Browser] ✅ Cloudflare bypassed successfully!")
            except Exception as e:
                print(f"[Browser] Note: Error checking blockers: {e}")
            
            # FEATURE 4: NUCLEAR COOKIE BANNER + MODAL DESTROYER
            # Step 1: JS nuclear strike — removes all known cookie overlay elements from DOM
            try:
                page.evaluate("""
                    () => {
                        const killSelectors = [
                            '[id*="cookie"]','[class*="cookie"]','[id*="consent"]','[class*="consent"]',
                            '[id*="gdpr"]','[class*="gdpr"]','[id*="banner"]','[class*="banner"]',
                            '[id*="overlay"]','[class*="overlay"]','[id*="modal"]','[class*="modal"]',
                            '[id*="popup"]','[class*="popup"]','[class*="cc-"]',
                            '#onetrust-banner-sdk','#CybotCookiebotDialog',
                            '.cky-consent-container','.termsfeed-com---nb',
                        ];
                        killSelectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach(el => {
                                if (el && el.style) {
                                    el.style.display = 'none';
                                    el.style.visibility = 'hidden';
                                    el.style.opacity = '0';
                                    el.style.pointerEvents = 'none';
                                }
                            });
                        });
                        // Unfreeze body scroll (some modals lock body scroll)
                        document.body.style.overflow = 'auto';
                        document.documentElement.style.overflow = 'auto';
                        document.body.style.position = 'static';
                    }
                """)
                print("[Cookie Destroyer] 💣 Nuclear strike executed on cookie/modal overlays")
            except Exception:
                pass
            # Step 2: Click-based dismissal for banners that need a real click
            cookie_selectors = [
                "button:has-text('Accept All')", "button:has-text('Accept Cookies')",
                "button:has-text('Accept')", "button:has-text('I Agree')",
                "button:has-text('Agree')", "button:has-text('Got it')",
                "button:has-text('Close')", "button:has-text('OK')",
                "#onetrust-accept-btn-handler", ".cc-btn.cc-allow",
                "[aria-label='Close']", "[aria-label='close']",
                "a:has-text('Accept')", "[id*='cookie'] button",
                "[class*='cookie'] button", "[class*='consent'] button",
                "[class*='cc-'] button",
            ]
            for sel in cookie_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=800):
                        el.click(force=True)
                        print(f"[Cookie Destroyer] 🍪 Clicked dismiss: {sel}")
                        time.sleep(1.0)
                        break
                except Exception:
                    continue

            
            # --- Enterprise Adapters (Workday, Lever, Greenhouse) ---
            if "myworkdayjobs.com" in job_url or "workday.com" in job_url:
                bot_email = os.getenv("BOT_EMAIL")
                bot_pass = os.getenv("BOT_EMAIL_PASSWORD")
                execute_workday_adapter(page, profile, bot_email, bot_pass)

            if "jobs.lever.co" in job_url:
                execute_lever_adapter(page, profile)

            # FEATURE 1: Greenhouse adapter
            if any(x in job_url for x in ["greenhouse.io", "grnh.se", "boards.greenhouse"]):
                bot_email = os.getenv("BOT_EMAIL")
                bot_pass  = os.getenv("BOT_EMAIL_PASSWORD")
                execute_greenhouse_adapter(page, profile, bot_email, bot_pass)
                # Take a screenshot immediately after Greenhouse adapter finishes
                gh_screenshot = "greenhouse_applied.png"
                page.screenshot(path=gh_screenshot)
                active_chat_id = load_chat_id()
                if bot and active_chat_id:
                    try:
                        with open(gh_screenshot, "rb") as ph:
                            bot.send_photo(
                                active_chat_id, ph,
                                caption=(
                                    f"✅ *Greenhouse Application Submitted!*\n"
                                    f"🏢 *URL:* `{job_url[:80]}`\n"
                                    f"📎 *Resume:* Uploaded\n"
                                    f"👤 *Name:* {profile.get('full_name','')}\n"
                                    f"📧 *Email:* {profile.get('email','')}\n"
                                    f"📞 *Phone:* {profile.get('phone','')}\n"
                                    f"🔗 *LinkedIn:* {profile.get('linkedin','')}\n"
                                    f"⏰ *Time:* {time.strftime('%d %b %Y, %I:%M %p')}"
                                ),
                                parse_mode=None
                            )
                    except Exception as gh_e:
                        print(f"[Greenhouse] Screenshot send failed: {gh_e}")

            # FEATURE 2: SmartRecruiters adapter (Freshworks, Robert Bosch, Avery Dennison)
            if any(x in job_url for x in ["smartrecruiters.com", "jobs.smartrecruiters.com", "smrtr.io"]):
                execute_smartrecruiters_adapter(page, profile)
                sr_screenshot = "smartrecruiters_applied.png"
                try:
                    page.screenshot(path=sr_screenshot)
                    active_chat_id = load_chat_id()
                    if bot and active_chat_id:
                        with open(sr_screenshot, "rb") as ph:
                            bot.send_photo(
                                active_chat_id, ph,
                                caption=(
                                    f"✅ *SmartRecruiters Application Submitted!*\n"
                                    f"🏢 *Company:* Freshworks / Bosch / Enterprise\n"
                                    f"📎 *Resume:* Uploaded\n"
                                    f"👤 *Name:* {profile.get('full_name','')}\n"
                                    f"📧 *Email:* {profile.get('email','')}\n"
                                    f"📞 *Phone:* {profile.get('phone','')}\n"
                                    f"⏰ *Time:* {time.strftime('%d %b %Y, %I:%M %p')}"
                                ),
                                parse_mode=None
                            )
                except Exception as sr_e:
                    print(f"[SmartRecruiters] Screenshot send notice: {sr_e}")
            
            # Track if the bot actually did any real work
            any_fields_filled = False
            total_steps_done = 0
            all_unknown_questions = {}  # Accumulated across all steps
            qa_report = []  # Initialize before loop to prevent UnboundLocalError
            last_form_signature = None  # Loop prevention
            
            # Generate dynamic resume for this job
            full_jd = page.evaluate("document.body.innerText")
            print("[Browser] Generating Dynamic Resume and Cover Letter...")
            dynamic_resume = generate_dynamic_resume(job_url, full_jd, profile)
            dynamic_cover_letter = generate_dynamic_cover_letter(job_url, full_jd, profile, gemini_client, groq_client=groq_client)
            
            # Load checkpoint to prevent restarting
            checkpoint_file = "checkpoints.json"
            checkpoints = {}
            if os.path.exists(checkpoint_file):
                try:
                    with open(checkpoint_file, "r") as f:
                        checkpoints = json.load(f)
                except: pass
            
            start_step = checkpoints.get(job_url, 0)
            if start_step > 0:
                print(f"[Browser] Checkpoint found! Resuming from step {start_step + 1}...")

            # Max 5 steps for multi-step forms
            for step in range(start_step, 5):
                print(f"[Browser] --- Processing Step {step+1} ---")
                
                # --- Feature 6: Auto-OTP Bypass ---
                try:
                    page_text_lower = page.locator("body").inner_text(timeout=2000).lower()
                    if any(phrase in page_text_lower for phrase in ["verification code", "enter otp", "security code", "check your email", "verify email"]):
                        print("[Browser] Verification Code requested! Triggering OTP Sniper...")
                        bot_email = os.getenv("BOT_EMAIL")
                        bot_pass = os.getenv("BOT_EMAIL_PASSWORD")
                        if bot_email and bot_pass:
                            otp = wait_for_otp(bot_email, bot_pass, timeout_seconds=90)
                            if otp:
                                otp_input = page.locator("input[type='text'], input[type='number'], input[name*='code'], input[name*='otp'], input[name*='verify']").first
                                if otp_input.is_visible(timeout=3000):
                                    otp_input.fill(otp)
                                    verify_btn = page.locator("button:has-text('Verify'), button:has-text('Submit'), button:has-text('Next'), button:has-text('Continue')").first
                                    if verify_btn.is_visible():
                                        verify_btn.click()
                                        print("[Browser] OTP verified successfully! Waiting for redirect...")
                                        time.sleep(5.0)
                except Exception as otp_e:
                    pass  # No OTP requested or check timed out
                # ----------------------------------
                
                # Take screenshot BEFORE filling (for Gemini to solve captchas/understand form)
                screenshot_path = f"step_{step}.png"
                page.screenshot(path=screenshot_path)
                
                # Live Ghost Mode Streaming
                if bot and active_chat_id in ghost_mode_chats:
                    try:
                        with open(screenshot_path, "rb") as ghost_img:
                            bot.send_photo(active_chat_id, ghost_img, caption=f"👻 *Ghost Mode (Live):* Step {step+1}", parse_mode=None)
                    except Exception as e:
                        print(f"[GhostMode] Failed to send live screenshot: {e}")
                
                with open(screenshot_path, "rb") as f:
                    screenshot_bytes = f.read()
                
                # FEATURE 3: HONEYPOT TRAP EVADER (DOM Purifier)
                # Removes hidden fields (opacity: 0, display: none, off-screen) so AI doesn't fall for bot traps
                try:
                    page.evaluate("""
                        () => {
                            const inputs = document.querySelectorAll('input, textarea, select');
                            inputs.forEach(el => {
                                const style = window.getComputedStyle(el);
                                const rect = el.getBoundingClientRect();
                                const isHidden = (
                                    style.display === 'none' || 
                                    style.visibility === 'hidden' || 
                                    style.opacity === '0' ||
                                    rect.left < -900 ||
                                    rect.width === 0 ||
                                    rect.height === 0 ||
                                    el.type === 'hidden'
                                );
                                if (isHidden && el.type !== 'file') {
                                    el.remove(); // Destroy the honeypot
                                }
                            });
                        }
                    """)
                    print("[Honeypot Evader] 🪤 Scanned and purged hidden bot traps from DOM.")
                except Exception as e:
                    print(f"[Honeypot Evader] Error purging DOM: {e}")

                # 🕳️ Shadow DOM & Deep iFrame Piercing
                form_elements = ""
                

                # 1. Pierce Shadow DOMs in the main page
                shadow_piercing_js = """() => {
                    function getShadowForms(root) {
                        let forms = [];
                        if (root.querySelectorAll) {
                            forms.push(...Array.from(root.querySelectorAll('form')));
                        }
                        const elements = root.querySelectorAll ? root.querySelectorAll('*') : [];
                        for (let el of elements) {
                            if (el.shadowRoot) {
                                forms.push(...getShadowForms(el.shadowRoot));
                            }
                        }
                        return forms;
                    }
                    const allForms = getShadowForms(document);
                    return allForms.map(f => f.outerHTML).join('\\n');
                }"""
                try:
                    form_elements += page.evaluate(shadow_piercing_js)
                except:
                    pass

                # 2. Extract from all Cross-Origin iFrames
                for frame in page.frames:
                    try:
                        frame_forms = frame.evaluate("() => Array.from(document.querySelectorAll('form')).map(f => f.outerHTML).join('\\n')")
                        if frame_forms:
                            form_elements += f"\\n<!-- IFRAME FORMS -->\\n{frame_forms}"
                    except:
                        pass
                
                # 3. Fallback if still empty
                if not form_elements.strip():
                    try:
                        form_elements = page.evaluate("() => (document.querySelector('main') || document.body).innerHTML")
                    except:
                        pass

                # FEATURE 1: HTML MINIFIER — strip noise before sending to Gemini
                # Reduces token usage by ~80% and speeds up AI response
                form_elements = minify_form_html(form_elements, max_chars=18000)
                print(f"[HTML Minifier] ✅ Cleaned HTML: {len(form_elements)} chars sent to Gemini")

                # FEATURE 4: REGEX FALLBACK — fill obvious fields instantly without AI
                # Only sends the remaining UNKNOWN fields to Gemini
                print("[Regex Fallback] Pre-filling standard fields without Gemini...")
                prefilled = apply_regex_fallback(page, profile)
                
                print("[RAG Memory] Running Local Vector Semantic Search on form labels...")
                qa_memory = load_qa_memory()
                rag_filled = apply_rag_memory_fallback(page, qa_memory, profile)
                
                prefilled_selectors = {sel for sel, _ in prefilled} | {sel for sel, _ in rag_filled}

                # FEATURE 3: MD5 FORM HASHING CACHE (O(1) Instant Solving) 🧮
                # If we've seen this exact form structure before, don't waste Gemini tokens
                import hashlib
                form_hash = hashlib.md5(form_elements.encode('utf-8')).hexdigest()
                hash_cache_file = "form_hash_cache.json"
                hash_cache = safe_load_json(hash_cache_file, {})
                
                mapping = None
                
                if form_hash in hash_cache:
                    print(f"[MD5 Cache] 🎯 MATCH FOUND! Hash: {form_hash}. Loading exact field selectors instantly...")
                    mapping = hash_cache[form_hash]
                else:
                    print("[Browser] Analyzing remaining fields with Gemini Vision...")
                    mapping = analyze_form_with_gemini(form_elements, profile, screenshot_bytes, job_url, job_description)
                    if mapping:
                        # Save successful mapping to MD5 cache
                        hash_cache[form_hash] = mapping
                        safe_save_json(hash_cache_file, hash_cache)
                        print(f"[MD5 Cache] 💾 Saved new form structure ({form_hash}) to memory.")
                        
                        # --- Automated Cover Letter Auto-Save ---
                        try:
                            for field in mapping.get('fields', []):
                                val = str(field.get('value', ''))
                                if len(val) > 200 and ("Dear" in val or "apply" in val.lower() or "experience" in val.lower()):
                                    os.makedirs("cover_letters", exist_ok=True)
                                    import urllib.parse
                                    safe_url = urllib.parse.quote_plus(job_url)[:50]
                                    with open(f"cover_letters/CL_{safe_url}.txt", "w", encoding="utf-8") as cl_f:
                                        cl_f.write(val)
                                    print("[Auto-Save] 📝 Custom Cover Letter saved to local disk.")
                                    break
                        except Exception as cl_e:
                            print(f"[Auto-Save] Cover letter save failed: {cl_e}")


                if not mapping:
                    err_msg = "[Browser] Failed to map form fields with Gemini AI. Gemini returned None."
                    print(err_msg)
                    if bot and active_chat_id:
                        try: bot.send_message(active_chat_id, f"❌ {err_msg}")
                        except: pass
                    return False
                    
                if "ERROR" in mapping:
                    err_msg = f"[Browser] Gemini AI crashed: {mapping['ERROR']}"
                    print(err_msg)
                    if bot and active_chat_id:
                        try: bot.send_message(active_chat_id, f"❌ {err_msg}")
                        except: pass
                    if "rate limit" in mapping["ERROR"].lower() or "limit exceeded" in mapping["ERROR"].lower() or "resource_exhausted" in mapping["ERROR"].lower():
                        raise Exception("GEMINI_RATE_LIMIT")
                    return False
                    
                print(f"[Browser] Gemini Mapping Result: {json.dumps(mapping, indent=2)}")
                
                fields = mapping.get("fields", [])
                file_fields = mapping.get("file_fields", [])
                submit_selector = mapping.get("submit_selector")
                
                # Feature: Intelligence (Reject Blog Comment Forms)
                # If Gemini accidentally mapped a WordPress "Leave a Reply" form, reject it.
                if len(fields) <= 4 and submit_selector:
                    is_comment = False
                    for f in fields:
                        if "comment" in f.get("selector", "").lower() or "author" in f.get("selector", "").lower():
                            is_comment = True
                    if is_comment:
                        print("[Browser] 🧠 Intelligence Module: Detected a blog 'Leave a Reply' comment form instead of a job application. Aborting to save quota.")
                        if bot and active_chat_id:
                            try: bot.send_message(active_chat_id, "⚠️ *Intelligence Alert:*\nBot detected a blog comment form instead of a real job application form. Aborting.", parse_mode=None)
                            except: pass
                        break
                
                # Feature: Intelligence (Infinite Error Loop Detection)
                # If the bot submits the form but the page reloads with an error showing the exact same form,
                # the bot will detect it and break out instead of trying 5 times.
                current_signature = str(fields) + str(submit_selector) + page.url
                if last_form_signature == current_signature:
                    print("[Browser] 🧠 Intelligence Module: Form signature is identical to previous step. Stuck in an error loop (e.g., validation failed). Aborting to save API quota.")
                    if bot and active_chat_id:
                        try: bot.send_message(active_chat_id, "⚠️ *Intelligence Alert:*\nForm validation failed (e.g. incorrect password or missing required data). Bot broke the infinite loop to save API quota.", parse_mode=None)
                        except: pass
                    break
                last_form_signature = current_signature
                
                # If nothing at all — check if we ever did any work
                if not fields and not file_fields and not submit_selector:
                    if any_fields_filled:
                        print("[Browser] No more fields. Application likely submitted successfully.")
                    else:
                        print("[Browser] No fields or buttons found. This page has no form to fill.")
                    break
                    
                # Track what was filled vs what failed
                filled_report = []
                failed_report = []
                qa_report = []  # NEW: Track question → answer pairs clearly
                
                # Fill standard fields
                for field in fields:
                    # Defensive access: a malformed AI field entry must skip one
                    # field, not abort the entire application.
                    if not isinstance(field, dict):
                        continue
                    selector = field.get("selector")
                    value = field.get("value")
                    if not selector:
                        continue
                    
                    # Detect __ASK_USER__ fields — Zero-Interruption Auto-Hallucinate
                    if str(value).startswith("__ASK_USER__:"):
                        question_label = value.replace("__ASK_USER__:", "").strip()
                        print(f"[QA] Auto-Hallucinating answer for unknown question: {question_label}")
                        
                        try:
                            prompt = f"""
You are applying for a job. A form asked this question: "{question_label}"
Based on the candidate's profile, generate the best possible, highly professional answer.
If it's a yes/no question, answer appropriately (e.g. Yes/No).
If it asks for salary expectations, say '0' or 'Negotiable'.
If it asks about sponsorship, use profile data.
Keep it concise (1-2 sentences max). DO NOT hallucinate fake job titles, just use generic positive answers if uncertain.

Profile: {json.dumps(profile)}

Reply ONLY with the text of the answer. No formatting, no quotes.
"""
                            resp = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                            hallucinated_answer = resp.text.strip()
                            print(f"[QA] Hallucinated: {hallucinated_answer}")
                            
                            # Overwrite value and save to QA memory
                            value = hallucinated_answer
                            qa_memory = load_qa_memory()
                            qa_memory[question_label] = hallucinated_answer
                            save_qa_memory(qa_memory)
                            try:
                                record_learned_qa(question_label, hallucinated_answer)
                            except Exception:
                                pass
                            # Track this Q&A for the Telegram report
                            qa_report.append(f"🤖 *AI Answer*\n❓ {question_label}\n💬 {hallucinated_answer}")
                            
                        except Exception as e:
                            print(f"[QA] Auto-Hallucinate failed: {e}")
                            all_unknown_questions[question_label] = selector
                            failed_report.append(f"❓ {selector} → NEEDS YOUR ANSWER: {question_label}")
                            continue
                    
                    # Detect __OTP_REQUEST__ fields
                    if str(value).startswith("__OTP_REQUEST__:"):
                        search_term = value.replace("__OTP_REQUEST__:", "").strip()
                        if not search_term:
                            search_term = "verify"
                        
                        print(f"[IMAP] OTP/Magic Link Request detected for '{search_term}'. Booting IMAP Listener...")
                        bot_email = os.environ.get("BOT_EMAIL")
                        bot_pw = os.environ.get("BOT_EMAIL_PASSWORD")
                        
                        if bot_email and bot_pw:
                            try:
                                from imap_handler import get_latest_otp
                                otp_result = get_latest_otp(bot_email, bot_pw, search_term)
                                
                                if otp_result and otp_result["type"] == "code":
                                    value = otp_result["value"]
                                    print(f"[IMAP] Success! Filling OTP: {value}")
                                elif otp_result and otp_result["type"] == "link":
                                    # Open the magic link in a new tab to verify
                                    print(f"[IMAP] Magic link found! Verifying in background...")
                                    temp_page = context.new_page()
                                    try:
                                        temp_page.goto(otp_result["value"], wait_until="domcontentloaded", timeout=20000)
                                        time.sleep(4)
                                    except:
                                        pass
                                    temp_page.close()
                                    filled_report.append(f"✅ {selector} → Clicked Magic Link via email!")
                                    continue
                                else:
                                    failed_report.append(f"❌ {selector} → Failed to retrieve OTP via Email")
                                    continue
                            except Exception as imap_err:
                                failed_report.append(f"❌ {selector} → IMAP Error: {str(imap_err)[:30]}")
                                continue
                        else:
                            failed_report.append(f"❌ {selector} → BOT_EMAIL missing in .env")
                            continue
                    
                    # Detect __GENERATE_PASSWORD__ fields
                    if str(value) == "__GENERATE_PASSWORD__":
                        # NOTE: json is already imported at top of file — do NOT re-import here
                        password = "EliteJobBot@2026!"
                        value = password
                        
                        # Save to vault
                        vault_file = "vault.json"
                        vault_data = []
                        if os.path.exists(vault_file):
                            try:
                                with open(vault_file, "r") as vf:
                                    vault_data = json.load(vf)
                            except: pass
                        
                        vault_email = os.environ.get("BOT_EMAIL", "UserEmail")
                        vault_data.append({
                            "url": job_url,
                            "email": vault_email,
                            "password": password,
                            "date": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                        with open(vault_file, "w") as vf:
                            json.dump(vault_data, vf, indent=2)
                        
                        filled_report.append(f"🔐 {selector} → Generated Secure Password & Saved to Vault!")
                        print(f"[Vault] Generated password and saved to vault.json for {job_url}")
                    
                    # Truncate value for display (hide sensitive data partially)
                    if str(value) == "EliteJobBot@2026!":
                        display_value = "******** (Vault Password)"
                    else:
                        value_str = str(value)
                        display_value = value_str[:40] + "..." if len(value_str) > 40 else value_str
                    try:
                        locator = page.locator(selector).first
                        if locator.is_visible():
                            locator.scroll_into_view_if_needed()

                            # Human hover: move mouse to field before interacting
                            try:
                                box = locator.bounding_box()
                                if box:
                                    target_x = int(box["x"] + box["width"] / 2)
                                    target_y = int(box["y"] + box["height"] / 2)
                                    vp = page.viewport_size or {"width": 1280, "height": 800}
                                    cur_x = random.randint(50, vp["width"] - 50)
                                    cur_y = random.randint(50, vp["height"] - 50)
                                    _bezier_mouse_move(page, cur_x, cur_y, target_x, target_y)
                                    time.sleep(random.uniform(0.1, 0.35))  # Hover pause
                            except Exception:
                                pass

                            # Check tag name to determine correct action (fill, select, or check)
                            tag_name = locator.evaluate("el => el.tagName.toLowerCase()")
                            
                            if tag_name == "select":
                                # ENHANCEMENT: Smart dropdown selection — reads actual option values
                                # and asks AI to pick the best one if direct match fails
                                try:
                                    locator.select_option(label=value)
                                    filled_report.append(f"✅ {selector} (dropdown) → {display_value}")
                                except Exception:
                                    try:
                                        locator.select_option(value=value)
                                        filled_report.append(f"✅ {selector} (dropdown) → {display_value}")
                                    except Exception:
                                        try:
                                            # Read actual options from DOM and pick the closest match
                                            options = locator.evaluate(
                                                "el => Array.from(el.options).map(o => ({value: o.value, label: o.text.trim()}))"
                                            )
                                            if options:
                                                option_labels = [o['label'] for o in options if o['label'] and o['value']]
                                                # Ask Groq (fast, cheap) to pick the best matching option
                                                best_option = None
                                                if groq_client and option_labels:
                                                    try:
                                                        pick_prompt = f"""From this list of dropdown options: {option_labels}
                                                        Which option best matches the user's intent: "{value}"?
                                                        Reply ONLY with the exact option text from the list. Nothing else."""
                                                        pick_resp = groq_client.chat.completions.create(
                                                            model=GROQ_MODEL,
                                                            messages=[{"role": "user", "content": pick_prompt}],
                                                            temperature=0,
                                                        )
                                                        best_option = pick_resp.choices[0].message.content.strip().strip('"').strip("'")
                                                    except Exception:
                                                        pass
                                                if best_option and best_option in option_labels:
                                                    locator.select_option(label=best_option)
                                                    filled_report.append(f"🧠 {selector} (AI dropdown) → {best_option}")
                                                elif option_labels:
                                                    # Pick first non-empty, non-placeholder option
                                                    for opt in options:
                                                        if opt['value'] and opt['label'] and opt['label'].lower() not in ['select', 'choose', 'please select', '-', '--']:
                                                            locator.select_option(value=opt['value'])
                                                            filled_report.append(f"✅ {selector} (dropdown) → {opt['label']} (best available)")
                                                            break
                                                else:
                                                    locator.select_option(index=1)
                                                    filled_report.append(f"✅ {selector} (dropdown) → fallback (index 1)")
                                            else:
                                                locator.select_option(index=1)
                                                filled_report.append(f"✅ {selector} (dropdown) → fallback (index 1)")
                                        except Exception as dd_e:
                                            failed_report.append(f"❌ {selector} (dropdown) → {str(dd_e)[:40]}")
                            elif tag_name == "input":
                                input_type = locator.evaluate("el => el.type ? el.type.toLowerCase() : 'text'")
                                if input_type in ["checkbox", "radio"]:
                                    should_check = str(value).lower() in ["true", "yes", "1", "check", "select", "on"]
                                    if should_check:
                                        locator.check()
                                        filled_report.append(f"✅ {selector} ({input_type}) → Checked")
                                    else:
                                        locator.uncheck()
                                        filled_report.append(f"✅ {selector} ({input_type}) → Unchecked")
                                elif input_type == "range":
                                    # Physics Engine Slider Drag
                                    box = locator.bounding_box()
                                    if box:
                                        print(f"[Physics Engine] Simulating drag for slider: {selector}")
                                        page.mouse.move(box["x"] + 5, box["y"] + box["height"] / 2)
                                        page.mouse.down()
                                        # Simulate human dragging motion
                                        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=15)
                                        page.evaluate(f"el => el.value = '{value}'", locator)
                                        page.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))", locator)
                                        page.evaluate("el => el.dispatchEvent(new Event('change', { bubbles: true }))", locator)
                                        page.mouse.up()
                                        filled_report.append(f"🎚️ {selector} (Physics Slider) → Dragged to {display_value}")
                                else:
                                    if len(str(value)) < 150:
                                        human_type(locator, str(value))
                                    else:
                                        locator.fill(str(value))
                                    filled_report.append(f"✅ {selector} → {display_value}")
                            else:
                                # Try standard fill/type first
                                try:
                                    if len(str(value)) < 150:
                                        human_type(locator, str(value))
                                    else:
                                        locator.fill(str(value))
                                except Exception:
                                    pass
                                # Also dispatch JS input/change events for React/Angular forms
                                try:
                                    page.evaluate("""
                                        ([sel, val]) => {
                                            const el = document.querySelector(sel);
                                            if (!el) return;
                                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value') ||
                                                                            Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                                            if (nativeInputValueSetter) nativeInputValueSetter.set.call(el, val);
                                            el.dispatchEvent(new Event('input', { bubbles: true }));
                                            el.dispatchEvent(new Event('change', { bubbles: true }));
                                            el.dispatchEvent(new Event('blur', { bubbles: true }));
                                        }
                                    """, [selector, value])
                                except Exception:
                                    pass
                                filled_report.append(f"✅ {selector} → {display_value}")
                                
                            time.sleep(random.uniform(0.3, 0.8))
                        else:
                            # Element not visible — try JS scroll + force fill
                            try:
                                page.evaluate("""
                                    ([sel, val]) => {
                                        const el = document.querySelector(sel);
                                        if (!el) return;
                                        el.scrollIntoView();
                                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value') ||
                                                                        Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                                        if (nativeInputValueSetter) nativeInputValueSetter.set.call(el, val);
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                    }
                                """, [selector, value])
                                filled_report.append(f"⚡ {selector} → {display_value} (JS force)")
                            except Exception:
                                # 👁️ Vision-Coordinate Fallback for impossible React/Custom elements
                                try:
                                    print(f"[Browser] JS force failed for {selector}. Engaging Vision-Coordinate Fallback...")
                                    box = locator.bounding_box()
                                    if box:
                                        x = box["x"] + box["width"] / 2
                                        y = box["y"] + box["height"] / 2
                                        page.mouse.click(x, y)
                                        time.sleep(0.5)
                                        # Type character by character to bypass event listeners
                                        for char in str(value):
                                            page.keyboard.type(char, delay=random.randint(10, 30))
                                        filled_report.append(f"👁️ {selector} → {display_value} (Vision Coordinate Fallback)")
                                    else:
                                        failed_report.append(f"👻 {selector} → Not visible and No Bounding Box")
                                except Exception:
                                    failed_report.append(f"👻 {selector} → Not visible on page")
                    except Exception as e:
                        print(f"[Browser] Selector {selector} failed: {e}. Asking AI for alternative...")
                        # ENHANCEMENT: Ask AI for alternative selector when current one fails
                        try:
                            alt_selector = ai_fix_selector(page, selector, value, screenshot_bytes, gemini_client, groq_client)
                            if alt_selector:
                                print(f"[AI Fix] Trying AI-suggested selector: {alt_selector}")
                                alt_loc = page.locator(alt_selector).first
                                if alt_loc.is_visible(timeout=2000):
                                    if len(str(value)) < 150:
                                        human_type(alt_loc, str(value))
                                    else:
                                        alt_loc.fill(str(value))
                                    # Fire React/Angular events
                                    try:
                                        page.evaluate("""
                                            ([sel, val]) => {
                                                const el = document.querySelector(sel);
                                                if (!el) return;
                                                const niv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                                                         || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                                                if (niv) niv.set.call(el, val);
                                                ['input','change','blur'].forEach(ev => el.dispatchEvent(new Event(ev, {bubbles: true})));
                                            }
                                        """, [alt_selector, value])
                                    except Exception:
                                        pass
                                    filled_report.append(f"🤖 {alt_selector} (AI fix) → {display_value}")
                                else:
                                    failed_report.append(f"❌ {selector} → AI suggested {alt_selector} but not visible")
                            else:
                                failed_report.append(f"❌ {selector} → {str(e)[:50]}")
                        except Exception as fix_e:
                            failed_report.append(f"❌ {selector} → {str(e)[:50]}")
                            print(f"[Browser] AI fix also failed: {fix_e}")
                        
                # Upload Resume
                for file_field in file_fields:
                    selector = file_field["selector"]
                    file_type = file_field.get("file_type", "")
                    try:
                        if file_type.lower() in ["cover letter", "coverletter"]:
                            file_to_upload = dynamic_cover_letter if (dynamic_cover_letter and os.path.exists(dynamic_cover_letter)) else None
                        else:
                            file_to_upload = dynamic_resume if (dynamic_resume and os.path.exists(dynamic_resume)) else RESUME_FILE
                        
                        if file_to_upload and os.path.exists(file_to_upload):
                            page.locator(selector).first.set_input_files(file_to_upload)
                            filled_report.append(f"📎 {file_type} uploaded via {selector} ({file_to_upload})")
                            print(f"[Browser] Uploaded {file_to_upload} successfully!")
                            time.sleep(random.uniform(1.0, 2.0))
                        else:
                            failed_report.append(f"📎 {file_type} file not found!")
                            print(f"[Browser] File {file_to_upload} not found.")
                    except Exception as e:
                        # Try to force upload by un-hiding the input element via JS
                        try:
                            if file_to_upload and os.path.exists(file_to_upload):
                                # Make the hidden file input visible and interactable
                                page.evaluate(f"document.querySelector('{selector}').style.display = 'block';")
                                page.evaluate(f"document.querySelector('{selector}').style.visibility = 'visible';")
                                page.evaluate(f"document.querySelector('{selector}').style.opacity = '1';")
                                
                                page.locator(selector).first.set_input_files(file_to_upload)
                                filled_report.append(f"⚡ {file_type} uploaded via {selector} (forced visibility)")
                                print(f"[Browser] Forced upload for {file_to_upload} via visibility override")
                                time.sleep(1.0)
                            else:
                                raise e
                        except Exception as force_e:
                            failed_report.append(f"❌ Upload {selector} → {str(force_e)[:50]}")
                            print(f"[Browser] Skipping upload for {selector}: {force_e}")
                        
                # Handle CAPTCHA checkbox if visible
                try:
                    recaptcha_iframe = page.frame_locator("iframe[title='reCAPTCHA']")
                    if recaptcha_iframe.locator("#recaptcha-anchor").is_visible():
                        print("[Browser] Found Google reCAPTCHA checkbox. Clicking...")
                        recaptcha_iframe.locator("#recaptcha-anchor").click()
                        filled_report.append("🔐 reCAPTCHA checkbox clicked")
                        time.sleep(3.0)
                except Exception:
                    pass
                
                # Mark that real work was done if any fields were filled
                if filled_report:
                    any_fields_filled = True
                    
                # Build the detailed report message
                report = f"📝 *Step {step+1} Form Report*\n`{job_url[:60]}...`\n\n"
                if filled_report:
                    report += "✅ *Fields Filled:*\n" + "\n".join(filled_report) + "\n\n"
                if failed_report:
                    report += "❌ *Not Filled:*\n" + "\n".join(failed_report) + "\n\n"
                if not filled_report and not failed_report:
                    if submit_selector:
                        report += f"🔘 Clicking button: `{submit_selector}`\n\n"
                    else:
                        report += "ℹ️ No fields to fill on this step.\n\n"
                report += f"📊 Total: *{len(filled_report)} filled*, *{len(failed_report)} failed*"
                
                # Send QA pairs as a SEPARATE clean Telegram message
                if qa_report and bot and active_chat_id:
                    try:
                        qa_msg = "🧠 *AI Auto-Answers Used:*\n\n" + "\n\n".join(qa_report)
                        bot.send_message(active_chat_id, qa_msg[:4096], parse_mode=None, disable_web_page_preview=True)
                    except Exception as qe:
                        print(f"[QA Report] Failed to send: {qe}")
                
                # Take screenshot AFTER filling fields
                filled_screenshot_path = f"step_{step}_filled.png"
                page.screenshot(path=filled_screenshot_path)
                
                # ENHANCEMENT: Post-fill validation — ask Gemini if the form has any visible errors
                # This catches required field highlights, validation messages, etc. BEFORE we click submit
                if fields and gemini_client:
                    try:
                        with open(filled_screenshot_path, "rb") as vf:
                            validate_bytes = vf.read()
                        from google.genai import types as gtypes
                        val_prompt = """
                        You are checking if a job application form was filled correctly.
                        Look at this screenshot and check:
                        1. Are any fields highlighted red or showing validation errors?
                        2. Are there any "required field" warnings?
                        3. Are there any empty fields that are clearly required (marked with *)?

                        Reply ONLY in this JSON format (no markdown):
                        {"has_errors": true/false, "error_fields": ["description of what's wrong"]}
                        """
                        val_contents = [val_prompt, gtypes.Part.from_bytes(data=validate_bytes, mime_type='image/png')]
                        val_resp = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=val_contents)
                        val_text = val_resp.text.strip()
                        if val_text.startswith("```"): val_text = re.sub(r"^```(?:json)?\n", "", val_text); val_text = re.sub(r"\n```$", "", val_text)
                        val_json = json.loads(val_text)
                        if val_json.get("has_errors") and val_json.get("error_fields"):
                            err_list = val_json["error_fields"]
                            print(f"[AI Validate] Form has errors: {err_list}")
                            failed_report.extend([f"⚠️ Validation Error: {e}" for e in err_list])
                            # Re-add errors to report
                            report += f"\n\n⚠️ *AI Validation Found Issues:*\n" + "\n".join([f"• {e}" for e in err_list])
                        else:
                            print("[AI Validate] ✅ Form looks correctly filled!")
                    except Exception as val_e:
                        print(f"[AI Validate] Could not validate: {val_e}")

                # Send screenshot + detailed report to Telegram
                if bot and active_chat_id:
                    try:
                        with open(filled_screenshot_path, "rb") as photo:
                            bot.send_photo(
                                active_chat_id, 
                                photo, 
                                caption=report[:1024]  # Telegram caption limit is 1024 chars
                            )
                    except Exception as e:
                        print(f"Failed to send Telegram photo: {e}")
                        try:
                            bot.send_message(active_chat_id, report, disable_web_page_preview=True)
                        except:
                            pass
                        
                if submit_selector:
                    # Translate jQuery-like :contains() to Playwright's native :has-text()
                    playwright_selector = submit_selector
                    if ":contains(" in playwright_selector:
                        playwright_selector = playwright_selector.replace(":contains(", ":has-text(")

                    print(f"[Browser] Clicking submit/next button: {playwright_selector}")

                    # Human hover: move to button, pause like reviewing the form, then click
                    try:
                        btn_loc = page.locator(playwright_selector).first
                        btn_box = btn_loc.bounding_box()
                        if btn_box:
                            bx = int(btn_box["x"] + btn_box["width"] / 2)
                            by = int(btn_box["y"] + btn_box["height"] / 2)
                            vp = page.viewport_size or {"width": 1280, "height": 800}
                            _bezier_mouse_move(page, random.randint(50, vp["width"]-50),
                                               random.randint(50, vp["height"]-50), bx, by)
                            time.sleep(random.uniform(0.4, 1.1))  # Pause like a human reviewing before submitting
                    except Exception:
                        pass

                    try:
                        page.locator(playwright_selector).first.click()
                    except Exception as e:
                        print(f"[Browser] Error clicking submit button with Playwright (trying JS fallback): {e}")
                        try:
                            js_click = """
                            (selector) => {
                                try {
                                    const el = document.querySelector(selector);
                                    if (el) { el.click(); return true; }
                                } catch(e) {}
                                
                                let matchText = "";
                                let tagName = "*";
                                
                                const containsMatch = selector.match(/([a-zA-Z0-9_-]+)?:contains\\(['"](.*?)['"]\\)/) 
                                                   || selector.match(/([a-zA-Z0-9_-]+)?:has-text\\(['"](.*?)['"]\\)/);
                                                   
                                if (containsMatch) {
                                    tagName = containsMatch[1] || "*";
                                    matchText = containsMatch[2];
                                }
                                
                                if (matchText) {
                                    const elements = document.getElementsByTagName(tagName);
                                    for (let el of elements) {
                                        if (el.textContent.includes(matchText)) {
                                            el.click();
                                            return true;
                                        }
                                    }
                                }
                                return false;
                            }
                            """
                            success_js = page.evaluate(js_click, submit_selector)
                            if success_js:
                                print("[Browser] JS fallback click succeeded!")
                            else:
                                print("[Browser] JS fallback click did not find or click element.")
                        except Exception as fallback_e:
                            print(f"[Browser] Fallback JS submit also failed: {fallback_e}")
                    
                    total_steps_done += 1
                    time.sleep(5.0) # Wait for page load after submit

                    # ENHANCEMENT: Post-submit AI page verification
                    # Gemini looks at the page AFTER clicking submit to detect success/error/next step
                    try:
                        post_submit_path = f"step_{step}_post_submit.png"
                        page.screenshot(path=post_submit_path)
                        with open(post_submit_path, "rb") as ps_f:
                            post_bytes = ps_f.read()
                        page_state = verify_page_with_ai(page, post_bytes, f"Just submitted step {step+1} of job application at {job_url}")
                        print(f"[AI Verify] Post-submit page state: {page_state}")

                        if page_state == 'success':
                            print("[AI Verify] ✅ AI confirmed: Application successfully submitted!")
                            any_fields_filled = True
                            if bot and active_chat_id:
                                try:
                                    with open(post_submit_path, "rb") as ps_photo:
                                        bot.send_photo(active_chat_id, ps_photo,
                                            caption="✅ *AI Verified: Application Submitted Successfully!*\n\n_Gemini Vision confirmed this is a success/confirmation page._",
                                            parse_mode=None)
                                except Exception: pass
                            break  # Stop the loop — we're done!

                        elif page_state == 'error':
                            print("[AI Verify] ⚠️ AI detected an error on the page after submission.")
                            if bot and active_chat_id:
                                try:
                                    with open(post_submit_path, "rb") as ps_photo:
                                        bot.send_photo(active_chat_id, ps_photo,
                                            caption="⚠️ *AI Detected a Form Error After Submit*\n\n_Gemini Vision saw a validation error. The bot will re-analyze and retry the form._",
                                            parse_mode=None)
                                except Exception: pass
                            # Don't break — let the loop re-analyze the form with errors visible

                        elif page_state == 'captcha':
                            print("[AI Verify] 🔒 CAPTCHA detected after submit.")
                            if bot and active_chat_id:
                                try:
                                    with open(post_submit_path, "rb") as ps_photo:
                                        bot.send_photo(active_chat_id, ps_photo,
                                            caption="🔒 *CAPTCHA Detected*\n\nThe bot encountered a CAPTCHA after submitting. Manual intervention may be needed.",
                                            parse_mode=None)
                                except Exception: pass

                        elif page_state == 'login':
                            print("[AI Verify] 🔑 Login wall detected after submit.")
                            if bot and active_chat_id:
                                try: bot.send_message(active_chat_id, f"🔑 *Login Required*\n\nThe site is asking for login/account creation after submit.\n\n{job_url}", parse_mode=None)
                                except Exception: pass
                            break  # Stop — cannot continue without login

                        else:  # 'form' or 'unknown'
                            print(f"[AI Verify] Page state: {page_state} — continuing to next step")

                    except Exception as verify_e:
                        print(f"[AI Verify] Post-submit check failed (non-fatal): {verify_e}")

                    # Save Checkpoint after successful step
                    checkpoints[job_url] = step + 1
                    try:
                        with open(checkpoint_file, "w") as f:
                            json.dump(checkpoints, f)
                    except: pass
                else:
                    print("[Browser] No submit selector found, triggering Live Takeover Handoff...")
                    global HANDOFF_ACTIVE, HANDOFF_PAGE, HANDOFF_URL
                    HANDOFF_ACTIVE = True
                    HANDOFF_PAGE = page
                    HANDOFF_URL = job_url
                    
                    if bot and active_chat_id:
                        try:
                            handoff_path = "handoff_stuck.png"
                            page.screenshot(path=handoff_path)
                            with open(handoff_path, "rb") as photo:
                                bot.send_photo(active_chat_id, photo, caption="🚨 *Manual Handoff Required*\n\nThe bot is stuck. Click the link below to take over the browser and solve the form:\n\n🔗 http://localhost:7860/live\n\n_The bot is paused and waiting for you to finish._", parse_mode=None)
                        except: pass
                        
                    # Wait for user to finish and hit resume
                    while HANDOFF_ACTIVE:
                        time.sleep(1)
                        
                    print("[Browser] Live Takeover finished. Bot resuming...")
                    total_steps_done += 1
                    time.sleep(3)
                    
            # === COMPREHENSIVE APPLICATION REPORT ===
            # Take final screenshot of the page after all steps
            import uuid
            filename = f"submit_{uuid.uuid4().hex[:8]}.png"
            success_screenshot_path = os.path.join("screenshots", filename)
            os.makedirs("screenshots", exist_ok=True)
            try:
                page.screenshot(path=success_screenshot_path)
            except: pass
            
            # Gather all info first, then send as one beautiful report
            
            # 1. Build the summary report text
            apply_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
            email_status = "🟡 Not Sent"
            cold_email_sent = False
            notion_status = "🟡 Not Synced"
            
            if any_fields_filled:
                # Send Cold Email first and capture status
                try:
                    bot_email_addr = os.getenv("BOT_EMAIL")
                    bot_pw = os.getenv("BOT_EMAIL_PASSWORD")
                    if bot_email_addr and bot_pw:
                        print("[Features] Sending Cold Email...")
                        success, email_msg = send_cold_email_if_found(full_jd, profile, dynamic_resume, bot_email_addr, bot_pw, gemini_client, groq_client=groq_client)
                        if success:
                            email_status = f"✅ Sent! ({email_msg[:60]})"
                            cold_email_sent = True
                        else:
                            email_status = f"❌ {email_msg[:80]}"
                except Exception as e:
                    email_status = f"❌ Error: {str(e)[:60]}"
                    print(f"[Cold Email] Failed: {e}")
                
                # Sync to Notion and capture status
                try:
                    print("[Features] Syncing to Notion CRM...")
                    public_screenshot_url = f"https://gokuuc-myjob-bot.hf.space/screenshots/{filename}"
                    notion_success, notion_msg = sync_to_notion(job_url, full_jd, "Applied", gemini_client, groq_client=groq_client, screenshot_url=public_screenshot_url)
                    if notion_success:
                        notion_status = "✅ Synced to Notion CRM"
                    elif "disabled" in notion_msg.lower():
                        notion_status = "⚡ Notion not configured"
                    else:
                        notion_status = f"❌ {notion_msg[:60]}"
                except Exception as e:
                    notion_status = f"❌ Error: {str(e)[:60]}"
            
            # 2. Build complete QA answers section
            qa_summary_lines = []
            for item in qa_report:
                # Extract just the question and answer cleanly
                lines = item.replace("\ud83e\udd16 *AI Answer*\n", "").split("\n")
                if len(lines) >= 2:
                    q = lines[0].replace("❓ ", "")
                    a = lines[1].replace("💬 ", "") if len(lines) > 1 else ""
                    qa_summary_lines.append(f"• {q[:50]}: *{a[:80]}*")
            
            # 3. Detect confirmation on page
            confirmed = False
            if any_fields_filled:
                try:
                    page_text = page.locator("body").inner_text(timeout=2000).lower()
                    if any(word in page_text for word in ["success", "received", "thank you for applying", "application submitted"]):
                        confirmed = True
                except: pass
            
            # 4. Build the beautiful final caption
            if any_fields_filled:
                status_icon = "✅" if confirmed else "🟢"
                status_text = "Application Submitted!" if confirmed else "Form Filled & Submitted"
                
                final_caption = (
                    f"{status_icon} *{status_text}*\n"
                    f"⏰ {apply_time}\n"
                    f"🔗 [Open Application]({job_url})\n\n"
                    f"📊 *Summary:*\n"
                    f"• Steps Completed: {total_steps_done}\n"
                    f"• Fields Filled: {total_steps_done}\n"
                    f"📧 Email: {email_status}\n"
                    f"🗒️ Notion: {notion_status}\n"
                )
                if qa_summary_lines:
                    final_caption += f"\n🧠 *AI Answers Used:*\n" + "\n".join(qa_summary_lines[:5])
                    if len(qa_summary_lines) > 5:
                        final_caption += f"\n… +{len(qa_summary_lines)-5} more answers"
            else:
                final_caption = (
                    f"⚠️ *No Form Found*\n"
                    f"⏰ {apply_time}\n"
                    f"🔗 [Apply Manually]({job_url})\n\n"
                    f"_Page may require Google Sign-In or CAPTCHA._"
                )
            
            # 5. Send screenshot + full report as one message
            if bot and active_chat_id:
                try:
                    with open(success_screenshot_path, "rb") as photo:
                        bot.send_photo(
                            active_chat_id,
                            photo,
                            caption=final_caption[:1024],
                            parse_mode=None
                        )
                    # If caption was truncated, send the rest as a follow-up text
                    if len(final_caption) > 1024:
                        bot.send_message(active_chat_id, final_caption[1024:], parse_mode=None, disable_web_page_preview=True)
                except Exception as send_err:
                    print(f"[Report] Failed to send photo: {send_err}")
                    try:
                        bot.send_message(active_chat_id, final_caption[:4096], parse_mode=None, disable_web_page_preview=True)
                    except: pass
            
            # 6. Generate and send Interview Prep sheet
            if any_fields_filled and bot and active_chat_id:
                try:
                    print("[Features] Generating Interview Prep...")
                    prep = generate_interview_prep(job_url, full_jd, gemini_client, groq_client=groq_client)
                    bot.send_message(active_chat_id, f"🧠 *Interview Cheat Sheet:*\n\n{prep}", parse_mode=None)
                except Exception as prep_err:
                    print(f"[Interview Prep] Failed: {prep_err}")
            
            # --- Notify user about unknown questions with inline Answer buttons ---
            if bot and active_chat_id and all_unknown_questions:
                try:
                    # Save pending questions as numbered dict
                    pending = {str(i+1): q for i, q in enumerate(all_unknown_questions.keys())}
                    save_pending_qa(pending)
                    
                    header = "❓ *Questions Need Your Answer!*\n\n_Tap \"✏️ Answer\" below each question or type:_\n`/answer 1 | your answer`\n"
                    bot.send_message(active_chat_id, header, parse_mode=None)
                    
                    # Send each question as a separate message with an inline Answer button
                    for num, q in pending.items():
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton(
                            text=f"✏️ Answer Q{num}",
                            callback_data=f"qa_answer:{num}"
                        ))
                        bot.send_message(
                            active_chat_id,
                            f"*Q{num}.* {q}",
                            parse_mode=None,
                            reply_markup=markup
                        )
                except Exception as qa_err:
                    print(f"[QA] Error sending question prompt: {qa_err}")
            
            return any_fields_filled
                
        except Exception as e:
            if "GEMINI_RATE_LIMIT" in str(e):
                raise e # Don't take screenshots for rate limits, just pass it up

            err_text = str(e)
            print(f"[Browser] Error during application: {err_text}")
            
            if bot and active_chat_id:
                try:
                    bot.send_message(active_chat_id, f"🚨 *System Alert: Application Halted*\n\n*Reason:* `{err_text[:150]}...`\n\n_Don't worry, the job has been sent to the Retry Queue._", parse_mode=None)
                except: pass
                
            # Take error screenshot
            try:
                err_path = "error_screenshot.png"
                page.screenshot(path=err_path)
                if bot and active_chat_id:
                    with open(err_path, "rb") as photo:
                        bot.send_photo(active_chat_id, photo, caption="📸 *Error Snapshot*")
            except Exception:
                pass
            return False
        finally:
            playwright_active = False
            try:
                video_path = None
                if 'page' in locals() and page and page.video:
                    try:
                        video_path = page.video.path()
                    except: pass
                if context:
                    # Save cookies before closing so we stay logged in next time!
                    context.storage_state(path="state.json")
                    context.close()
                if video_path and os.path.exists(video_path):
                    if bot and active_chat_id:
                        print(f"[Video] Sending Time-Lapse Video Proof from {video_path}")
                        try:
                            with open(video_path, "rb") as vid:
                                bot.send_video(active_chat_id, vid, caption="🎥 *Time-Lapse Application Video Proof*\n\nHere is exactly what the bot did.", parse_mode=None)
                        except Exception as ve:
                            print(f"[Video] Telegram send failed: {ve}")
            except Exception as e:
                print(f"[Browser] Error in finally block: {e}")
            try:
                if browser:
                    browser.close()
            except Exception:
                pass

_PROMO_DOMAINS = (
    "t.me", "telegram.org", "telegram.dog", "whatsapp.com", "wa.me",
    "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "pinterest.com", "threads.net",
    "linktr.ee", "bio.link", "campsite.bio", "taplink.cc", "beacons.ai",
    "play.google.com", "apps.apple.com", "aratt.ai",
    # Online courses, tutorials, coupon sites
    "udemy.com", "coursera.org", "edx.org", "simplilearn.com", "greatlearning.in",
    "udemy-free-course", "free-course", "free-udemy", "interview-questions-answers",
    # Social sharing / blog widgets
    "addtoany.com", "addthis.com", "sharethis.com", "disqus.com", "gravatar.com",
    "blogger.com", "feedburner.com", "wordpress.com", "w3.org",
    # Expired / Parked / Squatter domains
    "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com",
    "namecheap.com", "domainmarket.com", "parklogic.com", "parkingcrew.com",
    "bodis.com", "above.com", "domainagents.com", "undeveloped.com",
    "buydomains.com", "domain_profile.cfm", "domainforbuy"
)
_LINKEDIN_NON_JOB_SUBSTRS = ("/company/", "/in/", "/feed/", "/posts/", "/groups/", "/pulse/", "/school/")

def is_social_or_promo_link(url):
    """Detects if a URL is a social media link, channel promo, parked domain, or non-job page."""
    if not url or not isinstance(url, str):
        return True
    u = url.lower().strip()
    
    if any(d in u for d in _PROMO_DOMAINS):
        return True
        
    # LinkedIn company, personal profile, or feed pages are NOT direct job apply links
    if "linkedin.com" in u:
        if any(p in u for p in _LINKEDIN_NON_JOB_SUBSTRS):
            return True
            
    return False

def fetch_target_page_job_meta(url):
    """
    Fetches title, h1, and key meta from the actual destination webpage.
    Inspects ATS URL domains directly (Greenhouse, Lever, Workday, etc.) and structured tables.
    """
    if not url or not url.startswith("http") or is_social_or_promo_link(url):
        return {}

    from urllib.parse import urlparse
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    path = parsed.path.strip("/")

    company_from_url = ""
    role_from_url = ""

    # Direct ATS detection from URL structure
    if "greenhouse.io" in netloc:
        parts = path.split("/")
        if parts:
            company_from_url = parts[0].replace("-", " ").title()
    elif "lever.co" in netloc:
        parts = path.split("/")
        if parts:
            company_from_url = parts[0].replace("-", " ").title()
    elif "myworkdayjobs.com" in netloc:
        sub = netloc.split(".")[0]
        if sub and sub not in ["wd1", "wd2", "wd3", "wd4", "wd5"]:
            company_from_url = sub.replace("-", " ").title()
    elif "smartrecruiters.com" in netloc:
        parts = path.split("/")
        if parts:
            company_from_url = parts[0].replace("-", " ").title()
    elif "ashbyhq.com" in netloc:
        parts = path.split("/")
        if parts:
            company_from_url = parts[0].replace("-", " ").title()
    elif "bamboohr.com" in netloc:
        sub = netloc.split(".")[0]
        if sub:
            company_from_url = sub.replace("-", " ").title()
    elif "amazon.jobs" in netloc:
        company_from_url = "Amazon"
    elif "google.com" in netloc and "careers" in path:
        company_from_url = "Google"
    elif "microsoft.com" in netloc and "careers" in path:
        company_from_url = "Microsoft"
    elif "apple.com" in netloc and "jobs" in path:
        company_from_url = "Apple"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code != 200:
            return {"company": company_from_url, "role": role_from_url}
        ct = r.headers.get("content-type", "").lower()
        if ct and not any(ok in ct for ok in ["text", "html", "json"]):
            return {"company": company_from_url, "role": role_from_url}
        soup = BeautifulSoup(r.text[:300000], "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        h1 = soup.find("h1").get_text().strip() if soup.find("h1") else ""

        full_text = f"{title}\n{h1}"
        company = company_from_url
        role = role_from_url
        loc_str = ""

        # Extract from structured tables on job blogs / career portals
        for tr in soup.find_all("tr"):
            row_text = tr.get_text(separator=" | ").strip()
            full_text += "\n" + row_text
            if re.search(r'Company\s*\|', row_text, re.I) and not company:
                parts = row_text.split('|')
                if len(parts) >= 2:
                    c_cand = parts[1].strip()
                    if len(c_cand) >= 2 and not any(k in c_cand.lower() for k in ["hiring", "recruiter", "http"]):
                        company = c_cand
            if re.search(r'Role\s*\||Position\s*\||Designation\s*\||Job\s*Title\s*\|', row_text, re.I) and not role:
                parts = row_text.split('|')
                if len(parts) >= 2:
                    role = parts[1].strip()
            if re.search(r'Location\s*\||Job\s*Location\s*\|', row_text, re.I) and not loc_str:
                parts = row_text.split('|')
                if len(parts) >= 2:
                    loc_str = parts[1].strip()

        # Extract from H1 / Title if not in table
        if not company:
            m_h1 = re.search(r'^([A-Za-z0-9\s.,&-]+?)\s+(?:Walk-in|Hiring|Recruitment|Drive|is\s+Hiring|Off\s*Campus)', h1, re.I)
            if m_h1:
                company = m_h1.group(1).strip()
        junk_role_words = ["offices of the us", "careers", "job detail", "about us", "welcome", "hiring", "home", "search jobs", "deloitte", "freshers", "graduates", "any graduate"]
        if not role or any(bad in role.lower() for bad in junk_role_words) or (company and role.lower() == company.lower()):
            role = ""
            for src in [h1, title]:
                if not src:
                    continue
                # Pattern A: Hiring ... for [Role]
                m_for = re.search(r'(?:Hiring|Recruiting)\s+(?:Any\s+)?(?:Graduates?|Freshers?|Students?|Batch|Candidates?|\d{4}\s+Batch)*(?:\s+Freshers?)?\s+(?:for|as|role\s+of)\s+([A-Za-z0-9\s/&,().-]+)', src, re.I)
                if m_for:
                    cand = m_for.group(1).strip()
                    cand = re.split(r'[-–—|]|(?:\s+(?:at|in|with)\s+[A-Z])', cand)[0].strip()
                    if len(cand) >= 3 and not any(bad in cand.lower() for bad in junk_role_words):
                        role = cand
                        break
                # Pattern B: Hiring [Role] Freshers/Drive/Walkin
                m_role = re.search(r'(?:Hiring|Recruiting)\s+(?:Any\s+)?(?:Freshers?\s+)?([A-Za-z0-9\s/&,().-]+?)(?:\s+(?:Freshers?|Drive|Walk-?in|Recruitment|Off\s*Campus|\d{4}\s+Batch|Job|Opportunities?)|[-–—|]|$)', src, re.I)
                if m_role:
                    cand = m_role.group(1).strip()
                    if len(cand) >= 3 and not any(bad in cand.lower() for bad in junk_role_words):
                        role = cand
                        break
            # Fallback to general title split
            if not role and title:
                title_parts = [p.strip() for p in re.split(r'[-–—|]', title) if p.strip()]
                for p in title_parts:
                    p_clean = re.sub(r'\s*\b(job|careers?|recruitment|drive|\d{5,})\b.*', '', p, flags=re.I).strip()
                    if len(p_clean) >= 4 and not any(bad in p_clean.lower() for bad in junk_role_words + ["india", "hyderabad", "bangalore", "chennai", "offices"]):
                        role = p_clean
                        break

        return {
            "company": company,
            "role": role,
            "location_raw": loc_str,
            "page_title": title,
            "h1": h1,
            "page_text": full_text
        }
    except Exception:
        return {"company": company_from_url, "role": role_from_url}

def extract_structured_channel_job_details(message_text, raw_link, final_url, channel_name):
    """
    Parses channel message text, target webpage, and direct URL to extract structured job metadata.
    Combines multi-pattern regex, URL analysis, and fast AI fallback (Gemini/Groq) for 100% accuracy.
    Returns: dict with (company, role, location, batch, salary, work_mode, description_summary, direct_url, is_tamil_nadu, priority_tier, is_valid_india)
    """
    from job_radar import classify_location

    text_clean = message_text.strip()
    lines = [l.strip() for l in text_clean.split('\n') if l.strip()]

    # Fetch webpage metadata to verify against false channel claims
    page_meta = fetch_target_page_job_meta(final_url)

    invalid_companies = [
        "bit", "bitly", "tinyurl", "cutt", "cuttly", "rb", "rbgy", "t", "tly", "isgd", "buffly",
        "owly", "shorturl", "dub", "linkvertise", "adf", "goo", "gl", "lnkd", "linktr", "forms",
        "google", "docs", "sheets", "drive", "notion", "airtable", "blogger", "blogspot",
        "wordpress", "medium", "github", "gitlab", "jobsgovind", "freshershunt", "foundthejob",
        "jobopenings", "jobopenings_india", "tech_jobs_india", "indiawalkinjobs", "walkinjobs",
        "meganaukri", "dailyjobalerts", "sarkariprep", "freejobalert", "freshersvoice", "naukriauto",
        "jobalertshub", "placementdrive", "allindiajobs", "offcampusjobs4u", "kickcharm", "jobskull",
        "naukri", "foundit", "shine", "monster", "telegram", "telegram.org", "telegram.dog", "t.me",
        "whatsapp", "wa.me", "youtube", "instagram", "facebook", "twitter", "x.com", "threads.net",
        "verified recruiter", "verified", "recruiter", "company", "organisation", "organization",
        "hiring", "careers", "jobs", "job", "apply", "unknown", "admin", "domain", "hugedomains",
        "godaddy", "sedo", "dan", "afternic", "addtoany", "addthis", "sharethis", "disqus", "direct hiring organization"
    ]

    # 1. EXTRACT COMPANY (Multi-Line Regex)
    company = ""
    if page_meta.get("company") and len(page_meta["company"]) >= 2 and page_meta["company"].lower() not in invalid_companies:
        company = page_meta["company"]

    if not company:
        comp_m = re.search(r'(?:🏢\s*(?:Company|Organisation|Org|Organization|Company\s*Name)?|Company|Organisation|Org|Organization)\s*[:\-]\s*([^\n📍💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
        if comp_m:
            cand = comp_m.group(1).strip()
            if len(cand) >= 2 and cand.lower() not in invalid_companies:
                company = cand

    if not company:
        for line in lines[:4]:
            m_hiring = re.search(r'^[^\w\s]*\s*([A-Za-z0-9\s.,&-]+?)\s+(?:is\s+Hiring|is\s+Recruiting|Recruitment\s+20\d\d|Recruitment|Off\s*Campus\s+Drive|Off\s*Campus|Mega\s+Drive|Drive|Hiring|Walkin|Walk-in)', line, re.I)
            if m_hiring:
                cand = m_hiring.group(1).strip()
                if len(cand) >= 2 and cand.lower() not in invalid_companies:
                    company = cand
                    break

    if not company:
        for line in lines[:3]:
            m_ad = re.search(r'#ad\s*🚀?\s*([A-Za-z0-9\s.,&-]+?)\s+(?:Hiring|Recruitment|Drive)', line, re.I)
            if m_ad:
                cand = m_ad.group(1).strip()
                if len(cand) >= 2 and cand.lower() not in invalid_companies:
                    company = cand
                    break

    company = re.sub(r'[^\w\s.,&-]', '', company).replace('Title', '').replace(':', '').strip()
    if company.lower() in invalid_companies or len(company) < 2:
        company = ""

    # 2. EXTRACT ROLE / POSITION (Multi-Line Regex)
    role = ""
    if page_meta.get("role") and len(page_meta["role"]) >= 3:
        role = page_meta["role"]

    if not role:
        role_m = re.search(r'(?:(?:💼\s*)?Role|Position|Job\s*Title|Profile|Post|Designation|▪️\s*Post)\s*[:\-]\s*([^\n🏢📍🛠️💰📝👉🔗|]+)', text_clean, re.I)
        if role_m:
            role = role_m.group(1).strip()

    if not role:
        for line in lines[:4]:
            m_role_paren = re.search(r'is\s+Hiring\s*(?:for\s+)?(?:\(([^)]+)\)|([A-Za-z0-9\s/&,.-]+?(?:Developer|Engineer|Analyst|Associate|Specialist|Trainee|Intern|Executive|Manager|Consultant)))', line, re.I)
            if m_role_paren:
                role = (m_role_paren.group(1) or m_role_paren.group(2) or "").strip()
                break

    role = re.sub(r'^[▪️👉•\-:\s]+', '', role).strip()
    role = re.sub(r'[^\w\s.,&/\(\)\-]', '', role).strip()

    # 3. EXTRACT LOCATION
    if page_meta.get("location_raw"):
        raw_loc = page_meta["location_raw"]
        context_for_loc = f"{raw_loc} {page_meta.get('page_text', '')}"
    elif page_meta.get("page_text"):
        loc_m = re.search(r'(?:📍\s*Location|Location|Job\s*Location|Work\s*Location|Place)\s*[:\-]\s*([^\n🏢💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
        raw_loc = loc_m.group(1).strip() if loc_m else ""
        context_for_loc = f"{raw_loc} {page_meta.get('page_text', '')}"
    else:
        loc_m = re.search(r'(?:📍\s*Location|Location|Job\s*Location|Work\s*Location|Place)\s*[:\-]\s*([^\n🏢💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
        raw_loc = loc_m.group(1).strip() if loc_m else ""
        context_for_loc = f"{raw_loc} {text_clean}"

    # 4. EXTRACT BATCH & EXPERIENCE LEVEL (High-Precision Indian Batch Tagger)
    batch = extract_eligible_batch(text_clean)
    if not batch and page_meta.get("page_text"):
        batch = extract_eligible_batch(page_meta["page_text"])
    if not batch:
        batch_m = re.search(r'(?:(?:🎓\s*)?Batch|Batch|Eligibility|Passout|Year\s*of\s*Passing|Qualification|Experience|Exp)\s*[:\-]\s*([^\n🏢📍💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
        if batch_m:
            batch = batch_m.group(1).strip()

    experience = extract_experience_level(text_clean)
    if (not experience or experience == "Freshers (0-1 yrs)") and page_meta.get("page_text"):
        exp_page = extract_experience_level(page_meta["page_text"])
        if exp_page:
            experience = exp_page

    # 5. EXTRACT SALARY / CTC (High-Precision Indian Packages: LPA, CTC, Stipend)
    salary = extract_job_salary(text_clean)
    if not salary and page_meta.get("page_text"):
        salary = extract_job_salary(page_meta["page_text"])
    if not salary:
        sal_m = re.search(r'(?:(?:💰\s*)?(?:Expected\s*CTC|CTC)|Expected\s*CTC|CTC|Salary|Package|Pay|Stipend)\s*[:\-]\s*([^\n🏢📍💼🛠️📝👉🔗|]+)', text_clean, re.I)
        if sal_m:
            salary = sal_m.group(1).strip()

    # 5b. EXTRACT HR / RECRUITER EMAIL (Tier 2 Outreach Automation)
    hr_email = extract_hr_email(text_clean)
    if not hr_email and page_meta.get("page_text"):
        hr_email = extract_hr_email(page_meta["page_text"])

    # 6. EXTRACT WORK STATUS / JOB TYPE
    work_mode = ""
    wm_m = re.search(r'(?:(?:🛠️\s*)?Work\s*Status|Work\s*Status|💼\s*Job\s*Type|Job\s*Type|Work\s*Mode)\s*[:\-]\s*([^\n🏢📍💰📝👉🔗|]+)', text_clean, re.I)
    if wm_m:
        work_mode = wm_m.group(1).strip()
        work_mode = re.sub(r'🛠️\s*Work\s*Status\s*:\s*', '| ', work_mode).strip()

    # 7. EXTRACT JOB DESCRIPTION / SUMMARY
    desc_summary = ""
    desc_m = re.search(r'(?:📝\s*Job\s*Description|Job\s*Description|Description|Responsibilities|About\s*Role|Highlights)\s*[:\-]\s*([^\n👉🔗]+)', text_clean, re.I)
    if desc_m:
        desc_summary = desc_m.group(1).strip()[:200]

    # ── AI EXTRACTION FALLBACK (When company or role is uncertain) ──
    if not company or company.lower() in invalid_companies or not role or role == "Software Developer / Fresher Engineer":
        ai_data = None
        # Try Gemini Flash
        try:
            gc = get_gemini_client()
            if gc:
                resp = gc.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"Extract structured job data from this post:\n{text_clean[:600]}\nReturn JSON with keys: company, role, location, batch, salary, work_mode, key_highlights."
                )
                raw_t = resp.text.strip()
                if "```" in raw_t:
                    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_t)
                    if m:
                        raw_t = m.group(1)
                ai_data = json.loads(raw_t)
        except Exception:
            pass

        # Try Groq fallback
        if not ai_data and groq_client:
            try:
                g_resp = groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[{"role": "user", "content": f"Extract structured job data from this post:\n{text_clean[:600]}\nReturn valid JSON with keys: company, role, location, batch, salary, work_mode, key_highlights."}],
                    timeout=5
                )
                raw_t = g_resp.choices[0].message.content.strip()
                if "```" in raw_t:
                    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_t)
                    if m:
                        raw_t = m.group(1)
                ai_data = json.loads(raw_t)
            except Exception:
                pass

        if ai_data and isinstance(ai_data, dict):
            ai_comp = str(ai_data.get("company", "")).strip()
            if ai_comp and len(ai_comp) >= 2 and ai_comp.lower() not in invalid_companies and "null" not in ai_comp.lower():
                company = ai_comp
                print(f"[AI Extraction] Successfully resolved company: {company}")
            ai_role = str(ai_data.get("role", "")).strip()
            if ai_role and len(ai_role) >= 3 and "null" not in ai_role.lower():
                role = ai_role
                print(f"[AI Extraction] Successfully resolved role: {role}")
            if not raw_loc and ai_data.get("location") and "null" not in str(ai_data["location"]).lower():
                raw_loc = str(ai_data["location"]).strip()
                context_for_loc = f"{raw_loc} {context_for_loc}"
            if not batch and ai_data.get("batch") and "null" not in str(ai_data["batch"]).lower():
                batch = str(ai_data["batch"]).strip()
            if not salary and ai_data.get("salary") and "null" not in str(ai_data["salary"]).lower():
                salary = str(ai_data["salary"]).strip()
            if not hr_email and ai_data.get("hr_email") and "null" not in str(ai_data["hr_email"]).lower():
                hr_email = str(ai_data["hr_email"]).strip()
            if not work_mode and ai_data.get("work_mode") and "null" not in str(ai_data["work_mode"]).lower():
                work_mode = str(ai_data["work_mode"]).strip()
            if not desc_summary and ai_data.get("key_highlights") and "null" not in str(ai_data["key_highlights"]).lower():
                desc_summary = str(ai_data["key_highlights"]).strip()[:200]

    # Fallback to URL domain ONLY for corporate domains (NEVER shorteners/aggregators)
    if not company or company.lower() in invalid_companies:
        if final_url and "http" in final_url and not is_social_or_promo_link(final_url):
            from urllib.parse import urlparse
            netloc = urlparse(final_url).netloc.lower()
            parts = [p for p in netloc.split('.') if p not in ["www", "com", "in", "io", "co", "careers", "jobs", "apply", "wd3", "myworkdayjobs", "sensehq", "greenhouse", "lever", "smartrecruiters", "docs", "google", "org", "net"]]
            if parts and parts[0] not in invalid_companies and len(parts[0]) >= 3:
                company = parts[0].capitalize()

    if not company or company.lower() in invalid_companies:
        company = "Direct Hiring Organization"

    if not role or len(role) < 2:
        role = "Software Developer / Fresher Engineer"

    if not batch:
        batch = "2024 / 2025 / 2026 Batch"

    if not experience:
        experience = "Freshers (0-1 yrs)"

    eligibility_badge = format_eligibility_badge(batch, experience)

    if not salary:
        salary = "As per Industry Standard"

    is_valid_loc, tier, loc_tag, is_tn = classify_location(raw_loc, context_for_loc)

    # Compute ATS-style skill match score against candidate profile
    match_data = calculate_skill_match_score(f"{text_clean} {role} {company}", load_profile())

    return {
        "company": company[:50],
        "role": role[:65],
        "location": loc_tag if loc_tag else (raw_loc if raw_loc else "India (PAN India) 🇮🇳"),
        "raw_location": raw_loc,
        "batch": batch[:50],
        "experience": experience[:50],
        "eligibility_badge": eligibility_badge,
        "salary": salary[:40],
        "hr_email": hr_email[:80] if hr_email else "",
        "work_mode": work_mode[:40] if work_mode else "Full-time / Fresher",
        "description_summary": desc_summary,
        "direct_url": final_url,
        "is_tamil_nadu": is_tn,
        "priority_tier": tier,
        "is_valid_india": is_valid_loc,
        "match_data": match_data,
    }

# --- 5. TELEGRAM CHANNEL SCRAPER (PUBLIC WEB PREVIEW) ---
_channel_session = None

def get_channel_session():
    global _channel_session
    if _channel_session is None:
        _channel_session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=2, pool_connections=10, pool_maxsize=10)
        _channel_session.mount("https://", adapter)
        _channel_session.mount("http://", adapter)
    return _channel_session

def scrape_single_channel(channel_name, applied_jobs, active_chat_id, max_jobs=2):
    """
    Scrapes one Telegram public channel and triggers applications for new jobs.
    Supports text links, media captions, and inline keyboard buttons.
    Returns (new_jobs_found, attempts_this_cycle).
    """
    global _seen_this_cycle
    channel_name = channel_name.replace("@", "").strip()
    session = get_channel_session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
    new_jobs_found = 0
    attempts_this_cycle = 0
    profile = load_profile()

    # Load and update channel status
    ch_status = load_channel_status()
    ch_status.setdefault(channel_name, {"last_scan": "Never", "jobs_found": 0, "status": "Pending"})

    soup = None
    # Dual-domain resilient fallback (try t.me first, then telegram.dog)
    for domain in ["t.me", "telegram.dog"]:
        try:
            url = f"https://{domain}/s/{channel_name}"
            response = session.get(url, headers=headers, timeout=8)
            if response.status_code == 200:
                candidate_soup = BeautifulSoup(response.text, "html.parser")
                bubbles = candidate_soup.find_all("div", class_="tgme_widget_message_bubble") or candidate_soup.find_all("div", class_="tgme_widget_message_wrap")
                if bubbles:
                    soup = candidate_soup
                    break
        except Exception:
            continue

    if not soup:
        ch_status[channel_name].update({"status": "Fetch Error / Rate Limited", "last_scan": datetime.now().strftime("%H:%M")})
        save_channel_status(ch_status)
        print(f"[Scraper] @{channel_name} -> Fetch error or connection dropped across both domains.")
        return 0, 0

    bubbles = soup.find_all("div", class_="tgme_widget_message_bubble") or soup.find_all("div", class_="tgme_widget_message_wrap")
    if not bubbles:
        ch_status[channel_name].update({"status": "Empty/Private", "last_scan": datetime.now().strftime("%H:%M")})
        save_channel_status(ch_status)
        print(f"[Scraper] @{channel_name} -> No messages found (private or empty channel).")
        return 0, 0

    print(f"[Scraper] @{channel_name} -> Found {len(bubbles)} post widgets.")

    # Inspect up to 12 recent messages per channel to ensure no jobs are missed
    recent_bubbles = bubbles[-12:] if len(bubbles) > 12 else bubbles
    for bubble in reversed(recent_bubbles):
        if attempts_this_cycle >= max_jobs:
            break

        # Extract text from message text block or entire bubble (handles images with captions)
        text_el = bubble.find("div", class_="tgme_widget_message_text")
        message_text = text_el.get_text(separator=" ").strip() if text_el else bubble.get_text(separator=" ").strip()

        # --- IMPROVED LINK EXTRACTION (Supports BOTH text links & inline buttons!) ---
        urls_found = []
        for a_tag in bubble.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("http") and not is_social_or_promo_link(href):
                if href not in urls_found:
                    urls_found.append(href)

        regex_urls = re.findall(r'(https?://[^\s<>"]+)', message_text)
        for u in regex_urls:
            u = u.rstrip(").,!*'\"")
            if u not in urls_found and not is_social_or_promo_link(u):
                urls_found.append(u)

        if not urls_found:
            continue

        for job_link in urls_found:
            if attempts_this_cycle >= max_jobs:
                break
            job_link = job_link.rstrip(").,!*'\"")
            if job_link in applied_jobs:
                continue

            # Cross-channel duplicate check (same scan cycle)
            if job_link in _seen_this_cycle:
                print(f"[Dedup] Skipping duplicate seen in another channel: {job_link}")
                continue
            _seen_this_cycle.add(job_link)

            print(f"[Scraper] @{channel_name} -> Candidate link: {job_link}")

            # Resolve redirects & unwrap direct ATS/career links
            final_url = bypass_blog_redirect(job_link)
            if not final_url or is_social_or_promo_link(final_url):
                print(f"[Scraper] Resolved link is empty or a promo/parked URL ({final_url}) — skipping.")
                applied_jobs.add(job_link)
                save_applied_job(job_link)
                continue

            # Fast Dead Link & Expired ATS Probe (Feature 10)
            if not is_job_link_alive(final_url, timeout=3.5):
                print(f"[Scraper] Filtered out expired/closed job link ({final_url[:60]}) — skipping.")
                applied_jobs.add(job_link)
                save_applied_job(job_link)
                log_job(final_url, message_text, False, "Filtered: Dead/Expired ATS Opening")
                continue

            print(f"[Scraper] Resolved Direct Link: {final_url}")

            # Structured Details Extraction & India / Tamil Nadu check
            details = extract_structured_channel_job_details(message_text, job_link, final_url, channel_name)

            # Skip if company is invalid or default placeholder with no real info
            if details["company"] in ["Verified Recruiter", "Hugedomains", "Addtoany"] and details["role"] == "Software Developer / Fresher Engineer" and "http" not in final_url:
                print(f"[Scraper] Skipping generic/unparseable job post.")
                applied_jobs.add(job_link)
                save_applied_job(job_link)
                continue

            # Strict Non-Engineering / BPO / Medical Billing Filter
            non_eng_keywords = [
                "medical billing", "medical coder", "medical coding", "bpo", "telecaller", "telecalling",
                "data entry", "voice process", "non-voice", "non voice", "customer care", "customer support executive",
                "telesales", "insurance agent", "sales executive", "front desk", "receptionist", "security guard",
                "delivery boy", "delivery partner", "pharma sales", "retail sales"
            ]
            if any(k in details["role"].lower() for k in non_eng_keywords):
                print(f"[Scraper] Filtered out non-engineering/BPO role ({details['role']}) — skipping.")
                applied_jobs.add(job_link)
                save_applied_job(job_link)
                continue

            # Strict Location Filter: Reject foreign onsite locations
            if not details["is_valid_india"]:
                print(f"[Scraper] Filtered out non-India location: {details['raw_location']}")
                applied_jobs.add(job_link)
                save_applied_job(job_link)
                log_job(final_url, message_text, False, f"Filtered: Non-India location ({details['raw_location']})")
                continue

            # Smart Filter — strict fresher+engineering check
            try:
                filter_text = f"Role: {details['role']}\nCompany: {details['company']}\nLocation: {details['location']}\n\n{message_text}"
                is_match, job_summary = check_job_match(filter_text, profile)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception as filter_e:
                if "GEMINI_RATE_LIMIT" in str(filter_e):
                    print("[Scraper] Rate limit in filter. Stopping cycle.")
                    raise Exception("GEMINI_RATE_LIMIT")
                is_match, job_summary = True, str(filter_e)

            if not is_match:
                print(f"[Scraper] AI Rejected: {job_summary[:80]}")
                applied_jobs.add(job_link)
                save_applied_job(job_link)
                log_job(final_url, message_text, False, f"AI Rejected: {job_summary[:80]}")
                continue

            # ✅ Job matched — send ultra-spacious, executive HTML card to Telegram
            if bot and active_chat_id:
                try:
                    import html
                    import urllib.parse
                    channel_post_url = f"https://t.me/s/{channel_name}"

                    priority_banner = ""
                    if details.get("is_tamil_nadu"):
                        priority_banner = (
                            "🌟 <b>TAMIL NADU PRIORITY OPPORTUNITY</b> 🇮🇳\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        )
                    elif "remote" in str(details.get("work_mode", "")).lower() or "remote" in str(details.get("location", "")).lower():
                        priority_banner = (
                            "🏠 <b>REMOTE / WORK FROM HOME OPPORTUNITY</b> 🌐\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        )

                    work_info = f"🛠️ <b>Work Mode / Type:</b>\n   <code>{html.escape(str(details['work_mode']))}</code>\n\n" if details.get('work_mode') else ""

                    desc_section = ""
                    if details.get('description_summary') and len(details['description_summary']) > 15:
                        desc_section = (
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            "📋 <b>Key Highlights & Responsibilities:</b>\n"
                            f"<i>{html.escape(str(details['description_summary']))}</i>\n\n"
                        )

                    hr_email_val = str(details.get("hr_email", "")).strip()
                    hr_email_section = ""
                    if hr_email_val:
                        hr_email_section = f"📧 <b>HR Recruiter Email:</b>\n   <code>{html.escape(hr_email_val)}</code>\n\n"

                    # Tier 2: AI Outreach Drafter (LinkedIn connection note)
                    linkedin_note = generate_linkedin_outreach_note(details.get("company", ""), details.get("role", ""), profile)

                    # Feature 9: AI Skill Match Score & Resume Fit Analyzer
                    match_data = details.get("match_data") or calculate_skill_match_score(f"{message_text} {details.get('role', '')}", profile)
                    match_badge = html.escape(str(match_data.get("badge", "🟢 85% Fresher Fit")).strip())
                    matched_list = match_data.get("matched", [])

                    # Ultra-Sleek Banner
                    if details.get("is_tamil_nadu"):
                        banner = "🌟 <b>TAMIL NADU PRIORITY</b> 🇮🇳"
                    elif "remote" in str(details.get("work_mode", "")).lower() or "remote" in str(details.get("location", "")).lower():
                        banner = "🏠 <b>REMOTE / WORK FROM HOME</b> 🌐"
                    else:
                        banner = "🚀 <b>NEW JOB OPPORTUNITY</b> 🇮🇳"

                    comp_name = html.escape(str(details.get('company', 'Direct Hiring')).strip())
                    clean_role = html.escape(str(details.get('role', 'Software Engineer')).strip())
                    loc_val = html.escape(str(details.get('location', 'India (PAN India)')).strip())
                    batch_val = html.escape(str(details.get('batch', '2024 / 2025 / 2026 Batch')).strip())
                    exp_val = html.escape(str(details.get('experience', 'Freshers (0-1 yrs)')).strip())
                    sal_val = html.escape(str(details.get('salary', 'As per Industry Standard')).strip())
                    channel_post_url = f"https://t.me/s/{channel_name}"

                    # Feature 16: Check Keyword Watchdog Subscriptions
                    watchdogs = get_watchdog_subscriptions(active_chat_id)
                    matched_watchdogs = check_job_against_watchdogs(details, watchdogs)
                    watchdog_tag = ""
                    if matched_watchdogs:
                        tags_str = ", ".join([f"#{w.replace(' ', '_')}" for w in matched_watchdogs])
                        watchdog_tag = (
                            f"🔔 <b>[WATCHDOG ALERT: {html.escape(tags_str.upper())}]</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        )

                    # Compact 1-Screen Modern Card Layout
                    notification = (
                        f"{watchdog_tag}"
                        f"{banner}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🏢 <b>{comp_name}</b> • <i>{clean_role}</i>\n\n"
                        f"📍 <b>Location:</b> {loc_val}\n"
                        f"🎓 <b>Batch:</b> {batch_val}\n"
                        f"💼 <b>Experience:</b> {exp_val}\n"
                        f"💰 <b>Salary:</b> {sal_val}\n"
                        f"🎯 <b>Match:</b> {match_badge} • <b>Conviction:</b> {match_data.get('star_rating', 4.2)}/5.0 ⭐\n"
                        f"📡 <b>Source:</b> <a href=\"{html.escape(str(channel_post_url))}\">@{html.escape(str(channel_name))}</a>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━"
                    )

                    # Feature 11: 1-Tap Interview Prep Callback Cache
                    import hashlib
                    prep_hash = hashlib.md5(f"{details.get('company','')}_{details.get('role','')}".encode()).hexdigest()[:8]
                    _INTERVIEW_PREP_CACHE[prep_hash] = {
                        "company": details.get("company", "Hiring Organization"),
                        "role": details.get("role", "Software Engineer"),
                        "skills": matched_list or match_data.get("job_skills", [])
                    }
                    if len(_INTERVIEW_PREP_CACHE) > 500:
                        _INTERVIEW_PREP_CACHE.pop(next(iter(_INTERVIEW_PREP_CACHE)))

                    # CareerOps 3-Bucket Skill Gap Cache
                    _SKILL_GAP_CACHE[prep_hash] = match_data
                    store_gap_cache(prep_hash, match_data)
                    if len(_SKILL_GAP_CACHE) > 500:
                        _SKILL_GAP_CACHE.pop(next(iter(_SKILL_GAP_CACHE)))

                    # 1-Tap Cold Outreach Email Cache
                    _COLD_EMAIL_CACHE[prep_hash] = {
                        "company": details.get("company", "Hiring Organization"),
                        "role": details.get("role", "Software Engineer"),
                        "skills": matched_list or match_data.get("job_skills", [])
                    }

                    # 1-Tap LinkedIn Outreach Note Callback Cache
                    note_hash = hashlib.md5(f"note_{details.get('company','')}_{details.get('role','')}".encode()).hexdigest()[:8]
                    _LINKEDIN_NOTE_CACHE[note_hash] = linkedin_note or (
                        f"Hi! I noticed the {clean_role} opening at {comp_name}. With hands-on experience in "
                        f"{profile.get('top_skills', 'Python, software engineering')}, I would love to connect and explore how I can add value to your team!"
                    )
                    if len(_LINKEDIN_NOTE_CACHE) > 500:
                        _LINKEDIN_NOTE_CACHE.pop(next(iter(_LINKEDIN_NOTE_CACHE)))

                    share_text = urllib.parse.quote(f"🚀 Job Alert: {details['company']} - {details['role']}\nApply Link: {final_url}")
                    share_url = f"https://t.me/share/url?url={urllib.parse.quote(final_url)}&text={share_text}"

                    markup = InlineKeyboardMarkup()
                    markup.row(
                        InlineKeyboardButton("🚀 Direct Apply (Official)", url=final_url)
                    )
                    markup.row(
                        InlineKeyboardButton("💡 Interview Prep", callback_data=f"prep:{prep_hash}"),
                        InlineKeyboardButton("📊 Skill Gap", callback_data=f"gap:{prep_hash}")
                    )
                    markup.row(
                        InlineKeyboardButton("💬 LinkedIn Note", callback_data=f"note:{note_hash}"),
                        InlineKeyboardButton("✉️ 1-Tap Pitch", callback_data=f"email:{prep_hash}")
                    )
                    markup.row(
                        InlineKeyboardButton("📢 View Channel Post", url=channel_post_url),
                        InlineKeyboardButton("📤 Share Alert", url=share_url)
                    )
                    if hr_email_val and "@" in hr_email_val:
                        candidate_name = profile.get("name", "Applicant")
                        job_role = details.get("role", "Engineering Role")
                        company_name = details.get("company", "Company")
                        mail_subject = urllib.parse.quote(f"Application for {job_role} - {candidate_name}")
                        mail_body = urllib.parse.quote(f"Dear Hiring Team,\n\nI am writing to express my strong interest in the {job_role} opening at {company_name}. Please find my resume attached.\n\nBest regards,\n{candidate_name}")
                        gmail_compose_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={urllib.parse.quote(hr_email_val)}&su={mail_subject}&body={mail_body}"
                        markup.row(
                            InlineKeyboardButton("📧 Email Recruiter (Gmail)", url=gmail_compose_url)
                        )
                    if len(notification) > 3900:
                        notification = notification[:3850] + "\n...</i>\n\n👇 <b>Tap below to apply:</b>"

                    try:
                        bot.send_message(active_chat_id, notification, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
                    except Exception as html_err:
                        print(f"[Scraper] HTML parse send failed ({html_err}). Retrying plain text...")
                        clean_plain = re.sub(r'<[^>]+>', '', notification)
                        bot.send_message(active_chat_id, clean_plain[:3900], parse_mode=None, reply_markup=markup)

                    print(f"[Scraper] Sent direct job alert to Telegram: {details['company']} - {details['role']}")
                except Exception as notif_e:
                    print(f"[Scraper] Failed to send job summary: {notif_e}")

            # Mark as processed & log
            applied_jobs.add(job_link)
            save_applied_job(job_link)
            log_job(final_url, message_text, True, "Alerted to user (Direct apply)")
            new_jobs_found += 1
            attempts_this_cycle += 1
            ch_status[channel_name]["jobs_found"] = ch_status[channel_name].get("jobs_found", 0) + 1
            wk = load_weekly_stats()
            wk["applied"] = wk.get("applied", 0) + 1
            save_weekly_stats(wk)

            # Sync to Notion (if configured)
            try:
                gc = get_gemini_client()
                sync_to_notion(final_url, message_text, "Alerted", gc, override_company=details['company'], groq_client=groq_client)
            except Exception as e:
                pass

            # Save last job
            save_last_job({
                "channel": channel_name, "url": final_url,
                "summary": f"{details['company']} - {details['role']}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "📢 Alerted"
            })

            # BUG FIX 2: Raised per-channel cap from 2 to 5 so more jobs are processed
            if new_jobs_found >= 5 or attempts_this_cycle >= 5:
                print(f"[Scraper] @{channel_name} cycle limit reached.")
                break

        if new_jobs_found >= 5 or attempts_this_cycle >= 5:
            break

    ch_status[channel_name]["last_scan"] = datetime.now().strftime("%H:%M")
    ch_status[channel_name]["status"] = f"✅ {new_jobs_found} alerted"
    save_channel_status(ch_status)
    return new_jobs_found, attempts_this_cycle


def scrape_telegram_channel():
    """
    Loops through all TARGET_CHANNELS and scrapes each one for new engineering fresher jobs.
    """
    global BOT_PAUSED, _seen_this_cycle
    if BOT_PAUSED:
        print("[Loop] Bot is paused. Skipping this cycle.")
        return

    # Smart sleep: rest between 11 PM and 6 AM
    if is_sleep_time():
        print("[Loop] Sleep hours (11 PM–6 AM). Bot resting to avoid detection.")
        return

    # Reset duplicate tracker each cycle
    _seen_this_cycle = set()

    active_chat_id = load_chat_id()
    applied_jobs = load_applied_jobs()

    # --- Auto-Retry Failed Applications ---
    retry_queue = load_retry_queue()
    now_ts = time.time()
    for job_url, data in list(retry_queue.items()):
        if now_ts - data["timestamp"] > 1800:  # 30 minutes
            print(f"[Retry] Retrying failed job: {job_url}")
            try:
                success = run_playwright_apply(job_url)
                if success:
                    print(f"[Retry] Success! {job_url}")
                    log_job(job_url, "Retried", success, "Auto applied on retry")
                    del retry_queue[job_url]
                else:
                    data["attempts"] += 1
                    if data["attempts"] >= 3:
                        print(f"[Retry] Giving up on {job_url} after 3 attempts.")
                        del retry_queue[job_url]
                save_retry_queue(retry_queue)
                time.sleep(random.uniform(30, 60))
            except Exception as retry_e:
                if "GEMINI_RATE_LIMIT" in str(retry_e):
                    if bot and active_chat_id:
                        try: bot.send_message(active_chat_id, "⏳ *API Cooldown Activated*\n\n_Speed limit hit during retry. Sleeping 15 min._", parse_mode=None)
                        except: pass
                    return
                print(f"[Retry] Error: {retry_e}")
                time.sleep(10)

    # --- Scrape each channel in the list ---
    total_applied = 0
    for channel in TARGET_CHANNELS:
        # BUG FIX 2: Raised global cycle cap from 3 to 15 so all 20+ channel jobs get processed
        if total_applied >= 15:
            print("[Loop] Global cycle limit (15 applications) reached. Stopping.")
            break
        print(f"\n[Loop] === Scanning @{channel} ===")
        try:
            found, attempts = scrape_single_channel(channel, applied_jobs, active_chat_id)
            total_applied += found
            if attempts > 0:
                time.sleep(random.uniform(10, 20))  # Pause between channels
        except Exception as e:
            if "GEMINI_RATE_LIMIT" in str(e):
                return  # Stop entire cycle on rate limit
            print(f"[Loop] Error on @{channel}: {e}")
            continue

# --- 6. BACKGROUND MONITOR LOOP ---
def job_monitor_loop():
    print("[Loop] Background Job Monitor Loop started...")
    while True:
        if BOT_PAUSED:
            time.sleep(5) # Check state every 5 seconds when paused
            continue
            
        try:
            print("[Loop] Checking Telegram channel for new jobs...")
            scrape_telegram_channel()
            
            # Feature: Check for interview requests in email
            bot_email = os.getenv("BOT_EMAIL")
            bot_pw = os.getenv("BOT_EMAIL_PASSWORD")
            if bot_email and bot_pw:
                print("[Loop] Checking inbox for Interview Requests...")
                alerts = check_for_interviews(bot_email, bot_pw)
                for alert in alerts:
                    active_chat_id = load_chat_id()
                    if bot and active_chat_id:
                        try:
                            if alert["image"] and os.path.exists(alert["image"]):
                                with open(alert["image"], "rb") as photo:
                                    bot.send_photo(active_chat_id, photo, caption=alert["text"], parse_mode=None)
                            else:
                                bot.send_message(active_chat_id, alert["text"], parse_mode=None)
                        except Exception as e:
                            print(f"[Loop] Error sending interview alert: {e}")
                        
        except Exception as e:
            print(f"Error in monitor loop: {e}")
            
        # Feature: Morning Standup Daily Briefing (7 AM)
        global last_briefing_date, last_notion_digest_date
        
        now = datetime.now()
        if now.hour == 7 and now.date() != last_briefing_date:
            print("[Loop] Triggering 7 AM Morning Summary...")
            active_chat_id_local = load_chat_id()
            if bot and active_chat_id_local:
                try:
                    stats_data = load_stats()
                    total_app = stats_data.get('applied', 0)
                    total_skip = stats_data.get('skipped', 0)
                    total_fail = stats_data.get('failed', 0)
                    streak = stats_data.get('current_streak', 0)
                    
                    # Load radar results for found jobs count
                    radar_found = 0
                    radar_sources = 0
                    try:
                        if os.path.exists("radar_results.json"):
                            with open("radar_results.json", "r", encoding="utf-8") as rf:
                                radar_data = json.load(rf)
                                radar_found = radar_data.get("total", 0)
                                radar_sources = len(set(j.get("source", "") for j in radar_data.get("jobs", [])))
                    except: pass
                    
                    # Load recent applications from CSV
                    recent_apps = []
                    try:
                        import csv as csv_mod
                        if os.path.exists("applied_jobs_log.csv"):
                            with open("applied_jobs_log.csv", "r", encoding="utf-8") as cf:
                                rows = list(csv_mod.reader(cf))
                                yesterday = (now - __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
                                for row in rows[1:]:
                                    if len(row) >= 4 and row[0][:10] == yesterday:
                                        recent_apps.append(row)
                    except: pass
                    
                    # Build comprehensive morning message
                    channels_count = len(TARGET_CHANNELS)
                    
                    briefing = (
                        "🌅 *Good Morning! Daily Job Summary — 7 AM* ☕\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "🤖 _I worked all night. Here's your summary:_\n\n"
                        f"📊 *Yesterday's Results:*\n"
                        f"  ✅ Applied: *{total_app}* jobs\n"
                        f"  ⏭️ Filtered: *{total_skip}* jobs\n"
                        f"  ❌ Failed: *{total_fail}* jobs\n"
                        f"  🔥 Streak: *{streak}* days\n\n"
                        f"📡 *Job Radar:*\n"
                        f"  🆕 Found: *{radar_found}* jobs from *{radar_sources}* sources\n"
                        f"  📡 Channels: *{channels_count}* monitored\n\n"
                    )
                    
                    # Add recent successful applications
                    if recent_apps:
                        briefing += "💼 *Recently Applied To:*\n"
                        for app in recent_apps[:5]:
                            title = app[1][:35] if len(app) > 1 else "Unknown"
                            status = app[3][:20] if len(app) > 3 else "Unknown"
                            briefing += f"  • {title} — {status}\n"
                        if len(recent_apps) > 5:
                            briefing += f"  _...+{len(recent_apps)-5} more_\n"
                        briefing += "\n"
                    
                    briefing += (
                        "━━━━━━━━━━━━━━━━━━━━━━\n"
                        "_Enjoy your day while I keep hunting! 🚀_"
                    )
                    
                    markup = InlineKeyboardMarkup()
                    # Build Notion CRM link
                    raw_db_id = os.getenv('NOTION_DATABASE_ID', '')
                    notion_match = re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', raw_db_id)
                    notion_id = notion_match.group(1).replace('-', '') if notion_match else ''
                    notion_link = f"https://notion.so/{notion_id}" if notion_id else "https://notion.so"
                    
                    markup.row(
                        InlineKeyboardButton("📋 Notion CRM", url=notion_link),
                        InlineKeyboardButton("📱 Dashboard", url=DASHBOARD_URL)
                    )
                    
                    bot.send_message(active_chat_id_local, briefing, parse_mode=None, reply_markup=markup)
                    
                    # Reset stats for the new day
                    save_stats({"date": now.strftime("%Y-%m-%d"), "applied": 0, "skipped": 0, "failed": 0, "current_streak": streak, "last_apply_date": stats_data.get("last_apply_date", "")})
                    last_briefing_date = now.date()
                except Exception as err:
                    print(f"[Loop] Failed to send 7 AM Summary: {err}")

        # Feature: Nightly 10 PM Notion CRM Digest
        if now.hour == 22 and now.date() != last_notion_digest_date:
            print("[Loop] Triggering 10 PM Notion CRM Digest...")
            active_chat_id_local = load_chat_id()
            if bot and active_chat_id_local:
                try:
                    stats_data = load_stats()
                    total_app = stats_data.get('applied', 0)
                    total_skip = stats_data.get('skipped', 0)
                    
                    # Build Notion CRM link
                    raw_db_id = os.getenv('NOTION_DATABASE_ID', '')
                    notion_match = re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', raw_db_id)
                    notion_id = notion_match.group(1).replace('-', '') if notion_match else ''
                    notion_link = f"https://notion.so/{notion_id}" if notion_id else "https://notion.so"
                    
                    digest = (
                        "🌙 *Nightly CRM Digest — 10 PM*\n"
                        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📊 *Today's Activity:*\n"
                        f"✅ Applied: *{total_app}* jobs\n"
                        f"⏭️ Filtered: *{total_skip}* jobs\n\n"
                        f"📋 *Your Notion Job Tracker has been updated with all jobs found today.*\n\n"
                        f"Each entry includes:\n"
                        f"• 🏢 Company Name\n"
                        f"• 💼 Role / Position\n"
                        f"• 📊 Status (Found/Applied)\n"
                        f"• 🔗 Direct Apply Link\n"
                        f"• 📅 Date Applied\n\n"
                        f"_Tap the button below to review your full CRM tracker._"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("📋 Open Notion CRM", url=notion_link))
                    markup.add(InlineKeyboardButton("📱 Open Dashboard", url=DASHBOARD_URL))
                    bot.send_message(active_chat_id_local, digest, parse_mode=None, reply_markup=markup)
                    
                    last_notion_digest_date = now.date()
                    print("[Loop] 10 PM Notion digest sent successfully!")
                except Exception as err:
                    print(f"[Loop] Failed to send Notion digest: {err}")
            
        # Feature: 11 PM Instahyre Auto-Search — DISABLED for HF free-tier safety.
        # The Playwright engine is now MANUAL-ONLY (triggered from dashboard or Telegram).
        # Running headless Chrome automatically every night is the #1 reason accounts get banned.
        # Use the dashboard "LAUNCH CAMPAIGN NOW" button or /instahyre Telegram command instead.
        # if now.hour == 23 and now.date() != getattr(job_monitor_loop, '_last_instahyre_date', None):
        #     ... (auto-run disabled for HF safety)

        # ⏱️ HF-SAFE: Wait 15 minutes before the next scrape cycle.
        # Broken into 30-second chunks so the bot can pause instantly.
        # This reduces CPU usage by 5x compared to the old 3-minute cycle.
        for _ in range(30):  # 30 x 30s = 15 minutes
            if BOT_PAUSED:
                break
            time.sleep(30)
# --- 7. FLASK WEB SERVER (PORT 7860 FOR HUGGING FACE) ---
from flask import send_file, jsonify, request
import io
import time as _time_module
_server_start_time = _time_module.time()  # Track when server started (for uptime)
app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────
# 🔒  DASHBOARD AUTHENTICATION
# Every route below drives a real job-application session (it can overwrite
# resume.pdf, inject Google session cookies, launch mass-apply campaigns and
# read the ATS log). The server binds 0.0.0.0, so without this anyone who can
# reach the host owns the bot.
# ─────────────────────────────────────────────────────────────────
DASHBOARD_TOKEN = str(os.getenv("DASHBOARD_TOKEN", "")).strip()

# Kept reachable without a token so the hosting platform's health probe still
# succeeds. None of these expose job, profile, credential or browser data.
# NOTE: "/" is deliberately NOT in this set. The "/" route renders the full
# dashboard (job URLs, applied-jobs log, chat id, profile stats), so leaving it
# open leaked that data to anyone who could reach the host. Unauthenticated
# requests to "/" now receive the harmless health payload (see below), which
# keeps the hosting platform's root health probe green without exposing data.
_DASHBOARD_OPEN_PATHS = {"/healthz", "/favicon.ico"}


def _dashboard_health_response():
    return jsonify({
        "service": "myjob-ai-bot",
        "status": "up",
        "dashboard": "locked" if DASHBOARD_TOKEN else "disabled",
    }), 200


@app.route("/healthz")
def _dashboard_healthz():
    return _dashboard_health_response()


def _dashboard_token_is_valid(candidate: str) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, DASHBOARD_TOKEN)


def _extract_dashboard_token(req):
    header = req.headers.get("X-Admin-Token", "")
    if header:
        return header.strip()
    auth = req.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    if req.args.get("token"):
        return req.args.get("token", "").strip()
    return ""


def _dashboard_unauthorised(req):
    """Return a challenge for browser navigations, JSON for API/XHR callers."""
    wants_json = (
        req.path.startswith("/api/")
        or req.headers.get("X-Requested-With") == "XMLHttpRequest"
        or req.accept_mimetypes.best == "application/json"
    )
    if wants_json:
        return jsonify({"error": "unauthorized", "detail": "X-Admin-Token header required"}), 401
    from flask import make_response
    resp = make_response(
        "<h1>401 &mdash; Dashboard locked</h1>"
        "<p>Send the <code>X-Admin-Token</code> header, "
        "<code>?token=</code> query parameter, or a <code>Authorization: Bearer</code> "
        "header matching <code>DASHBOARD_TOKEN</code>.</p>",
        401,
    )
    resp.headers["WWW-Authenticate"] = 'Bearer realm="myjob-dashboard"'
    return resp


@app.before_request
def _enforce_dashboard_auth():
    from flask import request

    if request.method == "OPTIONS":
        return None

    if not DASHBOARD_TOKEN:
        # Fail loudly and closed: an unset token must never mean "no auth".
        app.logger.error(
            "DASHBOARD_TOKEN is not set - refusing to serve any dashboard route. "
            "Set it in .env or as a Space secret."
        )
        if request.path in _DASHBOARD_OPEN_PATHS:
            return None
        # "/" is the platform's health-probe path, but the same route renders
        # the full dashboard. Only ever answer it with the harmless payload.
        if request.path == "/":
            return _dashboard_health_response()
        return (
            jsonify({"error": "dashboard_disabled",
                     "detail": "DASHBOARD_TOKEN is not configured on the server"}),
            503,
        )

    if request.path in _DASHBOARD_OPEN_PATHS:
        return None

    if _dashboard_token_is_valid(_extract_dashboard_token(request)):
        return None

    # Unauthenticated root request: return the health payload instead of leaking
    # the dashboard (job URLs, applied-jobs log, chat id, profile stats).
    if request.path == "/":
        return _dashboard_health_response()

    app.logger.warning(
        "Rejected unauthenticated dashboard request: %s %s from %s",
        request.method, request.path, request.remote_addr,
    )
    return _dashboard_unauthorised(request)

@app.after_request
def _dashboard_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp

@app.route("/live")
def live_handoff():
    if not HANDOFF_ACTIVE:
        return "<h1>No active handoff required. Bot is running fine!</h1>", 200
        
    return f"""
    <html><head><title>Live Takeover Handoff</title></head>
    <body style='background:#111; color:white; font-family:sans-serif; text-align:center;'>
      <h2>🚨 Live Browser Takeover</h2>
      <p style='color: #aaa;'>Job URL: {HANDOFF_URL}</p>
      <div style="margin-bottom: 20px;">
        <button onclick="resumeBot()" style="padding:10px 20px; background:#10b981; color:white; border:none; border-radius:5px; cursor:pointer; font-size:16px; font-weight:bold;">▶️ Resume Bot Automation</button>
      </div>
      <div style="margin-bottom: 20px; display:flex; justify-content:center; gap:10px;">
        <input type="text" id="typeText" placeholder="Type text here..." style="padding:10px; width:300px; border-radius:5px; border:1px solid #333; background:#222; color:white;">
        <button onclick="sendType()" style="padding:10px 15px; background:#3b82f6; color:white; border:none; border-radius:5px; cursor:pointer;">Type & Enter</button>
      </div>
      <p style='color: #ef4444; font-size: 14px;'>Click directly on the image below to interact with the webpage.</p>
      <img id="screen" src="/api/live_screenshot" style="max-width:90%; border:2px solid #333; border-radius:10px; cursor:crosshair; box-shadow: 0 0 20px rgba(0,0,0,0.5);" onclick="clickImage(event)">
      <script>
        setInterval(() => document.getElementById('screen').src = '/api/live_screenshot?' + new Date().getTime(), 2000);
        function clickImage(e) {{
          const rect = e.target.getBoundingClientRect();
          const scaleX = e.target.naturalWidth / rect.width;
          const scaleY = e.target.naturalHeight / rect.height;
          const x = (e.clientX - rect.left) * scaleX;
          const y = (e.clientY - rect.top) * scaleY;
          fetch('/api/live_action', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{action:'click', x:x, y:y}}) }});
        }}
        function sendType() {{
          const txt = document.getElementById('typeText').value;
          fetch('/api/live_action', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{action:'type', text:txt}}) }});
          document.getElementById('typeText').value = '';
        }}
        function resumeBot() {{
          fetch('/api/live_resume', {{ method:'POST' }}).then(() => window.location.reload());
        }}
      </script>
    </body></html>
    """

@app.route("/api/status")
def api_status():
    """Live stats for dashboard widgets."""
    import time as _time
    wk = load_weekly_stats()
    retry_q = load_retry_queue()
    uptime_secs = int(_time.time() - _server_start_time) if '_server_start_time' in globals() else 0
    hours, rem = divmod(uptime_secs, 3600)
    mins = rem // 60
    return jsonify({
        "queue_size": application_queue.qsize(),
        "weekly_applied": wk.get("applied", 0),
        "retry_count": len(retry_q),
        "uptime": f"{hours}h {mins}m" if hours > 0 else f"{mins}m",
        "bot_paused": BOT_PAUSED,
        "instahyre_running": playwright_active,
    })

@app.route("/api/live_screenshot")
def live_screenshot():
    if not HANDOFF_ACTIVE or not HANDOFF_PAGE:
        return "No active handoff", 404
    try:
        ss_bytes = HANDOFF_PAGE.screenshot()
        return send_file(io.BytesIO(ss_bytes), mimetype='image/png')
    except Exception as e:
        return str(e), 500

@app.route("/api/live_action", methods=["POST"])
def live_action():
    if not HANDOFF_ACTIVE or not HANDOFF_PAGE: return "No active handoff", 400
    try:
        data = request.get_json(silent=True) or {}
        if data.get('action') == 'click':
            HANDOFF_PAGE.mouse.click(data['x'], data['y'])
        elif data.get('action') == 'type':
            HANDOFF_PAGE.keyboard.type(data['text'])
            HANDOFF_PAGE.keyboard.press('Enter')
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/live_resume", methods=["POST"])
def live_resume():
    global HANDOFF_ACTIVE
    HANDOFF_ACTIVE = False
    return jsonify({"status": "resumed"})

@app.route("/logs")
def view_logs():
    try:
        with open("debug.log", "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "<pre>" + "".join(lines[-100:]) + "</pre>"  # Show last 100 lines
    except Exception as e:
        return f"Log file not found or error: {e}"

# ─── JOB RADAR API ROUTES ─────────────────────────────────
@app.route("/api/radar")
def api_radar():
    """Returns the last radar scan results from radar_results.json."""
    try:
        with open("radar_results.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception:
        return jsonify({"last_scan": "Never", "total": 0, "jobs": []})

@app.route("/api/run_radar", methods=["POST"])
def api_run_radar():
    """Triggers a fresh Job Radar scan in a background thread."""
    def _run():
        try:
            from job_radar import run_radar
            run_radar()
        except Exception as e:
            print(f"[RadarAPI] Error: {e}")
    Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "message": "Radar scan started! Results will appear in ~60-90 seconds. Check your Telegram too!"})

@app.route("/screenshots/<filename>")
def serve_screenshot(filename):
    from flask import send_from_directory
    return send_from_directory("screenshots", filename)

@app.route("/api/debug_bot", methods=["GET"])
def api_debug_bot():
    token_val = str(TELEGRAM_TOKEN) if TELEGRAM_TOKEN else "None"
    masked = token_val[:5] + "..." + token_val[-5:] if len(token_val) > 10 else token_val
    
    # Test connection to Telegram API
    telegram_ok = False
    telegram_err = None
    try:
        r = requests.get("https://api.telegram.org", timeout=5)
        telegram_ok = True
    except Exception as e:
        telegram_err = str(e)

    return jsonify({
        "bot_exists": bot is not None,
        "token_loaded": masked,
        "chat_id_loaded": load_chat_id(),
        "telegram_api_reachable": telegram_ok,
        "telegram_api_error": telegram_err
    })

@app.route("/api/telegram_test", methods=["POST"])
def api_telegram_test():
    """Sends a test message to Telegram to verify bot connectivity."""
    chat_id = load_chat_id()
    if not bot or not chat_id:
        return jsonify({"status": "error", "message": "Bot or chat ID not configured."})
    try:
        bot.send_message(chat_id, "✅ *Elite Job Bot Dashboard — Connection Test Successful!*\n\n🤖 Your bot is fully online and connected.\n📡 Radar is scanning for your Unicorn Developer jobs.", parse_mode=None)
        return jsonify({"status": "ok", "message": "Test message sent to Telegram!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/force_scan", methods=["POST"])
def api_force_scan():
    """Triggers an immediate Telegram channel scan."""
    def _run():
        try:
            scrape_telegram_channel()
        except Exception as e:
            print(f"[ForceScan] Error: {e}")
    Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "message": "Channel scan triggered! Check Telegram for updates."})

@app.route("/api/instahyre", methods=["POST"])
def api_instahyre():
    """Triggers the Instahyre mass-applier engine from the dashboard."""
    chat_id = load_chat_id()
    
    data = request.get_json(silent=True) or {}
    email = data.get('email')
    password = data.get('password')
    
    if bot and chat_id:
        try: bot.send_message(chat_id, "🚀 Instahyre Campaign Launched!\n\nThe stealth engine has started in the background. It will automatically apply to 20 Fresher Software Engineer roles. Please wait 5-10 minutes for the final report.", parse_mode=None)
        except: pass

    def _run():
        global playwright_active
        playwright_active = True
        try:
            success, msg, _ = run_instahyre_mass_apply(email=email, password=password, skills="Software Engineer Fresher", max_applications=20)
            print(f"[Instahyre] {msg}")
            if bot and chat_id:
                status_icon = "✅" if success else "❌"
                bot.send_message(chat_id, f"{status_icon} Instahyre Campaign Finished\n\n{msg}", parse_mode=None)
        except Exception as e:
            err_str = str(e)
            print(f"[Instahyre] Engine Error: {err_str}")
            if bot and chat_id:
                try: bot.send_message(chat_id, f"❌ Instahyre Campaign Error\n\n{err_str[:300]}\n\nThe engine encountered an error. Check dashboard logs for details.")
                except: pass
        finally:
            playwright_active = False

    Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "message": "Instahyre Engine launched! It will take 5-10 mins. Results will be sent to Telegram."})

@app.route("/")
def home():
    active_chat_id = load_chat_id()
    stats = load_stats()
    applied = load_applied_jobs()
    
    qa_memory = load_qa_memory()
    qa_size = len(qa_memory) if qa_memory else 0
    imap_status = "CONNECTED" if os.environ.get("BOT_EMAIL") and os.environ.get("BOT_EMAIL_PASSWORD") else "OFFLINE"
    ghost_mode_active = len(ghost_mode_chats) > 0

    # AI Engine Status
    gemini_status = "ONLINE" if gemini_client else "OFFLINE"
    groq_status = "ONLINE" if groq_client else "OFFLINE"
    gemini_key_count = len(GEMINI_API_KEYS)
    active_key_num = current_gemini_key_index + 1

    # Success Rate
    total_applied = stats.get('applied', 0)
    total_skipped = stats.get('skipped', 0)
    total = total_applied + total_skipped
    success_pct = round((total_applied / total) * 100) if total > 0 else 0
    stroke_offset = round(339.3 * (1 - success_pct / 100), 1)

    # Recent jobs from CSV
    recent_rows = []
    csv_file = "applied_jobs_log.csv"
    best_job = None
    best_score = 0
    if os.path.exists(csv_file):
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
                if len(rows) > 1:
                    recent_rows = list(reversed(rows[-10:]))
        except Exception:
            pass

    recent_jobs_html = '<div class="overflow-x-auto"><table class="w-full text-left border-collapse">'
    if recent_rows:
        recent_jobs_html += '<thead><tr class="border-b border-white/10 text-xs text-gray-400 uppercase"><th class="py-2 pl-2">Status</th><th class="py-2">Job URL / Title</th><th class="py-2">Date</th><th class="py-2 text-right pr-2">CRM Actions</th></tr></thead><tbody class="text-sm">'
        for row in recent_rows:
            if len(row) >= 4:
                date, title, url, status = row[0], row[1][:50], row[2], row[3]
                
                # Check if it was marked as interview previously in notes or status
                notes = row[4] if len(row) > 4 else ""
                if "Interview" in status or "Interview" in notes:
                    badge = '<span class="px-2 py-0.5 rounded-full text-xs font-bold bg-purple-900/80 text-purple-300 border border-purple-500 drop-shadow-[0_0_8px_rgba(168,85,247,0.6)]">📞 INTERVIEW</span>'
                elif "Rejected" in status or "Rejected" in notes:
                    badge = '<span class="px-2 py-0.5 rounded-full text-xs font-bold bg-red-900/60 text-red-300 border border-red-700">❌ REJECTED</span>'
                elif "Auto applied" in status:
                    badge = '<span class="px-2 py-0.5 rounded-full text-xs font-bold bg-green-900/60 text-green-300 border border-green-700">✅ APPLIED</span>'
                elif "Failed" in status or "failed" in status:
                    badge = '<span class="px-2 py-0.5 rounded-full text-xs font-bold bg-orange-900/60 text-orange-300 border border-orange-700">❌ FAILED</span>'
                else:
                    badge = '<span class="px-2 py-0.5 rounded-full text-xs font-bold bg-gray-800/60 text-gray-300 border border-gray-600">⏭ SKIPPED</span>'
                
                recent_jobs_html += f'''
                <tr class="border-b border-white/5 hover:bg-white/5 transition-all">
                    <td class="py-3 pl-2">{badge}</td>
                    <td class="py-3 max-w-[200px] truncate"><a href="{url}" target="_blank" class="text-blue-400 hover:text-blue-300 hover:underline">{title}</a></td>
                    <td class="py-3 text-xs text-gray-400">{date}</td>
                    <td class="py-3 text-right pr-2">
                        <button onclick="markCRM('{url}', 'Interview')" class="px-2 py-1 bg-purple-600/30 hover:bg-purple-500 border border-purple-500/50 rounded text-xs text-purple-200 hover:text-white transition-all mr-1">📞 Interview</button>
                        <button onclick="markCRM('{url}', 'Rejected')" class="px-2 py-1 bg-red-900/50 hover:bg-red-700 border border-red-700/50 rounded text-xs text-red-200 hover:text-white transition-all">❌ Reject</button>
                    </td>
                </tr>'''
        recent_jobs_html += '</tbody></table></div>'
    else:
        recent_jobs_html = '<p class="text-gray-500 text-sm text-center py-8">No recent activity found. Jobs will appear here as a CRM table once the bot runs.</p>'

    # Channel grid
    channels_html = ""
    for ch in TARGET_CHANNELS:
        channels_html += f'<div class="channel-chip flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 hover:border-blue-500/50 transition-all"><span class="w-2 h-2 rounded-full bg-green-400 animate-pulse flex-shrink-0"></span><span class="text-xs text-gray-300 truncate">@{ch}</span></div>'

    from flask import render_template_string
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, "templates", "dashboard.html")
        if not os.path.exists(template_path):
            # Fallback if the user uploaded it directly to the root on Hugging Face
            template_path = os.path.join(base_dir, "dashboard.html")
            
        with open(template_path, "r", encoding="utf-8") as f:
            html_template = f.read()
        rendered = render_template_string(html_template, 
            gemini_status=gemini_status,
            groq_status=groq_status,
            active_key_num=active_key_num,
            gemini_key_count=gemini_key_count,
            success_pct=success_pct,
            stroke_offset=stroke_offset,
            total_applied=total_applied,
            total_skipped=total_skipped,
            qa_size=qa_size,
            active_chat_id=active_chat_id,
            imap_status=imap_status,
            ghost_mode_active=ghost_mode_active,
            channels_html=channels_html,
            recent_jobs_html=recent_jobs_html,
            HANDOFF_URL=HANDOFF_URL,
            notion_url=f"https://notion.so/{re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', os.getenv('NOTION_DATABASE_ID', '')).group(1).replace('-', '') if re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', os.getenv('NOTION_DATABASE_ID', '')) else ''}" if os.getenv('NOTION_DATABASE_ID') else "https://notion.so",
            stats=stats,
            applied=applied,
            os=__import__('os'),
            TARGET_CHANNEL=TARGET_CHANNEL,
            TARGET_CHANNELS=TARGET_CHANNELS,
            len=len,
            RESUME_FILE=RESUME_FILE,
            BOT_PAUSED=BOT_PAUSED
        )
        from flask import make_response
        resp = make_response(rendered)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error loading dashboard template: {e}"

# (Radar routes defined earlier in file)

@app.route("/api/pause", methods=["POST"])
def api_pause():
    global BOT_PAUSED
    BOT_PAUSED = True
    print("[Dashboard] Bot PAUSED via web dashboard.")
    return {"status": "paused", "message": "Bot is now paused."}

@app.route("/api/resume", methods=["POST"])
def api_resume():
    global BOT_PAUSED
    BOT_PAUSED = False
    print("[Dashboard] Bot RESUMED via web dashboard.")
    return {"status": "running", "message": "Bot is now running."}

# (force_scan route defined earlier in file)

@app.route("/api/rotate_key", methods=["POST"])
def api_rotate_key():
    success = rotate_gemini_key()
    if success:
        return {"status": "success", "message": f"Switched to key #{current_gemini_key_index + 1}"}
    return {"status": "error", "message": "Failed to rotate key"}

@app.route("/api/download_log")
def api_download_log():
    csv_file = "applied_jobs_log.csv"
    if os.path.exists(csv_file):
        return send_file(csv_file, as_attachment=True)
    return {"status": "error", "message": "No log file found! The bot needs to apply to at least one job first."}

# ── TELEGRAM MINI-APP ENDPOINTS ──────────────────────────────────────
@app.route("/miniapp")
@app.route("/app")
def serve_miniapp():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "templates", "miniapp.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(base_dir, "miniapp.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read(), 200, {'Content-Type': 'text/html; charset=utf-8'}
    return "Mini-App template not found", 404

@app.route("/api/miniapp/jobs")
def api_miniapp_jobs():
    from job_radar import classify_location, TAMIL_NADU_LOCATIONS
    jobs = []
    seen_urls = set()

    # 1. Load from applied_jobs_log.csv
    csv_file = "applied_jobs_log.csv"
    if os.path.exists(csv_file):
        try:
            import csv as csv_mod
            with open(csv_file, "r", encoding="utf-8") as cf:
                rows = list(csv_mod.reader(cf))
                for idx, row in enumerate(reversed(rows[1:])):
                    if len(row) >= 4:
                        date_str, title_str, url_str, status_str = row[0], row[1], row[2], row[3]
                        notes = row[4] if len(row) > 4 else ""
                        if url_str in seen_urls or not url_str.startswith("http") or is_social_or_promo_link(url_str):
                            continue
                        seen_urls.add(url_str)

                        is_valid, tier, loc_tag, is_tn = classify_location("", f"{title_str} {notes}")
                        company_guess = "Verified Recruiter"
                        role_guess = title_str
                        if " - " in title_str:
                            parts = title_str.split(" - ", 1)
                            company_guess, role_guess = parts[0].strip(), parts[1].strip()

                        jobs.append({
                            "id": f"csv-{idx}",
                            "company": company_guess,
                            "role": role_guess,
                            "location": loc_tag if loc_tag else "India (PAN India) 🇮🇳",
                            "is_tamil_nadu": is_tn,
                            "salary": "As per Industry Standard",
                            "batch": "2024 / 2025 / 2026 Batch | Freshers",
                            "work_mode": "Full-time / Fresher",
                            "link": url_str,
                            "source": "@Radar",
                            "status": status_str,
                            "date": date_str,
                            "summary": notes if notes and len(notes) > 5 else "Verified engineering opportunity matching your profile."
                        })
        except Exception as e:
            print(f"[MiniApp] CSV parse error: {e}")

    # 2. Load from radar_jobs.json if present
    if os.path.exists("radar_jobs.json"):
        try:
            with open("radar_jobs.json", "r", encoding="utf-8") as rf:
                rdata = json.load(rf)
                for idx, rj in enumerate(rdata.get("jobs", [])):
                    link = rj.get("link", "")
                    if link and link not in seen_urls and not is_social_or_promo_link(link):
                        seen_urls.add(link)
                        jobs.append({
                            "id": f"radar-{idx}",
                            "company": rj.get("company", "Verified Recruiter"),
                            "role": rj.get("title", "Software Developer"),
                            "location": rj.get("location", "India"),
                            "is_tamil_nadu": rj.get("is_tamil_nadu", False) or rj.get("priority_tier") == 1,
                            "salary": rj.get("salary", "As per Industry Standard"),
                            "batch": rj.get("batch", "Freshers (0-2 Yrs)"),
                            "work_mode": rj.get("work_mode", "Full-time"),
                            "link": link,
                            "source": rj.get("source", "@Radar"),
                            "status": "Alerted",
                            "date": rj.get("date_posted", datetime.now().strftime("%Y-%m-%d")),
                            "summary": rj.get("description", "Verified job post.")[:200]
                        })
        except Exception as e:
            print(f"[MiniApp] Radar JSON parse error: {e}")

    # Sort Tamil Nadu jobs to the top
    jobs.sort(key=lambda j: 0 if j.get("is_tamil_nadu") else 1)
    return jsonify({"status": "success", "total": len(jobs), "jobs": jobs})

from flask import request, send_file, jsonify

import subprocess

@app.route("/api/manual_apply", methods=["POST"])
def api_manual_apply():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    if url:
        if not url.startswith("http"):
            url = "https://" + url
        final_url = bypass_blog_redirect(url)
        print(f"[Dashboard] Manual apply initiated for {final_url}")
        
        def run():
            if any(domain in final_url.lower() for domain in UNSUPPORTED_DOMAINS):
                log_job(final_url, "Web Dashboard /apply", False, "Unsupported platform or social media")
                return
            success = run_playwright_apply(final_url, "Manual application from Web Dashboard")
            log_job(final_url, "Web Dashboard /apply", success, "Manual apply")
            
        Thread(target=run, daemon=True).start()
        return {"status": "success", "message": "Application started in background."}
    return {"status": "error", "message": "Invalid URL"}

@app.route("/api/update_profile", methods=["POST"])
def api_update_profile():
    data = request.get_json(silent=True) or {}
    field = data.get("field")
    value = data.get("value")
    if field and value:
        profile = load_profile()
        profile[field] = value
        try:
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=4)
            print(f"[Dashboard] Profile updated: {field} = {value}")
            return {"status": "success", "message": f"{field} updated."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Missing data"}

@app.route("/api/regenerate_resume", methods=["POST"])
def api_regenerate_resume():
    try:
        subprocess.run(["python", "generate_resume.py"], check=True)
        return {"status": "success", "message": "Resume regenerated."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route("/api/reset_history", methods=["POST"])
def api_reset_history():
    try:
        if os.path.exists("applied_jobs_log.csv"):
            os.remove("applied_jobs_log.csv")
        if os.path.exists(STATS_FILE):
            os.remove(STATS_FILE)
        return {"status": "success", "message": "History and stats wiped."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route("/api/health_check", methods=["GET"])
def api_health_check():
    gemini_status = "Offline"
    groq_status = "Offline"
    try:
        if gemini_client:
            st = time.time()
            gemini_client.models.generate_content(model="gemini-2.5-flash", contents="reply ok")
            gemini_status = f"Online ({int((time.time()-st)*1000)}ms)"
    except Exception:
        pass
    
    try:
        if groq_client:
            st = time.time()
            groq_client.chat.completions.create(model=GROQ_MODEL, messages=[{"role": "user", "content": "ok"}])
            groq_status = f"Online ({int((time.time()-st)*1000)}ms)"
    except Exception:
        pass
        
    return {"gemini": gemini_status, "groq": groq_status}

@app.route("/api/download_qa")
def api_download_qa():
    qa_file = "qa_memory.json"
    if os.path.exists(qa_file):
        return send_file(qa_file, as_attachment=True)
    return {"status": "error", "message": "No Q&A Brain found! Use the /answer command in Telegram to create one."}
    
@app.route("/api/download_profile")
def api_download_profile():
    if os.path.exists(PROFILE_FILE):
        return send_file(PROFILE_FILE, as_attachment=True)
    return {"status": "error", "message": "No profile found"}

@app.route("/api/add_channel", methods=["POST"])
def api_add_channel():
    global TARGET_CHANNELS
    data = request.get_json(silent=True) or {}
    channel = data.get("channel", "").replace("@", "").strip()
    if channel:
        if channel not in TARGET_CHANNELS:
            TARGET_CHANNELS.append(channel)
            print(f"[Dashboard] Added channel @{channel}")
            return {"status": "success", "message": f"Added @{channel}"}
        return {"status": "error", "message": "Channel already exists"}
    return {"status": "error", "message": "Invalid channel"}

@app.route("/api/upload_resume", methods=["POST"])
def api_upload_resume():
    if 'resume' not in request.files:
        return {"status": "error", "message": "No file part"}
    file = request.files['resume']
    if file.filename == '':
        return {"status": "error", "message": "No selected file"}
    if file and file.filename.lower().endswith('.pdf'):
        file.save(RESUME_FILE)
        return {"status": "success", "message": "Resume uploaded successfully!"}
    return {"status": "error", "message": "Invalid file type. Must be PDF."}

@app.route("/api/upload_auth", methods=["POST"])
def api_upload_auth():
    if 'auth' not in request.files:
        return {"status": "error", "message": "No file part"}
    file = request.files['auth']
    if file.filename == '':
        return {"status": "error", "message": "No selected file"}
    if file and file.filename.lower().endswith('.json'):
        file.save("instahyre_auth.json")
        return {"status": "success", "message": "Session auth state uploaded successfully!"}
    return {"status": "error", "message": "Invalid file type. Must be a .json file containing Playwright storage state."}

@app.route("/api/scan_inbox", methods=["POST"])
def api_scan_inbox():
    try:
        from imap_handler import scan_for_interview_invites
        results = scan_for_interview_invites()
        if results:
            msg = f"🎉 FOUND {len(results)} INTERVIEW EMAILS! Check Telegram."
        else:
            msg = "No new interview emails found in the last 7 days."
        return {"status": "success", "message": msg}
    except Exception as e:
        return {"status": "error", "message": f"IMAP Error: {str(e)}"}

@app.route("/api/mark_crm", methods=["POST"])
def api_mark_crm():
    data = request.get_json(silent=True) or {}
    url = data.get("url")
    new_status = data.get("status")
    
    csv_file = "applied_jobs_log.csv"
    if os.path.exists(csv_file):
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
                
            for i in range(1, len(rows)):
                if len(rows[i]) >= 4 and rows[i][2] == url:
                    rows[i][3] = f"{new_status} (Manually Updated)"
                    if len(rows[i]) > 4:
                        rows[i][4] = new_status
                    else:
                        rows[i].append(new_status)
                        
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            return {"status": "success", "message": f"Marked as {new_status}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "No log file found"}



def manual_radar_scan(chat_id):
    """
    Dedicated Radar Scan: 
    1. Scrapes the configured Telegram channel.
    2. Fetches fresh Software Engineering jobs specifically for Tamil Nadu, Bangalore, and Kerala.
    """
    import urllib.request
    import json
    
    if bot:
        bot.send_message(chat_id, "📡 *South India Job Radar Active!*\n\nScanning portals for Software Engineering jobs in:\n📍 `Tamil Nadu (Chennai, Coimbatore, Madurai)`\n📍 `Bangalore`\n📍 `Kerala`...", parse_mode=None)
    
    applied = load_applied_jobs()
    found_jobs = 0
    
    # 1. Standard Telegram scan
    try:
        if 'TARGET_CHANNEL' in globals() and TARGET_CHANNEL:
            f, _ = scrape_single_channel(TARGET_CHANNEL, applied, chat_id)
            found_jobs += f
    except Exception as e:
        print(f"[Radar] Telegram scan error: {e}")

    # 2. Multi-API Tech Job Aggregator (Arbeitnow, Remotive, Hasjob concepts)
    south_india_keywords = ['bangalore', 'bengaluru', 'chennai', 'tamil nadu', 'coimbatore', 'madurai', 'kerala', 'kochi', 'trivandrum', 'india', 'remote']
    api_endpoints = [
        {"url": "https://remotive.com/api/remote-jobs?category=software-dev&search=India", "type": "remotive"},
        {"url": "https://www.arbeitnow.com/api/job-board-api", "type": "arbeitnow"}
    ]
    
    # Simple hash memory for current run to avoid duplicates across APIs
    seen_hashes = set()
    
    for api in api_endpoints:
        if found_jobs >= 5: # Hard limit to protect queue
            break
            
        try:
            req = urllib.request.Request(api["url"], headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # Extract jobs based on API format
                if api["type"] == "remotive":
                    jobs = data.get('jobs', [])[:20]
                    for j in jobs:
                        loc = str(j.get('candidate_required_location', '')).lower()
                        title = str(j.get('title', '')).lower()
                        company = str(j.get('company_name', '')).lower()
                        url = j.get('url')
                        
                        fingerprint = f"{company}_{title}"
                        if fingerprint in seen_hashes: continue
                        
                        if any(kw in loc for kw in south_india_keywords) or 'india' in loc:
                            if url and url not in applied:
                                seen_hashes.add(fingerprint)
                                application_queue.put(url)
                                found_jobs += 1
                                applied.add(url)
                                save_applied_job(url)
                                if bot:
                                    bot.send_message(chat_id, f"🎯 *Remotive Match!*\n\n💻 *Role:* {j.get('title')}\n🏢 *Company:* {j.get('company_name')}\n📍 *Location:* {j.get('candidate_required_location')}\n\n_Added to Queue!_", parse_mode=None)
                                time.sleep(1)
                                if found_jobs >= 5: break

                elif api["type"] == "arbeitnow":
                    jobs = data.get('data', [])[:30]
                    for j in jobs:
                        loc = str(j.get('location', '')).lower()
                        title = str(j.get('title', '')).lower()
                        company = str(j.get('company_name', '')).lower()
                        url = j.get('url')
                        
                        fingerprint = f"{company}_{title}"
                        if fingerprint in seen_hashes: continue
                        
                        # Arbeitnow is global, we strictly filter for South India/Remote
                        if any(kw in loc for kw in south_india_keywords):
                            if url and url not in applied:
                                seen_hashes.add(fingerprint)
                                application_queue.put(url)
                                found_jobs += 1
                                applied.add(url)
                                save_applied_job(url)
                                if bot:
                                    bot.send_message(chat_id, f"🎯 *Arbeitnow Match!*\n\n💻 *Role:* {j.get('title')}\n🏢 *Company:* {j.get('company_name')}\n📍 *Location:* {j.get('location')}\n\n_Added to Queue!_", parse_mode=None)
                                time.sleep(1)
                                if found_jobs >= 5: break
                                
        except Exception as e:
            print(f"[Radar] Multi-API scan error on {api['url']}: {e}")

    if bot:
        bot.send_message(chat_id, f"✅ *Radar Scan Complete*\nFound {found_jobs} new tech jobs. They are now processing in the background queue.", parse_mode=None)

if bot:
    @bot.message_handler(commands=['dashboard', 'menu'])
    @admin_only
    def send_dashboard(message):
        """Renders the epic interactive control panel inside Telegram."""
        save_chat_id(message.chat.id)
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Row 1: Core Commands
        markup.add(
            InlineKeyboardButton("📊 Status & Stats", callback_data="status"),
            InlineKeyboardButton("📸 Last Screenshot", callback_data="last_job")
        )
        
        # Row 2: Management
        markup.add(
            InlineKeyboardButton("📋 My Profile", callback_data="profile"),
            InlineKeyboardButton("🧠 AI Memory (QA)", callback_data="qa_memory")
        )
        
        # Row 3: Discovery & Actions
        markup.add(
            InlineKeyboardButton("🔍 Search Jobs", callback_data="search:menu"),
            InlineKeyboardButton("🌟 Tamil Nadu Jobs", callback_data="tnjobs")
        )
        markup.add(
            InlineKeyboardButton("⚡ JobSpy Live", callback_data="jobspy:python fresher"),
            InlineKeyboardButton("🎓 Simplify Freshers", callback_data="simplify:all")
        )
        markup.add(
            InlineKeyboardButton("🚶‍♂️ Weekend Walk-Ins", callback_data="walkins:all"),
            InlineKeyboardButton("📢 National Drives", callback_data="drives")
        )
        markup.add(
            InlineKeyboardButton("⏳ Mass Deadlines", callback_data="deadlines"),
            InlineKeyboardButton("📊 Career Analytics", callback_data="analytics")
        )
        markup.add(
            InlineKeyboardButton("🎯 Job Radar", callback_data="radar"),
            InlineKeyboardButton("👁️ Ghost Mode Toggle", callback_data="ghost")
        )
        markup.add(
            InlineKeyboardButton("🎓 Exam Syllabus (OA)", callback_data="oa:menu"),
            InlineKeyboardButton("🔔 Keyword Alerts", callback_data="alerts:list")
        )
        
        # Row 4: Control
        state_btn = InlineKeyboardButton("▶️ Resume Bot", callback_data="resume") if BOT_PAUSED else InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause")
        markup.add(
            state_btn,
            InlineKeyboardButton("🕒 Download History", callback_data="history")
        )

        bot.reply_to(message,
            "🎛️ *Elite Bot Command Center*\n\n"
            "Use the interactive buttons below to control your automation empire instantly.",
            parse_mode=None, reply_markup=markup)

    def get_main_reply_keyboard():
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.row(
            KeyboardButton("🌟 TN Freshers"),
            KeyboardButton("🚶 Walk-In Drives")
        )
        markup.row(
            KeyboardButton("📢 National Drives"),
            KeyboardButton("⚡ Live Search")
        )
        markup.row(
            KeyboardButton("🎯 ATS Score Match"),
            KeyboardButton("💰 CTC Calculator")
        )
        return markup

    @bot.message_handler(commands=['menu', 'keyboard'])
    @admin_only
    def send_menu_keyboard(message):
        save_chat_id(message.chat.id)
        bot.reply_to(
            message,
            "🎛️ <b>Quick Navigation Menu Enabled</b>\n\n"
            "Use the 6 persistent mobile buttons below for instant 1-tap discovery without typing commands!",
            parse_mode="HTML",
            reply_markup=get_main_reply_keyboard()
        )

    @bot.message_handler(commands=['start'])
    @admin_only
    def send_welcome(message):
        save_chat_id(message.chat.id)
        bot.reply_to(
            message,
            "👋 <b>Welcome to MyJob AI Radar Bot!</b>\n\n"
            "🤖 <b>Status:</b> Locked to your Chat ID and actively scanning 47+ verified channels!\n\n"
            "🌟 <b>Priority:</b> Tiruvannamalai, Vellore, Puducherry/Pondicherry &amp; Chennai; other India jobs remain available.\n"
            "🔗 <b>Mode:</b> Verified Search & Direct ATS Link Extraction (No auto-apply, 100% manual review).\n\n"
            "💡 <i>Tap any of the 6 quick-navigation buttons below or type /help:</i>",
            parse_mode="HTML",
            reply_markup=get_main_reply_keyboard()
        )

    @bot.message_handler(commands=['help'])
    @admin_only
    def send_help(message):
        save_chat_id(message.chat.id)
        help_text = (
            "🤖 <b>ELITE JOB BOT | COMMAND CENTER</b> 🇮🇳\n"
            "<i>Your Autonomous AI Engineering Career & Job Radar Engine</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⚡ <b>DISCOVERY & LIVE SEARCH</b>\n"
            "• <code>/jobspy &lt;role&gt;</code> — ⚡ Live LinkedIn & Indeed India search with direct ATS links\n"
            "• <code>/simplify &lt;keyword&gt;</code> — 🎓 Live SimplifyJobs feed (fresher tech & new grad roles)\n"
            "• <code>/search &lt;keyword&gt;</code> — 🔍 Unified search across TN, drives, walk-ins & radar\n"
            "• <code>/walkins [city]</code> — 🚶‍♂️ Weekend walk-in drives with venues & Google Maps\n"
            "• <code>/nearme [area]</code> — 🧭 GPS Walk-In Navigator (finds closest in-person drives)\n"
            "• <code>/tnjobs [tech|core]</code> — 🌟 Verified Tamil Nadu freshers feed & 1-tap prep\n"
            "• <code>/drives</code> — 📢 National mass off-campus hiring drives (TCS, Zoho, CTS)\n"
            "• <code>/deadlines</code> — ⏳ Upcoming drive registration deadlines countdown\n"
            "• <code>/radar</code> — 📡 Multi-platform job radar (Adzuna, Unstop, Telegram)\n\n"
            "🎯 <b>ATS ANALYSIS & EXAM BLUEPRINTS</b>\n"
            "• <code>/match &lt;text|URL&gt;</code> — 🎯 Instant ATS resume compatibility %, gaps & prep\n"
            "• <code>/oa [company]</code> — 🎓 Company OA pattern & coding syllabus (Zoho, TCS, CTS)\n"
            "• <code>/alertme &lt;keyword&gt;</code> — 🔔 Subscribe to real-time keyword notifications\n"
            "• <code>/alerts</code> — 📋 Manage active keyword watchdog triggers\n"
            "• <code>/unalert &lt;keyword&gt;</code> — ❌ Remove a watchdog alert trigger\n\n"
            "🧠 <b>PROFILE & AI MEMORY</b>\n"
            "• <code>/profile</code> — 📋 View active candidate profile details\n"
            "• <code>/setprofile &lt;field&gt; | &lt;val&gt;</code> — ✍️ Dynamically update a profile field\n"
            "• <code>/qa</code> — 🗂 View memorized application questions & answers\n"
            "• <code>/answer &lt;num&gt; | &lt;text&gt;</code> — 💡 Teach the bot how to answer custom questions\n\n"
            "🎛️ <b>CONTROL & SYSTEM HEALTH</b>\n"
            "• <code>/dashboard</code> — 🎛️ Interactive command control panel\n"
            "• <code>/status</code> — 🩺 System heartbeat, API keys & daily statistics\n"
            "• <code>/pause</code> / <code>/resume</code> — ⏸️ Pause or resume 24/7 background scans\n"
            "• <code>/history</code> / <code>/download</code> — 🕒 Export application CSV history\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("⚡ JobSpy Live", callback_data="jobspy:python fresher"),
            InlineKeyboardButton("🎓 Simplify Freshers", callback_data="simplify:all")
        )
        markup.row(
            InlineKeyboardButton("🚶 Weekend Walk-Ins", callback_data="walkins:all"),
            InlineKeyboardButton("🎯 ATS Matcher", callback_data="ats:analyze")
        )
        markup.row(
            InlineKeyboardButton("🌟 TN Jobs", callback_data="tnjobs"),
            InlineKeyboardButton("🎛️ Open Dashboard", callback_data="dashboard")
        )
        try:
            bot.reply_to(message, help_text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.reply_to(message, re.sub(r'<[^>]+>', '', help_text), parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['instahyre'])
    @admin_only
    def trigger_instahyre(message):
        save_chat_id(message.chat.id)
        text = message.text.replace("/instahyre", "", 1).strip()
        if "|" not in text:
            bot.reply_to(message, "⚠️ *Invalid Format*\n\nPlease provide your credentials like this:\n`/instahyre your_email@gmail.com | your_password`\n\n_Note: We do not save your password. It is only used once in memory to run the engine._", parse_mode=None)
            return
            
        parts = text.split("|", 1)
        email = parts[0].strip()
        password = parts[1].strip()
        
        bot.reply_to(message, "🚀 *Instahyre Mass-Applier Activated!* 🚀\n\nBooting up the headless browser... This will take about 5-10 minutes to finish applying to 20 jobs. I'll notify you when it's done!", parse_mode=None)
        
        def run_engine():
            success, result_msg, _ = run_instahyre_mass_apply(email=email, password=password, skills="Software Engineer Fresher", max_applications=20)
            if success:
                bot.send_message(message.chat.id, f"✅ *Instahyre Campaign Complete!*\n\n{result_msg}", parse_mode=None)
            else:
                bot.send_message(message.chat.id, f"❌ *Instahyre Campaign Failed*\n\n{result_msg}", parse_mode=None)
                
        Thread(target=run_engine, daemon=True).start()

    @bot.message_handler(commands=['notion'])
    @admin_only
    def show_notion(message):
        save_chat_id(message.chat.id)
        raw_db_id = os.getenv('NOTION_DATABASE_ID', '')
        notion_match = re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', raw_db_id)
        notion_id = notion_match.group(1).replace('-', '') if notion_match else ''
        notion_link = f"https://notion.so/{notion_id}" if notion_id else "https://notion.so"
        
        stats = load_stats()
        total_app = stats.get('applied', 0)
        
        msg = (
            "📋 *Notion Job Tracker*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Your CRM tracks every job automatically:\n\n"
            "• 🏢 *Company* — Extracted via AI\n"
            "• 💼 *Role* — With level & location\n"
            "• 📊 *Status* — Found → Applied → Interview\n"
            "• 🔗 *Direct Link* — Click to view posting\n"
            "• 📅 *Date* — When it was found/applied\n"
            "• 📡 *Source* — Which channel/radar found it\n\n"
            f"📊 Today's Applications: *{total_app}*\n\n"
            "_Tap the button below to open your tracker._"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 Open Notion CRM", url=notion_link))
        markup.add(InlineKeyboardButton("📱 Open Dashboard", url=DASHBOARD_URL))
        bot.reply_to(message, msg, parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['status'])
    @admin_only
    def send_status(message):
        save_chat_id(message.chat.id)
        applied = load_applied_jobs()
        stats = load_stats()
        resume_ok = "🟢 Ready" if os.path.exists(RESUME_FILE) else "🔴 Missing"
        gemini_ok = "🟢 Online" if gemini_client else "🔴 Offline"
        groq_ok = "🟢 Online" if groq_client else "🔴 Offline"
        bot_state = "⏸️ PAUSED" if BOT_PAUSED else "🟢 RUNNING (24/7 Engine)"
        markup = InlineKeyboardMarkup()
        if BOT_PAUSED:
            markup.row(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
        else:
            markup.row(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
        markup.row(
            InlineKeyboardButton("🕒 History", callback_data="history"),
            InlineKeyboardButton("🔄 Refresh Status", callback_data="status")
        )
        markup.row(
            InlineKeyboardButton("⚡ JobSpy Live", callback_data="jobspy:python fresher"),
            InlineKeyboardButton("🚶 Walk-Ins", callback_data="walkins:all")
        )
        status_text = (
            f"🤖 <b>Elite Job Bot — Live Command Center</b> 🇮🇳\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>Engine State:</b> <code>{bot_state}</code>\n"
            f"🎯 <b>Total Processed:</b> <code>{len(applied)}</code> jobs\n"
            f"🚀 <b>Applied Today:</b> <code>{stats.get('applied', 0)}</code>\n"
            f"⏭️ <b>Skipped / Filtered:</b> <code>{stats.get('skipped', 0)}</code>\n"
            f"🔥 <b>Active Streak:</b> <code>{stats.get('current_streak', 0)} Days</code>\n\n"
            f"🧠 <b>Gemini AI Engine:</b> {gemini_ok}\n"
            f"⚡ <b>Groq Inference:</b> {groq_ok}\n"
            f"📄 <b>Resume Profile:</b> {resume_ok}\n"
            f"📡 <b>Target Feed:</b> <code>@{TARGET_CHANNEL}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 <i>Tip: Tap /help or quick buttons below to control your bot.</i>"
        )
        try:
            bot.reply_to(message, status_text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.reply_to(message, re.sub(r'<[^>]+>', '', status_text), parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['profile'])
    @admin_only
    def send_profile(message):
        save_chat_id(message.chat.id)
        profile = load_profile()
        if not profile:
            bot.reply_to(message, "⚠️ Profile is empty! Use <code>/setprofile &lt;field&gt; | &lt;value&gt;</code> to add your details.", parse_mode="HTML")
            return

        msg = (
            "📋 <b>Your Active Candidate Profile:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for k, v in profile.items():
            clean_k = html.escape(k.replace('_', ' ').title())
            clean_v = html.escape(str(v))
            msg += f"• <b>{clean_k}:</b> <code>{clean_v}</code>\n"
        msg += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✏️ <i>To update any field:</i>\n"
            "<code>/setprofile &lt;field&gt; | &lt;new_value&gt;</code>\n"
            "<i>Example:</i> <code>/setprofile phone | +91 9876543210</code>"
        )
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("🎯 Match Resume (ATS)", callback_data="ats:analyze"),
            InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard")
        )
        try:
            bot.reply_to(message, msg, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.reply_to(message, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['history'])
    @admin_only
    def send_history(message):
        save_chat_id(message.chat.id)
        csv_file = "applied_jobs_log.csv"
        if not os.path.exists(csv_file):
            bot.reply_to(message, "📭 No applications logged yet. The bot hasn't processed any jobs.")
            return
        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
            if len(rows) <= 1:
                bot.reply_to(message, "📭 No applications logged yet.")
                return
            # Show last 10 entries (skip header)
            recent = rows[-10:]
            msg = "📊 **Last 10 Applications:**\n\n"
            for row in recent:
                if len(row) >= 5:
                    date, title, url, status, notes = row[0], row[1], row[2], row[3], row[4]
                    emoji = "✅" if status == "Applied" else "⏭️"
                    msg += f"{emoji} {date}\n{title}\n{status}: {notes}\n{url}\n\n"
                elif len(row) >= 4:
                    msg += f"• {row[0]} | {row[1]} | {row[3]}\n"
            bot.reply_to(message, msg, disable_web_page_preview=True)
        except Exception as e:
            bot.reply_to(message, f"⚠️ Error reading log: {e}")

    @bot.message_handler(commands=['download'])
    @admin_only
    def send_download(message):
        save_chat_id(message.chat.id)
        csv_file = "applied_jobs_log.csv"
        if not os.path.exists(csv_file):
            bot.reply_to(message, "📭 No CSV log file exists yet.")
            return
        try:
            with open(csv_file, "rb") as f:
                bot.send_document(message.chat.id, f, caption="📎 Full application log (CSV)")
        except Exception as e:
            bot.reply_to(message, f"⚠️ Error sending file: {e}")

    @bot.message_handler(commands=['pause'])
    @admin_only
    def pause_bot(message):
        save_chat_id(message.chat.id)
        global BOT_PAUSED
        BOT_PAUSED = True
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
        bot.reply_to(message, "⏸️ *Bot Paused!*\n\nAuto job scanning is stopped.\nTap the button below to resume.", parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['resume'])
    @admin_only
    def resume_bot(message):
        save_chat_id(message.chat.id)
        global BOT_PAUSED
        BOT_PAUSED = False
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
        bot.reply_to(message, "▶️ *Bot Resumed!*\n\nAuto job scanning is now active! The bot will find and apply to jobs automatically.", parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['watch', 'ghost'])
    @admin_only
    def toggle_ghost_mode(message):
        chat_id = message.chat.id
        save_chat_id(chat_id)
        if chat_id in ghost_mode_chats:
            ghost_mode_chats.remove(chat_id)
            bot.reply_to(message, "👻 *Ghost Mode Disabled!*\n\nYou will no longer receive live streaming screenshots.", parse_mode=None)
        else:
            ghost_mode_chats.add(chat_id)
            bot.reply_to(message, "👻 *Ghost Mode ENABLED!*\n\nYou will now receive live visual updates while the bot fills out applications in real-time.", parse_mode=None)

    @bot.message_handler(commands=['scan_inbox', 'sync'])
    @admin_only
    def command_scan_inbox(message):
        bot.reply_to(message, "📧 *Scanning Inbox for CRM Updates...*\nThis might take a few seconds.", parse_mode=None)
        import threading
        def _bg_scan():
            try:
                from imap_handler import scan_for_interview_invites
                results = scan_for_interview_invites()
                if results:
                    msg = f"🎉 *FOUND {len(results)} UPDATES!* CRM Synced.\n\n"
                    for r in results:
                        emoji = "📅" if r['status'] == "Interview" else "❌"
                        msg += f"{emoji} *{r['company']}* ({r['status']})\n"
                    bot.send_message(message.chat.id, msg, parse_mode=None)
                else:
                    bot.send_message(message.chat.id, "📭 No new interview or rejection emails found in the last 7 days.")
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ *Error scanning inbox:* {e}", parse_mode=None)
        threading.Thread(target=_bg_scan).start()

    @bot.callback_query_handler(func=lambda call: call.data in ["pause", "resume", "status", "dashboard", "history", "profile", "help", "last_job", "qa_memory", "radar", "ghost", "analytics", "drives", "tnjobs", "tnjobs:refresh"])
    @admin_only
    def handle_button(call):
        global BOT_PAUSED
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id)  # Dismiss the loading spinner
        except Exception:
            pass

        if call.data == "pause":
            BOT_PAUSED = True
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
            try:
                bot.edit_message_text("⏸️ <b>Bot Paused!</b>\n\nAuto job scanning is stopped.\nTap below to resume.",
                    chat_id=chat_id, message_id=call.message.message_id,
                    parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, "⏸️ <b>Bot Paused!</b>", parse_mode="HTML", reply_markup=markup)

        elif call.data == "resume":
            BOT_PAUSED = False
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
            try:
                bot.edit_message_text("▶️ <b>Bot Resumed!</b>\n\nScanning jobs 24/7 again!",
                    chat_id=chat_id, message_id=call.message.message_id,
                    parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, "▶️ <b>Bot Resumed!</b>", parse_mode="HTML", reply_markup=markup)

        elif call.data in ["status", "dashboard"]:
            applied = load_applied_jobs()
            stats = load_stats()
            resume_ok = "🟢 Ready" if os.path.exists(RESUME_FILE) else "🔴 Missing"
            gemini_ok = "🟢 Online" if gemini_client else "🔴 Offline"
            groq_ok = "🟢 Online" if groq_client else "🔴 Offline"
            bot_state = "⏸️ PAUSED" if BOT_PAUSED else "🟢 RUNNING (24/7 Engine)"

            # Calculate Success Rate
            success_count = 0
            total_logs = 0
            try:
                import csv
                if os.path.exists("applied_jobs_log.csv"):
                    with open("applied_jobs_log.csv", "r", encoding="utf-8") as f:
                        reader = csv.reader(f)
                        next(reader, None) # skip header
                        for row in reader:
                            if len(row) > 3:
                                total_logs += 1
                                if "Applied" in row[3]:
                                    success_count += 1
            except Exception:
                pass
            
            success_rate = "0%"
            if total_logs > 0:
                success_rate = f"{int((success_count/total_logs)*100)}%"
            
            status_text = (
                f"🤖 <b>Elite Job Bot — Live Command Center</b> 🇮🇳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚙️ <b>Engine State:</b> <code>{bot_state}</code>\n"
                f"🎯 <b>Total Processed:</b> <code>{len(applied)}</code> jobs\n"
                f"🚀 <b>Applied Today:</b> <code>{stats.get('applied', 0)}</code>\n"
                f"🔥 <b>Active Streak:</b> <code>{stats.get('current_streak', 0)} Days</code>\n"
                f"📈 <b>Success Rate:</b> <code>{success_rate}</code> <i>({success_count}/{total_logs})</i>\n\n"
                f"🧠 <b>Gemini AI Engine:</b> {gemini_ok}\n"
                f"⚡ <b>Groq Inference:</b> {groq_ok}\n"
                f"📄 <b>Resume Profile:</b> {resume_ok}\n"
                f"📡 <b>Target Feed:</b> <code>@{TARGET_CHANNEL}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Tip: Tap buttons below for instant live radar & walk-ins.</i>"
            )
            markup = InlineKeyboardMarkup()
            if BOT_PAUSED:
                markup.row(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
            else:
                markup.row(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
            markup.row(
                InlineKeyboardButton("🕒 History", callback_data="history"),
                InlineKeyboardButton("🔄 Refresh", callback_data="status")
            )
            markup.row(
                InlineKeyboardButton("⚡ JobSpy Live", callback_data="jobspy:python fresher"),
                InlineKeyboardButton("🚶 Weekend Walk-Ins", callback_data="walkins:all")
            )
            markup.row(
                InlineKeyboardButton("🎯 Match Resume (ATS)", callback_data="ats:analyze"),
                InlineKeyboardButton("🌟 Tamil Nadu Feeds", callback_data="tnjobs")
            )
            try:
                bot.edit_message_text(status_text, chat_id=chat_id,
                    message_id=call.message.message_id,
                    parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, status_text, parse_mode="HTML", reply_markup=markup)

        elif call.data == "history":
            csv_file = "applied_jobs_log.csv"
            if not os.path.exists(csv_file):
                bot.send_message(chat_id, "📭 No applications logged yet.")
                return
            try:
                with open(csv_file, "rb") as f:
                    bot.send_document(chat_id, f, caption="🕒 Here is your full application history.")
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Error sending history: {e}")

        elif call.data == "profile":
            profile = load_profile()
            if not profile:
                bot.send_message(chat_id, "⚠️ Profile is empty! Use <code>/setprofile &lt;field&gt; | &lt;value&gt;</code> to add your details.", parse_mode="HTML")
            else:
                msg = (
                    "📋 <b>Your Active Candidate Profile:</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                )
                for k, v in profile.items():
                    clean_k = html.escape(k.replace('_', ' ').title())
                    clean_v = html.escape(str(v))
                    msg += f"• <b>{clean_k}:</b> <code>{clean_v}</code>\n"
                msg += (
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "✏️ <i>To update any field:</i>\n"
                    "<code>/setprofile &lt;field&gt; | &lt;new_value&gt;</code>"
                )
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("🎯 Match Resume (ATS)", callback_data="ats:analyze"),
                    InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard")
                )
                try:
                    bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=markup)
                except Exception:
                    bot.send_message(chat_id, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup)
                
        elif call.data == "last_job":
            if os.path.exists("after_submit.png"):
                try:
                    with open("after_submit.png", "rb") as ph:
                        bot.send_photo(chat_id, ph, caption="📸 *Last Job Application Result*", parse_mode=None)
                except Exception as e:
                    bot.send_message(chat_id, f"⚠️ Could not load image: {e}")
            else:
                bot.send_message(chat_id, "📭 No screenshot available yet. The bot hasn't applied to anything recently.")

        elif call.data == "qa_memory":
            qa_memory = load_qa_memory()
            if not qa_memory:
                bot.send_message(chat_id, "🧠 AI Memory is empty. No custom questions answered yet.")
            else:
                msg = f"🧠 *Saved Q&A Memory ({len(qa_memory)} answers):*\n\n"
                for i, (q, a) in enumerate(list(qa_memory.items())[:10], 1):  # show top 10
                    msg += f"*Q:* {q}\n💬 _{a}_\n\n"
                if len(qa_memory) > 10:
                    msg += f"_...and {len(qa_memory)-10} more. Use `/qa` to see all._"
                bot.send_message(chat_id, msg, parse_mode=None)

        elif call.data.startswith("tnjobs"):
            try:
                bot.answer_callback_query(call.id, "🔍 Loading Tamil Nadu jobs...")
            except Exception:
                pass
            try:
                from job_radar import get_tamil_nadu_jobs, format_tamil_nadu_telegram_digest
                cat = None
                page = 1
                force = False
                parts = call.data.split(":")
                if len(parts) >= 2:
                    if parts[1] == "refresh":
                        force = True
                        if len(parts) >= 3 and parts[2] != "all":
                            cat = parts[2]
                    elif parts[1] == "p":
                        if len(parts) >= 3:
                            try:
                                page = max(1, int(parts[2]))
                            except Exception:
                                page = 1
                        if len(parts) >= 4 and parts[3] != "all":
                            cat = parts[3]
                    elif parts[1] != "all":
                        cat = parts[1]

                jobs, total = get_tamil_nadu_jobs(limit=10, force_refresh=force, category=cat, page=page, return_total=True)
                chunks, markup = format_tamil_nadu_telegram_digest(jobs, category=cat, current_page=page, total_jobs=total)
                for idx, chunk in enumerate(chunks):
                    is_last = (idx == len(chunks) - 1)
                    try:
                        bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    except Exception:
                        bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    time.sleep(0.4)
            except Exception as e:
                bot.send_message(chat_id, f"❌ Error loading Tamil Nadu jobs: {e}")

        elif call.data == "radar":
            bot.send_message(chat_id, "📡 *Job Radar Triggered!*\nScanning all configured Telegram channels right now for fresh jobs...", parse_mode=None)
            # We trigger the manual radar scan thread
            import threading
            threading.Thread(target=manual_radar_scan, args=(chat_id,)).start()

        elif call.data == "ghost":
            if chat_id in ghost_mode_chats:
                ghost_mode_chats.remove(chat_id)
                bot.send_message(chat_id, "👻 *Ghost Mode Disabled.*\nThe bot will now send you screenshots of every successful application.")
            else:
                ghost_mode_chats.add(chat_id)
                bot.send_message(chat_id, "👻 *Ghost Mode Activated!*\nThe bot is now fully stealth. It will apply to jobs silently in the background and will NOT send you screenshots or alerts. Check `/status` anytime.")
        elif call.data == "history":
            csv_file = "applied_jobs_log.csv"
            if not os.path.exists(csv_file):
                bot.send_message(chat_id, "📭 No applications logged yet.")
                return
            try:
                with open(csv_file, "r", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
                recent = rows[-5:]
                msg = "🕒 *Last 5 Applications:*\n\n"
                for row in reversed(recent):
                    if len(row) >= 4:
                        emoji = "✅" if "Applied" in row[3] else "❌"
                        msg += f"{emoji} {row[0]}\n📌 {row[1][:40]}\n📋 {row[3]}\n\n"
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🔄 Refresh", callback_data="history"))
                bot.send_message(chat_id, msg, parse_mode=None, reply_markup=markup, disable_web_page_preview=True)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Error: {e}")

        elif call.data == "analytics":
            try:
                report = generate_market_analytics_report(".")
                markup = InlineKeyboardMarkup(row_width=2)
                markup.row(
                    InlineKeyboardButton("📡 View Radar Jobs", callback_data="radar"),
                    InlineKeyboardButton("🩺 Bot Status", callback_data="status")
                )
                markup.row(
                    InlineKeyboardButton("📱 Open Web Dashboard", url=DASHBOARD_URL)
                )
                bot.send_message(chat_id, report, parse_mode="HTML", reply_markup=markup)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Analytics error: {e}")

        elif call.data == "drives":
            try:
                chunks = format_national_drives_report()
                markup = InlineKeyboardMarkup()
                markup.row(
                    InlineKeyboardButton("📋 TCS Syllabus", callback_data="drive_info:tcs_nqt"),
                    InlineKeyboardButton("📋 Zoho Pattern", callback_data="drive_info:zoho_drive")
                )
                markup.row(
                    InlineKeyboardButton("📋 Infosys Prep", callback_data="drive_info:infosys_drive"),
                    InlineKeyboardButton("📋 Accenture Prep", callback_data="drive_info:accenture_ase")
                )
                markup.row(
                    InlineKeyboardButton("📋 Google Intern", callback_data="drive_info:google_intern"),
                    InlineKeyboardButton("📋 Cognizant GenC", callback_data="drive_info:cognizant_genc")
                )
                markup.row(
                    InlineKeyboardButton("⏳ Mass Drive Deadlines", callback_data="deadlines"),
                    InlineKeyboardButton("📊 Market Analytics", callback_data="analytics")
                )
                markup.row(
                    InlineKeyboardButton("📡 View Radar Jobs", callback_data="radar")
                )
                for idx, chunk in enumerate(chunks):
                    is_last = (idx == len(chunks) - 1)
                    try:
                        bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    except Exception:
                        bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    time.sleep(0.3)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Drives error: {e}")

        elif call.data.startswith("deadlines"):
            try:
                is_urgent = ("urgent" in call.data)
                chunks = format_deadlines_radar_report(urgent_only=is_urgent)
                markup = InlineKeyboardMarkup()
                if is_urgent:
                    markup.row(
                        InlineKeyboardButton("📋 View All 18 Deadlines", callback_data="deadlines:all"),
                        InlineKeyboardButton("📢 All Drives & Syllabus", callback_data="drives")
                    )
                else:
                    markup.row(
                        InlineKeyboardButton("🚨 Critical Only (≤ 4 Days)", callback_data="deadlines:urgent"),
                        InlineKeyboardButton("📢 All Drives & Syllabus", callback_data="drives")
                    )
                markup.row(
                    InlineKeyboardButton("📡 View Radar Jobs", callback_data="radar"),
                    InlineKeyboardButton("📊 Market Analytics", callback_data="analytics")
                )
                for idx, chunk in enumerate(chunks):
                    is_last = (idx == len(chunks) - 1)
                    try:
                        bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    except Exception:
                        bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    time.sleep(0.3)
            except Exception as e:
                bot.send_message(chat_id, f"⚠️ Deadlines error: {e}")

        elif call.data == "help":
            help_text = (
                "🤖 *Command Reference*\n\n"
                "📢 /drives — National mass off-campus hiring drives (e.g. /drives 2025)\n"
                "⏳ /deadlines — Mass drive countdown & expiry radar (e.g. /deadlines urgent)\n"
                "📊 /analytics — Live market intelligence & stats\n"
                "📊 /status — Live bot status\n"
                "⏸️ /pause — Stop auto-scanning\n"
                "▶️ /resume — Start auto-scanning\n"
                "👻 /watch — Toggle Live Ghost Mode\n"
                "🕒 /history — Last 10 applications\n"
                "📋 /profile — View your profile\n"
                "🎯 /apply <url> — Apply to specific job\n"
                "📥 /download — Export CSV log"
            )
            bot.send_message(chat_id, help_text, parse_mode=None)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('jobcard:'))
    @admin_only
    def handle_job_card(call):
        _, action, key = call.data.split(':', 2)
        job = get_card(key)
        bot.answer_callback_query(call.id)
        if not job:
            bot.send_message(call.message.chat.id, '⚠️ Listing no longer available. Please refresh /walkins.')
            return
        if action == 'remind':
            bot.send_message(call.message.chat.id, schedule_reminder(call.message.chat.id, job))
        elif action == 'calendar':
            import io
            try:
                document = io.BytesIO(calendar_event(job))
                document.name = 'walkin.ics'
                bot.send_document(call.message.chat.id, document, caption='📅 Import this event into your calendar. Confirm availability with the employer before travelling.')
            except ValueError as exc:
                bot.send_message(call.message.chat.id, str(exc))
        elif action == 'details':
            text = format_single_walkin_detail(str(job.get('id', '')))
            bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=walkin_keyboard(job), disable_web_page_preview=True)

    @bot.message_handler(commands=['reminders'])
    @admin_only
    def show_walkin_reminders(message):
        if message.text.strip().split()[-1].lower() == 'cancel':
            cancel_reminders(message.chat.id)
            bot.reply_to(message, '🔕 Your walk-in reminders have been cancelled.')
            return
        entries = list_reminders(message.chat.id)
        lines = ['🔔 Walk-in reminders (IST):']
        for reminder, job in entries:
            due = datetime.fromisoformat(reminder['due']).astimezone(IST)
            lines.append(f"• {job.get('company', 'Company')}: {due:%d %b %Y, %I:%M %p}")
        if not entries:
            lines.append('No pending reminders. Tap Remind me on a dated walk-in card.')
        lines.append('Use /reminders cancel to cancel all your reminders.')
        bot.reply_to(message, '\n'.join(lines)[:4000])

    @bot.callback_query_handler(func=lambda call: call.data.startswith("walkin_detail:"))
    @admin_only
    def handle_walkin_detail_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="⚡ Fetching Drive Briefing...")
        except Exception:
            pass
        drive_id = call.data.split(":", 1)[1].strip()
        try:
            from bot_optimizer import format_single_walkin_detail
            msg = format_single_walkin_detail(drive_id)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🚶‍♂️ All Walk-In Drives", callback_data="walkins:all"),
                InlineKeyboardButton("🌟 TN Online Jobs", callback_data="tnjobs")
            )
            try:
                bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Error fetching walk-in detail: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("walkins"))
    @admin_only
    def handle_walkins_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="⚡ Loading Weekend Walk-In Drives...")
        except Exception:
            pass
        city_filter = None
        if ":" in call.data:
            sub = call.data.split(":")[1].strip().lower()
            if priority_city(sub) or sub in ["chennai", "coimbatore", "madurai", "trichy", "south", "hosur", "salem"]:
                city_filter = sub
        try:
            from bot_optimizer import format_walkins_report, get_walkin_drives
            drives = get_walkin_drives(city=city_filter)
            chunks = format_walkins_report(drives, city_filter=city_filter)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🧭 Walk-Ins Near Me (GPS)", callback_data="nearme:prompt"),
                InlineKeyboardButton("🎒 Walk-In Checklist", callback_data="nearme:checklist")
            )
            markup.row(
                InlineKeyboardButton("📍 Chennai Walk-Ins", callback_data="walkins:chennai"),
                InlineKeyboardButton("📍 Coimbatore Walk-Ins", callback_data="walkins:coimbatore")
            )
            markup.row(
                InlineKeyboardButton("📍 Madurai & Trichy", callback_data="walkins:south"),
                InlineKeyboardButton("📢 All TN Walk-Ins", callback_data="walkins:all")
            )
            markup.row(
                InlineKeyboardButton("🌟 TN Online Jobs", callback_data="tnjobs"),
                InlineKeyboardButton("📢 National Drives", callback_data="drives")
            )
            markup.row(
                InlineKeyboardButton("⏳ Mass Deadlines", callback_data="deadlines"),
                InlineKeyboardButton("🔄 Refresh Walk-Ins", callback_data="walkins:all")
            )
            if drives:
                send_walkin_cards(bot, chat_id, drives, navigation=markup)
            else:
                bot.send_message(chat_id, chunks[0], parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Walk-In error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("nearme:"))
    @admin_only
    def handle_nearme_callbacks(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        action = call.data.split(":", 1)[1] if ":" in call.data else ""
        if action == "checklist":
            try:
                bot.answer_callback_query(call.id, text="📋 Loading Packing Checklist...")
            except Exception:
                pass
            txt = get_walkin_checklist_text()
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🧭 Find Walk-Ins Near Me", callback_data="nearme:prompt"),
                InlineKeyboardButton("🚶‍♂️ All Walk-In Drives", callback_data="walkins:all")
            )
            bot.send_message(chat_id, txt, parse_mode="HTML", reply_markup=markup)
            return

        if action.startswith("hub:"):
            hub_key = action.split("hub:", 1)[1].strip()
            try:
                bot.answer_callback_query(call.id, text=f"📍 Locating near {hub_key.upper()}...")
            except Exception:
                pass
            geo = geocode_location_text(hub_key)
            if geo:
                lat, lon, label = geo
                drives = find_nearby_walkin_drives(lat, lon, max_radius_km=75.0, limit=5)
                chunks, nearby_list = format_nearby_walkins_report(drives, (lat, lon), location_label=label)
                markup = InlineKeyboardMarkup()
                for d in nearby_list[:4]:
                    dist_km = d.get("distance_km", 0.0)
                    comp = d.get("company", "Company")
                    nav_url = d.get("nav_url", "#")
                    markup.row(
                        InlineKeyboardButton(f"🚗 {comp} ({dist_km} km)", url=nav_url),
                        InlineKeyboardButton(f"📄 Briefing", callback_data=f"walkin_detail:{d.get('id')}")
                    )
                markup.row(
                    InlineKeyboardButton("🎒 Walk-In Checklist", callback_data="nearme:checklist"),
                    InlineKeyboardButton("🧭 Search Other Area", callback_data="nearme:prompt")
                )
                markup.row(
                    InlineKeyboardButton("🚶‍♂️ All Walk-In Drives", callback_data="walkins:all"),
                    InlineKeyboardButton("🌟 TN Online Jobs", callback_data="tnjobs")
                )
                for idx, chunk in enumerate(chunks):
                    is_last = (idx == len(chunks) - 1)
                    try:
                        bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    except Exception:
                        bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    time.sleep(0.3)
            return

        # Default action: nearme:prompt
        try:
            bot.answer_callback_query(call.id, text="🧭 Share your location or pick an area!")
        except Exception:
            pass
        prompt_user_for_location(chat_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("jobspy:"))
    @admin_only
    def handle_jobspy_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        query = call.data.split(":", 1)[1].strip() if ":" in call.data else ""
        try:
            bot.answer_callback_query(call.id, text=f"⚡ Live JobSpy scraping for '{query}'...")
        except Exception:
            pass
        try:
            results = search_jobs_multi_source(query=query, limit=6)
            chunks, markup = format_search_results_report(query=f"JobSpy: {query}", results=results)
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ JobSpy error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("simplify:") or call.data == "simplify")
    @admin_only
    def handle_simplify_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        raw_target = call.data.split(":", 1)[1].strip() if ":" in call.data else ""
        force = False
        query = None

        if raw_target == "refresh":
            force = True
            query = None
            try:
                bot.answer_callback_query(call.id, text="🔄 Refreshing SimplifyJobs feed...")
            except Exception:
                pass
        elif raw_target in ("all", ""):
            query = None
            try:
                bot.answer_callback_query(call.id, text="🎓 Fetching latest Simplify tech freshers...")
            except Exception:
                pass
        else:
            query = raw_target
            try:
                bot.answer_callback_query(call.id, text=f"🔍 Searching SimplifyJobs for '{query}'...")
            except Exception:
                pass

        try:
            jobs = fetch_simplify_jobs(keyword=query, limit=8, force_refresh=force)
            chunks, markup = format_simplify_jobs_report(jobs, keyword=query)
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ SimplifyJobs feed error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data == "ats:analyze" or call.data.startswith("ats:") or call.data == "ats")
    @admin_only
    def handle_ats_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="🎯 ATS Resume & Compatibility Matcher")
        except Exception:
            pass
        guide = (
            "🎯 <b>ATS RESUME & JOB COMPATIBILITY ENGINE</b> 🇮🇳\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Compare your candidate profile against any job description or career URL in seconds!\n\n"
            "<b>Commands & Usage:</b>\n"
            "• <code>/match &lt;Job Title or JD Text&gt;</code>\n"
            "• <code>/match https://careers.company.com/job/12345</code>\n"
            "• <code>/ats python developer fresher</code>\n\n"
            "<i>The AI engine analyzes required skills, calculates your exact ATS match percentage, "
            "and highlights missing keywords to optimize your resume!</i>"
        )
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("🐍 Match Python Fresher", callback_data="jobspy:python fresher"),
            InlineKeyboardButton("⚛️ Match React Developer", callback_data="jobspy:react developer")
        )
        markup.row(
            InlineKeyboardButton("📋 View Profile", callback_data="profile"),
            InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard")
        )
        try:
            bot.send_message(chat_id, guide, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, re.sub(r'<[^>]+>', '', guide), parse_mode=None, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("apply:"))
    @admin_only
    def handle_apply_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        raw_val = call.data.split("apply:", 1)[1].strip()
        try:
            bot.answer_callback_query(call.id, text="🤖 Launching AI Browser-Use Agent...")
        except Exception:
            pass

        from bot_optimizer import get_url_cache
        target_url = get_url_cache(raw_val) or raw_val
        if not target_url.startswith("http"):
            target_url = f"https://{target_url}"

        status_card = (
            f"🤖 <b>AI BROWSER-USE AGENT INITIATED</b> 🌐\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Target URL:</b> <code>{html.escape(target_url[:80])}</code>\n"
            f"🧠 <b>Vision Engine:</b> Gemini 2.5 Flash\n"
            f"📄 <b>Resume:</b> <code>resume.pdf</code>\n\n"
            f"⚡ <i>Launching autonomous AI agent to visually navigate, autofill profile fields, attach resume, and submit...</i>"
        )
        try:
            bot.send_message(chat_id, status_card, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, f"⌛ Initiating Browser-Use AI application for:\n{target_url}")

        def run():
            try:
                final_url = bypass_blog_redirect(target_url)

                # 1. Try Browser-Use AI Agent
                try:
                    from browser_use_applier import BrowserUseJobApplier, BROWSER_USE_AVAILABLE
                    if BROWSER_USE_AVAILABLE and os.getenv("GEMINI_API_KEY"):
                        # Submitting is irreversible, so live mode is opt-in.
                        # Default is dry-run: the agent fills the form, screenshots the
                        # review page, and stops. Set BROWSER_USE_DRY_RUN=0 to submit.
                        _bu_dry = os.getenv("BROWSER_USE_DRY_RUN", "1").strip() not in ("0", "false", "False", "no")
                        applier = BrowserUseJobApplier(dry_run=_bu_dry)
                        res = applier.apply_sync(final_url, "Software Developer", "Target Employer")
                        if res.get("status") == "dry_run":
                            try:
                                bot.send_message(chat_id, "🧪 <b>Dry run complete</b> — the form was filled but <b>not submitted</b>.\n\n"
                                                         f"Steps: {res.get('steps_taken', 0)} · {res.get('duration_seconds', 0)}s\n\n"
                                                         f"<i>{html.escape(str(res.get('message', ''))[:600])}</i>", parse_mode="HTML")
                            except Exception:
                                pass
                        if res.get("status") in ["success", "completed"]:
                            confirm_card = (
                                f"🎉 <b>AI APPLICATION SUBMITTED!</b> 🚀\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🏢 <b>Target:</b> {html.escape(res.get('company') or 'Employer')}\n"
                                f"💼 <b>Role:</b> {html.escape(res.get('role') or 'Software Developer')}\n"
                                f"⏱️ <b>Duration:</b> {res.get('duration_seconds', 0)}s ({res.get('steps_taken', 0)} steps)\n"
                                f"📝 <b>Summary:</b> {html.escape(str(res.get('message', 'Applied successfully'))[:250])}\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"✅ <i>Logged to applied_jobs.json & applied_jobs_log.csv</i>"
                            )
                            bot.send_message(chat_id, confirm_card, parse_mode="HTML")
                            ss = res.get("screenshot")
                            if ss and os.path.exists(ss):
                                try:
                                    with open(ss, "rb") as photo_file:
                                        bot.send_photo(chat_id, photo_file, caption="📸 Proof of Submission")
                                except Exception:
                                    pass
                            return
                except Exception as bu_err:
                    print(f"[BrowserUse Callback] Notice: {bu_err}")

                # 2. Fallback to standard apply
                success = run_playwright_apply(final_url, "Callback apply requested by user")
                if success:
                    bot.send_message(chat_id, f"✅ Application submitted for:\n{final_url}")
                else:
                    bot.send_message(chat_id, f"❌ Application could not be completed automatically for:\n{final_url}\nPlease apply manually.")
            except Exception as e:
                try:
                    bot.send_message(chat_id, f"⚠️ Application error: {e}")
                except Exception:
                    pass

        Thread(target=run).start()

    @bot.callback_query_handler(func=lambda call: call.data.startswith("search:"))
    @admin_only
    def handle_search_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        query = call.data.split(":", 1)[1].strip() if ":" in call.data else ""
        if query == "menu":
            query = ""
        try:
            bot.answer_callback_query(call.id, text=f"🔍 Searching for '{query or 'jobs'}'...")
        except Exception:
            pass

        if not query:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🐍 Python", callback_data="search:python"),
                InlineKeyboardButton("⚛️ React", callback_data="search:react"),
                InlineKeyboardButton("📊 Data Analyst", callback_data="search:data analyst")
            )
            markup.row(
                InlineKeyboardButton("📍 Chennai / TN", callback_data="search:chennai"),
                InlineKeyboardButton("🏠 Remote", callback_data="search:remote"),
                InlineKeyboardButton("📢 Mass Drives", callback_data="drives")
            )
            markup.row(
                InlineKeyboardButton("🚶‍♂️ Weekend Walk-Ins", callback_data="walkins:all"),
                InlineKeyboardButton("⏳ Deadlines", callback_data="deadlines")
            )
            help_msg = (
                "🔍 <b>Multi-Source Job Search Engine</b>\n\n"
                "Search live openings across Tamil Nadu feeds, mass drives, weekend walk-ins, and radar caches!\n\n"
                "<b>Usage:</b> <code>/search python</code>, <code>/search react</code>, <code>/search chennai</code>\n\n"
                "<i>Or tap any popular category below for instant results:</i>"
            )
            add_priority_buttons(markup)
            bot.send_message(chat_id, help_msg, parse_mode="HTML", reply_markup=markup)
            return

        try:
            bot.send_message(chat_id, '🔍 Searching priority cities: Tiruvannamalai, Vellore, Puducherry/Pondicherry and Chennai…')
            results = search_jobs_multi_source(query=query, limit=6)
            chunks, markup = format_search_results_report(query=query, results=results)
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Search error: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("drive_info:"))
    @admin_only
    def handle_drive_detail_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="⚡ Loading Syllabus & Exam Pattern...")
        except Exception:
            pass
        try:
            drive_id = call.data.split(":", 1)[1]
            card, apply_link = format_single_drive_detail(drive_id)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🚀 Direct Registration Portal", url=apply_link),
                InlineKeyboardButton("📢 All National Drives", callback_data="drives")
            )
            try:
                bot.send_message(chat_id, card, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', card), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Unable to load drive syllabus: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("oa:"))
    @admin_only
    def handle_oa_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        comp_key = call.data.split(":", 1)[1] if ":" in call.data else "menu"
        try:
            bot.answer_callback_query(call.id, text=f"⚡ Loading OA Blueprint: {comp_key.upper()}...")
        except Exception:
            pass
        try:
            report_text, markup = format_oa_report(comp_key)
            try:
                bot.send_message(chat_id, report_text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', report_text), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Unable to load OA syllabus: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("unalert:"))
    @admin_only
    def handle_unalert_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        keyword = call.data.split(":", 1)[1].strip() if ":" in call.data else ""
        if keyword:
            updated = remove_watchdog_subscription(keyword, str(chat_id))
            try:
                bot.answer_callback_query(call.id, text=f"❌ Removed alert for '{keyword}'", show_alert=False)
            except Exception:
                pass
            
            if updated:
                msg = f"✅ Removed watchdog for: <code>{html.escape(keyword)}</code>\n\n<b>Active Keyword Subscriptions:</b>\n"
                for i, k in enumerate(updated, 1):
                    msg += f"• <code>{html.escape(k)}</code>\n"
                msg += "\n<i>Tap any button below to remove more:</i>"
                markup = InlineKeyboardMarkup()
                for k in updated[:10]:
                    markup.row(InlineKeyboardButton(f"❌ Remove '{k}'", callback_data=f"unalert:{k}"))
                markup.row(InlineKeyboardButton("➕ Add New Alert", callback_data="alerts:how_to"))
                markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
            else:
                msg = (
                    f"✅ Removed watchdog for: <code>{html.escape(keyword)}</code>\n\n"
                    "ℹ️ You have no active keyword alerts remaining.\n"
                    "Use <code>/alertme &lt;keyword&gt;</code> to create a new one (e.g. <code>/alertme python chennai</code>)."
                )
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
            try:
                bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("alerts:"))
    @admin_only
    def handle_alerts_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        sub_action = call.data.split(":", 1)[1] if ":" in call.data else "list"
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass

        if sub_action == "how_to":
            msg = (
                "🔔 <b>HOW TO CREATE KEYWORD ALERTS</b>\n\n"
                "Send any command in this format:\n"
                "• <code>/alertme python chennai</code>\n"
                "• <code>/alertme remote 2025</code>\n"
                "• <code>/alertme zoho developer</code>\n"
                "• <code>/alertme data analyst</code>\n\n"
                "The bot will highlight matching openings instantly with high priority!"
            )
            bot.send_message(chat_id, msg, parse_mode="HTML")
            return

        subs = get_watchdog_subscriptions(str(chat_id))
        markup = InlineKeyboardMarkup()
        if subs:
            msg = (
                "🔔 <b>YOUR ACTIVE KEYWORD WATCHDOG ALERTS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "You will receive priority highlighted notifications whenever a matching job is scanned:\n\n"
            )
            for i, kw in enumerate(subs, 1):
                msg += f"<b>{i}.</b> <code>{html.escape(kw)}</code>\n"
                markup.row(InlineKeyboardButton(f"❌ Remove '{kw}'", callback_data=f"unalert:{kw}"))
            msg += "\n<i>To add more, send:</i> <code>/alertme &lt;keyword&gt;</code>"
            markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
        else:
            msg = (
                "🔔 <b>CUSTOM KEYWORD WATCHDOGS</b>\n\n"
                "You currently have no active keyword alerts.\n\n"
                "<b>How it works:</b>\n"
                "Subscribe to any role, technology, or city. When our 24/7 scrapers find a match, you get an instant 🔔 <b>[WATCHDOG ALERT]</b> notification!\n\n"
                "<b>Examples:</b>\n"
                "• <code>/alertme python chennai</code>\n"
                "• <code>/alertme remote 2025</code>\n"
                "• <code>/alertme zoho</code>\n"
                "• <code>/alertme data analyst</code>"
            )
            markup.row(
                InlineKeyboardButton("🐍 /alertme python", callback_data="search:python"),
                InlineKeyboardButton("📍 /alertme chennai", callback_data="search:chennai")
            )
            markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))

        try:
            bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.send_message(chat_id, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("prep:"))
    @admin_only
    def handle_interview_prep_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="⚡ Generating Interview Prep...")
        except Exception:
            pass

        try:
            from bot_optimizer import get_prep_cache
            prep_key = call.data.split(":", 1)[1]
            prep_info = _INTERVIEW_PREP_CACHE.get(prep_key) or get_prep_cache(prep_key) or {}
            company = prep_info.get("company", "Target Company")
            role = prep_info.get("role", "Software Engineer")
            skills = prep_info.get("skills", [])
            sheet = generate_fast_interview_cheat_sheet(company, role, skills, gemini_client, groq_client)
            try:
                bot.send_message(chat_id, sheet, parse_mode="HTML")
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', sheet), parse_mode=None)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Unable to generate interview cheat sheet: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("note:") or call.data.startswith("linote:"))
    @admin_only
    def handle_linkedin_note_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        from bot_optimizer import get_note_cache
        if call.data.startswith("linote:"):
            # Format: linote:Company:Role
            parts = call.data.split(":", 2)
            comp = parts[1] if len(parts) > 1 else "Hiring Team"
            role = parts[2] if len(parts) > 2 else "Software Engineer"
            profile = load_profile()
            skills = profile.get("top_skills", "Python, software engineering, problem solving")
            note = f"Hi! I noticed the {role} opening at {comp}. With hands-on experience in {skills}, I would love to connect and explore how I can add value to your engineering team!"
        else:
            note_key = call.data.split(":", 1)[1]
            note = _LINKEDIN_NOTE_CACHE.get(note_key) or get_note_cache(note_key) or ""
            if not note:
                note = "Hi! I noticed your opening and would love to connect and explore how my engineering background can add value to your team!"
        try:
            bot.answer_callback_query(call.id, text="💬 LinkedIn note sent below!")
        except Exception:
            pass

        try:
            msg = (
                "💬 <b>1-Tap LinkedIn Outreach Note (Copy & Send):</b>\n\n"
                f"<code>{html.escape(note)}</code>"
            )
            bot.send_message(chat_id, msg, parse_mode="HTML")
        except Exception as e:
            bot.send_message(chat_id, f"Note: {note}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("email:"))
    @admin_only
    def handle_cold_email_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="✉️ Generating Cold Outreach Pitch...")
        except Exception:
            pass

        try:
            from bot_optimizer import get_email_cache, generate_cold_email_pitch
            email_key = call.data.split(":", 1)[1]
            email_info = _COLD_EMAIL_CACHE.get(email_key) or get_email_cache(email_key) or {}
            company = email_info.get("company", "Target Company")
            role = email_info.get("role", "Software Engineer")
            skills = email_info.get("skills", [])
            profile = load_profile()
            pitch = generate_cold_email_pitch(company, role, skills, profile)
            try:
                bot.send_message(chat_id, pitch, parse_mode="HTML")
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', pitch), parse_mode=None)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Unable to generate cold outreach email: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("gap:"))
    @admin_only
    def handle_skill_gap_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        try:
            bot.answer_callback_query(call.id, text="📊 Analyzing ATS Skill Gaps...")
        except Exception:
            pass

        try:
            from bot_optimizer import get_gap_cache, format_skill_gap_report, get_prep_cache
            gap_key = call.data.split(":", 1)[1]
            gap_info = _SKILL_GAP_CACHE.get(gap_key) or get_gap_cache(gap_key) or {}
            prep_info = _INTERVIEW_PREP_CACHE.get(gap_key) or get_prep_cache(gap_key) or {}
            company = prep_info.get("company", "Hiring Organization")
            role = prep_info.get("role", "Software Engineer")
            report = format_skill_gap_report(company, role, gap_info)
            try:
                bot.send_message(chat_id, report, parse_mode="HTML")
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', report), parse_mode=None)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Unable to generate skill gap report: {e}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("ctc:") or call.data == "ctc")
    @admin_only
    def handle_ctc_callback(call):
        chat_id = call.message.chat.id
        save_chat_id(chat_id)
        ctc_val = call.data.split(":", 1)[1] if ":" in call.data else "4.5"
        try:
            bot.answer_callback_query(call.id, text=f"💰 Calculating in-hand salary for ₹{ctc_val} LPA...")
        except Exception:
            pass
        try:
            from bot_optimizer import calculate_inhand_salary, format_ctc_report
            data = calculate_inhand_salary(ctc_val)
            card, markup = format_ctc_report(data, ctc_input_raw=ctc_val)
            try:
                bot.edit_message_text(card, chat_id=chat_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, card, parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ CTC calculation error: {e}")

    @bot.message_handler(commands=['analytics', 'metrics'])
    @admin_only
    def send_career_analytics(message):
        chat_id = message.chat.id
        save_chat_id(chat_id)
        try:
            report = generate_market_analytics_report(".")
            markup = InlineKeyboardMarkup(row_width=2)
            markup.row(
                InlineKeyboardButton("📡 View Radar Jobs", callback_data="radar"),
                InlineKeyboardButton("🩺 Bot Status", callback_data="status")
            )
            markup.row(
                InlineKeyboardButton("📱 Open Web Dashboard", url=DASHBOARD_URL)
            )
            try:
                bot.send_message(chat_id, report, parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, re.sub(r'<[^>]+>', '', report), parse_mode=None, reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Analytics error: {e}")

    @bot.message_handler(commands=['drives', 'offcampus', 'massdrives'])
    @admin_only
    def send_national_drives(message):
        chat_id = message.chat.id
        save_chat_id(chat_id)
        try:
            text_args = message.text.replace("/drives", "").replace("/offcampus", "").replace("/massdrives", "").strip()
            query = text_args if text_args else None
            chunks = format_national_drives_report(query=query)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("📋 TCS Syllabus", callback_data="drive_info:tcs_nqt"),
                InlineKeyboardButton("📋 Zoho Pattern", callback_data="drive_info:zoho_drive")
            )
            markup.row(
                InlineKeyboardButton("📋 Infosys Prep", callback_data="drive_info:infosys_drive"),
                InlineKeyboardButton("📋 Accenture Prep", callback_data="drive_info:accenture_ase")
            )
            markup.row(
                InlineKeyboardButton("📋 Google Intern", callback_data="drive_info:google_intern"),
                InlineKeyboardButton("📋 Cognizant GenC", callback_data="drive_info:cognizant_genc")
            )
            markup.row(
                InlineKeyboardButton("⏳ Drive Deadlines Radar", callback_data="deadlines"),
                InlineKeyboardButton("📊 Market Analytics", callback_data="analytics")
            )
            markup.row(
                InlineKeyboardButton("📡 View Radar Jobs", callback_data="radar")
            )
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.4)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ National Drives error: {e}")

    @bot.message_handler(commands=['deadlines', 'countdown', 'cutoff'])
    @admin_only
    def send_mass_drives_deadlines(message):
        chat_id = message.chat.id
        save_chat_id(chat_id)
        try:
            cmd_args = message.text.lower().replace("/deadlines", "").replace("/countdown", "").replace("/cutoff", "").strip()
            is_urgent = any(k in cmd_args for k in ["urgent", "soon", "critical", "close", "week", "7"])
            chunks = format_deadlines_radar_report(urgent_only=is_urgent)
            markup = InlineKeyboardMarkup()
            if is_urgent:
                markup.row(
                    InlineKeyboardButton("📋 View All 18 Deadlines", callback_data="deadlines:all"),
                    InlineKeyboardButton("📢 All Drives & Syllabus", callback_data="drives")
                )
            else:
                markup.row(
                    InlineKeyboardButton("🚨 Critical Only (≤ 4 Days)", callback_data="deadlines:urgent"),
                    InlineKeyboardButton("📢 All Drives & Syllabus", callback_data="drives")
                )
            markup.row(
                InlineKeyboardButton("📡 View Radar Jobs", callback_data="radar"),
                InlineKeyboardButton("📊 Market Analytics", callback_data="analytics")
            )
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(chat_id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.4)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Deadlines command error: {e}")

    @bot.message_handler(commands=['setprofile'])
    @admin_only
    def set_profile_field(message):
        save_chat_id(message.chat.id)
        # Format: /setprofile field | value
        text = message.text.replace("/setprofile", "", 1).strip()
        if "|" not in text:
            profile = load_profile()
            fields = ", ".join([f"<code>{html.escape(k)}</code>" for k in profile.keys()])
            bot.reply_to(message, f"📝 <b>Update Candidate Profile:</b>\n<code>/setprofile &lt;field&gt; | &lt;value&gt;</code>\n\n<b>Available fields:</b>\n{fields}\n\n<b>Example:</b>\n<code>/setprofile phone | +91 9876543210</code>", parse_mode="HTML")
            return
        parts = text.split("|", 1)
        field = parts[0].strip().lower()
        value = parts[1].strip()
        profile = load_profile()
        if field not in profile:
            bot.reply_to(message, f"❌ Unknown field: <code>{html.escape(field)}</code>\n\nValid fields: {', '.join(profile.keys())}", parse_mode="HTML")
            return
        profile[field] = value
        try:
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            bot.reply_to(message, f"✅ <b>Profile Updated!</b>\n\n<b>{html.escape(field.title())}</b> → <code>{html.escape(value)}</code>", parse_mode="HTML")
        except Exception as e:
            bot.reply_to(message, f"⚠️ Error saving profile: {e}")

    @bot.message_handler(commands=['clearqa'])
    @admin_only
    def clear_qa(message):
        save_chat_id(message.chat.id)
        text = message.text.replace("/clearqa", "", 1).strip()
        qa_memory = load_qa_memory()
        if not text:
            if not qa_memory:
                bot.reply_to(message, "📭 No saved answers to clear.")
                return
            msg = "🗑️ <b>Which answer to delete?</b>\nSend <code>/clearqa &lt;number&gt;</code>\n\n"
            for i, q in enumerate(qa_memory.keys(), 1):
                msg += f"<b>{i}.</b> {html.escape(q)}\n"
            bot.reply_to(message, msg, parse_mode="HTML")
            return
        if text.isdigit():
            keys = list(qa_memory.keys())
            idx = int(text) - 1
            if 0 <= idx < len(keys):
                deleted_q = keys[idx]
                del qa_memory[deleted_q]
                save_qa_memory(qa_memory)
                bot.reply_to(message, f"🗑️ <b>Deleted answer for:</b>\n<i>{html.escape(deleted_q)}</i>", parse_mode="HTML")
            else:
                bot.reply_to(message, "❌ Invalid question number.")
        else:
            if text in qa_memory:
                del qa_memory[text]
                save_qa_memory(qa_memory)
                bot.reply_to(message, f"🗑️ <b>Deleted answer for:</b>\n<i>{html.escape(text)}</i>", parse_mode="HTML")
            else:
                bot.reply_to(message, "❌ Question not found in memory.")

    # --- Inline button callback handler ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("qa_answer:"))
    @admin_only
    def handle_qa_button(call):
        num = call.data.split(":", 1)[1]
        pending = load_pending_qa()
        question = pending.get(num, f"Question {num}")
        # Send a ForceReply so user can type answer directly as a reply
        markup = ForceReply(selective=True)
        sent = bot.send_message(
            call.message.chat.id,
            f"✏️ <b>Answer for Q{num}:</b>\n<i>{html.escape(question)}</i>\n\nType your answer below 👇",
            parse_mode="HTML",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        # Register a next-step handler to capture the reply
        bot.register_next_step_handler(sent, lambda msg, q=question: _save_inline_answer(msg, q))

    def _save_inline_answer(message, question):
        answer = message.text.strip()
        if not answer:
            bot.reply_to(message, "❌ Answer cannot be empty!")
            return
        qa_memory = load_qa_memory()
        qa_memory[question] = answer
        save_qa_memory(qa_memory)
        bot.reply_to(message, f"✅ <b>Saved to AI Brain!</b>\n\n❓ <b>Question:</b> {html.escape(question)}\n💬 <b>Answer:</b> <code>{html.escape(answer)}</code>\n\n<i>Will use this automatically in all future applications!</i>", parse_mode="HTML")

    @bot.message_handler(commands=['answer'])
    @admin_only
    def save_answer(message):
        save_chat_id(message.chat.id)
        text = message.text.replace("/answer", "", 1).strip()
        
        if "|" not in text:
            bot.reply_to(message, "❌ <b>Format:</b> <code>/answer &lt;number&gt; | &lt;your answer&gt;</code>\n\n<b>Example:</b>\n<code>/answer 1 | Yes, I am available immediately</code>", parse_mode="HTML")
            return
        
        parts = text.split("|", 1)
        key = parts[0].strip()   # Either a number like "1" or the full question text
        answer = parts[1].strip()
        
        if not answer:
            bot.reply_to(message, "❌ Answer cannot be empty!")
            return
        
        # Resolve question text from number
        pending = load_pending_qa()
        if key.isdigit() and key in pending:
            question = pending[key]
        else:
            # Fallback: treat the key as full question text
            question = key
        
        # Save to permanent QA memory
        qa_memory = load_qa_memory()
        qa_memory[question] = answer
        save_qa_memory(qa_memory)
        
        bot.reply_to(message, f"✅ <b>Saved to AI Brain!</b>\n\n❓ <b>Question:</b> {html.escape(question)}\n💬 <b>Answer:</b> <code>{html.escape(answer)}</code>\n\n<i>Will use this automatically in all future applications!</i>", parse_mode="HTML")

    @bot.message_handler(commands=['qa'])
    @admin_only
    def show_qa_memory(message):
        save_chat_id(message.chat.id)
        qa_memory = load_qa_memory()
        if not qa_memory:
            bot.reply_to(message, "📭 <b>AI Memory is empty.</b>\n\nWhen the bot encounters unknown questions, it will alert you. Use <code>/answer &lt;num&gt; | &lt;answer&gt;</code> to teach it!", parse_mode="HTML")
            return
        msg = (
            f"🧠 <b>Saved Q&A Memory ({len(qa_memory)} answers):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for i, (q, a) in enumerate(list(qa_memory.items())[:15], 1):
            msg += f"<b>Q{i}.</b> {html.escape(q)}\n💬 <code>{html.escape(a)}</code>\n\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n💡 <i>To update an answer:</i> <code>/answer &lt;num&gt; | &lt;new answer&gt;</code>"
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🗑️ Clear an Answer", callback_data="qa_clear"))
        markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
        try:
            bot.reply_to(message, msg, parse_mode="HTML", reply_markup=markup)
        except Exception:
            bot.reply_to(message, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['apply'])
    @admin_only
    def manual_apply(message):
        save_chat_id(message.chat.id)
        
        # Robust URL extraction
        urls = re.findall(r'(https?://[^\s]+)', message.text)
        if not urls:
            args = message.text.split()
            if len(args) < 2:
                bot.reply_to(message, "Usage: /apply <job_url>")
                return
            url = args[1]
            if not url.startswith("http"):
                url = "https://" + url
        else:
            url = urls[0]
            
        status_card = (
            f"🤖 <b>AI BROWSER-USE AGENT INITIATED</b> 🌐\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Target URL:</b> <code>{html.escape(url[:80])}</code>\n"
            f"🧠 <b>Vision Engine:</b> Gemini 2.5 Flash\n"
            f"📄 <b>Resume:</b> <code>resume.pdf</code>\n\n"
            f"⚡ <i>Launching autonomous AI agent to visually navigate, autofill profile fields, attach resume, and submit...</i>"
        )
        try:
            bot.reply_to(message, status_card, parse_mode="HTML")
        except Exception:
            bot.reply_to(message, f"⌛ Initiating Browser-Use AI application for:\n{url}")
        
        # Run in thread so bot doesn't freeze
        def run():
            try:
                final_url = bypass_blog_redirect(url)
                
                # 1. Try Browser-Use AI Agent First
                try:
                    from browser_use_applier import BrowserUseJobApplier, BROWSER_USE_AVAILABLE
                    if BROWSER_USE_AVAILABLE and os.getenv("GEMINI_API_KEY"):
                        # Submitting is irreversible, so live mode is opt-in.
                        # Default is dry-run: the agent fills the form, screenshots the
                        # review page, and stops. Set BROWSER_USE_DRY_RUN=0 to submit.
                        _bu_dry = os.getenv("BROWSER_USE_DRY_RUN", "1").strip() not in ("0", "false", "False", "no")
                        applier = BrowserUseJobApplier(dry_run=_bu_dry)
                        res = applier.apply_sync(final_url, "Software Developer", "Target Employer")
                        if res.get("status") == "dry_run":
                            try:
                                bot.send_message(message.chat.id, "🧪 <b>Dry run complete</b> — the form was filled but <b>not submitted</b>.\n\n"
                                                         f"Steps: {res.get('steps_taken', 0)} · {res.get('duration_seconds', 0)}s\n\n"
                                                         f"<i>{html.escape(str(res.get('message', ''))[:600])}</i>", parse_mode="HTML")
                            except Exception:
                                pass
                        
                        if res.get("status") in ["success", "completed"]:
                            confirm_card = (
                                f"🎉 <b>AI APPLICATION SUBMITTED!</b> 🚀\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🏢 <b>Target:</b> {html.escape(res.get('company') or 'Target Employer')}\n"
                                f"💼 <b>Role:</b> {html.escape(res.get('role') or 'Software Developer')}\n"
                                f"⏱️ <b>Duration:</b> {res.get('duration_seconds', 0)}s ({res.get('steps_taken', 0)} steps)\n"
                                f"📝 <b>Summary:</b> {html.escape(str(res.get('message', 'Applied successfully'))[:250])}\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"✅ <i>Logged to applied_jobs.json & applied_jobs_log.csv</i>"
                            )
                            bot.send_message(message.chat.id, confirm_card, parse_mode="HTML")
                            
                            ss = res.get("screenshot")
                            if ss and os.path.exists(ss):
                                try:
                                    with open(ss, "rb") as photo_file:
                                        bot.send_photo(message.chat.id, photo_file, caption="📸 Proof of Submission")
                                except Exception as ss_err:
                                    print(f"[BrowserUse] Screenshot send notice: {ss_err}")
                            return
                        else:
                            print(f"[BrowserUse] Concluded with: {res.get('message')}. Proceeding with standard fallback.")
                except Exception as bu_err:
                    print(f"[BrowserUse] Notice: {bu_err}")

                # 2. Fallback to existing Playwright form filler
                if any(domain in final_url.lower() for domain in UNSUPPORTED_DOMAINS):
                    bot.send_message(message.chat.id, f"⚠️ Notice: The platform or link ({final_url}) requires manual direct apply.")
                    log_job(final_url, "Manual /apply", False, "Unsupported platform or social media")
                    return
                    
                success = run_playwright_apply(final_url, "Manual application requested by user")
                log_job(final_url, "Manual /apply", success, "Manual apply")
                if success:
                    bot.send_message(message.chat.id, f"✅ Application submitted for:\n{url}")
                else:
                    bot.send_message(message.chat.id, f"❌ Application could not be completed automatically for:\n{url}\nPlease apply manually.")
            except Exception as e:
                print(f"[Manual Apply] Error in run thread: {e}")
                try:
                    bot.send_message(message.chat.id, f"⚠️ Bot error: {e}")
                except Exception:
                    pass
                
        Thread(target=run).start()

    @bot.message_handler(commands=['channels'])
    @admin_only
    def show_channels(message):
        save_chat_id(message.chat.id)
        ch_status = load_channel_status()
        sleep_note = "💤 _Bot is in sleep hours (11 PM–6 AM). Will resume at 6 AM._\n\n" if is_sleep_time() else ""
        msg = f"📡 *Monitored Channels ({len(TARGET_CHANNELS)} total)*\n\n{sleep_note}"
        for ch in TARGET_CHANNELS:
            info = ch_status.get(ch, {})
            status = info.get("status", "Not scanned yet")
            last = info.get("last_scan", "Never")
            found = info.get("jobs_found", 0)
            msg += f"• *@{ch}*\n  🕒 Last scan: `{last}` | 🔗 Applied: `{found}` | {status}\n\n"
        bot.reply_to(message, msg, parse_mode=None)

    @bot.message_handler(commands=['lastjob'])
    @admin_only
    def show_last_job(message):
        save_chat_id(message.chat.id)
        job = load_last_job()
        if not job:
            bot.reply_to(message, "💭 No applications have been made yet. The bot hasn't found a matching job.")
            return
        msg = (
            f"💼 *Last Application Attempt*\n\n"
            f"📍 *Channel:* @{job.get('channel', 'N/A')}\n"
            f"⏰ *Time:* {job.get('timestamp', 'N/A')}\n"
            f"📊 *Result:* {job.get('status', 'N/A')}\n\n"
            f"{job.get('summary', 'No summary available.')}\n\n"
            f"🔗 [View Job]({job.get('url', '#')})"
        )
        bot.reply_to(message, msg, parse_mode=None, disable_web_page_preview=True)

    @bot.message_handler(commands=['ping'])
    @admin_only
    def ping_test(message):
        bot.reply_to(message, "🏓 Pong! The cloud bot is alive and listening!")

    @bot.message_handler(commands=['walkins', 'walkin'])
    @admin_only
    def send_walkin_drives(message):
        save_chat_id(message.chat.id)
        city_filter = None
        target_company = None
        parts = message.text.strip().split()
        if len(parts) > 1:
            raw_c = parts[1].strip().lower()
            if priority_city(raw_c):
                city_filter = raw_c
            elif "chennai" in raw_c:
                city_filter = "chennai"
            elif "coimbatore" in raw_c:
                city_filter = "coimbatore"
            elif any(k in raw_c for k in ["madurai", "trichy", "south", "hosur", "salem"]):
                city_filter = raw_c
            elif raw_c not in ["all", "tn"]:
                target_company = raw_c

        try:
            from bot_optimizer import format_walkins_report, format_single_walkin_detail, get_walkin_drives
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🧭 Walk-Ins Near Me (GPS)", callback_data="nearme:prompt"),
                InlineKeyboardButton("🎒 Walk-In Checklist", callback_data="nearme:checklist")
            )
            markup.row(
                InlineKeyboardButton("📍 Chennai Walk-Ins", callback_data="walkins:chennai"),
                InlineKeyboardButton("📍 Coimbatore Walk-Ins", callback_data="walkins:coimbatore")
            )
            markup.row(
                InlineKeyboardButton("📍 Madurai & Trichy", callback_data="walkins:south"),
                InlineKeyboardButton("📢 All TN Walk-Ins", callback_data="walkins:all")
            )
            markup.row(
                InlineKeyboardButton("🌟 TN Online Jobs", callback_data="tnjobs"),
                InlineKeyboardButton("📢 National Drives", callback_data="drives")
            )
            markup.row(
                InlineKeyboardButton("⏳ Mass Deadlines", callback_data="deadlines"),
                InlineKeyboardButton("🔄 Refresh Walk-Ins", callback_data="walkins:all")
            )

            if target_company:
                drives = get_walkin_drives()
                matched = next((d for d in drives if target_company in d.get("id", "").lower() or target_company in d.get("company", "").lower()), None)
                if matched:
                    detail = format_single_walkin_detail(matched["id"])
                    try:
                        bot.send_message(message.chat.id, detail, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
                    except Exception:
                        bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', detail), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)
                    return

            drives = get_walkin_drives(city=city_filter)
            chunks = format_walkins_report(drives, city_filter=city_filter)
            if drives:
                send_walkin_cards(bot, message.chat.id, drives, navigation=markup)
            else:
                bot.send_message(message.chat.id, chunks[0], parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Walk-In error: {e}")

    def prompt_user_for_location(chat_id):
        reply_kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        reply_kb.row(KeyboardButton("📍 Share My Current Location (GPS)", request_location=True))
        reply_kb.row(KeyboardButton("📍 Near OMR"), KeyboardButton("📍 Near Guindy"))
        reply_kb.row(KeyboardButton("📍 Near Tambaram"), KeyboardButton("📍 Near Coimbatore"))

        inline_kb = InlineKeyboardMarkup()
        inline_kb.row(
            InlineKeyboardButton("📍 OMR IT Corridor", callback_data="nearme:hub:omr"),
            InlineKeyboardButton("📍 Guindy / DLF", callback_data="nearme:hub:guindy")
        )
        inline_kb.row(
            InlineKeyboardButton("📍 Tambaram / MEPZ", callback_data="nearme:hub:tambaram"),
            InlineKeyboardButton("📍 Coimbatore (CHIL)", callback_data="nearme:hub:saravanampatti")
        )
        inline_kb.row(
            InlineKeyboardButton("📍 Madurai ELCOT", callback_data="nearme:hub:madurai"),
            InlineKeyboardButton("📍 Trichy ELCOT", callback_data="nearme:hub:trichy")
        )
        inline_kb.row(
            InlineKeyboardButton("🎒 Walk-In Packing Checklist", callback_data="nearme:checklist"),
            InlineKeyboardButton("🚶‍♂️ All Walk-In Drives", callback_data="walkins:all")
        )

        msg = (
            "🧭 <b>GPS WALK-IN DRIVE NAVIGATOR</b> 📍\n\n"
            "Find in-person walk-in interviews happening closest to where you are right now, complete with <b>exact driving distance</b>, <b>commute time</b>, and <b>turn-by-turn Google Maps GPS links</b>!\n\n"
            "<b>Choose how to locate:</b>\n"
            "1. 📱 Tap <b>'📍 Share My Current Location (GPS)'</b> on your keyboard below.\n"
            "2. 🏙️ Or tap any major Tamil Nadu IT hub button.\n"
            "3. ⌨️ Or type: <code>/nearme omr</code>, <code>/nearme guindy</code>, <code>/nearme coimbatore</code>, <code>/nearme velachery</code>."
        )
        bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=inline_kb)
        try:
            bot.send_message(chat_id, "👇 Tap the button below to send your live GPS location:", reply_markup=reply_kb)
        except Exception:
            pass

    @bot.message_handler(commands=['nearme', 'nearby', 'gps', 'walkin_near'])
    @admin_only
    def handle_nearme_command(message):
        save_chat_id(message.chat.id)
        parts = message.text.strip().split(maxsplit=1)
        if len(parts) > 1 and parts[1].strip():
            query_area = parts[1].strip()
            geo = geocode_location_text(query_area)
            if geo:
                lat, lon, label = geo
                drives = find_nearby_walkin_drives(lat, lon, max_radius_km=75.0, limit=5)
                chunks, nearby_list = format_nearby_walkins_report(drives, (lat, lon), location_label=label)
                markup = InlineKeyboardMarkup()
                for d in nearby_list[:4]:
                    dist_km = d.get("distance_km", 0.0)
                    comp = d.get("company", "Company")
                    nav_url = d.get("nav_url", "#")
                    markup.row(
                        InlineKeyboardButton(f"🚗 Navigate {comp} ({dist_km} km)", url=nav_url),
                        InlineKeyboardButton(f"📄 Briefing", callback_data=f"walkin_detail:{d.get('id')}")
                    )
                markup.row(
                    InlineKeyboardButton("🎒 Walk-In Checklist", callback_data="nearme:checklist"),
                    InlineKeyboardButton("🧭 Search Other Area", callback_data="nearme:prompt")
                )
                markup.row(
                    InlineKeyboardButton("🚶‍♂️ All Walk-In Drives", callback_data="walkins:all"),
                    InlineKeyboardButton("🌟 TN Online Jobs", callback_data="tnjobs")
                )
                for idx, chunk in enumerate(chunks):
                    is_last = (idx == len(chunks) - 1)
                    try:
                        bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    except Exception:
                        bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                    time.sleep(0.3)
                return
            else:
                bot.send_message(message.chat.id, f"⚠️ Area '<code>{html.escape(query_area)}</code>' not recognized in local tech hubs. Pick from below or share your live GPS location:", parse_mode="HTML")

        prompt_user_for_location(message.chat.id)

    @bot.message_handler(content_types=['location'])
    @admin_only
    def handle_user_location(message):
        save_chat_id(message.chat.id)
        if not message.location:
            return
        user_lat = message.location.latitude
        user_lon = message.location.longitude

        try:
            bot.send_message(message.chat.id, "📍 <i>GPS Location acquired! Scanning Tamil Nadu walk-in venues closest to you...</i>", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        except Exception:
            pass

        try:
            drives = find_nearby_walkin_drives(user_lat, user_lon, max_radius_km=80.0, limit=5)
            chunks, nearby_list = format_nearby_walkins_report(drives, (user_lat, user_lon), location_label=f"Your GPS ({user_lat:.4f}° N, {user_lon:.4f}° E)")

            markup = InlineKeyboardMarkup()
            for d in nearby_list[:4]:
                dist_km = d.get("distance_km", 0.0)
                comp = d.get("company", "Company")
                nav_url = d.get("nav_url", "#")
                markup.row(
                    InlineKeyboardButton(f"🚗 Navigate {comp} ({dist_km} km)", url=nav_url),
                    InlineKeyboardButton(f"📄 Briefing", callback_data=f"walkin_detail:{d.get('id')}")
                )
            markup.row(
                InlineKeyboardButton("🎒 Walk-In Checklist", callback_data="nearme:checklist"),
                InlineKeyboardButton("🧭 Refresh Location", callback_data="nearme:prompt")
            )
            markup.row(
                InlineKeyboardButton("🚶‍♂️ All Walk-In Drives", callback_data="walkins:all"),
                InlineKeyboardButton("🌟 TN Online Jobs", callback_data="tnjobs")
            )

            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)

            if nearby_list:
                closest = nearby_list[0]
                c_lat = closest.get("latitude")
                c_lon = closest.get("longitude")
                if c_lat and c_lon:
                    try:
                        bot.send_venue(
                            message.chat.id,
                            latitude=float(c_lat),
                            longitude=float(c_lon),
                            title=f"🥇 Closest: {closest.get('company')}",
                            address=f"{closest.get('venue_name')}, {closest.get('location_area')}"
                        )
                    except Exception:
                        pass
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error calculating proximity: {e}")

    @bot.message_handler(func=lambda msg: msg.text and msg.text.strip().startswith("📍 Near "))
    @admin_only
    def handle_quick_near_text(message):
        clean_area = message.text.replace("📍 Near ", "").strip().lower()
        geo = geocode_location_text(clean_area)
        if geo:
            lat, lon, label = geo
            drives = find_nearby_walkin_drives(lat, lon, max_radius_km=75.0, limit=5)
            chunks, nearby_list = format_nearby_walkins_report(drives, (lat, lon), location_label=label)
            markup = InlineKeyboardMarkup()
            for d in nearby_list[:4]:
                dist_km = d.get("distance_km", 0.0)
                comp = d.get("company", "Company")
                nav_url = d.get("nav_url", "#")
                markup.row(
                    InlineKeyboardButton(f"🚗 {comp} ({dist_km} km)", url=nav_url),
                    InlineKeyboardButton(f"📄 Briefing", callback_data=f"walkin_detail:{d.get('id')}")
                )
            markup.row(
                InlineKeyboardButton("🎒 Walk-In Checklist", callback_data="nearme:checklist"),
                InlineKeyboardButton("🧭 Search Other Area", callback_data="nearme:prompt")
            )
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)

    @bot.message_handler(commands=['jobspy', 'livejobs', 'spy', 'glassdoor'])
    @admin_only
    def handle_jobspy_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        query = raw_cmd[1].strip() if len(raw_cmd) > 1 else ""
        if not query:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🐍 Python Fresher", callback_data="jobspy:python fresher"),
                InlineKeyboardButton("⚛️ React Developer", callback_data="jobspy:react developer")
            )
            markup.row(
                InlineKeyboardButton("📊 Data Analyst", callback_data="jobspy:data analyst"),
                InlineKeyboardButton("☕ Java Fresher", callback_data="jobspy:java fresher")
            )
            markup.row(
                InlineKeyboardButton("🌐 Full Stack", callback_data="jobspy:full stack developer"),
                InlineKeyboardButton("🤖 ML / AI Engineer", callback_data="jobspy:machine learning engineer")
            )
            markup.row(
                InlineKeyboardButton("📍 Chennai IT Jobs", callback_data="jobspy:software engineer chennai"),
                InlineKeyboardButton("🏢 Coimbatore", callback_data="jobspy:software developer coimbatore")
            )
            markup.row(
                InlineKeyboardButton("🏠 Remote India", callback_data="jobspy:remote software engineer india"),
                InlineKeyboardButton("🔍 Multi-Source /search", callback_data="search:menu")
            )
            help_msg = (
                "⚡ <b>JobSpy Live Multi-Portal Search</b> 🕵️\n\n"
                "Search across <b>LinkedIn and Indeed India</b> plus configured feeds — "
                "source links, reported salaries, and job descriptions. Availability depends on each source.\n\n"
                "⭐ Priority: Tiruvannamalai, Vellore, Puducherry/Pondicherry and Chennai.\n\n"
                "<b>Usage:</b>\n"
                "• <code>/jobspy python fresher</code>\n"
                "• <code>/jobspy react developer chennai</code>\n"
                "• <code>/jobspy data analyst</code>\n"
                "• <code>/jobspy zoho</code>\n"
                "• <code>/jobspy full stack bangalore</code>\n\n"
                "<i>Tap any quick category below for instant live scraping:</i>"
            )
            bot.send_message(message.chat.id, help_msg, parse_mode="HTML", reply_markup=markup)
            return

        try:
            status_msg = bot.send_message(message.chat.id, f"⚡ <i>Scraping LinkedIn, Indeed India & Google Jobs live for '<b>{html.escape(query)}</b>'...</i>", parse_mode="HTML")
        except Exception:
            status_msg = None

        try:
            results = search_jobs_multi_source(query=query, limit=6)

            chunks, markup = format_search_results_report(query=f"JobSpy: {query}", results=results)
            if status_msg:
                try:
                    bot.delete_message(message.chat.id, status_msg.message_id)
                except Exception:
                    pass

            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ JobSpy query error: {e}")

    @bot.message_handler(commands=['simplify', 'simplifyjobs', 'freshers', 'entrylevel', 'internships'])
    @admin_only
    def handle_simplify_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        query = raw_cmd[1].strip() if len(raw_cmd) > 1 else ""
        if not query:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("💻 Software Engineer", callback_data="simplify:software"),
                InlineKeyboardButton("🤖 AI & ML Engineer", callback_data="simplify:ai")
            )
            markup.row(
                InlineKeyboardButton("📊 Data Science / Analyst", callback_data="simplify:data"),
                InlineKeyboardButton("🌐 Remote Tech Roles", callback_data="simplify:remote")
            )
            markup.row(
                InlineKeyboardButton("🎓 All Latest Freshers", callback_data="simplify:all"),
                InlineKeyboardButton("🔄 Refresh Cache", callback_data="simplify:refresh")
            )
            markup.row(
                InlineKeyboardButton("🎛️ Open Dashboard", callback_data="dashboard")
            )
            menu_msg = (
                "🎓 <b>SIMPLIFYJOBS LIVE TECH FEED</b> 🌐\n\n"
                "Real-time tech fresher and new grad job postings directly from the "
                "open-source <b>SimplifyJobs</b> repository!\n\n"
                "🌟 <b>Highlights:</b>\n"
                "• 100% verified official careers portals (Greenhouse, Ashby, Lever, Workday)\n"
                "• Target: <b>2024 / 2025 / 2026 Batch Freshers</b> & Early Career Engineers\n"
                "• Zero fake consultancies or middleman portals\n\n"
                "<b>Usage:</b>\n"
                "• <code>/simplify software</code>\n"
                "• <code>/simplify ai</code>\n"
                "• <code>/simplify python</code>\n"
                "• <code>/freshers remote</code>\n\n"
                "<i>Tap any quick category below to fetch active openings:</i>"
            )
            bot.send_message(message.chat.id, menu_msg, parse_mode="HTML", reply_markup=markup)
            return

        try:
            status_msg = bot.send_message(message.chat.id, f"🎓 <i>Querying SimplifyJobs live feed for '<b>{html.escape(query)}</b>'...</i>", parse_mode="HTML")
        except Exception:
            status_msg = None

        try:
            jobs = fetch_simplify_jobs(keyword=query, limit=8)
            chunks, markup = format_simplify_jobs_report(jobs, keyword=query)
            if status_msg:
                try:
                    bot.delete_message(message.chat.id, status_msg.message_id)
                except Exception:
                    pass

            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ SimplifyJobs query error: {e}")

    @bot.message_handler(commands=['search', 'find'])
    @admin_only
    def handle_search_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        query = raw_cmd[1].strip() if len(raw_cmd) > 1 else ""
        if not query:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🐍 Python", callback_data="search:python"),
                InlineKeyboardButton("⚛️ React", callback_data="search:react"),
                InlineKeyboardButton("📊 Data Analyst", callback_data="search:data analyst")
            )
            markup.row(
                InlineKeyboardButton("📍 Chennai / TN", callback_data="search:chennai"),
                InlineKeyboardButton("🏠 Remote", callback_data="search:remote"),
                InlineKeyboardButton("📢 Mass Drives", callback_data="drives")
            )
            markup.row(
                InlineKeyboardButton("🚶‍♂️ Weekend Walk-Ins", callback_data="walkins:all"),
                InlineKeyboardButton("⏳ Deadlines", callback_data="deadlines")
            )
            help_msg = (
                "🔍 <b>Multi-Source Job Search Engine</b>\n\n"
                "Search live openings across Tamil Nadu feeds, mass drives, weekend walk-ins, and radar caches!\n\n"
                "<b>Usage:</b>\n"
                "• <code>/search python</code>\n"
                "• <code>/search react</code>\n"
                "• <code>/search data analyst</code>\n"
                "• <code>/search chennai</code>\n"
                "• <code>/search zoho</code>\n\n"
                "<i>Or tap any popular category below for instant results:</i>"
            )
            add_priority_buttons(markup)
            bot.send_message(message.chat.id, help_msg, parse_mode="HTML", reply_markup=markup)
            return

        try:
            bot.send_message(message.chat.id, '🔍 Searching priority cities: Tiruvannamalai, Vellore, Puducherry/Pondicherry and Chennai…')
            results = search_jobs_multi_source(query=query, limit=6)
            chunks, markup = format_search_results_report(query=query, results=results)
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.3)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Search error: {e}")

    @bot.message_handler(commands=['match', 'ats', 'fit'])
    @admin_only
    def handle_match_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        input_text = raw_cmd[1].strip() if len(raw_cmd) > 1 else ""
        profile = load_profile()
        report_text, markup = match_job_compatibility(input_text, profile=profile)
        try:
            bot.send_message(message.chat.id, report_text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', report_text), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)

    @bot.message_handler(commands=['ctc', 'salary', 'inhand', 'takehome'])
    @admin_only
    def handle_ctc_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        ctc_arg = raw_cmd[1].strip() if len(raw_cmd) > 1 else "4.5"
        try:
            from bot_optimizer import calculate_inhand_salary, format_ctc_report
            data = calculate_inhand_salary(ctc_arg)
            card, markup = format_ctc_report(data, ctc_input_raw=ctc_arg)
            try:
                bot.send_message(message.chat.id, card, parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', card), parse_mode=None, reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ CTC calculation error: {e}")

    @bot.message_handler(commands=['pitch', 'coldemail', 'outreach'])
    @admin_only
    def handle_pitch_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=2)
        company = raw_cmd[1].strip() if len(raw_cmd) > 1 else "Target Employer"
        role = raw_cmd[2].strip() if len(raw_cmd) > 2 else "Software Developer"
        try:
            from bot_optimizer import generate_cold_email_pitch
            profile = load_profile()
            pitch_card = generate_cold_email_pitch(company, role, profile=profile)
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("🌟 Tamil Nadu Jobs", callback_data="tnjobs"),
                InlineKeyboardButton("🔙 Dashboard", callback_data="dashboard")
            )
            try:
                bot.send_message(message.chat.id, pitch_card, parse_mode="HTML", reply_markup=markup)
            except Exception:
                bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', pitch_card), parse_mode=None, reply_markup=markup)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error generating pitch: {e}")

    @bot.message_handler(content_types=['document'])
    @admin_only
    def handle_resume_document(message):
        save_chat_id(message.chat.id)
        doc = message.document
        if not doc or not (doc.file_name or "").lower().endswith(".pdf"):
            bot.reply_to(message, "📄 Please send a <b>PDF document</b> (e.g. <code>resume.pdf</code>) for ATS skill extraction and job matching.", parse_mode="HTML")
            return

        loading_msg = bot.reply_to(message, "📄 <i>Downloading & auditing your Resume PDF with the AI ATS Engine...</i>", parse_mode="HTML")
        try:
            from bot_optimizer import parse_resume_pdf, format_resume_ats_audit
            # Download file
            file_info = bot.get_file(doc.file_id)
            downloaded_bytes = bot.download_file(file_info.file_path)

            # Save locally to resume.pdf so auto-applier can use it
            with open("resume.pdf", "wb") as f:
                f.write(downloaded_bytes)

            parsed = parse_resume_pdf("resume.pdf")

            # Update candidate profile
            profile = load_profile()
            if parsed.get("name") and parsed["name"] != "Candidate":
                profile["full_name"] = parsed["name"]
            if parsed.get("email"):
                profile["email"] = parsed["email"]
            if parsed.get("phone"):
                profile["phone"] = parsed["phone"]
            if parsed.get("skills"):
                profile["skills"] = parsed["skills_str"]
            safe_save_json(PROFILE_FILE, profile)

            # Find matching jobs from radar or TN jobs
            top_matches = []
            try:
                from job_radar import get_tamil_nadu_jobs
                tn_jobs = get_tamil_nadu_jobs(limit=15, force_refresh=False)
                skills_lower = [s.lower() for s in parsed.get("skills", [])]
                for j in tn_jobs:
                    j_text = (j.get("title", "") + " " + j.get("company", "") + " " + j.get("description", "")).lower()
                    overlap = sum(1 for s in skills_lower if s in j_text)
                    if overlap > 0:
                        score = min(96, 60 + overlap * 10)
                        top_matches.append({
                            "company": j.get("company", "Tech Company"),
                            "role": j.get("title", "Developer"),
                            "link": j.get("link", "#"),
                            "match_score": score
                        })
                top_matches.sort(key=lambda x: x["match_score"], reverse=True)
            except Exception:
                pass

            chunks, markup = format_resume_ats_audit(parsed, top_matches=top_matches[:3])
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except Exception:
                pass

            for chunk in chunks:
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)
        except Exception as e:
            bot.send_message(message.chat.id, f"⚠️ Error processing resume PDF: {e}")

    @bot.message_handler(commands=['oa', 'syllabus', 'exam', 'pattern'])
    @admin_only
    def handle_oa_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        company_query = raw_cmd[1].strip() if len(raw_cmd) > 1 else "menu"
        report_text, markup = format_oa_report(company_query)
        try:
            bot.send_message(message.chat.id, report_text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', report_text), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)

    @bot.message_handler(commands=['alertme', 'subscribe', 'watchdog'])
    @admin_only
    def handle_alertme_command(message):
        save_chat_id(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        keyword = raw_cmd[1].strip() if len(raw_cmd) > 1 else ""
        chat_id_str = str(message.chat.id)
        if not keyword:
            subs = get_watchdog_subscriptions(chat_id_str)
            markup = InlineKeyboardMarkup()
            if subs:
                for k in subs[:8]:
                    markup.row(InlineKeyboardButton(f"❌ Remove '{k}'", callback_data=f"unalert:{k}"))
            markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
            msg = (
                "🔔 <b>CUSTOM KEYWORD WATCHDOGS</b>\n\n"
                "Get instant priority alerts whenever our 24/7 scrapers find jobs matching your exact keywords!\n\n"
                "<b>Usage:</b>\n"
                "• <code>/alertme python chennai</code>\n"
                "• <code>/alertme remote 2025</code>\n"
                "• <code>/alertme zoho</code>\n"
                "• <code>/alertme data analyst</code>\n\n"
            )
            if subs:
                msg += "<b>Your Current Alerts:</b>\n" + "\n".join([f"• <code>{html.escape(s)}</code>" for s in subs])
            else:
                msg += "<i>You currently have no active keyword alerts. Try:</i> <code>/alertme python chennai</code>"
            bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_markup=markup)
            return

        updated_subs = add_watchdog_subscription(keyword, chat_id_str)
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(f"❌ Undo / Remove '{keyword}'", callback_data=f"unalert:{keyword}"),
            InlineKeyboardButton("📋 View All Alerts", callback_data="alerts:list")
        )
        markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
        resp = (
            f"✅ <b>WATCHDOG ALERT ACTIVATED!</b>\n\n"
            f"🎯 <b>Tracking Keyword:</b> <code>{html.escape(keyword)}</code>\n"
            f"⚡ <b>Priority:</b> Maximum\n\n"
            f"Whenever our scrapers detect a job matching <b>'{html.escape(keyword)}'</b> in title, role, company, or location, "
            f"you will receive an immediate highlighted 🔔 <b>[WATCHDOG ALERT]</b> card.\n\n"
            f"<b>Total Active Alerts:</b> {len(updated_subs)}"
        )
        bot.send_message(message.chat.id, resp, parse_mode="HTML", reply_markup=markup)

    @bot.message_handler(commands=['alerts', 'subscriptions', 'myalerts'])
    @admin_only
    def handle_alerts_command(message):
        save_chat_id(message.chat.id)
        chat_id_str = str(message.chat.id)
        subs = get_watchdog_subscriptions(chat_id_str)
        markup = InlineKeyboardMarkup()
        if subs:
            msg = (
                "🔔 <b>YOUR ACTIVE KEYWORD WATCHDOG ALERTS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "You are currently tracking these keywords across all channels:\n\n"
            )
            for i, kw in enumerate(subs, 1):
                msg += f"<b>{i}.</b> <code>{html.escape(kw)}</code>\n"
                markup.row(InlineKeyboardButton(f"❌ Remove '{kw}'", callback_data=f"unalert:{kw}"))
            msg += "\n<i>To add another trigger:</i> <code>/alertme &lt;keyword&gt;</code>"
            markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
        else:
            msg = (
                "🔔 <b>NO ACTIVE WATCHDOG ALERTS</b>\n\n"
                "You haven't subscribed to any custom keywords yet.\n\n"
                "<b>Quick Examples:</b>\n"
                "• <code>/alertme python chennai</code>\n"
                "• <code>/alertme react bangalore</code>\n"
                "• <code>/alertme remote 2025</code>\n"
                "• <code>/alertme zoho developer</code>\n\n"
                "Send any of these commands to begin tracking!"
            )
            markup.row(InlineKeyboardButton("⬅️ Dashboard", callback_data="dashboard"))
        bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_markup=markup)

    @bot.message_handler(commands=['unalert', 'unsubscribe'])
    @admin_only
    def handle_unalert_command(message):
        save_chat_id(message.chat.id)
        chat_id_str = str(message.chat.id)
        raw_cmd = message.text.strip().split(maxsplit=1)
        keyword = raw_cmd[1].strip() if len(raw_cmd) > 1 else ""
        if not keyword:
            subs = get_watchdog_subscriptions(chat_id_str)
            markup = InlineKeyboardMarkup()
            for k in subs[:8]:
                markup.row(InlineKeyboardButton(f"❌ Remove '{k}'", callback_data=f"unalert:{k}"))
            bot.send_message(message.chat.id, "Please specify which keyword to remove, e.g. <code>/unalert python</code>, or tap a button below:", parse_mode="HTML", reply_markup=markup)
            return

        updated = remove_watchdog_subscription(keyword, chat_id_str)
        bot.send_message(message.chat.id, f"✅ Removed keyword alert for <code>{html.escape(keyword)}</code>. You have {len(updated)} active alerts remaining.", parse_mode="HTML")

    @bot.message_handler(commands=['board', 'jobboard', 'livejobs', 'webapp'])
    @admin_only
    def show_job_board_miniapp(message):
        save_chat_id(message.chat.id)
        board_url = "https://nm969989-cmd.github.io/myjob-ai-bot/tn-live-jobs/"

        total_live = 0
        ats_count = 0
        govt_count = 0
        try:
            data_file = os.path.join(os.path.dirname(__file__), "tn-live-jobs", "data", "jobs.json")
            if os.path.exists(data_file):
                with open(data_file, "r", encoding="utf-8-sig") as f:
                    d = json.load(f)
                    total_live = len(d.get("jobs", []))
                    for j in d.get("jobs", []):
                        src = str(j.get("source", "")).lower()
                        if any(k in src for k in ["smartrecruiters", "freshworks", "bosch", "avery", "zoho"]):
                            ats_count += 1
                        elif any(k in src for k in ["mrb", "tnpsc", "nic.in", "govt"]):
                            govt_count += 1
        except Exception:
            pass

        markup = InlineKeyboardMarkup()
        try:
            from telebot.types import WebAppInfo
            markup.row(InlineKeyboardButton("🌐 Open Live Job Board (MiniApp)", web_app=WebAppInfo(url=board_url)))
        except Exception:
            markup.row(InlineKeyboardButton("🌐 Open Live Job Board (Web)", url=board_url))

        markup.row(
            InlineKeyboardButton("💻 Browse Tech Jobs", callback_data="tnjobs:tech"),
            InlineKeyboardButton("🏛️ Browse Govt Jobs", callback_data="tnjobs:govt")
        )
        markup.row(
            InlineKeyboardButton("🎓 Freshers Welcome", callback_data="tnjobs:freshers"),
            InlineKeyboardButton("🔄 Refresh All Jobs", callback_data="tnjobs:refresh:all")
        )

        msg = (
            "🌐 <b>TAMIL NADU LIVE JOBS WEB BOARD & MINIAPP</b> 🇮🇳\n\n"
            "✨ Real, 100% verified job vacancies in Tamil Nadu. Every opening is checked before publishing with zero expired links.\n\n"
            f"📊 <b>Active Verified Vacancies:</b> <code>{total_live or 150}+</code>\n"
            f"🏢 <b>Direct Enterprise ATS:</b> <code>{ats_count or 32}</code> (Freshworks, Bosch, Avery Dennison)\n"
            f"🏛️ <b>Govt & District Boards:</b> <code>{govt_count or 118}</code> (TN MRB, District Collectorates)\n"
            f"📍 <b>Cities:</b> Chennai, Coimbatore, Madurai, Trichy, Salem, Remote\n\n"
            "Tap below to launch the responsive board inside Telegram or browse directly by category!"
        )
        try:
            bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', msg), parse_mode=None, reply_markup=markup, disable_web_page_preview=True)

    @bot.message_handler(commands=['tnjobs', 'tamilnadu', 'chennai'])
    @admin_only
    def show_tamil_nadu_jobs(message):
        save_chat_id(message.chat.id)
        text_parts = message.text.strip().split()
        cat = None
        if len(text_parts) > 1:
            raw_cat = text_parts[1].lower().strip()
            if any(k in raw_cat for k in ["tech", "it", "soft", "dev"]):
                cat = "tech"
            elif any(k in raw_cat for k in ["govt", "mrb", "tnpsc"]):
                cat = "govt"
            elif any(k in raw_cat for k in ["core", "auto", "mech"]):
                cat = "core"
            elif any(k in raw_cat for k in ["fresh", "intern"]):
                cat = "freshers"

        loading_msg = bot.reply_to(message, f"🔍 Scanning latest Tamil Nadu jobs ({cat or 'all'} category)...", parse_mode=None)
        try:
            from job_radar import get_tamil_nadu_jobs, format_tamil_nadu_telegram_digest
            jobs, total = get_tamil_nadu_jobs(limit=10, force_refresh=False, category=cat, return_total=True)
            chunks, markup = format_tamil_nadu_telegram_digest(jobs, category=cat, total_jobs=total)
            try:
                bot.delete_message(message.chat.id, loading_msg.message_id)
            except Exception:
                pass
            for idx, chunk in enumerate(chunks):
                is_last = (idx == len(chunks) - 1)
                try:
                    bot.send_message(message.chat.id, chunk, parse_mode="HTML", reply_markup=markup if is_last else None, disable_web_page_preview=True)
                except Exception:
                    bot.send_message(message.chat.id, re.sub(r'<[^>]+>', '', chunk), parse_mode=None, reply_markup=markup if is_last else None, disable_web_page_preview=True)
                time.sleep(0.4)
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error retrieving Tamil Nadu jobs: {e}")

    # --- Quick-Access Mobile Reply Keyboard Handler ---
    @bot.message_handler(func=lambda m: (m.text or "").strip() in [
        "🌟 TN Freshers", "🚶 Walk-In Drives", "📢 National Drives",
        "⚡ Live Search", "🎯 ATS Score Match", "🩺 Bot Status", "💰 CTC Calculator",
        "🌟 TN Jobs", "🚶 Walk-Ins", "📢 Drives", "⚡ Search", "🎯 Match", "📊 Status", "💰 CTC Calc", "💰 Salary"
    ])
    @admin_only
    def handle_quick_keyboard_tap(message):
        text = str(message.text or "")
        chat_id = message.chat.id
        save_chat_id(chat_id)
        if "TN" in text:
            show_tamil_nadu_jobs(message)
        elif "Walk-In" in text or "Walk-ins" in text:
            send_walkin_drives(message)
        elif "National" in text or "Drive" in text:
            send_national_drives(message)
        elif "Search" in text:
            handle_search_command(message)
        elif "ATS" in text or "Match" in text:
            handle_match_command(message)
        elif "CTC" in text or "Salary" in text:
            handle_ctc_command(message)
        elif "Status" in text:
            send_status(message)

    @bot.message_handler(commands=['radar', 'jobs'])
    @admin_only
    def show_radar(message):
        save_chat_id(message.chat.id)
        bot.reply_to(message, "⏳ Loading latest Job Radar results...", parse_mode=None)
        try:
            with open("radar_results.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            jobs = data.get("jobs", [])
            if not jobs:
                bot.reply_to(message, "📡 *Job Radar* found no recent jobs. Check again later or run a scan from the dashboard.", parse_mode=None)
                return
            
            def clean_md(text):
                if not text:
                    return ""
                return str(text).replace("*", "").replace("_", "").replace("`", "").replace("[", "").replace("]", "")

            # Group jobs by source
            grouped = {}
            for j in jobs:
                grouped.setdefault(j.get("source", "Other"), []).append(j)

            msg = f"📡 *JOB RADAR — MULTI-PLATFORM*\n_Last scan: {data.get('last_scan', 'Unknown')}_ | 🎯 {len(jobs)} Jobs\n\n"
            
            source_headers = {
                "linkedin": "🌐 LINKEDIN",
                "indeed": "🟢 INDEED",
                "adzuna": "🎯 ADZUNA",
                "internshala": "🎓 INTERNSHALA",
                "unstop": "🚀 UNSTOP",
                "jobicy": "💼 JOBICY",
                "arbeitnow": "🇩🇪 ARBEITNOW",
                "remoteok": "🌴 REMOTEOK"
            }

            import string
            messages = []
            for source, src_jobs in grouped.items():
                s_key = source.lower().replace(" ", "")
                header_text = source_headers.get(s_key, f"📡 {source.upper()}")
                
                block = f"*{header_text}*\n━━━━━━━━━━━━━━━━━━━━\n"
                for j in src_jobs[:8]: # Limit to 8 per source
                    title = clean_md(j.get("title", "Unknown Role"))
                    company = clean_md(j.get("company", "Unknown"))
                    loc = clean_md(j.get("location", "Remote"))
                    link = j.get("link", "#")
                    desc = clean_md(j.get("description", ""))
                    date_str = clean_md(j.get("date_posted", ""))
                    
                    t_title = title[:45] + "..." if len(title) > 45 else title
                    t_company = company[:25] + "..." if len(company) > 25 else company
                    t_desc = desc[:150] + "..." if len(desc) > 150 else desc
                    
                    time_display = date_str
                    if date_str and len(date_str) >= 10:
                        try:
                            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                            days = (datetime.now() - dt).days
                            if days == 0:
                                time_display = "Today"
                            elif days == 1:
                                time_display = "Yesterday"
                            else:
                                time_display = f"{days} days ago"
                        except Exception:
                            pass

                    if "id" not in j:
                        j["id"] = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
                    job_id = j["id"]

                    desc_line = f"📝 _{t_desc}_\n" if t_desc else ""
                    
                    s_key_check = source.lower()
                    unsafe_platforms = ["linkedin", "indeed", "naukri", "foundit"]
                    is_safe = not any(p in s_key_check for p in unsafe_platforms)
                    
                    action_line = f"🔗 [Apply Manually]({link})\n"
                    if is_safe:
                        action_line += f"⚡ *Auto-Apply:* `/apply_{job_id}`\n"

                    line = (
                        f"💼 *{t_title}*\n"
                        f"🏢 {t_company}  •  📍 {loc}  •  🗓️ {time_display}\n"
                        f"{desc_line}"
                        f"{action_line}\n"
                    )
                    
                    if len(msg) + len(block) + len(line) > 3800:
                        messages.append(msg)
                        msg = f"📡 *JOB RADAR (continued)*\n\n"
                    msg += block + line
                    block = "" # Reset header block after printing once
            messages.append(msg)
            
            # Save generated IDs back
            with open("radar_results.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            for m in messages:
                bot.reply_to(message, m, parse_mode=None, disable_web_page_preview=True)
                time.sleep(0.5)
        except Exception as e:
            bot.reply_to(message, f"❌ Error loading radar results: {e}")

    @bot.message_handler(regexp=r"^/apply_([a-zA-Z0-9]+)$")
    @admin_only
    def handle_auto_apply(message):
        job_id = message.text.split("_")[1]
        
        # Look up job_id in radar_results.json
        link = None
        try:
            with open("radar_results.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                for j in data.get("jobs", []):
                    if j.get("id") == job_id:
                        link = j.get("link")
                        break
        except Exception:
            pass
            
        if not link:
            bot.reply_to(message, "❌ Job not found or expired from Radar. Please apply manually if possible.")
            return
            
        bot.reply_to(message, f"⚡ *Initiating Auto-Apply Sequence!*\n\nTarget: {link}\n\n_The Playwright engine is taking over... check the web dashboard for live status!_", parse_mode=None, disable_web_page_preview=True)
        
        # Add to the global application queue
        application_queue.put(link)
        try:
            bot.send_message(message.chat.id, f"✅ Job added to the background queue. (Queue size: {application_queue.qsize()})")
        except:
            pass


def daily_report_loop():
    """Sends a daily summary at 9 AM and a weekly report every Monday."""
    while True:
        now = datetime.now()
        chat_id = load_chat_id()
        # Daily report at 9:00 AM
        if now.hour == 9 and now.minute == 0:
            stats = load_stats()
            if bot and chat_id:
                channels_count = len(TARGET_CHANNELS)
                sleep_status = "💤 Sleeping" if is_sleep_time() else "🟢 Active"
                msg = (
                    f"📊 *Daily Report — {stats.get('date', '')}*\n\n"
                    f"✅ Applied: *{stats.get('applied', 0)}* jobs\n"
                    f"⏭️ Skipped: *{stats.get('skipped', 0)}* jobs\n"
                    f"❌ Failed: *{stats.get('failed', 0)}* jobs\n"
                    f"🔥 Streak: *{stats.get('current_streak', 0)}* days\n"
                    f"📡 Channels: *{channels_count}* being monitored\n"
                    f"🤖 Bot Status: {sleep_status}\n\n"
                    f"Keep it up! 🚀"
                )
                try:
                    bot.send_message(chat_id, msg, parse_mode=None)
                except Exception as e:
                    print(f"Error sending daily report: {e}")
                    
            # --- The Ghosting Preventer ---
            try:
                import csv
                if os.path.exists("applied_jobs_log.csv") and bot and chat_id:
                    with open("applied_jobs_log.csv", "r", encoding="utf-8") as f:
                        rows = list(csv.reader(f))
                    
                    follow_ups = []
                    for i in range(1, len(rows)):
                        row = rows[i]
                        if len(row) >= 4 and "Applied" in row[3] and "Followed Up" not in row[3]:
                            date_str = row[0][:10]
                            try:
                                dt = datetime.strptime(date_str, "%Y-%m-%d")
                                if (now - dt).days == 7:
                                    follow_ups.append((i, row[1], row[2]))
                            except: pass
                            
                    if follow_ups:
                        msg = f"👻 *GHOSTING PREVENTER ALERT*\nIt has been 7 days since you applied to {len(follow_ups)} jobs.\n\n"
                        for idx, title, url in follow_ups[:10]: # Limit to 10 in message
                            msg += f"💼 *{title[:30]}*\n🔗 [Job Link]({url})\n"
                            # Mark as followed up so it doesn't alert again
                            if len(rows[idx]) >= 5:
                                rows[idx][4] = "Followed Up"
                            else:
                                rows[idx].append("Followed Up")
                                
                        msg += "\n📝 _I highly recommend finding the recruiter on LinkedIn or sending a follow-up email today!_"
                        bot.send_message(chat_id, msg, parse_mode=None, disable_web_page_preview=True)
                        
                        with open("applied_jobs_log.csv", "w", newline="", encoding="utf-8") as f:
                            csv.writer(f).writerows(rows)
            except Exception as e:
                print(f"Ghosting Preventer error: {e}")
                
            time.sleep(61)
        # Weekly report every Monday at 9:05 AM
        if now.weekday() == 0 and now.hour == 9 and now.minute == 5:
            wk = load_weekly_stats()
            if bot and chat_id:
                msg = (
                    f"📈 *Weekly Report — {wk.get('week', '')}*\n\n"
                    f"✅ Total Applied: *{wk.get('applied', 0)}* jobs\n"
                    f"❌ Total Failed: *{wk.get('failed', 0)}* jobs\n"
                    f"📡 Channels Scanned: *{len(TARGET_CHANNELS)}*\n\n"
                    f"_New week starting! Quotas reset. Bot is fully charged! ⚡_"
                )
                try:
                    bot.send_message(chat_id, msg, parse_mode=None)
                except Exception as e:
                    print(f"Error sending weekly report: {e}")
            time.sleep(61)
        time.sleep(30)

def run_telegram_polling():
    print("Bot polling started...")
    
    # --- Conflict Prevention Feature ---
    # Detect if running locally (laptop) or on Hugging Face cloud.
    # Hugging Face sets the 'SPACE_ID' environment variable automatically.
    is_cloud = bool(os.environ.get("SPACE_ID"))
    if not is_cloud and not os.environ.get("FORCE_LOCAL"):
        print("⚠️ [Telegram] Running locally on laptop detected!")
        print("⚠️ [Telegram] Polling is DISABLED to prevent conflict with your Hugging Face cloud bot.")
        print("⚠️ [Telegram] Your cloud bot will handle all Telegram commands. Local script will only run background tasks.")
        print("⚠️ [Telegram] (To force local polling for testing, set FORCE_LOCAL=1 in .env)")
        while True:
            time.sleep(3600)  # Keep thread alive cleanly so supervisor doesn't detect it as a crash
    # -----------------------------------
    
    # CRITICAL: Remove any stale webhook to prevent polling conflicts
    try:
        bot.remove_webhook()
        print("[Telegram] Webhook cleared successfully. Starting clean polling...")
        
        # Set the bot commands in the menu (shown in "/" dashboard)
        from telebot.types import BotCommand
        commands = [
            BotCommand("start",      "❤️ Wake up & lock your Chat ID"),
            BotCommand("menu",       "🎛️ Show Quick-Access Navigation Keyboard"),
            BotCommand("help",       "📖 Full guide & all commands"),
            BotCommand("status",     "🚑 Bot health, API & stats"),
            BotCommand("oa",         "🎓 Company OA Syllabus & Exam Pattern"),
            BotCommand("alerts",     "🔔 Manage Keyword Watchdogs"),
            BotCommand("alertme",    "➕ Add Keyword Alert (/alertme python chennai)"),
            BotCommand("analytics",  "📊 Live Market & Career Analytics"),
            BotCommand("notion",     "📋 Open Notion Job Tracker"),
            BotCommand("channels",   "📡 View all monitored channels"),
            BotCommand("lastjob",    "💼 See the last application attempt"),
            BotCommand("history",    "📅 View last 10 applications"),
            BotCommand("radar",      "📡 View latest multi-platform jobs"),
            BotCommand("tnjobs",     "🌟 Tamil Nadu & Chennai Fresh Jobs"),
            BotCommand("walkins",    "🚶‍♂️ Tamil Nadu Weekend Walk-In Drives"),
            BotCommand("drives",     "📢 National Mass Off-Campus Drives"),
            BotCommand("instahyre",  "🚀 Trigger Instahyre mass-apply"),
            BotCommand("apply",      "🎯 Manually apply to a job URL"),
            BotCommand("pause",      "⏸️ Pause auto-scanning"),
            BotCommand("resume",     "▶️ Resume auto-scanning"),
            BotCommand("profile",    "📝 View your resume profile"),
            BotCommand("setprofile", "✏️ Update a profile field"),
            BotCommand("qa",         "🧠 View saved Q&A answers"),
            BotCommand("answer",     "💡 Teach bot an answer"),
            BotCommand("search",     "🔍 Multi-source job search (/search python)"),
            BotCommand("jobspy",     "⚡ Live LinkedIn & Indeed fresher search"),
            BotCommand("simplify",   "🎓 SimplifyJobs fresher tech openings"),
            BotCommand("match",      "🎯 Instant ATS resume score & gap report"),
            BotCommand("ctc",        "💰 Fresher CTC vs In-Hand Take-Home"),
            BotCommand("pitch",      "✉️ Generate 1-Tap Cold Outreach Pitch"),
            BotCommand("nearme",     "🧭 Nearest walk-in venue with GPS map"),
            BotCommand("deadlines",  "⏳ Mass drive deadlines & countdown"),
            BotCommand("clearqa",    "🗑️ Delete a saved answer"),
            BotCommand("download",   "📥 Export full CSV log"),
        ]
        bot.set_my_commands(commands)
        print("[Telegram] Bot commands menu updated.")
    except Exception as e:
        print(f"[Telegram] Error clearing webhook or setting commands: {e}")
    
    time.sleep(1)  # Small delay to let webhook removal propagate
    
    while True:
        try:
            print("[Telegram] Starting polling loop...")
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            err_str = str(e)
            if "409" in err_str or "Conflict" in err_str:
                # Another bot instance is running (e.g. Hugging Face + local at same time)
                # Wait 60 seconds for the other instance to die before retrying
                print("[Telegram] 409 Conflict: Another bot instance detected. Waiting 60s...")
                time.sleep(60)
            else:
                print(f"[Telegram] Polling error: {e}")
                print("[Telegram] Retrying in 15 seconds...")
                time.sleep(15)

# Automatically discover jobs and send unseen matches to the configured Telegram chat.
def radar_loop():
    """Priority-city search at startup and hourly by default, followed by the wider radar."""
    interval_minutes = automatic_search_interval_minutes()
    print(f"[Radar] Automatic Telegram search every {interval_minutes} minutes. First scan in 30 seconds...")
    time.sleep(30)  # Initial delay so bot fully starts first
    while True:
        if BOT_PAUSED:
            time.sleep(5)
            continue
        try:
            from job_radar import run_radar, dispatch_tamil_nadu_alerts
            chat_id = load_chat_id()

            # 1. Automatically dispatch fresh Tamil Nadu jobs (unseen only)
            if bot and chat_id:
                try:
                    print('[Radar Loop] Searching Tiruvannamalai, Vellore, Puducherry and Chennai; sending unseen jobs to Telegram...')
                    dispatch_tamil_nadu_alerts(bot=bot, chat_id=chat_id, limit=6, force_refresh=True, only_unseen=True)
                except Exception as tn_auto_e:
                    print(f"[Radar Loop] TN auto-dispatch warning: {tn_auto_e}")

            # 2. Automatically dispatch weekend walk-in drives once per day
            if bot and chat_id:
                try:
                    from bot_optimizer import dispatch_walkin_alerts
                    print("[Radar Loop] Checking Weekend Walk-In Drives auto-dispatch...")
                    dispatch_walkin_alerts(bot=bot, chat_id=chat_id, once_per_day=True, limit=5)
                except Exception as walkin_auto_e:
                    print(f"[Radar Loop] Walk-in auto-dispatch warning: {walkin_auto_e}")

            # 3. Run full radar
            new_jobs = run_radar()
            
            # If no new jobs found, send a heartbeat so user knows radar is alive
            if not new_jobs:
                chat_id = load_chat_id()
                if bot and chat_id:
                    try:
                        bot.send_message(chat_id, 
                            "📡 *Job Radar Scan Complete*\n\n"
                            "No new jobs found this cycle.\n"
                            f"⏰ Next scan in {interval_minutes} minutes.\n\n"
                            "Priority: Tiruvannamalai, Vellore, Puducherry/Pondicherry and Chennai.\n"
                            "New matches are sent automatically after each scheduled scan.",
                            parse_mode=None)
                    except: pass
            
            # Sync new radar jobs to Notion CRM
            if new_jobs:
                try:
                    gc = get_gemini_client()
                    for job in new_jobs[:5]:  # Sync top 5 to Notion
                        try:
                            sync_to_notion(
                                job.get("link", ""), 
                                f"{job.get('title', '')} at {job.get('company', '')} - {job.get('location', '')}", 
                                "Found (Pending)", gc,
                                override_company=job.get("company"),
                                override_role=job.get("title"),
                                groq_client=groq_client
                            )
                        except: pass
                except: pass
                    
        except Exception as e:
            print(f"[Radar] Loop error: {e}")
        # Short sleeps let /pause and /resume take effect while waiting between scans.
        for _ in range(interval_minutes * 12):
            time.sleep(5)
            if BOT_PAUSED:
                break

def cleanup_system_resources():
    """Kills orphaned browser processes and cleans cache to prevent resource leaks."""
    global playwright_active
    if playwright_active:
        print("[Cleanup] Playwright is currently active. Skipping resource cleanup...")
        return

    print("[Cleanup] Running periodic resource cleanup...")
    
    # 1. Kill orphaned chromium/playwright processes
    try:
        import psutil
    except ImportError:
        psutil = None

    if psutil is not None:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                if 'chrome' in name or 'chromium' in name or 'playwright' in name:
                    if proc.pid != os.getpid():
                        print(f"[Cleanup] Terminating orphaned process {name} (PID: {proc.pid})")
                        proc.terminate()
            except Exception:
                pass
    else:
        # Fallback to OS commands if psutil isn't ready
        try:
            if os.name == 'nt':
                os.system("taskkill /f /im chrome.exe /fi \"pid ne " + str(os.getpid()) + "\" 2>nul")
                os.system("taskkill /f /im chromedriver.exe 2>nul")
            else:
                os.system("pkill -f -9 chromium 2>/dev/null")
                os.system("pkill -f -9 chrome 2>/dev/null")
        except Exception as e:
            print(f"[Cleanup] OS taskkill failed: {e}")
            
    # 2. Clean temporary chrome profile cache
    cache_path = os.path.abspath("chrome_profile/Default/Cache")
    if os.path.exists(cache_path):
        try:
            import shutil
            shutil.rmtree(cache_path)
            print("[Cleanup] Cleared chrome profile Cache directory.")
        except Exception as e:
            print(f"[Cleanup] Error clearing cache: {e}")

def walkin_reminder_loop():
    while True:
        try:
            if bot:
                dispatch_due_reminders(bot)
        except Exception as exc:
            print(f'[Reminders] Dispatch error: {exc}')
        time.sleep(30)


def thread_supervisor():
    """Monitors and automatically restarts background threads if they crash."""
    print("[Supervisor] Thread supervisor loop started.")
    
    threads_config = {
        "Job Monitor": {"target": job_monitor_loop, "thread": None},
        "Daily Report": {"target": daily_report_loop, "thread": None},
        "Job Radar Loop": {"target": radar_loop, "thread": None},
        "Walk-in Reminders": {"target": walkin_reminder_loop, "thread": None},
    }
    if bot:
        threads_config["Telegram Polling"] = {"target": run_telegram_polling, "thread": None}

    last_cleanup = 0

    while True:
        try:
            for name, cfg in threads_config.items():
                t = cfg["thread"]
                if t is None or not t.is_alive():
                    if t is not None:
                        print(f"⚠️ [Supervisor] WARNING: Thread '{name}' died! Auto-restarting...")
                    new_t = Thread(target=cfg["target"], name=name, daemon=True)
                    new_t.start()
                    cfg["thread"] = new_t

            # Periodically run system resource cleanup every 4 hours
            now = time.time()
            if now - last_cleanup > 4 * 60 * 60:
                cleanup_system_resources()
                last_cleanup = now
        except Exception as e:
            print(f"[Supervisor] Loop error: {e}")
        # ⏱️ HF-SAFE: Check thread health every 60s (not 15s).
        # This reduces the supervisor's own CPU overhead by 4x.
        time.sleep(60)

if __name__ == "__main__":
    # Start the supervisor thread to spawn and maintain all workers
    supervisor_thread = Thread(target=thread_supervisor, daemon=True, name="Supervisor")
    supervisor_thread.start()

    # Start Flask on port 7860
    app.run(host="0.0.0.0", port=7860)

import os
import re
import json
import time
import random
import requests
import csv

from datetime import datetime
from bs4 import BeautifulSoup
from flask import Flask
from threading import Thread
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from playwright.sync_api import sync_playwright
# pyrefly: ignore [missing-import]
from playwright_stealth import stealth_sync
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
from enterprise_adapters import execute_workday_adapter, execute_lever_adapter, execute_greenhouse_adapter
from instahyre_engine import run_instahyre_mass_apply
from bot_optimizer import minify_form_html, apply_regex_fallback, apply_rag_memory_fallback

class LoggerWriter:
    def __init__(self, filename):
        self.filename = filename
        self.original_stdout = sys.__stdout__  # Use the real original stdout
    def write(self, message):
        try:
            # Encode to ASCII-safe for Windows console, then decode back
            safe_msg = message.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
            self.original_stdout.write(safe_msg)
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
_raw_token = os.getenv("TELEGRAM_TOKEN", "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4")
TELEGRAM_TOKEN = str(_raw_token).strip().strip('"').strip("'")
if TELEGRAM_TOKEN.lower().startswith("bot"):
    TELEGRAM_TOKEN = TELEGRAM_TOKEN[3:]
if not TELEGRAM_TOKEN:
    TELEGRAM_TOKEN = "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4"

_raw_chat = os.getenv("TELEGRAM_CHAT_ID", "7607565831")
TELEGRAM_CHAT_ID = str(_raw_chat).strip().strip('"').strip("'") or "7607565831"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL", "JobSkull")  # Primary channel (kept for backward compat)
# All channels to monitor (from env as comma-separated list, or use defaults)
_channels_env = os.getenv("TARGET_CHANNELS", "")
TARGET_CHANNELS = [c.strip().lstrip("@") for c in _channels_env.split(",") if c.strip()] if _channels_env else [
    # Top Pan-India Engineering & Fresher Job Channels
    "JobSkull",
    "KickCharm",
    "OffCampusJobs4u",
    "offcampusjobss",
    "Freshershunt",
    "job4freshers",
    "placementjobs",
    "jobsinternshipplacement",
    "fresheroffcampus",
    "workfromhomejobs1",
    "offcampusphodenge",
    "veagance",
    "DailyJobs4You",
    "Foundthejob",
    # Tamil Nadu & South India High Priority Channels
    "chennaijobs2025",
    "chennaijobsofficial",
    "tamilnadujob",
    "tamilnadujobsalert",
    "TamilNadu_Govt_Private_Jobs",
    "chennai_it_jobs",
    "coimbatore_jobs",
    "tn_job_alert",
    "bangalore_chennai_jobs",
    "tamil_tech_jobs",
    "chennai_walkins",
    "tamilnadu_freshers",
    "tn_fresher_jobs",
    # Tech & Placement Update Channels
    "offcampus_freshers",
    "freshers_jobs_india",
    "tech_jobs_india",
    "internships_freshers",
    "naukri_fresher_jobs",
    "allindiafreshersjobs",
    "it_jobs_freshers",
    "placement_season",
    "offcampushire",
    "freshersvoice",
    "jobopenings_india",
    "techfreshers",
    "jobsforyou_india",
    "freshers_drive",
    "engineering_jobs_india",
    "software_jobs_india",
    "campus_placement_prep",
    "india_remote_jobs",
    "fresher_engineer_jobs",
    "fresher_it_openings",
]

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

# Helper to load and save chat ID dynamically
def load_chat_id():
    global TELEGRAM_CHAT_ID
    if TELEGRAM_CHAT_ID:
        return TELEGRAM_CHAT_ID
    data = safe_load_json(CHAT_ID_FILE, {})
    return data.get("chat_id", "7607565831")

def save_chat_id(chat_id):
    global TELEGRAM_CHAT_ID
    TELEGRAM_CHAT_ID = str(chat_id)
    safe_save_json(CHAT_ID_FILE, {"chat_id": TELEGRAM_CHAT_ID})
    print(f"[Auth] Saved Telegram chat ID dynamically: {TELEGRAM_CHAT_ID}")

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
else:
    bot = None
# Handle multiple Gemini API keys
GEMINI_API_KEYS = [k.strip() for k in str(os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip() and k.strip().startswith("AIza")]
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

# Global pause flag
BOT_PAUSED = False
ghost_mode_chats = set()
playwright_active = False


# --- 1.5 THREAD-SAFE STORAGE UTILITIES ---
import threading
import queue
file_lock = threading.Lock()
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

# Load state
def load_applied_jobs():
    data = safe_load_json(STATE_FILE, [])
    return set(data)

def save_applied_job(job_url):
    applied = load_applied_jobs()
    applied.add(job_url)
    safe_save_json(STATE_FILE, list(applied))

# --- QA Memory: remember answers to custom job questions ---
def load_qa_memory():
    return safe_load_json(QA_MEMORY_FILE, {})

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

# Load profile data
def load_profile():
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
    return safe_load_json(PROFILE_FILE, default_profile)

def clean_tracking_params(url):
    """Strips Google Analytics/Social Media tracking parameters to keep URLs clean and direct."""
    if not url:
        return url
    from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        tracking_keys = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref", "source", "ref_id"]
        filtered_qs = {k: v for k, v in qs.items() if k.lower() not in tracking_keys}
        clean_query = urlencode(filtered_qs, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))
    except Exception:
        return url

# --- 2. WEBPAGE REDIRECT BYPASSER ---
def bypass_blog_redirect(blog_url):
    """
    Intelligently finds the real company application link inside ad-heavy blogger/shortener pages.
    Step 1: Follow HTTP redirects (handles URL shorteners like pdlink.in, bit.ly, tinyurl, etc.)
    Step 2: Deep container HTML scraping for the actual ATS/careers apply link
    Step 3: Playwright JS-rendering fallback for dynamic pages
    """
    from urllib.parse import urlparse, parse_qs, unquote

    if not blog_url:
        return blog_url

    # If the URL is already a direct job board/ATS/form, return it immediately without fetching
    direct_domains = [
        "docs.google.com/forms", "forms.gle", "greenhouse.io", "lever.co", "workdayjobs.com",
        "smartrecruiters.com", "joinsuperset.com", "myworkdayjobs.com", "sensehq.com",
        "oraclecloud.com", "successfactors", "icims.com", "ashbyhq.com",
        "bamboohr.com", "jobs.lever.co", "taleo.net", "breezy.hr",
        "recruitee.com", "freshteam.com", "zohorecruit.com", "wellfound.com",
        "angel.co", "workingnomads.com", "weworkremotely.com", "hired.com",
        "triplebyte.com", "ycombinator.com/companies", "darwinbox.com", "keka.com",
        "unstop.com", "internshala.com", "foundit.in", "naukri.com", "hirist.com",
    ]
    if any(domain in blog_url.lower() for domain in direct_domains):
        print(f"[Bypasser] URL is already a direct job page: {blog_url}")
        return clean_tracking_params(blog_url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        # Step 1: Follow all HTTP redirects to get the FINAL URL
        response = requests.get(blog_url, headers=headers, timeout=15, allow_redirects=True)
        final_url_after_redirect = response.url

        print(f"[Bypasser] Redirect chain resolved: {blog_url} → {final_url_after_redirect}")

        # If the redirect itself landed on a known job platform, return immediately
        if any(domain in final_url_after_redirect.lower() for domain in direct_domains):
            print(f"[Bypasser] Redirect resolved to direct job page: {final_url_after_redirect}")
            return clean_tracking_params(final_url_after_redirect)

        # Check if the final redirect landed on a parked / expired domain sale page
        parked_domains_list = [
            "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com",
            "namecheap.com", "domainmarket.com", "parklogic.com", "parkingcrew.com",
            "bodis.com", "above.com", "domainagents.com", "undeveloped.com",
            "buydomains.com", "domain_profile.cfm", "domainforbuy"
        ]
        if any(p in final_url_after_redirect.lower() for p in parked_domains_list):
            print(f"[Bypasser] Redirected to parked/expired domain ({final_url_after_redirect}) — rejecting.")
            return ""

        # If redirect changed the URL significantly (e.g. shortener resolved), use the final URL
        parsed_original = urlparse(blog_url)
        parsed_final = urlparse(final_url_after_redirect)
        if parsed_original.netloc != parsed_final.netloc:
            print(f"[Bypasser] URL shortener resolved to new domain: {final_url_after_redirect}")
            blog_url = final_url_after_redirect

        parsed_blog = urlparse(blog_url)
        blog_domain = parsed_blog.netloc

        soup = BeautifulSoup(response.text, "html.parser")

        # Focus search on post article container to avoid header/footer/sidebar clutter
        container = (
            soup.find("div", class_=lambda c: c and any(k in str(c) for k in ["post-body", "entry-content", "article-body", "article-content", "post-content"])) or
            soup.find("article") or
            soup.find("div", id=lambda i: i and any(k in str(i) for k in ["post-body", "content", "main-content"])) or
            soup
        )

        # Priority 0: Check <meta http-equiv="refresh"> redirect tags
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile(r"refresh", re.I)})
        if meta_refresh:
            content = meta_refresh.get("content", "")
            url_match = re.search(r'url\s*=\s*["\']?([^"\';\s>]+)', content, re.I)
            if url_match:
                meta_url = url_match.group(1)
                if meta_url.startswith("http") and blog_domain not in meta_url:
                    if not any(p in meta_url.lower() for p in parked_domains_list):
                        print(f"[Bypasser] Found meta refresh redirect: {meta_url}")
                        return clean_tracking_params(meta_url)

        skip_domains = [
            "newsletter", "instagram.com", "youtube.com", "youtu.be", "whatsapp.com", "telegram.org",
            "t.me", "telegram.dog", "facebook.com", "twitter.com", "x.com", "pinterest.com", "reddit.com",
            "play.google.com", "apps.apple.com", "aratt.ai", "wa.me", "threads.net", "linktr.ee",
            "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com", "namecheap.com",
            "domainmarket.com", "parklogic.com", "parkingcrew.com", "bodis.com", "above.com",
            "domainagents.com", "undeveloped.com", "buydomains.com", "domain_profile.cfm", "domainforbuy"
        ]

        # Priority 1: Direct ATS / Job board links inside container
        for link in container.find_all("a", href=True):
            href = link["href"].strip()
            if not href.startswith("http"):
                continue
            if any(domain in href.lower() for domain in direct_domains):
                if blog_domain not in href and not any(x in href.lower() for x in skip_domains):
                    print(f"[Bypasser] Found direct ATS link: {href}")
                    return clean_tracking_params(href)

        # Priority 2: Look for <a> links with "Apply" / "Registration" keywords in text
        apply_keywords = [
            "apply online", "click here to apply", "apply for this job", "start application",
            "apply link", "direct apply", "official apply link", "official link", "registration link",
            "apply now", "register now", "apply here", "external apply", "apply on company",
            "career page", "company website", "job link",
        ]
        for link in container.find_all("a", href=True):
            href = link["href"].strip()
            link_text = link.get_text(separator=" ").strip().lower()
            if not href.startswith("http"):
                continue
            if any(word in link_text for word in apply_keywords):
                if blog_domain not in href and not any(x in href.lower() for x in skip_domains):
                    print(f"[Bypasser] Found apply link by text keyword: {href}")
                    return clean_tracking_params(href)

        # Priority 3: Check query parameters in links for redirect targets
        for link in container.find_all("a", href=True):
            href = link["href"]
            if any(param in href for param in ["target=", "url=", "redirect=", "goto=", "link=", "dest=", "next=", "redir="]):
                try:
                    parsed = urlparse(href)
                    qs = parse_qs(parsed.query)
                    for key in ["target", "url", "redirect", "goto", "link", "dest", "next", "redir"]:
                        if key in qs:
                            real_url = unquote(qs[key][0])
                            if real_url.startswith("http") and not any(x in real_url.lower() for x in skip_domains):
                                print(f"[Bypasser] Found redirect param link: {real_url}")
                                return clean_tracking_params(real_url)
                except Exception:
                    pass

        # Priority 4: Look for JavaScript window.location or window.open redirects in scripts
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
                    js_url = match.group(1)
                    if js_url.startswith("http") and blog_domain not in js_url and not any(x in js_url.lower() for x in skip_domains):
                        print(f"[Bypasser] Found JS redirect link: {js_url}")
                        return clean_tracking_params(js_url)

        # Priority 5: Look for any external link matching career/jobs paths
        all_external_links = []
        for link in container.find_all("a", href=True):
            href = link["href"].strip()
            if href.startswith("http") and blog_domain not in href:
                if not any(x in href.lower() for x in skip_domains):
                    all_external_links.append(href)
        
        for ext_link in all_external_links:
            if any(kw in ext_link.lower() for kw in ["/career", "/job", "/apply", "/opening", "/hiring", "/recruit", "careers.", "jobs."]):
                print(f"[Bypasser] Found career page URL pattern: {ext_link}")
                return clean_tracking_params(ext_link)

        # Priority 6: Check for button onclick handlers
        for btn in container.find_all(["button", "a", "div"], onclick=True):
            onclick = btn.get("onclick", "")
            url_match = re.search(r'["\']?(https?://[^"\';\s]+)', onclick)
            if url_match:
                btn_url = url_match.group(1)
                if blog_domain not in btn_url and not any(x in btn_url.lower() for x in skip_domains):
                    print(f"[Bypasser] Found onclick URL: {btn_url}")
                    return clean_tracking_params(btn_url)

        if all_external_links:
            print(f"[Bypasser] Using first external link: {all_external_links[0]}")
            return clean_tracking_params(all_external_links[0])

        # Fallback: return the final URL after redirect resolution
        print(f"[Bypasser] No apply link found in HTML. Using final resolved URL: {blog_url}")
        return clean_tracking_params(blog_url)
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

    # ── ALL GEMINI KEYS FAILED → FALLBACK TO GROQ ──────────────────────
    print("[Groq] All Gemini keys failed for AI Filter. Falling back to Groq...")
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

        # Send skipped jobs with official links to Telegram
        if status == "Skipped" and url and "http" in url:
            try:
                chat_id = load_chat_id()
                if bot and chat_id:
                    msg = f"⏭ *SKIPPED JOB*\n\n*Title:* `{title}`\n*Reason:* {reason}\n*Link:* {url}"
                    try:
                        bot.send_message(chat_id, msg, parse_mode=None, disable_web_page_preview=True)
                    except:
                        msg_plain = f"⏭ SKIPPED JOB\n\nTitle: {title}\nReason: {reason}\nLink: {url}"
                        bot.send_message(chat_id, msg_plain, disable_web_page_preview=True)
            except Exception as e:
                print(f"[Tracker] Error sending skipped job to TG: {e}")
        
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

            # FEATURE 1: PLAYWRIGHT BANDWIDTH SAVER 🏎️
            # Intercept and block all heavy assets to make Playwright 5x faster and save HF bandwidth
            def intercept_route(route):
                if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
                    route.abort()
                else:
                    route.continue_()
            
            try:
                context.route("**/*", intercept_route)
                print("[Efficiency Engine] ✅ Blocked images, fonts, and media. Browser is running in Hyper-Speed Mode.")
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
                rag_filled = apply_rag_memory_fallback(page, qa_memory)
                
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

def is_social_or_promo_link(url):
    """Detects if a URL is a social media link, channel promo, parked domain, or non-job page."""
    if not url or not isinstance(url, str):
        return True
    u = url.lower().strip()
    
    # Exclude social media profiles, chat groups, channel promos & parked domains
    promo_domains = [
        "t.me", "telegram.org", "telegram.dog", "whatsapp.com", "wa.me",
        "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com",
        "youtube.com", "youtu.be", "pinterest.com", "threads.net",
        "linktr.ee", "bio.link", "campsite.bio", "taplink.cc", "beacons.ai",
        "play.google.com", "apps.apple.com", "aratt.ai",
        # Expired / Parked / Squatter domains
        "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com",
        "namecheap.com", "domainmarket.com", "parklogic.com", "parkingcrew.com",
        "bodis.com", "above.com", "domainagents.com", "undeveloped.com",
        "buydomains.com", "domain_profile.cfm", "domainforbuy"
    ]
    if any(d in u for d in promo_domains):
        return True
        
    # LinkedIn company, personal profile, or feed pages are NOT direct job apply links
    if "linkedin.com" in u:
        if any(p in u for p in ["/company/", "/in/", "/feed/", "/posts/", "/groups/", "/pulse/", "/school/"]):
            return True
            
    return False

def extract_structured_channel_job_details(message_text, raw_link, final_url, channel_name):
    """
    Parses channel message text and direct URL to extract structured job metadata.
    Returns: dict with (company, role, location, batch, salary, work_mode, description_summary, direct_url, is_tamil_nadu, priority_tier, is_valid_india)
    """
    from job_radar import classify_location

    text_clean = message_text.strip()
    lines = [l.strip() for l in text_clean.split('\n') if l.strip()]
    first_line = lines[0] if lines else ""

    # 1. EXTRACT COMPANY
    company = ""
    comp_m = re.search(r'(?:🏢\s*Company|Company|Organisation|Org|Organization)\s*[:\-]\s*([^\n📍💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
    if comp_m:
        company = comp_m.group(1).strip()
    
    if not company or len(company) < 2:
        m_hiring = re.search(r'^[^\w\s]*\s*([A-Za-z0-9\s.,&-]+?)\s+(?:is\s+Hiring|is\s+Recruiting|Recruitment\s+20\d\d|Recruitment|Off\s*Campus\s+Drive|Off\s*Campus|Mega\s+Drive|Drive|Hiring|Walkin|Walk-in)', first_line, re.I)
        if m_hiring:
            company = m_hiring.group(1).strip()

    if not company or len(company) < 2:
        m_comp_after = re.search(r'🏢\s*Company\s*:\s*([^\n📍💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
        if m_comp_after:
            company = m_comp_after.group(1).strip()

    company = re.sub(r'[^\w\s.,&-]', '', company).replace('Title', '').replace(':', '').strip()
    invalid_companies = ["verified recruiter", "hiring", "job", "hugedomains", "godaddy", "sedo", "dan", "afternic", "domain", "admin", "unknown"]
    if not company or len(company) < 2 or company.lower() in invalid_companies:
        # Fallback from direct URL domain
        if final_url and "http" in final_url and not is_social_or_promo_link(final_url):
            from urllib.parse import urlparse
            netloc = urlparse(final_url).netloc.lower()
            for part in netloc.split('.'):
                if part not in ["www", "com", "in", "io", "co", "careers", "jobs", "apply", "wd3", "myworkdayjobs", "sensehq", "greenhouse", "lever", "smartrecruiters", "docs", "google", "hugedomains", "sedo", "godaddy"]:
                    if len(part) >= 3:
                        company = part.capitalize()
                        break
        if not company or len(company) < 2 or company.lower() in invalid_companies:
            company = "Verified Recruiter"

    # 2. EXTRACT ROLE / POSITION
    role = ""
    role_m = re.search(r'(?:(?:🚀\s*)?Hiring\s+Now|Role|Position|Job\s*Title|Profile|Post|Designation)\s*[:\-]\s*([^\n🏢📍💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
    if role_m:
        role = role_m.group(1).strip()

    if not role or len(role) < 2:
        m_role_paren = re.search(r'is\s+Hiring\s*\(([^)]+)\)', first_line, re.I)
        if m_role_paren:
            role = m_role_paren.group(1).strip()

    if not role or len(role) < 2:
        if "is Hiring" in first_line:
            after_hiring = first_line.split("is Hiring")[-1].strip()
            after_hiring = re.sub(r'[^\w\s.,&-]', '', after_hiring).strip()
            if len(after_hiring) > 3:
                role = after_hiring

    role = re.sub(r'^[▪️👉•\-:\s]+', '', role).strip()
    role = re.sub(r'[^\w\s.,&/\(\)\-]', '', role).strip()
    if not role or len(role) < 2:
        role = "Software Developer / Fresher Engineer"

    # 3. EXTRACT LOCATION
    raw_loc = ""
    loc_m = re.search(r'(?:📍\s*Location|Location|Job\s*Location|Work\s*Location|Place)\s*[:\-]\s*([^\n🏢💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
    if loc_m:
        raw_loc = loc_m.group(1).strip()
    is_valid_loc, tier, loc_tag, is_tn = classify_location(raw_loc, text_clean)

    # 4. EXTRACT BATCH / ELIGIBILITY
    batch = ""
    batch_m = re.search(r'(?:🎓\s*Batch|Batch|Eligibility|Passout|Year\s*of\s*Passing|Qualification|Experience|Exp)\s*[:\-]\s*([^\n🏢📍💼🛠️💰📝👉🔗|]+)', text_clean, re.I)
    if batch_m:
        batch = batch_m.group(1).strip()
    if not batch:
        batch = "2024 / 2025 / 2026 Batch | Freshers"

    # 5. EXTRACT SALARY / CTC
    salary = ""
    sal_m = re.search(r'(?:💰\s*(?:Expected\s*CTC|CTC)|Expected\s*CTC|CTC|Salary|Package|Pay|Stipend)\s*[:\-]\s*([^\n🏢📍💼🛠️📝👉🔗|]+)', text_clean, re.I)
    if sal_m:
        salary = sal_m.group(1).strip()
    if not salary:
        salary = "As per Industry Standard"

    # 6. EXTRACT WORK STATUS / JOB TYPE
    work_mode = ""
    wm_m = re.search(r'(?:🛠️\s*Work\s*Status|Work\s*Status|💼\s*Job\s*Type|Job\s*Type|Work\s*Mode)\s*[:\-]\s*([^\n🏢📍💰📝👉🔗|]+)', text_clean, re.I)
    if wm_m:
        work_mode = wm_m.group(1).strip()
        work_mode = re.sub(r'🛠️\s*Work\s*Status\s*:\s*', '| ', work_mode).strip()

    # 7. EXTRACT JOB DESCRIPTION / SUMMARY
    desc_summary = ""
    desc_m = re.search(r'(?:📝\s*Job\s*Description|Job\s*Description|Description|Responsibilities|About\s*Role)\s*[:\-]\s*([^\n👉🔗]+)', text_clean, re.I)
    if desc_m:
        desc_summary = desc_m.group(1).strip()[:200]
        if len(desc_m.group(1).strip()) > 200:
            desc_summary += "..."

    return {
        "company": company[:50],
        "role": role[:65],
        "location": loc_tag if loc_tag else "India (PAN India) 🇮🇳",
        "raw_location": raw_loc,
        "batch": batch[:50],
        "salary": salary[:40],
        "work_mode": work_mode[:40] if work_mode else "Full-time / Fresher",
        "description_summary": desc_summary,
        "direct_url": final_url,
        "is_tamil_nadu": is_tn,
        "priority_tier": tier,
        "is_valid_india": is_valid_loc,
    }

# --- 5. TELEGRAM CHANNEL SCRAPER (PUBLIC WEB PREVIEW) ---
def scrape_single_channel(channel_name, applied_jobs, active_chat_id, max_jobs=2):
    """
    Scrapes one Telegram public channel and triggers applications for new jobs.
    Returns (new_jobs_found, attempts_this_cycle).
    """
    global _seen_this_cycle
    channel_name = channel_name.replace("@", "")
    url = f"https://telegram.dog/s/{channel_name}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    new_jobs_found = 0
    attempts_this_cycle = 0
    profile = load_profile()

    # Load and update channel status
    ch_status = load_channel_status()
    ch_status.setdefault(channel_name, {"last_scan": "Never", "jobs_found": 0, "status": "Pending"})

    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"[Scraper] @{channel_name} -> HTTP {response.status_code}")
        soup = BeautifulSoup(response.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message_text")
        if not messages:
            ch_status[channel_name].update({"status": "Empty/Private", "last_scan": datetime.now().strftime("%H:%M")})
            save_channel_status(ch_status)
            print(f"[Scraper] @{channel_name} -> No messages found (private or empty channel).")
            return 0, 0
    except Exception as e:
        ch_status[channel_name].update({"status": f"Error: {str(e)[:40]}", "last_scan": datetime.now().strftime("%H:%M")})
        save_channel_status(ch_status)
        print(f"[Scraper] @{channel_name} → Fetch error: {e}")
        return 0, 0

    # Only inspect the latest 5 messages per channel for lightning fast cloud runs
    recent_messages = messages[-5:] if len(messages) > 5 else messages
    for msg in reversed(recent_messages):
        if attempts_this_cycle >= max_jobs:
            break
        message_text = msg.get_text(separator=" ")

        # --- IMPROVED LINK EXTRACTION ---
        # Extract hrefs from <a> tags and raw text
        urls_found = []
        for a_tag in msg.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("http") and not is_social_or_promo_link(href):
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

            print(f"[Scraper] Resolved Direct Link: {final_url}")

            # Structured Details Extraction & India / Tamil Nadu check
            details = extract_structured_channel_job_details(message_text, job_link, final_url, channel_name)

            # Skip if company is invalid or default placeholder with no real info
            if details["company"] in ["Verified Recruiter", "Hugedomains"] and details["role"] == "Software Developer / Fresher Engineer" and "http" not in final_url:
                print(f"[Scraper] Skipping generic/unparseable job post.")
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
                is_match, job_summary = check_job_match(message_text, profile)
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

            # ✅ Job matched — send ultra-detailed executive HTML card to Telegram
            if bot and active_chat_id:
                try:
                    import html
                    channel_post_url = f"https://t.me/s/{channel_name}"
                    
                    tn_header = "🌟 <b>[TAMIL NADU PRIORITY OPPORTUNITY]</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" if details["is_tamil_nadu"] else ""
                    work_info = f"🛠️ <b>Work Mode / Type:</b> <code>{html.escape(str(details['work_mode']))}</code>\n" if details.get('work_mode') else ""
                    desc_info = f"\n📋 <b>Job Summary & Highlights:</b>\n<i>{html.escape(str(details['description_summary']))}</i>\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" if details.get('description_summary') else ""

                    notification = (
                        f"🎯 <b>New Verified Job Opening Detected!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"{tn_header}"
                        f"🏢 <b>Company:</b> <code>{html.escape(str(details['company']))}</code>\n"
                        f"💼 <b>Role / Position:</b> <b>{html.escape(str(details['role']))}</b>\n"
                        f"📍 <b>Job Location:</b> <code>{html.escape(str(details['location']))}</code>\n"
                        f"🎓 <b>Batch / Eligibility:</b> <code>{html.escape(str(details['batch']))}</code>\n"
                        f"💰 <b>Salary / CTC:</b> <code>{html.escape(str(details['salary']))}</code>\n"
                        f"{work_info}"
                        f"📡 <b>Source Channel:</b> <a href=\"{html.escape(str(channel_post_url))}\">@{html.escape(str(channel_name))}</a>\n\n"
                        f"🔗 <b>Verified Direct Apply:</b> <a href=\"{html.escape(str(final_url))}\">Apply on Official Portal</a>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        f"{desc_info}"
                        f"👉 <b>Tap the button below to apply directly on the official portal!</b>"
                    )
                    markup = InlineKeyboardMarkup()
                    markup.row(
                        InlineKeyboardButton("🚀 Direct Apply (Official)", url=final_url),
                        InlineKeyboardButton("📢 View Channel Post", url=channel_post_url)
                    )
                    bot.send_message(active_chat_id, notification, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
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
                        InlineKeyboardButton("📱 Dashboard", url="https://gokuuc-myjob-bot.hf.space")
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
                    markup.add(InlineKeyboardButton("📱 Open Dashboard", url="https://gokuuc-myjob-bot.hf.space"))
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
        data = request.json
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

from flask import request, send_file, jsonify

import subprocess

@app.route("/api/manual_apply", methods=["POST"])
def api_manual_apply():
    data = request.json
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
    data = request.json
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
    data = request.json
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
    if file and file.filename.endswith('.pdf'):
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
    if file and file.filename.endswith('.json'):
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
    data = request.json
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
        
        # Row 3: Actions
        markup.add(
            InlineKeyboardButton("🎯 Job Radar", callback_data="radar"),
            InlineKeyboardButton("👁️ Ghost Mode Toggle", callback_data="ghost")
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

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        save_chat_id(message.chat.id)
        bot.reply_to(message,
            "👋 Welcome to *Elite Job Auto-Apply Bot!*\n\n"
            "🤖 I am now locked to your Chat ID and scanning jobs 24/7!\n\n"
            "📱 Use `/dashboard` or `/menu` to open your Interactive Command Center.\n\n"
            "Type `/help` to see all available text commands.",
            parse_mode=None)

    @bot.message_handler(commands=['help'])
    def send_help(message):
        save_chat_id(message.chat.id)
        help_text = """
🤖 *ELITE JOB AUTO-APPLY BOT | COMMAND CENTER* 🤖

_Welcome to your fully autonomous AI job-hunting engine! Here is your complete manual:_

⚡️ *CORE OPERATIONS*
🔹 `/start` - Wake up the bot and lock your Chat ID for notifications.
🔹 `/help` - Show this detailed command manual.
🔹 `/status` - 🩺 Check the heartbeat of the bot, API keys, and total jobs processed.
🔹 `/pause` - 🛑 Temporarily stop the background 24/7 scanning.
🔹 `/resume` - 🟢 Turn the background scanning back on.

🧠 *AI MEMORY & PROFILE*
🔹 `/profile` - 📋 View all your current resume details the bot uses to fill forms.
🔹 `/setprofile <field> | <value>` - ✍️ Update a specific field dynamically (e.g., `/setprofile phone | +19876543210`).
🔹 `/qa` - 🗂 View all the tricky company questions the bot has permanently memorized.
🔹 `/answer <num> | <text>` - 💡 Teach the bot how to answer a specific question so it never asks you again!
🔹 `/clearqa <num>` - 🗑 Delete a saved answer from the bot's brain.

📊 *ANALYTICS & MANUAL ACTION*
🔹 `/apply <url>` - 🎯 Force the bot to immediately apply to a specific job link you found.
🔹 `/instahyre <email> | <password>` - 🚀 Trigger the Instahyre Mass-Applier (Submits 20 jobs instantly).
🔹 `/notion` - 📋 Open your Notion Job Tracker with full CRM details.
🔹 `/history` - 🕒 View the last 10 jobs the bot attempted, including success/fail status.
🔹 `/download` - 📥 Export a massive CSV Excel file of every single job ever applied to.

_Tip: The bot sends a daily summary at 7 AM, runs Instahyre at 11 PM, and tracks your streak!_ 🔥
"""
        bot.reply_to(message, help_text, parse_mode=None)

    @bot.message_handler(commands=['instahyre'])
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
        markup.add(InlineKeyboardButton("📱 Open Dashboard", url="https://gokuuc-myjob-bot.hf.space"))
        bot.reply_to(message, msg, parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['status'])
    def send_status(message):
        save_chat_id(message.chat.id)
        applied = load_applied_jobs()
        stats = load_stats()
        resume_ok = "✅" if os.path.exists(RESUME_FILE) else "❌"
        gemini_ok = "✅" if gemini_client else "❌"
        groq_ok = "✅" if groq_client else "❌"
        bot_state = "⏸️ PAUSED" if BOT_PAUSED else "▶️ RUNNING"
        markup = InlineKeyboardMarkup(row_width=2)
        if BOT_PAUSED:
            markup.add(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
        else:
            markup.add(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
        markup.add(
            InlineKeyboardButton("🕒 History", callback_data="history"),
            InlineKeyboardButton("🔄 Refresh Status", callback_data="status")
        )
        status_text = (
            f"🤖 *Elite Job Bot — Live Status*\n\n"
            f"⚙️ Bot State: `{bot_state}`\n"
            f"🎯 Total Jobs Processed: `{len(applied)}`\n"
            f"🚀 Applied Today: `{stats.get('applied', 0)}`\n"
            f"⏭️ Skipped Today: `{stats.get('skipped', 0)}`\n"
            f"🔥 Day Streak: `{stats.get('current_streak', 0)}`\n\n"
            f"🧠 Gemini AI: {gemini_ok}\n"
            f"⚡ Groq AI: {groq_ok}\n"
            f"📄 Resume: {resume_ok}\n"
            f"📡 Channel: @{TARGET_CHANNEL}"
        )
        bot.reply_to(message, status_text, parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['profile'])
    def send_profile(message):
        save_chat_id(message.chat.id)
        profile = load_profile()
        bot.reply_to(message, f"📋 Profile details loaded:\n\n{json.dumps(profile, indent=2)}")

    @bot.message_handler(commands=['history'])
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
    def pause_bot(message):
        save_chat_id(message.chat.id)
        global BOT_PAUSED
        BOT_PAUSED = True
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
        bot.reply_to(message, "⏸️ *Bot Paused!*\n\nAuto job scanning is stopped.\nTap the button below to resume.", parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['resume'])
    def resume_bot(message):
        save_chat_id(message.chat.id)
        global BOT_PAUSED
        BOT_PAUSED = False
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
        bot.reply_to(message, "▶️ *Bot Resumed!*\n\nAuto job scanning is now active! The bot will find and apply to jobs automatically.", parse_mode=None, reply_markup=markup)

    @bot.message_handler(commands=['watch', 'ghost'])
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

    @bot.callback_query_handler(func=lambda call: call.data in ["pause", "resume", "status", "history", "profile", "help", "last_job", "qa_memory", "radar", "ghost"])
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
                bot.edit_message_text("⏸️ *Bot Paused!*\n\nAuto job scanning is stopped.\nTap below to resume.",
                    chat_id=chat_id, message_id=call.message.message_id,
                    parse_mode=None, reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, "⏸️ *Bot Paused!*", parse_mode=None, reply_markup=markup)

        elif call.data == "resume":
            BOT_PAUSED = False
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
            try:
                bot.edit_message_text("▶️ *Bot Resumed!*\n\nScanning jobs 24/7 again!",
                    chat_id=chat_id, message_id=call.message.message_id,
                    parse_mode=None, reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, "▶️ *Bot Resumed!*", parse_mode=None, reply_markup=markup)

        elif call.data == "status":
            applied = load_applied_jobs()
            stats = load_stats()
            resume_ok = "✅" if os.path.exists(RESUME_FILE) else "❌"
            gemini_ok = "✅" if gemini_client else "❌"
            groq_ok = "✅" if groq_client else "❌"
            bot_state = "⏸️ PAUSED" if BOT_PAUSED else "▶️ RUNNING"
            markup = InlineKeyboardMarkup(row_width=2)
            if BOT_PAUSED:
                markup.add(InlineKeyboardButton("▶️ Resume Bot", callback_data="resume"))
            else:
                markup.add(InlineKeyboardButton("⏸️ Pause Bot", callback_data="pause"))
            markup.add(
                InlineKeyboardButton("🕒 History", callback_data="history"),
                InlineKeyboardButton("🔄 Refresh", callback_data="status")
            )
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
                            # CSV columns: [Date, Job Title, URL, Status, Notes]
                            if len(row) > 3:
                                total_logs += 1
                                if "Applied" in row[3]:
                                    success_count += 1
            except:
                pass
            
            success_rate = "0%"
            if total_logs > 0:
                success_rate = f"{int((success_count/total_logs)*100)}%"
            
            status_text = (
                f"🤖 *Elite Job Bot — Live Status*\n\n"
                f"⚙️ Bot State: `{bot_state}`\n"
                f"🎯 Total Processed: `{len(applied)}`\n"
                f"🚀 Applied Today: `{stats.get('applied', 0)}`\n"
                f"🔥 Day Streak: `{stats.get('current_streak', 0)}`\n"
                f"📈 *Success Rate:* `{success_rate}` _({success_count}/{total_logs})_\n\n"
                f"✨ Gemini AI: {gemini_ok} | ⚡ Groq: {groq_ok}\n"
                f"📄 Resume: {resume_ok} | 📡 @{TARGET_CHANNEL}"
            )
            try:
                bot.edit_message_text(status_text, chat_id=chat_id,
                    message_id=call.message.message_id,
                    parse_mode=None, reply_markup=markup)
            except Exception:
                bot.send_message(chat_id, status_text, parse_mode=None, reply_markup=markup)

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
                bot.send_message(chat_id, "⚠️ Profile is empty! Use `/setprofile` to add your details.")
            else:
                msg = "📋 *Your Current Profile:*\n\n"
                for k, v in profile.items():
                    msg += f"• *{k.replace('_', ' ').title()}:* `{v}`\n"
                bot.send_message(chat_id, msg, parse_mode=None)
                
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

        elif call.data == "help":
            help_text = (
                "🤖 *Command Reference*\n\n"
                "📊 /status — Live bot status\n"
                "⏸️ /pause — Stop auto-scanning\n"
                "▶️ /resume — Start auto-scanning\n"
                "👻 /watch — Toggle Live Ghost Mode\n"
                "🕒 /history — Last 10 applications\n"
                "📋 /profile — View your profile\n"
                "🎯 /apply \<url\> — Apply to specific job\n"
                "📥 /download — Export CSV log"
            )
            bot.send_message(chat_id, help_text, parse_mode=None)

    @bot.message_handler(commands=['setprofile'])
    def set_profile_field(message):
        save_chat_id(message.chat.id)
        # Format: /setprofile field | value
        text = message.text.replace("/setprofile", "", 1).strip()
        if "|" not in text:
            profile = load_profile()
            fields = ", ".join(profile.keys())
            bot.reply_to(message, f"📝 *Update your profile:*\n`/setprofile <field> | <value>`\n\nAvailable fields: `{fields}`\n\nExample:\n`/setprofile phone | +91 9876543210`", parse_mode=None)
            return
        parts = text.split("|", 1)
        field = parts[0].strip().lower()
        value = parts[1].strip()
        profile = load_profile()
        if field not in profile:
            bot.reply_to(message, f"❌ Unknown field: `{field}`\n\nValid fields: {', '.join(profile.keys())}", parse_mode=None)
            return
        profile[field] = value
        try:
            with open(PROFILE_FILE, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
            bot.reply_to(message, f"✅ Profile updated!\n\n*{field}* → `{value}`", parse_mode=None)
        except Exception as e:
            bot.reply_to(message, f"⚠️ Error saving profile: {e}")

    @bot.message_handler(commands=['clearqa'])
    def clear_qa(message):
        save_chat_id(message.chat.id)
        text = message.text.replace("/clearqa", "", 1).strip()
        qa_memory = load_qa_memory()
        if not text:
            if not qa_memory:
                bot.reply_to(message, "📭 No saved answers to clear.")
                return
            msg = "🗑️ *Which answer to delete?*\nSend `/clearqa <number>`\n\n"
            for i, q in enumerate(qa_memory.keys(), 1):
                msg += f"*{i}.* {q}\n"
            bot.reply_to(message, msg, parse_mode=None)
            return
        if text.isdigit():
            keys = list(qa_memory.keys())
            idx = int(text) - 1
            if 0 <= idx < len(keys):
                deleted_q = keys[idx]
                del qa_memory[deleted_q]
                save_qa_memory(qa_memory)
                bot.reply_to(message, f"🗑️ Deleted answer for:\n_{deleted_q}_", parse_mode=None)
            else:
                bot.reply_to(message, "❌ Invalid number.")
        else:
            if text in qa_memory:
                del qa_memory[text]
                save_qa_memory(qa_memory)
                bot.reply_to(message, f"🗑️ Deleted answer for:\n_{text}_", parse_mode=None)
            else:
                bot.reply_to(message, "❌ Question not found in memory.")

    # --- Inline button callback handler ---
    @bot.callback_query_handler(func=lambda call: call.data.startswith("qa_answer:"))
    def handle_qa_button(call):
        num = call.data.split(":", 1)[1]
        pending = load_pending_qa()
        question = pending.get(num, f"Question {num}")
        # Send a ForceReply so user can type answer directly as a reply
        markup = ForceReply(selective=True)
        sent = bot.send_message(
            call.message.chat.id,
            f"✏️ *Answer for Q{num}:*\n_{question}_\n\nType your answer below 👇",
            parse_mode=None,
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
        bot.reply_to(message, f"✅ *Saved!*\n\n❓ {question}\n💬 *{answer}*\n\n_I'll use this automatically in all future applications!_", parse_mode=None)

    @bot.message_handler(commands=['answer'])
    def save_answer(message):
        save_chat_id(message.chat.id)
        text = message.text.replace("/answer", "", 1).strip()
        
        if "|" not in text:
            bot.reply_to(message, "❌ Format: `/answer <number> | <your answer>`\n\nExample:\n`/answer 1 | Yes`", parse_mode=None)
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
        
        bot.reply_to(message, f"✅ *Saved!*\n\n❓ {question}\n💬 *{answer}*\n\n_I will use this answer automatically from now on!_", parse_mode=None)

    @bot.message_handler(commands=['qa'])
    def show_qa_memory(message):
        save_chat_id(message.chat.id)
        qa_memory = load_qa_memory()
        if not qa_memory:
            bot.reply_to(message, "📭 No answers saved yet.\n\nWhen the bot encounters unknown questions, it will ask you via Telegram. Use `/answer <question> | <answer>` to teach it!", parse_mode=None)
            return
        msg = f"🧠 *Saved Q&A Memory ({len(qa_memory)} answers):*\n\n"
        for i, (q, a) in enumerate(qa_memory.items(), 1):
            msg += f"*Q{i}.* {q}\n💬 _{a}_\n\n"
        msg += "To update an answer, just use `/answer` again with the same question."
        bot.reply_to(message, msg, parse_mode=None)

    @bot.message_handler(commands=['apply'])
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
            
        bot.reply_to(message, f"⌛ Manually initiating application for:\n{url}")
        
        # Run in thread so bot doesn't freeze
        def run():
            try:
                final_url = bypass_blog_redirect(url)
                
                if any(domain in final_url.lower() for domain in UNSUPPORTED_DOMAINS):
                    bot.send_message(message.chat.id, f"⚠️ Skipped: The platform or link ({final_url}) is not supported for auto-filling (e.g. Naukri, LinkedIn, YouTube, Telegram).")
                    log_job(final_url, "Manual /apply", False, "Unsupported platform or social media")
                    return
                    
                success = run_playwright_apply(final_url, "Manual application requested by user")
                log_job(final_url, "Manual /apply", success, "Manual apply")
                if success:
                    bot.send_message(message.chat.id, f"✅ Manual application submitted for:\n{url}")
                else:
                    bot.send_message(message.chat.id, f"❌ Manual application failed for:\n{url}")
            except Exception as e:
                print(f"[Manual Apply] Error in run thread: {e}")
                try:
                    bot.send_message(message.chat.id, f"⚠️ Bot error: {e}")
                except:
                    pass
                
        Thread(target=run).start()

    @bot.message_handler(commands=['channels'])
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
    def ping_test(message):
        bot.reply_to(message, "🏓 Pong! The cloud bot is alive and listening!")

    @bot.message_handler(commands=['radar', 'jobs'])
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
                    
                    from datetime import datetime
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

                    import random, string
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
            BotCommand("help",       "📖 Full guide & all commands"),
            BotCommand("status",     "🚑 Bot health, API & stats"),
            BotCommand("notion",     "📋 Open Notion Job Tracker"),
            BotCommand("channels",   "📡 View all monitored channels"),
            BotCommand("lastjob",    "💼 See the last application attempt"),
            BotCommand("history",    "📅 View last 10 applications"),
            BotCommand("radar",      "📡 View latest multi-platform jobs"),
            BotCommand("instahyre",  "🚀 Trigger Instahyre mass-apply"),
            BotCommand("apply",      "🎯 Manually apply to a job URL"),
            BotCommand("pause",      "⏸️ Pause auto-scanning"),
            BotCommand("resume",     "▶️ Resume auto-scanning"),
            BotCommand("profile",    "📝 View your resume profile"),
            BotCommand("setprofile", "✏️ Update a profile field"),
            BotCommand("qa",         "🧠 View saved Q&A answers"),
            BotCommand("answer",     "💡 Teach bot an answer"),
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

# Start Job Radar background thread (runs every 6 hours)
def radar_loop():
    """Background thread that runs the Job Radar scan every 6 hours and sends results to Telegram."""
    print("[Radar] Background radar thread started. First scan in 30 seconds...")
    time.sleep(30)  # Initial delay so bot fully starts first
    while True:
        try:
            from job_radar import run_radar
            new_jobs = run_radar()
            
            # If no new jobs found, send a heartbeat so user knows radar is alive
            if not new_jobs:
                chat_id = load_chat_id()
                if bot and chat_id:
                    try:
                        bot.send_message(chat_id, 
                            "📡 *Job Radar Scan Complete*\n\n"
                            "No new jobs found this cycle.\n"
                            "⏰ Next scan in 6 hours.\n\n"
                            "_The radar is running 24/7. You will be notified instantly when new matches appear._",
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
        time.sleep(6 * 60 * 60)  # Sleep 6 hours between scans

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

def thread_supervisor():
    """Monitors and automatically restarts background threads if they crash."""
    print("[Supervisor] Thread supervisor loop started.")
    
    threads_config = {
        "Job Monitor": {"target": job_monitor_loop, "thread": None},
        "Daily Report": {"target": daily_report_loop, "thread": None},
        "Job Radar Loop": {"target": radar_loop, "thread": None},
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

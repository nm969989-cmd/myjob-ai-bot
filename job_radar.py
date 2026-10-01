"""
📡 JOB RADAR — Multi-Platform Job Finder (India & Tamil Nadu Priority Engine)
=============================================================================
Strictly filters for India-based jobs & Global Remote jobs open to India.
Prioritizes Tamil Nadu (Chennai, Coimbatore, Madurai, Trichy, Salem, etc.) at the top.
Deeply scrapes all major Telegram job channels and extracts direct apply links.
"""

import os
import sys
import json
import time
import random
import re
import urllib.parse
from datetime import datetime
import requests
from dotenv import load_dotenv
import functools
import html

try:
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
except Exception:
    InlineKeyboardMarkup = None
    InlineKeyboardButton = None

from bot_optimizer import (
    extract_job_salary,
    extract_hr_email,
    extract_eligible_batch,
    extract_experience_level,
    format_eligibility_badge,
    _clean_str,
    _safe_amount,
)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# override=False: a real environment variable (CI secret) must always win over a
# stray local .env file, otherwise a developer's checkout silently shadows prod.
load_dotenv(override=False)

# ──────────────────────────────────────────────────
# 🎯  FILTER & LOCATION CONFIGURATION
# ──────────────────────────────────────────────────

RADAR_KEYWORDS = [
    # Software / Engineering / Trainee
    "Software Developer", "Software Engineer", "Junior Software Engineer",
    "Graduate Engineer Trainee", "GET", "Software Development Engineer", "SDE", "SDE-1", "SDE 1",
    "Associate Developer", "Associate Software Engineer", "Systems Engineer Trainee",
    "Programmer Analyst", "Trainee Engineer", "Engineer Trainee", "Junior Developer",
    # Frontend / UI / Web
    "Frontend Developer", "Front End Developer", "React Developer", "Web Developer",
    "Application Developer", "UI Engineer", "UI/UX Designer", "Product Designer",
    # Backend / Full-Stack
    "Backend Developer", "Back End Developer", "Full-Stack Developer", "Full Stack Developer",
    "Full Stack", "Java Developer", "Java Engineer", "Spring Boot", "Python Developer",
    "Node", "Node.js Developer", "Angular", "Vue", "Oracle APEX Developer",
    # Data / AI / Cloud
    "Data Analyst", "Data Engineer", "AI Engineer", "Machine Learning", "DevOps Engineer",
    "Cloud Engineer", "QA Engineer", "Software Test Engineer", "Quality Analyst",
    # Operations / Support / Fresher Non-Tech Roles
    "Customer Success", "Customer Support", "Technical Support", "Operations Associate",
    # Batch Specifics
    "2024 Batch", "2025 Batch", "2026 Batch", "Fresher", "Freshers", "0-1 Year", "0-2 Years",
    "Off Campus", "Campus Hiring", "Entry Level",
]

TAMIL_NADU_LOCATIONS = [
    "chennai", "coimbatore", "madurai", "tiruchirappalli", "trichy", "salem",
    "tirunelveli", "vellore", "erode", "tiruppur", "tiruvannamalai", "hosur",
    "thanjavur", "dindigul", "kanchipuram", "nagercoil", "tuticorin", "thoothukudi",
    "karur", "cuddalore", "neyveli", "kumbakonam", "sivakasi", "ranipet",
    "tamil nadu", "tamilnadu", "tn",
]

INDIA_OTHER_LOCATIONS = [
    "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "delhi", "new delhi",
    "noida", "gurgaon", "gurugram", "kolkata", "ahmedabad", "kochi", "cochin",
    "trivandrum", "thiruvananthapuram", "chandigarh", "jaipur", "indore", "bhubaneswar",
    "mysuru", "mysore", "nagpur", "visakhapatnam", "vizag", "pan india", "india",
]

EXCLUDED_FOREIGN_LOCATIONS = [
    "usa", "united states", "us", "uk", "united kingdom", "london", "germany",
    "berlin", "munich", "canada", "toronto", "vancouver", "australia", "sydney",
    "melbourne", "singapore", "netherlands", "amsterdam", "france", "paris",
    "europe", "emea", "latam", "california", "new york", "texas", "seattle",
    "austin", "san francisco", "boston", "ireland", "dublin", "poland", "sweden",
    "switzerland", "brazil", "spain", "italy", "japan", "tokyo", "philippines",
    "new zealand", "dubai", "uae", "mexico",
]

EXCLUDED_REMOTE_RESTRICTIONS = [
    "us only", "usa only", "uk only", "europe only", "eu only", "north america only",
    "canada only", "latam only", "apac only (excluding india)", "us/canada only",
]

# Only show jobs from 2025 onwards
FILTER_YEAR = 2025

# ⚡ Pre-compiled high-performance regular expressions for O(1) matching
_RADAR_KW_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(kw) for kw in sorted(RADAR_KEYWORDS, key=len, reverse=True)) + r')\b', re.IGNORECASE)
_FOREIGN_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(f) for f in sorted(EXCLUDED_FOREIGN_LOCATIONS, key=len, reverse=True)) + r')\b', re.IGNORECASE)
_REMOTE_RESTRICTIONS_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(r) for r in sorted(EXCLUDED_REMOTE_RESTRICTIONS, key=len, reverse=True)) + r')\b', re.IGNORECASE)
_TN_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(tn) for tn in sorted(TAMIL_NADU_LOCATIONS, key=len, reverse=True) if tn.lower() != 'tn') + r')\b', re.IGNORECASE)
# "TN" on its own is ambiguous: it is the ISO code for Tamil Nadu but also the US
# postal abbreviation for Tennessee ("Memphis, TN", "Knoxville, TN"). Only treat a
# bare "TN" as Tamil Nadu when the string also signals India.
_TN_BARE_REGEX = re.compile(r'(?:^|[\s,(/])tn(?:$|[\s,)/])', re.IGNORECASE)
_INDIA_HINT_REGEX = re.compile(r'\b(?:india|indian|in\b|bangalore|bengaluru|hyderabad|pune|mumbai|delhi|chennai|coimbatore|madurai|trichy|trichy|hosur|salem|tamil nadu)\b', re.IGNORECASE)
_INDIA_REGEX = re.compile(r'\b(?:' + '|'.join(re.escape(i) for i in sorted(INDIA_OTHER_LOCATIONS, key=len, reverse=True)) + r')\b', re.IGNORECASE)
_REMOTE_KW_REGEX = re.compile(r'\b(?:remote|work from home|wfh|worldwide|global|anywhere|telecommute)\b', re.IGNORECASE)

TRACKING_KEYS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "campaign", "trk", "trkinfo",
    "affiliate", "sub_id"
})

# Max jobs per individual source
MAX_PER_SOURCE = 35

# Memory and tracking files
SEEN_JOBS_FILE = "radar_seen_jobs.txt"
RESULTS_JSON   = "radar_results.json"

# ──────────────────────────────────────────────────
# 📡 COMPREHENSIVE TELEGRAM CHANNELS DATABASE
# ──────────────────────────────────────────────────

RADAR_TELEGRAM_CHANNELS = [
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

# ──────────────────────────────────────────────────
# 🥷  STEALTH ENGINE & HELPERS
# ──────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

_RADAR_SESSION = None

def _get_radar_session():
    global _RADAR_SESSION
    if _RADAR_SESSION is None:
        from requests.adapters import HTTPAdapter
        s = requests.Session()
        adapter = HTTPAdapter(pool_connections=15, pool_maxsize=30, max_retries=1)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        _RADAR_SESSION = s
    return _RADAR_SESSION

def _api_request(url, headers_extra=None, max_retries=2, timeout=20):
    """Robust HTTP request helper with persistent connection pooling."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html, */*",
        "Accept-Encoding": "identity",
    }
    if headers_extra:
        headers.update(headers_extra)
    session = _get_radar_session()
    for attempt in range(max_retries):
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code in [429, 503]:
                time.sleep(3 * (attempt + 1))
                continue
        except Exception:
            time.sleep(2)
    return None

def clean_html(raw_html):
    if not raw_html:
        return ""
    clean_text = re.sub(r'<[^>]+>', '', raw_html)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text[:160] + "..." if len(clean_text) > 160 else clean_text

def escape_md(text):
    if not text:
        return ""
    return str(text).replace("*", "").replace("_", " ").replace("[", "(").replace("]", ")").replace("`", "")

def safe_date_timestamp(date_val):
    """
    Safely converts any date representation (YYYY-MM-DD, ISO string, RFC 2822, 
    unix timestamp, or datetime object) into a POSIX timestamp (float).
    Always returns a float >= 0.0, never raises exceptions, and never yields year 0.
    """
    if not date_val:
        return 0.0
    if isinstance(date_val, (int, float)):
        try:
            val = float(date_val)
            if 0.0 <= val <= 2500000000.0:
                return val
        except Exception:
            return 0.0

    s = str(date_val).strip()
    if not s or s.lower() in ("none", "null", "unknown", "nan", "recently"):
        return 0.0

    # 1. Try ISO date substring YYYY-MM-DD
    iso_m = re.search(r'\b(20\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b', s)
    if iso_m:
        try:
            y, m, d = int(iso_m.group(1)), int(iso_m.group(2)), int(iso_m.group(3))
            dt = datetime(y, m, d)
            return dt.timestamp()
        except Exception:
            pass

    # 2. Try unix timestamp string (e.g. "1727632800")
    if s.isdigit() and len(s) in (10, 13):
        try:
            ts = float(s)
            if len(s) == 13:
                ts /= 1000.0
            if 0.0 <= ts <= 2500000000.0:
                return ts
        except Exception:
            pass

    # 3. Try standard strptime formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%a, %d %b %Y %H:%M:%S %z", "%d %b %Y"):
        try:
            dt = datetime.strptime(s[:25].strip(), fmt)
            if 1970 <= dt.year <= 2100:
                return dt.timestamp()
        except Exception:
            continue

    return 0.0

@functools.lru_cache(maxsize=8192)
def normalize_job_url(url):
    """
    Normalizes a job URL by removing tracking parameters (UTM, ref, fbclid),
    anchors, and trailing slashes for rock-solid deduplication across channels.
    Cached via LRU cache for instant O(1) deduplication.
    """
    if not url or not isinstance(url, str):
        return ""
    try:
        url_str = url.strip()
        if not url_str.startswith("http"):
            return url_str
        parsed = urllib.parse.urlparse(url_str)
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
        cleaned_pairs = [(k, v) for k, v in query_pairs if k.lower() not in TRACKING_KEYS]
        new_query = urllib.parse.urlencode(cleaned_pairs)
        cleaned = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            new_query,
            ""
        ))
        return cleaned or url_str
    except Exception:
        return url

_SEEN_JOBS_CACHE = None
_SEEN_JOBS_MTIME = 0

def load_seen_jobs():
    global _SEEN_JOBS_CACHE, _SEEN_JOBS_MTIME
    current_mtime = os.path.getmtime(SEEN_JOBS_FILE) if os.path.exists(SEEN_JOBS_FILE) else 0
    if _SEEN_JOBS_CACHE is not None and current_mtime == _SEEN_JOBS_MTIME:
        return _SEEN_JOBS_CACHE.copy()

    seen = set()
    if os.path.exists(SEEN_JOBS_FILE):
        try:
            with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
                for line in f.read().splitlines():
                    clean_l = line.strip()
                    if clean_l:
                        seen.add(clean_l)
                        norm = normalize_job_url(clean_l)
                        if norm:
                            seen.add(norm)
        except Exception:
            pass
    _SEEN_JOBS_CACHE = seen
    _SEEN_JOBS_MTIME = current_mtime
    return _SEEN_JOBS_CACHE.copy()

def mark_seen(link):
    global _SEEN_JOBS_CACHE, _SEEN_JOBS_MTIME
    norm = normalize_job_url(link)
    clean_link = link.strip()
    try:
        with open(SEEN_JOBS_FILE, "a", encoding="utf-8") as f:
            f.write(clean_link + "\n")
            if norm and norm != clean_link:
                f.write(norm + "\n")
    except Exception:
        pass
    if _SEEN_JOBS_CACHE is not None:
        _SEEN_JOBS_CACHE.add(clean_link)
        if norm:
            _SEEN_JOBS_CACHE.add(norm)
        _SEEN_JOBS_MTIME = os.path.getmtime(SEEN_JOBS_FILE) if os.path.exists(SEEN_JOBS_FILE) else time.time()

def save_results(jobs):
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(jobs),
            "jobs": jobs
        }, f, indent=2, ensure_ascii=False)

def _keyword_match(text):
    if not text:
        return False
    return bool(_RADAR_KW_REGEX.search(text))

# ──────────────────────────────────────────────────
# 📍 STRICT LOCATION CLASSIFIER & TAMIL NADU PRIORITIZER
# ──────────────────────────────────────────────────

def classify_location(location_str, context_text=""):
    """
    Evaluates a location string and surrounding text context with pre-compiled regexes.
    Returns: (is_valid, priority_tier, formatted_location_string, is_tamil_nadu)
      - Priority 1: Tamil Nadu (Chennai, Coimbatore, Madurai, Trichy, Salem, etc.)
      - Priority 2: Other India (Bangalore, Hyderabad, Pune, Mumbai, Delhi, PAN India)
      - Priority 3: Remote (India / Worldwide open)
      - Rejected: Outside India (USA, UK, London, Europe, etc.) -> (False, 99, "", False)
    """
    loc_clean = str(location_str or "").strip()
    loc_lower = loc_clean.lower()
    ctx_lower = str(context_text or "").lower()
    combined = f"{loc_lower} {ctx_lower}"

    # 1. Check for explicit foreign exclusion
    if _FOREIGN_REGEX.search(loc_lower):
        if not ("india" in loc_lower or _TN_REGEX.search(loc_lower)):
            return False, 99, "", False

    # Check for remote restrictions (e.g., "US Only")
    if _REMOTE_RESTRICTIONS_REGEX.search(combined):
        return False, 99, "", False

    # 2. Check for Tamil Nadu (Highest Priority — Tier 1)
    tn_match = _TN_REGEX.search(loc_lower) or _TN_REGEX.search(ctx_lower)
    matched_kw = tn_match.group(0).lower() if tn_match else ""
    if not tn_match and _TN_BARE_REGEX.search(loc_lower) and _INDIA_HINT_REGEX.search(combined):
        tn_match = True
        matched_kw = "tn"
    if tn_match:
        matched_name = matched_kw.title() if matched_kw not in ["tn", "tamilnadu"] else "Tamil Nadu"
        if loc_clean and loc_clean.lower() != "india" and not _FOREIGN_REGEX.search(loc_lower):
            display = f"{loc_clean} ⭐"
        else:
            display = f"{matched_name}, Tamil Nadu ⭐"
        return True, 1, display, True

    # 3. Check for Other India Tech Hubs (Tier 2)
    in_match = _INDIA_REGEX.search(loc_lower) or _INDIA_REGEX.search(ctx_lower)
    if in_match:
        display = loc_clean if loc_clean else f"{in_match.group(0).title()}, India"
        if "india" not in display.lower():
            display += ", India 🇮🇳"
        return True, 2, display, False

    # 4. Check for Remote / Work from Home / Worldwide
    if _REMOTE_KW_REGEX.search(loc_lower):
        return True, 3, "Remote (India / Global) 🌐", False

    # If location field is empty or says "India", accept as Tier 2
    if not loc_clean or loc_lower in ["in", "ind", "india", "pan india"]:
        return True, 2, "India (PAN India) 🇮🇳", False

    # Otherwise, reject unknown or foreign location
    return False, 99, "", False

def tn_live_apply_url(record: dict) -> str:
    """Extract the apply URL from a tn-live-jobs record, tolerating schema drift.

    The Node engine emits `apply_url`; earlier Python readers expected `url`.
    Falling back across both means a schema change degrades to "no data" loudly
    rather than silently ingesting zero jobs while reporting success.
    """
    for key in ("apply_url", "url", "job_url", "job_url_direct", "link"):
        value = _clean_str(record.get(key))
        if value.startswith(("http://", "https://")):
            return value
    return ""


def tn_live_posted_at(record: dict) -> str:
    """Return an ISO date from whichever timestamp field the record carries."""
    for key in ("posted_at", "date_posted", "created_at", "published_at"):
        value = _clean_str(record.get(key))
        if not value:
            continue
        head = value.split("T")[0].split(" ")[0]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", head):
            return head
    return ""


def tn_live_description(record: dict) -> str:
    """Best-effort description across known field names."""
    for key in ("description", "summary", "text", "snippet"):
        value = _clean_str(record.get(key))
        if value:
            return value
    return _clean_str(record.get("title"))


def tn_live_salary(record: dict) -> str:
    """Return a salary string, dropping the obvious junk the scraper emitted."""
    for key in ("salary", "salary_raw", "salary_text"):
        value = _clean_str(record.get(key))
        if not value:
            continue
        # tn-live-jobs has emitted values like "RS22" for unparsed postings.
        if re.fullmatch(r"[A-Za-z]{1,4}\d{1,4}", value):
            continue
        if re.search(r"\d{3}", value):
            return value
    return ""


def _make_job(title, company, link, location, source, date_posted="", description="", priority_tier=2, is_tn=False, direct_link="", salary="", hr_email="", batch="", experience=""):
    if not date_posted:
        date_posted = datetime.now().strftime("%Y-%m-%d")

    # Smart auto-extraction if not explicitly provided
    if not salary and description:
        try:
            salary = extract_job_salary(description)
        except Exception:
            pass
    if not hr_email and description:
        try:
            hr_email = extract_hr_email(description)
        except Exception:
            pass
    if not batch:
        try:
            batch = extract_eligible_batch(f"{title} {description}")
        except Exception:
            pass
    if not experience:
        try:
            experience = extract_experience_level(f"{title} {description}")
        except Exception:
            pass
    badge = format_eligibility_badge(batch, experience)

    return {
        "title":              title.strip(),
        "company":            company.strip(),
        "link":               direct_link.strip() if direct_link else link.strip(),
        "raw_link":           link.strip(),
        "location":           location.strip(),
        "source":             source,
        "date_posted":        date_posted,
        "description":        description.strip(),
        "priority_tier":      priority_tier,
        "is_tamil_nadu":      is_tn,
        "salary":             salary.strip() if salary else "",
        "hr_email":           hr_email.strip() if hr_email else "",
        "batch":              batch.strip() if batch else "",
        "experience":         experience.strip() if experience else "",
        "eligibility_badge":  badge,
        "found_at":           datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

def is_social_or_promo_link(url):
    """Detects if a URL is a social media link, channel promo, parked domain, or non-job page."""
    if not url or not isinstance(url, str):
        return True
    u = url.lower().strip()
    promo_domains = [
        "t.me", "telegram.org", "telegram.dog", "whatsapp.com", "wa.me",
        "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com",
        "youtube.com", "youtu.be", "pinterest.com", "threads.net",
        "linktr.ee", "bio.link", "campsite.bio", "taplink.cc", "beacons.ai",
        "play.google.com", "apps.apple.com", "aratt.ai",
        # Social sharing / blog widgets
        "addtoany.com", "addthis.com", "sharethis.com", "disqus.com", "gravatar.com",
        "blogger.com", "feedburner.com", "wordpress.com", "w3.org",
        # Expired / Parked / Squatter domains
        "hugedomains.com", "sedo.com", "godaddy.com", "dan.com", "afternic.com",
        "namecheap.com", "domainmarket.com", "parklogic.com", "parkingcrew.com",
        "bodis.com", "above.com", "domainagents.com", "undeveloped.com",
        "buydomains.com", "domain_profile.cfm", "domainforbuy"
    ]
    if any(d in u for d in promo_domains):
        return True
    if "linkedin.com" in u:
        if any(p in u for p in ["/company/", "/in/", "/feed/", "/posts/", "/groups/", "/pulse/", "/school/"]):
            return True
    return False

# ──────────────────────────────────────────────────
# 🔗 DIRECT LINK UNWRAPPER FOR RADAR (MULTI-HOP ENGINE)
# ──────────────────────────────────────────────────

def unwrap_radar_direct_link(url):
    """
    Unwraps URL shorteners, follows redirects, decodes Base64 params,
    and extracts direct application links from job blogs & aggregators.
    """
    if not url or not url.startswith("http") or is_social_or_promo_link(url):
        return url
    
    direct_ats_domains = [
        "greenhouse.io", "lever.co", "myworkdayjobs.com", "workdayjobs.com",
        "smartrecruiters.com", "joinsuperset.com", "docs.google.com/forms",
        "forms.gle", "sensehq.com", "ashbyhq.com", "bamboohr.com", "taleo.net",
        "zohorecruit.com", "recruitee.com", "freshteam.com", "darwinbox.com",
        "keka.com", "unstop.com", "internshala.com", "foundit.in", "naukri.com",
        "rippling-ats.com", "breezy.hr", "workable.com"
    ]

    # Fast-path: Already a verified ATS or direct portal
    if any(d in url.lower() for d in direct_ats_domains):
        return normalize_job_url(url)

    # Base64 quick unpack in query params
    current_url = url.strip()
    try:
        parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(current_url).query)
        for param in ["url", "target", "link", "redirect", "dest", "destination", "u"]:
            if param in parsed_q:
                val = parsed_q[param][0]
                if val.startswith("http"):
                    current_url = val
                    break
                elif len(val) > 20 and " " not in val:
                    try:
                        import base64
                        decoded = base64.b64decode(val.encode()).decode("utf-8", errors="ignore")
                        if decoded.startswith("http"):
                            current_url = decoded
                            break
                    except Exception:
                        pass
    except Exception:
        pass

    if any(d in current_url.lower() for d in direct_ats_domains):
        return normalize_job_url(current_url)

    # Fast redirect resolution (single request with allow_redirects)
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        resp = requests.get(current_url, headers=headers, timeout=3.0, allow_redirects=True)
        if resp and resp.url:
            final_url = resp.url
            if any(d in final_url.lower() for d in direct_ats_domains):
                return normalize_job_url(final_url)
            
            # Check meta refresh
            meta_m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\']\d+;\s*url=([^"\']+)["\']', resp.text[:4000], re.I)
            if meta_m:
                redir = meta_m.group(1).strip()
                if redir.startswith("http"):
                    return normalize_job_url(redir)

            # Check DOM for ATS links (first 50KB)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text[:50000], "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if any(d in href.lower() for d in direct_ats_domains) and not is_social_or_promo_link(href):
                    return normalize_job_url(href)
            
            return normalize_job_url(final_url)
    except Exception:
        pass

    return normalize_job_url(current_url)

def _scan_single_channel_radar(ch, max_jobs=2):
    """Scrapes a single Telegram channel for the Job Radar."""
    ch_clean = ch.replace("@", "").strip()
    url = f"https://telegram.dog/s/{ch_clean}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if not resp or resp.status_code != 200:
            return []
    except Exception:
        return []

    jobs_found = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message_text")
        if not messages:
            return []

        for msg in reversed(messages[-5:]):
            text = msg.get_text(separator=" ").strip()
            if not text or len(text) < 30:
                continue

            if not _keyword_match(text):
                continue

            is_valid_loc, tier, loc_tag, is_tn = classify_location("", text)
            if not is_valid_loc:
                continue

            urls = []
            for a in msg.find_all("a", href=True):
                href = a["href"].strip()
                if href.startswith("http") and not is_social_or_promo_link(href):
                    urls.append(href)
            if not urls:
                regex_urls = re.findall(r'(https?://[^\s<>"]+)', text)
                for u in regex_urls:
                    u = u.rstrip(").,!*'\"")
                    if not is_social_or_promo_link(u):
                        urls.append(u)

            if not urls:
                continue

            raw_link = urls[0]
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            first_line = lines[0] if lines else ""

            # Robust Multi-Line Company Extraction
            company = ""
            invalid_companies = {
                "bit", "bitly", "tinyurl", "cutt", "tco", "rbgy", "shorturl", "linktr", "biolink",
                "verified recruiter", "hiring", "job", "jobs", "apply", "opening", "openings",
                "hugedomains", "godaddy", "sedo", "dan", "afternic", "domain", "admin", "unknown",
                "addtoany", "addthis", "sharethis", "blogger", "wordpress", "disqus", "telegram",
                "telegram.org", "telegram.dog", "freshershunt", "foundthejob", "jobopenings",
                "jobopenings_india", "tech_jobs_india", "indiawalkinjobs", "walkinjobs", "meganaukri",
                "dailyjobalerts", "sarkariprep", "freejobalert", "freshersvoice", "naukriauto",
                "jobalertshub", "placementdrive", "allindiajobs", "jobskull", "kickcharm", "offcampusjobs4u"
            }

            company_patterns = [
                r'(?:🏢\s*Company|Company|Organisation|Org|Organization|Employer)\s*[:\-–]\s*([^\n📍💼🛠️💰📝👉🔗|]+)',
                r'(?:hiring|recruiting)\s+(?:at|for|by)\s+([A-Za-z0-9\s&.,\'\-]+)',
                r'^[^\w\s]*\s*([A-Za-z0-9\s.,&-]+?)\s+(?:is\s+Hiring|is\s+Recruiting|Recruitment\s+20\d\d|Recruitment|Off\s*Campus\s+Drive|Off\s*Campus|Mega\s+Drive|Drive|Hiring|Walkin|Walk-in)'
            ]
            for pat in company_patterns:
                m = re.search(pat, text, re.I)
                if m:
                    cand = m.group(1).strip()
                    cand_clean = re.sub(r'[^\w\s.,&-]', '', cand).replace('Title', '').replace(':', '').strip()
                    if cand_clean and len(cand_clean) >= 2 and cand_clean.lower() not in invalid_companies:
                        company = cand_clean
                        break

            if not company or len(company) < 2 or company.lower() in invalid_companies:
                company = "Verified Tech Recruiter"

            # Robust Role Extraction
            role = ""
            role_m = re.search(r'(?:(?:🚀\s*)?Hiring\s+Now|Role|Position|Job\s*Title|Profile|Post|Designation)\s*[:\-]\s*([^\n🏢📍💼🛠️💰📝👉🔗|]+)', text, re.I)
            if role_m:
                role = role_m.group(1).strip()
            if not role or len(role) < 2:
                if "is Hiring" in first_line:
                    after_hiring = first_line.split("is Hiring")[-1].strip()
                    after_hiring = re.sub(r'[^\w\s.,&-]', '', after_hiring).strip()
                    if len(after_hiring) > 3:
                        role = after_hiring
            role = re.sub(r'^[▪️👉•\-:\s]+', '', role).strip()
            role = re.sub(r'[^\w\s.,&/\(\)\-]', '', role).strip()
            if not role or len(role) < 2:
                role = "Software Developer / Engineer Trainee"

            # Strict Non-Engineering / BPO / Medical Billing Filter
            non_eng_keywords = [
                "medical billing", "medical coder", "medical coding", "bpo", "telecaller", "telecalling",
                "data entry", "voice process", "non-voice", "non voice", "customer care", "customer support executive",
                "telesales", "insurance agent", "sales executive", "front desk", "receptionist", "security guard",
                "delivery boy", "delivery partner", "pharma sales", "retail sales"
            ]
            if any(k in role.lower() for k in non_eng_keywords):
                continue

            direct_link = unwrap_radar_direct_link(raw_link)
            if is_social_or_promo_link(direct_link):
                continue

            desc = clean_html(text)[:200]
            src_name = f"Telegram @{ch_clean} 📢"
            if is_tn:
                src_name = f"Telegram @{ch_clean} 🌟"

            sal = extract_job_salary(text)
            hr_em = extract_hr_email(text)

            jobs_found.append(_make_job(
                title=role[:65],
                company=company[:45],
                link=direct_link,
                location=loc_tag,
                source=src_name,
                description=desc,
                priority_tier=tier,
                is_tn=is_tn,
                direct_link=direct_link,
                salary=sal,
                hr_email=hr_em
            ))
            if len(jobs_found) >= max_jobs:
                break

    except Exception:
        pass
    return jobs_found

# ──────────────────────────────────────────────────
# 📢 SCRAPER 1 — Telegram Channels Radar (45+ Channels)
# ──────────────────────────────────────────────────

def scrape_telegram_channels_radar():
    """Scrapes all public Telegram job channels concurrently and extracts verified Indian tech fresher jobs."""
    print("[Radar] Scanning 45+ Telegram Channels concurrently for India & Tamil Nadu Jobs...")
    all_channel_jobs = []
    seen_links = set()

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        future_to_ch = {executor.submit(_scan_single_channel_radar, ch): ch for ch in RADAR_TELEGRAM_CHANNELS}
        try:
            for future in concurrent.futures.as_completed(future_to_ch, timeout=25):
                try:
                    res = future.result()
                    if res:
                        for job in res:
                            lnk = job.get("link") or job.get("raw_link")
                            if lnk and lnk not in seen_links:
                                seen_links.add(lnk)
                                all_channel_jobs.append(job)
                except Exception:
                    pass
        except concurrent.futures.TimeoutError:
            print("  [Telegram Radar] Channel scan timeout reached. Continuing.")

    print(f"  [Telegram Radar] Found {len(all_channel_jobs)} India/TN jobs across channels.")
    return all_channel_jobs

# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 2 — Adzuna India (Tamil Nadu & India Tech)
# ──────────────────────────────────────────────────

def scrape_adzuna_india():
    """Queries Adzuna India API with focus on Tamil Nadu and India tech roles."""
    print("[Radar] Scanning Adzuna India (Tamil Nadu & Tech)...")
    jobs_found = []

    app_id  = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")

    if not app_id or not app_key:
        print("  [Adzuna] Skipped — set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env")
        return []

    queries = [
        ("software engineer", "Tamil Nadu"),
        ("frontend developer", "Chennai"),
        ("python developer", "Coimbatore"),
        ("full stack developer", "India"),
    ]

    for kw, where in queries:
        try:
            url = (
                f"https://api.adzuna.com/v1/api/jobs/in/search/1"
                f"?app_id={app_id}&app_key={app_key}"
                f"&what={urllib.parse.quote(kw)}&where={urllib.parse.quote(where)}"
                f"&results_per_page=20&content-type=application/json"
                f"&sort_by=date"
            )
            resp = _api_request(url)
            if not resp:
                continue

            data = resp.json()
            for job in data.get("results", []):
                title   = job.get("title", "")
                company = job.get("company", {}).get("display_name", "Unknown")
                link    = job.get("redirect_url", "")
                raw_loc = job.get("location", {}).get("display_name", where)
                full_created = str(job.get("created", "2025-01-01T"))

                if not link or not _keyword_match(title):
                    continue

                is_valid, tier, loc_tag, is_tn = classify_location(raw_loc, where)
                if not is_valid:
                    continue

                desc = clean_html(job.get("description", ""))
                sal_min = job.get("salary_min")
                sal_max = job.get("salary_max")
                adzuna_sal = ""
                if sal_min and sal_max:
                    adzuna_sal = f"₹{int(sal_min):,} - ₹{int(sal_max):,}"
                elif sal_min:
                    adzuna_sal = f"₹{int(sal_min):,}+"

                jobs_found.append(_make_job(
                    title=title, company=company, link=link, location=loc_tag,
                    source="Adzuna India 🇮🇳", date_posted=full_created[:10],
                    description=desc, priority_tier=tier, is_tn=is_tn,
                    salary=adzuna_sal
                ))
                if len(jobs_found) >= MAX_PER_SOURCE:
                    break

        except Exception as e:
            print(f"  [Adzuna] Error for '{kw}': {e}")
        time.sleep(2.0)

    print(f"  [Adzuna India] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 3 — Unstop (India Campus & Fresher Hiring)
# ──────────────────────────────────────────────────

def scrape_unstop():
    """Queries Unstop public job listings API for Indian fresher campus roles."""
    print("[Radar] Scanning Unstop India...")
    jobs_found = []
    try:
        url = "https://unstop.com/api/public/opportunity/search-result?opportunity=jobs&per_page=30&oppstatus=open"
        resp = _api_request(url)
        if not resp:
            return []
        data = resp.json()
        items = (data.get("data", {}).get("data", []) if isinstance(data.get("data"), dict) else data.get("data", []))
        for job in items:
            title   = job.get("title", "")
            org     = job.get("organisation", {})
            company = org.get("name", "Unknown") if isinstance(org, dict) else "Unknown"
            slug    = job.get("public_url", "") or job.get("slug", "")
            link    = slug if slug.startswith("http") else f"https://unstop.com/{slug}"
            raw_loc = job.get("job_location", "") or "India"

            if not title or not slug or not _keyword_match(title):
                continue

            is_valid, tier, loc_tag, is_tn = classify_location(raw_loc, title)
            if not is_valid:
                continue

            desc = clean_html(job.get("description", ""))
            jobs_found.append(_make_job(
                title=title, company=company, link=link, location=loc_tag,
                source="Unstop India 🏆", description=desc, priority_tier=tier, is_tn=is_tn
            ))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"  [Unstop] Error: {e}")
    print(f"  [Unstop] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 4 — Foundit India (Monster India API)
# ──────────────────────────────────────────────────

def scrape_foundit():
    """Queries Foundit India for fresher software roles in Tamil Nadu & India."""
    print("[Radar] Scanning Foundit India...")
    jobs_found = []
    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.foundit.in/",
            "Origin": "https://www.foundit.in",
        }
        url = "https://www.foundit.in/middleware/jobsearch/v2/search?query=software+engineer+fresher&location=Tamil+Nadu&experience=0-1&limit=25&sort=1"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []

        data = resp.json()
        items = data.get("jobSearchResponse", {}).get("data", []) or data.get("data", [])
        for job in items:
            title    = job.get("designation", "") or job.get("title", "")
            company  = job.get("companyName", "Unknown")
            link     = job.get("jdURL", "") or job.get("applyUrl", "")
            raw_loc  = job.get("location", "Tamil Nadu, India")

            if not title or not link or not _keyword_match(title):
                continue

            full_link = link if link.startswith("http") else "https://www.foundit.in" + link
            is_valid, tier, loc_tag, is_tn = classify_location(raw_loc, title)
            if not is_valid:
                continue

            desc = clean_html(job.get("description", job.get("jobDescription", "")))
            jobs_found.append(_make_job(
                title=title, company=company, link=full_link, location=loc_tag,
                source="Foundit India 🔍", description=desc, priority_tier=tier, is_tn=is_tn
            ))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"  [Foundit] Error: {e}")
    print(f"  [Foundit] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🌐  SCRAPER 5 — Remotive API (Strict India & Worldwide Remote Only)
# ──────────────────────────────────────────────────

def scrape_remotive():
    """Queries Remotive API — strictly filtering for India & unrestricted Worldwide Remote."""
    print("[Radar] Scanning Remotive (India/Global Remote)...")
    jobs_found = []

    for kw in ["software engineer", "frontend developer", "python developer"]:
        try:
            url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(kw)}&limit=20"
            resp = _api_request(url)
            if not resp:
                continue
            data = resp.json()
            for job in data.get("jobs", []):
                title     = job.get("title", "")
                company   = job.get("company_name", "Unknown")
                link      = job.get("url", "")
                geo       = job.get("candidate_required_location", "")
                full_date = str(job.get("publication_date", "2025-01-01T"))
                tags      = " ".join(job.get("tags", []))

                if not link or not _keyword_match(title + " " + tags):
                    continue

                is_valid, tier, loc_tag, is_tn = classify_location(geo, title + " " + tags)
                if not is_valid:
                    continue

                desc = clean_html(job.get("description", ""))
                rem_sal = str(job.get("salary", "")).strip()
                jobs_found.append(_make_job(
                    title=title, company=company, link=link, location=loc_tag,
                    source="Remotive 🚀", date_posted=full_date[:10],
                    description=desc, priority_tier=tier, is_tn=is_tn,
                    salary=rem_sal
                ))
                if len(jobs_found) >= MAX_PER_SOURCE:
                    break
        except Exception as e:
            print(f"  [Remotive] Error: {e}")
        time.sleep(1.5)

    print(f"  [Remotive] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🌐  SCRAPER 6 — Jobicy API (Strict India & Worldwide Remote Only)
# ──────────────────────────────────────────────────

def scrape_jobicy():
    """Queries Jobicy API — strictly filtering for India & unrestricted Worldwide Remote."""
    print("[Radar] Scanning Jobicy (India/Global Remote)...")
    jobs_found = []
    try:
        url = "https://jobicy.com/api/v2/remote-jobs?count=40&industry=engineering"
        resp = _api_request(url)
        if not resp:
            return []
        data = resp.json()
        for job in data.get("jobs", []):
            title     = job.get("jobTitle", "")
            company   = job.get("companyName", "Unknown")
            link      = job.get("url", "")
            geo       = job.get("jobGeo", "")
            full_date = str(job.get("pubDate", "2025-01-01T"))
            tags      = " ".join(job.get("jobIndustry", []))

            if not link or not _keyword_match(title + " " + tags):
                continue

            is_valid, tier, loc_tag, is_tn = classify_location(geo, title)
            if not is_valid:
                continue

            desc = clean_html(job.get("jobDescription", job.get("description", "")))
            j_min = job.get("annualSalaryMin")
            j_max = job.get("annualSalaryMax")
            j_cur = job.get("salaryCurrency", "USD")
            j_sal = f"{j_min} - {j_max} {j_cur}" if j_min and j_max else ""
            jobs_found.append(_make_job(
                title=title, company=company, link=link, location=loc_tag,
                source="Jobicy 💼", date_posted=full_date[:10],
                description=desc, priority_tier=tier, is_tn=is_tn,
                salary=j_sal
            ))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"  [Jobicy] Error: {e}")
    print(f"  [Jobicy] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🌐  SCRAPER 7 — Arbeitnow API (India / Worldwide Remote Only)
# ──────────────────────────────────────────────────

def scrape_arbeitnow():
    """Queries Arbeitnow API — strictly filtering for India & unrestricted Worldwide Remote."""
    print("[Radar] Scanning Arbeitnow (India/Global Remote)...")
    jobs_found = []
    try:
        url = "https://www.arbeitnow.com/api/job-board-api?page=1"
        resp = _api_request(url)
        if not resp:
            return []
        data = resp.json()
        for job in data.get("data", []):
            title     = job.get("title", "")
            company   = job.get("company_name", "Unknown")
            link      = job.get("url", "")
            raw_loc   = job.get("location", "")
            remote    = job.get("remote", False)
            tags      = " ".join(job.get("tags", []))
            full_date = str(job.get("created_at", "2025-01-01T"))

            if not link or not _keyword_match(title + " " + tags):
                continue

            loc_check = "Remote" if remote else raw_loc
            is_valid, tier, loc_tag, is_tn = classify_location(loc_check, title)
            if not is_valid:
                continue

            desc = clean_html(job.get("description", ""))
            jobs_found.append(_make_job(
                title=title, company=company, link=link, location=loc_tag,
                source="Arbeitnow 🌐", date_posted=full_date[:10],
                description=desc, priority_tier=tier, is_tn=is_tn
            ))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"  [Arbeitnow] Error: {e}")
    print(f"  [Arbeitnow] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🌐  SCRAPER 8 — RemoteOK API (India / Worldwide Remote Only)
# ──────────────────────────────────────────────────

def scrape_remoteok():
    """Queries RemoteOK API — strictly filtering for India & unrestricted Worldwide Remote."""
    print("[Radar] Scanning RemoteOK (India/Global Remote)...")
    jobs_found = []
    try:
        resp = _api_request("https://remoteok.com/api")
        if not resp:
            return []
        data = resp.json()
        for job in data[1:]:
            title     = job.get("position", "")
            company   = job.get("company", "Unknown")
            link      = job.get("url", "")
            geo       = job.get("location", "")
            tags      = " ".join(job.get("tags", []))
            full_date = str(job.get("date", "2025-01-01T"))

            if not link or not _keyword_match(title + " " + tags):
                continue

            is_valid, tier, loc_tag, is_tn = classify_location(geo, title + " " + tags)
            if not is_valid:
                continue

            desc = clean_html(job.get("description", ""))
            ro_min = job.get("salary_min")
            ro_max = job.get("salary_max")
            ro_sal = f"${int(ro_min):,} - ${int(ro_max):,}" if ro_min and ro_max else str(job.get("salary", "")).strip()

            jobs_found.append(_make_job(
                title=title, company=company, link=link, location=loc_tag,
                source="RemoteOK 🌏", date_posted=full_date[:10],
                description=desc, priority_tier=tier, is_tn=is_tn,
                salary=ro_sal
            ))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"  [RemoteOK] Error: {e}")
    print(f"  [RemoteOK] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 🔵  SCRAPER 9 — LinkedIn & Indeed India via JobSpy
# ──────────────────────────────────────────────────

def scrape_linkedin_indeed():
    """
    Uses python-jobspy to aggregate fresh tech openings across Indeed India, Google Jobs,
    and LinkedIn for Chennai, Coimbatore, Tamil Nadu & Bangalore.
    Extracts direct company ATS application links wherever available.
    """
    print("[Radar] Scanning Multi-Portal via JobSpy (Indeed India + Google Jobs + LinkedIn)...")
    jobs_found = []
    try:
        from jobspy import scrape_jobs
        queries = [
            ("software engineer fresher", "Chennai, Tamil Nadu, India"),
            ("python developer fresher", "Chennai, Tamil Nadu, India"),
            ("junior software engineer", "Coimbatore, Tamil Nadu, India"),
            ("data analyst fresher", "Chennai, Tamil Nadu, India"),
            ("frontend react developer fresher", "Tamil Nadu, India"),
        ]
        for query, loc in queries:
            try:
                df = scrape_jobs(
                    site_name=["indeed", "linkedin"],
                    search_term=query,
                    location=loc,
                    results_wanted=3,
                    hours_old=72,
                    country_indeed="India",
                    linkedin_fetch_description=False,
                    verbose=0,
                )
                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    title    = str(row.get("title", "")).strip()
                    raw_comp = str(row.get("company", "")).strip()
                    company  = "Verified Employer" if not raw_comp or raw_comp.lower() in ["nan", "none", "unknown", ""] else raw_comp
                    # Direct ATS URL prioritized over aggregator redirect
                    link     = str(row.get("job_url_direct") or row.get("job_url") or "").strip()
                    location = str(row.get("location", loc)).strip()
                    site     = str(row.get("site", "portal")).lower()

                    if not link or link == "nan" or not title or title.lower() in ["nan", "none", ""] or not _keyword_match(title):
                        continue

                    is_valid, tier, loc_tag, is_tn = classify_location(location, loc)
                    if not is_valid:
                        continue

                    if "linkedin" in site:
                        source = "LinkedIn 🔵"
                    elif "indeed" in site:
                        source = "Indeed India 🟢"
                    elif "glassdoor" in site:
                        source = "Glassdoor 🚪"
                    else:
                        source = f"JobSpy ({site.title()}) ⚡"

                    # Safe salary parsing without NaN crashes
                    min_sal = row.get("min_amount")
                    max_sal = row.get("max_amount")
                    cur = str(row.get("currency") or "INR").strip().upper()
                    cur_sym = "₹" if cur in ["INR", ""] else f"{cur} "

                    def _is_valid_num(val):
                        if val is None:
                            return False
                        try:
                            import math
                            f = float(val)
                            return not math.isnan(f) and f > 0
                        except (ValueError, TypeError):
                            return False

                    if _is_valid_num(min_sal) and _is_valid_num(max_sal):
                        sal_val = f"{cur_sym}{int(float(min_sal)):,} – {cur_sym}{int(float(max_sal)):,} p.a."
                    elif _is_valid_num(min_sal):
                        sal_val = f"{cur_sym}{int(float(min_sal)):,}+ p.a."
                    else:
                        sal_val = ""

                    desc_val = str(row.get("description", ""))
                    desc = clean_html(desc_val) if desc_val and desc_val != "nan" else ""

                    jobs_found.append(_make_job(
                        title=title,
                        company=company,
                        link=normalize_job_url(link),
                        location=loc_tag,
                        source=source,
                        description=desc,
                        priority_tier=tier,
                        is_tn=is_tn,
                        salary=sal_val,
                        direct_link=link
                    ))
                    if len(jobs_found) >= MAX_PER_SOURCE:
                        break
            except Exception as e:
                print(f"  [JobSpy Radar] Isolated error for '{query}': {e}")
            time.sleep(1.0)
    except ImportError:
        print("  [JobSpy Radar] python-jobspy library not installed. Skipping.")
    except Exception as e:
        print(f"  [JobSpy Radar] Error: {e}")

    print(f"  [JobSpy Multi-Portal] Found {len(jobs_found)} verified live jobs.")
    return jobs_found

# Alias for external modules
scrape_jobspy_multi_portal = scrape_linkedin_indeed

# ──────────────────────────────────────────────────
# 📤  TELEGRAM SENDER (WITH TAMIL NADU PRIORITY DISPLAY)
# ──────────────────────────────────────────────────

def send_radar_telegram(new_jobs):
    """Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized at the top."""
    try:
        import telebot
        
        _raw_token = os.getenv("TELEGRAM_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
        bot_token = str(_raw_token).strip().strip('"').strip("'")
        if bot_token.lower().startswith("bot"):
            bot_token = bot_token[3:]
        if not bot_token:
            print("[Radar Telegram] ⚠️ TELEGRAM_TOKEN missing. Skipping Telegram notification.")
            return

        _raw_chat = os.getenv("TELEGRAM_CHAT_ID", "")
        chat_id = str(_raw_chat).strip().strip('"').strip("'")
        if not chat_id and os.path.exists("chat_id.json"):
            try:
                with open("chat_id.json", "r") as f:
                    data = json.load(f)
                    chat_id = str(data.get("chat_id", "")).strip()
            except Exception:
                pass
        if not chat_id:
            print("[Radar Telegram] ⚠️ TELEGRAM_CHAT_ID missing. Skipping Telegram notification.")
            return

        radar_bot = telebot.TeleBot(bot_token, parse_mode=None)

        tn_jobs = [j for j in new_jobs if j.get("is_tamil_nadu", False) or j.get("priority_tier") == 1]
        india_jobs = [j for j in new_jobs if not j.get("is_tamil_nadu", False) and j.get("priority_tier") == 2]
        remote_jobs = [j for j in new_jobs if j.get("priority_tier") == 3]

        total = len(new_jobs)
        now_str = datetime.now().strftime('%I:%M %p, %d %b %Y')

        job_entries = []
        global_idx = 1

        import html

        def _format_section(title_header, job_list):
            nonlocal global_idx
            if not job_list:
                return
            job_entries.append(title_header)
            for job in job_list:
                title   = html.escape(str(job.get("title", "Unknown Role"))[:60])
                company = html.escape(str(job.get("company", "Unknown Company"))[:35])
                loc     = html.escape(str(job.get("location", "India"))[:40])
                link    = html.escape(str(job.get("link", "")).strip())
                date_str = str(job.get("date_posted", ""))
                desc    = html.escape(clean_html(job.get("description", "")))[:120]
                src     = html.escape(str(job.get("source", "Radar")))

                time_tag = "🟢 Today"
                if date_str:
                    ts = safe_date_timestamp(date_str)
                    if ts > 0:
                        try:
                            dt = datetime.fromtimestamp(ts)
                            days = (datetime.now() - dt).days
                            if days <= 0: time_tag = "🟢 Today"
                            elif days == 1: time_tag = "🟡 Yesterday"
                            elif days <= 7: time_tag = f"📅 {days}d ago"
                            else: time_tag = f"📆 {dt.strftime('%Y-%m-%d')}"
                        except Exception:
                            time_tag = "🟢 Recent"
                    else:
                        time_tag = "🟢 Recent"

                sal = html.escape(str(job.get("salary", "")).strip())
                hr_em = html.escape(str(job.get("hr_email", "")).strip())
                fit_badge = html.escape(str(job.get("fit_badge", "")).strip())

                entry = (
                    f"<b>{global_idx}.</b> <a href=\"{link}\"><b>{title}</b></a>\n"
                    f"   🏢 <b>Company:</b> <code>{company}</code>\n"
                    f"   📍 <b>Location:</b> <code>{loc}</code>\n"
                    f"   📡 <b>Source:</b> <i>{src}</i>\n"
                    f"   🕒 <b>Posted:</b> {time_tag}"
                )
                if fit_badge:
                    entry += f"\n   🎯 <b>Fit:</b> {fit_badge}"
                if sal:
                    entry += f"\n   💰 <b>Package:</b> <code>{sal}</code>"
                if hr_em:
                    entry += f"\n   📧 <b>HR Email:</b> <code>{hr_em}</code>"
                if desc and len(desc) > 15:
                    entry += f"\n   📝 <b>Work Detail:</b> <i>{desc}</i>"

                job_entries.append(entry)
                global_idx += 1

        # 1. TAMIL NADU HIGH PRIORITY SECTION
        if tn_jobs:
            _format_section(f"🌟 <b>TAMIL NADU OPPORTUNITIES ({len(tn_jobs)} JOBS — TOP PRIORITY)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", tn_jobs)

        # 2. OTHER INDIA TECH HUBS SECTION
        if india_jobs:
            _format_section(f"🇮🇳 <b>INDIA TECH OPPORTUNITIES ({len(india_jobs)} JOBS)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", india_jobs)

        # 3. REMOTE / GLOBAL SECTION
        if remote_jobs:
            _format_section(f"🌐 <b>REMOTE TECH OPPORTUNITIES ({len(remote_jobs)} JOBS)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", remote_jobs)

        # Split into chunks of under 3500 chars
        chunks = []
        current_chunk = []
        current_len = 0

        for item in job_entries:
            item_len = len(item) + 2
            if current_len + item_len > 3400 and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [item]
                current_len = item_len
            else:
                current_chunk.append(item)
                current_len += item_len
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        header = (
            f"📡 <b>JOB RADAR REPORT (INDIA & TN PRIORITY)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆕 Found <b>{total}</b> Verified Opportunities!\n"
            f"🌟 <b>Tamil Nadu Priority:</b> <b>{len(tn_jobs)}</b> jobs\n"
            f"🇮🇳 <b>Pan-India:</b> <b>{len(india_jobs)}</b> jobs | 🌐 <b>Remote:</b> <b>{len(remote_jobs)}</b> jobs\n"
            f"🕒 {now_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

        # Build rich interactive action keyboard for direct applying & sharing
        radar_kb = InlineKeyboardMarkup()
        top_row = []

        if tn_jobs:
            top_tn = tn_jobs[0]
            top_tn_link = (top_tn.get("link") or top_tn.get("raw_link") or "").strip()
            top_tn_comp = top_tn.get("company", "Tamil Nadu")[:14]
            if top_tn_link.startswith("http"):
                top_row.append(InlineKeyboardButton(text=f"🌟 Top TN ({top_tn_comp})", url=top_tn_link))

        if india_jobs:
            top_in = india_jobs[0]
            top_in_link = (top_in.get("link") or top_in.get("raw_link") or "").strip()
            top_in_comp = top_in.get("company", "India")[:14]
            if top_in_link.startswith("http"):
                top_row.append(InlineKeyboardButton(text=f"🚀 Top India ({top_in_comp})", url=top_in_link))

        if top_row:
            radar_kb.row(*top_row)

        radar_kb.row(
            InlineKeyboardButton(text="📢 National Drives", callback_data="drives"),
            InlineKeyboardButton(text="📊 Live Analytics", callback_data="analytics")
        )

        share_text = urllib.parse.quote(f"🚀 Found {total} verified tech fresher jobs in Tamil Nadu & India! Check them out on JobPulse AI.")
        share_url = f"https://t.me/share/url?url=https://t.me&text={share_text}"
        radar_kb.row(InlineKeyboardButton(text="📤 Share Radar Digest", url=share_url))

        for idx, chunk in enumerate(chunks):
            if idx == 0:
                msg = header + chunk
            else:
                msg = f"📡 <b>Opportunities (Part {idx+1}/{len(chunks)})</b>\n\n" + chunk

            is_last = (idx == len(chunks) - 1)
            if is_last:
                msg += (
                    f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 <b>Total:</b> {total} jobs strictly verified for India & TN\n"
                    f"⏰ Next radar scan in 1 hour (24/7 Cloud)\n"
                    f"👉 <i>Tap any numbered title link to view & apply directly!</i>"
                )

            try:
                radar_bot.send_message(
                    chat_id,
                    msg,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=radar_kb if is_last else None
                )
                if not is_last:
                    time.sleep(0.6)
            except Exception as msg_e:
                try:
                    plain_msg = re.sub(r'<[^>]+>', '', msg)
                    radar_bot.send_message(chat_id, plain_msg[:4096], parse_mode=None, disable_web_page_preview=True)
                except Exception:
                    pass

    except Exception as e:
        print(f"[Radar] Telegram notification failed: {e}")

# ──────────────────────────────────────────────────
# 🕵️  SCRAPER 9 — JobSpy Multi-Platform (LinkedIn / Indeed / Glassdoor)
# ──────────────────────────────────────────────────

def scrape_jobspy():
    """
    Uses python-jobspy to scrape LinkedIn, Indeed, and Glassdoor for
    India-based fresher/junior software jobs. Filters through the existing
    location classifier and keyword engine. Runs WITHOUT any API key.
    """
    print("[Radar] 🕵️  JobSpy — Scanning LinkedIn + Indeed + Glassdoor for India jobs...")
    jobs_found = []

    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("  [JobSpy] python-jobspy not installed. Run: pip install python-jobspy")
        return []

    # Query configs: (site_names, search_term, location, results_wanted)
    queries = [
        (["linkedin", "indeed"], "software engineer fresher", "India", 20),
        (["linkedin", "indeed"], "python developer", "Chennai", 15),
        (["linkedin"],          "frontend developer react", "Tamil Nadu", 15),
        (["indeed"],            "full stack developer junior", "Bangalore India", 15),
        (["linkedin", "indeed"], "software developer 0-2 years", "Coimbatore India", 15),
    ]

    seen_links_local = set()

    for site_names, search_term, location, results_wanted in queries:
        if len(jobs_found) >= MAX_PER_SOURCE:
            break
        try:
            df = scrape_jobs(
                site_name=site_names,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                hours_old=72,          # Only jobs posted in last 3 days
                country_indeed="India",
                linkedin_fetch_description=False,  # Faster; titles+company are enough
                verbose=0,
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                title   = str(row.get("title") or "").strip()
                raw_comp = str(row.get("company") or "").strip()
                company = "Verified Employer" if not raw_comp or raw_comp.lower() in ["nan", "none", "unknown", ""] else raw_comp
                link    = str(row.get("job_url") or row.get("job_url_direct") or "").strip()
                raw_loc = str(row.get("location") or location).strip()
                date_p  = str(row.get("date_posted") or "")[:10]
                desc    = str(row.get("description") or "")[:300]
                salary_raw = str(row.get("min_amount") or "").strip()
                site_src   = str(row.get("site") or "jobspy").title()
                job_type   = str(row.get("job_type") or "").lower()

                if not link or not title:
                    continue

                # Skip if already seen in this batch
                norm = normalize_job_url(link)
                if norm in seen_links_local:
                    continue
                seen_links_local.add(norm)

                # Keyword filter
                if not _keyword_match(f"{title} {desc}"):
                    continue

                # Location classifier
                is_valid, tier, loc_tag, is_tn = classify_location(raw_loc, f"{title} {desc}")
                if not is_valid:
                    continue

                # Skip irrelevant job types
                if job_type and any(x in job_type for x in ["contract", "part"]):
                    # Allow contract but not pure part-time
                    if "part" in job_type and "full" not in job_type:
                        continue

                # Build salary string
                salary_str = ""
                try:
                    min_amt = row.get("min_amount")
                    max_amt = row.get("max_amount")
                    currency = str(row.get("currency") or "").upper()
                    sym = "₹" if currency in ["INR", ""] else currency + " "
                    if min_amt and max_amt and float(min_amt) > 0:
                        salary_str = f"{sym}{int(float(min_amt)):,} – {sym}{int(float(max_amt)):,} p.a."
                    elif min_amt and float(min_amt) > 0:
                        salary_str = f"{sym}{int(float(min_amt)):,}+ p.a."
                except Exception:
                    pass

                # Enrich from description
                if not salary_str and desc:
                    salary_str = extract_job_salary(desc)
                hr_email = extract_hr_email(desc) if desc else ""

                source_tag = f"{site_src} via JobSpy 🕵️"
                if is_tn:
                    source_tag = f"{site_src} via JobSpy 🌟"

                jobs_found.append(_make_job(
                    title=title[:65],
                    company=company[:45],
                    link=link,
                    location=loc_tag,
                    source=source_tag,
                    date_posted=date_p,
                    description=desc[:200],
                    priority_tier=tier,
                    is_tn=is_tn,
                    salary=salary_str,
                    hr_email=hr_email,
                ))

                if len(jobs_found) >= MAX_PER_SOURCE:
                    break

        except Exception as e:
            print(f"  [JobSpy] Error for '{search_term}' in '{location}': {e}")

        time.sleep(1.5)  # Polite delay between queries

    print(f"  [JobSpy] Found {len(jobs_found)} India/TN jobs from LinkedIn + Indeed + Glassdoor.")
    return jobs_found

def scrape_simplify_jobs(max_results=8):
    """
    Scrapes verified entry-level and fresher software engineering jobs from SimplifyJobs feed.
    """
    try:
        from bot_optimizer import fetch_simplify_jobs
        jobs = fetch_simplify_jobs(keyword="software", limit=max_results)
        results = []
        for j in jobs:
            loc = j.get("location", "Remote")
            is_valid, tier, norm_loc, is_tn = classify_location(loc, f"{j.get('role')} {j.get('company')}")
            if not is_valid and any(w in loc.lower() for w in ["remote", "global", "anywhere", "worldwide"]):
                is_valid = True
                tier = 3
                norm_loc = "Remote"
                is_tn = False

            # The SimplifyJobs feed is overwhelmingly US/Canada onsite roles
            # (2,384 live rows, only ~22 mentioning India). Without this the
            # radar alerts on Austin TX / Toronto jobs the user cannot apply to.
            if not is_valid:
                continue

            job_dict = _make_job(
                title=j.get("role", "Software Engineer"),
                company=j.get("company", "Tech Startup"),
                link=j.get("apply_url", "https://simplify.jobs"),
                location=norm_loc,
                source=f"SimplifyJobs ({j.get('portal', 'ATS')})",
                date_posted=datetime.now().strftime("%Y-%m-%d"),
                description=f"Entry-Level & Fresher Role via SimplifyJobs. Portal: {j.get('portal')}. Location: {loc}",
                priority_tier=tier,
                is_tn=is_tn,
                direct_link=j.get("apply_url", "")
            )
            results.append(job_dict)
        print(f"  [SimplifyJobs] Collected {len(results)} fresh tech roles.")
        return results
    except Exception as e:
        print(f"  [SimplifyJobs] Scrape error: {e}")
        return []

# ──────────────────────────────────────────────────
# 🚀  MAIN RADAR RUNNER
# ──────────────────────────────────────────────────

def run_radar():
    print("\n" + "=" * 60)
    print("[Radar] JOB RADAR STARTING SCAN — INDIA & TAMIL NADU ENGINE")
    print(f"   Priority 1: Tamil Nadu (Chennai, Coimbatore, Madurai, Trichy, etc.)")
    print(f"   Priority 2: India Tech Hubs (Bangalore, Hyderabad, Pune, etc.)")
    print(f"   Priority 3: Global Remote open to India")
    print(f"   Channels  : {len(RADAR_TELEGRAM_CHANNELS)} Telegram Job Channels")
    print(f"   Foreign   : Strictly Filtered Out (USA/UK/Europe onsite rejected)")
    print("=" * 60 + "\n")

    seen_jobs = load_seen_jobs()
    all_jobs  = []

    import concurrent.futures
    scrapers = {
        "Telegram Channels": scrape_telegram_channels_radar,
        "Adzuna India": scrape_adzuna_india,
        "Unstop India": scrape_unstop,
        "Foundit India": scrape_foundit,
        "LinkedIn/Indeed": scrape_linkedin_indeed,
        "Remotive": scrape_remotive,
        "Jobicy": scrape_jobicy,
        "Arbeitnow": scrape_arbeitnow,
        "RemoteOK": scrape_remoteok,
        "JobSpy (LinkedIn+Indeed+Glassdoor)": scrape_jobspy,  # 🕵️ NEW
        "SimplifyJobs (Tech Freshers)": scrape_simplify_jobs,  # 🎓 NEW
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(scrapers)) as executor:
        future_to_name = {executor.submit(func): name for name, func in scrapers.items()}
        try:
            for future in concurrent.futures.as_completed(future_to_name, timeout=40):
                name = future_to_name[future]
                try:
                    res = future.result()
                    if res:
                        all_jobs.extend(res)
                except Exception as e:
                    print(f"  [Radar] Scraper '{name}' error: {e}")
        except concurrent.futures.TimeoutError:
            print("  [Radar] Scrapers timeout reached. Proceeding with collected jobs.")

    from bot_optimizer import (
        calculate_skill_match_score,
        is_job_link_alive,
        extract_job_salary,
        extract_hr_email
    )
    profile_data = {}
    if os.path.exists("profile.json"):
        try:
            with open("profile.json", "r", encoding="utf-8") as pf:
                profile_data = json.load(pf)
        except Exception:
            pass

    new_jobs = []
    for job in all_jobs:
        raw_link = (job.get("link") or job.get("raw_link") or "").strip()
        norm_link = normalize_job_url(raw_link)
        if norm_link and norm_link not in seen_jobs and raw_link not in seen_jobs:
            # 1. Non-blocking dead-link probe (Feature 10)
            if not is_job_link_alive(norm_link, timeout=2.5):
                seen_jobs.add(norm_link)
                seen_jobs.add(raw_link)
                continue

            # 2. Enrich salary and HR email if not present
            text_bundle = f"{job.get('title', '')} {job.get('company', '')} {job.get('description', '')}"
            if not job.get("salary"):
                job["salary"] = extract_job_salary(text_bundle)
            if not job.get("hr_email"):
                job["hr_email"] = extract_hr_email(text_bundle)

            # 3. Compute ATS skill fit badge (Feature 9)
            match_res = calculate_skill_match_score(text_bundle, profile_data)
            job["fit_badge"] = match_res.get("badge", "")
            job["matched_skills"] = match_res.get("matched", [])

            new_jobs.append(job)
            mark_seen(norm_link)
            seen_jobs.add(norm_link)
            seen_jobs.add(raw_link)

    # 🎯 SORTING ENGINE: Tamil Nadu (Tier 1) FIRST, then India (Tier 2), then Remote (Tier 3)
    def _priority_sort_key(job):
        tier = job.get("priority_tier", 2)
        # Sort by tier ascending (1 first: TN, 2: India, 3: Remote), then date descending (newest first)
        return (tier, -safe_date_timestamp(job.get("date_posted")))

    new_jobs.sort(key=_priority_sort_key)

    print(f"\n[Radar] Total new unique India/TN jobs: {len(new_jobs)}")
    tn_count = sum(1 for j in new_jobs if j.get("is_tamil_nadu", False))
    print(f"[Radar] 🌟 Tamil Nadu Priority Jobs: {tn_count}")

    # Retain existing data if empty
    existing_data = {}
    try:
        if os.path.exists(RESULTS_JSON):
            with open(RESULTS_JSON, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
    except Exception:
        pass

    jobs_to_save = new_jobs if new_jobs else existing_data.get("jobs", [])
    save_results(jobs_to_save)

    if new_jobs:
        send_radar_telegram(new_jobs)
    else:
        print("[Radar] No new jobs this cycle. Previous results retained.")

    print("[Radar] Scan complete.\n")
    return new_jobs

# ──────────────────────────────────────────────────
# 🌟  DEDICATED TAMIL NADU JOB RADAR & DISPATCH
# ──────────────────────────────────────────────────

TN_CACHE_FILE = "tn_jobs_cache.json"

def _filter_and_paginate_tn_jobs(jobs, limit=10, category=None, city=None, page=1):
    filtered = list(jobs)
    if category:
        c_str = str(category).lower().strip()
        if c_str in ["tech", "it", "software"]:
            filtered = [
                j for j in filtered
                if any(w in (str(j.get("title", "")) + " " + str(j.get("description", "")) + " " + str(j.get("source", "")) + " " + str(j.get("category", ""))).lower()
                       for w in ["software", "developer", "engineer", "python", "java", "react", "data", "cloud", "devops", "qa", "test", "full stack", "backend", "frontend", "smartrecruiters", "freshworks", "bosch", "zoho", "programmer", "analyst", "node", "ai", "ml"])
            ]
        elif c_str in ["govt", "mrb", "tnpsc", "government"]:
            filtered = [
                j for j in filtered
                if any(w in (str(j.get("company", "")) + " " + str(j.get("title", "")) + " " + str(j.get("source", ""))).lower()
                       for w in ["govt", "mrb", "tnpsc", "district", "collectorate", "tamil nadu", "health", "hospital", "recruitment board", "medical services", "samagra", "nhm", "collector", "nic.in"])
            ]
        elif c_str in ["core", "auto", "manufacturing", "engineering"]:
            filtered = [
                j for j in filtered
                if any(w in (str(j.get("title", "")) + " " + str(j.get("company", "")) + " " + str(j.get("description", ""))).lower()
                       for w in ["bosch", "renault", "nissan", "ford", "caterpillar", "valeo", "auto", "mechanical", "electrical", "production", "avery dennison", "plant", "manufacturing", "quality", "design", "maintenance"])
            ]
        elif c_str in ["freshers", "fresher", "intern"]:
            filtered = [
                j for j in filtered
                if "fresh" in str(j.get("experience", "")).lower()
                or "0-1" in str(j.get("experience", "")).lower()
                or "0-2" in str(j.get("experience", "")).lower()
                or "intern" in str(j.get("title", "")).lower()
                or any(b in str(j.get("batch", "")) for b in ["2024", "2025", "2026"])
            ]
    if city:
        city_lower = str(city).lower().strip()
        filtered = [
            j for j in filtered
            if city_lower in str(j.get("location", "")).lower()
            or city_lower in str(j.get("city", "")).lower()
        ]

    total_matched = len(filtered)
    start_idx = max(0, (page - 1) * limit)
    end_idx = start_idx + limit
    page_items = filtered[start_idx:end_idx]
    return page_items, total_matched


def get_tamil_nadu_jobs(limit=10, force_refresh=False, category=None, city=None, page=1, return_total=False):
    """
    Retrieves recently posted engineering and tech jobs in Tamil Nadu (Chennai, Coimbatore, Madurai, Trichy, Salem, Hosur, etc.)
    and verified Remote positions open to TN candidates.
    Supports category filtering, city filtering, and pagination.
    Uses intelligent caching (30-min TTL) unless force_refresh is True.
    """
    now_ts = time.time()
    if not force_refresh and os.path.exists(TN_CACHE_FILE):
        try:
            with open(TN_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cached_ts = cached.get("timestamp", 0)
            cached_jobs = cached.get("jobs", [])
            if cached_jobs and (now_ts - cached_ts < 1800):
                print(f"[TN Radar] Using cached Tamil Nadu jobs ({len(cached_jobs)} available, TTL: {int(1800 - (now_ts - cached_ts))}s remaining)")
                page_items, total_matched = _filter_and_paginate_tn_jobs(cached_jobs, limit=limit, category=category, city=city, page=page)
                if return_total:
                    return page_items, total_matched
                return page_items
        except Exception as e:
            print(f"[TN Radar] Cache read warning: {e}")

    print("[TN Radar] 🔍 Sweeping live sources for fresh Tamil Nadu job openings...")
    collected = []
    seen_links = set()

    # 0. Load high-confidence verified Tamil Nadu jobs from tn-live-jobs (Zero-Bot-Block ATS + TN Govt)
    tn_live_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "tn-live-jobs", "data", "jobs.json"))
    if os.path.exists(tn_live_json):
        try:
            with open(tn_live_json, "r", encoding="utf-8-sig") as f:
                tdata = json.load(f)
            raw_records = tdata.get("jobs", [])
            ingested = 0
            skipped_no_link = 0
            for j in raw_records:
                link = normalize_job_url(tn_live_apply_url(j))
                if not link:
                    skipped_no_link += 1
                    continue
                if link in seen_links:
                    continue
                seen_links.add(link)
                ingested += 1
                city = _clean_str(j.get("city"), "Tamil Nadu")
                collected.append(_make_job(
                    title=_clean_str(j.get("title"), "Untitled role"),
                    company=_clean_str(j.get("company"), "Employer not listed"),
                    link=link,
                    location=f"{city}, Tamil Nadu ⭐",
                    source=f"TN Live ({_clean_str(j.get('source'), 'Verified')})",
                    date_posted=tn_live_posted_at(j) or datetime.now().strftime("%Y-%m-%d"),
                    description=tn_live_description(j),
                    priority_tier=1,
                    is_tn=True,
                    salary=tn_live_salary(j),
                    experience=_clean_str(j.get("experience")),
                    batch=_clean_str(j.get("qualification")),
                ))
            # The old message printed the raw record count regardless of how many were
            # actually ingested, so a total schema mismatch looked like a healthy run.
            print(f"[TN Radar] 🌟 Ingested {ingested}/{len(raw_records)} verified live jobs from tn-live-jobs suite.")
            if skipped_no_link:
                print(f"[TN Radar] ⚠️  {skipped_no_link} tn-live-jobs records had no usable apply_url and were dropped.")
        except Exception as e:
            print(f"[TN Radar] Error reading tn-live-jobs data: {e}")

    # 1. Inspect existing radar_results.json
    if os.path.exists(RESULTS_JSON):
        try:
            with open(RESULTS_JSON, "r", encoding="utf-8") as f:
                rdata = json.load(f)
            for j in rdata.get("jobs", []):
                loc = (j.get("location") or "").lower()
                is_tn = j.get("is_tamil_nadu") or any(k in loc for k in TAMIL_NADU_LOCATIONS)
                link = normalize_job_url(j.get("link") or j.get("raw_link") or "")
                if is_tn and link and link not in seen_links:
                    seen_links.add(link)
                    collected.append(j)
        except Exception as e:
            print(f"[TN Radar] Error reading radar_results.json: {e}")

    # 2. Query Adzuna India for Tamil Nadu, Chennai, Coimbatore & Hosur
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")
    if app_id and app_key:
        tn_queries = [
            ("software engineer", "Chennai"),
            ("developer", "Tamil Nadu"),
            ("fresher", "Chennai"),
            ("python developer", "Chennai"),
            ("fresher engineer", "Coimbatore"),
            ("software trainee", "Tamil Nadu"),
            ("junior developer", "Chennai"),
        ]
        for kw, where in tn_queries:
            try:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/in/search/1"
                    f"?app_id={app_id}&app_key={app_key}"
                    f"&what={urllib.parse.quote(kw)}&where={urllib.parse.quote(where)}"
                    f"&results_per_page=15&content-type=application/json&sort_by=date"
                )
                resp = _api_request(url)
                if resp:
                    for job in resp.json().get("results", []):
                        title = job.get("title", "")
                        comp = job.get("company", {}).get("display_name", "Tech Company")
                        link = job.get("redirect_url", "")
                        raw_loc = job.get("location", {}).get("display_name", where)
                        norm = normalize_job_url(link)
                        if not norm or norm in seen_links:
                            continue
                        seen_links.add(norm)
                        desc = clean_html(job.get("description", ""))
                        sal_min = job.get("salary_min")
                        sal_max = job.get("salary_max")
                        adz_sal = f"₹{int(sal_min):,} - ₹{int(sal_max):,}" if sal_min and sal_max else ""
                        item = _make_job(
                            title=title,
                            company=comp,
                            link=link,
                            location=f"{where}, Tamil Nadu ⭐",
                            source="Adzuna India 🇮🇳",
                            date_posted=str(job.get("created", ""))[:10],
                            description=desc,
                            priority_tier=1,
                            is_tn=True,
                            salary=adz_sal
                        )
                        collected.append(item)
            except Exception as adz_e:
                print(f"[TN Radar] Adzuna error: {adz_e}")

    # 3. Targeted scrape of dedicated Tamil Nadu & top fresher Telegram channels
    tn_channels = [
        "chennaijobsofficial",
        "coimbatore_jobs",
        "JobSkull",
        "KickCharm",
        "Freshershunt",
        "chennai_walkins",
        "tn_fresher_jobs",
    ]
    def _fetch_channel_tn(channel_name):
        res = []
        resp_text = None
        for host in ["telegram.dog", "t.me"]:
            try:
                tg_url = f"https://{host}/s/{channel_name}"
                headers = {"User-Agent": random.choice(USER_AGENTS)}
                r = requests.get(tg_url, headers=headers, timeout=6)
                if r.status_code == 200 and r.text:
                    resp_text = r.text
                    break
            except Exception:
                continue
        if not resp_text:
            return []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp_text, "html.parser")
            msgs = soup.find_all("div", class_="tgme_widget_message_wrap")
            for b in reversed(msgs[-15:]):
                txt_el = b.find("div", class_="tgme_widget_message_text")
                if not txt_el:
                    continue
                text = txt_el.get_text(separator="\n").strip()
                t_lower = text.lower()
                is_tn = any(k in t_lower for k in TAMIL_NADU_LOCATIONS)
                is_remote = any(k in t_lower for k in ["remote", "work from home", "wfh", "pan india"])
                if not (is_tn or is_remote or channel_name.startswith("chennai") or channel_name.startswith("tamil") or channel_name.startswith("coimbatore")):
                    continue

                links = []
                for a in b.find_all("a", href=True):
                    href = a["href"].strip()
                    if href.startswith("http") and not is_social_or_promo_link(href):
                        links.append(href)
                for u in re.findall(r'(https?://[^\s<>"]+)', text):
                    u = u.rstrip(").,!*'\"")
                    if not is_social_or_promo_link(u) and u not in links:
                        links.append(u)

                if not links:
                    continue

                raw_link = links[0]
                direct_link = unwrap_radar_direct_link(raw_link)
                if is_social_or_promo_link(direct_link):
                    continue

                # Clean Company Extraction
                comp = ""
                comp_m = re.search(r'(?:🏢|Company|Organisation|Org)\s*[:\-]?\s*([^\n📍💼🛠️💰📝👉🔗|]+)', text, re.I)
                if comp_m:
                    comp = comp_m.group(1).strip()
                if not comp:
                    comp_m2 = re.search(r'([A-Za-z0-9\s&.,\-]{2,30}?)\s+(?:is\s+Hiring|Hiring|Off\s*Campus\s+Drive|Recruitment)', text, re.I)
                    if comp_m2:
                        comp = comp_m2.group(1).strip()
                comp = re.sub(r'^[^\w\s]+', '', comp).strip()
                comp = re.sub(r'^(?:Miss|Alert|Opportunity|Permanent|Remote)\s+', '', comp, flags=re.I).strip()
                comp = re.sub(r'\s+(?:is\s+)?hiring.*$', '', comp, flags=re.I).strip()
                if not comp or len(comp) < 2 or comp.lower() in ["hiring", "apply", "job", "verified recruiter", "recruitment", "online", "drive"]:
                    comp = "Verified Tech Company"

                # Clean Role Extraction
                role = ""
                role_m = re.search(r'(?:💼|Role|Position|Job\s*Title|Post|Designation)\s*[:\-]?\s*([^\n🏢📍💼🛠️💰📝👉🔗|]+)', text, re.I)
                if role_m:
                    role = role_m.group(1).strip()
                if not role:
                    role_m2 = re.search(r'(?:Hiring|for)\s+([A-Za-z0-9\s&.,\-/]{3,45}?)(?:\s+Location|\s+Experience|\s+Salary|\n|$)', text, re.I)
                    if role_m2:
                        role = role_m2.group(1).strip()
                role = re.sub(r'^[^\w\s]+', '', role).strip()
                role = re.sub(r'^(?:Freshers\s+for|Freshers\s+as)\s+', '', role, flags=re.I).strip()
                if not role or len(role) < 3 or not re.search(r'[A-Za-z]', role):
                    role = "Software Development Engineer"

                # Strict non-engineering filter
                non_eng_keywords = [
                    "medical billing", "medical coder", "medical coding", "bpo", "telecaller",
                    "telecalling", "delivery boy", "delivery partner", "pharma sales", "retail sales"
                ]
                if any(k in role.lower() for k in non_eng_keywords):
                    continue

                loc_str = "Chennai, Tamil Nadu ⭐"
                for city in ["coimbatore", "madurai", "trichy", "salem", "hosur", "tirunelveli"]:
                    if city in t_lower:
                        loc_str = f"{city.capitalize()}, Tamil Nadu ⭐"
                        break
                if is_remote and not is_tn:
                    loc_str = "Remote (All TN Candidates) 🌐"

                item = _make_job(
                    title=role[:60],
                    company=comp[:35],
                    link=direct_link,
                    location=loc_str,
                    source=f"Telegram @{channel_name}",
                    description=text[:250],
                    priority_tier=1,
                    is_tn=True,
                    direct_link=direct_link
                )
                res.append(item)
        except Exception:
            pass
        return res

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tn_channels), 8)) as ex:
        futures = [ex.submit(_fetch_channel_tn, ch) for ch in tn_channels]
        try:
            for f in concurrent.futures.as_completed(futures, timeout=12):
                try:
                    ch_jobs = f.result()
                    for j in ch_jobs:
                        norm = normalize_job_url(j.get("link") or j.get("raw_link") or "")
                        if norm and norm not in seen_links:
                            seen_links.add(norm)
                            collected.append(j)
                except Exception:
                    pass
        except concurrent.futures.TimeoutError:
            print("  [TN Radar] Channel sweep timeout reached. Proceeding with collected jobs.")

    # Sort newest first
    def _tn_sort_key(job):
        return -safe_date_timestamp(job.get("date_posted"))

    collected.sort(key=_tn_sort_key)

    # Save to cache
    try:
        cache_data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": now_ts,
            "total": len(collected),
            "jobs": collected
        }
        with open(TN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TN Radar] Failed to write cache: {e}")

    page_items, total_matched = _filter_and_paginate_tn_jobs(collected, limit=limit, category=category, city=city, page=page)
    print(f"[TN Radar] Found {len(collected)} verified Tamil Nadu jobs (Matched: {total_matched}).")
    if return_total:
        return page_items, total_matched
    return page_items


def format_tamil_nadu_telegram_digest(jobs, max_chars=3800, category=None, current_page=1, total_jobs=None):
    """
    Formats recently posted Tamil Nadu jobs into clean, high-aesthetic HTML chunks
    with batch year & experience badges, direct links, 1-tap prep/note/cold-email buttons,
    category filter chips, pagination, and WebApp live board link.
    Returns (chunks: list[str], reply_markup: InlineKeyboardMarkup).
    """
    cat_labels = {
        "tech": "💻 IT & Software",
        "govt": "🏛️ Govt & TNPSC",
        "core": "🏢 Core Engineering & Auto",
        "freshers": "🎓 Freshers (0-1 yrs)",
    }
    cat_name = cat_labels.get(str(category).lower().strip()) if category else None

    if not jobs:
        sub_info = f" in <b>{cat_name}</b>" if cat_name else ""
        msg = (
            f"🌟 <b>TAMIL NADU JOB RADAR</b> 🇮🇳\n\n"
            f"⚠️ No active jobs currently listed{sub_info}.\n"
            "Tap <b>All Jobs</b> or <b>Refresh</b> below to see fresh openings across Chennai, Coimbatore, and Remote."
        )
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton(text="🔄 All TN Jobs", callback_data="tnjobs:all"),
            InlineKeyboardButton(text="📡 All India Radar", callback_data="radar")
        )
        markup.row(
            InlineKeyboardButton(text="🌐 Open Live Job Board", url="https://nm969989-cmd.github.io/myjob-ai-bot/tn-live-jobs/")
        )
        return [msg], markup

    cat_badge = f" • [{cat_name}]" if cat_name else ""
    page_info = f" (Page {current_page})" if (current_page > 1 or (total_jobs and total_jobs > len(jobs))) else ""
    header = (
        f"🌟 <b>TAMIL NADU FRESH JOB RADAR</b> 🇮🇳{cat_badge}{page_info}\n"
        "📍 <i>Targeting: Chennai, Coimbatore, Madurai, Trichy, Salem & Remote</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    chunks = []
    current_chunk = header
    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for idx, j in enumerate(jobs):
        num = num_emojis[idx] if idx < len(num_emojis) else f"#{idx+1}"
        title = html.escape(str(j.get("title", "Software Engineer"))[:50])
        company = html.escape(str(j.get("company", "Tech Company"))[:35])
        location = html.escape(str(j.get("location", "Chennai, Tamil Nadu ⭐")))
        batch = html.escape(str(j.get("batch") or "2024 / 2025 / 2026 Batch"))
        exp = html.escape(str(j.get("experience") or "Freshers (0-1 yrs)"))
        sal = html.escape(str(j.get("salary") or "As per Industry Standards"))
        link = (j.get("link") or j.get("raw_link") or "#").strip()
        date_posted = html.escape(str(j.get("date_posted", "Recently"))[:10])

        card = (
            f"{num} <b>{title}</b>\n"
            f"🏢 <b>{company}</b>\n"
            f"📍 <i>{location}</i>\n"
            f"🎓 <b>Eligible:</b> <code>{batch}</code>\n"
            f"💼 <b>Experience:</b> <code>{exp}</code>\n"
            f"💰 <b>Package:</b> {sal}\n"
            f"🗓️ <b>Posted:</b> {date_posted}\n"
            f"🔗 <a href=\"{link}\">👉 <b>Tap to Apply Online</b></a>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        if len(current_chunk) + len(card) > max_chars:
            chunks.append(current_chunk)
            current_chunk = f"🌟 <b>TAMIL NADU JOBS (Contd. {len(chunks)+1})</b>\n\n" + card
        else:
            current_chunk += card

    if current_chunk.strip():
        chunks.append(current_chunk)

    # Attach interactive keyboard
    markup = InlineKeyboardMarkup()
    top_job = jobs[0] if jobs else None

    if top_job:
        top_link = (top_job.get("link") or top_job.get("raw_link") or "").strip()
        top_comp = str(top_job.get("company", "Top Job")).strip()
        top_role = str(top_job.get("title", "Software Engineer")).strip()
        top_skills = top_job.get("skills") or []

        if top_link.startswith("http"):
            markup.row(InlineKeyboardButton(text=f"🚀 Apply to #1: {top_comp[:18]}", url=top_link))

        # 1-Tap Action Buttons for Top Job
        try:
            import hashlib
            from bot_optimizer import store_prep_cache, store_note_cache, store_email_cache
            prep_hash = hashlib.md5(f"tn_p_{top_comp}_{top_role}".encode()).hexdigest()[:8]
            note_hash = hashlib.md5(f"tn_n_{top_comp}_{top_role}".encode()).hexdigest()[:8]
            email_hash = hashlib.md5(f"tn_e_{top_comp}_{top_role}".encode()).hexdigest()[:8]

            store_prep_cache(prep_hash, {"company": top_comp, "role": top_role, "skills": top_skills})
            store_note_cache(note_hash, f"Hi! I noticed the {top_role} opening at {top_comp} in Tamil Nadu. With experience in software development, I would love to connect and learn more about your engineering team!")
            store_email_cache(email_hash, {"company": top_comp, "role": top_role, "skills": top_skills})

            markup.row(
                InlineKeyboardButton(text="💡 Prep #1", callback_data=f"prep:{prep_hash}"),
                InlineKeyboardButton(text="💬 Note #1", callback_data=f"note:{note_hash}"),
                InlineKeyboardButton(text="✉️ Email #1", callback_data=f"email:{email_hash}")
            )
        except Exception:
            pass

    # Quick category filter chips
    markup.row(
        InlineKeyboardButton(text="💻 Tech / IT", callback_data="tnjobs:tech"),
        InlineKeyboardButton(text="🏛️ Govt / MRB", callback_data="tnjobs:govt"),
        InlineKeyboardButton(text="🎓 Freshers", callback_data="tnjobs:freshers")
    )

    # Pagination & Refresh row
    nav_buttons = []
    cat_tag = category or "all"
    if current_page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"tnjobs:p:{current_page - 1}:{cat_tag}"))
    nav_buttons.append(InlineKeyboardButton(text="🔄 Refresh TN Jobs", callback_data=f"tnjobs:refresh:{cat_tag}"))
    if total_jobs and (current_page * len(jobs) < total_jobs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"tnjobs:p:{current_page + 1}:{cat_tag}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    # Web Board & Radar row
    markup.row(
        InlineKeyboardButton(text="🌐 Open Live Job Board", url="https://nm969989-cmd.github.io/myjob-ai-bot/tn-live-jobs/"),
        InlineKeyboardButton(text="📡 All India Radar", callback_data="radar")
    )

    return chunks, markup


def dispatch_tamil_nadu_alerts(bot=None, chat_id=None, limit=8, force_refresh=False, only_unseen=False):
    """
    Sweeps and directly dispatches Tamil Nadu job cards to the given or configured Telegram chat.
    If only_unseen=True, filters against already dispatched links so automated runs never send duplicates.
    """
    if not bot:
        token = os.getenv("TELEGRAM_TOKEN", "").strip().strip('"').strip("'")
        if not token:
            print("[TN Radar] No TELEGRAM_TOKEN available for dispatch.")
            return False
        import telebot
        bot = telebot.TeleBot(token)

    if not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip().strip('"').strip("'")
        if not chat_id and os.path.exists("chat_id.json"):
            try:
                with open("chat_id.json", "r", encoding="utf-8") as f:
                    chat_id = json.load(f).get("chat_id", "")
            except Exception:
                pass

    if not chat_id:
        print("[TN Radar] No TELEGRAM_CHAT_ID found for dispatch.")
        return False

    # Fetch wider pool (up to 50 jobs) so unseen filtering finds fresh opportunities across multiple sweeps
    jobs = get_tamil_nadu_jobs(limit=50 if only_unseen else limit, force_refresh=force_refresh)

    if only_unseen:
        seen_links = set(load_seen_jobs())
        if os.path.exists("applied_jobs.json"):
            try:
                with open("applied_jobs.json", "r", encoding="utf-8") as f:
                    seen_links.update(json.load(f))
            except Exception:
                pass

        unseen = []
        for j in jobs:
            link = normalize_job_url(j.get("link") or j.get("raw_link") or "")
            raw = (j.get("raw_link") or "").strip()
            if link and link not in seen_links and raw not in seen_links:
                unseen.append(j)
        jobs = unseen[:limit]

        if not jobs:
            print("[TN Radar] All available Tamil Nadu jobs have already been dispatched. Skipping duplicate send.")
            return 0

    chunks, markup = format_tamil_nadu_telegram_digest(jobs)

    for idx, chunk in enumerate(chunks):
        is_last = (idx == len(chunks) - 1)
        try:
            bot.send_message(
                chat_id,
                chunk,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=markup if is_last else None
            )
        except Exception:
            plain = re.sub(r'<[^>]+>', '', chunk)
            bot.send_message(
                chat_id,
                plain[:4096],
                parse_mode=None,
                disable_web_page_preview=True,
                reply_markup=markup if is_last else None
            )
        time.sleep(0.5)

    # Mark sent links as seen so they are never resent automatically
    for j in jobs:
        link = normalize_job_url(j.get("link") or j.get("raw_link") or "")
        if link:
            mark_seen(link)

    print(f"[TN Radar] Successfully dispatched {len(jobs)} Tamil Nadu jobs to Telegram.")
    return len(jobs)

if __name__ == "__main__":
    if "--tn-only" in sys.argv:
        tn_jobs = get_tamil_nadu_jobs(limit=10, force_refresh=("--refresh" in sys.argv))
        print(f"\n[CLI] Discovered {len(tn_jobs)} Tamil Nadu jobs:")
        for idx, j in enumerate(tn_jobs, 1):
            print(f" {idx}. {j.get('title')} @ {j.get('company')} ({j.get('location')}) - Batch: {j.get('batch')} - Link: {j.get('link')}")
        if "--send" in sys.argv:
            dispatch_tamil_nadu_alerts(limit=8, force_refresh=("--refresh" in sys.argv))
            print("[CLI] Dispatched to Telegram.")
    else:
        run_radar()

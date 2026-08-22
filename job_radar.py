"""
📡 JOB RADAR — Multi-Platform Job Finder (v2 - Fixed APIs)
================================================================
Optimized for Unicorn Developer Profile (Tamil Nadu & Remote)
Uses free public APIs that don't require registration.
"""

import os
import json
import time
import random
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

# ──────────────────────────────────────────────────
# 🎯  FILTER CONFIGURATION  (Unicorn Profile)
# ──────────────────────────────────────────────────

RADAR_KEYWORDS = [
    # Software / Engineering
    "Software Developer", "Software Engineer", "Junior Software Engineer",
    "Graduate Engineer Trainee", "Software Development Engineer", "SDE-1",
    "Associate Developer", "Systems Engineer Trainee",
    # Frontend / UI
    "Frontend Developer", "React Developer", "Web Developer",
    "Application Developer", "UI Engineer",
    # Design / UX
    "UI/UX Designer", "Product Designer", "Interface Designer", "UX Researcher",
    # Backend / Full-Stack
    "Backend Developer", "Full-Stack Developer", "Full Stack", "Java Developer",
    "Java Engineer", "Spring Boot", "Oracle APEX Developer",
    # Other tech
    "Python Developer", "Node", "Angular", "Vue",
    # 2025 Specific
    "2025 Batch", "2025 Passout", "2025 Graduate",
]

PREFERRED_LOCATIONS = [
    "Tiruvannamalai", "Tiruppur", "Chennai", "Coimbatore",
    "Madurai", "Tiruchirappalli", "Trichy", "Salem", "Tirunelveli", "Vellore", "Erode",
    "Tamil Nadu", "Tamilnadu", "TN",
    "Remote", "Work from Home", "WFH", "Worldwide", "Global",
]

# Only show jobs from 2025 onwards
FILTER_YEAR = 2025

# How many results max per source (Increased to find more jobs)
MAX_PER_SOURCE = 30

# Memory so the same job isn't sent twice
SEEN_JOBS_FILE   = "radar_seen_jobs.txt"
RESULTS_JSON     = "radar_results.json"   # Dashboard reads this

# ──────────────────────────────────────────────────
# 🥷  STEALTH ENGINE
# ──────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

def _api_request(url, max_retries=2):
    """Simple JSON API request — uses minimal headers to avoid gzip/encoding issues."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JobRadarBot/1.0)",
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 200:
                return resp
            if resp.status_code in [429, 503]:
                print(f"  [API] Rate limited on {url}, waiting...")
                time.sleep(5 * (attempt + 1))
                continue
            print(f"  [API] Got {resp.status_code} for {url}")
        except Exception as e:
            print(f"  [API Request] Error: {e}")
            time.sleep(3)
    return None

def human_jitter(min_sec=1.0, max_sec=3.0):
    time.sleep(random.uniform(min_sec, max_sec))

# ──────────────────────────────────────────────────
# 🔧  HELPERS
# ──────────────────────────────────────────────────

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def mark_seen(link):
    with open(SEEN_JOBS_FILE, "a", encoding="utf-8") as f:
        f.write(link.strip() + "\n")

def save_results(jobs):
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "last_scan": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(jobs),
            "jobs": jobs
        }, f, indent=2, ensure_ascii=False)

def _keyword_match(text):
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in RADAR_KEYWORDS)

def _location_match(text):
    text_lower = text.lower()
    return any(loc.lower() in text_lower for loc in PREFERRED_LOCATIONS)

import re

def clean_html(raw_html):
    if not raw_html:
        return ""
    # Strip HTML tags
    clean_text = re.sub(r'<[^>]+>', '', raw_html)
    # Replace multiple spaces/newlines
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text[:120] + "..." if len(clean_text) > 120 else clean_text

def _make_job(title, company, link, location, source, date_posted="", description=""):
    if not date_posted:
        date_posted = datetime.now().strftime("%Y-%m-%d")
    return {
        "title":       title.strip(),
        "company":     company.strip(),
        "link":        link.strip(),
        "location":    location.strip(),
        "source":      source,
        "date_posted": date_posted,
        "description": description.strip(),
        "found_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

# ──────────────────────────────────────────────────
# 🕷️  SCRAPER 1 — Remotive API (Free, No Key Needed)
# ──────────────────────────────────────────────────

def scrape_remotive():
    """Queries the free Remotive.com public API for remote tech jobs."""
    print("[Radar] Scanning Remotive API...")
    jobs_found = []

    for kw in ["software engineer", "frontend developer", "react developer", "python developer"]:
        try:
            import urllib.parse
            url = f"https://remotive.com/api/remote-jobs?search={urllib.parse.quote(kw)}&limit=20"
            resp = _api_request(url)
            if not resp:
                continue
            data = resp.json()
            for job in data.get("jobs", []):
                title   = job.get("title", "")
                company = job.get("company_name", "Unknown")
                link    = job.get("url", "")
                full_date = str(job.get("publication_date", "2025-01-01T"))
                pub_year = full_date[:4]
                tags    = " ".join(job.get("tags", []))

                if not link:
                    continue
                try:
                    if int(pub_year) < FILTER_YEAR:
                        continue
                except Exception:
                    pass

                if not _keyword_match(title + " " + tags):
                    continue

                desc = clean_html(job.get("description", ""))
                jobs_found.append(_make_job(title, company, link, "Remote 🌍", "Remotive 🚀", full_date[:10], desc))
                if len(jobs_found) >= MAX_PER_SOURCE:
                    break

            if len(jobs_found) >= MAX_PER_SOURCE:
                break

        except Exception as e:
            print(f"  [Remotive] Error for '{kw}': {e}")

        time.sleep(1.5)

    print(f"  [Remotive] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🕷️  SCRAPER 2 — Jobicy API (Free, No Key)
# ──────────────────────────────────────────────────

def scrape_jobicy():
    """Queries the free Jobicy public API for remote tech jobs."""
    print("[Radar] Scanning Jobicy API...")
    jobs_found = []

    try:
        url = "https://jobicy.com/api/v2/remote-jobs?count=50&industry=engineering"
        resp = _api_request(url)
        if not resp:
            print("  [Jobicy] No response")
            return []

        data = resp.json()
        for job in data.get("jobs", []):
            title    = job.get("jobTitle", "")
            company  = job.get("companyName", "Unknown")
            link     = job.get("url", "")
            location = job.get("jobGeo", "Remote")
            full_date = str(job.get("pubDate", "2025-01-01T"))
            pub_year = full_date[:4]
            tags     = " ".join(job.get("jobIndustry", []))

            if not link:
                continue
            try:
                if int(pub_year) < FILTER_YEAR:
                    continue
            except Exception:
                pass

            if not _keyword_match(title + " " + tags):
                continue

            desc = clean_html(job.get("jobDescription", job.get("description", "")))
            jobs_found.append(_make_job(title, company, link, location or "Remote", "Jobicy 💼", full_date[:10], desc))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break

    except Exception as e:
        print(f"  [Jobicy] Error: {e}")

    print(f"  [Jobicy] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🕷️  SCRAPER 3 — Arbeitnow API (Free, No Key)
# ──────────────────────────────────────────────────

def scrape_arbeitnow():
    """Queries the free Arbeitnow public API — works very reliably."""
    print("[Radar] Scanning Arbeitnow API...")
    jobs_found = []

    try:
        url = "https://www.arbeitnow.com/api/job-board-api?page=1"
        resp = _api_request(url)
        if not resp:
            print("  [Arbeitnow] No response")
            return []

        data = resp.json()
        for job in data.get("data", []):
            title    = job.get("title", "")
            company  = job.get("company_name", "Unknown")
            link     = job.get("url", "")
            location = job.get("location", "Remote")
            remote   = job.get("remote", False)
            tags     = " ".join(job.get("tags", []))
            full_date = str(job.get("created_at", "2025-01-01T"))

            if not link:
                continue

            # Accept remote jobs OR keyword-matching roles
            if not (remote or _keyword_match(title + " " + tags)):
                continue

            loc_str = "Remote 🌍" if remote else location
            desc = clean_html(job.get("description", ""))
            jobs_found.append(_make_job(title, company, link, loc_str, "Arbeitnow 🌐", full_date[:10], desc))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break

    except Exception as e:
        print(f"  [Arbeitnow] Error: {e}")

    print(f"  [Arbeitnow] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🕷️  SCRAPER 4 — RemoteOK API (Fixed headers)
# ──────────────────────────────────────────────────

def scrape_remoteok():
    print("[Radar] Scanning RemoteOK API...")
    jobs_found = []

    try:
        resp = _api_request("https://remoteok.com/api")
        if not resp:
            print("  [RemoteOK] No response")
            return []

        data = resp.json()
        for job in data[1:]:  # First item is metadata, skip it
            title   = job.get("position", "")
            company = job.get("company", "Unknown")
            link    = job.get("url", "")
            tags    = " ".join(job.get("tags", []))
            full_date = str(job.get("date", "2025-01-01T"))
            date_year = full_date[:4]

            if not link:
                continue
            try:
                if int(date_year) < FILTER_YEAR:
                    continue
            except Exception:
                pass

            if not _keyword_match(title + " " + tags):
                continue

            desc = clean_html(job.get("description", ""))
            jobs_found.append(_make_job(title, company, link, "Remote 🌍", "RemoteOK 🌏", full_date[:10], desc))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break

    except Exception as e:
        print(f"  [RemoteOK] Error: {e}")

    print(f"  [RemoteOK] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 📤  TELEGRAM SENDER
# ──────────────────────────────────────────────────

# NOTE: send_radar_telegram function is defined below (after all scrapers)

# ──────────────────────────────────────────────────
#   MAIN RUNNER
# ──────────────────────────────────────────────────

# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 5 — Adzuna India (Free API, Real Indian Jobs)
# Adzuna has a generous free tier — sign up at api.adzuna.com
# ──────────────────────────────────────────────────

def scrape_adzuna_india():
    """Queries Adzuna India API for fresher tech jobs. Get free keys at api.adzuna.com"""
    print("[Radar] Scanning Adzuna India...")
    jobs_found = []

    app_id  = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")

    if not app_id or not app_key:
        print("  [Adzuna] Skipped — set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env (free at api.adzuna.com)")
        return []

    import urllib.parse
    # Broader keywords to find more jobs
    for kw in ["software engineer", "react developer", "python developer", "frontend developer"]:
        try:
            # Sort by date so it shows days, then weeks, then months
            url = (
                f"https://api.adzuna.com/v1/api/jobs/in/search/1"
                f"?app_id={app_id}&app_key={app_key}"
                f"&what={urllib.parse.quote(kw)}&where=Tamil+Nadu"
                f"&results_per_page=30&content-type=application/json"
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
                location = job.get("location", {}).get("display_name", "India")
                full_created = str(job.get("created", "2025-01-01T"))

                if not link or not _keyword_match(title):
                    continue

                desc = clean_html(job.get("description", ""))
                jobs_found.append(_make_job(title, company, link, location, "Adzuna India 🇮🇳", full_created[:10], desc))
                if len(jobs_found) >= MAX_PER_SOURCE:
                    break

            if len(jobs_found) >= MAX_PER_SOURCE:
                break
        except Exception as e:
            print(f"  [Adzuna] Error: {e}")
        # Wait longer between requests to satisfy the 1-2 minute search request and avoid rate limits
        time.sleep(5.0)

    print(f"  [Adzuna India] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 6 — Internshala via Playwright (JavaScript Rendered)
# Only runs if Playwright is available
# ──────────────────────────────────────────────────

def scrape_internshala():
    """Uses Playwright to render Internshala (JS-heavy site)."""
    print("[Radar] Scanning Internshala (Playwright)...")
    jobs_found = []

    try:
        from playwright.sync_api import sync_playwright
        from bs4 import BeautifulSoup

        urls_to_scan = [
            "https://internshala.com/jobs/fresher-jobs/",
            "https://internshala.com/jobs/work-from-home-jobs/",
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
            )

            for url in urls_to_scan:
                try:
                    page.goto(url, timeout=20000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)  # Let JS render
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    # Try multiple selectors
                    cards = (
                        soup.find_all("div", class_="individual_internship") or
                        soup.find_all("div", class_=lambda c: c and "internship_meta" in str(c)) or
                        soup.find_all("div", attrs={"data-internship_id": True})
                    )

                    for card in cards:
                        try:
                            title_tag   = card.find("h3") or card.find("h2")
                            company_tag = card.find("a", class_="link_display_like_text") or card.find("p", class_="company-name")
                            link_tag    = card.find("a", href=True)

                            if not title_tag or not link_tag:
                                continue

                            title   = title_tag.get_text(strip=True)
                            company = company_tag.get_text(strip=True) if company_tag else "See Link"
                            href    = link_tag["href"]
                            link    = href if href.startswith("http") else "https://internshala.com" + href

                            if not _keyword_match(title):
                                continue

                            jobs_found.append(_make_job(title, company, link, "India", "Internshala 🎓"))
                            if len(jobs_found) >= MAX_PER_SOURCE:
                                break
                        except Exception:
                            continue

                    if len(jobs_found) >= MAX_PER_SOURCE:
                        break

                except Exception as e:
                    print(f"  [Internshala] Page error: {e}")

            browser.close()

    except ImportError:
        print("  [Internshala] Playwright not available — skipping")
    except Exception as e:
        print(f"  [Internshala] Error: {e}")

    print(f"  [Internshala] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 7 — Foundit India (Monster India) — JSON API
# ──────────────────────────────────────────────────

def scrape_foundit():
    """Queries Foundit (formerly Monster India) for fresher jobs."""
    print("[Radar] Scanning Foundit (Monster India)...")
    jobs_found = []

    try:
        # Foundit has a public search endpoint
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.foundit.in/",
            "Origin": "https://www.foundit.in",
        }
        url = "https://www.foundit.in/middleware/jobsearch/v2/search?query=software+engineer+fresher&location=Tamil+Nadu&experience=0-1&limit=20&sort=1"
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code != 200:
            print(f"  [Foundit] Got {resp.status_code}")
            return []

        data = resp.json()
        for job in data.get("jobSearchResponse", {}).get("data", []) or data.get("data", []):
            title    = job.get("designation", "") or job.get("title", "")
            company  = job.get("companyName", "Unknown")
            link     = job.get("jdURL", "") or job.get("applyUrl", "")
            location = job.get("location", "India")

            if not title or not link:
                continue

            full_link = link if link.startswith("http") else "https://www.foundit.in" + link

            if not _keyword_match(title):
                continue

            desc = clean_html(job.get("description", job.get("jobDescription", "")))
            jobs_found.append(_make_job(title, company, full_link, location, "Foundit 🔍", description=desc))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break

    except Exception as e:
        print(f"  [Foundit] Error: {e}")

    print(f"  [Foundit] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🇮🇳  SCRAPER 8 — Unstop (Campus Hiring)
# ──────────────────────────────────────────────────

def scrape_unstop():
    """Queries Unstop public job listings API for fresher campus roles."""
    print("[Radar] Scanning Unstop...")
    jobs_found = []
    try:
        url = "https://unstop.com/api/public/opportunity/search-result?opportunity=jobs&per_page=20&oppstatus=open"
        resp = _api_request(url)
        if not resp:
            print("  [Unstop] No response")
            return []
        data = resp.json()
        items = (data.get("data", {}).get("data", [])
                 if isinstance(data.get("data"), dict)
                 else data.get("data", []))
        for job in items:
            title   = job.get("title", "")
            org     = job.get("organisation", {})
            company = org.get("name", "Unknown") if isinstance(org, dict) else "Unknown"
            slug    = job.get("public_url", "") or job.get("slug", "")
            link    = slug if slug.startswith("http") else f"https://unstop.com/{slug}"
            if not title or not slug:
                continue
            if not _keyword_match(title):
                continue
            desc = clean_html(job.get("description", ""))
            jobs_found.append(_make_job(title, company, link, "India", "Unstop 🏆", description=desc))
            if len(jobs_found) >= MAX_PER_SOURCE:
                break
    except Exception as e:
        print(f"  [Unstop] Error: {e}")
    print(f"  [Unstop] Found {len(jobs_found)} jobs.")
    return jobs_found


# ──────────────────────────────────────────────────
# 🔵  SCRAPER 9 — LinkedIn + Indeed via JobSpy
# python-jobspy handles LinkedIn stealth automatically
# ──────────────────────────────────────────────────

def scrape_linkedin_indeed():
    """Uses python-jobspy to scrape LinkedIn and Indeed India jobs."""
    print("[Radar] Scanning LinkedIn + Indeed (JobSpy)...")
    jobs_found = []

    try:
        from jobspy import scrape_jobs

        search_queries = [
            "software engineer fresher",
            "react developer fresher",
            "frontend developer",
        ]

        for query in search_queries:
            try:
                df = scrape_jobs(
                    site_name=["linkedin", "indeed"],
                    search_term=query,
                    location="Chennai, Tamil Nadu, India",
                    results_wanted=5,
                    hours_old=72,           # Only last 3 days
                    country_indeed="India",
                    linkedin_fetch_description=False,  # Faster
                    verbose=0,
                )

                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    title   = str(row.get("title", ""))
                    company = str(row.get("company", "Unknown"))
                    link    = str(row.get("job_url", ""))
                    location = str(row.get("location", "India"))
                    site    = str(row.get("site", "linkedin")).title()

                    if not link or link == "nan":
                        continue
                    if not _keyword_match(title):
                        continue

                    source = f"LinkedIn 🔵" if "linkedin" in site.lower() else f"Indeed India 🟢"
                    desc_val = str(row.get("description", ""))
                    desc = clean_html(desc_val) if desc_val and desc_val != "nan" else ""
                    jobs_found.append(_make_job(title, company, link, location, source, description=desc))
                    if len(jobs_found) >= MAX_PER_SOURCE:
                        break

            except Exception as e:
                print(f"  [JobSpy] Error for '{query}': {e}")

            time.sleep(2.0)   # Avoid LinkedIn rate-limit

            if len(jobs_found) >= MAX_PER_SOURCE:
                break

    except ImportError:
        print("  [JobSpy] python-jobspy not installed. Run: pip install python-jobspy")
    except Exception as e:
        print(f"  [LinkedIn/Indeed] Error: {e}")

    print(f"  [LinkedIn + Indeed] Found {len(jobs_found)} jobs.")
    return jobs_found




def escape_md(text):
    if not text:
        return ""
    return str(text).replace("*", "").replace("_", " ").replace("[", "(").replace("]", ")").replace("`", "")

def send_radar_telegram(new_jobs):
    """Sends ALL found jobs in a single consolidated Telegram message — no separate Apply buttons."""
    try:
        import telebot
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Load bot token with sanitization
        _raw_token = os.getenv("TELEGRAM_TOKEN", "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4")
        bot_token = str(_raw_token).strip().strip('"').strip("'")
        if bot_token.lower().startswith("bot"):
            bot_token = bot_token[3:]
        if not bot_token:
            bot_token = "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4"

        _raw_chat = os.getenv("TELEGRAM_CHAT_ID", "7607565831")
        chat_id = str(_raw_chat).strip().strip('"').strip("'")
        if not chat_id and os.path.exists("chat_id.json"):
            try:
                with open("chat_id.json", "r") as f:
                    data = json.load(f)
                    chat_id = str(data.get("chat_id", "7607565831")).strip()
            except: pass
        if not chat_id:
            chat_id = "7607565831"
        
        if not bot_token or not chat_id:
            print("[Radar] Telegram not configured. Skipping instant notification.")
            return
        
        radar_bot = telebot.TeleBot(bot_token, parse_mode=None)
        
        # Build source breakdown summary
        source_counts = {}
        for job in new_jobs:
            src = job.get("source", "Unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        
        source_summary = "\n".join([f"  {escape_md(src)}: *{cnt}* jobs" for src, cnt in source_counts.items()])
        
        total = len(new_jobs)
        now_str = datetime.now().strftime('%I:%M %p, %d %b %Y')
        
        # Build jobs grouped by source
        grouped_jobs = {}
        for job in new_jobs:
            src = job.get("source", "Unknown")
            grouped_jobs.setdefault(src, []).append(job)
            
        job_lines = []
        global_idx = 1
        
        job_entries = []
        global_idx = 1
        
        for src, jobs in grouped_jobs.items():
            section_header = f"📡 *{escape_md(src)}*\n━━━━━━━━━━━━━━━━━━━━━━"
            job_entries.append(section_header)
            for job in jobs:
                title   = escape_md(job.get("title", "Unknown Role"))[:60]
                company = escape_md(job.get("company", "Unknown Company"))[:35]
                loc     = escape_md(job.get("location", "Remote / PAN India"))[:35]
                link    = job.get("link", "").strip()
                date_str = job.get("date_posted", "")
                desc    = escape_md(clean_html(job.get("description", "")))[:110]
                if desc:
                    desc = desc.replace("\n", " ").strip()
                
                # Time display
                time_tag = "🟢 Today"
                if date_str and len(date_str) >= 10:
                    try:
                        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                        days = (datetime.now() - dt).days
                        if days == 0: time_tag = "🟢 Today"
                        elif days == 1: time_tag = "🟡 Yesterday"
                        elif days <= 7: time_tag = f"📅 {days}d ago"
                        else: time_tag = f"📆 {date_str[:10]}"
                    except Exception:
                        time_tag = "🟢 Recent"
                
                # Rich multi-line job card with location and work detail
                entry = (
                    f"*{global_idx}.* [{title}]({link})\n"
                    f"   🏢 *Company:* _{company}_\n"
                    f"   📍 *Location:* `{loc}`\n"
                    f"   🕒 *Posted:* {time_tag}"
                )
                if desc and len(desc) > 15:
                    entry += f"\n   📝 *Work Detail:* _{desc}_"
                
                job_entries.append(entry)
                global_idx += 1
        
        # Split into smart character-length chunks (Telegram max 4096 chars)
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
        
        # Header
        header = (
            f"📡 *JOB RADAR REPORT*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆕 Found *{total}* New Opportunities!\n"
            f"🕒 {now_str}\n"
            f"📊 *Sources:*\n{source_summary}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                msg = header + chunk
            else:
                msg = f"📡 *Opportunities (Part {idx+1}/{len(chunks)})*\n\n" + chunk
            
            # Add footer to the last chunk
            if idx == len(chunks) - 1:
                msg += (
                    f"\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 *Total:* {total} jobs across {len(source_counts)} sources\n"
                    f"⏰ Next scan in 1 hour (24/7 Cloud)\n"
                    f"🟢 = Today | 🟡 = Yesterday | 📅 = This week\n"
                    f"_Tap any job title link to view & apply directly!_"
                )
            
            try:
                radar_bot.send_message(chat_id, msg, parse_mode="Markdown", disable_web_page_preview=True)
                if idx < len(chunks) - 1:
                    time.sleep(0.6)  # Small delay between chunks
            except Exception as msg_e:
                print(f"[Radar] Failed to send chunk #{idx+1}: {msg_e}")
                # Fallback: try without Markdown if formatting fails
                try:
                    plain_msg = msg.replace("*", "").replace("_", "").replace("`", "")
                    radar_bot.send_message(chat_id, plain_msg[:4096], parse_mode=None, disable_web_page_preview=True)
                except: pass
                
    except Exception as e:
        print(f"[Radar] Telegram notification failed: {e}")


def run_radar():
    print("\n" + "=" * 50)
    print("[Radar] JOB RADAR STARTING SCAN")
    print(f"   Global   : Remotive, Jobicy, Arbeitnow, RemoteOK")
    print(f"   India    : LinkedIn, Indeed, Adzuna, Internshala, Unstop")
    print(f"   Locations: Tamil Nadu + Remote")
    print(f"   Year     : {FILTER_YEAR}+")
    print("=" * 50 + "\n")

    seen_jobs = load_seen_jobs()
    all_jobs  = []

    # Run all scrapers concurrently using a ThreadPoolExecutor
    import concurrent.futures
    scrapers = {
        "Remotive": scrape_remotive,
        "Jobicy": scrape_jobicy,
        "Arbeitnow": scrape_arbeitnow,
        "RemoteOK": scrape_remoteok,
        "LinkedIn/Indeed": scrape_linkedin_indeed,
        "Adzuna": scrape_adzuna_india,
        "Internshala": scrape_internshala,
        "Unstop": scrape_unstop,
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(scrapers)) as executor:
        future_to_name = {executor.submit(func): name for name, func in scrapers.items()}
        try:
            for future in concurrent.futures.as_completed(future_to_name, timeout=35):
                name = future_to_name[future]
                try:
                    res = future.result()
                    if res:
                        all_jobs.extend(res)
                except Exception as e:
                    print(f"  [Radar Concurrent] Scraper '{name}' raised exception: {e}")
        except concurrent.futures.TimeoutError:
            print("  [Radar] ThreadPool timeout (35s) reached. Proceeding with collected jobs.")

    new_jobs = []
    for job in all_jobs:
        link = job["link"]
        if link and link not in seen_jobs:
            new_jobs.append(job)
            mark_seen(link)
            seen_jobs.add(link)

    # Sort newest-posted first. date_posted is normally "YYYY-MM-DD" but some
    # sources pass a full ISO timestamp; take the first 10 chars and fall back
    # to an empty string (sorts last) if it can't be parsed.
    def _posted_key(job):
        raw = str(job.get("date_posted", ""))[:10]
        try:
            return datetime.strptime(raw, "%Y-%m-%d")
        except Exception:
            return datetime.min
    new_jobs.sort(key=_posted_key, reverse=True)

    print(f"\n[Radar] Total new unique jobs: {len(new_jobs)}")

    # Load previous jobs so dashboard always has data to show
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
        print("[Radar] No new jobs this cycle. Previous results retained on dashboard.")

    print("[Radar] Scan complete.\n")
    return new_jobs

if __name__ == "__main__":
    run_radar()

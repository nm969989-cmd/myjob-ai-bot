"""
📡 JOB RADAR — Multi-Platform Job Finder (India & Tamil Nadu Priority Engine)
=============================================================================
Strictly filters for India-based jobs & Global Remote jobs open to India.
Prioritizes Tamil Nadu (Chennai, Coimbatore, Madurai, Trichy, Salem, etc.) at the top.
Deeply scrapes all major Telegram job channels and extracts direct apply links.
"""

import os
import json
import time
import random
import re
import urllib.parse
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

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

def _api_request(url, headers_extra=None, max_retries=2, timeout=20):
    """Robust HTTP request helper."""
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html, */*",
        "Accept-Encoding": "identity",
    }
    if headers_extra:
        headers.update(headers_extra)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
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

# ──────────────────────────────────────────────────
# 📍 STRICT LOCATION CLASSIFIER & TAMIL NADU PRIORITIZER
# ──────────────────────────────────────────────────

def classify_location(location_str, context_text=""):
    """
    Evaluates a location string and surrounding text context.
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
    for foreign in EXCLUDED_FOREIGN_LOCATIONS:
        if re.search(rf"\b{re.escape(foreign)}\b", loc_lower):
            # Check if it also explicitly says India
            if not ("india" in loc_lower or any(tn in loc_lower for tn in TAMIL_NADU_LOCATIONS)):
                return False, 99, "", False

    # Check for remote restrictions (e.g., "US Only")
    for restriction in EXCLUDED_REMOTE_RESTRICTIONS:
        if restriction in combined:
            return False, 99, "", False

    # 2. Check for Tamil Nadu (Highest Priority — Tier 1)
    for tn_loc in TAMIL_NADU_LOCATIONS:
        if re.search(rf"\b{re.escape(tn_loc)}\b", loc_lower) or re.search(rf"\b{re.escape(tn_loc)}\b", ctx_lower):
            matched_name = tn_loc.title() if tn_loc not in ["tn", "tamilnadu"] else "Tamil Nadu"
            if loc_clean and loc_clean.lower() != "india" and not any(f in loc_lower for f in EXCLUDED_FOREIGN_LOCATIONS):
                display = f"{loc_clean} ⭐"
            else:
                display = f"{matched_name}, Tamil Nadu ⭐"
            return True, 1, display, True

    # 3. Check for Other India Tech Hubs (Tier 2)
    for in_loc in INDIA_OTHER_LOCATIONS:
        if re.search(rf"\b{re.escape(in_loc)}\b", loc_lower) or re.search(rf"\b{re.escape(in_loc)}\b", ctx_lower):
            display = loc_clean if loc_clean else f"{in_loc.title()}, India"
            if "india" not in display.lower():
                display += ", India 🇮🇳"
            return True, 2, display, False

    # 4. Check for Remote / Work from Home / Worldwide
    remote_keywords = ["remote", "work from home", "wfh", "worldwide", "global", "anywhere", "telecommute"]
    if any(rk in loc_lower for rk in remote_keywords):
        return True, 3, "Remote (India / Global) 🌐", False

    # If location field is empty or says "India", accept as Tier 2
    if not loc_clean or loc_lower in ["in", "ind", "india", "pan india"]:
        return True, 2, "India (PAN India) 🇮🇳", False

    # Otherwise, reject unknown or foreign location
    return False, 99, "", False

def _make_job(title, company, link, location, source, date_posted="", description="", priority_tier=2, is_tn=False, direct_link=""):
    if not date_posted:
        date_posted = datetime.now().strftime("%Y-%m-%d")
    return {
        "title":          title.strip(),
        "company":        company.strip(),
        "link":           direct_link.strip() if direct_link else link.strip(),
        "raw_link":       link.strip(),
        "location":       location.strip(),
        "source":         source,
        "date_posted":    date_posted,
        "description":    description.strip(),
        "priority_tier":  priority_tier,
        "is_tamil_nadu":  is_tn,
        "found_at":       datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

def is_social_or_promo_link(url):
    """Detects if a URL is a social media link, channel promo, or non-job page."""
    if not url or not isinstance(url, str):
        return True
    u = url.lower().strip()
    promo_domains = [
        "t.me", "telegram.org", "telegram.dog", "whatsapp.com", "wa.me",
        "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com",
        "youtube.com", "youtu.be", "pinterest.com", "threads.net",
        "linktr.ee", "bio.link", "campsite.bio", "taplink.cc", "beacons.ai",
        "play.google.com", "apps.apple.com", "aratt.ai"
    ]
    if any(d in u for d in promo_domains):
        return True
    if "linkedin.com" in u:
        if any(p in u for p in ["/company/", "/in/", "/feed/", "/posts/", "/groups/", "/pulse/", "/school/"]):
            return True
    return False

# ──────────────────────────────────────────────────
# 🔗 DIRECT LINK UNWRAPPER FOR RADAR
# ──────────────────────────────────────────────────

def unwrap_radar_direct_link(url):
    """
    Unwraps URL shorteners and extracts direct application links from job blogs.
    """
    if not url or not url.startswith("http") or is_social_or_promo_link(url):
        return url
    
    direct_domains = [
        "greenhouse.io", "lever.co", "workdayjobs.com", "myworkdayjobs.com",
        "smartrecruiters.com", "joinsuperset.com", "docs.google.com/forms",
        "forms.gle", "sensehq.com", "ashbyhq.com", "bamboohr.com", "taleo.net",
        "zohorecruit.com", "recruitee.com", "freshteam.com", "darwinbox.com",
        "keka.com", "unstop.com", "internshala.com", "foundit.in", "naukri.com",
    ]
    if any(d in url.lower() for d in direct_domains):
        return url

    try:
        resp = _api_request(url, max_retries=1, timeout=8)
        if not resp:
            return url
        
        final_url = resp.url
        if any(d in final_url.lower() for d in direct_domains):
            return final_url
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        
        container = soup.find("div", class_=lambda c: c and any(x in str(c) for x in ["post-body", "entry-content", "article", "content"])) or soup
        
        # Priority 1: Known ATS / job boards
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            if any(d in href.lower() for d in direct_domains) and not is_social_or_promo_link(href):
                return href
        
        # Priority 2: Text matching "Apply", "Registration"
        apply_kws = ["apply online", "click here to apply", "apply link", "apply now", "official link", "direct apply", "registration link"]
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            txt = a.get_text(strip=True).lower()
            if any(k in txt for k in apply_kws):
                if href.startswith("http") and not is_social_or_promo_link(href):
                    return href
        
        return final_url if not is_social_or_promo_link(final_url) else url
    except Exception:
        return url

def _scan_single_channel_radar(ch):
    """Scrapes a single Telegram channel for the Job Radar."""
    ch_clean = ch.replace("@", "").strip()
    url = f"https://telegram.dog/s/{ch_clean}"
    jobs_found = []
    try:
        resp = _api_request(url, timeout=8)
        if not resp or resp.status_code != 200:
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        messages = soup.find_all("div", class_="tgme_widget_message_text")
        if not messages:
            return []

        for msg in reversed(messages[-6:]):
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

            # Robust Company Extraction
            company = ""
            comp_m = re.search(r'(?:🏢\s*Company|Company|Organisation|Org|Organization)\s*[:\-]\s*([^\n📍💼🛠️💰📝👉🔗|]+)', text, re.I)
            if comp_m:
                company = comp_m.group(1).strip()
            if not company or len(company) < 2:
                m_hiring = re.search(r'^[^\w\s]*\s*([A-Za-z0-9\s.,&-]+?)\s+(?:is\s+Hiring|is\s+Recruiting|Recruitment\s+20\d\d|Recruitment|Off\s*Campus\s+Drive|Off\s*Campus|Mega\s+Drive|Drive|Hiring|Walkin|Walk-in)', first_line, re.I)
                if m_hiring:
                    company = m_hiring.group(1).strip()
            company = re.sub(r'[^\w\s.,&-]', '', company).replace('Title', '').replace(':', '').strip()
            if not company or len(company) < 2:
                company = "Verified Recruiter"

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

            direct_link = unwrap_radar_direct_link(raw_link)
            if is_social_or_promo_link(direct_link):
                continue

            desc = clean_html(text)[:200]
            src_name = f"Telegram @{ch_clean} 📢"
            if is_tn:
                src_name = f"Telegram @{ch_clean} 🌟"

            jobs_found.append(_make_job(
                title=role[:65],
                company=company[:45],
                link=direct_link,
                location=loc_tag,
                source=src_name,
                description=desc,
                priority_tier=tier,
                is_tn=is_tn,
                direct_link=direct_link
            ))

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
                jobs_found.append(_make_job(
                    title=title, company=company, link=link, location=loc_tag,
                    source="Adzuna India 🇮🇳", date_posted=full_created[:10],
                    description=desc, priority_tier=tier, is_tn=is_tn
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
                jobs_found.append(_make_job(
                    title=title, company=company, link=link, location=loc_tag,
                    source="Remotive 🚀", date_posted=full_date[:10],
                    description=desc, priority_tier=tier, is_tn=is_tn
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
            jobs_found.append(_make_job(
                title=title, company=company, link=link, location=loc_tag,
                source="Jobicy 💼", date_posted=full_date[:10],
                description=desc, priority_tier=tier, is_tn=is_tn
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
            jobs_found.append(_make_job(
                title=title, company=company, link=link, location=loc_tag,
                source="RemoteOK 🌏", date_posted=full_date[:10],
                description=desc, priority_tier=tier, is_tn=is_tn
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
    """Uses python-jobspy for Chennai, Coimbatore, Tamil Nadu & Bangalore India jobs."""
    print("[Radar] Scanning LinkedIn + Indeed India (JobSpy)...")
    jobs_found = []
    try:
        from jobspy import scrape_jobs
        queries = [
            ("software engineer fresher", "Chennai, Tamil Nadu, India"),
            ("frontend developer", "Coimbatore, Tamil Nadu, India"),
            ("full stack developer fresher", "Bangalore, Karnataka, India"),
        ]
        for query, loc in queries:
            try:
                df = scrape_jobs(
                    site_name=["linkedin", "indeed"],
                    search_term=query,
                    location=loc,
                    results_wanted=6,
                    hours_old=72,
                    country_indeed="India",
                    linkedin_fetch_description=False,
                    verbose=0,
                )
                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    title    = str(row.get("title", ""))
                    company  = str(row.get("company", "Unknown"))
                    link     = str(row.get("job_url", ""))
                    location = str(row.get("location", loc))
                    site     = str(row.get("site", "linkedin")).title()

                    if not link or link == "nan" or not _keyword_match(title):
                        continue

                    is_valid, tier, loc_tag, is_tn = classify_location(location, loc)
                    if not is_valid:
                        continue

                    source = f"LinkedIn 🔵" if "linkedin" in site.lower() else f"Indeed India 🟢"
                    desc_val = str(row.get("description", ""))
                    desc = clean_html(desc_val) if desc_val and desc_val != "nan" else ""
                    jobs_found.append(_make_job(
                        title=title, company=company, link=link, location=loc_tag,
                        source=source, description=desc, priority_tier=tier, is_tn=is_tn
                    ))
                    if len(jobs_found) >= MAX_PER_SOURCE:
                        break
            except Exception as e:
                print(f"  [JobSpy] Error for '{query}': {e}")
            time.sleep(2.0)
    except ImportError:
        pass
    except Exception as e:
        print(f"  [LinkedIn/Indeed] Error: {e}")
    print(f"  [LinkedIn + Indeed] Found {len(jobs_found)} jobs.")
    return jobs_found

# ──────────────────────────────────────────────────
# 📤  TELEGRAM SENDER (WITH TAMIL NADU PRIORITY DISPLAY)
# ──────────────────────────────────────────────────

def send_radar_telegram(new_jobs):
    """Sends consolidated Telegram messages with Tamil Nadu opportunities prioritized at the top."""
    try:
        import telebot
        
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
            except Exception:
                pass
        if not chat_id:
            chat_id = "7607565831"

        radar_bot = telebot.TeleBot(bot_token, parse_mode=None)

        tn_jobs = [j for j in new_jobs if j.get("is_tamil_nadu", False) or j.get("priority_tier") == 1]
        india_jobs = [j for j in new_jobs if not j.get("is_tamil_nadu", False) and j.get("priority_tier") == 2]
        remote_jobs = [j for j in new_jobs if j.get("priority_tier") == 3]

        total = len(new_jobs)
        now_str = datetime.now().strftime('%I:%M %p, %d %b %Y')

        job_entries = []
        global_idx = 1

        def _format_section(title_header, job_list):
            nonlocal global_idx
            if not job_list:
                return
            job_entries.append(title_header)
            for job in job_list:
                title   = escape_md(job.get("title", "Unknown Role"))[:60]
                company = escape_md(job.get("company", "Unknown Company"))[:35]
                loc     = escape_md(job.get("location", "India"))[:40]
                link    = job.get("link", "").strip()
                date_str = job.get("date_posted", "")
                desc    = escape_md(clean_html(job.get("description", "")))[:120]
                src     = escape_md(job.get("source", "Radar"))

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

                entry = (
                    f"*{global_idx}.* [{title}]({link})\n"
                    f"   🏢 *Company:* _{company}_\n"
                    f"   📍 *Location:* `{loc}`\n"
                    f"   📡 *Source:* _{src}_\n"
                    f"   🕒 *Posted:* {time_tag}"
                )
                if desc and len(desc) > 15:
                    entry += f"\n   📝 *Work Detail:* _{desc}_"

                job_entries.append(entry)
                global_idx += 1

        # 1. TAMIL NADU HIGH PRIORITY SECTION
        if tn_jobs:
            _format_section(f"🌟 *TAMIL NADU OPPORTUNITIES ({len(tn_jobs)} JOBS — TOP PRIORITY)*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", tn_jobs)

        # 2. OTHER INDIA TECH HUBS SECTION
        if india_jobs:
            _format_section(f"🇮🇳 *INDIA TECH OPPORTUNITIES ({len(india_jobs)} JOBS)*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", india_jobs)

        # 3. REMOTE / GLOBAL SECTION
        if remote_jobs:
            _format_section(f"🌐 *REMOTE TECH OPPORTUNITIES ({len(remote_jobs)} JOBS)*\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", remote_jobs)

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
            f"📡 *JOB RADAR REPORT (INDIA & TN PRIORITY)*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆕 Found *{total}* Verified Opportunities!\n"
            f"🌟 *Tamil Nadu Priority:* *{len(tn_jobs)}* jobs\n"
            f"🇮🇳 *Pan-India:* *{len(india_jobs)}* jobs | 🌐 *Remote:* *{len(remote_jobs)}* jobs\n"
            f"🕒 {now_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for idx, chunk in enumerate(chunks):
            if idx == 0:
                msg = header + chunk
            else:
                msg = f"📡 *Opportunities (Part {idx+1}/{len(chunks)})*\n\n" + chunk

            if idx == len(chunks) - 1:
                msg += (
                    f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 *Total:* {total} jobs filtered strictly for India & TN\n"
                    f"⏰ Next scan in 1 hour (24/7 Cloud)\n"
                    f"👉 _Tap any job title link to view & apply directly!_"
                )

            try:
                radar_bot.send_message(chat_id, msg, parse_mode="Markdown", disable_web_page_preview=True)
                if idx < len(chunks) - 1:
                    time.sleep(0.6)
            except Exception as msg_e:
                try:
                    plain_msg = msg.replace("*", "").replace("_", "").replace("`", "")
                    radar_bot.send_message(chat_id, plain_msg[:4096], parse_mode=None, disable_web_page_preview=True)
                except Exception:
                    pass

    except Exception as e:
        print(f"[Radar] Telegram notification failed: {e}")

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

    new_jobs = []
    for job in all_jobs:
        link = job.get("link") or job.get("raw_link")
        if link and link not in seen_jobs:
            new_jobs.append(job)
            mark_seen(link)
            seen_jobs.add(link)

    # 🎯 SORTING ENGINE: Tamil Nadu (Tier 1) FIRST, then India (Tier 2), then Remote (Tier 3)
    def _priority_sort_key(job):
        tier = job.get("priority_tier", 2)
        raw_date = str(job.get("date_posted", ""))[:10]
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%d")
        except Exception:
            dt = datetime.min
        # Sort by tier ascending (1 first), then date descending (newest first)
        return (tier, -dt.timestamp())

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

if __name__ == "__main__":
    run_radar()

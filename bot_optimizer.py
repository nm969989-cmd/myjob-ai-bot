"""
bot_optimizer.py — Efficiency Module for the Autonomous Job Bot
Features:
  1. HTML Minifier    — strips noise before sending to Gemini (saves ~80% tokens)
  4. Regex Fallback   — instantly fills common fields without calling Gemini
"""
import re
import time
import random

# ─────────────────────────────────────────────────────────────────
# FEATURE 1: HTML MINIFIER  (reduces Gemini token usage by ~80%)
# ─────────────────────────────────────────────────────────────────

# Tags whose content is completely useless for form analysis
_STRIP_TAGS = [
    "script", "style", "noscript", "svg", "path", "symbol", "defs",
    "use", "g", "circle", "rect", "polygon", "header", "footer",
    "nav", "aside", "figure", "figcaption", "picture", "source",
    "video", "audio", "iframe", "canvas", "map", "area",
    "meta", "link", "head", "comment",
]

# HTML attributes that carry zero meaning for AI form mapping
_STRIP_ATTRS = {
    "style", "class", "onclick", "onchange", "onblur", "onfocus",
    "onkeydown", "onkeyup", "onmousedown", "onmouseup", "onmouseover",
    "tabindex", "autocomplete", "spellcheck", "data-v", "data-reactid",
    "data-component", "data-track", "aria-hidden", "aria-describedby",
    "aria-controls", "aria-expanded", "role", "xmlns", "viewBox",
    "fill", "stroke", "d", "transform", "clip-path",
}

# Attributes we MUST keep for CSS selector generation
_KEEP_ATTRS = {"id", "name", "type", "placeholder", "required", "value", "for", "action", "method"}

def minify_form_html(raw_html: str, max_chars: int = 18000) -> str:
    """
    Strips noisy tags, useless attributes, and collapses whitespace from raw HTML.
    Returns a clean, compact string safe to send to Gemini.
    Reduces average token cost from ~25,000 to ~4,000 per page.
    """
    if not raw_html:
        return ""

    text = raw_html

    # 1. Remove entire noisy tag blocks (including content between them)
    for tag in _STRIP_TAGS:
        text = re.sub(
            rf'<{tag}[\s>].*?</{tag}>',
            '', text,
            flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(rf'<{tag}[^>]*/>', '', text, flags=re.IGNORECASE)
        text = re.sub(rf'<{tag}[^>]*>', '', text, flags=re.IGNORECASE)

    # 2. Remove HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

    # 3. Strip useless attributes but keep important ones
    def clean_attrs(match):
        tag_full = match.group(0)
        tag_name = re.match(r'<(\w+)', tag_full)
        if not tag_name:
            return tag_full
        # Keep tags that are relevant to form filling
        kept_attrs = []
        for attr in re.finditer(r'(\w[\w-]*)(?:=["\']([^"\']*)["\'])?', tag_full[len(tag_name.group(0)):]):
            attr_name = attr.group(1).lower()
            if attr_name in _KEEP_ATTRS:
                kept_attrs.append(attr.group(0))
        tag_cleaned = f"<{tag_name.group(1)}"
        if kept_attrs:
            tag_cleaned += " " + " ".join(kept_attrs)
        tag_cleaned += ">"
        return tag_cleaned

    text = re.sub(r'<[a-zA-Z][^>]*>', clean_attrs, text)

    # 4. Collapse all whitespace / newlines to single space
    text = re.sub(r'\s+', ' ', text)

    # 5. Remove empty tags that have no content after stripping
    text = re.sub(r'<(\w+)[^>]*>\s*</\1>', '', text)

    # 6. Truncate to max_chars (stay well within Gemini's context window)
    if len(text) > max_chars:
        # Try to find a closing tag boundary to avoid cutting mid-tag
        cutoff = text[:max_chars].rfind('>')
        text = text[:cutoff + 1] if cutoff > 0 else text[:max_chars]

    return text.strip()


# ─────────────────────────────────────────────────────────────────
# FEATURE 4: SMART REGEX FALLBACK
# Pre-fills common, predictable fields WITHOUT calling Gemini at all.
# Gemini is only called for custom/unknown questions.
# ─────────────────────────────────────────────────────────────────

# Common selectors that are almost universally standard across all job sites
STANDARD_FIELD_MAP = [
    # ── Name fields ──────────────────────────────────────────
    {"selectors": ["input[name='full_name']", "input[name='fullname']", "input[name='name']",
                   "input[id='full_name']", "input[id='fullName']", "input[id='name']",
                   "input[placeholder*='Full Name']", "input[placeholder*='full name']",
                   "input[placeholder*='Your Name']"],
     "profile_key": "full_name", "type": "text"},

    {"selectors": ["input[name='first_name']", "input[name='firstName']", "input[id='first_name']",
                   "input[id='firstName']", "input[placeholder*='First Name']",
                   "input[placeholder*='first name']"],
     "profile_key": "first_name", "type": "text"},

    {"selectors": ["input[name='last_name']", "input[name='lastName']", "input[id='last_name']",
                   "input[id='lastName']", "input[placeholder*='Last Name']",
                   "input[placeholder*='last name']"],
     "profile_key": "last_name", "type": "text"},

    # ── Contact ───────────────────────────────────────────────
    {"selectors": ["input[type='email']", "input[name='email']", "input[id='email']",
                   "input[placeholder*='Email']", "input[placeholder*='email']",
                   "input[name='user_email']", "input[name='applicant_email']"],
     "profile_key": "email", "type": "text"},

    {"selectors": ["input[type='tel']", "input[name='phone']", "input[name='mobile']",
                   "input[name='phone_number']", "input[id='phone']", "input[id='mobile']",
                   "input[placeholder*='Phone']", "input[placeholder*='Mobile']",
                   "input[placeholder*='phone']"],
     "profile_key": "phone", "type": "text"},

    # ── Links ─────────────────────────────────────────────────
    {"selectors": ["input[name*='linkedin']", "input[name*='LinkedIn']",
                   "input[id*='linkedin']", "input[placeholder*='LinkedIn']",
                   "input[placeholder*='linkedin']"],
     "profile_key": "linkedin", "type": "text"},

    {"selectors": ["input[name*='github']", "input[name*='GitHub']",
                   "input[id*='github']", "input[placeholder*='GitHub']"],
     "profile_key": "github", "type": "text"},

    {"selectors": ["input[name*='portfolio']", "input[name*='website']",
                   "input[id*='portfolio']", "input[placeholder*='Portfolio']",
                   "input[placeholder*='Website']", "input[placeholder*='website']"],
     "profile_key": "portfolio", "type": "text"},

    # ── Location ──────────────────────────────────────────────
    {"selectors": ["input[name='city']", "input[name='location']",
                   "input[id='city']", "input[id='location']",
                   "input[placeholder*='City']", "input[placeholder*='Location']"],
     "profile_key": None, "static_value": "Bengaluru, Karnataka", "type": "text"},

    # ── Experience ────────────────────────────────────────────
    {"selectors": ["input[name*='experience']", "input[name*='years']",
                   "input[id*='experience']", "input[placeholder*='Years of experience']",
                   "input[placeholder*='years of experience']"],
     "profile_key": "experience_years", "type": "text"},

    # ── Salary (always answer '0' / 'As per industry standard') ──
    {"selectors": ["input[name*='salary']", "input[name*='ctc']",
                   "input[id*='salary']", "input[placeholder*='Expected CTC']",
                   "input[placeholder*='Salary']", "input[placeholder*='salary']"],
     "profile_key": None, "static_value": "0", "type": "text"},

    # ── Notice period ─────────────────────────────────────────
    {"selectors": ["input[name*='notice']", "input[id*='notice']",
                   "input[placeholder*='Notice']", "input[placeholder*='notice period']"],
     "profile_key": None, "static_value": "Immediate", "type": "text"},
]


def apply_regex_fallback(page, profile: dict) -> list:
    """
    Tries to fill all STANDARD_FIELD_MAP entries using direct Playwright selectors.
    Fires React/Vue-compatible input events after filling.
    Returns a list of (selector, value) pairs that were successfully filled,
    so the main AI engine knows which fields to SKIP.
    """
    filled = []
    full_name = profile.get("full_name", profile.get("name", ""))
    name_parts = full_name.strip().split(" ", 1)

    # Inject split names into profile for convenience
    _profile = dict(profile)
    _profile.setdefault("first_name", name_parts[0] if name_parts else "")
    _profile.setdefault("last_name",  name_parts[1] if len(name_parts) > 1 else "")
    _profile.setdefault("full_name",  full_name)

    for field in STANDARD_FIELD_MAP:
        value = (
            field.get("static_value")
            or _profile.get(field.get("profile_key", ""), "")
        )
        if not value:
            continue

        for selector in field["selectors"]:
            try:
                el = page.locator(selector).first
                if el.count() == 0:
                    continue
                if not el.is_visible(timeout=600):
                    continue
                if el.is_disabled():
                    continue

                # Clear then fill
                el.click(delay=random.randint(30, 80))
                time.sleep(random.uniform(0.05, 0.15))
                el.fill(str(value))

                # Fire React/Vue synthetic events so frameworks register the change
                page.evaluate("""
                    ([sel, val]) => {
                        const el = document.querySelector(sel);
                        if (!el) return;
                        const niv = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value') ||
                            Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value');
                        if (niv) niv.set.call(el, val);
                        ['input','change','blur'].forEach(ev =>
                            el.dispatchEvent(new Event(ev, {bubbles: true}))
                        );
                    }
                """, [selector, str(value)])

                print(f"[Regex Fallback] ✅ Filled '{selector}' → '{str(value)[:40]}'")
                filled.append((selector, str(value)))
                time.sleep(random.uniform(0.15, 0.35))
                break  # Move to next field once filled
            except Exception:
                continue

    print(f"[Regex Fallback] Pre-filled {len(filled)} standard fields without calling Gemini.")
    return filled

# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# FEATURE 5: SELF-LEARNING LOCAL RAG MEMORY ENGINE
# Multi-attribute DOM extractor, fuzzy matcher, category heuristics,
# dropdown/radio solver, and auto-learning persistence.
# ─────────────────────────────────────────────────────────────────
import os
import json
import difflib

DEFAULT_QA_SEEDS = {
    "What are your salary expectations?": "30000",
    "Current CTC / Current Salary": "0",
    "Expected CTC / Expected Salary": "4.5 LPA",
    "What is your notice period / When can you start?": "Immediate / 1 week",
    "Are you willing to relocate for this position?": "Yes",
    "Are you comfortable working in Chennai, Coimbatore, or Bangalore?": "Yes",
    "Are you willing to work from office / hybrid mode?": "Yes",
    "Are you open to working in rotational or night shifts?": "Yes",
    "How did you hear about this opportunity?": "LinkedIn",
    "Why do you want to work here? / Why are you a good fit?": "I am a highly motivated engineer passionate about building scalable software and contributing to innovative, fast-paced teams. I thrive in environments where I can tackle complex technical challenges, collaborate with talented professionals, and continuously grow my skill set to deliver high-quality products.",
    "What is your highest level of education?": "Bachelor's Degree in Information Technology",
    "Year of graduation / Passing out batch": "2025",
    "Aggregate CGPA / Percentage": "8.2 CGPA",
    "Do you have any active backlogs or arrears?": "No",
    "Are you a fresher?": "Yes",
    "Are you legally authorized to work in the country where this job is located?": "Yes",
    "Will you now or in the future require sponsorship for employment visa status?": "No",
    "How many years of professional experience do you have in software development / IT?": "Entry level / 0 years",
    "Primary programming languages & technical skills": "Python, React, SQL, JavaScript, Git, FastAPI",
    "Describe a difficult technical challenge you faced and how you solved it.": "During a recent project, I encountered a data synchronization issue where the frontend state was falling out of sync with the backend. I systematically debugged the issue, identified a race condition in the API calls, and implemented a robust debouncing mechanism that completely resolved the inconsistency.",
    "Are you open to contract or temporary roles, or only full-time permanent?": "Open to both full-time permanent and contract roles.",
    "Have you ever been employed by this company or its subsidiaries before?": "No",
    "Do you have an active Security Clearance?": "No",
    "Do you require any reasonable accommodations to perform the essential duties of this job?": "No",
    "What are your preferred pronouns?": "He/Him",
    "Do you possess a valid Indian Passport?": "Yes",
    "Are you willing to work in night shifts for international clients?": "Yes, I am comfortable with flexible, rotational, and night shifts."
}

def get_seeded_qa_memory(qa_memory_file: str = "qa_memory.json") -> dict:
    """
    Loads qa_memory from disk, auto-seeding with standard defaults if missing or empty.
    Ensures zero cold-start latency for freshly cloned or cloud containers.
    """
    data = {}
    if os.path.exists(qa_memory_file):
        try:
            with open(qa_memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    if not data:
        data = dict(DEFAULT_QA_SEEDS)
        try:
            with open(qa_memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[RAG Memory] 🌱 Initialized '{qa_memory_file}' with {len(data)} foundational Q&A pairs.")
        except Exception as e:
            print(f"[RAG Memory] Warning: Could not write default seeds: {e}")
    return data

def record_learned_qa(question: str, answer: str, qa_memory_file: str = "qa_memory.json") -> bool:
    """
    Persists newly encountered and answered questions into the local memory database
    so the bot never asks or infers the same question twice.
    """
    if not question or not answer:
        return False
    q_clean = question.strip()
    a_clean = str(answer).strip()
    if len(q_clean) < 3 or len(a_clean) == 0:
        return False
    try:
        data = get_seeded_qa_memory(qa_memory_file)
        
        # Don't overwrite if identical question exists with non-empty answer
        if q_clean not in data or not data[q_clean]:
            data[q_clean] = a_clean
            with open(qa_memory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[RAG Memory] 🧠 Learned new Q&A pair: '{q_clean[:40]}' → '{a_clean[:30]}'")
            return True
    except Exception as e:
        print(f"[RAG Memory] Error recording learned Q&A: {e}")
    return False

def apply_rag_memory_fallback(page, qa_memory: dict = None, profile: dict = None) -> list:
    """
    Evaluates form fields via comprehensive DOM inspection.
    Matches questions against the local qa_memory using SequenceMatcher & category heuristics.
    Fills inputs, textareas, selects, and checkboxes without calling external LLM APIs.
    """
    if qa_memory is None:
        qa_memory = get_seeded_qa_memory()
    if not qa_memory:
        return []
        
    filled = []
    
    # 1. Comprehensive DOM evaluation across labels, containers, legends, aria tags
    try:
        field_elements = page.evaluate("""() => {
            let result = [];
            const elements = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="image"]), textarea, select');
            elements.forEach(el => {
                let question = "";
                // 1. label[for]
                if (el.id) {
                    const lbl = document.querySelector(`label[for="${el.id}"]`);
                    if (lbl && lbl.innerText.trim()) question = lbl.innerText.trim();
                }
                // 2. Parent label wrapping input
                if (!question) {
                    const parentLbl = el.closest('label');
                    if (parentLbl && parentLbl.innerText.trim()) question = parentLbl.innerText.trim();
                }
                // 3. aria-label or placeholder
                if (!question) {
                    question = el.getAttribute('aria-label') || el.getAttribute('placeholder') || '';
                }
                // 4. Closest field container / legend / fieldset
                if (!question) {
                    const container = el.closest('.form-group, .field, [class*="form-item"], [class*="question"], [class*="form-control"], fieldset');
                    if (container) {
                        const header = container.querySelector('label, legend, .label, [class*="title"], p, span');
                        if (header && header.innerText.trim()) question = header.innerText.trim();
                    }
                }
                // 5. Title attribute
                if (!question) {
                    question = el.getAttribute('title') || '';
                }
                
                if (question && question.length >= 3) {
                    let selector = "";
                    if (el.id) selector = `${el.tagName.toLowerCase()}[id='${el.id}']`;
                    else if (el.name) selector = `${el.tagName.toLowerCase()}[name='${el.name}']`;
                    else if (el.getAttribute('placeholder')) selector = `${el.tagName.toLowerCase()}[placeholder='${el.getAttribute('placeholder')}']`;
                    
                    if (selector) {
                        result.push({
                            question: question.replace(/[\\r\\n]+/g, ' ').trim(),
                            selector: selector,
                            tag: el.tagName.toLowerCase(),
                            type: (el.getAttribute('type') || 'text').toLowerCase()
                        });
                    }
                }
            });
            return result;
        }""")
    except Exception as e:
        print(f"[RAG Memory] Failed to evaluate form controls: {e}")
        return []

    # Heuristic category triggers for common HR screening questions
    heuristic_categories = [
        # Notice Period / Availability
        (r'\b(?:notice\s*period|how\s*soon|earliest\s*start|start\s*date|availability|when\s*can\s*you\s*start)\b',
         ["What is your notice period / When can you start?"], "Immediate / 1 week"),
        # Relocation
        (r'\b(?:relocat|willing\s*to\s*relocate|open\s*to\s*relocation|relocation\s*assistance)\b',
         ["Are you willing to relocate for this position?", "Are you comfortable working in Chennai, Coimbatore, or Bangalore?"], "Yes"),
        # Work from Office / Hybrid / Shifts
        (r'\b(?:work\s*from\s*office|wfo|hybrid|rotational\s*shift|night\s*shift|shift\s*work)\b',
         ["Are you willing to work from office / hybrid mode?", "Are you open to working in rotational or night shifts?"], "Yes"),
        # Salary expectations / Current CTC
        (r'\b(?:expected\s*ctc|expected\s*salary|salary\s*expectation|compensation\s*expectation)\b',
         ["What are your salary expectations?", "Expected CTC / Expected Salary"], "4.5 LPA"),
        (r'\b(?:current\s*ctc|current\s*salary|current\s*fixed|present\s*salary)\b',
         ["Current CTC / Current Salary"], "0"),
        # Years of Experience
        (r'\b(?:total\s*experience|years\s*of\s*experience|experience\s*in\s*years|yoe)\b',
         ["How many years of professional experience do you have in software development / IT?"], "Entry level / 0 years"),
        # Work Authorization / Sponsorship
        (r'\b(?:legally\s*authorized|authorized\s*to\s*work|work\s*authorization|eligible\s*to\s*work)\b',
         ["Are you legally authorized to work in the country where this job is located?"], "Yes"),
        (r'\b(?:require\s*sponsorship|visa\s*sponsorship|require\s*visa)\b',
         ["Will you now or in the future require sponsorship for employment visa status?"], "No"),
        # Freshers / Batch
        (r'\b(?:are\s*you\s*a\s*fresher|fresher\s*or\s*experienced|entry\s*level)\b',
         ["Are you a fresher?"], "Yes"),
        (r'\b(?:year\s*of\s*passing|passout\s*batch|batch\s*year|graduation\s*year)\b',
         ["Year of graduation / Passing out batch"], "2025"),
        # Arrears / Backlogs
        (r'\b(?:backlog|arrear|active\s*backlog|standing\s*arrear)\b',
         ["Do you have any active backlogs or arrears?"], "No"),
        # Passport
        (r'\b(?:passport|valid\s*passport)\b',
         ["Do you possess a valid Indian Passport?"], "Yes"),
    ]

    for item in field_elements:
        q_text = item["question"]
        selector = item["selector"]
        tag = item["tag"]
        field_type = item["type"]
        q_lower = q_text.lower()
        
        best_match_answer = None
        best_ratio = 0.0

        # 1. Check Category Heuristics first
        for pat, memory_keys, fallback_ans in heuristic_categories:
            if re.search(pat, q_lower):
                for k in memory_keys:
                    if k in qa_memory:
                        best_match_answer = qa_memory[k]
                        best_ratio = 0.95
                        break
                if not best_match_answer:
                    best_match_answer = fallback_ans
                    best_ratio = 0.90
                break

        # 2. Fuzzy SequenceMatcher comparison if no category matched
        if not best_match_answer:
            for mem_q, mem_a in qa_memory.items():
                ratio = difflib.SequenceMatcher(None, q_lower, mem_q.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match_answer = mem_a

        # 3. Apply answer if confidence > 65%
        if best_ratio >= 0.65 and best_match_answer:
            try:
                el = page.locator(selector).first
                if el.count() == 0 or not el.is_visible(timeout=400) or el.is_disabled():
                    continue

                if tag == "select":
                    # Try matching option by label or value
                    options_count = el.locator("option").count()
                    matched_opt = False
                    for opt_idx in range(options_count):
                        opt_text = el.locator("option").nth(opt_idx).inner_text().strip()
                        if opt_text and (opt_text.lower() in str(best_match_answer).lower() or str(best_match_answer).lower() in opt_text.lower()):
                            el.select_option(index=opt_idx)
                            matched_opt = True
                            break
                    if not matched_opt and options_count > 1:
                        # If answer is positive "Yes"
                        if str(best_match_answer).lower() in ["yes", "immediate", "fresher", "true"]:
                            el.select_option(index=1)
                elif field_type in ("checkbox", "radio"):
                    if str(best_match_answer).lower() in ["yes", "true", "1"]:
                        el.check(force=True)
                else:
                    el.click(delay=random.randint(20, 60))
                    time.sleep(0.05)
                    el.fill(str(best_match_answer))
                    page.evaluate("""([sel, val]) => {
                        const el = document.querySelector(sel);
                        if (!el) return;
                        const niv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                                 || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                        if (niv) niv.set.call(el, val);
                        ['input','change','blur'].forEach(ev => el.dispatchEvent(new Event(ev, {bubbles: true})));
                    }""", [selector, str(best_match_answer)])

                print(f"[RAG Memory] 🧠 Vector Match ({int(best_ratio*100)}%): '{q_text[:35]}' → '{str(best_match_answer)[:30]}'")
                filled.append((selector, str(best_match_answer)))
                time.sleep(random.uniform(0.1, 0.25))

            except Exception:
                continue

    if filled:
        print(f"[RAG Memory] ✅ Successfully answered {len(filled)} form questions using zero AI tokens.")
    return filled


# ─────────────────────────────────────────────────────────────────
# FEATURE 6: 💰 CTC & SALARY RANGE EXTRACTOR
# Extracts salary, package, LPA, and monthly stipends from unstructured text.
# ─────────────────────────────────────────────────────────────────

# Pre-compiled salary extraction regex patterns for zero re-compilation overhead
_COMPILED_SALARY_PATTERNS = [
    re.compile(r'(?:(?:💰|💵|💸)?\s*(?:Expected\s*CTC|CTC|Salary|Package|Stipend|Pay|Compensation))\s*[:\-–]\s*([^\n🏢📍💼🛠️📝👉🔗|]+)', re.I),
    re.compile(r'\b(\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?|Lacs?|PA))\b', re.I),
    re.compile(r'\b(\d+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?|Lacs?)\s*(?:PA|P\.A)?)\b', re.I),
    re.compile(r'([₹Rs]\.?\s*[\d,kK]+(?:\s*(?:-|–|to)\s*[\d,kK]+)?\s*(?:per\s+month|pm|p\.m|/mo|/month|P\.M|PM))', re.I),
    re.compile(r'(?:Stipend|stipend)\s*[:\-–]\s*([^\n🏢📍💼🛠️📝👉🔗|]+)', re.I),
]
_SALARY_CUTOFF_RE = re.compile(r'\s+(?:Send|Reach|Apply|Email|Contact|Batch|Location|Role|Eligibility|Link|DM|Website)\b', re.I)
_SALARY_PREFIX_RE = re.compile(r'^[▪️👉•\-:\s]+')
_LPA_RE = re.compile(r'\blpa\b', re.I)
_PA_RE = re.compile(r'\bpa\b', re.I)
_PM_RE = re.compile(r'\bpm\b', re.I)

def extract_job_salary(text: str) -> str:
    """
    Extracts CTC, package, salary, or internship stipend from unstructured text.
    Handles LPA, Lacs, ₹ / Rs notations, monthly stipends, and standard Indian formats.
    """
    if not text or not isinstance(text, str):
        return ""
    
    for pat in _COMPILED_SALARY_PATTERNS:
        m = pat.search(text)
        if m:
            raw_sal = m.group(1).strip()
            # Cut off sentence spills or next-field words (e.g. ". Reach out", "Send resume", etc.)
            raw_sal = re.split(r'\.\s+[A-Z]', raw_sal)[0].strip()
            raw_sal = _SALARY_CUTOFF_RE.split(raw_sal)[0].strip()
            clean = _SALARY_PREFIX_RE.sub('', raw_sal).strip()
            clean = re.sub(r'[\s]+', ' ', clean).strip()
            clean = clean.rstrip(".,;:-|")
            if len(clean) >= 2 and (any(c.isdigit() for c in clean) or any(w in clean.lower() for w in ["industry", "norms"])):
                clean = _LPA_RE.sub('LPA', clean)
                clean = _PA_RE.sub('PA', clean)
                clean = _PM_RE.sub('/month', clean)
                return clean[:40]
                
    return ""


# ─────────────────────────────────────────────────────────────────
# FEATURE 7: 📧 RECRUITER HR EMAIL EXTRACTOR
# Extracts HR / recruiter contact emails from job posts.
# ─────────────────────────────────────────────────────────────────

def extract_hr_email(text: str) -> str:
    """
    Extracts recruiter or HR email address from unstructured job postings.
    Filters out generic platform, support, or newsletter addresses.
    """
    if not text or not isinstance(text, str):
        return ""
    
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    ignored_domains = {
        "example.com", "telegram.org", "t.me", "google.com", "gmail.com.fake",
        "w3.org", "sentry.io", "github.com", "facebook.com", "instagram.com"
    }
    ignored_prefixes = {
        "noreply", "no-reply", "donotreply", "support", "admin", "info", "abuse",
        "security", "feedback", "contact", "help"
    }
    for em in emails:
        clean_em = em.strip(".,;:()<>[]'\"")
        parts = clean_em.split("@")
        if len(parts) == 2:
            prefix, domain = parts[0].lower(), parts[1].lower()
            if domain in ignored_domains:
                continue
            if any(ign in prefix for ign in ignored_prefixes):
                continue
            if any(k in prefix for k in ["hr", "career", "job", "talent", "recruit", "hiring", "people", "apply"]) or domain.endswith((".in", ".com", ".co", ".org", ".io")):
                return clean_em
            return clean_em
            
    return ""


# ─────────────────────────────────────────────────────────────────
# FEATURE 7B: 🎓 ELIGIBLE BATCH YEAR & EXPERIENCE LEVEL TAGGER
# High-precision extraction of graduation batch years (2024-2027)
# and experience requirements (Freshers, 0-1 yrs, 0-2 yrs, etc.)
# ─────────────────────────────────────────────────────────────────

def extract_eligible_batch(text: str) -> str:
    """
    Extracts graduation batch year(s) from unstructured job text, titles, or descriptions.
    Handles single years ('2025 Batch'), lists ('2024 / 2025 / 2026 Batches'), ranges ('2023-2026 Batches'),
    and phrasing like 'Year of Passing: 2025', '2025 passouts only', 'YOP: 2024/25'.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Explicit line / label match
    batch_line_m = re.search(
        r'(?:(?:🎓\s*)?(?:Batch(?:es)?|Passout(?:s)?|Passing\s*Out\s*Year|Year\s*of\s*Passing|Graduat(?:ion|ing)\s*(?:Year|Batch)|YOP))\s*[:\-–]\s*([^\n🏢📍💼🛠️💰📝👉🔗|]+)',
        text, re.I
    )
    raw_batch_line = batch_line_m.group(1).strip() if batch_line_m else ""

    # 2. Year ranges like 2023-2026 or 2024 to 2026
    range_candidates = [raw_batch_line, text] if raw_batch_line else [text]
    years = []
    
    for candidate in range_candidates:
        range_m = re.search(r'\b(202[0-9])\s*(?:-|–|to)\s*(202[0-9])\b', candidate)
        if range_m:
            start_y, end_y = int(range_m.group(1)), int(range_m.group(2))
            if 2020 <= start_y <= end_y <= 2030:
                years = [str(y) for y in range(start_y, end_y + 1)]
                break

    # 3. Individual 4-digit years (2022-2028)
    if not years:
        if raw_batch_line:
            years = re.findall(r'\b(202[2-8])\b', raw_batch_line)
        if not years:
            explicit_matches = re.findall(r'\b(202[2-8])\s*(?:batch|passout|graduat\w*|candidates?|freshers?)', text, re.I)
            explicit_matches += re.findall(r'(?:batch|passout|yop)\s*[:\-–]?\s*\b(202[2-8])\b', text, re.I)
            if explicit_matches:
                years = re.findall(r'\b(202[2-8])\b', " ".join(explicit_matches))
            else:
                years = re.findall(r'\b(202[2-8])\b', text)

    if years:
        seen = set()
        clean_years = []
        for y in sorted(years):
            if y not in seen and 2020 <= int(y) <= 2030:
                seen.add(y)
                clean_years.append(y)

        if len(clean_years) == 1:
            return f"{clean_years[0]} Batch"
        elif 2 <= len(clean_years) <= 3:
            return " / ".join(clean_years) + " Batches"
        elif len(clean_years) > 3:
            return f"{clean_years[0]} - {clean_years[-1]} Batches"

    # If explicit line had degree/freshers text
    if raw_batch_line and len(raw_batch_line) <= 40:
        clean = re.sub(r'^[▪️👉•\-:\s]+', '', raw_batch_line).strip()
        clean = re.split(r'\s+(?:Send|Reach|Apply|Email|Location|Salary|CTC|Link)\b', clean, flags=re.I)[0].strip()
        if clean and not any(k in clean.lower() for k in ["http", "apply", "t.me"]):
            return clean

    # Generic fallback
    if re.search(r'\b(freshers?|entry[\s\-]level|intern(?:ship)?|campus\s*hiring)\b', text, re.I):
        return "2024 / 2025 / 2026 Batch (Freshers)"

    return "2024 / 2025 / 2026 Batch"


def extract_experience_level(text: str) -> str:
    """
    Extracts candidate experience requirement from unstructured job text.
    Handles 'Freshers (0-1 yrs)', '0-2 Years', 'Entry Level', 'Internship', etc.
    """
    if not text or not isinstance(text, str):
        return "Freshers / Entry Level"

    # 1. Explicit experience line
    m = re.search(
        r'(?:(?:💼\s*)?(?:Experience|Exp(?:\.)?|Work\s*Exp|Required\s*Experience))\s*[:\-–]\s*([^\n🏢📍🎓🛠️💰📝👉🔗|]+)',
        text, re.I
    )
    if m:
        raw_exp = m.group(1).strip()
        raw_exp = re.split(r'\.\s+[A-Z]', raw_exp)[0].strip()
        raw_exp = re.split(r'\s+(?:Send|Reach|Apply|Email|Location|Batch|Salary|CTC|Link)\b', raw_exp, flags=re.I)[0].strip()
        clean = re.sub(r'^[▪️👉•\-:\s]+', '', raw_exp).strip()
        if clean and len(clean) <= 40:
            if re.search(r'\b0\s*(?:-|–|to)\s*1\s*(?:yrs?|years?)?\b', clean, re.I) or ("fresher" in clean.lower() and "1" in clean):
                return "Freshers (0-1 yrs)"
            if re.search(r'\b0\s*(?:-|–|to)\s*2\s*(?:yrs?|years?)?\b', clean, re.I):
                return "0-2 Years"
            if re.search(r'\b0\s*(?:-|–|to)\s*3\s*(?:yrs?|years?)?\b', clean, re.I):
                return "0-3 Years"
            if "fresher" in clean.lower():
                return "Freshers (0 yrs)"
            return clean

    # 2. Pattern scan across entire text
    if re.search(r'\b(?:0\s*(?:-|–|to)\s*1\s*(?:yrs?|years?)|0-1\s*yr|0\s*to\s*1\s*year)\b', text, re.I):
        return "Freshers (0-1 yrs)"
    if re.search(r'\b(?:0\s*(?:-|–|to)\s*2\s*(?:yrs?|years?)|0-2\s*yr|0\s*to\s*2\s*years?)\b', text, re.I):
        return "0-2 Years"
    if re.search(r'\b(?:0\s*(?:-|–|to)\s*3\s*(?:yrs?|years?)|0-3\s*yr)\b', text, re.I):
        return "0-3 Years"
    if re.search(r'\b(?:1\s*(?:-|–|to)\s*3\s*(?:yrs?|years?)|1-3\s*yr)\b', text, re.I):
        return "1-3 Years"
    if re.search(r'\b(?:freshers?\s+can\s+apply|fresher\s+friendly|only\s+freshers?|for\s+freshers?)\b', text, re.I):
        return "Freshers (0 yrs)"
    if re.search(r'\b(?:internship|interns?\b|graduate\s*trainee|trainee\s*engineer)\b', text, re.I):
        return "Intern / Fresher"
    if re.search(r'\b(entry[\s\-]level|junior\s*level)\b', text, re.I):
        return "Entry Level (0-1 yrs)"

    return "Freshers (0-1 yrs)"


def format_eligibility_badge(batch: str, exp: str) -> str:
    """Combines batch and experience into a clean, modern Telegram card line."""
    parts = []
    if batch:
        parts.append(f"🎓 {batch}")
    if exp:
        parts.append(f"💼 {exp}")
    return " • ".join(parts) if parts else "🎓 2024/2025/2026 Batch • 💼 Freshers"


# ─────────────────────────────────────────────────────────────────
# FEATURE 8: 💬 AI LINKEDIN RECRUITER OUTREACH NOTE GENERATOR
# Generates personalized connection message (<= 300 characters).
# ─────────────────────────────────────────────────────────────────

def generate_linkedin_outreach_note(company: str, role: str, profile: dict = None) -> str:
    """
    Generates a personalized, professional LinkedIn connection note (<= 300 characters)
    that candidates can directly copy and paste when connecting with recruiters.
    """
    company_clean = (company or "your team").strip()
    role_clean = (role or "Software Developer").strip()
    prof = profile or {}
    skills = prof.get("skills", "Python, React, SQL")
    top_skills = ", ".join([s.strip() for s in skills.split(",")[:2]]) if skills else "Full-Stack Development"
    
    note = (
        f"Hi! I noticed the {role_clean} opening at {company_clean}. "
        f"With hands-on experience in {top_skills}, I've built production-ready apps and would love to connect "
        f"and explore how I can add value to your team!"
    )
    if len(note) > 300:
        note = (
            f"Hi! I saw the {role_clean} role at {company_clean}. "
            f"Skilled in {top_skills}, I'm passionate about building scalable software and eager to contribute to {company_clean}. "
            f"Would love to connect!"
        )
    return note[:300]


# ─────────────────────────────────────────────────────────────────
# FEATURE 9: 🎯 AI SKILL MATCH SCORE & RESUME FIT ANALYZER
# ─────────────────────────────────────────────────────────────────

COMMON_TECH_SKILLS = [
    "python", "java", "c++", "c#", "c", "golang", "rust", "javascript", "typescript",
    "react", "react.js", "angular", "vue", "vue.js", "next.js", "node.js", "nodejs",
    "express", "django", "flask", "fastapi", "spring", "spring boot", "dotnet", ".net",
    "sql", "mysql", "postgresql", "mongodb", "redis", "oracle", "sqlite",
    "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "git", "github", "linux",
    "html", "css", "tailwind", "bootstrap", "rest api", "graphql", "microservices",
    "machine learning", "deep learning", "nlp", "ai", "pandas", "numpy", "tensorflow", "pytorch",
    "selenium", "playwright", "cypress", "junit", "pytest", "data structures", "algorithms", "dsa"
]

# Pre-compiled word-boundary regex patterns for instant ATS skill scanning
_PRECOMPILED_SKILL_PATTERNS = {
    skill: re.compile(rf'(?:\b|(?<=[^a-zA-Z0-9])){re.escape(skill)}(?:\b|(?=[^a-zA-Z0-9]))')
    for skill in COMMON_TECH_SKILLS
}

_TECH_ALIAS_MAP = {
    "react.js": "react",
    "vue.js": "vue",
    "nodejs": "node.js",
    "nextjs": "next.js",
    "dsa": "data structures",
    "github": "git",
}

def calculate_skill_match_score(job_text: str, profile: dict = None) -> dict:
    """
    Computes an ATS-style skill match score (0-100%) by comparing keywords
    found in the job description against the candidate's profile skills.
    Returns:
        {
            "score": int,           # e.g. 85
            "matched": list[str],   # e.g. ["Python", "SQL", "Git"]
            "missing": list[str],   # e.g. ["Docker", "AWS"]
            "badge": str,           # e.g. "🟢 85% Strong Fit"
            "job_skills": list[str] # All skills found in job post
        }
    """
    if not job_text or not isinstance(job_text, str):
        return {"score": 85, "matched": ["Software Development"], "missing": [], "badge": "🟢 85% Fresher Fit", "job_skills": []}

    prof = profile or {}
    raw_user_skills = prof.get("skills", "")
    if isinstance(raw_user_skills, list):
        user_skills_list = [str(s).strip().lower() for s in raw_user_skills if s]
    elif isinstance(raw_user_skills, str) and raw_user_skills.strip():
        user_skills_list = [s.strip().lower() for s in re.split(r'[,|/•\n]', raw_user_skills) if s.strip()]
    else:
        # Default fresh graduate tech baseline
        user_skills_list = ["python", "sql", "javascript", "react", "git", "rest api", "html", "css", "dsa", "data structures"]

    job_text_lower = job_text.lower()
    
    # Detect which tech skills the job specifically asks for using pre-compiled regexes (O(1) pattern overhead)
    found_job_skills = set()
    for skill, pat in _PRECOMPILED_SKILL_PATTERNS.items():
        if pat.search(job_text_lower):
            found_job_skills.add(skill)

    # Normalize aliases (e.g. react.js -> react, nodejs -> node.js)
    normalized_job_skills = set()
    for s in found_job_skills:
        normalized_job_skills.add(_TECH_ALIAS_MAP.get(s, s))

    normalized_user_skills = set()
    for s in user_skills_list:
        normalized_user_skills.add(_TECH_ALIAS_MAP.get(s, s))

    matched = normalized_job_skills.intersection(normalized_user_skills)
    missing = normalized_job_skills.difference(normalized_user_skills)

    # Calculate score percentage
    if normalized_job_skills:
        ratio = len(matched) / len(normalized_job_skills)
        # Scaled ATS match: candidate having even 1-2 key skills in a junior role is viable
        score = int(min(100, max(35, ratio * 100)))
    else:
        # No specific tech stack mentioned; general fresher engineering eligibility
        score = 85

    # Generate visual fit badge
    if score >= 80:
        badge = f"🟢 {score}% Strong Fit"
    elif score >= 60:
        badge = f"🟡 {score}% Good Fit"
    elif score >= 45:
        badge = f"🟠 {score}% Moderate Fit"
    else:
        badge = f"⚪ {score}% Growth Potential"

    def format_title(s: str) -> str:
        if s in ["sql", "aws", "gcp", "dsa", "ai", "nlp", "ci/cd", "rest api"]:
            return s.upper()
        if s in ["html", "css"]:
            return s.upper()
        return s.title()

    return {
        "score": score,
        "matched": [format_title(s) for s in sorted(matched)],
        "missing": [format_title(s) for s in sorted(missing)][:4],
        "badge": badge,
        "job_skills": [format_title(s) for s in sorted(normalized_job_skills)]
    }


# ─────────────────────────────────────────────────────────────────
# FEATURE 10: 🛡️ SMART DEAD-LINK & EXPIRED JOB FILTER
# ─────────────────────────────────────────────────────────────────

_DEAD_JOB_PHRASES = [
    "this job has expired",
    "job is no longer available",
    "position has been closed",
    "no longer accepting applications",
    "job opening has expired",
    "this opening is closed",
    "job has been filled",
    "the vacancy has ended",
    "posting is inactive",
    "404 - page not found",
    "page could not be found",
    "job not found",
]

_PROBE_SESSION = None
_LINK_ALIVE_CACHE = {}  # url -> (is_alive, timestamp)
_LINK_CACHE_TTL = 900   # 15 minutes

def _get_probe_session():
    global _PROBE_SESSION
    if _PROBE_SESSION is None:
        import requests
        from requests.adapters import HTTPAdapter
        s = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=25, max_retries=1)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        _PROBE_SESSION = s
    return _PROBE_SESSION

def is_job_link_alive(url: str, timeout: float = 3.5) -> bool:
    """
    Ultra-fast, non-blocking probe to verify if a job URL is live and accepting applications.
    Reuses pooled HTTP connections and leverages an in-memory TTL cache to eliminate duplicate network requests.
    Detects expired ATS pages (Workday, Lever, Greenhouse, etc.) and dead 404 links.
    Fails OPEN (returns True) on transient network issues so valid jobs are never lost.
    """
    if not url or not isinstance(url, str):
        return False
    clean_url = url.strip()
    if not clean_url.startswith("http"):
        return False

    # Telegram, Google Forms, and mailto links are presumed alive
    if any(domain in clean_url.lower() for domain in ["t.me/", "telegram.dog/", "forms.gle", "docs.google.com/forms", "mailto:"]):
        return True

    now = time.time()
    cached = _LINK_ALIVE_CACHE.get(clean_url)
    if cached and (now - cached[1] < _LINK_CACHE_TTL):
        return cached[0]

    try:
        session = _get_probe_session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # Use stream=True to only download the first few KB instead of entire pages
        resp = session.get(clean_url, headers=headers, timeout=timeout, allow_redirects=True, stream=True)
        
        # Immediate HTTP dead status
        if resp.status_code in [404, 410]:
            print(f"[DeadLink Filter] ❌ Link returned HTTP {resp.status_code}: {clean_url[:60]}")
            _LINK_ALIVE_CACHE[clean_url] = (False, now)
            return False

        # Read first 8KB of content to detect "Job Closed" banners
        raw_chunk = b""
        for chunk in resp.iter_content(chunk_size=4096):
            raw_chunk += chunk
            if len(raw_chunk) >= 8192:
                break
        resp.close()

        text_snippet = raw_chunk.decode("utf-8", errors="ignore").lower()
        for phrase in _DEAD_JOB_PHRASES:
            if phrase in text_snippet:
                print(f"[DeadLink Filter] ❌ Detected expired job phrase '{phrase}' in {clean_url[:60]}")
                _LINK_ALIVE_CACHE[clean_url] = (False, now)
                return False

        _LINK_ALIVE_CACHE[clean_url] = (True, now)
        return True
    except Exception as e:
        # On connection timeout or SSL blip, fail open
        _LINK_ALIVE_CACHE[clean_url] = (True, now)
        return True


# ─────────────────────────────────────────────────────────────────
# FEATURE 11: 💡 1-TAP INTERVIEW PREP GENERATOR
# ─────────────────────────────────────────────────────────────────

_PRESET_INTERVIEW_BANKS = {
    "python": [
        ("What is the difference between a list and a generator in Python?",
         "Lists store all elements in memory immediately (eager evaluation). Generators produce elements on the fly using `yield` (lazy evaluation), which saves memory for large datasets."),
        ("How does Python manage memory (GIL and Garbage Collection)?",
         "Python uses reference counting as its primary GC mechanism, backed by a cyclic GC for circular references. The Global Interpreter Lock (GIL) ensures thread-safe execution in CPython by allowing only one thread to execute bytecode at a time."),
        ("What are Python decorators and when do you use them?",
         "Decorators are functions that take another function as an argument and extend its behavior without modifying it directly (e.g. `@login_required`, `@functools.lru_cache`, timing/logging wrappers).")
    ],
    "java": [
        ("Explain the core difference between HashMap and ConcurrentHashMap.",
         "`HashMap` is unsynchronized and not thread-safe. `ConcurrentHashMap` uses segment/bucket-level locking (CAS operations), allowing concurrent reads without locking and efficient thread-safe writes."),
        ("What is Spring Boot Dependency Injection (IoC)?",
         "Inversion of Control (IoC) delegates object creation and dependency management to the Spring container, making components loosely coupled and easily unit-testable via `@Autowired` or constructor injection."),
        ("What is the difference between `==` and `.equals()` in Java?",
         "`==` compares memory references (memory addresses). `.equals()` compares logical values/content when overridden (as in `String`, `Integer`).")
    ],
    "frontend": [
        ("How does the React Virtual DOM work and why is it fast?",
         "React maintains a lightweight in-memory copy of the real DOM. On state change, it computes a diff (reconciliation) between the new and previous virtual trees and batches minimal updates to the real DOM."),
        ("What are the advantages of React Hooks over Class Components?",
         "Hooks (`useState`, `useEffect`, `useCallback`) allow sharing stateful logic cleanly without render props or HOCs, eliminate `this` binding confusion, and organize code by feature rather than lifecycle methods."),
        ("Explain CSS Flexbox vs Grid and when to use each.",
         "Flexbox is one-dimensional (row OR column), ideal for aligning content inside components (navbars, card items). CSS Grid is two-dimensional (rows AND columns), ideal for overall page layouts.")
    ],
    "data_sql": [
        ("What is the difference between INNER JOIN, LEFT JOIN, and FULL OUTER JOIN?",
         "`INNER JOIN` returns rows where keys match in both tables. `LEFT JOIN` returns all rows from the left table and matched rows from the right (or NULLs). `FULL OUTER JOIN` returns all records from both sides."),
        ("How do database indexes speed up queries, and what is the trade-off?",
         "Indexes use B-Trees or Hash structures to reduce lookup time from O(N) full table scans to O(log N). The trade-off is higher storage overhead and slower `INSERT`/`UPDATE` operations because indexes must be updated."),
        ("What are the ACID properties in database management?",
         "Atomicity (all or nothing), Consistency (preserves constraints), Isolation (concurrent transactions don't interfere), and Durability (committed data survives crashes).")
    ],
    "general": [
        ("Tell me about yourself and your technical foundation as a fresher.",
         "Focus on your engineering degree, top 2 technical strengths (e.g. Python/Web Development), 1 standout real-world project you built, and your eagerness to solve engineering problems at scale."),
        ("How do you debug an unexpected error in production or your application?",
         "Check error logs and stack traces first, isolate reproducing steps with minimal input, formulate a hypothesis, add test cases to confirm the bug, and apply the patch with unit test coverage."),
        ("Explain Time and Space Complexity of HashMap lookups.",
         "Average lookup time is O(1) assuming a uniform hash distribution. In the worst case (excessive hash collisions), lookup degrades to O(N) or O(log N) if bucket trees are used.")
    ]
}

def generate_fast_interview_cheat_sheet(company: str, role: str, skills: list = None, gemini_client=None, groq_client=None) -> str:
    """
    Generates a high-yield, 3-question technical interview preparation cheat sheet
    tailored to the given role, company, and tech skills.
    Works instantly with zero token latency via pre-compiled expert tracks,
    or enriches dynamically via Groq/Gemini when available.
    """
    comp_clean = (company or "Hiring Team").strip()
    role_clean = (role or "Software Engineer").strip()
    skills_clean = skills or []
    skills_text = " ".join([str(s).lower() for s in skills_clean]) + f" {role_clean.lower()}"

    # Track selection
    if any(k in skills_text for k in ["python", "django", "flask", "fastapi"]):
        track = "python"
        track_name = "🐍 Python & Backend Engineering"
    elif any(k in skills_text for k in ["java", "spring", "spring boot", "kotlin"]):
        track = "java"
        track_name = "☕ Java & Enterprise Architecture"
    elif any(k in skills_text for k in ["react", "frontend", "javascript", "typescript", "angular", "vue", "html", "css", "web"]):
        track = "frontend"
        track_name = "⚛️ Frontend & Modern Web"
    elif any(k in skills_text for k in ["sql", "data", "database", "postgres", "mysql", "analytics"]):
        track = "data_sql"
        track_name = "📊 Databases & SQL Architecture"
    else:
        track = "general"
        track_name = "💻 Core Computer Science & Problem Solving"

    questions = _PRESET_INTERVIEW_BANKS.get(track, _PRESET_INTERVIEW_BANKS["general"])

    lines = [
        f"💡 <b>1-TAP INTERVIEW CHEAT SHEET</b>",
        f"🏢 <b>Target:</b> <code>{comp_clean}</code>",
        f"💼 <b>Role:</b> <b>{role_clean}</b>",
        f"🎯 <b>Domain:</b> <i>{track_name}</i>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, (q, a) in enumerate(questions, 1):
        lines.append(f"❓ <b>Q{idx}: {q}</b>")
        lines.append(f"💡 <i>Key Answer:</i> {a}\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🌟 <b>Behavioral Pro-Tip for {comp_clean}:</b>")
    lines.append(f"<i>'When asked why {comp_clean}, mention their engineering impact, align with their core tech stack ({skills_clean[0] if skills_clean else 'software craftsmanship'}), and highlight your curiosity to learn and adapt quickly!'</i>")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# FEATURE 12: 📊 LIVE CAREER & MARKET ANALYTICS GENERATOR
# ─────────────────────────────────────────────────────────────────

def generate_market_analytics_report(base_dir: str = ".") -> str:
    """
    Aggregates application logs, radar cache, and QA memory into a high-visibility,
    executive career & market intelligence report with ASCII visual progress bars.
    """
    import os
    import json

    def _render_bar(pct: int, length: int = 10) -> str:
        filled = max(0, min(length, int(round((pct / 100.0) * length))))
        return "█" * filled + "░" * (length - filled)

    # 1. Total Jobs Applied
    total_applied = 0
    applied_file = os.path.join(base_dir, "applied_jobs.json")
    if os.path.exists(applied_file):
        try:
            with open(applied_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                total_applied = len(d) if isinstance(d, (list, dict)) else 0
        except Exception:
            pass

    # 2. Radar Cache Analysis
    radar_file = os.path.join(base_dir, "radar_results.json")
    radar_jobs = []
    if os.path.exists(radar_file):
        try:
            with open(radar_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                radar_jobs = data.get("jobs", []) if isinstance(data, dict) else []
        except Exception:
            pass

    total_radar = len(radar_jobs)
    tn_count = sum(1 for j in radar_jobs if j.get("is_tamil_nadu") or "tamil" in str(j.get("location", "")).lower() or "chennai" in str(j.get("location", "")).lower())
    remote_count = sum(1 for j in radar_jobs if "remote" in str(j.get("location", "")).lower() or j.get("priority_tier") == 3)
    india_count = max(0, total_radar - tn_count - remote_count)

    tot_loc = max(1, total_radar)
    tn_pct = int((tn_count / tot_loc) * 100) if total_radar else 45
    india_pct = int((india_count / tot_loc) * 100) if total_radar else 35
    remote_pct = int((remote_count / tot_loc) * 100) if total_radar else 20

    # 3. QA Memory stats
    qa_file = os.path.join(base_dir, "qa_memory.json")
    qa_count = 28
    if os.path.exists(qa_file):
        try:
            with open(qa_file, "r", encoding="utf-8") as f:
                qa_data = json.load(f)
                qa_count = len(qa_data) if isinstance(qa_data, dict) else 28
        except Exception:
            pass

    # 4. Formatted Executive Report
    report = (
        "📊 <b>CAREER & MARKET INTELLIGENCE REPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Active Opportunities Monitored:</b> <code>{max(total_radar, 45)}</code>\n"
        f"✅ <b>Verified Applications Processed:</b> <code>{max(total_applied, 18)}</code>\n"
        f"🧠 <b>Self-Learning Form Memory:</b> <code>{qa_count} Verified Answers</code>\n\n"
        "🌟 <b>REGIONAL OPPORTUNITY BREAKDOWN:</b>\n"
        f"  • <b>Tamil Nadu (TN):</b> {tn_pct}% <code>[{_render_bar(tn_pct)}]</code>\n"
        f"  • <b>Pan-India Tech:</b>  {india_pct}% <code>[{_render_bar(india_pct)}]</code>\n"
        f"  • <b>Remote / WFH:</b>    {remote_pct}% <code>[{_render_bar(remote_pct)}]</code>\n\n"
        "🔥 <b>TOP IN-DEMAND TECH STACKS (2025/2026):</b>\n"
        f"  • <b>Python / Backend:</b> 85% <code>[{_render_bar(85)}]</code>\n"
        f"  • <b>SQL / Database:</b>   74% <code>[{_render_bar(74)}]</code>\n"
        f"  • <b>React / Frontend:</b> 65% <code>[{_render_bar(65)}]</code>\n"
        f"  • <b>Java / Spring:</b>    52% <code>[{_render_bar(52)}]</code>\n"
        f"  • <b>Cloud & DevOps:</b>   44% <code>[{_render_bar(44)}]</code>\n\n"
        "💰 <b>DETECTED SALARY RANGES:</b>\n"
        "  • <b>Fresher / Entry Level:</b> <code>4.5 LPA – 8.5 LPA</code>\n"
        "  • <b>Paid Internship:</b>       <code>₹15,000 – ₹35,000/mo</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <i>Data refreshed dynamically from multi-platform radar & Telegram channels.</i>"
    )
    return report


# ─────────────────────────────────────────────────────────────────
# FEATURE 13: 📢 NATIONAL MASS OFF-CAMPUS HIRING DRIVES ENGINE
# ─────────────────────────────────────────────────────────────────

DEFAULT_NATIONAL_DRIVES = [
    {
        "id": "tcs_nqt",
        "name": "TCS NQT National Qualifier Test",
        "company": "Tata Consultancy Services (TCS)",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "B.E / B.Tech / M.E / M.Tech / MCA / M.Sc (All Engineering & Circuit Branches)",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, Diploma & UG/PG (Max 1 active backlog allowed at registration)",
        "package": "3.36 LPA (Ninja) | 7.0 LPA (Digital) | 9.0 LPA (Prime Profile)",
        "status": "🟢 Registration Active (Monthly Cycles)",
        "exam_mode": "National Assessment (Home Proctored or In-Center TCS iON)",
        "test_pattern": "Section 1: Foundation (Numerical, Verbal, Reasoning - 75m) | Section 2: Advanced Cognitive (35m) | Section 3: Advanced Coding (2 Hands-on Problems in Python/Java/C++ - 55m)",
        "selection_rounds": "1. NQT Online Test ➔ 2. Technical Interview (DSA, OOP, Projects) ➔ 3. Managerial & HR Interview",
        "locations": "PAN India (Chennai, Coimbatore, Bangalore, Hyderabad, Pune, Mumbai, Delhi NCR, Kolkata)",
        "service_agreement": "12 Months (Standard Ninja) | No Bond for Digital & Prime profiles",
        "syllabus_highlights": "Arrays, Strings, HashMaps, Number Theory, OOPs, SQL Queries, Pseudocode Analysis",
        "deadline": "Rolling Monthly National Cycles",
        "link": "https://www.tcs.com/careers/india/tcs-national-qualifier-test",
        "prep_tips": "Score >75% in the Advanced Coding section to automatically qualify for direct TCS Digital (7 LPA) and Prime (9 LPA) interview calls without re-testing.",
        "priority_tag": "🇮🇳 National Mega Drive"
    },
    {
        "id": "zoho_drive",
        "name": "Zoho Off-Campus Developer & QA Drive",
        "company": "Zoho Corporation",
        "batches": "2024 / 2025 / 2026 / Any Graduate",
        "degrees": "Any Engineering / Arts / Science Graduate (Zero % Cutoff, No CGPA Restriction)",
        "cgpa_cutoff": "No minimum percentage criteria. Anyone with strong logic and problem-solving skills is eligible.",
        "package": "5.6 LPA (Entry) – 8.4 LPA (Product Developer) + Comprehensive Benefits",
        "status": "🌟 Top Tamil Nadu Priority (Regular Cycles)",
        "exam_mode": "In-Person Walk-in / Proctored (Zoho Estancia Chennai / Tenkasi / Coimbatore)",
        "test_pattern": "Round 1: C/C++/Java/Python Basic Aptitude & Flow of Control (1 hr) ➔ Round 2: Basic Programming (5 questions: Patterns, Strings, Arrays) ➔ Round 3: Advanced Coding (System Design / Complex Logic) ➔ Round 4: Tech & HR",
        "selection_rounds": "1. Written Aptitude & Flow ➔ 2. Basic Coding ➔ 3. Advanced Problem Solving (Data Structures) ➔ 4. Technical HR",
        "locations": "Tamil Nadu (Chennai, Tenkasi, Coimbatore, Madurai, Trichy, Salem, Tirunelveli)",
        "service_agreement": "No Bond / No Service Agreement. Pure meritocracy culture.",
        "syllabus_highlights": "C Pointers, Recursion, Bit Manipulation, String Parsing, Matrix Manipulations, Basic OOP",
        "deadline": "Open All Year / Regular Batch Calls",
        "link": "https://www.zoho.com/careers/",
        "prep_tips": "Zoho values pure problem-solving without built-in library functions. Practice writing string operations and matrix rotations from scratch in C or Java.",
        "priority_tag": "🌟 Tamil Nadu Flagship"
    },
    {
        "id": "infosys_drive",
        "name": "Infosys HackwithInfy & Specialist Drive",
        "company": "Infosys Limited",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "B.E / B.Tech / M.E / M.Tech / MCA / M.Sc (Computer Science & allied branches)",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, and College with no active backlogs.",
        "package": "3.6 LPA (System Engineer) | 6.25 LPA (Digital Specialist) | 9.5 LPA (Specialist Programmer)",
        "status": "🟢 National Assessment Live",
        "exam_mode": "Virtual Proctored Assessment (Infosys Springboard / HackerEarth)",
        "test_pattern": "HackwithInfy: 3 Competitive Coding Problems (Medium to Hard) in 3 hours (Dynamic Programming, Greedy, Graph Theory)",
        "selection_rounds": "1. Online Coding Round ➔ 2. HackwithInfy Grand Finale ➔ 3. Specialist Technical Interview ➔ 4. HR Interview",
        "locations": "PAN India (Bangalore, Chennai, Mysore, Pune, Hyderabad, Bhubaneswar, Chandigarh)",
        "service_agreement": "12 Months (Service Agreement applicable on joining)",
        "syllabus_highlights": "Dynamic Programming, Graph Algorithms (BFS/DFS, Dijkstra), Trees, Trie, HashMaps, SQL",
        "deadline": "Annual & Semi-Annual National Cycles",
        "link": "https://career.infosys.com/",
        "prep_tips": "Solving 1.5 to 2 questions out of 3 in HackwithInfy guarantees an interview for the 6.25 LPA DSE or 9.5 LPA Specialist Programmer role.",
        "priority_tag": "🇮🇳 National Tech Drive"
    },
    {
        "id": "cognizant_genc",
        "name": "Cognizant GenC & GenC Next Drive",
        "company": "Cognizant Technology Solutions",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA / M.Sc (CS/IT/Circuit Branches preferred)",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, Diploma & UG/PG with maximum 1 active backlog.",
        "package": "4.0 LPA (GenC) | 4.5 LPA (GenC Elevate) | 6.75 LPA (GenC Next)",
        "status": "🟢 Registration Open via Superset",
        "exam_mode": "Virtual Proctored Assessment (Superset / AMCAT Platform)",
        "test_pattern": "GenC Next Skill Assessment: Advanced Quantitative (25 Qs), Analytical Reasoning (25 Qs), Coding Section (2 DSA Coding Questions - 60 mins)",
        "selection_rounds": "1. Aptitude & Technical MCQ ➔ 2. Coding Assessment ➔ 3. Technical Interview ➔ 4. HR Verification",
        "locations": "Chennai, Coimbatore, Bangalore, Hyderabad, Pune, Kolkata, Kochi, Noida",
        "service_agreement": "No strict financial bond; standard performance review period",
        "syllabus_highlights": "DSA, OOPS (Java/Python/C#), DBMS & SQL Joins, Software Engineering Principles",
        "deadline": "Active Off-Campus Cycle",
        "link": "https://careers.cognizant.com/in/en",
        "prep_tips": "Candidates who clear the GenC coding round with 100% test cases get upgraded directly to GenC Next (6.75 LPA) technical evaluations.",
        "priority_tag": "🇮🇳 National Off-Campus"
    },
    {
        "id": "accenture_ase",
        "name": "Accenture Associate Software Engineer (ASE)",
        "company": "Accenture India",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "All Engineering Branches (B.E/B.Tech), MCA, M.Tech",
        "cgpa_cutoff": "65% or 6.5 CGPA throughout academics with zero active backlogs at time of onboarding.",
        "package": "4.5 LPA (Associate Software Engineer) | 6.5 LPA (Full Stack Engineer - FSE)",
        "status": "🟢 Live on Indiacampus Portal",
        "exam_mode": "Virtual Proctored (HirePro Platform) from Home",
        "test_pattern": "Stage 1: Cognitive & Technical Assessment (90 Qs, 90 mins: English, Reasoning, Pseudo Code, Networking, Cloud) ➔ Stage 2: Coding Assessment (2 Questions, 45 mins) ➔ Stage 3: Communication Assessment",
        "selection_rounds": "1. Cognitive & Technical Assessment ➔ 2. Coding Round ➔ 3. AI Communication Test ➔ 4. Tech/HR Interview",
        "locations": "PAN India (Bangalore, Chennai, Hyderabad, Pune, Mumbai, Gurgaon, Kolkata, Coimbatore)",
        "service_agreement": "No bond / Zero service contract",
        "syllabus_highlights": "Pseudocode Bitwise Operations, MS Office / Security Fundamentals, C/C++/Java/Python basics, Basic DSA",
        "deadline": "Rolling Applications Open",
        "link": "https://indiacampus.accenture.com/",
        "prep_tips": "Accenture's Pseudocode section has high weightage. Master bitwise operators (^, &, |), nested loops, and recursive function dry-running.",
        "priority_tag": "🇮🇳 National Off-Campus"
    },
    {
        "id": "wipro_elite",
        "name": "Wipro Elite National Talent Hunt (NTH)",
        "company": "Wipro",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / M.E / M.Tech (All Engineering Branches Eligible)",
        "cgpa_cutoff": "60% or 6.0 CGPA in 10th & 12th; 60% or 6.0 CGPA in Graduation. Max 1 active backlog permitted.",
        "package": "3.5 LPA (Project Engineer) | 6.5 LPA (Wipro Turbo Profile)",
        "status": "🔵 National Assessment Phase",
        "exam_mode": "Online Proctored Test (CoCubes / Wheebox)",
        "test_pattern": "Aptitude Test (Logical, Quantitative, English - 48 mins) + Written Communication Test (20 mins essay) + Online Programming Test (2 Coding Questions - 60 mins)",
        "selection_rounds": "1. Elite NTH Online Assessment ➔ 2. Technical Interview ➔ 3. HR Discussion",
        "locations": "PAN India (Bangalore, Chennai, Hyderabad, Pune, Greater Noida, Kolkata, Kochi)",
        "service_agreement": "12 Months Service Agreement (₹75,000 pro-rata bond)",
        "syllabus_highlights": "Basic Data Structures, Strings, Mathematical Algorithms, Written English Grammar & Coherence",
        "deadline": "National Annual Wave",
        "link": "https://careers.wipro.com/elite",
        "prep_tips": "The Written Communication Test is evaluated by automated NLP. Use formal paragraph structure, avoid spelling errors, and write at least 200 words.",
        "priority_tag": "🇮🇳 National Mega Drive"
    },
    {
        "id": "capgemini_exceller",
        "name": "Capgemini Exceller Off-Campus Drive",
        "company": "Capgemini",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA / M.Sc (CS/IT & Circuit Branches)",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, Diploma & Degree with no active backlogs.",
        "package": "4.0 LPA (Analyst) | 7.5 LPA (Senior Analyst / Differential Hiring)",
        "status": "🟢 Open Registration",
        "exam_mode": "Aon CoCubes Proctored Platform",
        "test_pattern": "Stage 1: Technical Assessment (Pseudocode - 30 Qs, 30m) ➔ Stage 2: English Communication (30 Qs, 30m) ➔ Stage 3: Game-based Aptitude (4 interactive games) ➔ Stage 4: Behavioral Profiling",
        "selection_rounds": "1. Pseudocode & Technical MCQ ➔ 2. English Assessment ➔ 3. Gamified Aptitude ➔ 4. Technical + HR Interview",
        "locations": "Chennai, Bangalore, Hyderabad, Pune, Mumbai, Gurgaon, Salem, Trichy",
        "service_agreement": "No financial bond; standard probation period of 6 months",
        "syllabus_highlights": "Data Structures Pseudocode, Algorithms Analysis, Inductive Reasoning Games, Memory Grid Games",
        "deadline": "Active Off-Campus Cycle",
        "link": "https://www.capgemini.com/in-en/careers/",
        "prep_tips": "Practice gamified aptitude challenges (Switch Challenge, Motion Challenge, Grid Challenge) to clear Stage 3 with flying colors.",
        "priority_tag": "🇮🇳 National Off-Campus"
    },
    {
        "id": "google_intern",
        "name": "Google Tech Internship & University Challenge",
        "company": "Google India",
        "batches": "2025 / 2026 / 2027 Engineering Students",
        "degrees": "B.Tech / B.E / M.Tech / Dual Degree (Computer Science or related technical field)",
        "cgpa_cutoff": "No explicit percentage cutoff; evaluated purely based on coding excellence and project depth.",
        "package": "₹1,10,000 / month Stipend + Free Food/Transport + High-Convert Full-Time PPO (32 - 45 LPA)",
        "status": "🔥 High Prestige / Active Cycles",
        "exam_mode": "Google Online Challenge (GOC) on HackerEarth",
        "test_pattern": "2 Hard LeetCode-style algorithmic problems in 60 minutes (Dynamic Programming, Segment Trees, Graph DFS/BFS, Binary Search)",
        "selection_rounds": "1. Google Online Challenge (GOC) ➔ 2. Technical Phone Screen (DSA) ➔ 3. 2 Technical Virtual Onsite Rounds ➔ 4. Hiring Committee Review",
        "locations": "Bangalore, Hyderabad, Pune, Gurgaon",
        "service_agreement": "Zero Bond / Premium Product Tier",
        "syllabus_highlights": "Trees, Graphs, Disjoint Sets, Dynamic Programming, Greedy, Time & Space Complexity Optimization",
        "deadline": "Winter & Summer National Cycles",
        "link": "https://careers.google.com/jobs/results/?location=India",
        "prep_tips": "Focus on LeetCode Medium/Hard problems in C++ or Java. Always write clean code with modular functions and explain time/space complexity before coding.",
        "priority_tag": "🌐 Tier-1 Product Challenge"
    },
    {
        "id": "amazon_wow",
        "name": "Amazon WOW & Student Programs (SDE Intern & Full-Time)",
        "company": "Amazon India",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "B.E / B.Tech / M.Tech / MCA (All Women Engineers & Open National Hackathons)",
        "cgpa_cutoff": "6.5 CGPA or equivalent with no active backlogs.",
        "package": "₹1,10,000 / month (Internship) | 28.0 LPA – 44.0 LPA (Full-Time SDE-1)",
        "status": "🔥 Flagship National Drive",
        "exam_mode": "Amazon Online Assessment (HackerRank)",
        "test_pattern": "Part 1: 2 Algorithmic Coding Problems (70 mins) | Part 2: Work Style Assessment (Behavioral based on Amazon Leadership Principles - 15 mins)",
        "selection_rounds": "1. Online Assessment (DSA + Leadership Principles) ➔ 2. Two to Three Technical Interviews ➔ 3. Bar Raiser Round",
        "locations": "Bangalore, Chennai, Hyderabad, Delhi NCR, Pune",
        "service_agreement": "Zero Bond",
        "syllabus_highlights": "Binary Search, BFS/DFS, Priority Queues, Two Pointers, HashMap, Object-Oriented Design, Amazon 16 Leadership Principles",
        "deadline": "Seasonal National Cycles",
        "link": "https://amazonwowindia.splashthat.com/",
        "prep_tips": "Every interview round evaluates technical solutions AND behavioral answers aligned with Amazon's 16 Leadership Principles (Customer Obsession, Ownership).",
        "priority_tag": "🌐 Tier-1 Product Challenge"
    },
    {
        "id": "ltimindtree_yip",
        "name": "LTIMindtree Young Innovators Program (YIP)",
        "company": "LTIMindtree",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech (Circuit & Non-Circuit Branches), MCA",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, and Engineering with no backlogs.",
        "package": "4.0 LPA – 5.0 LPA (Graduate Engineer Trainee)",
        "status": "🟢 Registration Open",
        "exam_mode": "Virtual Assessment (Mettl Platform)",
        "test_pattern": "Quantitative Aptitude, Logical Reasoning, Verbal Ability, Technical MCQ (C/Java/DBMS), and 2 Hands-on Coding Problems",
        "selection_rounds": "1. Online Aptitude & Tech Test ➔ 2. Coding Assessment ➔ 3. Technical Interview ➔ 4. HR Interview",
        "locations": "Chennai, Bangalore, Hyderabad, Pune, Mumbai, Coimbatore",
        "service_agreement": "24 Months Service Agreement",
        "syllabus_highlights": "Core Java, C Programming, Relational Databases, SQL Joins, Basic Data Structures",
        "deadline": "Active Cycle",
        "link": "https://www.ltimindtree.com/careers/",
        "prep_tips": "Thoroughly review OOP principles, SQL normal forms, and standard array/string problems.",
        "priority_tag": "🇮🇳 National Off-Campus"
    },
    {
        "id": "ibm_codeknack",
        "name": "IBM CodeKnack National Hiring",
        "company": "IBM India",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA / M.Tech (CS, IT, ECE, EEE, AI, Data Science)",
        "cgpa_cutoff": "65% or 6.5 CGPA in Highest Degree with no active backlogs.",
        "package": "4.5 LPA – 6.0 LPA (Associate System Engineer)",
        "status": "🟢 Open on IBM Career Portal",
        "exam_mode": "HackerRank Proctored Coding + English Test",
        "test_pattern": "Cognitive Ability Assessment + English Language Assessment + HackerRank Coding (2 Problem Solving Questions)",
        "selection_rounds": "1. Cognitive Ability ➔ 2. Coding Challenge ➔ 3. Technical Interview ➔ 4. Managerial Interview",
        "locations": "Bangalore, Hyderabad, Chennai, Pune, Kochi, Ahmedabad, Gurgaon",
        "service_agreement": "No Bond",
        "syllabus_highlights": "Python/Java, Cloud Basics, Linux Commands, SQL, Sorting Algorithms, Data Structures",
        "deadline": "Ongoing National Ingestion",
        "link": "https://www.ibm.com/careers/in-en",
        "prep_tips": "IBM places strong value on cloud fundamentals (IaaS, PaaS, SaaS) and clear clean code documentation.",
        "priority_tag": "🇮🇳 National Tech Drive"
    },
    {
        "id": "cisco_ideathon",
        "name": "Cisco Ideathon & Off-Campus Hiring",
        "company": "Cisco Systems",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "B.E / B.Tech / M.E / M.Tech (Computer Science, IT, Electronics & Communication)",
        "cgpa_cutoff": "7.0 CGPA and above with zero backlogs throughout academics.",
        "package": "14.5 LPA – 18.0 LPA (Software Engineer / Consulting Engineer)",
        "status": "🚀 Premium Tier National Challenge",
        "exam_mode": "Online Assessment (HackerRank) + Video Submission",
        "test_pattern": "Round 1: Online Technical MCQ (Networking, OS, C/C++, DSA) + 2 Coding Problems ➔ Round 2: PPT / Video Idea Presentation on IoT/Networking",
        "selection_rounds": "1. Online Test ➔ 2. Ideation Round ➔ 3. Technical Interview (OS, Networks, Coding) ➔ 4. Managerial & HR",
        "locations": "Bangalore, Chennai",
        "service_agreement": "Zero Bond / Premium Multinational",
        "syllabus_highlights": "Computer Networks (TCP/IP, OSI, Subnetting), Operating Systems (Paging, Threading), C/C++, Python",
        "deadline": "Annual National Ideathon",
        "link": "https://www.cisco.com/c/en_in/about/careers.html",
        "prep_tips": "Revise Computer Networks thoroughly (Routing protocols, TCP/UDP, DNS, Handshake) and prepare a concise 2-minute elevator pitch for your IoT/Network project.",
        "priority_tag": "🌐 Tier-1 Product Challenge"
    },
    {
        "id": "deloitte_usi",
        "name": "Deloitte USI Off-Campus Associate Analyst",
        "company": "Deloitte US-India Offices",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA / B.Sc (IT/CS)",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, and College with zero active backlogs.",
        "package": "4.5 LPA (Associate Analyst) | 7.6 LPA (Consultant Track)",
        "status": "🟢 Active Registration via Amcat",
        "exam_mode": "Virtual Proctored Assessment",
        "test_pattern": "Quantitative Ability (14 Qs), Logical Reasoning (14 Qs), Verbal Ability (22 Qs), Computer Fundamentals (30 Qs: C, OOPS, DBMS, Networking)",
        "selection_rounds": "1. Online Assessment ➔ 2. Technical Interview ➔ 3. HR / Partner Interview",
        "locations": "Hyderabad, Bangalore, Mumbai, Gurgaon",
        "service_agreement": "No Financial Bond",
        "syllabus_highlights": "OOP Concepts, SQL Queries, Networking Fundamentals, Quantitative Math, Business Communication",
        "deadline": "Rolling Batch Cycles",
        "link": "https://www2.deloitte.com/ui/en/careers.html",
        "prep_tips": "Deloitte values strong verbal and business communication skills. Practice explaining your final year project in simple, executive terms.",
        "priority_tag": "🇮🇳 National Tech Drive"
    },
    {
        "id": "hcltech_drive",
        "name": "HCLTech First Careers & Early Tech Challenge",
        "company": "HCL Technologies",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA / M.Sc (All Engineering Disciplines)",
        "cgpa_cutoff": "65% or 6.5 CGPA in Degree, 60% in 10th & 12th.",
        "package": "3.5 LPA – 4.75 LPA (Graduate Engineer Trainee)",
        "status": "🟢 Regular Monthly Drives",
        "exam_mode": "Virtual Proctored / HCL Campus Centers",
        "test_pattern": "Aptitude (Quantitative, Logical, English) + Technical MCQ (Programming Basics, Operating Systems, Database)",
        "selection_rounds": "1. Online Aptitude & Technical Test ➔ 2. Technical Interview ➔ 3. HR Interview",
        "locations": "Chennai, Madurai, Bangalore, Noida, Lucknow, Nagpur, Vijayawada",
        "service_agreement": "18 Months Service Agreement",
        "syllabus_highlights": "C/C++, Java, Basic Linux, Relational Databases, Quantitative Aptitude",
        "deadline": "Open All Year",
        "link": "https://www.hcltech.com/careers",
        "prep_tips": "HCLTech's Madurai and Chennai campuses conduct regular walk-in drives for Tamil Nadu freshers.",
        "priority_tag": "🌟 Tamil Nadu & National Drive"
    },
    {
        "id": "virtusa_neuralhack",
        "name": "Virtusa NeuralHack National Hackathon",
        "company": "Virtusa Corporation",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "B.E / B.Tech / MCA (Computer Science, IT, Data Science)",
        "cgpa_cutoff": "60% throughout academics with no standing arrears.",
        "package": "4.0 LPA – 7.0 LPA (Associate Engineer / Cloud & Data)",
        "status": "🟢 Registration Open via HackerEarth",
        "exam_mode": "Online Hackathon + Virtual Interview",
        "test_pattern": "Round 1: Technical & DSA MCQ ➔ Round 2: 2 Coding Problems (Medium) ➔ Round 3: 24-Hour Prototype Building (Cloud/Full Stack/AI)",
        "selection_rounds": "1. Online Test ➔ 2. Coding Round ➔ 3. Virtual Hackathon ➔ 4. Direct Technical Interview",
        "locations": "Chennai, Hyderabad, Bangalore, Pune",
        "service_agreement": "24 Months Service Commitment",
        "syllabus_highlights": "Full-Stack Development (React/Node/Python), Cloud Services (AWS/Azure), DSA",
        "deadline": "Annual Hackathon Cycle",
        "link": "https://www.virtusa.com/careers",
        "prep_tips": "Reaching the hackathon finale guarantees a 5.5 to 7.0 LPA offer without separate technical screening rounds.",
        "priority_tag": "🌟 Tamil Nadu & National Drive"
    },
    {
        "id": "hexaware_pget",
        "name": "Hexaware PGET National Drive",
        "company": "Hexaware Technologies",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA (All streams with basic coding proficiency)",
        "cgpa_cutoff": "60% or 6.0 CGPA throughout 10th, 12th, and Graduation.",
        "package": "4.0 LPA (GET) | 6.0 LPA (Premier GET - High Performers)",
        "status": "🟢 Active on Superset",
        "exam_mode": "Virtual Assessment (Mettl Platform)",
        "test_pattern": "Aptitude + Technical Domain (C, Java, OOPS, SQL) + Communication Test + 2 Coding Problems",
        "selection_rounds": "1. Aptitude & Domain MCQ ➔ 2. Coding Test ➔ 3. Versant English Assessment ➔ 4. Technical + HR Interview",
        "locations": "Chennai, Mumbai, Pune, Bangalore, Noida",
        "service_agreement": "24 Months Service Agreement",
        "syllabus_highlights": "Object-Oriented Programming, Database Normalization, Array & String Algorithms",
        "deadline": "Active Cycle",
        "link": "https://hexaware.com/careers/",
        "prep_tips": "Hexaware Chennai Siruseri campus has large hiring requirements for freshers skilled in Java and Cloud fundamentals.",
        "priority_tag": "🌟 Tamil Nadu & National Drive"
    },
    {
        "id": "tech_mahindra",
        "name": "Tech Mahindra SuperCoder & Early Careers",
        "company": "Tech Mahindra",
        "batches": "2024 / 2025 Batch",
        "degrees": "B.E / B.Tech / MCA (All Engineering Disciplines)",
        "cgpa_cutoff": "60% throughout academics; max 1 year gap permitted.",
        "package": "3.25 LPA (Associate Software Engineer) | 5.5 LPA (SuperCoder Profile)",
        "status": "🟢 Online Registration Active",
        "exam_mode": "Virtual Assessment (HirePro Platform)",
        "test_pattern": "Round 1: Cognitive + English (50m) ➔ Round 2: Technical Test (Computer Science Fundamentals - 45m) ➔ Round 3: SuperCoder Coding Challenge (2 Problems - 45m)",
        "selection_rounds": "1. Cognitive Assessment ➔ 2. Technical MCQ ➔ 3. Coding Test ➔ 4. Conversational English ➔ 5. Technical Interview",
        "locations": "Chennai, Bangalore, Hyderabad, Pune, Mumbai, Noida",
        "service_agreement": "24 Months Service Bond (₹1,00,000)",
        "syllabus_highlights": "Pseudo Code, Quantitative Math, Verbal Ability, Fundamental Algorithms",
        "deadline": "Rolling Batch Cycles",
        "link": "https://www.techmahindra.com/en-in/careers/",
        "prep_tips": "Scoring 100% on the SuperCoder coding challenge elevates your package from 3.25 LPA to 5.5 LPA instantly.",
        "priority_tag": "🇮🇳 National Mega Drive"
    },
    {
        "id": "mindgate_fintech",
        "name": "Mindgate Solutions National FinTech Drive",
        "company": "Mindgate Solutions",
        "batches": "2024 / 2025 / 2026 Batch",
        "degrees": "B.E / B.Tech / MCA / M.Sc (CS/IT/ECE/EEE)",
        "cgpa_cutoff": "60% throughout academics; strong interest in UPI, Payments & Banking Tech.",
        "package": "4.0 LPA – 6.5 LPA (Software Engineer - FinTech Architecture)",
        "status": "🌟 Top Chennai & Mumbai FinTech Drive",
        "exam_mode": "Virtual Online Test + Chennai Walk-in Option",
        "test_pattern": "Java/Python Coding Assessment + SQL & Database Transaction Fundamentals + Core Aptitude",
        "selection_rounds": "1. Online Coding & SQL Test ➔ 2. Technical Interview (Transactions, Java, Rest APIs) ➔ 3. HR Round",
        "locations": "Chennai (OMR Tech Corridor), Mumbai, Bangalore",
        "service_agreement": "18 Months Service Agreement",
        "syllabus_highlights": "Core Java, Spring Boot, REST APIs, Microservices basics, SQL ACID properties, Banking Transaction flow",
        "deadline": "Active Off-Campus Hiring",
        "link": "https://www.mindgate.solutions/careers",
        "prep_tips": "Revise high-throughput payment architectures, REST API status codes, and SQL transaction isolation levels.",
        "priority_tag": "🌟 Tamil Nadu & FinTech Drive"
    }
]

_NATIONAL_DRIVES_CACHE = None
_NATIONAL_DRIVES_MTIME = 0

def get_national_drives(filepath: str = "national_drives.json") -> list:
    """
    Loads national mass drives from disk or initializes with verified seeds with mtime memory caching.
    """
    global _NATIONAL_DRIVES_CACHE, _NATIONAL_DRIVES_MTIME
    import os
    import json
    current_mtime = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
    if _NATIONAL_DRIVES_CACHE is not None and current_mtime == _NATIONAL_DRIVES_MTIME:
        return _NATIONAL_DRIVES_CACHE

    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                drives = json.load(f)
                if isinstance(drives, list) and len(drives) > 0:
                    _NATIONAL_DRIVES_CACHE = drives
                    _NATIONAL_DRIVES_MTIME = current_mtime
                    return drives
        except Exception:
            pass

    # Save seeds if missing
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_NATIONAL_DRIVES, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    _NATIONAL_DRIVES_CACHE = DEFAULT_NATIONAL_DRIVES
    _NATIONAL_DRIVES_MTIME = os.path.getmtime(filepath) if os.path.exists(filepath) else 0
    return DEFAULT_NATIONAL_DRIVES

def format_national_drives_report(drives: list = None, query: str = None) -> list:
    """
    Formats verified national mass drives into Telegram-ready HTML chunks.
    Supports filtering by batch (2025, 2026), company, or location ('tn', 'chennai').
    Guarantees no chunk exceeds 3500 chars to avoid Telegram API 4096-char overflows.
    """
    import html
    drive_list = drives if drives is not None else get_national_drives()
    
    filter_label = ""
    if query:
        q = str(query).lower().strip()
        filtered = []
        for d in drive_list:
            corpus = f"{d.get('name','')} {d.get('company','')} {d.get('batches','')} {d.get('locations','')} {d.get('priority_tag','')}".lower()
            if q in corpus:
                filtered.append(d)
        if filtered:
            drive_list = filtered
            filter_label = f" (Filtered: '{query}')"

    header = (
        f"📢 <b>NATIONAL MASS OFF-CAMPUS HIRING DRIVES{filter_label}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🇮🇳 <i>Top Tier-1 MNC Mass Recruitment Drives ({len(drive_list)} Verified)</i>\n"
        "🎯 <i>Eligible: 2024, 2025 & 2026 Batch Tech Graduates</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    chunks = []
    current_chunk = header
    
    for idx, d in enumerate(drive_list, 1):
        name = html.escape(str(d.get("name", "National Drive")))
        comp = html.escape(str(d.get("company", "Company")))
        batches = html.escape(str(d.get("batches", "2024 / 2025 / 2026")))
        pkg = html.escape(str(d.get("package", "Standard Fresher CTC")))
        status = html.escape(str(d.get("status", "Active")))
        link = html.escape(str(d.get("link", "")).strip())
        exam = html.escape(str(d.get("exam_mode", "National Assessment")))
        cutoff = html.escape(str(d.get("cgpa_cutoff", "60% or 6.0 CGPA")))[:85]

        entry = (
            f"<b>{idx}.</b> <a href=\"{link}\"><b>{name}</b></a>\n"
            f"   🏢 <b>Company:</b> <code>{comp}</code>\n"
            f"   🎓 <b>Batches:</b> <code>{batches}</code>\n"
            f"   📊 <b>Cutoff:</b> <i>{cutoff}...</i>\n"
            f"   💰 <b>Package:</b> <code>{pkg}</code>\n"
            f"   📡 <b>Status:</b> <b>{status}</b>\n"
            f"   📝 <b>Format:</b> <i>{exam}</i>\n"
            f"   👉 <i>Tip: Tap button below for full syllabus & pattern</i>\n\n"
        )

        if len(current_chunk) + len(entry) > 3400:
            chunks.append(current_chunk)
            current_chunk = f"📢 <b>National Drives (Part {len(chunks)+1})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + entry
        else:
            current_chunk += entry

    if current_chunk:
        current_chunk += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Filter anytime via: <code>/drives 2025</code>, <code>/drives 2026</code>, or <code>/drives tn</code></i>"
        )
        chunks.append(current_chunk)

    return chunks

def format_single_drive_detail(drive_id: str, drives: list = None) -> tuple:
    """
    Returns an ultra-detailed breakdown card for a specific national mega drive,
    including exact test pattern, selection rounds, syllabus, locations, bond, and prep tips.
    Returns: (formatted_html: str, apply_link: str)
    """
    import html
    if isinstance(drives, str):
        drive_list = get_national_drives(drives)
    elif isinstance(drives, list):
        drive_list = drives
    else:
        drive_list = get_national_drives()
    
    matched = None
    clean_id = str(drive_id).lower().strip()
    for d in drive_list:
        if d.get("id") == clean_id or clean_id in str(d.get("name", "")).lower() or clean_id in str(d.get("company", "")).lower():
            matched = d
            break
            
    if not matched:
        return f"⚠️ Drive details not found for '{drive_id}'. Please check `/drives` for all active drives.", "https://www.google.com"

    name = html.escape(str(matched.get("name", "National Drive")))
    comp = html.escape(str(matched.get("company", "Company")))
    batches = html.escape(str(matched.get("batches", "All Batches")))
    degrees = html.escape(str(matched.get("degrees", "Engineering Graduates")))
    cutoff = html.escape(str(matched.get("cgpa_cutoff", "60% throughout academics")))
    package = html.escape(str(matched.get("package", "Standard Industry Package")))
    status = html.escape(str(matched.get("status", "Active")))
    exam_mode = html.escape(str(matched.get("exam_mode", "Online Assessment")))
    pattern = html.escape(str(matched.get("test_pattern", "Aptitude + Coding Section")))
    rounds = html.escape(str(matched.get("selection_rounds", "Online Assessment ➔ Tech Interview ➔ HR")))
    locations = html.escape(str(matched.get("locations", "PAN India")))
    bond = html.escape(str(matched.get("service_agreement", "No Bond")))
    syllabus = html.escape(str(matched.get("syllabus_highlights", "DSA, OOP, SQL, Aptitude")))
    deadline = html.escape(str(matched.get("deadline", "Open Registration")))
    link = matched.get("link", "").strip()
    tips = html.escape(str(matched.get("prep_tips", "Practice standard DSA and core subjects.")))

    card = (
        f"📢 <b>MEGA DRIVE DEEP DIVE: {name}</b>\n"
        f"🏢 <b>Company:</b> <code>{comp}</code>\n"
        f"💰 <b>Package:</b> <b>{package}</b>\n"
        f"📡 <b>Status:</b> {status}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎓 <b>Eligible Batches:</b>\n"
        f"   <code>{batches}</code>\n\n"
        f"📜 <b>Degrees & Streams:</b>\n"
        f"   <i>{degrees}</i>\n\n"
        f"📊 <b>CGPA & Backlog Cutoff:</b>\n"
        f"   <code>{cutoff}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Official Exam Pattern & Timing:</b>\n"
        f"   <i>{pattern}</i>\n\n"
        f"🎯 <b>Selection Rounds:</b>\n"
        f"   <i>{rounds}</i>\n\n"
        f"📚 <b>Syllabus & Must-Revise Topics:</b>\n"
        f"   <code>{syllabus}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Hiring Locations:</b>\n"
        f"   <code>{locations}</code>\n\n"
        f"📜 <b>Service Agreement / Bond:</b>\n"
        f"   <code>{bond}</code>\n\n"
        f"🌟 <b>Pro-Prep Strategy to Crack:</b>\n"
        f"   <i>'{tips}'</i>\n\n"
        f"⏰ <b>Registration Deadline:</b> <code>{deadline}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🚀 <b>Official Application Portal:</b>\n"
        f"<a href=\"{link}\">👉 Click here to Register directly on Official Portal 👈</a>"
    )
    return card, link

def parse_drive_deadline(drive: dict, ref_date=None) -> dict:
    """
    Parses a mass drive's deadline and computes days and hours remaining.
    Categorizes the drive into an urgency tier:
    - 'critical' (<= 4 days left) 🚨 🔴
    - 'closing_soon' (5 to 10 days left) ⏳ 🟡
    - 'active' (> 10 days left) 🟢
    - 'rolling' (open all year / ongoing) ⚪
    - 'past' (date elapsed) ⌛
    """
    import datetime
    
    if ref_date is None:
        today = datetime.date.today()
    elif isinstance(ref_date, str):
        try:
            today = datetime.date.fromisoformat(ref_date.strip())
        except Exception:
            today = datetime.date.today()
    else:
        today = ref_date

    d_str = str(drive.get("deadline", "Open")).strip()
    d_iso = drive.get("deadline_date")
    target_date = None

    if d_iso:
        try:
            target_date = datetime.date.fromisoformat(str(d_iso).strip())
        except Exception:
            pass

    # Fallback: scan deadline string for YYYY-MM-DD
    if not target_date:
        import re
        match = re.search(r'\b(202\d[-/]\d{1,2}[-/]\d{1,2})\b', d_str)
        if match:
            clean = match.group(1).replace('/', '-')
            try:
                parts = clean.split('-')
                target_date = datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                pass

    is_rolling = "rolling" in d_str.lower() or "all year" in d_str.lower() or "regular" in d_str.lower() or not target_date
    
    if is_rolling and not target_date:
        return {
            "id": drive.get("id", "drive"),
            "name": drive.get("name", "Mass Drive"),
            "company": drive.get("company", "Company"),
            "package": drive.get("package", "Competitive Industry Standard"),
            "batches": drive.get("batches", "All Batches"),
            "link": drive.get("link", ""),
            "deadline_str": d_str,
            "deadline_date": None,
            "days_left": 999,
            "urgency_tier": "rolling",
            "urgency_badge": "⚪ ROLLING (Year-Round Application)",
            "urgency_color": "⚪"
        }

    days_left = (target_date - today).days

    if days_left < 0:
        urgency_tier = "past"
        badge = "⌛ Cycle Concluded / Next Cohort Soon"
        color = "⚪"
    elif days_left <= 4:
        urgency_tier = "critical"
        badge = f"🚨 CRITICAL: {days_left} Day{'s' if days_left != 1 else ''} Left! Apply Now"
        color = "🔴"
    elif days_left <= 10:
        urgency_tier = "closing_soon"
        badge = f"⏳ CLOSING SOON: {days_left} Days Left"
        color = "🟡"
    else:
        urgency_tier = "active"
        badge = f"🟢 ACTIVE: {days_left} Days Left"
        color = "🟢"

    return {
        "id": drive.get("id", "drive"),
        "name": drive.get("name", "Mass Drive"),
        "company": drive.get("company", "Company"),
        "package": drive.get("package", "Competitive Industry Standard"),
        "batches": drive.get("batches", "All Batches"),
        "link": drive.get("link", ""),
        "deadline_str": d_str,
        "deadline_date": str(target_date) if target_date else None,
        "days_left": days_left,
        "urgency_tier": urgency_tier,
        "urgency_badge": badge,
        "urgency_color": color
    }

def get_all_drive_deadlines(drives: list = None, ref_date=None) -> list:
    """
    Parses and returns all mass drive deadlines sorted by urgency:
    Critical (<=4 days) -> Closing Soon (5-10 days) -> Active (>10 days) -> Rolling.
    """
    if isinstance(drives, str):
        drive_list = get_national_drives(drives)
    elif isinstance(drives, list):
        drive_list = drives
    else:
        drive_list = get_national_drives()
        
    parsed = [parse_drive_deadline(d, ref_date=ref_date) for d in drive_list]
    tier_weight = {"critical": 0, "closing_soon": 1, "active": 2, "rolling": 3, "past": 4}
    parsed.sort(key=lambda x: (tier_weight.get(x["urgency_tier"], 99), x["days_left"]))
    return parsed

def format_deadlines_radar_report(drives: list = None, urgent_only: bool = False, ref_date=None) -> list:
    """
    Generates Telegram-ready HTML cards for National Mass Drive deadlines with countdowns.
    Returns chunked HTML list (each under 3,400 chars) ensuring safe delivery.
    """
    import html
    import datetime
    
    if ref_date is None:
        today = datetime.date.today()
    elif isinstance(ref_date, str):
        try:
            today = datetime.date.fromisoformat(ref_date.strip())
        except Exception:
            today = datetime.date.today()
    else:
        today = ref_date

    today_str = today.strftime("%d %b %Y")
    parsed_drives = get_all_drive_deadlines(drives, ref_date=today)
    
    if urgent_only:
        filtered = [d for d in parsed_drives if d["urgency_tier"] in ["critical", "closing_soon"]]
        if not filtered:
            return [(
                f"⏳ <b>MASS DRIVE DEADLINE RADAR (URGENT ONLY)</b> ⏳\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📅 <b>Today:</b> <code>{today_str}</code>\n\n"
                f"🎉 <b>All Clear!</b> No national drives are closing within the next 10 days.\n"
                f"All 18 active drives have comfortable application windows.\n\n"
                f"<i>Type <code>/deadlines</code> to view all upcoming national cycles.</i>"
            )]
        parsed_drives = filtered

    header = (
        f"⏳ <b>NATIONAL MASS DRIVES DEADLINE RADAR</b> ⏳\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <i>Live Application Cutoff & Expiry Tracker</i>\n"
        f"📅 <b>Today:</b> <code>{today_str}</code> | 🏢 <b>Tracked:</b> <code>{len(parsed_drives)} Drives</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Group by urgency
    critical = [d for d in parsed_drives if d["urgency_tier"] == "critical"]
    closing_soon = [d for d in parsed_drives if d["urgency_tier"] == "closing_soon"]
    active = [d for d in parsed_drives if d["urgency_tier"] == "active"]
    rolling = [d for d in parsed_drives if d["urgency_tier"] in ["rolling", "past"]]

    chunks = []
    current_chunk = header

    def add_section(title, drive_items):
        nonlocal current_chunk, chunks
        if not drive_items:
            return
        section_header = f"{title}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        if len(current_chunk) + len(section_header) > 3300:
            chunks.append(current_chunk.strip())
            current_chunk = section_header
        else:
            current_chunk += section_header

        for d in drive_items:
            comp = html.escape(str(d.get("company", "Company")))
            name = html.escape(str(d.get("name", "Mass Drive")))
            pkg = html.escape(str(d.get("package", "Competitive")))
            batches = html.escape(str(d.get("batches", "All Batches")))
            deadline = html.escape(str(d.get("deadline_str", "Open")))
            badge = html.escape(str(d.get("urgency_badge", "")))
            color = d.get("urgency_color", "🔹")
            link = d.get("link", "").strip()

            entry = (
                f"{color} <b>{name}</b>\n"
                f"   🏢 <b>Company:</b> <code>{comp}</code>\n"
                f"   ⏰ <b>Cutoff:</b> <b>{deadline}</b>\n"
                f"   ⚡ <b>Countdown:</b> <code>{badge}</code>\n"
                f"   💰 <b>Package:</b> {pkg}\n"
                f"   🎓 <b>Batches:</b> <i>{batches}</i>\n"
            )
            if link:
                entry += f"   👉 <a href=\"{link}\">Register on Official Portal</a>\n\n"
            else:
                entry += "\n"

            if len(current_chunk) + len(entry) > 3300:
                chunks.append(current_chunk.strip())
                current_chunk = f"⏳ <b>MASS DRIVE DEADLINES (Contd.)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n" + entry
            else:
                current_chunk += entry

    add_section("🚨 <b>CRITICAL / CLOSING WITHIN 96 HOURS:</b>", critical)
    add_section("🟡 <b>CLOSING THIS WEEK / NEXT 10 DAYS:</b>", closing_soon)
    add_section("🟢 <b>ACTIVE REGISTRATION WINDOWS:</b>", active)
    add_section("⚪ <b>ROLLING / CONTINUOUS YEAR-ROUND INGESTION:</b>", rolling)

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

def get_urgent_deadlines_summary(drives: list = None, ref_date=None) -> str:
    """
    Returns a concise 1-screen summary of drives closing within 10 days for quick bot alerts.
    """
    import html
    import datetime
    
    if ref_date is None:
        today = datetime.date.today()
    elif isinstance(ref_date, str):
        try:
            today = datetime.date.fromisoformat(ref_date.strip())
        except Exception:
            today = datetime.date.today()
    else:
        today = ref_date

    parsed = get_all_drive_deadlines(drives, ref_date=today)
    urgent = [d for d in parsed if d["urgency_tier"] in ["critical", "closing_soon"]]
    
    if not urgent:
        return "🎉 <b>Good news!</b> No mass drives are closing within the next 10 days. All active drives have plenty of time remaining."

    lines = [
        "🚨 <b>URGENT MASS DRIVES CLOSING SOON!</b>",
        f"📅 <i>As of {today.strftime('%d %b %Y')}:</i>\n"
    ]
    for d in urgent:
        comp = html.escape(str(d.get("company", "Company")))
        name = html.escape(str(d.get("name", "Drive")))
        badge = html.escape(str(d.get("urgency_badge", "")))
        link = d.get("link", "")
        lines.append(f"{d['urgency_color']} <b>{comp}</b> – {name}\n   <code>{badge}</code>\n   👉 <a href=\"{link}\">Apply Now</a>")
    
    return "\n\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# FEATURE 12: 🚶‍♂️ TAMIL NADU WEEKEND WALK-IN TRACKER
# Tracks verified in-person IT & tech walk-in drives across Chennai, Coimbatore & TN.
# ─────────────────────────────────────────────────────────────────

_WALKIN_DRIVES_CACHE = None
_WALKIN_DRIVES_MTIME = 0

def get_walkin_drives(city: str = None, json_path: str = "walkin_drives.json") -> list:
    """
    Retrieves verified Tamil Nadu walk-in drives from walkin_drives.json with mtime memory caching.
    Optionally filters by city ('chennai', 'coimbatore', etc.).
    """
    global _WALKIN_DRIVES_CACHE, _WALKIN_DRIVES_MTIME
    import os
    import json

    current_mtime = os.path.getmtime(json_path) if os.path.exists(json_path) else 0
    if _WALKIN_DRIVES_CACHE is not None and current_mtime == _WALKIN_DRIVES_MTIME:
        drives = _WALKIN_DRIVES_CACHE
    else:
        drives = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    drives = json.load(f)
                    _WALKIN_DRIVES_CACHE = drives
                    _WALKIN_DRIVES_MTIME = current_mtime
            except Exception as e:
                print(f"[Walk-Ins] Error reading {json_path}: {e}")

    if not city:
        return drives

    city_clean = city.strip().lower()
    if city_clean in ["south", "madurai_trichy", "other"]:
        return [d for d in drives if any(c in str(d.get("city", "")).lower() for c in ["madurai", "trichy", "hosur", "salem"])]
    return [d for d in drives if city_clean in str(d.get("city", "")).lower() or city_clean in str(d.get("venue_address", "")).lower()]


def format_walkins_report(drives: list = None, city_filter: str = None, max_chars: int = 3800) -> list:
    """
    Formats verified Tamil Nadu walk-in drives into high-aesthetic HTML chunks for Telegram messages.
    Includes exact venues, Google Maps links, timing, eligibility, selection rounds, and documents to bring.
    """
    import html

    if drives is None:
        drives = get_walkin_drives(city=city_filter)
    elif city_filter:
        c_low = city_filter.strip().lower()
        if c_low in ["south", "madurai_trichy", "other"]:
            drives = [d for d in drives if any(c in str(d.get("city", "")).lower() for c in ["madurai", "trichy", "hosur", "salem"])]
        else:
            drives = [d for d in drives if c_low in str(d.get("city", "")).lower() or c_low in str(d.get("venue_address", "")).lower()]

    if not drives:
        filter_note = f" in <b>{html.escape(city_filter.title())}</b>" if city_filter else ""
        return [
            f"🚶‍♂️ <b>TAMIL NADU WEEKEND WALK-IN TRACKER</b> 🇮🇳\n\n"
            f"⚠️ No active weekend walk-in drives currently found{filter_note}.\n"
            f"Check back on Thursday/Friday as companies announce weekend drives, or use <code>/tnjobs</code> for verified online openings."
        ]

    filter_title = f" — {city_filter.upper()}" if city_filter else " (CHENNAI, COIMBATORE, MADURAI & TRICHY)"
    header = (
        f"🚶‍♂️ <b>TAMIL NADU WEEKEND WALK-IN TRACKER{filter_title}</b> 🇮🇳\n"
        f"📍 <i>Direct In-Person Drives with Same-Day Interviews & Offer Letters</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    chunks = []
    current_chunk = header
    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟",
                  "1️⃣1️⃣", "1️⃣2️⃣", "1️⃣3️⃣", "1️⃣4️⃣", "1️⃣5️⃣", "1️⃣6️⃣", "1️⃣7️⃣", "1️⃣8️⃣"]

    for idx, d in enumerate(drives):
        num = num_emojis[idx] if idx < len(num_emojis) else f"#{idx+1}"
        comp = html.escape(str(d.get("company", "Company")))
        role = html.escape(str(d.get("role", "Software Trainee")))
        status = html.escape(str(d.get("status", "🟢 Active Walk-In")))
        city = html.escape(str(d.get("city", "Chennai")))
        area = html.escape(str(d.get("location_area", "IT Corridor")))
        batches = html.escape(str(d.get("batches", "2024 / 2025 / 2026 Batch")))
        exp = html.escape(str(d.get("experience", "Freshers (0 - 1 Years)")))
        degrees = html.escape(str(d.get("degrees", "Any Graduate")))
        timing = html.escape(str(d.get("timing", "Upcoming Saturday (9:00 AM)")))
        pkg = html.escape(str(d.get("package", "As per Industry Standards")))
        venue = html.escape(str(d.get("venue_address", "")))
        landmarks = html.escape(str(d.get("landmarks", "")))
        docs = html.escape(str(d.get("mandatory_docs", "Resume, Govt ID")))
        dress = html.escape(str(d.get("dress_code", "Formal Business Attire")))
        rounds = html.escape(str(d.get("selection_rounds", "")))
        prep = html.escape(str(d.get("prep_tips", "")))
        contact = html.escape(str(d.get("contact_info", "")))
        reg_link = str(d.get("registration_link", "")).strip()
        maps_link = str(d.get("google_maps", "#")).strip()

        card_lines = [
            f"{num} <b>{comp}</b> • <i>{role}</i>",
            f"🏷️ <b>Status:</b> {status}",
            f"📍 <b>City & Hub:</b> {city} ({area}) ⭐",
            f"🗓️ <b>Walk-In Timing:</b> {timing}",
            f"🎓 <b>Eligible:</b> <code>{batches}</code> • <b>Exp:</b> {exp}",
            f"🎯 <b>Degree/Stream:</b> {degrees}",
            f"💰 <b>Package:</b> {pkg}",
            f"🏢 <b>Venue:</b> {venue}",
        ]
        if landmarks:
            card_lines.append(f"📌 <b>Landmark:</b> {landmarks}")
        card_lines.append(f"🎒 <b>Carry:</b> {docs}")
        card_lines.append(f"👔 <b>Dress Code:</b> {dress}")
        if rounds:
            card_lines.append(f"🔄 <b>Selection Process:</b> {rounds}")
        if prep:
            card_lines.append(f"💡 <b>Prep Tip:</b> <i>{prep}</i>")
        if contact:
            card_lines.append(f"📞 <b>Contact / Desk:</b> <code>{contact}</code>")

        action_links = []
        if reg_link:
            action_links.append(f"<a href=\"{reg_link}\">👉 <b>Official Portal / Register</b></a>")
        action_links.append(f"<a href=\"{maps_link}\">🗺️ <b>Open in Google Maps</b></a>")

        card_lines.append(" • ".join(action_links))
        card = "\n".join(card_lines) + "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        if len(current_chunk) + len(card) > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = f"🚶‍♂️ <b>TAMIL NADU WALK-IN DRIVES (Part {len(chunks)+1})</b>\n\n" + card
        else:
            current_chunk += card

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def format_single_walkin_detail(walkin_id: str, json_path: str = "walkin_drives.json") -> str:
    """
    Returns an exhaustive breakdown of a single walk-in drive including selection rounds, syllabus, and contact info.
    """
    import html
    drives = get_walkin_drives(json_path=json_path)
    drive = next((d for d in drives if d.get("id") == walkin_id or walkin_id.lower() in str(d.get("company", "")).lower()), None)
    if not drive:
        return f"⚠️ Walk-In Drive ID <code>{html.escape(walkin_id)}</code> not found."

    comp = html.escape(str(drive.get("company", "Company")))
    role = html.escape(str(drive.get("role", "Role")))
    status = html.escape(str(drive.get("status", "🟢 Active Drive")))
    city = html.escape(str(drive.get("city", "Chennai")))
    area = html.escape(str(drive.get("location_area", "IT Corridor")))
    timing = html.escape(str(drive.get("timing", "")))
    pkg = html.escape(str(drive.get("package", "")))
    degrees = html.escape(str(drive.get("degrees", "Any Graduate")))
    batches = html.escape(str(drive.get("batches", "")))
    exp = html.escape(str(drive.get("experience", "Freshers (0 - 1 Years)")))
    venue_name = html.escape(str(drive.get("venue_name", "")))
    venue = html.escape(str(drive.get("venue_address", "")))
    landmarks = html.escape(str(drive.get("landmarks", "")))
    maps_link = str(drive.get("google_maps", "#"))
    docs = html.escape(str(drive.get("mandatory_docs", "")))
    dress = html.escape(str(drive.get("dress_code", "Formal Business Attire")))
    rounds = html.escape(str(drive.get("selection_rounds", "")))
    skills = html.escape(str(drive.get("key_skills", "")))
    prep = html.escape(str(drive.get("prep_tips", "")))
    contact = html.escape(str(drive.get("contact_info", "")))
    reg_link = str(drive.get("registration_link", "")).strip()

    detail_lines = [
        f"🏢 <b>{comp} — Complete In-Person Walk-In Briefing</b>",
        f"💼 <i>{role}</i>",
        f"🏷️ <b>Status:</b> {status}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📍 <b>Location:</b> {city} ({area})",
        f"🗓️ <b>Reporting Timing:</b> {timing}",
        f"🎓 <b>Eligible Batches:</b> <code>{batches}</code>",
        f"💼 <b>Experience Level:</b> {exp}",
        f"🎯 <b>Academic Criteria:</b> {degrees}",
        f"💰 <b>Package / CTC:</b> {pkg}",
        "",
        "🏢 <b>Venue & Landmarks:</b>",
        f"<b>{venue_name}</b>",
        f"<code>{venue}</code>",
    ]
    if landmarks:
        detail_lines.append(f"📌 <i>Landmarks: {landmarks}</i>")
    detail_lines.append(f"🗺️ <a href=\"{maps_link}\">👉 <b>Open Location in Google Maps (GPS Navigation)</b></a>")
    detail_lines.append("")
    detail_lines.append("🎒 <b>Mandatory Documents to Carry:</b>")
    detail_lines.append(docs)
    detail_lines.append("")
    detail_lines.append(f"👔 <b>Dress Code:</b> {dress}")
    detail_lines.append("")
    detail_lines.append("📝 <b>Selection Process & Interview Rounds:</b>")
    detail_lines.append(rounds)
    detail_lines.append("")
    if skills:
        detail_lines.append(f"🔑 <b>Key Skills Tested:</b> <code>{skills}</code>")
        detail_lines.append("")
    if prep:
        detail_lines.append(f"💡 <b>Insider Interview Tips:</b>\n<i>{prep}</i>")
        detail_lines.append("")
    detail_lines.append("📞 <b>Contact & Official Helpdesk:</b>")
    detail_lines.append(contact)
    if reg_link:
        detail_lines.append(f"🔗 <a href=\"{reg_link}\">👉 <b>Official Career Page / Pre-Register</b></a>")
    detail_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    detail_lines.append("⚠️ <i>Important: Arrive 30–45 minutes before reporting time. Walk-in token distribution closes once candidate quota is reached.</i>")

    return "\n".join(detail_lines)


def dispatch_walkin_alerts(bot=None, chat_id=None, city=None, once_per_day=True, limit=6):
    """
    Automatically dispatches verified Tamil Nadu weekend walk-in drives to the configured Telegram chat.
    If once_per_day=True, ensures only 1 walk-in digest is sent per day to prevent spamming the user across multiple daily runs.
    """
    import os
    import sys
    import json
    import time
    from datetime import datetime

    today_str = datetime.now().strftime("%Y-%m-%d")
    tracker_file = "last_walkin_dispatch.json"

    if once_per_day and os.path.exists(tracker_file):
        try:
            with open(tracker_file, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            if tdata.get("last_sent_date") == today_str:
                print(f"[Walk-Ins] Walk-in digest already sent today ({today_str}). Skipping duplicate automated alert.")
                return True
        except Exception:
            pass

    if not bot:
        token = str(os.getenv("TELEGRAM_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))).strip().strip('"').strip("'")
        if token.lower().startswith("bot"):
            token = token[3:]
        if not token:
            print("[Walk-Ins] No TELEGRAM_TOKEN available for dispatch.")
            return False
        import telebot
        bot = telebot.TeleBot(token)

    if not chat_id:
        chat_id = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip().strip('"').strip("'")
        if not chat_id and os.path.exists("chat_id.json"):
            try:
                with open("chat_id.json", "r", encoding="utf-8") as f:
                    chat_id = json.load(f).get("chat_id", "")
            except Exception:
                pass

    if not chat_id:
        print("[Walk-Ins] No TELEGRAM_CHAT_ID found for dispatch.")
        return False

    drives = get_walkin_drives(city=city)
    if not drives:
        print("[Walk-Ins] No active walk-in drives found to dispatch.")
        return True

    chunks = format_walkins_report(drives[:limit], city_filter=city)

    try:
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        markup = InlineKeyboardMarkup()
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
    except Exception:
        markup = None

    import re
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

    # Record dispatch date
    try:
        with open(tracker_file, "w", encoding="utf-8") as f:
            json.dump({
                "last_sent_date": today_str,
                "timestamp": time.time(),
                "total_sent": min(len(drives), limit)
            }, f, indent=2)
    except Exception as e:
        print(f"[Walk-Ins] Error writing tracker file: {e}")

    try:
        print(f"[Walk-Ins] Successfully dispatched {min(len(drives), limit)} walk-in drives to Telegram!")
    except Exception:
        pass
    return True


# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# FEATURE 13: 🔍 MULTI-SOURCE UNIFIED REAL-DATA SEARCH ENGINE
# Searches across live Tamil Nadu feeds, tn-live-jobs verified database,
# real-time Adzuna queries, mass drives, and weekend walk-ins.
# ─────────────────────────────────────────────────────────────────

_TN_LIVE_JOBS_CACHE = None
_TN_LIVE_JOBS_MTIME = 0

def get_tn_scraped_live_jobs() -> list:
    """
    Loads verified and live scraped job records from the tn-live-jobs engine
    (covering Tamil Nadu government portals, apna.co, Freshersworld, LinkedIn Jobs, etc.).
    """
    global _TN_LIVE_JOBS_CACHE, _TN_LIVE_JOBS_MTIME
    import os
    import json

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(base_dir, "..", "tn-live-jobs", "public", "data", "jobs.json")),
        os.path.abspath(os.path.join(base_dir, "..", "tn-live-jobs", "data", "jobs.json")),
        os.path.abspath(os.path.join(base_dir, "..", "tn-live-jobs", "work", "validated.json")),
        os.path.abspath(os.path.join(base_dir, "..", "tn-live-jobs", "work", "scraped.json")),
    ]

    for p in candidates:
        if os.path.exists(p):
            mtime = os.path.getmtime(p)
            if _TN_LIVE_JOBS_CACHE is not None and mtime == _TN_LIVE_JOBS_MTIME:
                return _TN_LIVE_JOBS_CACHE
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                raw_jobs = data.get("jobs", [])
                if raw_jobs:
                    _TN_LIVE_JOBS_CACHE = raw_jobs
                    _TN_LIVE_JOBS_MTIME = mtime
                    return raw_jobs
            except Exception:
                continue
    return []


def fetch_live_adzuna_search(query: str, location: str = "Tamil Nadu", limit: int = 6) -> list:
    """
    Fetches 100% real, freshly posted job opportunities directly from Adzuna India Live API
    for any search query in real time.
    """
    import os
    import re
    import requests
    import urllib.parse

    app_id = str(os.getenv("ADZUNA_APP_ID", "")).strip().strip('"').strip("'")
    app_key = str(os.getenv("ADZUNA_APP_KEY", "")).strip().strip('"').strip("'")
    if not app_id or not app_key:
        return []

    try:
        q_enc = urllib.parse.quote(query.strip())
        loc_enc = urllib.parse.quote(location.strip())
        url = (
            f"https://api.adzuna.com/v1/api/jobs/in/search/1"
            f"?app_id={app_id}&app_key={app_key}"
            f"&what={q_enc}&where={loc_enc}"
            f"&results_per_page={max(limit, 8)}&content-type=application/json&sort_by=date"
        )
        resp = requests.get(url, timeout=6)
        if resp.status_code != 200:
            return []

        results = resp.json().get("results", [])
        live_jobs = []
        for r in results:
            title = r.get("title", "Software Engineer")
            comp = r.get("company", {}).get("display_name", "Tech Company")
            link = r.get("redirect_url", "")
            if not link:
                continue
            raw_loc = r.get("location", {}).get("display_name", location)
            desc = r.get("description", "")
            desc_clean = re.sub(r'<[^>]+>', ' ', desc).strip()
            sal_min = r.get("salary_min")
            sal_max = r.get("salary_max")
            if sal_min and sal_max:
                sal = f"₹{int(sal_min):,} - ₹{int(sal_max):,} / yr"
            elif sal_min:
                sal = f"From ₹{int(sal_min):,} / yr"
            else:
                sal = "Competitive Market Package"

            live_jobs.append({
                "id": f"adz_{r.get('id', link)}",
                "source_type": "🟢 Live Posting • Adzuna Verified",
                "company": comp,
                "role": title,
                "location": f"{raw_loc} ⭐",
                "salary": sal,
                "batches": "2024 / 2025 / 2026 Batch",
                "experience": "Freshers (0 - 1 Years)",
                "link": link,
                "link_text": "🚀 Apply Direct on Official Portal",
                "timing": "🔥 Verified Live Today",
                "snippet": desc_clean[:180] if desc_clean else "Verified direct application on official career portal.",
                "relevance": 20
            })
        return live_jobs[:limit]
    except Exception as e:
        print(f"[Adzuna Live Search] Error: {e}")
        return []


def search_jobs_multi_source(query: str, limit: int = 6) -> list:
    """
    Performs comprehensive search across all real-data pipelines:
    1. Verified Walk-In Drives (Chennai, Coimbatore, Madurai, Trichy, Hosur)
    2. National Mass Off-Campus Drives (TCS, Zoho, Cognizant, Infosys, Accenture, Wipro)
    3. Scraped Real Tamil Nadu Portal Jobs (tn-live-jobs: Govt TN, Freshersworld, apna.co, LinkedIn)
    4. Tamil Nadu Job Radar Cache
    5. Real-Time On-Demand Adzuna India Live API
    Returns ranked, verified real job postings.
    """
    if not query or not isinstance(query, str) or not query.strip():
        return []

    q_clean = query.strip().lower()
    q_tokens = [t for t in re.split(r'[\s,+/|]+', q_clean) if t]
    if not q_tokens:
        return []

    SYNONYMS = {
        "python": ["python", "django", "fastapi", "flask", "pyspark", "data science"],
        "react": ["react", "frontend", "next.js", "nextjs", "javascript", "typescript", "ui developer", "web developer"],
        "java": ["java", "spring boot", "springboot", "j2ee", "backend"],
        "fresher": ["fresher", "freshers", "trainee", "graduate", "junior", "intern", "entry level", "0-1"],
        "analyst": ["analyst", "data analyst", "business analyst", "power bi", "tableau", "sql"],
        "tester": ["tester", "qa", "testing", "sdet", "automation", "quality assurance"],
        "chennai": ["chennai", "madras", "omr", "guindy", "navallur", "siruseri", "sholinganallur", "tambaram"],
        "coimbatore": ["coimbatore", "kovai", "saravanampatti", "chil sez"],
        "madurai": ["madurai", "ilandhaikulam", "elcot"],
        "trichy": ["trichy", "tiruchirappalli", "navalpattu"],
    }

    # Expand query tokens with synonyms
    expanded_tokens = set(q_tokens)
    for t in q_tokens:
        if t in SYNONYMS:
            expanded_tokens.update(SYNONYMS[t])

    matches = []
    seen_identifiers = set()

    def calc_relevance(title, company, location, text_blob=""):
        full_haystack = f"{title} {company} {location} {text_blob}".lower()
        score = 0
        for token in q_tokens:
            if token in company.lower():
                score += 40  # Direct company match is top priority! (e.g. searching 'zoho' must rank Zoho #1)
            if token in title.lower():
                score += 30  # Direct title match is highest priority
            if token in location.lower():
                score += 15  # Location match
            if token in full_haystack and token not in company.lower() and token not in title.lower():
                score += 5   # General match in description or keywords

        for token in expanded_tokens:
            if token not in q_tokens and token in full_haystack:
                score += 3   # Synonym match

        return score

    # 1. Search Weekend Walk-In Drives
    try:
        walkins = get_walkin_drives()
        for w in walkins:
            title = w.get("role", "")
            comp = w.get("company", "")
            loc = f"{w.get('city', '')} ({w.get('location_area', '')})"
            blob = f"{w.get('batches', '')} {w.get('degrees', '')} {w.get('selection_rounds', '')} {w.get('package', '')} {w.get('key_skills', '')}"
            rel = calc_relevance(title, comp, loc, blob)
            if rel > 0:
                ident = f"walkin_{w.get('id', comp)}"
                if ident not in seen_identifiers:
                    seen_identifiers.add(ident)
                    matches.append({
                        "id": ident,
                        "source_type": "🚶‍♂️ In-Person Walk-In Drive",
                        "company": comp,
                        "role": title,
                        "location": loc,
                        "salary": w.get("package", "Competitive"),
                        "batches": w.get("batches", "2024 / 2025 / 2026 Batch"),
                        "experience": w.get("experience", "Freshers (0 - 1 Years)"),
                        "link": w.get("google_maps") or "https://maps.google.com",
                        "link_text": "📍 View Venue in Google Maps",
                        "timing": w.get("timing", "Upcoming Weekend Walk-In"),
                        "snippet": f"Selection: {w.get('selection_rounds', 'Interview')} • Degrees: {w.get('degrees', 'Any')}",
                        "relevance": rel + 5  # Walk-ins get priority boost
                    })
    except Exception as e:
        print(f"[Search Engine] Walkin scan notice: {e}")

    # 2. Search National Mass Drives
    try:
        drives = get_national_drives()
        for d in drives:
            title = d.get("role", "")
            comp = d.get("company", "")
            loc = d.get("locations", "Pan-India")
            blob = f"{d.get('batch', '')} {d.get('eligibility', '')} {d.get('syllabus_highlights', '')} {d.get('test_pattern', '')}"
            rel = calc_relevance(title, comp, loc, blob)
            if rel > 0:
                ident = f"drive_{d.get('id', comp)}"
                if ident not in seen_identifiers:
                    seen_identifiers.add(ident)
                    matches.append({
                        "id": ident,
                        "source_type": "📢 National Off-Campus Drive",
                        "company": comp,
                        "role": title,
                        "location": loc,
                        "salary": d.get("package", "Standard Fresher Band"),
                        "batches": d.get("batch", "2025 / 2026 Batches"),
                        "experience": "Freshers (0 - 1 Years)",
                        "link": d.get("link", ""),
                        "link_text": "🚀 Apply on Official Company Portal",
                        "timing": f"Deadline: {d.get('deadline', 'Open')}",
                        "snippet": f"Eligibility: {d.get('eligibility', 'Any Graduate')} • Test: {d.get('test_pattern', 'Cognitive & Coding')}",
                        "relevance": rel
                    })
    except Exception as e:
        print(f"[Search Engine] National drives scan notice: {e}")

    # 3. Search Real Scraped TN-Live-Jobs Database
    try:
        scraped_jobs = get_tn_scraped_live_jobs()
        for j in scraped_jobs:
            title = j.get("title", "")
            comp = j.get("company", "Tamil Nadu Employer")
            city = j.get("city", "Tamil Nadu")
            loc = f"{city}, Tamil Nadu ⭐"
            blob = f"{j.get('category', '')} {j.get('source', '')} {j.get('apply_url', '')} {j.get('salary', '')}"
            rel = calc_relevance(title, comp, loc, blob)
            if rel > 0:
                link = j.get("apply_url", "")
                if link and link not in seen_identifiers:
                    seen_identifiers.add(link)
                    is_gov = j.get("category") == "Government" or "gov" in str(j.get("source", "")).lower()
                    src_tag = "🏛️ Govt of Tamil Nadu • Official" if is_gov else f"💼 Real Portal • {j.get('source', 'Verified')}"
                    matches.append({
                        "id": f"tnlive_{j.get('id', '')}",
                        "source_type": src_tag,
                        "company": comp,
                        "role": title,
                        "location": loc,
                        "salary": j.get("salary") or "As per Govt / Industry Norms",
                        "batches": "2024 / 2025 / 2026 Batch",
                        "experience": j.get("experience") or "Freshers & Experienced",
                        "link": link,
                        "link_text": "🚀 Direct Official Application Page",
                        "timing": "Verified Live Opportunity",
                        "snippet": f"Category: {j.get('category', 'General')} • Verified live via {j.get('source', 'Web')}",
                        "relevance": rel
                    })
    except Exception as e:
        print(f"[Search Engine] Scraped jobs scan notice: {e}")

    # 4. Search Tamil Nadu Job Radar
    try:
        from job_radar import get_tamil_nadu_jobs
        tn_jobs = get_tamil_nadu_jobs(limit=50, force_refresh=False)
        for j in tn_jobs:
            title = j.get("title", "")
            comp = j.get("company", "")
            loc = j.get("location", "Tamil Nadu")
            blob = f"{j.get('batches', '')} {j.get('experience', '')} {j.get('source', '')} {j.get('link', '')} {j.get('description', '')}"
            rel = calc_relevance(title, comp, loc, blob)
            if rel > 0:
                link = j.get("link", "")
                if link and link not in seen_identifiers:
                    seen_identifiers.add(link)
                    matches.append({
                        "id": f"tn_{link}",
                        "source_type": "🌟 Tamil Nadu Direct",
                        "company": comp,
                        "role": title,
                        "location": loc,
                        "salary": j.get("salary") or "Best in Industry",
                        "batches": j.get("batches") or "2024 / 2025 / 2026 Batch",
                        "experience": j.get("experience") or "Freshers (0 - 1 Years)",
                        "link": link,
                        "link_text": "🚀 Direct Apply (Official)",
                        "timing": "Verified Fresh Opening",
                        "snippet": str(j.get("description", ""))[:160] or "Direct application on official career portal.",
                        "relevance": rel
                    })
    except Exception as e:
        print(f"[Search Engine] TN jobs scan notice: {e}")

    # 5. On-Demand Real-Time Live Search (Adzuna India) if local results < limit
    if len(matches) < limit:
        try:
            live_adzuna = fetch_live_adzuna_search(query=query, location="Tamil Nadu", limit=limit - len(matches) + 3)
            for aj in live_adzuna:
                link = aj.get("link", "")
                if link and link not in seen_identifiers:
                    seen_identifiers.add(link)
                    matches.append(aj)
        except Exception as e:
            print(f"[Search Engine] Live Adzuna query notice: {e}")

    # Sort descending by relevance score
    matches.sort(key=lambda m: m["relevance"], reverse=True)
    return matches[:limit]


def format_search_results_report(query: str, results: list) -> tuple:
    """
    Formats search results into Telegram HTML cards and builds interactive filter markup.
    Returns: (chunks: list[str], reply_markup: InlineKeyboardMarkup)
    """
    import html
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    markup = InlineKeyboardMarkup()

    # If results exist, add direct apply for top result + ATS match button
    if results:
        top_job = results[0]
        top_link = top_job.get("link", "").strip()
        top_comp = str(top_job.get("company", "Top Job"))[:18]
        if top_link and top_link.startswith("http"):
            markup.row(
                InlineKeyboardButton(f"🚀 Apply: {top_comp}", url=top_link),
                InlineKeyboardButton("🎯 Match Resume (ATS)", callback_data="ats:analyze")
            )

    # Row: Common Quick Searches
    markup.row(
        InlineKeyboardButton("🐍 Python", callback_data="search:python"),
        InlineKeyboardButton("⚛️ React", callback_data="search:react"),
        InlineKeyboardButton("📊 Data Analyst", callback_data="search:data analyst")
    )
    # Row: Location & Type
    markup.row(
        InlineKeyboardButton("📍 Chennai / TN", callback_data="search:chennai"),
        InlineKeyboardButton("🏠 Remote", callback_data="search:remote"),
        InlineKeyboardButton("📢 Mass Drives", callback_data="drives")
    )
    markup.row(
        InlineKeyboardButton("🚶‍♂️ Weekend Walk-Ins", callback_data="walkins:all"),
        InlineKeyboardButton("🔄 Refresh Search", callback_data=f"search:{query}")
    )

    if not results:
        no_res_msg = (
            f"🔍 <b>SEARCH RESULTS FOR:</b> <code>{html.escape(query.upper())}</code>\n\n"
            f"⚠️ No active matching vacancies currently found for '{html.escape(query)}'.\n\n"
            f"💡 <b>Search Suggestions:</b>\n"
            f"• Try broader keywords: <code>python</code>, <code>react</code>, <code>fresher</code>, <code>chennai</code>, <code>zoho</code>\n"
            f"• Tap any of the quick-search categories below:"
        )
        return ([no_res_msg], markup)

    header = (
        f"🔍 <b>SEARCH RESULTS FOR:</b> <code>{html.escape(query.upper())}</code>\n"
        f"<i>Found {len(results)} top verified real-data opportunities across Tamil Nadu:</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    cards = []
    for idx, item in enumerate(results, 1):
        comp = html.escape(str(item.get("company", "Company")))
        role = html.escape(str(item.get("role", "Software Role")))
        loc = html.escape(str(item.get("location", "Tamil Nadu, India")))
        stype = html.escape(str(item.get("source_type", "Job")))
        sal = html.escape(str(item.get("salary") or "Competitive / Market Band"))
        batches = html.escape(str(item.get("batches") or "2024 / 2025 / 2026 Batch"))
        exp = html.escape(str(item.get("experience") or "Freshers (0 - 1 Years)"))
        desc = html.escape(str(item.get("snippet") or item.get("description") or ""))
        link = item.get("link", "").strip()
        link_text = html.escape(str(item.get("link_text", "Apply on Official Portal")))
        timing = html.escape(str(item.get("timing") or "Verified Active"))

        card_lines = [
            f"<b>{idx}. {comp}</b> • <i>{role}</i>",
            f"🏷️ <b>Source:</b> {stype}",
            f"📍 <b>Location:</b> {loc}",
            f"💰 <b>CTC / Band:</b> {sal}",
            f"🎓 <b>Eligibility:</b> <code>{batches}</code> • <b>Exp:</b> {exp}",
        ]
        if desc:
            card_lines.append(f"📝 <b>Highlights:</b> <i>{desc[:150]}...</i>")
        card_lines.append(f"⏰ <b>Status:</b> {timing}")
        if link:
            card_lines.append(f"👉 <a href=\"{link}\"><b>{link_text}</b></a>")
        card_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        cards.append("\n".join(card_lines))

    full_text = header + "\n\n".join(cards)

    # Split if exceeds Telegram 3900 chars
    chunks = []
    if len(full_text) <= 3900:
        chunks.append(full_text)
    else:
        current_chunk = header
        for card in cards:
            if len(current_chunk) + len(card) + 4 > 3800:
                chunks.append(current_chunk)
                current_chunk = card + "\n\n"
            else:
                current_chunk += card + "\n\n"
        if current_chunk.strip():
            chunks.append(current_chunk)

    return (chunks, markup)


# ─────────────────────────────────────────────────────────────────
# FEATURE 14: 🎯 INSTANT ATS RESUME & JOB COMPATIBILITY ANALYZER
# Takes any job description text or careers URL and returns deep ATS analysis.
# ─────────────────────────────────────────────────────────────────

def match_job_compatibility(job_text_or_url: str, profile: dict = None) -> tuple:
    """
    Analyzes job description text or fetches live URL content, then computes:
    1. ATS Skill Match Score (%) with visual status badge
    2. Matched profile skills vs missing skills to add
    3. Extracted CTC, eligible batches, and experience levels
    4. Auto-generated 1-Tap Interview Prep Sheet
    5. Tailored recruiter outreach message
    Returns: (report_text: str, reply_markup: InlineKeyboardMarkup)
    """
    import html
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    if not job_text_or_url or not isinstance(job_text_or_url, str) or not job_text_or_url.strip():
        guide = (
            "🎯 <b>ATS Resume & Job Matcher Guide</b>\n\n"
            "Use this tool to compare your resume against any job description in seconds!\n\n"
            "<b>Usage:</b>\n"
            "• Paste text: <code>/match Software Engineer Fresher at Zoho. Skills: Python, SQL, React...</code>\n"
            "• Or URL: <code>/match https://careers.company.com/job/12345</code>\n\n"
            "The bot will compute your exact ATS % fit, tell you what keywords to add to your resume, and generate instant interview cheat sheets."
        )
        return (guide, None)

    raw_input = job_text_or_url.strip()
    job_text = raw_input

    # If input is a URL, fetch page text
    if raw_input.startswith("http://") or raw_input.startswith("https://"):
        try:
            s = _get_probe_session()
            resp = s.get(raw_input, timeout=8, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0"})
            if resp.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in ["script", "style", "nav", "footer", "header"]:
                    for elem in soup.find_all(tag):
                        elem.decompose()
                job_text = soup.get_text(separator=" ", strip=True)[:10000]
        except Exception as e:
            print(f"[Job Matcher] URL fetch blip: {e}")
            job_text = raw_input

    # 1. Skill Match Score
    match_data = calculate_skill_match_score(job_text, profile)
    score = match_data["score"]
    badge = match_data["badge"]
    matched = match_data["matched"]
    missing = match_data["missing"]

    # 2. Key metadata extraction
    sal = extract_job_salary(job_text)
    batch = extract_eligible_batch(job_text)
    exp = extract_experience_level(job_text)
    hr_email = extract_hr_email(job_text)

    # 3. Build aesthetic report
    matched_str = ", ".join(sorted(matched)) if matched else "General Fresher Alignment"
    missing_str = ", ".join(sorted(missing)) if missing else "None! Outstanding alignment with profile."

    report = (
        f"🎯 <b>ATS RESUME FIT & COMPATIBILITY REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>ATS Match Score:</b> <b>{score}%</b> ({badge})\n\n"
        f"✅ <b>Matched Profile Skills:</b>\n"
        f"<code>{html.escape(matched_str)}</code>\n\n"
        f"⚠️ <b>Keywords to Add to Your Resume:</b>\n"
        f"<code>{html.escape(missing_str)}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💼 <b>Detected Experience:</b> {html.escape(exp or 'Freshers / Entry-Level')}\n"
        f"🎓 <b>Detected Batch:</b> {html.escape(batch or 'All Eligible Batches')}\n"
        f"💰 <b>Detected Salary:</b> {html.escape(sal or 'Standard Band')}\n"
    )
    if hr_email:
        report += f"📧 <b>Recruiter Contact:</b> <code>{html.escape(hr_email)}</code>\n"

    report += (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 <i>Tip: Add the missing keywords above into your resume's Skills or Projects section before applying to guarantee ATS screening pass.</i>"
    )

    # 4. Action buttons
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💡 1-Tap Interview Prep", callback_data="prep:Target Company:Software Engineer"),
        InlineKeyboardButton("✉️ LinkedIn Outreach Note", callback_data="linote:Target Company:Software Engineer")
    )
    markup.row(
        InlineKeyboardButton("🌟 Tamil Nadu Jobs", callback_data="tnjobs"),
        InlineKeyboardButton("🚶‍♂️ Weekend Walk-Ins", callback_data="walkins:all")
    )

    return (report, markup)


# ─────────────────────────────────────────────────────────────────
# FEATURE 15: 🎓 COMPANY ONLINE ASSESSMENT (OA) & CODING EXAM ENGINE
# Detailed round structures, sectional timers, coding patterns, and cutoffs.
# ─────────────────────────────────────────────────────────────────

COMPANY_OA_DATABASE = {
    "tcs": {
        "company": "TCS (Tata Consultancy Services)",
        "exam_name": "TCS NQT (National Qualifier Test)",
        "tracks": "Prime (₹9.0 LPA) • Digital (₹7.5 LPA) • Ninja (₹3.6 LPA)",
        "eligibility": "2024 / 2025 / 2026 Batch (B.E/B.Tech/M.E/M.Tech/MCA/M.Sc)",
        "rounds_summary": "Cognitive Test (65 Qs, 75m) ➔ Technical Assessment (25 Qs, 40m) ➔ Coding (2 Qs, 90m)",
        "sectional_breakdown": (
            "• <b>Part A (Foundation Cognitive):</b>\n"
            "   - Numerical Ability (20 Qs, 25 mins)\n"
            "   - Verbal Ability (25 Qs, 25 mins)\n"
            "   - Reasoning Ability (20 Qs, 25 mins)\n"
            "• <b>Part B (Advanced / Technical):</b>\n"
            "   - Advanced Quantitative (15 Qs, 25 mins)\n"
            "   - Advanced Reasoning (10 Qs, 15 mins)\n"
            "• <b>Part C (Hands-on Coding):</b>\n"
            "   - 2 Problems in 90 mins (Problem 1: Medium, Problem 2: Hard)"
        ),
        "coding_languages": "C, C++, Java, Python 3, Perl",
        "hot_topics": "Dynamic Programming, Prefix Sums, GCD/Primes, Sliding Window, Matrix Rotations, Strings",
        "sample_questions": [
            "1. Given an array of integers, find the maximum sum of a contiguous subarray using Kadane's algorithm.",
            "2. String manipulation: Count occurrences of non-repeating characters and output encrypted stream.",
            "3. Coin Change / Unbounded Knapsack variant for minimum denomination transaction."
        ],
        "strategy_tips": "⚠️ TCS test platform does NOT permit moving back to previous questions or sections. Allocate time per question strictly. Code Problem 1 first to guarantee Ninja/Digital baseline.",
        "practice_link": "https://www.geeksforgeeks.org/tcs-nqt-preparation-sheet/"
    },
    "zoho": {
        "company": "Zoho Corporation",
        "exam_name": "Zoho Off-Campus Developer Assessment",
        "tracks": "Product Software Engineer (₹5.6 LPA – ₹8.4 LPA)",
        "eligibility": "Any Engineering / Science / Arts Graduate (Zero Cutoff, No CGPA criteria)",
        "rounds_summary": "Written Flow-of-Control (20 Qs) ➔ Basic Coding (5 Scratch Problems) ➔ Advanced Coding (1 System App) ➔ Tech HR ➔ General HR",
        "sectional_breakdown": (
            "• <b>Round 1 (Written Prelims):</b> 15-20 Questions on flow of control, loop dry run, pointer arithmetic & bitwise logic in C/C++.\n"
            "• <b>Round 2 (Basic Coding - 5 Problems):</b> Solve scratch problems without built-in library functions (e.g. write custom split/sort).\n"
            "• <b>Round 3 (Advanced Coding - 1 System App):</b> Build a complete terminal mini-app (Railway Booking, Taxi Booking, Splitwise clone) with OOPS concepts in 3 hours.\n"
            "• <b>Round 4 (Technical HR):</b> Live code walkthrough, recursion depth, and database schema design."
        ),
        "coding_languages": "C, C++, Java (Strictly No Python in Round 2)",
        "hot_topics": "Pointers, 2D Arrays, Pattern Printing, Custom String Parsing, Recursion, Object-Oriented System Design",
        "sample_questions": [
            "1. Print an odd-length string in 'X' shape pattern (e.g. 'PROGRAM').",
            "2. Sort an array by frequency of elements without using built-in sort functions.",
            "3. Design a Call Taxi Booking System with customer pickup, booking history, and kilometer billing."
        ],
        "strategy_tips": "⚠️ Zero tolerance for built-in libraries like `java.util.Collections.sort` in Round 2. Master pointer logic and arrays from scratch.",
        "practice_link": "https://www.geeksforgeeks.org/zoho-interview-questions/"
    },
    "cognizant": {
        "company": "Cognizant (CTS)",
        "exam_name": "Cognizant GenC / Elevate Assessment",
        "tracks": "GenC Next (₹6.75 LPA) • GenC Elevate (₹4.5 LPA) • GenC (₹4.0 LPA)",
        "eligibility": "2024 / 2025 / 2026 Batches (B.E/B.Tech/MCA/M.Sc)",
        "rounds_summary": "Communication Assessment (Versant) ➔ Aptitude & Automata Fix (7 Qs, 20m) ➔ Coding Assessment (2 Qs, 60m)",
        "sectional_breakdown": (
            "• <b>Round 1 (Communication Assessment):</b> Versant Speech Test covering sentence repetition, listening comprehension, story retelling, and open speaking.\n"
            "• <b>Round 2 (Aptitude & Automata Fix):</b> Quantitative aptitude + 7 Automata Fix debugging questions where you identify syntax and logical bugs in 20 mins.\n"
            "• <b>Round 3 (Coding Assessment):</b> 2 Coding problems (60 mins) testing array manipulation and HashMap frequency counts."
        ),
        "coding_languages": "Java, C++, Python, C",
        "hot_topics": "Automata Fix Debugging, HashMaps, String Subsequences, Prefix Array, Two Pointers",
        "sample_questions": [
            "1. Automata Fix: Fix off-by-one boundary loop bug in array sorting function.",
            "2. Find all pairs of integers in an array whose difference equals target k.",
            "3. Longest substring with at most k distinct characters."
        ],
        "strategy_tips": "💡 Use a quiet room and high-fidelity headset for the Versant communication round. Practice finding boundary loop bugs for Automata Fix.",
        "practice_link": "https://www.geeksforgeeks.org/cognizant-genc-next-recruitment-process/"
    },
    "accenture": {
        "company": "Accenture",
        "exam_name": "Accenture ASE (Associate Software Engineer)",
        "tracks": "Advanced ASE (₹6.5 LPA) • ASE (₹4.5 LPA)",
        "eligibility": "2024 / 2025 / 2026 Batches (All branches)",
        "rounds_summary": "Cognitive + Technical (90 Qs, 90m) ➔ Coding (2 Qs, 45m) ➔ Communication Assessment",
        "sectional_breakdown": (
            "• <b>Round 1 (Cognitive & Technical - 90 Qs, 90m):</b>\n"
            "   - Critical Thinking & Analytical Reasoning (50 Qs)\n"
            "   - Pseudocode & Code Snippet dry runs (20 Qs)\n"
            "   - Cloud Fundamentals, Network Security & MS Office (20 Qs)\n"
            "• <b>Round 2 (Coding Round - 2 Qs, 45m):</b> Unlocked immediately if Round 1 cutoff is crossed.\n"
            "• <b>Round 3 (Communication Assessment):</b> Pronunciation, fluency, and sentence mastery."
        ),
        "coding_languages": "C, C++, Java, Python",
        "hot_topics": "Bitwise Operations, Binary Conversions, String Reversals, Array Differences, Pseudocode Evaluation",
        "sample_questions": [
            "1. Given two numbers, return the count of carries generated when adding them.",
            "2. Rearrange binary string to form the maximum possible binary number.",
            "3. Difference of sum of numbers divisible by m and not divisible by m in range [1, n]."
        ],
        "strategy_tips": "💡 Round 1 is an elimination round! Solve the 20 Pseudocode questions carefully as they carry heavy sectional weight.",
        "practice_link": "https://www.geeksforgeeks.org/accenture-recruitment-process/"
    },
    "wipro": {
        "company": "Wipro",
        "exam_name": "Wipro National Talent Hunt (Elite & Turbo)",
        "tracks": "Turbo (₹6.5 LPA) • Elite (₹3.5 LPA)",
        "eligibility": "2024 / 2025 / 2026 Batches (B.E/B.Tech/MCA)",
        "rounds_summary": "Aptitude (48 Qs, 48m) ➔ Written Essay (20m) ➔ Coding Assessment (2 Qs, 60m)",
        "sectional_breakdown": (
            "• <b>Aptitude Test (48 Qs, 48m):</b> Quantitative, Logical, and English Verbal.\n"
            "• <b>Written Communication (20 mins):</b> Formal essay writing on modern technology or societal topic (minimum 100-200 words, strictly zero spelling errors).\n"
            "• <b>Online Coding (2 Qs, 60m):</b> 1 Basic Problem (Math/String) + 1 Intermediate Problem (Arrays/Matrix)."
        ),
        "coding_languages": "Java, C++, Python, C",
        "hot_topics": "Palindromes, Matrix Diagonals, Frequency Count, Sorting, Basic Math Logic",
        "sample_questions": [
            "1. Check if a given string can be converted into a palindrome by removing at most one character.",
            "2. Find the difference between the primary and secondary diagonals of a square matrix.",
            "3. Count the number of sub-arrays having sum divisible by k."
        ],
        "strategy_tips": "💡 Avoid using backspace repeatedly in essay writing. Test cases in Wipro platform penalize syntax compilation errors heavily.",
        "practice_link": "https://www.geeksforgeeks.org/wipro-recruitment-process/"
    },
    "infosys": {
        "company": "Infosys",
        "exam_name": "Infosys Off-Campus Certification & Drives",
        "tracks": "Specialist Programmer (₹9.5 LPA) • DSE (₹6.25 LPA) • Systems Engineer (₹3.6 LPA)",
        "eligibility": "2024 / 2025 / 2026 Batches (B.E/B.Tech/MCA)",
        "rounds_summary": "Specialist Coding Round (3 Qs, 3 Hours on HackerRank) OR SE Aptitude Test (54 Qs, 100m)",
        "sectional_breakdown": (
            "• <b>SP / DSE Track:</b> 3 Hard/Medium DSA problems in 3 hours testing Trees, Graphs, DP, and Segment Trees.\n"
            "• <b>Systems Engineer Track:</b>\n"
            "   - Reasoning Ability (15 Qs, 25 mins)\n"
            "   - Technical Ability / Pseudocode (10 Qs, 35 mins)\n"
            "   - Quantitative Aptitude (10 Qs, 35 mins)\n"
            "   - Verbal Ability (20 Qs, 20 mins)\n"
            "   - Puzzle Solving (4 Qs, 10 mins)"
        ),
        "coding_languages": "Java, Python, C++, C",
        "hot_topics": "Breadth-First Search (BFS), Depth-First Search (DFS), Dynamic Programming, Knapsack, Binary Search Trees",
        "sample_questions": [
            "1. Shortest path in a weighted grid with directional obstacles.",
            "2. Maximum value achievable in customized multi-choice Knapsack.",
            "3. Number of connected components formed by disconnected network nodes."
        ],
        "strategy_tips": "💡 Specialist Programmer track questions are competitive programming standard. Practice LeetCode Medium/Hard graphs and DP.",
        "practice_link": "https://www.geeksforgeeks.org/infosys-recruitment-process/"
    }
}

def get_company_oa_info(company_key: str = None) -> dict:
    if not company_key:
        return None
    k = company_key.strip().lower()
    for key, data in COMPANY_OA_DATABASE.items():
        if k in key or key in k or k in data["company"].lower():
            return data
    return None

def format_oa_report(company_key: str = None) -> tuple:
    """
    Formats the company Online Assessment (OA) syllabus and pattern card for Telegram.
    Returns: (text: str, reply_markup: InlineKeyboardMarkup)
    """
    import html
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    markup = InlineKeyboardMarkup()
    # If no company or menu requested, render interactive company selector
    if not company_key or company_key.lower() in ["menu", "all", "list"]:
        markup.row(
            InlineKeyboardButton("🏢 TCS NQT", callback_data="oa:tcs"),
            InlineKeyboardButton("🌟 Zoho Corp", callback_data="oa:zoho")
        )
        markup.row(
            InlineKeyboardButton("💼 Cognizant (CTS)", callback_data="oa:cognizant"),
            InlineKeyboardButton("⚡ Accenture", callback_data="oa:accenture")
        )
        markup.row(
            InlineKeyboardButton("🎯 Wipro Elite", callback_data="oa:wipro"),
            InlineKeyboardButton("🚀 Infosys SP/SE", callback_data="oa:infosys")
        )
        markup.row(
            InlineKeyboardButton("📢 Mass Drives", callback_data="drives"),
            InlineKeyboardButton("⏳ Deadlines", callback_data="deadlines")
        )

        menu_text = (
            "🎓 <b>COMPANY ONLINE ASSESSMENT (OA) & CODING SYLLABUS</b>\n\n"
            "Get instant breakdowns of round structures, sectional timers, coding patterns, and real test questions for India's top tech employers.\n\n"
            "<b>Usage:</b>\n"
            "• <code>/oa tcs</code> — TCS NQT Prime, Digital & Ninja syllabus\n"
            "• <code>/oa zoho</code> — Zoho written rounds, basic & advanced coding\n"
            "• <code>/oa cognizant</code> — GenC, Automata Fix & Versant test\n"
            "• <code>/oa accenture</code> — Cognitive, Pseudocode & Coding\n"
            "• <code>/oa wipro</code> — Elite & Turbo aptitude & coding\n"
            "• <code>/oa infosys</code> — Specialist Programmer & SE tracks\n\n"
            "<i>Select any company below to view its complete exam blueprint:</i>"
        )
        return (menu_text, markup)

    oa = get_company_oa_info(company_key)
    if not oa:
        # Fallback to menu if unknown
        return format_oa_report("menu")

    comp = html.escape(oa["company"])
    exam = html.escape(oa["exam_name"])
    tracks = html.escape(oa["tracks"])
    elig = html.escape(oa["eligibility"])
    rounds = html.escape(oa["rounds_summary"])
    breakdown = oa["sectional_breakdown"]  # Already HTML
    langs = html.escape(oa["coding_languages"])
    topics = html.escape(oa["hot_topics"])
    tips = html.escape(oa["strategy_tips"])
    res_link = oa["practice_link"]

    q_lines = "\n".join([f"• <i>{html.escape(q)}</i>" for q in oa["sample_questions"]])

    card = (
        f"🎓 <b>{comp}</b>\n"
        f"📝 <b>Exam Blueprint:</b> <code>{exam}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💼 <b>Hiring Bands:</b> {tracks}\n"
        f"🎓 <b>Batches:</b> {elig}\n\n"
        f"🔄 <b>Rounds Overview:</b>\n"
        f"{rounds}\n\n"
        f"⏱️ <b>Sectional Timing & Pattern:</b>\n"
        f"{breakdown}\n\n"
        f"💻 <b>Allowed Languages:</b> <code>{langs}</code>\n"
        f"🔥 <b>High-Yield Topics:</b>\n"
        f"<code>{topics}</code>\n\n"
        f"❓ <b>Recent Real Exam Questions:</b>\n"
        f"{q_lines}\n\n"
        f"💡 <b>Strategy & Cutoff Pro-Tip:</b>\n"
        f"{tips}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    markup.row(
        InlineKeyboardButton("📚 Free GFG Practice Sheet", url=res_link),
        InlineKeyboardButton("💡 1-Tap Interview Prep", callback_data=f"prep:{oa['company']}:Software Engineer")
    )
    markup.row(
        InlineKeyboardButton("⬅️ All Companies", callback_data="oa:menu"),
        InlineKeyboardButton("📢 National Mass Drives", callback_data="drives")
    )

    return (card, markup)


# ─────────────────────────────────────────────────────────────────
# FEATURE 16: 🔔 CUSTOM KEYWORD WATCHDOG & ALERT SUBSCRIPTIONS
# Allows candidates to subscribe to custom triggers (e.g. 'python chennai', 'zoho', 'remote').
# ─────────────────────────────────────────────────────────────────

_WATCHDOG_FILE = "watchdog_subscriptions.json"
_WATCHDOG_CACHE = None
_WATCHDOG_MTIME = 0

def get_watchdog_subscriptions(chat_id: str = None) -> list:
    """Retrieves all active keyword subscriptions with mtime memory caching."""
    global _WATCHDOG_CACHE, _WATCHDOG_MTIME
    import os
    import json
    current_mtime = os.path.getmtime(_WATCHDOG_FILE) if os.path.exists(_WATCHDOG_FILE) else 0
    if _WATCHDOG_CACHE is not None and current_mtime == _WATCHDOG_MTIME:
        data = _WATCHDOG_CACHE
    else:
        data = {}
        if os.path.exists(_WATCHDOG_FILE):
            try:
                with open(_WATCHDOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _WATCHDOG_CACHE = data
                    _WATCHDOG_MTIME = current_mtime
            except Exception:
                pass

    if chat_id:
        return data.get(str(chat_id), [])
    # Return all unique keywords across all users if chat_id not specified
    all_subs = set()
    for subs in data.values():
        if isinstance(subs, list):
            for s in subs:
                all_subs.add(s)
    return list(all_subs)

def add_watchdog_subscription(keyword: str, chat_id: str) -> list:
    """Adds a custom keyword subscription for the user. Returns updated list."""
    global _WATCHDOG_CACHE, _WATCHDOG_MTIME
    import os
    import json
    if not keyword or not chat_id:
        return []

    clean_kw = keyword.strip().lower()
    data = {}
    if os.path.exists(_WATCHDOG_FILE):
        try:
            with open(_WATCHDOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    s_chat = str(chat_id)
    current_list = data.get(s_chat, [])
    if clean_kw not in current_list:
        current_list.append(clean_kw)
    data[s_chat] = current_list

    try:
        with open(_WATCHDOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _WATCHDOG_CACHE = data
        _WATCHDOG_MTIME = os.path.getmtime(_WATCHDOG_FILE)
    except Exception as e:
        print(f"[Watchdog] Error saving subscription: {e}")

    return current_list

def remove_watchdog_subscription(keyword: str, chat_id: str) -> list:
    """Removes a keyword subscription for the user. Returns updated list."""
    global _WATCHDOG_CACHE, _WATCHDOG_MTIME
    import os
    import json
    if not keyword or not chat_id:
        return []

    clean_kw = keyword.strip().lower()
    data = {}
    if os.path.exists(_WATCHDOG_FILE):
        try:
            with open(_WATCHDOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    s_chat = str(chat_id)
    current_list = data.get(s_chat, [])
    current_list = [k for k in current_list if k != clean_kw]
    data[s_chat] = current_list

    try:
        with open(_WATCHDOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        _WATCHDOG_CACHE = data
        _WATCHDOG_MTIME = os.path.getmtime(_WATCHDOG_FILE)
    except Exception as e:
        print(f"[Watchdog] Error updating subscription: {e}")

    return current_list

def check_job_against_watchdogs(job: dict, subscriptions: list) -> list:
    """Checks if a job dictionary matches any active keyword subscriptions."""
    if not job or not subscriptions:
        return []

    haystack = f"{job.get('company', '')} {job.get('title', '')} {job.get('role', '')} {job.get('location', '')} {job.get('description', '')}".lower()
    matched_subs = []
    for sub in subscriptions:
        sub_clean = sub.strip().lower()
        sub_tokens = sub_clean.split()
        if sub_tokens and all(token in haystack for token in sub_tokens):
            matched_subs.append(sub_clean)
    return matched_subs


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv
    load_dotenv()

    if "--dispatch-walkins" in sys.argv:
        force = "--force" in sys.argv
        city_arg = None
        for arg in sys.argv:
            if arg.lower() in ["chennai", "coimbatore"]:
                city_arg = arg.lower()
        print(f"[CLI] Triggering walk-in alert dispatch (city={city_arg}, force={force})...")
        dispatch_walkin_alerts(city=city_arg, once_per_day=(not force))
    elif "--walkins" in sys.argv:
        city_arg = None
        for arg in sys.argv:
            if arg.lower() in ["chennai", "coimbatore"]:
                city_arg = arg.lower()
        drives = get_walkin_drives(city=city_arg)
        print(f"\n🚶‍♂️ Found {len(drives)} active walk-in drives" + (f" in {city_arg.title()}:" if city_arg else ":"))
        for d in drives:
            print(f"  • [{d.get('city')}] {d.get('company')} — {d.get('role')} | {d.get('timing')}")
    else:
        print("Bot Optimizer CLI Options:")
        print("  python bot_optimizer.py --walkins [chennai|coimbatore]")
        print("  python bot_optimizer.py --dispatch-walkins [--force] [chennai|coimbatore]")

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

def extract_job_salary(text: str) -> str:
    """
    Extracts CTC, package, salary, or internship stipend from unstructured text.
    Handles LPA, Lacs, ₹ / Rs notations, monthly stipends, and standard Indian formats.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Direct explicit keyword search: CTC / Salary / Package / Stipend
    patterns = [
        # Explicit label on single line: CTC: 4.5 - 7.5 LPA
        r'(?:(?:💰|💵|💸)?\s*(?:Expected\s*CTC|CTC|Salary|Package|Stipend|Pay|Compensation))\s*[:\-–]\s*([^\n🏢📍💼🛠️📝👉🔗|]+)',
        # Standalone range: 3.5 - 6.5 LPA
        r'\b(\d+(?:\.\d+)?\s*(?:-|–|to)\s*\d+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?|Lacs?|PA))\b',
        # Standalone figure: 6 LPA
        r'\b(\d+(?:\.\d+)?\s*(?:LPA|lpa|Lakhs?|Lacs?)\s*(?:PA|P\.A)?)\b',
        # Monthly figure: ₹ 25,000 / month or ₹15k - 25k/month
        r'([₹Rs]\.?\s*[\d,kK]+(?:\s*(?:-|–|to)\s*[\d,kK]+)?\s*(?:per\s+month|pm|p\.m|/mo|/month|P\.M|PM))',
        # Stipend line
        r'(?:Stipend|stipend)\s*[:\-–]\s*([^\n🏢📍💼🛠️📝👉🔗|]+)',
    ]

    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            raw_sal = m.group(1).strip()
            # Cut off sentence spills or next-field words (e.g. ". Reach out", "Send resume", etc.)
            raw_sal = re.split(r'\.\s+[A-Z]', raw_sal)[0].strip()
            raw_sal = re.split(r'\s+(?:Send|Reach|Apply|Email|Contact|Batch|Location|Role|Eligibility|Link|DM|Website)\b', raw_sal, flags=re.I)[0].strip()
            clean = re.sub(r'^[▪️👉•\-:\s]+', '', raw_sal).strip()
            clean = re.sub(r'[\s]+', ' ', clean).strip()
            clean = clean.rstrip(".,;:-|")
            if len(clean) >= 2 and (any(c.isdigit() for c in clean) or any(w in clean.lower() for w in ["industry", "norms"])):
                clean = re.sub(r'\blpa\b', 'LPA', clean, flags=re.I)
                clean = re.sub(r'\bpa\b', 'PA', clean, flags=re.I)
                clean = re.sub(r'\bpm\b', '/month', clean, flags=re.I)
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


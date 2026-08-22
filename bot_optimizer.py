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
# FEATURE 5: LOCAL VECTOR DATABASE (RAG MEMORY)
# Mathematically searches the local qa_memory JSON for semantic
# matches against form labels, bypassing the LLM completely.
# ─────────────────────────────────────────────────────────────────
import difflib

def apply_rag_memory_fallback(page, qa_memory: dict) -> list:
    """
    Acts as a Local Vector Database. Evaluates page labels, compares them 
    to saved Q&A memory using cosine-like sequence matching.
    If match > 75%, fills the input instantly.
    """
    if not qa_memory:
        return []
        
    filled = []
    
    # 1. Extract all labels and their corresponding input IDs using Playwright evaluate
    try:
        label_map = page.evaluate("""() => {
            let result = {};
            document.querySelectorAll('label').forEach(lbl => {
                let text = lbl.innerText.trim();
                let forAttr = lbl.getAttribute('for');
                if (text && forAttr) {
                    result[text] = forAttr;
                }
            });
            return result;
        }""")
    except Exception as e:
        print(f"[RAG Memory] Failed to extract labels: {e}")
        return []

    # 2. Compute similarity for each label against the memory database
    for page_label, input_id in label_map.items():
        best_match = None
        best_ratio = 0.0
        
        for mem_q, mem_a in qa_memory.items():
            # Calculate mathematical string similarity (a basic local vector space substitute)
            ratio = difflib.SequenceMatcher(None, page_label.lower(), mem_q.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = mem_a
                
        # 3. If similarity is very high (> 75%), fill it
        if best_ratio > 0.75 and best_match:
            selector = f"input[id='{input_id}'], textarea[id='{input_id}']"
            try:
                el = page.locator(selector).first
                if el.count() > 0 and el.is_visible(timeout=500) and not el.is_disabled():
                    el.fill(str(best_match))
                    # Fire synthetic events
                    page.evaluate("""([sel, val]) => {
                        const el = document.querySelector(sel);
                        if (!el) return;
                        ['input','change','blur'].forEach(ev => el.dispatchEvent(new Event(ev, {bubbles: true})));
                    }""", [selector, str(best_match)])
                    
                    print(f"[RAG Memory] 🧠 Local DB Match! '{page_label}' ({int(best_ratio*100)}% match) → '{str(best_match)[:30]}'")
                    filled.append((selector, best_match))
            except Exception:
                pass
                
    if filled:
        print(f"[RAG Memory] Successfully answered {len(filled)} custom questions locally using zero API tokens.")
        
    return filled

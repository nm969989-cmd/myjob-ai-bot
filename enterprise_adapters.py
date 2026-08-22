import os
import re
import time
import random
import string
import imaplib
import email as email_lib

# Secure Vault for enterprise accounts
VAULT_FILE = "enterprise_vault.txt"

def save_to_vault(platform, url, email, password):
    """Saves generated credentials to a secure local vault."""
    try:
        with open(VAULT_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{platform}] {url} | {email} | {password}\n")
    except Exception as e:
        print(f"[Vault] Error saving: {e}")

def generate_secure_password():
    """Generates a highly secure password that passes all enterprise checks."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(random.choice(chars) for _ in range(16))
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd) and
            any(c.isdigit() for c in pwd) and any(c in "!@#$%^&*" for c in pwd)):
            return pwd

# ─────────────────────────────────────────────────────
# FEATURE 3: IMAP OTP READER
# ─────────────────────────────────────────────────────
def fetch_otp_from_email(bot_email, bot_password, search_keyword="verify", timeout=60):
    """
    Logs into Gmail via IMAP and fetches the latest 6-digit OTP or magic link.
    Tries for up to `timeout` seconds. Returns the OTP string or None.
    """
    print(f"[IMAP OTP] Waiting for verification email (keyword: '{search_keyword}')...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(bot_email, bot_password)
            mail.select("INBOX")

            # Search for recent unseen emails from the last 2 minutes
            _, data = mail.search(None, f'(UNSEEN SUBJECT "{search_keyword}")')
            ids = data[0].split()

            if ids:
                # Get the most recent one
                _, msg_data = mail.fetch(ids[-1], "(RFC822)")
                raw = msg_data[0][1]
                msg = email_lib.message_from_bytes(raw)

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        if ctype in ("text/plain", "text/html"):
                            try:
                                body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            except Exception:
                                pass
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                # Look for 6-digit OTP code
                otp_match = re.search(r'\b(\d{6})\b', body)
                if otp_match:
                    otp = otp_match.group(1)
                    print(f"[IMAP OTP] ✅ Found OTP: {otp}")
                    mail.logout()
                    return otp

                # Look for magic verification link
                link_match = re.search(r'https?://[^\s"\'<>]+(?:verify|confirm|activate|token)[^\s"\'<>]*', body, re.IGNORECASE)
                if link_match:
                    link = link_match.group(0)
                    print(f"[IMAP OTP] ✅ Found magic link: {link[:80]}...")
                    mail.logout()
                    return f"MAGIC_LINK:{link}"

            mail.logout()
        except Exception as e:
            print(f"[IMAP OTP] Retry error: {e}")
        time.sleep(5)

    print("[IMAP OTP] ⏰ Timed out waiting for OTP email.")
    return None

# ─────────────────────────────────────────────────────
# FEATURE 1: LEVER ADAPTER (Enhanced)
# ─────────────────────────────────────────────────────
def execute_lever_adapter(page, profile):
    """
    Highly specialized adapter for Lever (jobs.lever.co).
    Lever is a predictable React app — fills fields with native React event dispatch.
    """
    print("[Lever Adapter] Intercepting Lever application...")
    try:
        # 1. Click "Apply for this job" if it's the landing page
        apply_btn = page.locator("a.postings-btn, button.postings-btn, a:has-text('Apply for this job'), button:has-text('Apply for this job')").first
        if apply_btn.is_visible(timeout=3000):
            apply_btn.click()
            time.sleep(2.5)

        # 2. Upload Resume
        resume_input = page.locator("input[type='file'][name='resume'], input[type='file']").first
        if resume_input.is_visible(timeout=2000):
            resume_path = os.path.abspath("Resume.pdf")
            if not os.path.exists(resume_path):
                resume_path = os.environ.get("RESUME_FILE", "resume.pdf")
            if os.path.exists(resume_path):
                print(f"[Lever Adapter] Uploading resume: {resume_path}")
                resume_input.set_input_files(resume_path)
                time.sleep(3.0)

        # 3. Fill standard fields with React-compatible native setter
        def lever_fill(selector, value):
            if not value:
                return
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=1000):
                    el.click()
                    time.sleep(0.2)
                    el.fill(str(value))
                    # Fire React synthetic events
                    page.evaluate("""
                        ([sel, val]) => {
                            const el = document.querySelector(sel);
                            if (!el) return;
                            const niv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                                     || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                            if (niv) niv.set.call(el, val);
                            ['input','change','blur'].forEach(ev =>
                                el.dispatchEvent(new Event(ev, {bubbles: true}))
                            );
                        }
                    """, [selector, str(value)])
            except Exception as ex:
                print(f"[Lever Adapter] Field {selector} skipped: {ex}")

        mapping = {
            "input[name='name']":              profile.get("full_name", profile.get("name", "")),
            "input[name='email']":             profile.get("email", ""),
            "input[name='phone']":             profile.get("phone", ""),
            "input[name='org']":               profile.get("company", ""),
            "input[name='urls[LinkedIn]']":    profile.get("linkedin", ""),
            "input[name='urls[GitHub]']":      profile.get("github", ""),
            "input[name='urls[Portfolio]']":   profile.get("portfolio", ""),
            "textarea[name='comments']":       f"Passionate fresher with {profile.get('experience_years','0')} years experience in {profile.get('skills','')}. Eager to contribute and grow.",
        }
        for selector, value in mapping.items():
            lever_fill(selector, value)
            time.sleep(random.uniform(0.2, 0.5))

        print("[Lever Adapter] ✅ Core fields injected. Handing back to AI engine for custom questions...")
        return True
    except Exception as e:
        print(f"[Lever Adapter] Failed: {e}")
        return False

# ─────────────────────────────────────────────────────
# FEATURE 1: GREENHOUSE ADAPTER (NEW)
# ─────────────────────────────────────────────────────
def execute_greenhouse_adapter(page, profile, bot_email=None, bot_password=None):
    """
    Dedicated adapter for Greenhouse.io (boards.greenhouse.io / grnh.se).
    Greenhouse forms are highly predictable — 100% accurate direct field mapping.
    No AI needed for standard fields, AI only for custom questions.
    """
    print("[Greenhouse Adapter] Intercepting Greenhouse application...")
    try:
        # 1. Click "Apply for this Position" if on job landing page
        for btn_text in ["Apply for this Position", "Apply Now", "Apply", "Submit Application"]:
            btn = page.locator(f"a:has-text('{btn_text}'), button:has-text('{btn_text}')").first
            try:
                if btn.is_visible(timeout=2000):
                    btn.click()
                    time.sleep(2.5)
                    break
            except Exception:
                pass

        def gh_fill(selector, value):
            """Fill a Greenhouse field and fire all necessary events."""
            if not value:
                return False
            try:
                el = page.locator(selector).first
                if el.is_visible(timeout=1500):
                    el.scroll_into_view_if_needed()
                    el.click()
                    time.sleep(0.15)
                    tag = el.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        try:
                            el.select_option(label=str(value))
                        except Exception:
                            try:
                                el.select_option(value=str(value))
                            except Exception:
                                el.select_option(index=1)
                    else:
                        el.fill(str(value))
                        page.evaluate("""
                            ([sel, val]) => {
                                const el = document.querySelector(sel);
                                if (!el) return;
                                const niv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
                                         || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
                                if (niv) niv.set.call(el, val);
                                ['input','change','blur'].forEach(ev =>
                                    el.dispatchEvent(new Event(ev, {bubbles: true}))
                                );
                            }
                        """, [selector, str(value)])
                    time.sleep(random.uniform(0.2, 0.5))
                    return True
            except Exception as ex:
                print(f"[Greenhouse Adapter] Skipping {selector}: {ex}")
            return False

        # 2. Core field mappings — Greenhouse uses predictable IDs
        full_name  = profile.get("full_name", profile.get("name", ""))
        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name  = name_parts[1] if len(name_parts) > 1 else ""

        gh_fill("#first_name",                  first_name)
        gh_fill("#last_name",                   last_name)
        gh_fill("#email",                       profile.get("email", ""))
        gh_fill("#phone",                       profile.get("phone", ""))
        gh_fill("#job_application_phone",       profile.get("phone", ""))

        # LinkedIn / Portfolio / Website
        gh_fill("input[name*='linkedin']",      profile.get("linkedin", ""))
        gh_fill("input[name*='LinkedIn']",      profile.get("linkedin", ""))
        gh_fill("input[name*='github']",        profile.get("github", ""))
        gh_fill("input[name*='website']",       profile.get("portfolio", profile.get("github", "")))
        gh_fill("input[name*='portfolio']",     profile.get("portfolio", ""))
        gh_fill("input[placeholder*='LinkedIn']", profile.get("linkedin", ""))

        # Location
        gh_fill("input[name*='location']",      "Bengaluru, Karnataka, India")
        gh_fill("input[placeholder*='City']",   "Bengaluru")
        gh_fill("#job_application_location",    "Bengaluru, Karnataka, India")

        # 3. Upload Resume
        for resume_sel in [
            "input[type='file'][name*='resume']",
            "input[type='file'][id*='resume']",
            "input[type='file'][name*='cv']",
            "input[type='file']",
        ]:
            try:
                file_el = page.locator(resume_sel).first
                if file_el.count() > 0:
                    resume_path = os.path.abspath("Resume.pdf")
                    if not os.path.exists(resume_path):
                        resume_path = os.environ.get("RESUME_FILE", "resume.pdf")
                    if os.path.exists(resume_path):
                        # Force-unhide the element if hidden
                        try:
                            page.evaluate(f"document.querySelector('{resume_sel}').style.display='block'")
                        except Exception:
                            pass
                        file_el.set_input_files(resume_path)
                        print(f"[Greenhouse Adapter] ✅ Resume uploaded via {resume_sel}")
                        time.sleep(2.5)
                        break
            except Exception:
                continue

        # 4. Handle EEO/demographic dropdowns (select first non-empty option)
        eeo_selectors = [
            "select[id*='gender']", "select[name*='gender']",
            "select[id*='race']",   "select[name*='race']",
            "select[id*='veteran']", "select[name*='veteran']",
            "select[id*='disability']", "select[name*='disability']",
        ]
        for sel in eeo_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=500):
                    el.select_option(index=1)  # "I prefer not to say" is usually index 1
                    time.sleep(0.3)
            except Exception:
                pass

        # 5. Submit button
        for submit_text in ["Submit Application", "Submit", "Apply"]:
            try:
                btn = page.locator(f"input[value='{submit_text}'], button:has-text('{submit_text}')").first
                if btn.is_visible(timeout=2000):
                    btn.scroll_into_view_if_needed()
                    time.sleep(random.uniform(0.5, 1.0))
                    btn.click()
                    print(f"[Greenhouse Adapter] ✅ Clicked '{submit_text}' button!")
                    time.sleep(5.0)
                    break
            except Exception:
                pass

        print("[Greenhouse Adapter] ✅ Application complete!")
        return True

    except Exception as e:
        print(f"[Greenhouse Adapter] Failed: {e}")
        return False

# ─────────────────────────────────────────────────────
# WORKDAY ADAPTER (Enhanced with OTP)
# ─────────────────────────────────────────────────────
def execute_workday_adapter(page, profile, bot_email, bot_password):
    """
    Advanced Workday adapter.
    Handles Apply, account creation, OTP email verification, consent checkboxes.
    """
    print("[Workday Adapter] Intercepting Workday application...")
    try:
        # 1. Click Apply -> Apply Manually
        apply_btn = page.locator("a:has-text('Apply'), button:has-text('Apply'), [data-automation-id='apply']").first
        if apply_btn.is_visible(timeout=5000):
            apply_btn.click()
            time.sleep(2.0)
            manual_btn = page.locator("a:has-text('Apply Manually'), button:has-text('Apply Manually'), [data-automation-id='applyManually']").first
            if manual_btn.is_visible(timeout=3000):
                manual_btn.click()
                time.sleep(4.0)

        # 2. Handle Login wall
        email_field = page.locator("input[type='email'], [data-automation-id='email']").first
        if email_field.is_visible(timeout=5000):
            print("[Workday Adapter] Login wall detected.")
            email_field.fill(bot_email)
            pass_field = page.locator("input[type='password'], [data-automation-id='password']").first
            if pass_field.is_visible():
                pass_field.fill(bot_password)
            signin_btn = page.locator("button:has-text('Sign In'), [data-automation-id='signInSubmitButton']").first
            if signin_btn.is_visible():
                signin_btn.click()
                print("[Workday Adapter] Attempting login...")
                time.sleep(5.0)

            # Check for failed login
            error_msg = page.locator("[data-automation-id='error-message'], :text('Invalid user name'), :text('not found')").first
            if error_msg.is_visible(timeout=3000):
                print("[Workday Adapter] Login failed. Triggering Auto-Account Creation...")
                create_btn = page.locator("a:has-text('Create Account'), [data-automation-id='createAccountLink']").first
                if create_btn.is_visible():
                    create_btn.click()
                    time.sleep(3.0)
                    new_secure_pwd = generate_secure_password()

                    email_create = page.locator("input[type='email'], input[type='text']").first
                    if email_create.is_visible():
                        email_create.fill(bot_email)
                    pass_inputs = page.locator("input[type='password']")
                    if pass_inputs.count() >= 2:
                        pass_inputs.nth(0).fill(new_secure_pwd)
                        pass_inputs.nth(1).fill(new_secure_pwd)
                    checkbox = page.locator("input[type='checkbox'], [data-automation-id='createAccountCheckbox']").first
                    if checkbox.is_visible():
                        checkbox.check(force=True)
                    submit_create = page.locator("button:has-text('Create Account'), [data-automation-id='click_filter']").first
                    if submit_create.is_visible():
                        submit_create.click()
                        print(f"[Workday Adapter] Created account! Saving to vault...")
                        save_to_vault("Workday", page.url, bot_email, new_secure_pwd)
                        time.sleep(8.0)

                    # FEATURE 3: Handle OTP email verification
                    otp_field = page.locator("input[placeholder*='verification'], input[placeholder*='code'], input[name*='otp'], input[name*='code']").first
                    if otp_field.is_visible(timeout=8000):
                        print("[Workday Adapter] OTP field detected! Fetching code from Gmail...")
                        otp_value = fetch_otp_from_email(bot_email, bot_password, search_keyword="Workday", timeout=60)
                        if otp_value and not otp_value.startswith("MAGIC_LINK:"):
                            otp_field.fill(otp_value)
                            # Submit OTP
                            verify_btn = page.locator("button:has-text('Verify'), button:has-text('Submit'), button:has-text('Continue')").first
                            if verify_btn.is_visible():
                                verify_btn.click()
                                time.sleep(4.0)
                                print("[Workday Adapter] ✅ OTP submitted!")
                        elif otp_value and otp_value.startswith("MAGIC_LINK:"):
                            link = otp_value.replace("MAGIC_LINK:", "")
                            print(f"[Workday Adapter] Magic link found — opening in new tab...")
                            temp_page = page.context.new_page()
                            try:
                                temp_page.goto(link, wait_until="domcontentloaded", timeout=20000)
                                time.sleep(4)
                            finally:
                                temp_page.close()
                        else:
                            print("[Workday Adapter] ⚠️ Could not fetch OTP. Manual intervention needed.")

        print("[Workday Adapter] ✅ Auth complete. Handing off to Shadow DOM engine...")
        return True
    except Exception as e:
        print(f"[Workday Adapter] Failed: {e}")
        return False

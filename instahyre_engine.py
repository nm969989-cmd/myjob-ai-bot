import time
import random
import os
import json
from playwright.sync_api import sync_playwright

from playwright_stealth import stealth_sync
from bot_features import wait_for_otp

def human_scroll(page):
    """Simulates a human scrolling up and down the page while reading."""
    scroll_amount = random.randint(300, 700)
    page.mouse.wheel(0, scroll_amount)
    time.sleep(random.uniform(1.0, 2.5))
    page.mouse.wheel(0, -random.randint(100, 300))
    time.sleep(random.uniform(0.5, 1.5))

def human_distraction(context):
    """Simulates a human getting distracted by opening a new tab, browsing, and coming back."""
    if random.random() < 0.15:  # 15% chance
        print("[Instahyre Stealth] User got distracted. Opening a new tab...")
        distraction_page = context.new_page()
        try:
            distraction_page.goto("https://www.google.com", timeout=10000)
            time.sleep(random.uniform(2, 5))
            distraction_page.type("textarea[name='q']", "software engineering news", delay=random.randint(50, 150))
            distraction_page.keyboard.press("Enter")
            time.sleep(random.uniform(3, 8))
        except Exception:
            pass
        finally:
            distraction_page.close()
            time.sleep(random.uniform(1, 2))

def coffee_break():
    """Simulates the user stepping away from the computer or checking their phone."""
    if random.random() < 0.10:  # 10% chance
        break_time = random.randint(25, 45)
        print(f"[Instahyre Stealth] Taking a coffee break for {break_time} seconds...")
        time.sleep(break_time)

def human_text_highlighting(page):
    """Simulates a human dragging their mouse to highlight text while reading."""
    try:
        width = page.viewport_size['width']
        height = page.viewport_size['height']
        start_x = random.randint(200, width - 200)
        start_y = random.randint(200, height - 200)
        
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        time.sleep(random.uniform(0.1, 0.4))
        page.mouse.move(start_x + random.randint(50, 300), start_y + random.randint(10, 50), steps=10)
        time.sleep(random.uniform(0.5, 1.5))
        page.mouse.up()
        
        # Click somewhere to un-highlight
        time.sleep(random.uniform(1, 3))
        page.mouse.click(start_x - 50, start_y - 50)
    except Exception:
        pass

def human_mouse_wandering(page):
    """Randomly moves the mouse around the screen to simulate a bored or reading human."""
    try:
        width = page.viewport_size['width']
        height = page.viewport_size['height']
        for _ in range(random.randint(2, 4)):
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            page.mouse.move(x, y, steps=random.randint(10, 25))
            time.sleep(random.uniform(0.2, 0.7))
    except Exception:
        pass

def human_typing_with_mistakes(page, selector, text):
    """Types text like a human, occasionally making a typo and using backspace to correct it."""
    page.click(selector)
    time.sleep(random.uniform(0.2, 0.8))
    for char in text:
        # 5% chance to make a typo
        if random.random() < 0.05:
            wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
            page.keyboard.press(wrong_char)
            time.sleep(random.uniform(0.1, 0.3))
            page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.2, 0.5))
        
        page.keyboard.press(char)
        time.sleep(random.uniform(0.05, 0.18))

def send_instahyre_results_telegram(applied_jobs_list, total_found, success):
    """Send Instahyre results to Telegram as a consolidated message."""
    try:
        import telebot
        bot_token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not chat_id:
            chat_id_file = "chat_id.json"
            if os.path.exists(chat_id_file):
                try:
                    with open(chat_id_file, "r") as f:
                        data = json.load(f)
                        chat_id = data.get("chat_id")
                except: pass
        
        if not bot_token or not chat_id:
            return
        
        tg_bot = telebot.TeleBot(bot_token, parse_mode=None)
        
        status_icon = "✅" if success else "⚠️"
        applied_count = len(applied_jobs_list)
        
        msg = (
            f"{status_icon} *Instahyre Campaign Results*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 *Summary:*\n"
            f"  🔍 Jobs Found: *{total_found}*\n"
            f"  ✅ Successfully Applied: *{applied_count}*\n\n"
        )
        
        if applied_jobs_list:
            msg += "💼 *Applied To:*\n"
            for i, job in enumerate(applied_jobs_list[:20]):
                title = job.get("title", "Unknown")[:40]
                company = job.get("company", "Unknown")[:25]
                msg += f"  {i+1}. {title} — _{company}_\n"
            if len(applied_jobs_list) > 20:
                msg += f"  _...+{len(applied_jobs_list)-20} more_\n"
        
        msg += (
            f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Instahyre engine completed. Next auto-run at 11 PM._"
        )
        
        tg_bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[Instahyre] Telegram notification failed: {e}")

def run_instahyre_mass_apply(skills="Software Engineer Fresher", max_applications=20, email=None, password=None):
    """
    Autonomous engine to log into Instahyre and mass-apply to jobs using human-mimicking behavior.
    Returns (success: bool, message: str, applied_jobs: list)
    """
    # Credentials from params or environment
    if not email:
        email = os.getenv("INSTAHYRE_EMAIL", "manojprofessional007@gmail.com")
    if not password:
        password = os.getenv("INSTAHYRE_PASSWORD")
    
    if not password:
        return False, "Instahyre password not set. Use `/instahyre your_email | your_password` in Telegram.", []
    
    print(f"[Instahyre] Starting Stealth Mass-Applier Engine for {email}...")
    applied_count = 0
    applied_jobs_list = []
    total_jobs_found = 0
    
    with sync_playwright() as p:
        is_huggingface = "SPACE_ID" in os.environ
        # Force headless=False to bypass Cloudflare Turnstile (xvfb handles it on Hugging Face)
        browser = p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        auth_file = "instahyre_auth.json"
        has_auth = os.path.exists(auth_file)
        
        context_args = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "viewport": {'width': 1920, 'height': 1080}
        }
        if has_auth:
            context_args["storage_state"] = auth_file
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        stealth_sync(page)
        
        # --- ENHANCEMENT: Advanced Stealth Injection ---
        # Bypasses Cloudflare Turnstile and Datadome fingerprinting
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)

        try:
            # 0. Check Session
            needs_login = True
            if has_auth:
                print("[Instahyre] Found saved session. Checking if it's still valid...")
                page.goto("https://www.instahyre.com/candidate/opportunities/", timeout=60000)
                time.sleep(random.uniform(3, 5))
                
                # Cloudflare check on session opportunities page
                for _ in range(4): # Check up to 4 times (40 seconds max)
                    try:
                        page_text = page.locator("body").inner_text(timeout=2000).lower()
                        if "just a moment" in page_text or "cloudflare" in page_text or "security check" in page_text or "verify you are human" in page_text:
                            print("[Instahyre] Cloudflare protection detected on opportunities page! Waiting 10s for it to resolve...")
                            time.sleep(10)
                            human_mouse_wandering(page)
                        else:
                            break
                    except: pass
                
                # Verify we are on opportunities and body text has dashboard characteristics
                try:
                    body_text = page.locator("body").inner_text(timeout=3000).lower()
                    is_logged_in = (
                        "login" not in page.url.lower() and 
                        ("opportunity" in body_text or "job" in body_text or "apply" in body_text or "profile" in body_text or "sign out" in body_text)
                    )
                except:
                    is_logged_in = False
                    
                if is_logged_in:
                    print("[Instahyre] Session is valid! Skipping login.")
                    needs_login = False
                else:
                    print("[Instahyre] Session is invalid or blocked. Navigating to login...")

            if needs_login:
                # 1. Login
                print("[Instahyre] Navigating to login page...")
                page.goto("https://www.instahyre.com/login/", timeout=60000)
                time.sleep(random.uniform(3, 5))
                
                # Cloudflare check
                for _ in range(4): # Check up to 4 times (40 seconds max)
                    try:
                        page_text = page.locator("body").inner_text(timeout=2000).lower()
                        if "just a moment" in page_text or "cloudflare" in page_text or "security check" in page_text or "verify you are human" in page_text:
                            print("[Instahyre] Cloudflare protection detected! Waiting 10s for it to resolve...")
                            time.sleep(10)
                            human_mouse_wandering(page)
                        else:
                            break
                    except: pass

                # Human-like typing with mistakes
                human_mouse_wandering(page)
                
                # Try multiple selectors for email field
                email_selectors = ["input[name='email']", "input[type='email']", "input[placeholder*='email']", "#email", "input.email-input"]
                email_filled = False
                for sel in email_selectors:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=3000):
                            el.hover()
                            el.click()
                            time.sleep(random.uniform(0.5, 1.0))
                            human_typing_with_mistakes(page, sel, email)
                            email_filled = True
                            break
                    except: continue
                
                if not email_filled:
                    return False, "Could not find email input field on Instahyre login page.", []
                
                time.sleep(random.uniform(1, 2))
                
                # Try multiple selectors for password field
                human_mouse_wandering(page)
                pwd_selectors = ["input[name='password']", "input[type='password']", "input[placeholder*='password']", "#password"]
                pwd_filled = False
                for sel in pwd_selectors:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=3000):
                            el.hover()
                            el.click()
                            time.sleep(random.uniform(0.5, 1.0))
                            human_typing_with_mistakes(page, sel, password)
                            pwd_filled = True
                            break
                    except: continue
                
                if not pwd_filled:
                    return False, "Could not find password input field on Instahyre login page.", []
                
                time.sleep(random.uniform(1.5, 3))
                
                print("[Instahyre] Clicking login...")
                # Try multiple submit button selectors
                submit_selectors = ["button[type='submit']", "input[type='submit']", "button:has-text('Login')", "button:has-text('Sign In')", ".login-btn", ".btn-primary"]
                for sel in submit_selectors:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible(timeout=2000):
                            btn.hover()
                            time.sleep(random.uniform(0.5, 1.2))
                            btn.click()
                            break
                    except: continue
                
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(random.uniform(3, 5))
                
                # Auto-OTP Handling (If Instahyre asks for email verification)
                otp_detected = False
                try:
                    page_text = page.locator("body").inner_text(timeout=5000).lower()
                    otp_detected = (
                        "verify" in page.url or 
                        "verification" in page_text or
                        "otp" in page_text or
                        "enter code" in page_text
                    )
                except: pass
                
                if otp_detected:
                    print("[Instahyre] OTP Verification Detected! Booting up IMAP Sniper...")
                    bot_email_pass = os.getenv("BOT_EMAIL_PASSWORD")
                    if bot_email_pass:
                        otp_code = wait_for_otp(email, bot_email_pass, timeout_seconds=90)
                        if otp_code:
                            # Try to find the OTP input field
                            otp_selectors = [
                                "input[placeholder*='OTP']", "input[placeholder*='otp']",
                                "input[placeholder*='code']", "input[placeholder*='Code']",
                                "input[name*='code']", "input[name*='otp']",
                                "input[type='text']", "input[type='number']"
                            ]
                            for sel in otp_selectors:
                                try:
                                    el = page.locator(sel).first
                                    if el.is_visible(timeout=2000):
                                        human_typing_with_mistakes(page, sel, otp_code)
                                        break
                                except: continue
                            
                            page.keyboard.press("Enter")
                            page.wait_for_load_state("networkidle")
                            time.sleep(random.uniform(3, 5))
                        else:
                            return False, "Login failed. OTP Verification required but sniper timed out.", []
                    else:
                        return False, "Login failed. OTP required but BOT_EMAIL_PASSWORD is not set in env.", []
                
                # Check if login was successful
                current_url = page.url.lower()
                if "login" in current_url and "verify" not in current_url and "dashboard" not in current_url:
                    return False, "Login failed. Please check your Instahyre password in environment variables.", []
                    
                print("[Instahyre] Login successful! Saving session and navigating to jobs...")
                try:
                    context.storage_state(path=auth_file)
                except Exception as e:
                    print(f"[Instahyre] Could not save session state: {e}")
                
            # End of login block - indent the rest properly if needed.
            # But here the search jobs block just continues in the same scope, which is fine since both paths (needs_login or not) end up here.

            # 2. Search Jobs — try multiple search URL patterns
            search_urls = [
                "https://www.instahyre.com/candidate/opportunities/",
                "https://www.instahyre.com/search-jobs/",
            ]
            
            jobs_page_loaded = False
            for search_url in search_urls:
                try:
                    print(f"[Instahyre] Trying search URL: {search_url}")
                    page.goto(search_url, timeout=60000)
                    page.wait_for_load_state("networkidle")
                    time.sleep(random.uniform(3, 6))
                    
                    # Check if page has job listings
                    body_text = page.locator("body").inner_text(timeout=5000)
                    if len(body_text) > 200 and ("opportunity" in body_text.lower() or "job" in body_text.lower() or "apply" in body_text.lower()):
                        jobs_page_loaded = True
                        print(f"[Instahyre] Job listings found on: {search_url}")
                        break
                except Exception as e:
                    print(f"[Instahyre] Search URL failed: {e}")
                    continue
            
            if not jobs_page_loaded:
                # Take screenshot for debugging
                try:
                    page.screenshot(path="instahyre_debug.png")
                except: pass
                return False, f"Could not load job listings. Current page: {page.url}", []
            
            # 3. Apply Loop — try multiple selectors for job cards
            while applied_count < max_applications:
                # Find all job cards using multiple selector strategies
                job_card_selectors = [
                    ".employer-details",
                    ".opportunity-card",
                    "[class*='opportunity']",
                    "[class*='job-card']",
                    ".card-body",
                    ".job-listing",
                    "div[data-opportunity-id]",
                ]
                
                job_cards = []
                for sel in job_card_selectors:
                    try:
                        cards = page.locator(sel).all()
                        if cards and len(cards) > 0:
                            job_cards = cards
                            print(f"[Instahyre] Found {len(cards)} jobs using selector: {sel}")
                            break
                    except: continue
                
                if not job_cards:
                    # Try getting all clickable elements that look like job entries
                    print("[Instahyre] No job cards found with known selectors. Trying generic approach...")
                    try:
                        # Look for any link or card that contains job-related text
                        all_links = page.locator("a[href*='opportunity'], a[href*='job'], div.card").all()
                        if all_links:
                            job_cards = all_links
                            print(f"[Instahyre] Found {len(all_links)} potential job elements via generic approach.")
                    except: pass
                
                if not job_cards:
                    print("[Instahyre] No more jobs found on this page.")
                    break
                
                total_jobs_found += len(job_cards)
                print(f"[Instahyre] Processing {len(job_cards)} jobs on current page.")
                
                for card in job_cards:
                    if applied_count >= max_applications:
                        break
                        
                    try:
                        human_mouse_wandering(page)
                        
                        # 15% chance to get distracted by another tab
                        human_distraction(context)
                        
                        # Scroll to the card to simulate human reading
                        card.scroll_into_view_if_needed()
                        human_scroll(page)
                        
                        # Extract job title/company before clicking
                        job_title = "Unknown"
                        job_company = "Unknown"
                        try:
                            card_text = card.inner_text(timeout=3000)
                            lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                            if lines:
                                job_title = lines[0][:50]
                                if len(lines) > 1:
                                    job_company = lines[1][:30]
                        except: pass
                        
                        # Randomly highlight text on the screen while reading
                        if random.random() < 0.3:
                            human_text_highlighting(page)
                            
                        # Hover over the specific job card before clicking
                        card.hover()
                        time.sleep(random.uniform(0.8, 1.5))
                        card.click()
                        time.sleep(random.uniform(3, 5))
                        
                        human_mouse_wandering(page)
                        human_scroll(page)
                        
                        # Look for the Apply button in the popup/details view — try multiple selectors
                        apply_selectors = [
                            "button:has-text('Apply')",
                            "button:has-text('Interested')",
                            "button:has-text('I am interested')",
                            "a:has-text('Apply')",
                            ".apply-btn",
                            "[class*='apply']",
                            "button.btn-primary:has-text('Apply')",
                        ]
                        
                        applied = False
                        for apply_sel in apply_selectors:
                            try:
                                apply_btn = page.locator(apply_sel).first
                                if apply_btn.is_visible(timeout=2000):
                                    apply_btn.hover()
                                    time.sleep(random.uniform(1.0, 2.5))
                                    
                                    # Randomly click near the button before clicking the button (simulating hesitation)
                                    try:
                                        box = apply_btn.bounding_box()
                                        if box:
                                            page.mouse.click(box['x'] - 20, box['y'] - 20)
                                            time.sleep(random.uniform(0.5, 1.5))
                                    except: pass
                                    
                                    apply_btn.click()
                                    applied_count += 1
                                    applied_jobs_list.append({
                                        "title": job_title,
                                        "company": job_company,
                                    })
                                    print(f"[Instahyre] ✅ Successfully applied to job #{applied_count}: {job_title}")
                                    applied = True
                                    time.sleep(random.uniform(5, 10)) # Human reading the success message
                                    
                                    # 10% chance to take a long coffee break after an application
                                    coffee_break()
                                    break
                            except: continue
                        
                        if not applied:
                            print(f"[Instahyre] ⏭ Already applied or Apply button missing for: {job_title}. Skipping.")
                            
                        # Close popup or go back if necessary
                        page.keyboard.press("Escape")
                        time.sleep(random.uniform(1, 2))
                        
                    except Exception as e:
                        print(f"[Instahyre] Error clicking job card: {e}")
                        page.keyboard.press("Escape")
                        time.sleep(1)
                
                if applied_count >= max_applications:
                    break
                    
                # Go to next page — try multiple selectors
                next_selectors = [
                    "li.next a",
                    "a:has-text('Next')",
                    ".pagination .next",
                    "button:has-text('Next')",
                    "a[rel='next']",
                ]
                next_found = False
                for next_sel in next_selectors:
                    try:
                        next_btn = page.locator(next_sel).first
                        if next_btn.is_visible(timeout=3000):
                            print("[Instahyre] Moving to next page...")
                            next_btn.click()
                            page.wait_for_load_state("networkidle")
                            time.sleep(random.uniform(3, 6))
                            next_found = True
                            break
                    except: continue
                
                if not next_found:
                    print("[Instahyre] No next page button found. Search complete.")
                    break

            result_msg = f"Successfully applied to {applied_count} out of {total_jobs_found} jobs found on Instahyre!"
            
            # Send results to Telegram
            send_instahyre_results_telegram(applied_jobs_list, total_jobs_found, applied_count > 0)
            
            return applied_count > 0, result_msg, applied_jobs_list
            
        except Exception as e:
            error_msg = f"Engine crashed: {str(e)}"
            # Send error to Telegram
            send_instahyre_results_telegram(applied_jobs_list, total_jobs_found, False)
            return False, error_msg, []
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    run_instahyre_mass_apply(None, None, 'Software Engineer Fresher', 1)
    pass

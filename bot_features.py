import os
import json
import re
import smtplib
from email.message import EmailMessage
import imaplib
from email import message_from_bytes
from email.header import decode_header
from fpdf import FPDF
import time
from playwright.sync_api import sync_playwright

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

def _sanitize_latin1(text):
    if not text:
        return ""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2014": "-", "\u2013": "-", "\u2026": "...", "\u2022": "*",
        "\u00a0": " ", "\u200b": "", "\u200e": "", "\u200f": ""
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")

# Feature 4: Dynamic Cover Letter Generator
class CoverLetterPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 8, _sanitize_latin1(getattr(self, 'name', 'Candidate')).upper(), 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f"{_sanitize_latin1(getattr(self, 'email', ''))} | {_sanitize_latin1(getattr(self, 'phone', ''))}", 0, 1, 'C')
        self.line(10, self.get_y()+2, 200, self.get_y()+2)
        self.ln(10)

def generate_dynamic_cover_letter(job_url, job_description, profile, gemini_client, groq_client=None):
    if not gemini_client and not groq_client:
        return None
    
    prompt = f"""
    You are an expert career coach. Write a highly tailored, 3-paragraph Cover Letter for this exact job description.
    Make it professional, compelling, and exactly match the required skills. No placeholders like [Company Name], infer it from the JD or use "Hiring Manager".
    
    Profile:
    {json.dumps(profile)}
    
    Job Description:
    {job_description[:3000]}
    
    Reply ONLY in this exact JSON format:
    {{
      "company": "Extracted Company Name",
      "hiring_manager": "Hiring Manager",
      "body_paragraphs": ["Paragraph 1", "Paragraph 2", "Paragraph 3"]
    }}
    """
    try:
        if groq_client:
            print("[Groq] Using Groq for Cover Letter Generation...")
            resp = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            text = resp.choices[0].message.content.strip()
        else:
            response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            text = response.text.strip()
            
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n", "", text)
            text = re.sub(r"\n```$", "", text)
        data = json.loads(text)
        
        pdf = CoverLetterPDF()
        pdf.name = _sanitize_latin1(profile.get("full_name", "Candidate"))
        pdf.email = _sanitize_latin1(profile.get("email", "email@example.com"))
        pdf.phone = _sanitize_latin1(profile.get("phone", ""))
        
        pdf.add_page()
        pdf.set_font('Arial', '', 11)
        pdf.set_text_color(0, 0, 0)
        
        from datetime import datetime
        pdf.cell(0, 6, datetime.now().strftime("%B %d, %Y"), 0, 1)
        pdf.ln(5)
        pdf.cell(0, 6, f"To: {_sanitize_latin1(data.get('hiring_manager', 'Hiring Manager'))}", 0, 1)
        pdf.cell(0, 6, _sanitize_latin1(data.get('company', 'Human Resources')), 0, 1)
        pdf.ln(5)
        pdf.cell(0, 6, f"Dear {_sanitize_latin1(data.get('hiring_manager', 'Hiring Manager'))},", 0, 1)
        pdf.ln(3)
        
        for para in data.get("body_paragraphs", []):
            clean_para = _sanitize_latin1(str(para))
            pdf.multi_cell(0, 6, clean_para)
            pdf.ln(4)
            
        pdf.cell(0, 6, "Sincerely,", 0, 1)
        pdf.cell(0, 6, pdf.name, 0, 1)
        
        out_path = "tailored_cover_letter.pdf"
        pdf.output(out_path)
        print("[Resume] Successfully generated ATS Cover Letter!")
        return out_path
    except Exception as e:
        print(f"[Cover Letter] Failed: {e}")
        return None

# Feature 3: Interview Cheat Sheet
def generate_interview_prep(job_url, job_description, gemini_client, groq_client=None):
    if not gemini_client and not groq_client:
        return "AI API unavailable."
    
    prompt = f"""
    Based on this job description, generate the Top 5 most likely technical/behavioral interview questions for this specific role, and a brief 1-sentence tip on how to answer each.
    JD: {job_description[:3000]}
    
    Format as clean Markdown list.
    """
    try:
        if groq_client:
            print("[Groq] Using Groq for Interview Prep...")
            resp = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            return resp.choices[0].message.content.strip()
        else:
            response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            return response.text.strip()
    except Exception as e:
        return f"Could not generate prep: {e}"

# Feature 1: Cold Email
def send_cold_email_if_found(job_description, profile, resume_path, bot_email, bot_password, gemini_client, groq_client=None):
    # Try to extract an email from JD
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', job_description)
    if not emails:
        return False, "No HR email found in JD."
    
    target_email = emails[0]
    
    if not bot_email or not bot_password:
        return False, "Bot email credentials missing."
        
    prompt = f"""
    Write a short, professional cold email to a recruiter submitting a resume for this job.
    JD: {job_description[:2000]}
    Candidate: {profile.get('full_name')}
    
    Reply ONLY in JSON:
    {{
      "subject": "Subject Line",
      "body": "Email Body text"
    }}
    """
    try:
        if groq_client:
            print("[Groq] Using Groq for Cold Email Generation...")
            resp = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            text = resp.choices[0].message.content.strip()
        else:
            response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            text = response.text.strip()
            
        if text.startswith("```"): text = re.sub(r"^```(?:json)?\n", "", text)
        data = json.loads(text.replace("```",""))
        
        msg = EmailMessage()
        msg['Subject'] = data['subject']
        msg['From'] = bot_email
        msg['To'] = target_email
        msg.set_content(data['body'])
        
        if resume_path and os.path.exists(resume_path):
            with open(resume_path, 'rb') as f:
                pdf_data = f.read()
            msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename='Resume.pdf')
            
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(bot_email, bot_password)
            smtp.send_message(msg)
            
        return True, f"Sent cold email to {target_email}"
    except Exception as e:
        return False, f"Failed to send cold email: {e}"

# Feature 2: Interview Alarm
def check_for_interviews(bot_email, bot_password):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(bot_email, bot_password)
        mail.select("inbox")
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        alerts = []
        for e_id in email_ids:
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    sender = msg.get("From")
                    subj_lower = subject.lower()
                    
                    if "interview" in subj_lower or "calendly" in subj_lower or "next steps" in subj_lower:
                        body_html = "<html><body><h3>Email Preview</h3><pre>No content found.</pre></body></html>"
                        
                        # Extract Body
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/html":
                                    body_html = part.get_payload(decode=True).decode()
                                    break
                                elif part.get_content_type() == "text/plain":
                                    body_html = f"<html><body><pre style='font-family: Arial; padding: 20px;'>{part.get_payload(decode=True).decode()}</pre></body></html>"
                        else:
                            content = msg.get_payload(decode=True).decode()
                            if msg.get_content_type() == "text/html":
                                body_html = content
                            else:
                                body_html = f"<html><body><pre style='font-family: Arial; padding: 20px;'>{content}</pre></body></html>"
                        
                        # Save HTML locally
                        html_path = "temp_email.html"
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(body_html)
                            
                        # Take screenshot using Playwright
                        screenshot_path = f"interview_screenshot_{int(time.time())}.png"
                        try:
                            with sync_playwright() as p:
                                browser = p.chromium.launch(headless=True)
                                page = browser.new_page(viewport={"width": 800, "height": 1000})
                                page.goto(f"file://{os.path.abspath(html_path)}")
                                page.screenshot(path=screenshot_path, full_page=True)
                                browser.close()
                        except Exception as e:
                            print(f"[IMAP] Playwright screenshot failed: {e}")
                            screenshot_path = None
                        
                        alerts.append({
                            "text": f"🎉 **INTERVIEW ALERT!**\nFrom: {sender}\nSubject: {subject}",
                            "image": screenshot_path
                        })
                        mail.store(e_id, '+FLAGS', '\\Seen')
        mail.logout()
        return alerts
    except Exception as e:
        print(f"[IMAP] check_for_interviews error: {e}")
        return []

# Feature 6: Auto-OTP / Email Verification Bypass
def wait_for_otp(bot_email, bot_password, timeout_seconds=60):
    """
    Actively listens to the Gmail inbox for a new verification code/OTP.
    Extracts the code (usually 4 to 8 digits) and returns it.
    """
    print(f"[OTP Sniper] Listening to {bot_email} for verification codes...")
    end_time = time.time() + timeout_seconds
    
    while time.time() < end_time:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(bot_email, bot_password)
            mail.select("inbox")
            
            # Search for unread emails from the last few minutes
            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()
            
            if email_ids:
                for e_id in reversed(email_ids):  # Start with newest
                    res, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = message_from_bytes(response_part[1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                            
                            # Extract Body
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode(errors='ignore')
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode(errors='ignore')
                            
                            # Check if it looks like a verification email
                            combined_text = (subject + " " + body).lower()
                            if any(word in combined_text for word in ["verification", "code", "otp", "verify", "security"]):
                                # Use regex to find 4 to 8 digit codes
                                match = re.search(r'\b(\d{4,8})\b', body)
                                if not match:
                                    # Sometimes codes are letters + numbers
                                    match = re.search(r'\b([A-Z0-9]{5,8})\b', body)
                                
                                if match:
                                    otp_code = match.group(1)
                                    print(f"[OTP Sniper] Successfully extracted code: {otp_code}")
                                    # Mark as seen so we don't read it again
                                    mail.store(e_id, '+FLAGS', '\\Seen')
                                    mail.logout()
                                    return otp_code
            
            mail.logout()
        except Exception as e:
            print(f"[OTP Sniper] IMAP Error: {e}")
            
        time.sleep(5)  # Wait 5 seconds before checking again
        
    print("[OTP Sniper] Timeout reached. No code found.")
    return None

# Feature 5: Notion CRM Sync
def sync_to_notion(job_url, job_description, status, gemini_client, override_company=None, override_role=None, groq_client=None, screenshot_url=None):
    notion_key = os.getenv("NOTION_API_KEY", "")
    raw_db_id = os.getenv("NOTION_DATABASE_ID", "")
    import re
    match = re.search(r'([a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12})', raw_db_id)
    database_id = match.group(1).replace("-", "") if match else raw_db_id.replace("-", "")
    
    if not notion_key or not database_id:
        return False, "Notion integration disabled (Missing API Key or Database ID)."
        
    # Use Gemini/Groq to extract Company, Role, Location, Level from the JD
    company = "Unknown Company"
    role = "Software Engineer"
    location = ""
    level = ""
    
    if override_company: company = override_company
    if override_role: role = override_role
    
    if not override_company and (gemini_client or groq_client) and job_description:
        prompt = f"Extract the Company Name, Job Title, Location, and Experience Level from this JD. Reply ONLY in JSON format like this: {{\"company\": \"Name\", \"role\": \"Title\", \"location\": \"City, State\", \"level\": \"Fresher/Entry/Mid/Senior\"}}\n\nJD: {job_description[:1500]}"
        text = ""
        try:
            if gemini_client:
                resp = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                text = resp.text.strip()
            else:
                raise Exception("No Gemini")
        except Exception as e:
            if groq_client:
                try:
                    resp = groq_client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=GROQ_MODEL,
                    )
                    text = resp.choices[0].message.content.strip()
                except Exception as groq_e:
                    print(f"[Notion] Groq extraction failed: {groq_e}")
            else:
                print(f"[Notion] Gemini extraction failed: {e}")
                
        if text:
            try:
                text = text.replace("```json", "").replace("```", "")
                import json
                data = json.loads(text)
                company = data.get("company", company)
                role = data.get("role", role)
                location = data.get("location", "")
                level = data.get("level", "")
            except: pass
            
    if company == "Unknown Company" and job_url:
        try:
            domain = job_url.split("://")[-1].split("/")[0]
            company = domain.replace("www.", "").replace(".com", "").replace(".in", "").replace(".co", "").capitalize()
        except: pass
            
    import requests
    from datetime import datetime
    
    headers = {
        "Authorization": f"Bearer {notion_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    # Build a rich role display with level and location
    role_display = role
    if level: role_display = f"[{level}] {role_display}"
    if location: role_display = f"{role_display} ({location})"
    
    # Determine source from URL
    source = "Direct"
    if job_url:
        url_lower = job_url.lower()
        if "arbeitnow" in url_lower: source = "Arbeitnow"
        elif "remotive" in url_lower: source = "Remotive"
        elif "remoteok" in url_lower: source = "RemoteOK"
        elif "jobicy" in url_lower: source = "Jobicy"
        elif "linkedin" in url_lower: source = "LinkedIn"
        elif "indeed" in url_lower: source = "Indeed"
        elif "adzuna" in url_lower: source = "Adzuna"
        elif "internshala" in url_lower: source = "Internshala"
        elif "unstop" in url_lower: source = "Unstop"
        elif "instahyre" in url_lower: source = "Instahyre"
        elif "foundit" in url_lower: source = "Foundit"
        elif "t.me" in url_lower or "telegram" in url_lower: source = "Telegram Channel"
    
    # Status emoji mapping for visual CRM
    status_emoji = {"Applied": "🟢", "Found (Pending)": "🟡", "Interview": "🎉", "Rejected": "🔴"}.get(status, "⚪")
    
    # Build beautiful blocks for the row page content!
    blocks = []
    
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [
                {"type": "text", "text": {"content": f"{status_emoji} {company} "}, "annotations": {"bold": True}},
                {"type": "text", "text": {"content": f"| {role}"}, "annotations": {"color": "gray"}}
            ]
        }
    })
    
    rich_text_array = []
    rich_text_array.append({"type": "text", "text": {"content": "📊 Status: "}, "annotations": {"bold": True}})
    
    color_map = {"🟢": "green", "🟡": "yellow", "🎉": "purple", "🔴": "red"}
    status_color = color_map.get(status_emoji, "default")
    
    rich_text_array.append({"type": "text", "text": {"content": f"{status}\n"}, "annotations": {"bold": True, "color": status_color}})
    rich_text_array.append({"type": "text", "text": {"content": "📅 Applied: "}, "annotations": {"bold": True}})
    rich_text_array.append({"type": "text", "text": {"content": f"{datetime.now().strftime('%Y-%m-%d')}\n"}})
    
    if location:
        rich_text_array.append({"type": "text", "text": {"content": "📍 Location: "}, "annotations": {"bold": True}})
        rich_text_array.append({"type": "text", "text": {"content": f"{location}\n"}})
        
    if level:
        rich_text_array.append({"type": "text", "text": {"content": "🎓 Level: "}, "annotations": {"bold": True}})
        rich_text_array.append({"type": "text", "text": {"content": f"{level}\n"}})
        
    rich_text_array.append({"type": "text", "text": {"content": "📡 Source: "}, "annotations": {"bold": True}})
    rich_text_array.append({"type": "text", "text": {"content": f"{source}\n\n"}})
    
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"emoji": "💼"},
            "color": "gray_background",
            "rich_text": rich_text_array
        }
    })
    
    if job_url and job_url.startswith("http"):
        # Add a bookmark block for the URL, which renders a nice rich link preview card in Notion!
        blocks.append({
            "object": "block",
            "type": "bookmark",
            "bookmark": {
                "url": job_url
            }
        })
        
    # Divider
    blocks.append({
        "object": "block",
        "type": "divider",
        "divider": {}
    })
    
    # Motivational Quote
    blocks.append({
        "object": "block",
        "type": "quote",
        "quote": {
            "rich_text": [{"type": "text", "text": {"content": "Opportunity favors the prepared mind. You've got this!"}, "annotations": {"italic": True}}],
            "color": "blue_background"
        }
    })
    
    # Interview Checklist Header
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": "🎯 Next Steps"}, "annotations": {"bold": True}}]
        }
    })
    
    # To-Do items
    todos = ["Research the company's recent projects", "Tailor my elevator pitch for this specific role", "Send a follow-up email in 1 week"]
    for todo in todos:
        blocks.append({
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [{"type": "text", "text": {"content": todo}}],
                "checked": False
            }
        })
    if screenshot_url:
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": "📸 Application Screenshot"}, "annotations": {"bold": True}}]
            }
        })
        blocks.append({
            "object": "block",
            "type": "image",
            "image": {
                "type": "external",
                "external": {"url": screenshot_url}
            }
        })
        
    payload = {
        "parent": {"database_id": database_id},
        "icon": {"emoji": status_emoji},
        "cover": {
            "type": "external",
            "external": {"url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?q=80&w=2850&auto=format&fit=crop"} 
        },
        "properties": {
            "Company": {"title": [{"text": {"content": f"{status_emoji} {company}"}}]},
            "Role": {"rich_text": [{"text": {"content": role_display}}]},
            "Status": {"select": {"name": status}},
            "Date Applied": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}
        },
        "children": blocks
    }
    
    # Add URL if it's valid
    if job_url and job_url.startswith("http"):
        payload["properties"]["Link"] = {"url": job_url}
        
    try:
        r = requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return True, f"✅ Added {company} to Notion CRM!"
        else:
            error_data = r.json()
            error_msg = error_data.get("message", r.text)
            
            # FALLBACK: If user provided a Page ID instead of a Database ID, append it as a block!
            if r.status_code == 400 and "is a page, not a database" in error_msg.lower():
                print(f"[Notion] ID is a page. Falling back to appending block to page {database_id}...")
                
                # Beautiful UI Fallback
                blocks = []
                
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [
                            {"type": "text", "text": {"content": f"{status_emoji} {company} "}, "annotations": {"bold": True}},
                            {"type": "text", "text": {"content": f"| {role}"}, "annotations": {"color": "gray"}}
                        ]
                    }
                })
                
                rich_text_array = []
                rich_text_array.append({"type": "text", "text": {"content": "📊 Status: "}, "annotations": {"bold": True}})
                
                color_map = {"🟢": "green", "🟡": "yellow", "🎉": "purple", "🔴": "red"}
                status_color = color_map.get(status_emoji, "default")
                
                rich_text_array.append({"type": "text", "text": {"content": f"{status}\n"}, "annotations": {"bold": True, "color": status_color}})
                rich_text_array.append({"type": "text", "text": {"content": "📅 Applied: "}, "annotations": {"bold": True}})
                rich_text_array.append({"type": "text", "text": {"content": f"{datetime.now().strftime('%Y-%m-%d')}\n"}})
                
                if location:
                    rich_text_array.append({"type": "text", "text": {"content": "📍 Location: "}, "annotations": {"bold": True}})
                    rich_text_array.append({"type": "text", "text": {"content": f"{location}\n"}})
                    
                if level:
                    rich_text_array.append({"type": "text", "text": {"content": "🎓 Level: "}, "annotations": {"bold": True}})
                    rich_text_array.append({"type": "text", "text": {"content": f"{level}\n"}})
                    
                rich_text_array.append({"type": "text", "text": {"content": "📡 Source: "}, "annotations": {"bold": True}})
                rich_text_array.append({"type": "text", "text": {"content": f"{source}\n\n"}})
                
                blocks.append({
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "icon": {"emoji": "💼"},
                        "color": "gray_background",
                        "rich_text": rich_text_array
                    }
                })

                if job_url and job_url.startswith("http"):
                    blocks.append({
                        "object": "block",
                        "type": "bookmark",
                        "bookmark": {"url": job_url}
                    })

                blocks.append({"object": "block", "type": "divider", "divider": {}})

                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {
                        "rich_text": [{"type": "text", "text": {"content": "Opportunity favors the prepared mind. You've got this!"}, "annotations": {"italic": True}}],
                        "color": "blue_background"
                    }
                })

                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": "🎯 Next Steps"}, "annotations": {"bold": True}}]
                    }
                })

                todos = ["Research the company's recent projects", "Tailor my elevator pitch for this specific role", "Send a follow-up email in 1 week"]
                for todo in todos:
                    blocks.append({
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [{"type": "text", "text": {"content": todo}}],
                            "checked": False
                        }
                    })
                
                # Double Divider to visually separate it from the next application
                blocks.append({"object": "block", "type": "divider", "divider": {}})
                
                block_payload = {"children": blocks}
                
                # Use the Blocks API to append children to the page
                patch_r = requests.patch(f"https://api.notion.com/v1/blocks/{database_id}/children", headers=headers, json=block_payload, timeout=15)
                
                if patch_r.status_code == 200:
                    return True, f"✅ Appended {company} to your Notion Page!"
                else:
                    return False, f"Notion API Error (Block Fallback): {patch_r.text}"
            
            return False, f"Notion API Error: {error_msg}"
    except Exception as e:
        return False, f"Failed to reach Notion API: {e}"


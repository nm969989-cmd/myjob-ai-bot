import imaplib
import email
from email.header import decode_header
import re
import time

def get_latest_otp(bot_email, bot_password, search_term, timeout=60):
    """
    Connects to Gmail, waits for a new email containing the search_term (e.g. 'workday' or 'netflix'),
    extracts a 6-digit OTP code or a verification link. It will leave the email in your inbox.
    """
    print(f"[IMAP] Waiting up to {timeout} seconds for an email related to '{search_term}'...")
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        mail = None
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(bot_email, bot_password)
            mail.select("inbox")
            
            # Search for ONLY UNSEEN emails since we are keeping them in the inbox now
            status, messages = mail.search(None, "UNSEEN")
            email_ids = messages[0].split()
            
            if email_ids:
                # Check from newest to oldest
                for e_id in reversed(email_ids):
                    res, msg_data = mail.fetch(e_id, "(RFC822)")
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            
                            # Decode subject
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                            
                            sender = msg.get("From")
                            
                            # If this email is from the company we are waiting for
                            if search_term.lower() in subject.lower() or search_term.lower() in sender.lower():
                                print(f"[IMAP] Found email: {subject} from {sender}")
                                
                                # Extract Body
                                body = ""
                                if msg.is_multipart():
                                    for part in msg.walk():
                                        content_type = part.get_content_type()
                                        if content_type == "text/plain" or content_type == "text/html":
                                            try:
                                                payload = part.get_payload(decode=True)
                                                if payload:
                                                    body = payload.decode(errors="ignore")
                                            except Exception:
                                                pass
                                else:
                                    payload = msg.get_payload(decode=True)
                                    if payload:
                                        body = payload.decode(errors="ignore")
                                
                                # Clean HTML tags if present to make regex more accurate
                                # We can do a simple replace or just rely on regex, but removing tags helps.
                                clean_body = re.sub(r'<[^>]+>', ' ', body)
                                
                                # 1. Look for a 4 to 8 digit OTP code (some companies use 4, 6, or 8 digits)
                                otp_match = re.search(r'\b\d{4,8}\b', clean_body)
                                if otp_match:
                                    code = otp_match.group(0)
                                    print(f"[IMAP] Extracted OTP Code: {code}")
                                    
                                    # Mark as read instead of deleting (optional, but safe)
                                    mail.store(e_id, '+FLAGS', '\\Seen')
                                    mail.logout()
                                    return {"type": "code", "value": code}
                                    
                                # 2. Look for a verification link
                                link_match = re.search(r'href=[\'"]?([^\'" >]+)', body)
                                if link_match:
                                    link = link_match.group(1)
                                    if "verify" in link.lower() or "confirm" in link.lower():
                                        print(f"[IMAP] Extracted Verification Link: {link}")
                                        mail.store(e_id, '+FLAGS', '\\Seen')
                                        mail.logout()
                                        return {"type": "link", "value": link}
                                
                                print("[IMAP] Found email but no OTP or Link inside.")
            
            mail.logout()
        except Exception as e:
            print(f"[IMAP] Error reading email: {e}")
            # Ensure the IMAP socket is always released, even on the error path.
            if mail is not None:
                try:
                    mail.logout()
                except Exception:
                    pass
            
        # Wait 5 seconds before checking again
        time.sleep(5)
        
    print("[IMAP] Timeout reached. No email arrived.")
    return None

def scan_for_interview_invites():
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    bot_email = os.getenv("BOT_EMAIL")
    # Match the env var name used everywhere else (main.py, GitHub Actions secret).
    # Fall back to BOT_PASSWORD for backwards compatibility.
    bot_password = os.getenv("BOT_EMAIL_PASSWORD") or os.getenv("BOT_PASSWORD")
    if not bot_email or not bot_password:
        raise Exception("BOT_EMAIL or BOT_EMAIL_PASSWORD not set in .env")
        
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(bot_email, bot_password)
    mail.select("inbox")
    
    results = []
    try:
        # Search for UNSEEN emails
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        if not email_ids:
            return results
            
        for e_id in reversed(email_ids): # Process newest first
            res, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                    
                    sender = msg.get("From", "")
                    subj_lower = subject.lower()
                    
                    # We are looking for interviews OR rejections
                    is_interview = any(k in subj_lower for k in ["interview", "next steps", "assessment", "calendly", "invitation"])
                    is_rejection = any(k in subj_lower for k in ["update on your application", "unfortunately", "not moving forward", "status of your application"])
                    
                    if is_interview or is_rejection:
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    try:
                                        payload = part.get_payload(decode=True)
                                        if payload:
                                            body = payload.decode(errors="ignore")
                                    except Exception:
                                        pass
                                    break
                        else:
                            try:
                                payload = msg.get_payload(decode=True)
                                if payload:
                                    body = payload.decode(errors="ignore")
                            except Exception:
                                pass
                        
                        if not body: continue
                        
                        # Determine status
                        if is_interview: new_status = "Interview"
                        elif "unfortunately" in body.lower() or "not moving forward" in body.lower(): new_status = "Rejected"
                        else: continue # False positive
                        
                        # Extract company name using Gemini
                        from main import get_gemini_client
                        client = get_gemini_client()
                        company_name = sender.split("@")[-1].split(".")[0].title() # fallback
                        if client:
                            try:
                                prompt = f"Extract the company name from this email. Reply ONLY with the company name, nothing else. Email From: {sender}\nSubject: {subject}\nBody: {body[:1000]}"
                                resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                                company_name = resp.text.strip()
                            except Exception: pass
                            
                        results.append({"company": company_name, "status": new_status, "subject": subject})
                        
                        # Update Notion CRM
                        from bot_features import sync_to_notion
                        sync_to_notion("", f"Update from email: {subject}", new_status, client, override_company=company_name)
                        
                        mail.store(e_id, '+FLAGS', '\\Seen')
                        
            # Limit to 20 emails per scan
            if len(results) >= 20: break
    finally:
        try:
            mail.logout()
        except Exception:
            pass
    return results

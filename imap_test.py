import os
import imaplib
import email
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

BOT_EMAIL = os.getenv("BOT_EMAIL")
BOT_EMAIL_PASSWORD = os.getenv("BOT_EMAIL_PASSWORD")

def test_email_connection():
    if not BOT_EMAIL or not BOT_EMAIL_PASSWORD:
        print("❌ ERROR: BOT_EMAIL or BOT_EMAIL_PASSWORD is missing in your .env file!")
        return

    print(f"🔄 Attempting to log into {BOT_EMAIL}...")
    
    try:
        # Connect to Gmail's IMAP server
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        
        # Login
        mail.login(BOT_EMAIL, BOT_EMAIL_PASSWORD)
        
        print("✅ SUCCESS! The bot successfully logged into the email inbox.")
        
        # Select the inbox and check how many emails there are
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")
        email_count = len(messages[0].split())
        print(f"📬 There are {email_count} emails in the inbox.")
        
        # Logout
        mail.logout()
        
    except imaplib.IMAP4.error as e:
        print("❌ LOGIN FAILED. Please check if your App Password is correct.")
        print(f"Error Details: {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    test_email_connection()

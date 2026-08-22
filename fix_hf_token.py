import re

# Fix main.py
try:
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_token = 'TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")'
    new_token = 'TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4")'
    
    content = content.replace(old_token, new_token)
    
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
except Exception as e: print("main:", e)

# Fix job_radar.py
try:
    with open('job_radar.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_radar_token = 'bot_token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")'
    new_radar_token = 'bot_token = os.getenv("TELEGRAM_TOKEN", "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4")'
    
    content = content.replace(old_radar_token, new_radar_token)
    
    with open('job_radar.py', 'w', encoding='utf-8') as f:
        f.write(content)
except Exception as e: print("radar:", e)

print("Tokens hardcoded for HF")

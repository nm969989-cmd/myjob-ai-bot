import re

# Fix main.py
try:
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_chat = 'data = safe_load_json(CHAT_ID_FILE, {})\\n    return data.get("chat_id")'
    new_chat = 'data = safe_load_json(CHAT_ID_FILE, {})\\n    return data.get("chat_id", "7607565831")'
    
    content = content.replace(old_chat, new_chat)
    
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
except Exception as e: print("main:", e)

# Fix job_radar.py
try:
    with open('job_radar.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    old_radar_chat = 'chat_id = os.getenv("TELEGRAM_CHAT_ID")'
    new_radar_chat = 'chat_id = os.getenv("TELEGRAM_CHAT_ID", "7607565831")'
    
    content = content.replace(old_radar_chat, new_radar_chat)
    
    with open('job_radar.py', 'w', encoding='utf-8') as f:
        f.write(content)
except Exception as e: print("radar:", e)

print("Chat ID hardcoded for HF")

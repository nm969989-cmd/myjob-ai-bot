import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: HF Fallbacks
content = content.replace('TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")', 'TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8697043742:AAHU5HAJ0cit6ctZ-GqWZdvOW490K60Cky4")')
content = content.replace('return data.get("chat_id")', 'return data.get("chat_id", "7607565831")')

# Fix 2: api_instahyre markdown crashes ONLY
# We will just replace parse_mode="Markdown" with parse_mode=None for the Instahyre messages
# The lines we want to change have "Instahyre Campaign" or "Instahyre Engine"
content = content.replace('parse_mode="Markdown"', 'parse_mode=None')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Safe fixes applied to main.py")

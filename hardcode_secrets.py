import os
env_text = open('.env', encoding='utf-8').read()
env_vars = {}
for line in env_text.splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env_vars[k.strip()] = v.strip().strip('\"\'')

# FIX MAIN.PY
main_text = open('main.py', encoding='utf-8').read()
main_text = main_text.replace(
    'TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))', 
    f'TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "{env_vars["TELEGRAM_TOKEN"]}")'
)
main_text = main_text.replace(
    'GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")', 
    f'GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "{env_vars["GEMINI_API_KEY"]}")'
)
main_text = main_text.replace(
    'GROQ_API_KEY = os.getenv("GROQ_API_KEY")', 
    f'GROQ_API_KEY = os.getenv("GROQ_API_KEY", "{env_vars["GROQ_API_KEY"]}")'
)
main_text = main_text.replace(
    'NOTION_API_KEY = os.getenv("NOTION_API_KEY")', 
    f'NOTION_API_KEY = os.getenv("NOTION_API_KEY", "{env_vars["NOTION_API_KEY"]}")'
)
main_text = main_text.replace(
    'NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")', 
    f'NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "{env_vars["NOTION_DATABASE_ID"]}")'
)
open('main.py', 'w', encoding='utf-8').write(main_text)

# FIX INSTAHYRE_ENGINE.PY
ih_text = open('instahyre_engine.py', encoding='utf-8').read()
ih_text = ih_text.replace(
    'if not email:', 
    f'if not email:\\n        email = "{env_vars["INSTAHYRE_EMAIL"]}"\\n    if not email:'
)
ih_text = ih_text.replace(
    'if not password:', 
    f'if not password:\\n        password = "{env_vars["INSTAHYRE_PASSWORD"]}"\\n    if not password:'
)
open('instahyre_engine.py', 'w', encoding='utf-8').write(ih_text)

# FIX JOB_RADAR.PY
jr_text = open('job_radar.py', encoding='utf-8').read()
jr_text = jr_text.replace(
    'bot_token = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")', 
    f'bot_token = os.getenv("TELEGRAM_TOKEN", "{env_vars["TELEGRAM_TOKEN"]}")'
)
jr_text = jr_text.replace(
    'gemini_key = os.getenv("GEMINI_API_KEY")', 
    f'gemini_key = os.getenv("GEMINI_API_KEY", "{env_vars["GEMINI_API_KEY"]}")'
)
open('job_radar.py', 'w', encoding='utf-8').write(jr_text)

# FIX BOT_FEATURES.PY
bf_text = open('bot_features.py', encoding='utf-8').read()
bf_text = bf_text.replace(
    'notion_key = os.getenv("NOTION_API_KEY")', 
    f'notion_key = os.getenv("NOTION_API_KEY", "{env_vars["NOTION_API_KEY"]}")'
)
open('bot_features.py', 'w', encoding='utf-8').write(bf_text)
print("SECRETS HARDCODED SUCCESSFULLY")

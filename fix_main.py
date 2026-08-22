import re

try:
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    old_pattern = re.compile(r'if bot and chat_id:\n\s+try: bot\.send_message\(chat_id.*?except: pass', re.DOTALL)
    new_code = '''if bot and chat_id:
        try: bot.send_message(chat_id, \"🚀 Instahyre Campaign Launched!\\n\\nThe stealth engine has started in the background. It will automatically apply to 20 Fresher Software Engineer roles. Please wait 5-10 minutes for the final report.\")
        except Exception as e: print(f\"[Telegram Error] {e}\")'''

    content = old_pattern.sub(new_code, content)

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Successfully patched main.py")
except Exception as e:
    print("Error:", e)

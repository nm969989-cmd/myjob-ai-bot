import re

try:
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()

    old1 = 'bot.send_message(chat_id, f"{status_icon} *Instahyre Campaign Finished*\\n\\n{msg}", parse_mode="Markdown")'
    new1 = 'try: bot.send_message(chat_id, f"{status_icon} Instahyre Campaign Finished\\n\\n{msg}")\n                except Exception as e: print("Telegram Error:", e)'
    content = content.replace(old1, new1)

    old2 = 'bot.send_message(chat_id, f"❌ *Instahyre Engine Crashed*\\n\\n{err_str}", parse_mode="Markdown")'
    new2 = 'try: bot.send_message(chat_id, f"❌ Instahyre Engine Crashed\\n\\n{err_str}")\n                except Exception as e: print("Telegram Error:", e)'
    content = content.replace(old2, new2)

    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Successfully removed markdown parse_mode from final reports")
except Exception as e:
    print("Error:", e)

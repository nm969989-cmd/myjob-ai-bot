import sys

def fix_main_py():
    path = r"d:\insta gravity\Telegram_Job_Bot\main.py"
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    out = []
    in_unindent_block = False
    
    for i, line in enumerate(lines):
        if "@bot.message_handler(commands=['dashboard', 'menu'])" in line:
            out.append("if bot:\n")
            
        if "def daily_report_loop():" in line:
            in_unindent_block = True
            
        if "def radar_loop():" in line:
            in_unindent_block = False
            
        if in_unindent_block:
            if line.startswith("    "):
                out.append(line[4:])
            else:
                out.append(line)
        else:
            out.append(line)
            
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.writelines(out)
        
    print("Fixed main.py indentation.")

if __name__ == "__main__":
    fix_main_py()

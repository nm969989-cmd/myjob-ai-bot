import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('dYs? *Instahyre Campaign Launched!*', '🚀 Instahyre Campaign Launched!')
content = content.replace('*Instahyre Campaign Finished*', '✅ Instahyre Campaign Finished')
content = content.replace('? *Instahyre Engine Crashed*', '❌ Instahyre Engine Crashed')
content = content.replace('? *Instahyre Campaign Finished*', '✅ Instahyre Campaign Finished')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed emojis in main.py")

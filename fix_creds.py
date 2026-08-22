import re

try:
    with open('instahyre_engine.py', 'r', encoding='utf-8') as f:
        content = f.read()

    old_cred = '''    if not email:
        email = os.getenv("INSTAHYRE_EMAIL", "gokuuchihatamil@gmail.com")
    if not password:
        password = os.getenv("INSTAHYRE_PASSWORD", "")'''

    new_cred = '''    if not email:
        email = "manojprofessional007@gmail.com"
    if not password:
        password = "oxgrxcwblaansfsw"'''

    content = content.replace(old_cred, new_cred)

    with open('instahyre_engine.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Successfully hardcoded credentials in instahyre_engine.py")
except Exception as e:
    print("Error:", e)

import re

try:
    with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove the two input lines
    content = re.sub(r'<input type="email" id="instaEmail".*?>\n', '', content)
    content = re.sub(r'<input type="password" id="instaPassword".*?>\n', '', content)
    content = re.sub(r'\s*<input type="email" id="instaEmail".*?>', '', content)
    content = re.sub(r'\s*<input type="password" id="instaPassword".*?>', '', content)

    # Remove JS lines
    content = re.sub(r'\s*const email = document\.getElementById\(''instaEmail''\)\.value;', '', content)
    content = re.sub(r'\s*const password = document\.getElementById\(''instaPassword''\)\.value;', '', content)
    
    # Update the fetch body to not send email and password
    content = content.replace('body: JSON.stringify({ email: email, password: password })', 'body: JSON.stringify({})')

    with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("Successfully removed input fields from dashboard.html")
except Exception as e:
    print("Error:", e)

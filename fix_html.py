import sys, re
try:
    with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
        content = f.read()

    old_html = '<div class="flex flex-col gap-2">\n            <button onclick="triggerInstahyre()"'
    new_html = '<div class="flex flex-col gap-2">\n            <input type="email" id="instaEmail" placeholder="Instahyre Email" class="w-full bg-black/50 border border-white/10 rounded px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-fuchsia-500/50">\n            <input type="password" id="instaPassword" placeholder="Instahyre Password" class="w-full bg-black/50 border border-white/10 rounded px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-fuchsia-500/50 mb-1">\n            <button onclick="triggerInstahyre()"'
    content = content.replace(old_html, new_html)

    old_js = re.compile(r'async function triggerInstahyre\(\) \{.*?method: \'POST\'\n\s*\}\);', re.DOTALL)
    new_js = '''async function triggerInstahyre() {
    const email = document.getElementById('instaEmail').value;
    const password = document.getElementById('instaPassword').value;
    const statusEl = document.getElementById('instaStatus');
    
    if(!email || !password) {
        statusEl.textContent = '❌ Please enter Email and Password first!';
        statusEl.style.color = '#ef4444';
        return;
    }
    
    statusEl.textContent = '🚀 Launching Instahyre Engine in background...';
    statusEl.style.color = '#9ca3af';
    try {
      const res = await fetch('api/instahyre', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email: email, password: password })
      });'''
    content = old_js.sub(new_js, content)

    with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully updated dashboard.html')
except Exception as e:
    print('Error:', e)

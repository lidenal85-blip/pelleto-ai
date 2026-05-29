import re

files = [
    'templates/base.html',
    'templates/landing/index.html',
    'templates/admin/base.html',
    'templates/admin/login.html',
    'templates/admin/products.html',
    'templates/admin/kb.html',
    'templates/admin/generate.html',
    'templates/admin/queue.html',
    'templates/admin/dialogues.html',
    'templates/admin/dashboard.html',
    'templates/admin/login.html',
    'static/js/agent.js',
]

RP = '{{ root_path }}'

for path in files:
    try:
        with open(path) as f:
            src = f.read()
    except FileNotFoundError:
        continue
    new = src
    # CSS/JS static refs in HTML
    new = re.sub(r'(href|src)="/static/', f'\\1="{RP}/static/', new)
    # /order links
    new = re.sub(r'href="/order"', f'href="{RP}/order"', new)
    new = re.sub(r"href='/order'", f"href='{RP}/order'", new)
    # admin action forms
    new = re.sub(r'action="/admin/', f'action="{RP}/admin/', new)
    # admin nav hrefs
    new = re.sub(r'href="/admin/', f'href="{RP}/admin/', new)
    # redirect after logout
    new = re.sub(r'href="/">', f'href="{RP}/">', new)
    # JS fetch
    new = new.replace("/api/agent/chat", f"{RP}/api/agent/chat")
    new = new.replace("/api/order", f"{RP}/api/order")
    if new != src:
        with open(path, 'w') as f:
            f.write(new)
        print(f'Updated: {path}')
    else:
        print(f'No change: {path}')

print('Done')
#!/usr/bin/env python3
"""
Converts log.*("msg", key=val, ...) -> log.*(f"msg | key=val ...")
for all .py files under app/
"""
import re, os, sys

LOG_RE = re.compile(
    r'(log\.(?:info|warning|error|debug|critical))\(([^)]+)\)',
    re.DOTALL
)

def fix_line(m):
    method = m.group(1)
    args_raw = m.group(2)
    # Split carefully: first arg is the message string, rest are kwargs
    # We do a simple split on ", " that's NOT inside quotes
    args_raw = args_raw.strip()
    # Find all kwargs: word= patterns after the first string
    # Check if there are any kwargs at all
    kw_match = re.search(r',\s*(\w+=)', args_raw)
    if not kw_match:
        return m.group(0)  # no kwargs, leave as-is
    
    # Extract message (first arg)
    msg_match = re.match(r'(f?["\'].*?["\'])', args_raw)
    if not msg_match:
        return m.group(0)
    msg = msg_match.group(1)
    rest = args_raw[msg_match.end():].strip().lstrip(',')
    
    # Parse kwargs
    kwargs = []
    for kv in re.findall(r'(\w+)=([^,)]+)', rest):
        kwargs.append(f"{kv[0]}={{{kv[1].strip()}}}")
    
    if not kwargs:
        return m.group(0)
    
    # Build new call
    # Strip outer quotes from msg to embed in f-string
    if msg.startswith('f"') or msg.startswith("f'"):
        inner = msg[2:-1]
    elif msg.startswith('"') or msg.startswith("'"):
        inner = msg[1:-1]
    else:
        return m.group(0)
    
    extra = ' | ' + ' '.join(kwargs)
    new_msg = f'f"{inner}{extra}"'
    return f'{method}({new_msg})'


def fix_file(path):
    with open(path, encoding='utf-8') as f:
        src = f.read()
    new_src = LOG_RE.sub(fix_line, src)
    if new_src != src:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_src)
        print(f'Fixed: {path}')


root = '/opt/pelleto-ai/app'
for dirpath, _, files in os.walk(root):
    for fn in files:
        if fn.endswith('.py'):
            fix_file(os.path.join(dirpath, fn))
print('Done.')
with open('templates/base.html') as f:
    src = f.read()
new = src.replace('<body>', '<body data-root-path="{{ root_path }}">',  1)
with open('templates/base.html', 'w') as f:
    f.write(new)
print('Done:', '<body data-root-path' in new)
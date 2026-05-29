path = 'static/js/agent.js'
with open(path) as f:
    src = f.read()

new = src.replace(
    "var ORDER_URL   = '/order';",
    "var ROOT_PATH   = (document.body.dataset.rootPath || '');\n  var ORDER_URL   = ROOT_PATH + '/order';"
).replace(
    "fetch('/api/agent/chat'",
    "fetch(ROOT_PATH + '/api/agent/chat'"
)

with open(path, 'w') as f:
    f.write(new)
print('Done')
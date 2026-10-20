"""Render a track-changes snapshot as one self-contained offline HTML page. The page has no network access (a
CSP forbids it), builds its DOM with textContent only, and its buttons only copy text; nothing it shows can run
a command. The snapshot is embedded as JSON with `<`, `>`, `&` and the line separators escaped, so no value in it
(a path, a plan cell, a diff line) can close the script tag or inject markup."""

import json
import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")  # run from stdin, track_changes.py sets it

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'">
<title>Track changes</title>
<style>__CSS__</style></head>
<body><div id="app"></div>
<script type="application/json" id="data">__DATA__</script>
<script>__JS__</script></body></html>
"""


def embed(value):
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    for raw, safe in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        text = text.replace(raw, safe)
    return text


def render(data, brief=""):
    with open(os.path.join(ASSETS, "viewer.css"), encoding="utf-8") as handle:
        css = handle.read()
    with open(os.path.join(ASSETS, "viewer.js"), encoding="utf-8") as handle:
        js = handle.read()
    with open(os.path.join(ASSETS, "journal.js"), encoding="utf-8") as handle:
        js = js.replace("__JOURNAL__", handle.read())
    # the data goes in last: nothing inside it can be mistaken for a marker
    return PAGE.replace("__CSS__", css).replace("__JS__", js).replace("__DATA__", embed(dict(data, brief_md=brief)))

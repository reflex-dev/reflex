"""reverify_hydration: is a lost pre-hydration click on /clickfast explained by React not having attached
its handlers yet (prerendered prod HTML)? Records __reactProps presence at click time and whether the
cf_click(always) event was sent on the websocket. Usage: s10_react_check.py BASE N"""
import json
import sys

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, n = sys.argv[1].rstrip("/"), int(sys.argv[2])
rows = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for i in range(n):
        ctx = b.new_context()
        p = ctx.new_page()
        sent = []
        p.on("websocket", lambda ws: ws.on("framesent", lambda d: sent.append(str(d))))
        p.goto(base + "/clickfast", wait_until="commit")
        p.wait_for_selector("#cf-always", timeout=15000)
        react = p.evaluate("() => { const el = document.querySelector('#cf-always'); return !!el && Object.keys(el).some(k => k.startsWith('__reactProps')); }")
        p.click("#cf-always", timeout=5000)
        p.wait_for_timeout(2500)
        log = p.locator("#cf-log").inner_text()
        always_sent = any('"which":"always"' in s for s in sent)
        rows.append({"react_attached_at_click": react, "always_sent": always_sent, "logged": "click-always" in log})
        ctx.close()
    b.close()
print(json.dumps(rows))
from collections import Counter
print(Counter((r["react_attached_at_click"], r["always_sent"], r["logged"]) for r in rows))

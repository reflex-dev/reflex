"""F6 without artificial holds: behind a latency proxy, click a client-side link as soon as React has hydrated it.
Usage: prenav_natural.py <proxied_base> <label> <runs> <out_json>"""
import json
import sys

from playwright.sync_api import sync_playwright

base, label, runs, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
res = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for i in range(runs):
        ctx = b.new_context()
        p = ctx.new_page()
        sent = []
        p.on("websocket", lambda ws: "_event" in ws.url and ws.on("framesent", lambda f: isinstance(f, str) and f.startswith("4") and sent.append(f[:60])))
        p.goto(base + "/items/1", wait_until="commit")
        p.wait_for_function("(() => { const a = document.getElementById('nav-item2'); return !!a && Object.keys(a).some(k => k.startsWith('__reactProps')); })()", timeout=15000, polling=5)
        connected_before_click = any(s.startswith("40") for s in sent)
        p.click("#nav-item2")
        p.wait_for_function("document.getElementById('hyd-flag') && document.getElementById('hyd-flag').textContent === 'H:yes' && location.pathname === '/items/2'", timeout=15000)
        p.wait_for_timeout(1500)
        tr = json.loads(p.inner_text("#item-trace"))
        res.append({"connect_sent_before_click": connected_before_click, "item_trace": tr})
        print(label, i, "CONNECT sent before click:", connected_before_click, "item_trace:", tr, flush=True)
        ctx.close()
    b.close()
json.dump(res, open(out, "w"), indent=1)

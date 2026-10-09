"""Interleaved A/B first-load timing: alternate fresh-context loads between two running prod servers.

Usage: ab_timing.py <urlA> <labelA> <urlB> <labelB> <n> <path> <out_json>
"""
import json
import statistics
import sys
import time

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
ua, la, ub, lb, n, path, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6], sys.argv[7]

JS = """
(() => { window.__t = {};
  const mark = () => { const el = document.getElementById('hyd-flag');
    if (el && el.textContent === 'H:yes' && !window.__t.yes) window.__t.yes = performance.now(); };
  const start = () => { mark(); new MutationObserver(mark).observe(document.documentElement, {subtree:true, childList:true, characterData:true}); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start(); })();
"""


def one(browser, url):
    ctx = browser.new_context()
    ctx.add_init_script(JS)
    p = ctx.new_page()
    frames = []
    p.on("websocket", lambda ws: "_event" in ws.url and (
        ws.on("framesent", lambda f: frames.append(("out", time.time() * 1000, f if isinstance(f, str) else ""))),
        ws.on("framereceived", lambda f: frames.append(("in", time.time() * 1000, f if isinstance(f, str) else "")))))
    p.goto(url + path)
    p.wait_for_function("window.__t && window.__t.yes", timeout=20000)
    p.wait_for_timeout(200)
    origin = p.evaluate("performance.timeOrigin")
    nav = p.evaluate("performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd")
    yes = p.evaluate("window.__t.yes")
    first_out = next((t for d, t, f in frames if d == "out" and f.startswith("4")), None)
    first_delta = next((t for d, t, f in frames if d == "in" and f.startswith("42") and '"delta"' in f), None)
    ctx.close()
    return {"dcl": round(nav), "connect_sent": round(first_out - origin) if first_out else None,
            "first_delta": round(first_delta - origin) if first_delta else None, "hydrated": round(yes),
            "connect_to_hydrated": round(yes - (first_out - origin)) if first_out else None}


res = {la: [], lb: []}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    for u, l in ((ua, la), (ub, lb)):  # warmup
        one(b, u)
    for i in range(n):
        order = [(ua, la), (ub, lb)] if i % 2 == 0 else [(ub, lb), (ua, la)]
        for u, l in order:
            res[l].append(one(b, u))
    b.close()
summary = {}
for l, runs in res.items():
    summary[l] = {k: statistics.median([r[k] for r in runs if r[k] is not None]) for k in runs[0]}
    summary[l]["n"] = len(runs)
json.dump({"path": path, "summary": summary, "runs": res}, open(out, "w"), indent=1)
print(json.dumps(summary, indent=1))

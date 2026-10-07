"""Drive the bootdup app: count computed-var evaluations and boot deltas per page load.

Usage: drive_bootdup.py BASE OUT_JSON SERVER_LOG
Phases: (1) fresh profile, first load (nothing in localStorage) - does `bd_tok` get written? (2) localStorage
bd_tok="hello", 3 reloads: per load, BOOTDUP eval lines added to the server log and every received delta.
"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

base, out, log = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
res = {"loads": [], "console": [], "page_errors": []}


def log_lines():
    return [l for l in open(log, errors="replace").read().splitlines() if l.startswith("BOOTDUP")]


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    frames = []
    page.on("console", lambda m: m.type in ("error", "warning") and res["console"].append(f"{m.type}: {m.text[:200]}"))
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)[:200]))
    page.on("websocket", lambda ws: ws.on("framereceived", lambda pl: frames.append((time.time(), str(pl)))))

    def load(what, reload=True):
        n0, f0, t0 = len(log_lines()), len(frames), time.time()
        if reload:
            page.reload(wait_until="networkidle")
        else:
            page.goto(base + "/", wait_until="networkidle")
        page.wait_for_function("() => (document.querySelector('#token')?.textContent || '').length > 10", timeout=60000)
        page.wait_for_timeout(3000)
        deltas = [f[1] for f in frames[f0:] if '"delta"' in f[1]]
        res["loads"].append({
            "what": what,
            "evals": [re.sub(r"^BOOTDUP [\d.]+ ", "", l) for l in log_lines()[n0:]],
            "n_deltas": len(deltas),
            "deltas": [re.sub(r'"rx_router_headers_rx_state_":\{.*?\}\}?,', '"rx_router_headers":"...",', d)[:1500] for d in deltas],
            "ui": {i: page.locator(f"#{i}").inner_text() for i in ("tok", "derived", "lookup", "sub")},
            "localStorage": page.evaluate("() => Object.fromEntries(Object.entries(localStorage))"),
        })

    load("fresh profile, first load", reload=False)
    page.evaluate("() => localStorage.setItem('bd_tok', 'hello')")
    for i in range(3):
        load(f"reload #{i + 1} with bd_tok=hello")
    b.close()
json.dump(res, open(out, "w"), indent=1)
for l in res["loads"]:
    print("==", l["what"], "| n_deltas", l["n_deltas"], "| ui", l["ui"], "| ls", {k: v for k, v in l["localStorage"].items() if k == "bd_tok"})
    for e in l["evals"]:
        print("   eval", e)
    for d in l["deltas"]:
        print("   delta", d[:700])
print("console", res["console"], "page_errors", res["page_errors"])

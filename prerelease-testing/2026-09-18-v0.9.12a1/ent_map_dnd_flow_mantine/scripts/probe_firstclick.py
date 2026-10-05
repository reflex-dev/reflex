"""Is the first Highcharts point-click lost in the browser or in the backend?

Captures both websocket directions around each click, so a click that never
produces a sent frame is a client-side drop, not a lost event.
"""
import sys, json, time
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
HOVER_FIRST = "--hover" in sys.argv
sent, recv = [], []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context(viewport={"width": 1400, "height": 1000}).new_page()
    page.on("websocket", lambda ws: (
        ws.on("framesent", lambda pl: sent.append((round(time.time() % 1000, 2), str(pl)[:260]))),
        ws.on("framereceived", lambda pl: recv.append((round(time.time() % 1000, 2), str(pl)[:260]))),
    ))
    page.goto(BASE, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(5000)
    marker = page.locator(".highcharts-series-1 .highcharts-point").nth(2)
    for attempt in (1, 2, 3):
        print(f"--- attempt {attempt} (hover_first={HOVER_FIRST})", flush=True)
        n_sent = len(sent)
        if HOVER_FIRST:
            marker.hover()
            page.wait_for_timeout(500)
        marker.click()
        page.wait_for_timeout(2500)
        print("   text:", [t for t in page.inner_text("body").split("\n") if "Click" in t], flush=True)
        print("   new sent frames:", json.dumps(sent[n_sent:])[:700], flush=True)
    br.close()
print("TOTAL sent", len(sent), "recv", len(recv))

"""Drive momentapp in Chromium and record every frame SENT on the /_event socket with a wall clock.

Usage: drive_moment.py <url> <shot_prefix> <report_json> [wait_seconds=10]
Flow: goto / -> wait W s -> reload -> wait W s -> client-side nav to /other -> back to / -> wait W s.
"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

url, shot, report = sys.argv[1], sys.argv[2], sys.argv[3]
W = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0

frames = []          # (wall_clock, ws_tag, name, payload)
console = []
page_errors = []
ws_events = []
phases = []


def mark(name):
    phases.append((time.strftime("%H:%M:%S"), name))
    print(f"--- {phases[-1][0]} {name}", flush=True)


def on_ws(ws):
    ws_events.append(("open", time.strftime("%H:%M:%S"), ws.url))
    if "_event" not in ws.url:
        return
    tag = f"ws#{len([e for e in ws_events if e[0] == 'open' and '_event' in e[2]])}"
    ws.on("close", lambda w: ws_events.append(("close", time.strftime("%H:%M:%S"), w.url)))

    def sent(payload):
        if not isinstance(payload, str) or "[" not in payload:
            return
        try:
            body = json.loads(payload[payload.index("["):])
        except Exception:
            return
        if isinstance(body, list) and len(body) > 1 and isinstance(body[1], dict):
            name = body[1].get("name", "")
            frames.append((time.strftime("%H:%M:%S.") + f"{int(time.time()*1000)%1000:03d}", tag, name.rsplit(".", 1)[-1], body[1].get("payload")))
    ws.on("framesent", sent)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1000, "height": 700})
    page = ctx.new_page()
    page.on("console", lambda m: console.append((m.type, m.text[:300])))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("websocket", on_ws)

    mark("goto")
    page.goto(url, wait_until="networkidle", timeout=90000)
    page.locator("#title").wait_for(timeout=30000)
    mark("mounted")
    page.wait_for_timeout(W * 1000)
    page.screenshot(path=f"{shot}-after-load.png")
    counts1 = {k: page.locator(f"#{k}").inner_text() for k in ("tick_count", "static_count", "zero_count", "tick_log", "static_log", "zero_log")}
    time_el = page.locator("#interval time").first
    interval_html = time_el.evaluate("e => e.outerHTML") if time_el.count() else page.locator("#interval").inner_html()
    static_html = page.locator("#static").inner_html()

    mark("reload")
    page.reload(wait_until="networkidle")
    page.locator("#title").wait_for(timeout=30000)
    mark("remounted")
    page.wait_for_timeout(W * 1000)
    counts2 = {k: page.locator(f"#{k}").inner_text() for k in ("tick_count", "static_count", "zero_count", "tick_log", "static_log", "zero_log")}

    mark("nav_to_other")
    page.locator("#to_other").click()
    page.locator("#other_title").wait_for(timeout=30000)
    page.wait_for_timeout(2500)
    mark("nav_back")
    page.locator("#to_index").click()
    page.locator("#title").wait_for(timeout=30000)
    mark("client_remounted")
    page.wait_for_timeout(W * 1000)
    counts3 = {k: page.locator(f"#{k}").inner_text() for k in ("tick_count", "static_count", "zero_count", "tick_log", "static_log", "zero_log")}
    page.screenshot(path=f"{shot}-final.png")
    mark("done")
    page.wait_for_timeout(500)
    browser.close()

out = {
    "url": url, "wait_seconds": W, "phases": phases, "frames": frames,
    "counts_after_load": counts1, "counts_after_reload": counts2, "counts_after_client_nav": counts3,
    "interval_time_outerHTML": interval_html, "static_innerHTML": static_html,
    "websockets": ws_events, "console": console, "page_errors": page_errors,
}
with open(report, "w") as f:
    json.dump(out, f, indent=1, ensure_ascii=False, default=str)
print("FRAMES (wall, ws, handler, payload):")
for fr in frames:
    print("  ", fr)
print("counts_after_load:", counts1)
print("counts_after_reload:", counts2)
print("counts_after_client_nav:", counts3)
print("interval outerHTML:", interval_html)
print("static innerHTML:", static_html)
print("page_errors:", page_errors)
print("console:", [c for c in console if c[0] in ("error", "warning")])

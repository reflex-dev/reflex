"""Verify per-yield interim update flushing from a sync generator (#6734).

Usage: drive_stream.py <frontend_url_base> <screenshot_dir>

The handler yields progress 1..10, blocking the event loop 120ms after each
yield via time.sleep. If the flush tick after each emit is intact, the browser
receives ~10 spaced DOM updates (~120ms apart). If interim updates batch, the
observer records few changes clustered at the end.
"""

import json
import statistics
import sys
import time

from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180").rstrip("/")
SHOTDIR = sys.argv[2] if len(sys.argv) > 2 else "."

console_msgs = []
failed_requests = []
bad_responses = []
out = {}

OBSERVER = """
() => {
  window.__prog = [];
  const el = document.querySelector('#progress');
  const mo = new MutationObserver(() => {
    window.__prog.push({t: performance.now(), v: el.textContent});
  });
  mo.observe(el, {childList: true, characterData: true, subtree: true});
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.on("requestfailed", lambda r: failed_requests.append((r.url, str(r.failure))))
    page.on(
        "response",
        lambda r: bad_responses.append((r.status, r.url)) if r.status >= 400 else None,
    )
    page.goto(BASE + "/stream/", wait_until="networkidle", timeout=90000)
    page.wait_for_selector("#progress", timeout=30000)
    time.sleep(2)  # hydration
    page.evaluate(OBSERVER)
    page.click("#btn-stream")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if page.eval_on_selector("#stream-done", "el => el.textContent") == "true":
            break
        time.sleep(0.1)
    time.sleep(0.5)
    changes = page.evaluate("() => window.__prog")
    page.screenshot(path=f"{SHOTDIR}/stream_final.png")
    browser.close()

values = [c["v"] for c in changes]
times = [c["t"] for c in changes]
out["n_changes"] = len(changes)
out["values"] = values
distinct = sorted({int(v) for v in values if v.isdigit()})
out["distinct_progress_values_seen"] = distinct
gaps = [t2 - t1 for t1, t2 in zip(times, times[1:])]
out["gaps_ms"] = [round(g, 1) for g in gaps]
if times:
    out["span_ms"] = round(times[-1] - times[0], 1)
if gaps:
    out["median_gap_ms"] = round(statistics.median(gaps), 1)

# Incremental streaming: at least 8 of the 10 interim values observed, spread
# over >= 800ms (10 * 120ms sleep would be ~1.2s), not batched at the end.
incremental = (
    len(distinct) >= 8
    and out.get("span_ms", 0) >= 800
    and out.get("median_gap_ms", 0) >= 60
)
out["incremental"] = incremental
print("RESULTS:", json.dumps(out, indent=1))
interesting_console = [
    (t, m)
    for t, m in console_msgs
    if not any(
        s in m
        for s in ("HydrateFallback", "[vite]", "React DevTools", "Download the React DevTools")
    )
]
print("CONSOLE:", json.dumps(interesting_console[:40], default=str))
print("FAILED_REQUESTS:", json.dumps(failed_requests, default=str))
print("HTTP_4XX_5XX:", json.dumps(bad_responses))
print("VERDICT:", "PASS" if incremental else "FAIL")
sys.exit(0 if incremental else 1)

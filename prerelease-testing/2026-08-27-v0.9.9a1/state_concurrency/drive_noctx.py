"""Verify background handlers that never enter ``async with self`` (#6920).

Usage: drive_noctx.py <frontend_url_base> <screenshot_dir>

1. bg_nudge (no context, no writes): clicking it must still refresh the
   uncached computed var `heartbeat` in the browser -- the compatibility
   flush now runs under the state lock but must still happen.
2. bg_illegal_write (writes without ``async with self``): expected to raise
   ImmutableStateError server-side; UI must stay responsive and unchanged.
"""

import json
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
  window.__hb_changes = [];
  const el = document.querySelector('#heartbeat');
  const mo = new MutationObserver(() => {
    window.__hb_changes.push({t: performance.now(), v: el.textContent});
  });
  mo.observe(el, {childList: true, characterData: true, subtree: true});
  return el.textContent;
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
    page.goto(BASE + "/noctx/", wait_until="networkidle", timeout=90000)
    page.wait_for_selector("#heartbeat", timeout=30000)
    # Wait for hydration: heartbeat gets a first server value on load.
    time.sleep(2)
    initial = page.eval_on_selector("#heartbeat", "el => el.textContent")

    # Attach observer, then click nudge once.
    before = page.evaluate(OBSERVER)
    page.click("#btn-nudge")
    time.sleep(2.5)
    changes = page.evaluate("() => window.__hb_changes")
    out["nudge_heartbeat_before"] = before
    out["nudge_changes"] = changes
    out["nudge_delta_emitted"] = len(changes) >= 1

    # Second nudge to confirm repeatability and count deltas per event.
    page.evaluate("() => { window.__hb_changes = [] }")
    page.click("#btn-nudge")
    time.sleep(2.5)
    out["nudge2_changes"] = page.evaluate("() => window.__hb_changes")

    # Illegal write: expect no UI change, no crash; server should log an error.
    page.evaluate("() => { window.__hb_changes = [] }")
    page.click("#btn-illegal")
    time.sleep(2.5)
    out["illegal_error_text"] = page.eval_on_selector(
        "#illegal-error", "el => el.textContent"
    )
    out["illegal_changes"] = page.evaluate("() => window.__hb_changes")
    # UI must remain responsive: nudge again and see a heartbeat change.
    page.evaluate("() => { window.__hb_changes = [] }")
    page.click("#btn-nudge")
    time.sleep(2.5)
    out["post_illegal_nudge_changes"] = page.evaluate("() => window.__hb_changes")
    out["responsive_after_illegal"] = len(out["post_illegal_nudge_changes"]) >= 1
    page.screenshot(path=f"{SHOTDIR}/noctx_final.png")
    browser.close()

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
ok = out["nudge_delta_emitted"] and out["responsive_after_illegal"] and out[
    "illegal_error_text"
].strip() == ""
print("VERDICT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)

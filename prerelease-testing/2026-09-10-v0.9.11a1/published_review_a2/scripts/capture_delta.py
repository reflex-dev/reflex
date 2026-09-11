"""Capture the state delta a single event produces, as parsed JSON.

Usage: capture_delta.py <base_url> <out.json>
Loads /reactive, clicks the "en" button, and saves every socket frame the
browser received, with the delta payload parsed rather than compared as text.
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], sys.argv[2]
recv = []

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("websocket", lambda ws: ws.on("framereceived", lambda pl: recv.append(str(pl))))
    page.goto(BASE + "/reactive", wait_until="domcontentloaded")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(2500)
    mark = len(recv)
    page.click("#btn-en")
    page.wait_for_timeout(2500)
    br.close()


def parse(frames):
    """Pull the delta objects out of socket.io frames."""
    out = []
    for f in frames:
        i = f.find("[")
        if i < 0:
            continue
        try:
            msg = json.loads(f[i:])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(msg, list) and len(msg) > 1 and isinstance(msg[1], dict):
            d = msg[1].get("delta")
            if d:
                out.append(d)
    return out


res = {"base": BASE, "frames_before_click": mark, "frames_total": len(recv),
       "deltas_after_click": parse(recv[mark:]), "deltas_hydrate": parse(recv[:mark])}
with open(OUT, "w") as f:
    json.dump(res, f, indent=1)
print(json.dumps(res["deltas_after_click"], indent=1)[:900])

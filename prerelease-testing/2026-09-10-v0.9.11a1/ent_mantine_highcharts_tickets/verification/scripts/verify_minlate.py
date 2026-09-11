"""Click the counter button and report whether the event reaches the backend."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE, OUT, SHOTS = sys.argv[1], sys.argv[2], sys.argv[3]
Path(SHOTS).mkdir(parents=True, exist_ok=True)
sent, recv, console = [], [], []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context(viewport={"width": 900, "height": 700}).new_page()
    page.on("console", lambda m: console.append([m.type, m.text[:400]]))
    page.on("websocket", lambda ws: (
        ws.on("framesent", lambda pl: sent.append(str(pl)[:1200])),
        ws.on("framereceived", lambda pl: recv.append(str(pl)[:1200])),
    ))
    page.goto(BASE, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(5000)
    page.screenshot(path=f"{SHOTS}/01_loaded.png")
    before = page.inner_text("#count")
    n = len(sent)
    for _ in range(3):
        page.click("#inc")
        page.wait_for_timeout(800)
    page.wait_for_timeout(2000)
    page.screenshot(path=f"{SHOTS}/02_after_clicks.png")
    rep = {
        "count_before": before,
        "count_after": page.inner_text("#count"),
        "new_sent": sent[n:],
        "console": console,
    }
    Path(OUT).write_text(json.dumps({**rep, "sent": sent, "recv": recv}, indent=1))
    print(json.dumps(rep, indent=1)[:3000])
    br.close()

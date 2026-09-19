"""Drive the otel test app in Chromium and capture console / network / ws frames."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

FRONTEND = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5180"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/otel-drive")
STEPS = sys.argv[3].split(",") if len(sys.argv) > 3 else ["all"]
OUT.mkdir(parents=True, exist_ok=True)

console: list = []
pageerrors: list = []
requests_failed: list = []
responses_bad: list = []
ws_frames: list = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/opt/pw-browsers/chromium",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(ignore_https_errors=True)
        page = ctx.new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: pageerrors.append(str(e)))
        page.on("requestfailed", lambda r: requests_failed.append({"url": r.url, "err": str(r.failure)}))

        def on_resp(r):
            if r.status >= 400:
                responses_bad.append({"url": r.url, "status": r.status})

        page.on("response", on_resp)

        def on_ws(ws):
            ws_frames.append({"ev": "open", "url": ws.url, "t": time.time()})
            ws.on("framesent", lambda pl: ws_frames.append({"ev": "sent", "payload": pl if isinstance(pl, str) else "<bin>", "t": time.time()}))
            ws.on("framereceived", lambda pl: ws_frames.append({"ev": "recv", "payload": pl if isinstance(pl, str) else "<bin>", "t": time.time()}))
            ws.on("close", lambda _: ws_frames.append({"ev": "close", "t": time.time()}))

        page.on("websocket", on_ws)

        page.goto(FRONTEND, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "01-loaded.png"))

        do = lambda s: "all" in STEPS or s in STEPS

        if do("inc"):
            for _ in range(3):
                page.click("#btn-inc")
                page.wait_for_timeout(250)
            print("count:", page.text_content("#count"))

        if do("chain"):
            page.click("#btn-chain")
            page.wait_for_timeout(800)
            print("chained:", page.text_content("#chained"))

        if do("userspan"):
            page.click("#btn-userspan")
            page.wait_for_timeout(800)
            print("count after userspan:", page.text_content("#count"))

        if do("bg"):
            page.click("#btn-bg")
            page.wait_for_timeout(1500)
            print("bg_ticks:", page.text_content("#bg_ticks"))

        if do("boom"):
            page.click("#btn-boom")
            page.wait_for_timeout(1200)

        if do("upload"):
            f = OUT / "payload.txt"
            f.write_text("hello otel upload " * 10)
            page.set_input_files("#up1 input[type=file]", str(f))
            page.wait_for_timeout(400)
            page.click("#btn-upload")
            page.wait_for_timeout(1500)
            print("uploaded:", page.text_content("#uploaded"))

        if do("nav"):
            page.click("#link-second")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / "02-second.png"))
            try:
                print("loaded:", page.text_content("#loaded"))
            except Exception as e:
                print("loaded read failed:", e)
            page.click("#link-home")
            page.wait_for_timeout(1200)

        page.screenshot(path=str(OUT / "03-final.png"))
        page.wait_for_timeout(500)
        ctx.close()
        browser.close()

    (OUT / "console.json").write_text(json.dumps(console, indent=1))
    (OUT / "pageerrors.json").write_text(json.dumps(pageerrors, indent=1))
    (OUT / "requests_failed.json").write_text(json.dumps(requests_failed, indent=1))
    (OUT / "responses_bad.json").write_text(json.dumps(responses_bad, indent=1))
    (OUT / "ws_frames.json").write_text(json.dumps(ws_frames, indent=1))
    errs = [c for c in console if c["type"] in ("error", "warning")]
    print("console errors/warnings:", json.dumps(errs, indent=1)[:3000])
    print("pageerrors:", pageerrors)
    print("requestfailed:", requests_failed)
    print("bad responses:", responses_bad)
    print("ws frames:", len(ws_frames))


main()

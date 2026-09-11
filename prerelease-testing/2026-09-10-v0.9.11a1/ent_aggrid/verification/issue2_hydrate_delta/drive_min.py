"""Hydrate-delta loss probe: click N times, reload, see whether the value survives."""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)
TAG = sys.argv[3] if len(sys.argv) > 3 else "run"

out = {"console": [], "page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1100, "height": 800})
    page = ctx.new_page()
    page.on("console", lambda m: out["console"].append(f"{m.type}: {m.text}"[:400]))
    page.on("pageerror", lambda e: out["page_errors"].append(str(e)[:400]))
    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector("#btn", timeout=30000)
    page.wait_for_timeout(2500)
    out["initial"] = page.locator("#btn").inner_text()
    for _ in range(3):
        page.locator("#btn").click()
        page.wait_for_timeout(500)
    out["after_3_clicks"] = page.locator("#btn").inner_text()
    page.screenshot(path=str(SHOTS / f"{TAG}_after3.png"))
    page.reload(wait_until="load", timeout=60000)
    page.wait_for_selector("#btn", timeout=30000)
    page.wait_for_timeout(3500)
    out["after_reload"] = page.locator("#btn").inner_text()
    out["body_text_after_reload"] = page.locator("body").inner_text()[:600]
    page.screenshot(path=str(SHOTS / f"{TAG}_afterreload.png"), full_page=True)
    page.locator("#btn").click()
    page.wait_for_timeout(1200)
    out["after_reload_plus_one_click"] = page.locator("#btn").inner_text()
    page.screenshot(path=str(SHOTS / f"{TAG}_afterclick.png"), full_page=True)
    ctx.close()
    b.close()

print(json.dumps(out, indent=2))
(SHOTS / f"{TAG}_report.json").write_text(json.dumps(out, indent=2))

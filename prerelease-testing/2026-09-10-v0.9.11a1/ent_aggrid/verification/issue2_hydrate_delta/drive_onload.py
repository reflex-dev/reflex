"""Does a failed hydrate delta also block on_load handlers and is_hydrated?"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)
TAG = sys.argv[3]
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_context(viewport={"width": 1100, "height": 800}).new_page()
    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector("#btn", timeout=30000)
    page.wait_for_timeout(4000)
    out["count"] = page.locator("#btn").inner_text()
    out["loaded"] = page.locator("#loaded").inner_text()
    out["is_hydrated"] = page.locator("#hyd").inner_text()
    out["body"] = page.locator("body").inner_text()[:400]
    page.screenshot(path=str(SHOTS / f"{TAG}_onload.png"), full_page=True)
    b.close()
print(json.dumps(out, indent=2))
(SHOTS / f"{TAG}_onload.json").write_text(json.dumps(out, indent=2))

"""Dump the body text of the two grid-state-serialization routes after clicking their buttons.

Usage: python dump_serialization.py <base_url> <out_dir>
Writes <out_dir>/<slug>.txt for /simple-serialization and /advanced-serialization.
"""
import sys, json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
console = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text[:300]}))
    page.on("pageerror", lambda e: console.append({"type": "pageerror", "text": str(e)[:300]}))
    for route in ("/simple-serialization", "/advanced-serialization"):
        page.goto(BASE + route, wait_until="load", timeout=60000)
        page.wait_for_selector(".ag-root", timeout=40000)
        page.wait_for_timeout(2500)
        slug = route.strip("/")
        (OUT / f"{slug}_before.txt").write_text(page.locator("body").inner_text())
        for label in ("Save", "Restore", "Save State", "Restore State", "Get State", "Apply State"):
            bt = page.get_by_role("button", name=label)
            if bt.count():
                bt.first.click(); page.wait_for_timeout(1200)
        page.wait_for_timeout(1000)
        txt = page.locator("body").inner_text()
        (OUT / f"{slug}_after.txt").write_text(txt)
        page.screenshot(path=str(OUT / f"{slug}_dump.png"), full_page=True)
        print(route, "len", len(txt))
    ctx.close(); b.close()
(OUT / "dump_console.json").write_text(json.dumps(console, indent=2))

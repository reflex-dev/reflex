"""Open URL(s) in Chromium, wait, screenshot, print console errors and visible text excerpt.

Usage: shot_url.py <out_dir> <label> <url> [<url> ...]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

out, label, urls = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    msgs = []
    pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:300]}"))
    pg.on("pageerror", lambda e: msgs.append(f"pageerror: {str(e)[:300]}"))
    for i, u in enumerate(urls):
        msgs.clear()
        pg.goto(u, wait_until="networkidle")
        pg.wait_for_timeout(4000)
        f = out / f"{label}-{i}.jpg"
        pg.screenshot(path=str(f), type="jpeg", quality=70)
        print("==", u, "->", f)
        print("text:", pg.inner_text("body")[:400].replace("\n", " | "))
        for m in msgs:
            if not m.startswith(("debug", "info")) and "AG Grid Enterprise" not in m and "****" not in m:
                print("  ", m)
    b.close()

"""Home -> /fr -> home, reading the two no-locale moments each time."""
import json
import sys

from playwright.sync_api import sync_playwright

base, out = sys.argv[1], sys.argv[2]
rec = {"console": [], "page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: rec["console"].append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: rec["page_errors"].append(str(e)))
    pg.goto(base + "/", wait_until="networkidle")
    pg.wait_for_selector("#plain", timeout=60000)
    pg.wait_for_timeout(2500)
    rec["home_fresh"] = {i: pg.inner_text(f"#{i}") for i in ("plain", "fromnow")}
    pg.screenshot(path=out.replace(".json", "-home-fresh.png"), full_page=True)
    pg.click("#tofr")
    pg.wait_for_selector("#french", timeout=60000)
    pg.wait_for_timeout(2500)
    rec["fr_page"] = {"french": pg.inner_text("#french")}
    pg.click("#tohome")
    pg.wait_for_selector("#plain", timeout=60000)
    pg.wait_for_timeout(2500)
    rec["home_after_visiting_fr"] = {i: pg.inner_text(f"#{i}") for i in ("plain", "fromnow")}
    pg.screenshot(path=out.replace(".json", "-home-after.png"), full_page=True)
    b.close()
open(out, "w").write(json.dumps(rec, indent=2))
print(json.dumps({k: v for k, v in rec.items() if k != "console"}, indent=2))

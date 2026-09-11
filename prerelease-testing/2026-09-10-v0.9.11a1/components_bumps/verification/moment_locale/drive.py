"""Read the moment components on a page; capture console, page errors, failed requests."""
import json
import sys

from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
ids = sys.argv[3].split(",") if len(sys.argv) > 3 else ["plain", "fromnow", "french"]

rec = {"url": url, "console": [], "page_errors": [], "failed": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: rec["console"].append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: rec["page_errors"].append(str(e)))
    pg.on("requestfailed", lambda r: rec["failed"].append(r.url))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_selector("#ready", timeout=60000)
    pg.wait_for_timeout(3000)
    rec["first_load"] = {i: pg.inner_text(f"#{i}") for i in ids}
    pg.reload(wait_until="networkidle")
    pg.wait_for_selector("#ready", timeout=60000)
    pg.wait_for_timeout(3000)
    rec["after_reload"] = {i: pg.inner_text(f"#{i}") for i in ids}
    pg.screenshot(path=out.replace(".json", ".png"), full_page=True)
    b.close()
open(out, "w").write(json.dumps(rec, indent=2))
print(json.dumps({k: rec[k] for k in ("first_load", "after_reload", "page_errors")}, indent=2))
print("console:", len(rec["console"]), "failed:", len(rec["failed"]))

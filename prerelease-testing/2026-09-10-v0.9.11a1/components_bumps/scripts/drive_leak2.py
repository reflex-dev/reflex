"""Read the three moments of the minimal locale-bleed repro."""
import json
import sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(3500)
    res = {i: pg.inner_text(f"#{i}") for i in ["plain", "fromnow", "french"]}
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(3000)
    res["after_reload"] = {i: pg.inner_text(f"#{i}") for i in ["plain", "fromnow", "french"]}
    b.close()
open(out, "w").write(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))

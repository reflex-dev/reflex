"""Read the four moments of the locale-leak repro app, before and after a locale change."""
import json
import sys
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
res = {"console": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text[:160]}"))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(3000)
    ids = ["plain", "fromnow", "french", "stateloc", "memoed", "spanish", "tzprobe"]
    res["initial"] = {i: pg.inner_text(f"#{i}") for i in ids}
    pg.click("#next")
    pg.wait_for_timeout(1500)
    res["after_next_locale"] = {i: pg.inner_text(f"#{i}") for i in ids}
    pg.click("#next")
    pg.wait_for_timeout(1500)
    res["after_next_locale_2"] = {i: pg.inner_text(f"#{i}") for i in ids}
    pg.reload(wait_until="networkidle")
    pg.wait_for_timeout(2500)
    res["after_reload"] = {i: pg.inner_text(f"#{i}") for i in ids}
    b.close()
open(out, "w").write(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))

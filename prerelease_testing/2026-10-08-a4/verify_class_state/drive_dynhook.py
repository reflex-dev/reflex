"""Click both toggles and record the two texts: independent vars => toggling one leaves the other.
Usage: drive_dynhook.py <url> <out.json> <screenshot.png>"""
import json
import sys

from playwright.sync_api import sync_playwright

url, out, shot = sys.argv[1:4]
res = {"console": [], "failed": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text[:200]}"))
    pg.on("requestfailed", lambda r: res["failed"].append(r.url))
    pg.goto(url, wait_until="networkidle", timeout=120000)
    pg.wait_for_function("document.querySelector('#p1') && document.querySelector('#p1').textContent.includes('page1:')", timeout=60000)

    def texts():
        return pg.text_content("#p1"), pg.text_content("#det")

    res["initial"] = texts()
    pg.click("#b2")
    pg.wait_for_timeout(1500)
    res["after_toggle_detail"] = texts()
    pg.click("#b1")
    pg.wait_for_timeout(1500)
    res["after_toggle_page1"] = texts()
    pg.screenshot(path=shot)
    b.close()
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1))

"""#7415/#7585: a background task started by a click, then the tab closes; what runs afterwards?"""
import json, sys, time
from playwright.sync_api import sync_playwright
base, logpath = sys.argv[1], sys.argv[2]
n0 = len(open(logpath).read().splitlines()) if __import__("os").path.exists(logpath) else 0
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium"); ctx = b.new_context(); page = ctx.new_page()
    page.goto(base + "/expire"); page.wait_for_selector("#start8"); page.wait_for_timeout(1500)
    page.click("#start8"); page.wait_for_timeout(800)
    print("status before close:", page.locator("#status").inner_text(), "loads:", page.locator("#loads").inner_text())
    ctx.close(); b.close()
time.sleep(14)
recs = [json.loads(x) for x in open(logpath).read().splitlines()[n0:]]
print("server records after click+close:", [(r["who"], r.get("step"), r.get("count"), r.get("loads")) for r in recs])

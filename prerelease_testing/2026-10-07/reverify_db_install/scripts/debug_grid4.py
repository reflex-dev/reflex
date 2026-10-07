"""List module requests for glide/react in direct vs nav mode."""
import re
import sys
from playwright.sync_api import sync_playwright
from pwkit import CHROMIUM
base, mode = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page()
    reqs = []
    page.on("request", lambda r: reqs.append(r.url))
    if mode == "nav":
        page.goto(base + "/", wait_until="networkidle"); page.wait_for_selector("#page-home"); page.click("#nav-charts")
    else:
        page.goto(base + "/charts", wait_until="networkidle")
    page.wait_for_selector("canvas[data-testid='data-grid-canvas']", timeout=30000)
    page.wait_for_timeout(2000)
    interesting = sorted({u.replace(base, "") for u in reqs if re.search(r"glide|data-grid|react-dom|/react\.js|react_jsx|chunk-|dataeditor", u)})
    print(mode, len(reqs), "requests")
    for u in interesting:
        print("  ", u[:160])
    b.close()

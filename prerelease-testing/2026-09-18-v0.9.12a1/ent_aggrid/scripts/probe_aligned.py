import json, sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_context(viewport={"width": 900, "height": 800}).new_page()
    page.goto(BASE + "/aligned-grids", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell", timeout=40000); page.wait_for_timeout(2500)
    info = page.evaluate("""() => {
      const q = s => Array.from(document.querySelectorAll(s));
      return {
        hviews: q('.ag-body-horizontal-scroll-viewport').map(e => ({sw:e.scrollWidth, cw:e.clientWidth, sl:e.scrollLeft})),
        centers: q('.ag-center-cols-viewport').map(e => ({sw:e.scrollWidth, cw:e.clientWidth, sl:e.scrollLeft})),
      };
    }""")
    print(json.dumps(info, indent=1))
    # scroll the first center viewport and read both
    page.evaluate("""() => { const e = document.querySelectorAll('.ag-center-cols-viewport')[0]; if (e) e.scrollLeft = 200; }""")
    page.wait_for_timeout(1200)
    after = page.evaluate("""() => Array.from(document.querySelectorAll('.ag-center-cols-viewport')).map(e => e.scrollLeft)""")
    print("after scroll of grid0:", after)
    page.screenshot(path=sys.argv[2])
    b.close()

import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    p.goto(sys.argv[1], wait_until="networkidle"); p.wait_for_timeout(2000)
    c0 = p.locator(".highcharts-container").nth(0)
    pt = c0.locator(".highcharts-series-1 .highcharts-point[class*='highcharts-color-']").nth(2)
    bb = pt.bounding_box()
    for dx in (0, 2, -2):
        p.mouse.move(bb["x"] + bb["width"] / 2 + dx, bb["y"] + bb["height"] / 2)
        p.wait_for_timeout(300)
    print(p.evaluate("""() => [...document.querySelectorAll('[class*=tooltip]')].map(e => e.tagName + '.' + e.getAttribute('class') + ' :: ' + (e.textContent||'').slice(0,120) + ' vis=' + getComputedStyle(e).visibility + ' op=' + getComputedStyle(e).opacity)"""))
    b.close()

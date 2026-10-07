import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    p.goto(sys.argv[1], wait_until="networkidle"); p.wait_for_timeout(2000)
    print(p.evaluate("""() => [...document.querySelectorAll('.highcharts-point')].map(e => e.tagName + '.' + e.getAttribute('class') + ' in ' + (e.closest('[id]')?.id || '') + ' ' + (e.closest('.highcharts-container')?.id || '')).join('\\n')"""))
    print("titles:", p.locator(".highcharts-title").evaluate_all("els => els.map(e => e.textContent)"))
    print("hc global:", p.evaluate("() => typeof window.Highcharts"))
    b.close()

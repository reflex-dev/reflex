"""Inspect overlay editor state in direct vs nav mode."""
import sys
from playwright.sync_api import sync_playwright
from pwkit import CHROMIUM
base, mode = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page(viewport={"width": 1100, "height": 1300})
    if mode == "nav":
        page.goto(base + "/", wait_until="networkidle"); page.wait_for_selector("#page-home"); page.click("#nav-charts")
    else:
        page.goto(base + "/charts", wait_until="networkidle")
    page.wait_for_selector("canvas[data-testid='data-grid-canvas']", timeout=30000)
    page.wait_for_timeout(2000)
    print(mode, "portals:", page.evaluate("document.querySelectorAll('#portal').length"),
          "portal parent:", page.evaluate("document.getElementById('portal')?.parentElement?.tagName"))
    box = page.locator("canvas[data-testid='data-grid-canvas']").first.bounding_box()
    page.mouse.click(box["x"] + 25, box["y"] + 36 + 17)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(600)
    info = page.evaluate("""() => { const a = document.activeElement; const r = a.getBoundingClientRect();
        return {cls: a.className, value: a.value, rect: [r.x, r.y, r.width, r.height],
                inPortal: !!a.closest('#portal'), overlay: !!document.querySelector('.gdg-overlay, [class*=overlay]')}; }""")
    print(mode, "after Enter:", info)
    page.keyboard.press("Control+A"); page.keyboard.type("gamma")
    print(mode, "after typing:", page.evaluate("document.activeElement.value"))
    page.keyboard.press("Enter"); page.wait_for_timeout(1500)
    print(mode, "after commit active:", page.evaluate("document.activeElement?.className"), "edited:", page.locator('#edited').inner_text())
    b.close()

import sys
from playwright.sync_api import sync_playwright
from pwkit import CHROMIUM
base, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page(viewport={"width": 1100, "height": 1300})
    logs = []
    page.on("console", lambda m: logs.append(f"{m.type}: {m.text[:200]}"))
    page.goto(base + "/charts", wait_until="networkidle")
    page.wait_for_selector("canvas[data-testid='data-grid-canvas']", timeout=30000)
    canvas = page.locator("canvas[data-testid='data-grid-canvas']").first
    box = canvas.bounding_box()
    print("canvas box", box)
    page.mouse.click(box["x"] + 25, box["y"] + 36 + 17)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    print("portal children:", page.evaluate("document.getElementById('portal')?.innerHTML?.slice(0,300)"))
    print("active element:", page.evaluate("document.activeElement?.tagName + ' ' + (document.activeElement?.className||'')"))
    page.screenshot(path=f"{out}/grid-after-enter.png")
    page.keyboard.press("Control+A")
    page.keyboard.type("gamma")
    page.wait_for_timeout(300)
    page.screenshot(path=f"{out}/grid-after-type.png")
    page.keyboard.press("Enter")
    page.wait_for_timeout(1500)
    print("edited:", page.locator("#edited").inner_text())
    print("\n".join(logs[-10:]))
    b.close()

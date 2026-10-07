"""Isolate data_editor edit after client-side navigation vs direct load."""
import sys
from playwright.sync_api import sync_playwright
from pwkit import CHROMIUM
base, out, mode = sys.argv[1], sys.argv[2], sys.argv[3]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    page = b.new_page(viewport={"width": 1100, "height": 1300})
    sent = []
    page.on("websocket", lambda ws: ws.on("framesent", lambda f: sent.append(str(f)[:400])))
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)[:300]))
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    if mode == "nav":
        page.goto(base + "/", wait_until="networkidle")
        page.wait_for_selector("#page-home")
        page.click("#nav-charts")
    else:
        page.goto(base + "/charts", wait_until="networkidle")
    page.wait_for_selector("canvas[data-testid='data-grid-canvas']", timeout=30000)
    page.wait_for_timeout(2000)
    canvas = page.locator("canvas[data-testid='data-grid-canvas']").first
    box = canvas.bounding_box()
    page.mouse.click(box["x"] + 25, box["y"] + 36 + 17)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(600)
    print("active:", page.evaluate("document.activeElement?.className"))
    page.keyboard.press("Control+A")
    page.keyboard.type("gamma")
    page.wait_for_timeout(int(sys.argv[4]) if len(sys.argv) > 4 else 0)
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)
    print(mode, "edited:", page.locator("#edited").inner_text())
    print("frames sent containing cell_edited:", [s for s in sent if "cell_edited" in s][:3])
    print("errors/warnings:", errs[:8])
    page.screenshot(path=f"{out}/grid-{mode}.png")
    b.close()

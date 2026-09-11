"""Count sonner Toaster roots on a page and show their config attributes."""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    msgs = []
    pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text}"[:200]))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(2500)
    print("toasters:", pg.evaluate("""() => Array.from(document.querySelectorAll('[data-sonner-toaster]')).map(e => ({
        y: e.dataset.yPosition, x: e.dataset.xPosition, rich: e.dataset.richColors,
        expanded: e.dataset.expanded, theme: e.dataset.theme, n: e.querySelectorAll('[data-sonner-toast]').length}))"""))
    pg.click("#t-info")
    pg.wait_for_timeout(1200)
    print("after info:", pg.evaluate("""() => Array.from(document.querySelectorAll('[data-sonner-toaster]')).map(e => ({
        y: e.dataset.yPosition, x: e.dataset.xPosition, rich: e.dataset.richColors,
        n: e.querySelectorAll('[data-sonner-toast]').length, texts: Array.from(e.querySelectorAll('[data-sonner-toast]')).map(t=>t.innerText)}))"""))
    print("console:", [m for m in msgs if "vite" not in m and "DevTools" not in m][:6])
    b.close()

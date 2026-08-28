import sys, time
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.on("console", lambda m: print(f"[{m.type}] {m.text[:300]}"))
    page.on("pageerror", lambda e: print(f"[pageerror] {e}"))
    page.on("websocket", lambda ws: print(f"[ws] {ws.url}"))
    page.on("response", lambda r: print(f"[http {r.status}] {r.url[:120]}") if r.status >= 400 else None)
    page.goto(url, wait_until="networkidle")
    time.sleep(3)
    print("--- clicking #btn-week ---")
    page.click("#btn-week")
    time.sleep(4)
    print("key text:", page.inner_text("#key"))
    browser.close()

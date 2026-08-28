import sys, time
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.on("console", lambda m: print("CONSOLE", m.type, m.text[:150]) if m.type in ("error","warning") else None)
    page.goto(base + "/login", wait_until="load")
    page.locator('input[name="username"]').wait_for(timeout=20000)
    page.fill('input[name="username"]', "user098")
    page.fill('input[name="password"]', "S3cretPass!42")
    page.get_by_role("button", name="Sign in").click()
    for i in range(15):
        time.sleep(1)
        print(i+1, "url:", page.url)
        if "/login" not in page.url:
            break
    b.close()

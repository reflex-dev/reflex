"""Type a key in overkey and read the timer twice to see the stacked background `tick` running. usage: drive_overkey.py <url> <png>"""
import sys, time
from playwright.sync_api import sync_playwright

url, png = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    msgs = []
    pg.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:160]}"))
    pg.goto(url)
    pg.wait_for_selector("#words", timeout=60000)
    time.sleep(2)
    pg.locator("input").first.click(force=True)
    pg.keyboard.press("a")
    time.sleep(1.5)
    t1 = pg.inner_text("body")
    time.sleep(2.5)
    t2 = pg.inner_text("body")
    pg.screenshot(path=png)
    import re
    nums = lambda t: re.findall(r"\b\d+\b", t)[:6]
    print("t1 numbers", nums(t1)); print("t2 numbers", nums(t2))
    print("console:", [m for m in msgs if m.startswith(("error", "warning"))])
    b.close()

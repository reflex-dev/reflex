"""Drive the smoke app; print page values, console errors/warnings, failed requests, toasts. usage: smoke_drive.py <base> <png_prefix>"""
import sys
import time

from playwright.sync_api import sync_playwright

base, prefix = sys.argv[1].rstrip("/"), sys.argv[2]
IDS = ["total", "ticks", "status", "has_hello", "ntags", "clicks"]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    msgs, bad = [], []
    pg.on("console", lambda m: msgs.append(f"console.{m.type}: {m.text[:250]}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: msgs.append(f"pageerror: {str(e)[:250]}"))
    pg.on("response", lambda r: bad.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.on("requestfailed", lambda r: bad.append(f"FAILED {r.url} {r.failure}"))
    pg.goto(base + "/")
    pg.wait_for_selector("#total", timeout=60000)
    pg.wait_for_timeout(2500)

    def snap(label):
        v = {i: pg.inner_text(f"#{i}").split("=", 1)[1] for i in IDS}
        print(f"{label:22s}", v, "log=", [e.inner_text() for e in pg.query_selector_all(".log")], flush=True)

    snap("initial")
    pg.click("#add_twice"); pg.wait_for_timeout(1500)
    toasts = [e.inner_text()[:80] for e in pg.query_selector_all("[data-sonner-toast]")]
    snap("after add_twice"); print("   toasts:", toasts)
    pg.fill("#draft", "hello"); pg.wait_for_timeout(300)
    for _ in range(4):
        pg.click("#throttled")
    pg.wait_for_timeout(1200)
    snap("after 4x throttled")
    pg.click("#ticker"); pg.wait_for_timeout(300)
    snap("ticker running")
    pg.wait_for_timeout(2000)
    snap("ticker done")
    pg.click("#clear"); pg.wait_for_timeout(1000)
    snap("after clear tags")
    pg.screenshot(path=f"{prefix}_home.png")
    pg.click("text=other"); pg.wait_for_selector("#o_total"); pg.wait_for_timeout(800)
    print("other page:", pg.inner_text("#o_total"), pg.inner_text("#o_clicks"))
    pg.click("text=home"); pg.wait_for_selector("#total"); pg.wait_for_timeout(800)
    snap("back home")
    pg.reload(); pg.wait_for_selector("#total"); pg.wait_for_timeout(2500)
    snap("after reload")
    print("console:", [m for m in msgs if "favicon" not in m])
    print("failed requests:", [x for x in bad if "favicon" not in x])
    b.close()

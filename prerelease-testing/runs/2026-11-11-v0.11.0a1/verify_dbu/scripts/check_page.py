"""check_page.py <url> <expected text> <screenshot>: load in Chromium, wait for text, report console errors / failed requests."""
import sys

from playwright.sync_api import sync_playwright

url, text, shot = sys.argv[1:4]
errs, bad = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: m.type in ("error", "warning") and errs.append(f"{m.type}: {m.text[:200]}"))
    pg.on("response", lambda r: r.status >= 400 and bad.append(f"{r.status} {r.url}"))
    pg.goto(url, timeout=180000)
    try:
        pg.get_by_text(text).first.wait_for(timeout=120000)
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = False
        print("WAIT FAILED", type(e).__name__)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=shot, full_page=True)
    b.close()
print(("PASS" if ok else "FAIL"), "text", repr(text), "on", url)
print("console:", errs or "none")
print("http>=400:", bad or "none")

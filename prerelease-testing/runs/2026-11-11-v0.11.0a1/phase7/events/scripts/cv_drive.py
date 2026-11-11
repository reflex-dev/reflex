"""Open pages, report status, console errors, failed responses and visible text."""
import sys

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
base, *paths = sys.argv[1:]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    msgs = []
    pg.on("console", lambda m: msgs.append(f"console.{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: msgs.append(f"pageerror: {str(e)[:300]}"))
    pg.on("response", lambda r: msgs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    for path in paths:
        click = None
        if "!" in path:
            path, click = path.split("!", 1)
        msgs.clear()
        r = pg.goto(base + path, wait_until="load")
        pg.wait_for_timeout(6000)
        if click:
            try:
                pg.click(f"#{click}", timeout=5000)
                pg.wait_for_timeout(1500)
            except Exception as e:
                msgs.append(f"click failed: {str(e)[:120]}")
        body = pg.inner_text("body")[:300].replace("\n", " | ")
        print(f"== {path} status={r.status if r else None} body={body!r}")
        for m in msgs:
            if "favicon" in m or "Hey developer" in m or "DevTools" in m:
                continue
            print("   ", m)
    b.close()

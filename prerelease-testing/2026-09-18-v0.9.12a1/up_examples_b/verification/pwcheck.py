import sys, json
from playwright.sync_api import sync_playwright

base, out = sys.argv[1], sys.argv[2]
paths = sys.argv[3:]
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(f"console[{m.type}] {m.text}") if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errs.append(f"pageerror {e}"))
    for path in paths:
        r = pg.goto(base + path, wait_until="networkidle", timeout=45000)
        pg.wait_for_timeout(1200)
        res[path] = {
            "status": r.status if r else None,
            "url": pg.url,
            "text": " | ".join(pg.inner_text("body").split("\n"))[:300],
        }
        pg.screenshot(path=f"{out}_{path.strip('/').replace('/','_') or 'root'}.png")
    b.close()
res["_console"] = errs
print(json.dumps(res, indent=1))

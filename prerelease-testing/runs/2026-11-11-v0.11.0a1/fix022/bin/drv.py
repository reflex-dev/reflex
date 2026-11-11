"""Load a page, click inc twice, report count/console/ws. usage: drv.py <url> <out.json> [shot.png]"""
import json, sys, time
from playwright.sync_api import sync_playwright

url, out = sys.argv[1], sys.argv[2]
shot = sys.argv[3] if len(sys.argv) > 3 else None
res = {"url": url, "console": [], "ws": [], "failed": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--host-resolver-rules=MAP *.test 127.0.0.1"])
    pg = b.new_page(ignore_https_errors=True)
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text}"[:300]))
    pg.on("websocket", lambda w: res["ws"].append(w.url))
    pg.on("requestfailed", lambda r: res["failed"].append(r.url))
    pg.on("response", lambda r: r.status >= 400 and res["failed"].append(f"{r.status} {r.url}"))
    pg.goto(url)
    pg.wait_for_selector("#inc", timeout=30000)
    time.sleep(3)
    for _ in range(2):
        pg.click("#inc"); time.sleep(1)
    time.sleep(8)
    res["count_text"] = pg.inner_text("#count")
    res["body_tail"] = pg.inner_text("body")[-400:]
    if shot: pg.screenshot(path=shot)
    b.close()
res["ok"] = res["count_text"].replace(" ", "") == "count=2"
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: res[k] for k in ("ok", "count_text")}), "ws_opens=", len(res["ws"]))
for c in res["console"][:6]: print("  console:", c)

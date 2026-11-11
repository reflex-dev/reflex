"""Cross-site attack page in Chromium: a page on evil.test opens raw websockets to the app's event endpoint.
usage: xsite.py <evil_page_url> <out.json> <ws_url>...   Prints which ws URLs opened (101) vs failed."""
import json, sys, time
from playwright.sync_api import sync_playwright

page_url, out, targets = sys.argv[1], sys.argv[2], sys.argv[3:]
res = {"page": page_url, "results": {}, "console": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--host-resolver-rules=MAP *.test 127.0.0.1"])
    pg = b.new_page(ignore_https_errors=True)
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text}"[:300]))
    pg.goto(page_url)
    res["origin"] = pg.evaluate("location.origin")
    for t in targets:
        r = pg.evaluate("""(u) => new Promise(ok => { const w = new WebSocket(u); const to = setTimeout(() => ok('timeout'), 8000);
            w.onopen = () => { clearTimeout(to); w.close(); ok('OPEN'); }; w.onerror = () => { clearTimeout(to); ok('ERROR'); }; })""", t)
        res["results"][t] = r
    b.close()
json.dump(res, open(out, "w"), indent=1)
print("origin", res["origin"], json.dumps(res["results"]))

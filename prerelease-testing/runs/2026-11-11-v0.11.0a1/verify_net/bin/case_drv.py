"""Direct-load /Foo, /foo, /FOO; record rendered #mark and on_load console logs. usage: case_drv.py <base> <out.json>"""
import json, sys, time
from playwright.sync_api import sync_playwright
base, out = sys.argv[1], sys.argv[2]
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for path in ["/Foo", "/foo", "/FOO"]:
        pg = b.new_page(); logs = []
        pg.on("console", lambda m: m.type == "log" and "onload-" in m.text and logs.append(m.text))
        r = pg.goto(base + path)
        try:
            pg.wait_for_selector("#mark", timeout=20000)
            mark = pg.inner_text("#mark")
        except Exception:
            mark = "NO #mark: " + pg.inner_text("body")[:80]
        time.sleep(4)
        res[path] = {"http": r.status if r else None, "mark": mark, "on_load": logs}
        pg.close()
    b.close()
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1))

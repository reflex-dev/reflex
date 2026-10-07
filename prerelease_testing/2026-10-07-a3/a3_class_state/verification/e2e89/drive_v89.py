"""Drive the v89app: fresh context, click everything, read browser storage, reload, open a second tab.

Run: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_v89.py <url> <out.json> <shot-prefix>
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

url, out, shot = sys.argv[1], sys.argv[2], sys.argv[3]
ids = ["opt", "plain", "box-a", "box-b", "box-c"]
res = {"console": []}


def wait_hyd(pg):
    pg.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=90000)
    time.sleep(1)


def read(pg):
    return {i: pg.inner_text(f"#{i}") for i in ids}


def storage(pg):
    return pg.evaluate("() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('v_') || k.includes('v89')).map(k => [k, localStorage.getItem(k)]))")


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.on("console", lambda m: res["console"].append(f"{m.type}: {m.text[:200]}"))
    pg.on("pageerror", lambda e: res["console"].append(f"pageerror: {e}"))
    pg.goto(url)
    wait_hyd(pg)
    res["1_initial"] = read(pg)
    res["1_storage"] = storage(pg)
    pg.click("#set")
    for t in ("a", "b", "c"):
        pg.click(f"#choose-{t}")
        time.sleep(0.7)
    time.sleep(1.5)
    res["2_after_clicks"] = read(pg)
    res["2_storage"] = storage(pg)
    pg.screenshot(path=f"{shot}-after-clicks.png")
    pg.reload()
    wait_hyd(pg)
    res["3_after_reload"] = read(pg)
    res["3_storage"] = storage(pg)
    pg.screenshot(path=f"{shot}-after-reload.png")
    pg2 = ctx.new_page()
    pg2.goto(url)
    wait_hyd(pg2)
    res["4_new_tab"] = read(pg2)
    b.close()

json.dump(res, open(out, "w"), indent=2)
for k, v in res.items():
    if k != "console":
        print(k, v)
print("console errors/warnings:", [c for c in res["console"] if c.startswith(("error", "warning", "pageerror"))])

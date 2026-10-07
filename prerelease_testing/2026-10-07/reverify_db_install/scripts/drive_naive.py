"""Drive naiveapp: load, click Add N times, reload; print status/rows/ages/toasts as JSON.

Usage: NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_naive.py <url> <out_json> <label> [clicks]
Always exits 0; the caller compares the JSON (the point is to record behaviour per version).
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

assert "/scratchpad/envs/driver/" in sys.executable, sys.executable
url, out, label = sys.argv[1:4]
clicks = int(sys.argv[4]) if len(sys.argv) > 4 else 2
res = {"label": label, "toasts": [], "steps": {}, "console_errors": [], "page_errors": []}


def toasts(page):
    for t in page.query_selector_all("[data-sonner-toast]"):
        try:
            txt = t.inner_text().replace("\n", " | ")[:300]
        except Exception:  # noqa: BLE001
            continue
        if txt not in res["toasts"]:
            res["toasts"].append(txt)


def snap(page, name):
    time.sleep(2)
    toasts(page)
    res["steps"][name] = {
        "status": page.inner_text("#status"),
        "rows": [r.inner_text().replace("\n", " | ") for r in page.query_selector_all(".post")],
        "ages": [a.inner_text() for a in page.query_selector_all(".age")],
    }
    print(name, json.dumps(res["steps"][name]), flush=True)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_context(timezone_id="America/New_York").new_page()
    page.on("console", lambda m: res["console_errors"].append(m.text[:300]) if m.type == "error" else None)
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)[:300]))
    page.goto(url)
    page.wait_for_selector("#status", timeout=60000)
    for _ in range(40):
        if page.inner_text("#status") != "idle":
            break
        time.sleep(0.25)
    snap(page, "01_load")
    for i in range(clicks):
        page.click("#add")
        time.sleep(2.5)
        snap(page, f"02_add_{i + 1}")
    page.reload()
    page.wait_for_selector("#status", timeout=60000)
    for _ in range(40):
        if page.inner_text("#status") != "idle":
            break
        time.sleep(0.25)
    snap(page, "03_reload")
    toasts(page)
    page.screenshot(path=out.replace(".json", ".png"))
    b.close()
json.dump(res, open(out, "w"), indent=1)
print("toasts:", res["toasts"])
print("console_errors:", res["console_errors"], "page_errors:", res["page_errors"])

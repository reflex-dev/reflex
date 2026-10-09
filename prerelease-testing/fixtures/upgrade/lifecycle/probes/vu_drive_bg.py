"""verify_upgrade A3-06 driver: click each background-task button, record status + var values, then reload.

Usage: vu_drive_bg.py <frontend_url> <out.json>
Runs under the driver venv (asserted).
"""

import json
import sys
import time

assert ("/envs/" + __import__("os").environ.get("DRIVER", "driver") + "/") in sys.executable, sys.executable

from playwright.sync_api import sync_playwright  # noqa: E402

URL, OUT = sys.argv[1], sys.argv[2]
CASES = [
    "bg_locked_control",
    "bg_write_inherited",
    "bg_write_grandparent_via_mid",
    "bg_write_own",
    "bg_append_inherited",
    "bg_call_inherited_handler",
    "bg_call_own_handler_inherited",
    "bg_call_own_handler_own",
    "bg_locked_control",
]


def values(page):
    return {k: page.inner_text(f"#{k}") for k in ("count", "level2", "own", "items", "status")}


res = {"url": URL, "steps": [], "console": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.on("console", lambda m: res["console"].append(f"{m.type}: {m.text}"[:300]))
    page.goto(URL)
    # wait for hydration: the websocket must be up before clicks count
    page.wait_for_selector("#count")
    time.sleep(3)
    res["initial"] = values(page)
    for case in CASES:
        before = values(page)
        page.click(f"#{case}")
        t0 = time.time()
        while time.time() - t0 < 8:
            st = page.inner_text("#status")
            if st != before["status"] or case == "bg_locked_control" and time.time() - t0 > 2:
                break
            time.sleep(0.1)
        time.sleep(0.8)
        after = values(page)
        res["steps"].append({"case": case, "before": before, "after": after})
        print(f"{case:32s} status={after['status']:45s} count {before['count']}->{after['count']} "
              f"level2 {before['level2']}->{after['level2']} own {before['own']}->{after['own']} "
              f"items {before['items']}->{after['items']}", flush=True)
    page.click("#noop")
    time.sleep(1)
    res["after_noop"] = values(page)
    page.reload()
    page.wait_for_selector("#count")
    time.sleep(3)
    res["after_reload"] = values(page)
    print("after noop  :", res["after_noop"])
    print("after reload:", res["after_reload"])
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
errs = [c for c in res["console"] if c.startswith("error")]
print("console errors:", errs[:5])

"""FINDING-018 acceptance: click to 3, reload with the same token, click once more.

Usage: drive_018.py <base_url> <out.json>
Pass: the reload still shows 3 and the next click shows 4.
Fail: the reload shows 0 and the next click jumps to 4.
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
R = {"base": BASE, "console": [], "pageerrors": [], "ws_recv": 0, "steps": {}}

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = br.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:250]))
    page.on("websocket", lambda ws: ws.on("framereceived", lambda pl: R.__setitem__("ws_recv", R["ws_recv"] + 1)))

    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector("#btn", timeout=45000)
    page.wait_for_timeout(4000)
    R["steps"]["0_initial"] = {"count": page.locator("#btn").inner_text(),
                               "loaded": page.locator("#loaded").inner_text(),
                               "hydrated": page.locator("#hyd").inner_text()}

    for _ in range(3):
        page.click("#btn")
        page.wait_for_timeout(900)
    R["steps"]["1_after_three_clicks"] = {"count": page.locator("#btn").inner_text(),
                                          "loaded": page.locator("#loaded").inner_text(),
                                          "hydrated": page.locator("#hyd").inner_text()}

    page.reload(wait_until="load")
    page.wait_for_selector("#btn", timeout=45000)
    page.wait_for_timeout(5000)
    R["steps"]["2_after_reload"] = {"count": page.locator("#btn").inner_text(),
                                    "loaded": page.locator("#loaded").inner_text(),
                                    "hydrated": page.locator("#hyd").inner_text()}

    page.click("#btn")
    page.wait_for_timeout(1500)
    R["steps"]["3_after_one_more_click"] = {"count": page.locator("#btn").inner_text(),
                                            "loaded": page.locator("#loaded").inner_text(),
                                            "hydrated": page.locator("#hyd").inner_text()}
    R["console_errors"] = [c for c in R["console"] if c["type"] == "error"]
    br.close()

reload_count = R["steps"]["2_after_reload"]["count"]
after = R["steps"]["3_after_one_more_click"]["count"]
R["verdict"] = ("PASS: reload kept the count and the next click incremented it"
                if reload_count == "3" and after == "4"
                else f"FAIL: reload showed {reload_count!r} then a click gave {after!r}")
with open(OUT, "w") as f:
    json.dump(R, f, indent=1)
print(json.dumps(R["steps"], indent=1))
print("VERDICT:", R["verdict"])
print("console errors:", json.dumps(R["console_errors"])[:500])

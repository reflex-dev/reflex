"""Drive the dsc app in Chromium, capturing console/network/errors.

Usage: python drive.py <base_url> <outprefix> [scenario]
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = sys.argv[2]
SCEN = sys.argv[3] if len(sys.argv) > 3 else "full"

events = []


def rec(kind, data):
    events.append({"t": round(time.time(), 3), "kind": kind, "data": data})


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(ignore_https_errors=True)
    page = ctx.new_page()
    page.on("console", lambda m: rec("console", {"type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: rec("pageerror", {"text": str(e)[:600]}))
    page.on("requestfailed", lambda r: rec("reqfail", {"url": r.url, "err": str(r.failure)[:200]}))
    page.on(
        "response",
        lambda r: rec("http", {"url": r.url, "status": r.status}) if r.status >= 400 else None,
    )

    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    rec("heading", page.inner_text("#heading"))
    rec("modules", page.inner_text("#modules"))
    page.screenshot(path=OUT + "_1_index.png")

    if SCEN in ("full", "interact"):
        for _ in range(3):
            page.click("#inc")
            page.wait_for_timeout(180)
        rec("count_after_3", page.inner_text("#count"))
        rec("big", page.inner_text("#big"))
        rec("memo_label", page.inner_text("#memo-label"))
        page.click("#add")
        page.wait_for_timeout(400)
        rec("chained", page.inner_text("#chained"))
        rec("items", page.locator(".item").all_inner_texts())
        page.click("#client-inc")
        page.click("#client-inc")
        page.wait_for_timeout(200)
        rec("client_val", page.inner_text("#client-val"))
        page.click("#cs-btn")
        page.wait_for_timeout(250)
        rec("cs_val", page.inner_text("#cs-val"))
        page.click("#bg")
        page.wait_for_timeout(1800)
        rec("bg_ticks", page.inner_text("#bg-ticks"))
        page.screenshot(path=OUT + "_2_interacted.png")

        # client-side nav
        page.click("#to-other")
        page.wait_for_timeout(900)
        rec("nav_other_heading", page.inner_text("#heading"))
        rec("nav_other_count", page.inner_text("#count"))
        page.click("#to-home")
        page.wait_for_timeout(900)
        rec("nav_home_count", page.inner_text("#count"))
        # direct load of dynamic route
        page.goto(BASE + "/item/xyz", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(800)
        rec("dyn_iid", page.inner_text("#iid"))
        page.screenshot(path=OUT + "_3_dyn.png")
        # reload index, state should be fresh-ish (same session -> preserved)
        page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        rec("after_reload_count", page.inner_text("#count"))

    ctx.close()
    b.close()

with open(OUT + "_events.json", "w") as f:
    json.dump(events, f, indent=1)

errs = [e for e in events if e["kind"] in ("pageerror", "reqfail")] + [
    e for e in events if e["kind"] == "console" and e["data"].get("type") == "error"
]
print("=== RESULTS ===")
for e in events:
    if e["kind"] not in ("console", "http"):
        print(e["kind"], "::", e["data"])
print("=== ERRORS:", len(errs))
for e in errs[:20]:
    print(" ", e["kind"], e["data"])
print("=== HTTP>=400:", sum(1 for e in events if e["kind"] == "http"))
for e in events:
    if e["kind"] == "http":
        print("  ", e["data"])

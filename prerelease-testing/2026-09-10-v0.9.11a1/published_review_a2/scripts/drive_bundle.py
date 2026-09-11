"""FINDING-022 acceptance driver: dynamic component trees and bundling.

Usage: drive_bundle.py <base_url> <out.json>
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, OUT = sys.argv[1], sys.argv[2]
R = {"base": BASE, "steps": [], "console": [], "pageerrors": [], "failed": [], "http_errors": []}


def step(name, **kw):
    """Record a step."""
    R["steps"].append({"step": name, **kw})
    print(f"[{name}] " + json.dumps(kw, default=str)[:400], flush=True)


def icons(page):
    """Which icon is on the page, by id."""
    return {
        "initial-icon": page.locator("#initial-icon").count(),
        "dynamic-icon": page.locator("#dynamic-icon").count(),
        "count": (page.locator("#count").inner_text() if page.locator("#count").count() else None),
    }


with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:300]))
    page.on("requestfailed", lambda r: R["failed"].append({"url": r.url[:200], "err": str(r.failure)[:120]}))
    page.on("response", lambda r: (
        R["http_errors"].append({"url": r.url[:200], "status": r.status}) if r.status >= 400 else None))

    page.goto(BASE, wait_until="domcontentloaded")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(3000)
    step("1_initial_load", **icons(page))

    R["window_reflex_keys_initial"] = page.evaluate(
        "() => Object.keys(window.__reflex || {}).sort()")
    step("1b_window_reflex_keys", count=len(R["window_reflex_keys_initial"]),
         lucide=[k for k in R["window_reflex_keys_initial"] if "lucide" in k])

    page.click("#activate")
    page.wait_for_timeout(2500)
    step("2_after_activate", **icons(page))
    R["window_reflex_keys_after"] = page.evaluate("() => Object.keys(window.__reflex || {}).sort()")
    step("2b_window_reflex_keys", count=len(R["window_reflex_keys_after"]),
         lucide=[k for k in R["window_reflex_keys_after"] if "lucide" in k])

    if page.locator("#inc").count():
        page.click("#inc"); page.wait_for_timeout(900)
        page.click("#inc"); page.wait_for_timeout(900)
        step("3_after_two_increments", **icons(page))
        page.click("#dec"); page.wait_for_timeout(900)
        step("4_after_decrement", **icons(page))
    else:
        step("3_increment_unavailable", reason="no #inc button rendered")

    page.click("#activate")
    page.wait_for_timeout(2000)
    step("5_after_deactivate", **icons(page))
    page.click("#activate")
    page.wait_for_timeout(2000)
    step("6_after_reactivate", **icons(page))

    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector("#ready", timeout=60000, state="attached")
    page.wait_for_timeout(3000)
    step("7_after_reload", **icons(page))
    if page.locator("#inc").count():
        page.click("#inc"); page.wait_for_timeout(900)
        step("8_increment_after_reload", **icons(page))

    R["console_errors"] = [c for c in R["console"] if c["type"] == "error"]
    br.close()

with open(OUT, "w") as f:
    json.dump(R, f, indent=1)
print("\nconsole errors:", json.dumps(R["console_errors"])[:700])
print("page errors:", json.dumps(R["pageerrors"])[:500])
print("failed requests:", json.dumps(R["failed"])[:500])
print("http>=400:", json.dumps(R["http_errors"])[:400])

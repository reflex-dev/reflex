"""Minimal check of the /app/dyn page (hydrate + flip) for marker experiments.

Usage: python dyn_check.py <base> <label>
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
out = {"label": LABEL, "console": [], "bad": []}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.on("console", lambda m: out["console"].append(f"{m.type}: {m.text[:200]}")
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: out["console"].append(f"pageerror: {str(e)[:200]}"))
    page.on("response", lambda r: out["bad"].append((r.url.split("/")[-1], r.status))
            if r.status >= 400 else None)
    page.goto(BASE + "/app/dyn/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(3000)
    out["widget_text"] = page.locator("#dyn-widget").inner_text()
    out["widget_svgs"] = page.locator("#dyn-widget svg").count()
    out["tag"] = page.locator("#dyn-tag").inner_text()
    try:
        page.click("#dyn-flip", timeout=4000)
        page.wait_for_timeout(1500)
        out["after_flip_tag"] = page.locator("#dyn-tag").inner_text()
        out["after_flip_widget"] = page.locator("#dyn-widget").inner_text()
        out["after_flip_class"] = page.locator("#dyn-widget svg").first.get_attribute("class")
    except Exception as e:  # noqa: BLE001
        out["flip_error"] = str(e)[:200]
    page.goto(BASE + "/app/components/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(2000)
    try:
        out["cs_idx"] = page.locator("#cs-idx").inner_text()
    except Exception as e:  # noqa: BLE001
        out["cs_error"] = str(e)[:150]
    b.close()
print(json.dumps(out))

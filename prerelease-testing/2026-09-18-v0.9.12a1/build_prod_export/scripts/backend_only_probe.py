"""Drive the statically served export against a backend-only reflex worker (#7096).

Usage: python backend_only_probe.py <static_base> <label> <out_json>
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, LABEL, OUT = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
res = {"label": LABEL, "base": BASE, "steps": [], "console": [], "bad": [], "ws": []}

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:300]})
            if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: res["console"].append({"type": "pageerror", "text": str(e)[:300]}))
    page.on("response", lambda r: res["bad"].append({"url": r.url, "status": r.status})
            if r.status >= 400 else None)
    page.on("websocket", lambda ws: ws.on(
        "framereceived",
        lambda p: res["ws"].append(str(p)[:600]) if len(res["ws"]) < 25 else None))

    page.goto(BASE + "/app/dyn/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(3000)
    res["steps"].append({
        "step": "dyn_loaded",
        "title": page.title(),
        "widget_text": page.locator("#dyn-widget").inner_text(),
        "widget_svgs": page.locator("#dyn-widget svg").count(),
        "widget_html": page.locator("#dyn-widget").inner_html()[:300],
        "tag": page.locator("#dyn-tag").inner_text(),
        "plain": page.locator("#dyn-plain").inner_text(),
    })
    page.click("#dyn-flip")
    page.wait_for_timeout(1500)
    res["steps"].append({
        "step": "after_flip",
        "widget_text": page.locator("#dyn-widget").inner_text(),
        "widget_svgs": page.locator("#dyn-widget svg").count(),
        "widget_html": page.locator("#dyn-widget").inner_html()[:300],
        "tag": page.locator("#dyn-tag").inner_text(),
    })
    # stateful page (ComponentState) served from the same backend-only worker
    page.goto(BASE + "/app/components/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(2500)
    page.click("#cs-bump")
    page.wait_for_timeout(1200)
    res["steps"].append({
        "step": "components_page",
        "cs_idx": page.locator("#cs-idx").inner_text(),
        "icon_name": page.locator("#icon-name").inner_text(),
        "dyn_icon_svgs": page.locator("#dyn-icon").count(),
    })
    page.goto(BASE + "/app/", wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(2000)
    page.click("#inc")
    page.wait_for_timeout(800)
    page.click("#probe")
    page.wait_for_timeout(1200)
    res["steps"].append({
        "step": "index_page",
        "counter": page.locator("#counter").inner_text(),
        "modules": page.locator("#modules").inner_text(),
    })
    page.screenshot(path=OUT.replace(".json", ".png"), full_page=True)
    ctx.close()
    b.close()

with open(OUT, "w") as f:
    json.dump(res, f, indent=2)
print(json.dumps({k: v for k, v in res.items() if k != "ws"}, indent=2)[:3000])
print("WS frames:", len(res["ws"]))
for w in res["ws"][:6]:
    print("  ", w[:300])

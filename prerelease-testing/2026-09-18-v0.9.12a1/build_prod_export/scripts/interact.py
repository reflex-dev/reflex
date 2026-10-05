"""Interactive end-to-end drive of the bpapp test app.

Usage: python interact.py <base_url> <out_json> <shots_dir> [label]
Covers: state counter, background task, client_state input, module probe,
dynamic icon (rx.icon(tag=Var)), rx.memo card, ComponentState, upload with
non-finite floats, client-side navigation, reload, and JS byte accounting.
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
SHOTS = sys.argv[3]
LABEL = sys.argv[4] if len(sys.argv) > 4 else "run"
os.makedirs(SHOTS, exist_ok=True)

UPLOAD = os.path.join(SHOTS, "payload.txt")
with open(UPLOAD, "w") as f:
    f.write("0123456789")  # 10 bytes -> upload_normal == 10.0

res = {"label": LABEL, "base": BASE, "steps": [], "console": [], "bad": [], "failed": []}


def note(name, **kw):
    res["steps"].append({"step": name, **kw})
    print(name, kw, flush=True)


with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    net = []
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:500]}))
    page.on("pageerror", lambda e: res["console"].append({"type": "pageerror", "text": str(e)[:500]}))
    page.on("requestfailed", lambda r: res["failed"].append({"url": r.url, "err": str(r.failure)}))

    def on_resp(r):
        if r.status >= 400:
            res["bad"].append({"url": r.url, "status": r.status})
        try:
            net.append({"url": r.url, "status": r.status, "type": r.request.resource_type})
        except Exception:  # noqa: BLE001
            pass

    page.on("response", on_resp)

    # --- index page ---
    page.goto(BASE + "/app/", wait_until="networkidle", timeout=60000)
    page.wait_for_selector("#counter", timeout=30000)
    page.wait_for_timeout(1500)
    js_urls = [n["url"] for n in net if n["url"].endswith(".js") and n["status"] < 400]
    note("index_loaded", js_requests=len(js_urls), title=page.title())
    res["index_js_urls"] = js_urls

    page.click("#inc")
    page.click("#inc")
    page.wait_for_timeout(800)
    note("counter", text=page.locator("#counter").inner_text())

    page.click("#bg")
    page.wait_for_timeout(1500)
    note("bg_ticks", text=page.locator("#bgticks").inner_text())

    page.fill("#cs-input", "client-state-typed")
    page.wait_for_timeout(500)
    note("client_state", out=page.locator("#cs-out").inner_text())

    page.click("#probe")
    page.wait_for_timeout(1000)
    note("module_probe", modules=page.locator("#modules").inner_text(),
         n=page.locator("#modules-len").inner_text())
    page.screenshot(path=os.path.join(SHOTS, f"{LABEL}-index.png"))

    # --- client-side nav to components ---
    net_before = len(net)
    page.click("#nav-components")
    page.wait_for_selector("#icon-name", timeout=30000)
    page.wait_for_timeout(2000)
    deferred = [n["url"] for n in net[net_before:] if n["url"].endswith(".js")]
    note("nav_components", url=page.url, deferred_js=len(deferred), icon=page.locator("#icon-name").inner_text())
    res["deferred_js_urls"] = deferred[:40]
    dyn_svg = page.locator("#dyn-icon").count()
    note("dyn_icon_present", count=dyn_svg,
         html=page.locator("#dyn-icon").first.evaluate("e=>e.outerHTML")[:200] if dyn_svg else None)
    page.click("#next-icon")
    page.wait_for_timeout(1200)
    note("dyn_icon_after_click", icon=page.locator("#icon-name").inner_text(),
         html=page.locator("#dyn-icon").first.evaluate("e=>e.outerHTML")[:200] if dyn_svg else None)
    page.click("#cs-bump")
    page.click("#cs-bump")
    page.wait_for_timeout(800)
    note("component_state", idx=page.locator("#cs-idx").inner_text())
    note("memo_cards", n=page.locator("text=memo-a").count() + page.locator("text=memo-b").count())
    note("logo_img_natural", w=page.locator("#logo").evaluate("e=>e.naturalWidth"))
    page.screenshot(path=os.path.join(SHOTS, f"{LABEL}-components.png"))

    # --- about page (markdown + code_block / shiki) ---
    page.click("#nav-about")
    page.wait_for_selector("#pagemark", timeout=30000)
    page.wait_for_timeout(2500)
    body = page.locator("body").inner_text()
    note("about", has_code=("shiki_highlighted" in body), has_md=("Markdown heading" in body),
         shiki_spans=page.locator("pre span").count())
    page.screenshot(path=os.path.join(SHOTS, f"{LABEL}-about.png"))

    # --- assets page + upload non-finite floats ---
    page.click("#nav-assets")
    page.wait_for_selector("#do-upload", timeout=30000)
    page.wait_for_timeout(800)
    page.set_input_files("#up input[type=file]", UPLOAD)
    page.wait_for_timeout(600)
    page.click("#do-upload")
    page.wait_for_timeout(2500)
    note("upload", summary=page.locator("#upload-summary").inner_text(),
         inf=page.locator("#v-inf").inner_text(),
         ninf=page.locator("#v-ninf").inner_text(),
         nan=page.locator("#v-nan").inner_text(),
         normal=page.locator("#v-normal").inner_text())
    page.screenshot(path=os.path.join(SHOTS, f"{LABEL}-upload.png"))

    # --- apple route (frontend_path prefix collision) ---
    page.click("#nav-apple")
    page.wait_for_selector("#pagemark", timeout=30000)
    page.wait_for_timeout(1200)
    note("nav_apple", url=page.url, mark=page.locator("#pagemark").inner_text(),
         counter=page.locator("#counter").inner_text())
    page.click("#inc")
    page.wait_for_timeout(700)
    note("apple_counter_after_inc", counter=page.locator("#counter").inner_text())

    # --- reload on apple (state preserved?) ---
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#counter", timeout=30000)
    page.wait_for_timeout(1500)
    note("apple_after_reload", url=page.url, counter=page.locator("#counter").inner_text(),
         mark=page.locator("#pagemark").inner_text())
    page.screenshot(path=os.path.join(SHOTS, f"{LABEL}-apple.png"))

    # --- dynamic route direct load ---
    page.goto(BASE + "/app/items/7?x=1", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    note("item_direct", url=page.url,
         item_id=page.locator("#item-id").inner_text() if page.locator("#item-id").count() else None,
         path=page.locator("#router-path").inner_text() if page.locator("#router-path").count() else None,
         rurl=page.locator("#router-url").inner_text() if page.locator("#router-url").count() else None)
    page.screenshot(path=os.path.join(SHOTS, f"{LABEL}-item.png"))

    # --- second tab shares nothing / independent state ---
    p2 = ctx.new_page()
    p2.goto(BASE + "/app/", wait_until="networkidle", timeout=60000)
    p2.wait_for_selector("#counter", timeout=30000)
    p2.wait_for_timeout(1200)
    note("second_tab_counter", counter=p2.locator("#counter").inner_text())
    p2.close()

    res["console_errors"] = [c for c in res["console"] if c["type"] in ("error", "pageerror")]
    res["console_warnings"] = [c for c in res["console"] if c["type"] == "warning"]
    ctx.close()
    browser.close()

with open(OUT, "w") as f:
    json.dump(res, f, indent=2)
print("ERRORS:", json.dumps(res["console_errors"], indent=1)[:2000])
print("BAD:", json.dumps(res["bad"], indent=1)[:1500])

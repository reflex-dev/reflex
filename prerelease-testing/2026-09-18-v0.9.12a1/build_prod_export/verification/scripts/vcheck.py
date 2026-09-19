"""Verification probe: asset-prefix (issue 3) + rx.dynamic re-render (issue 2)."""
import json, sys
from playwright.sync_api import sync_playwright

BASE, LABEL, OUT = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
SHOTS = sys.argv[4]
out = {"label": LABEL, "console": [], "bad": [], "requests_logo": [], "ws": []}

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.on("console", lambda m: out["console"].append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: out["console"].append(f"pageerror: {str(e)[:200]}"))
    page.on("response", lambda r: out["bad"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    page.on("request", lambda r: out["requests_logo"].append(r.url) if "logo.svg" in r.url else None)

    # --- issue 3: asset URL under frontend_path ---
    page.goto(BASE + "/app/components/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    out["logo_src_attr"] = page.locator("#logo").get_attribute("src")
    out["logo_natural"] = page.evaluate("() => { const i = document.getElementById('logo'); return {w: i.naturalWidth, h: i.naturalHeight, current: i.currentSrc}; }")
    page.screenshot(path=SHOTS + "-components.png")

    # --- issue 2: rx.dynamic ---
    ws_frames = []
    def on_ws(ws):
        ws.on("framereceived", lambda p: ws_frames.append(p[:600] if isinstance(p, str) else str(p)[:200]))
    page.on("websocket", on_ws)
    page.goto(BASE + "/app/dyn/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    out["dyn_before"] = {
        "widget_text": page.locator("#dyn-widget").inner_text(),
        "svg_class": page.locator("#dyn-widget svg").first.get_attribute("class") if page.locator("#dyn-widget svg").count() else None,
        "tag": page.locator("#dyn-tag").inner_text(),
    }
    page.screenshot(path=SHOTS + "-dyn-before.png")
    ws_frames.clear()
    page.click("#dyn-flip", timeout=8000)
    page.wait_for_timeout(2500)
    out["dyn_after"] = {
        "widget_text": page.locator("#dyn-widget").inner_text(),
        "svg_class": page.locator("#dyn-widget svg").first.get_attribute("class") if page.locator("#dyn-widget svg").count() else None,
        "tag": page.locator("#dyn-tag").inner_text(),
    }
    out["ws"] = [f for f in ws_frames if "dyn" in f or "delta" in f][:6]
    page.screenshot(path=SHOTS + "-dyn-after.png")
    # reload to see whether a fresh render picks it up
    page.reload(wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2500)
    out["dyn_after_reload"] = {
        "widget_text": page.locator("#dyn-widget").inner_text(),
        "svg_class": page.locator("#dyn-widget svg").first.get_attribute("class") if page.locator("#dyn-widget svg").count() else None,
        "tag": page.locator("#dyn-tag").inner_text(),
    }
    b.close()
with open(OUT, "w") as f:
    json.dump(out, f, indent=1)
print(json.dumps(out, indent=1))

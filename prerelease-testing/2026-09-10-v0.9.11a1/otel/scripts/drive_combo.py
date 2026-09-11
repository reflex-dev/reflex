import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
console, errs = [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = b.new_context(); page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL + "/combo", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2500)
    page.click("#one-btn"); page.wait_for_timeout(400)
    page.click("#one-btn"); page.wait_for_timeout(400)
    page.click("#two-btn"); page.wait_for_timeout(500)
    page.click("#btn-add"); page.wait_for_timeout(500)
    page.click("#btn-toggle"); page.wait_for_timeout(500)
    page.click("#btn-setcs"); page.wait_for_timeout(600)
    print("one:", page.text_content("#one-val"), "two:", page.text_content("#two-val"))
    print("cond:", page.text_content("#cond"))
    print("cs:", page.text_content("#cs-value"))
    print("rows:", page.locator(".row").count())
    page.screenshot(path=str(OUT / "combo.png"))
    ctx.close(); b.close()
(OUT / "console.json").write_text(json.dumps(console, indent=1))
print("errors/warnings:", [c for c in console if c["type"] in ("error", "warning")])
print("pageerrors:", errs)

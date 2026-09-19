"""Persistent-profile probe: keep the same client token across a reflex upgrade.

usage: persist_probe.py <url> <phase:write|read> <profiledir> <outdir>
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

url, phase, profile, outdir = sys.argv[1:5]
inject = sys.argv[5] if len(sys.argv) > 5 else None
out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
rec = {"phase": phase}
console, errs = [], []
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        profile, executable_path="/opt/pw-browsers/chromium",
        viewport={"width": 1100, "height": 900})
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    if inject:
        page.add_init_script("try { window.sessionStorage.setItem('token', %r); } catch (e) {}" % inject)
    page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(url, timeout=90000)
    page.wait_for_selector("input[name=new_item]", timeout=60000)
    page.wait_for_timeout(2000)
    rec["items_on_load"] = page.locator("li").all_inner_texts()
    rec["token"] = page.evaluate("() => window.sessionStorage.getItem('token')")
    if phase == "write":
        for it in ["OLDSTATE-alpha", "OLDSTATE-beta"]:
            page.fill("input[name=new_item]", it)
            page.press("input[name=new_item]", "Enter")
            page.wait_for_timeout(500)
        rec["items_after_write"] = page.locator("li").all_inner_texts()
    else:
        # exercise an event against the restored old state
        page.fill("input[name=new_item]", "NEWSTATE-gamma")
        page.press("input[name=new_item]", "Enter")
        page.wait_for_timeout(900)
        rec["items_after_event"] = page.locator("li").all_inner_texts()
        page.locator("li button").first.click()
        page.wait_for_timeout(700)
        rec["items_after_delete"] = page.locator("li").all_inner_texts()
    page.screenshot(path=str(out / f"todo-persist-{phase}.png"))
    ctx.close()
rec["console"] = console
rec["page_errors"] = errs
(out / f"todo-persist-{phase}.json").write_text(json.dumps(rec, indent=2))
print(json.dumps(rec, indent=2))

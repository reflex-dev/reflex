"""Drive refsnoid (buttons without ids). Usage: drive_refsnoid.py <fe> [shot.png]"""
import sys, time, json
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
out = {"errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append("pageerror: " + str(e)[:120]))
    pg.goto(base + "/"); pg.wait_for_selector("text=refs noid"); time.sleep(1.5)
    pg.get_by_text("raw var handler").click(); time.sleep(0.5)
    out["raw_handler_value"] = pg.eval_on_selector("#target", "e => e.value")
    pg.fill("#target", "typed"); pg.get_by_text("call_function").click(); time.sleep(1)
    out["call_function_log"] = pg.inner_text(".log")
    pg.goto(base + "/hook"); time.sleep(3)
    out["hook_value"] = pg.eval_on_selector("#target", "e => e.value") if pg.locator("#target").count() else None
    out["hook_page_text"] = pg.inner_text("body")[:100]
    if len(sys.argv) > 2: pg.screenshot(path=sys.argv[2])
    b.close()
print(json.dumps(out, indent=1))

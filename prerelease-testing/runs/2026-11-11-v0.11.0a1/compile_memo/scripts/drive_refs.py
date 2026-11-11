"""Drive refsrepro: prints raw/callfn/hook results and page errors. Usage: drive_refs.py http://localhost:3300"""
import sys, time, json
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
out = {"errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(str(e)[:200]))
    pg.on("console", lambda m: out["errors"].append("console." + m.type + ": " + m.text[:200]) if m.type == "error" and "404" not in m.text else None)
    pg.goto(base + "/"); pg.wait_for_selector("#h"); time.sleep(1.5)
    pg.click("#raw"); time.sleep(0.5)
    out["raw_handler_value"] = pg.eval_on_selector("#target", "e => e.value")
    pg.fill("#target", "typed"); pg.click("#callfn"); time.sleep(1)
    out["call_function_log"] = pg.inner_text("#log")
    pg.goto(base + "/hook"); time.sleep(3)
    out["hook_page_heading_visible"] = pg.locator("#h2").count() > 0
    out["hook_value"] = pg.eval_on_selector("#target", "e => e.value") if pg.locator("#target").count() else None
    out["hook_page_text"] = pg.inner_text("body")[:150]
    pg.screenshot(path=sys.argv[2]) if len(sys.argv) > 2 else None
    b.close()
print(json.dumps(out, indent=1))

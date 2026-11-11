"""Drive refsrepro: prints raw/callfn/hook/memo/decl results and page errors. Usage: drive_refs.py http://localhost:3300 [shot_prefix]"""
import sys, time, json
from playwright.sync_api import sync_playwright
base = sys.argv[1].rstrip("/")
shot = sys.argv[2] if len(sys.argv) > 2 else None
out = {"errors": []}
cur = {"page": "/"}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(cur["page"] + " pageerror: " + str(e)[:200]))
    pg.on("console", lambda m: out["errors"].append(cur["page"] + " console." + m.type + ": " + m.text[:200]) if m.type in ("error", "warning") and "404" not in m.text else None)
    pg.on("response", lambda r: out["errors"].append(f"{cur['page']} HTTP {r.status} {r.url}") if r.status >= 400 and "favicon" not in r.url else None)
    pg.goto(base + "/"); pg.wait_for_selector("#h", timeout=60000); time.sleep(1.5)
    pg.click("#raw"); time.sleep(0.5)
    out["raw_handler_value"] = pg.eval_on_selector("#target", "e => e.value")
    pg.fill("#target", "typed"); pg.click("#callfn"); time.sleep(1)
    out["call_function_log"] = pg.inner_text("#log")
    for path, key in (("/hook", "hook"), ("/memo", "memo"), ("/decl", "decl")):
        cur["page"] = path
        pg.goto(base + path); time.sleep(3)
        out[key + "_value"] = pg.eval_on_selector("#target", "e => e.value") if pg.locator("#target").count() else None
        out[key + "_text"] = pg.inner_text("body")[:150].replace("\n", " | ")
        if shot:
            pg.screenshot(path=f"{shot}_{key}.png")
    b.close()
print(json.dumps(out, indent=1))

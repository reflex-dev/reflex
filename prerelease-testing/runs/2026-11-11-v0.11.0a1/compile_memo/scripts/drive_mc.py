"""/memocond + /loopnokey. Usage: drive_mc.py <fe>"""
import sys, time, json
from playwright.sync_api import sync_playwright
fe = sys.argv[1].rstrip("/")
out = {"errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(str(e)[:200]))
    pg.on("console", lambda m: out["errors"].append(m.text[:200]) if m.type == "error" and "404" not in m.text else None)
    pg.goto(fe + "/memocond"); pg.wait_for_selector("#page-memocond"); time.sleep(1.5)
    pg.click("#clear-log"); time.sleep(0.5)
    pg.reload(); pg.wait_for_selector("#page-memocond"); time.sleep(2)
    out["mc_initial"] = {"shown": [e.inner_text() for e in pg.locator(".mc-shown").all()], "branch": pg.inner_text("#branch")}
    pg.click("#toggle"); time.sleep(1)
    out["mc_after_toggle"] = {"shown": [e.inner_text() for e in pg.locator(".mc-shown").all()], "branch": pg.inner_text("#branch")}
    pg.click("#toggle"); time.sleep(1)
    pg.click("#clear-log"); time.sleep(0.5)
    print("MC", json.dumps(out)); sys.stdout.flush()
    pg.goto(fe + "/loopnokey")
    try:
        pg.wait_for_selector("#page-loopnokey", timeout=15000)
    except Exception:
        out["nk"] = "PAGE DID NOT RENDER: " + pg.inner_text("body")[:120]
        b.close(); print(json.dumps(out, indent=1)); sys.exit()
    time.sleep(2)
    out["nk_initial"] = {"items": [e.inner_text() for e in pg.locator(".loop-item").all()], "m": pg.inner_text("#mounted"), "u": pg.inner_text("#unmounted")}
    pg.click("#clear-log"); time.sleep(0.5)
    pg.click("#rm-first"); time.sleep(1)
    out["nk_after_remove_first"] = {"items": [e.inner_text() for e in pg.locator(".loop-item").all()], "m": pg.inner_text("#mounted"), "u": pg.inner_text("#unmounted")}
    b.close()
print(json.dumps(out, indent=1))

"""/rows: per-row client_state in @rx.memo rows inside foreach + on_mount. Usage: drive_rows.py <fe>"""
import sys, time, json
from playwright.sync_api import sync_playwright
fe = sys.argv[1].rstrip("/")
out = {"errors": []}
def snap(pg):
    return {"names": [e.inner_text() for e in pg.locator(".mr-name").all()], "open": [e.inner_text() for e in pg.locator(".mr-open").all()],
            "mounted": pg.inner_text("#mounted"), "unmounted": pg.inner_text("#unmounted")}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(str(e)[:200]))
    pg.on("console", lambda m: out["errors"].append(m.text[:200]) if m.type == "error" and "404" not in m.text else None)
    pg.goto(fe + "/"); pg.wait_for_selector("#page-home"); time.sleep(1.5)
    pg.click("#clear-log"); time.sleep(0.5)
    pg.click("#nav-rows") if pg.locator("#nav-rows").count() else pg.goto(fe + "/rows")
    pg.wait_for_selector("#page-rows"); time.sleep(1.5)
    out["initial"] = snap(pg)
    pg.locator(".mr-toggle").nth(1).click(); time.sleep(0.6)
    out["after_toggle_row1(beta)"] = snap(pg)
    pg.click("#clear-log"); time.sleep(0.4)
    pg.click("#reverse"); time.sleep(0.8)
    out["after_reverse"] = snap(pg)
    pg.click("#clear-log"); time.sleep(0.4)
    pg.click("#rm-first"); time.sleep(0.8)
    out["after_rm_first"] = snap(pg)
    pg.click("#clear-log"); time.sleep(0.4)
    pg.click("#add"); time.sleep(0.8)
    out["after_add"] = snap(pg)
    b.close()
print(json.dumps(out, indent=1))

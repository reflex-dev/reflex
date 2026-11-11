"""/typing: fast typing into controlled inputs. Usage: drive_typing.py <fe>"""
import sys, time, json
from playwright.sync_api import sync_playwright
fe = sys.argv[1].rstrip("/")
out = {"errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(str(e)[:200]))
    pg.on("console", lambda m: out["errors"].append(m.text[:200]) if m.type == "error" and "404" not in m.text else None)
    pg.goto(fe + "/typing"); pg.wait_for_selector("#page-typing"); time.sleep(2)
    msg = "the quick brown fox jumps over"
    for sel in ["#ta", "#tb", "#tc"]:
        pg.click(sel); pg.keyboard.type(msg, delay=5)
    time.sleep(1.5)
    out["values"] = {s: pg.eval_on_selector(s, "e => e.value") for s in ["#ta", "#tb", "#tc", "#tarea"]}
    out["state"] = pg.inner_text("#tout")
    pg.fill("#ta", ""); pg.keyboard.type("zzz", delay=5); time.sleep(1)
    out["cond_removed"] = pg.locator("#tc").count() == 0
    b.close()
print(json.dumps(out))

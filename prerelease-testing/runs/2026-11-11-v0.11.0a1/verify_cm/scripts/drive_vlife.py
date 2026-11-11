"""Drive vlife. Usage: drive_vlife.py <fe> <out.json> [shotprefix]"""
import json, sys, time
from playwright.sync_api import sync_playwright

fe = sys.argv[1].rstrip("/")
out = {"errors": [], "console_warn_err": []}


def ev(pg):
    return pg.inner_text("#events")


def wait_ws(pg):
    pg.wait_for_selector("#page"); time.sleep(2)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["errors"].append(f"{pg.url}: {str(e)[:150]}"))
    pg.on("console", lambda m: out["console_warn_err"].append(f"{m.type}: {m.text[:150]}") if m.type in ("error", "warning") and "404" not in m.text else None)
    for route in ("nokey", "withkey"):
        pg.goto(fe + "/" + route); wait_ws(pg)
        if pg.locator("#reset").count() == 0:
            out[route] = "PAGE DID NOT RENDER: " + pg.inner_text("body")[:160]
            continue
        pg.click("#reset"); time.sleep(0.7); pg.click("#clear"); time.sleep(0.7)
        pg.click("#rm-first"); time.sleep(1.2)
        out[route] = {"rows": [e.inner_text() for e in pg.locator(".row").all()], "events_after_remove_first": ev(pg)}
        pg.click("#reset"); time.sleep(0.7)
    for route in ("memocond", "pagecond"):
        pg.goto(fe + "/"); wait_ws(pg)
        # make flag True and clear the log before loading the page under test
        pg.goto(fe + "/" + route); wait_ws(pg)
        if pg.inner_text("#flag").strip() != "flag=true":
            pg.click("#toggle"); time.sleep(0.7)
        pg.click("#clear"); time.sleep(0.7)
        pg.reload(); wait_ws(pg)
        r = {"initial_shown": [e.inner_text() for e in pg.locator(".shown").all()], "initial_events": ev(pg)}
        pg.click("#clear"); time.sleep(0.7)
        pg.click("#toggle"); time.sleep(1.2)
        r["after_toggle_shown"] = [e.inner_text() for e in pg.locator(".shown").all()]
        r["after_toggle_events"] = ev(pg)
        pg.click("#toggle"); time.sleep(1.2)
        r["after_toggle2_events"] = ev(pg)
        out[route] = r
    pg.goto(fe + "/icons"); wait_ws(pg); time.sleep(1)
    def svg(sel):
        return pg.locator(sel + " svg").count()
    out["icons"] = {"var": svg("#icn-var"), "static": svg("#icn-static"),
                    "loop": {e.get_attribute("data-name"): e.locator("svg").count() for e in pg.locator(".icn-loop").all()}}
    pg.click("#g3"); time.sleep(1)
    out["icons"]["var_after_g3"] = svg("#icn-var")
    if len(sys.argv) > 3:
        pg.screenshot(path=sys.argv[3] + "_icons.png")
    b.close()
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(json.dumps(out, indent=1))

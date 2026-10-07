"""Drive the guide app. Usage: drive_guide.py <base_url> <outdir> <tag> [--defaults-tabs N]"""

import sys
import time

from harness import Run, guard_driver_python, wait_for
from playwright.sync_api import sync_playwright

guard_driver_python()
base, outdir, tag = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
ntabs = int(sys.argv[sys.argv.index("--defaults-tabs") + 1]) if "--defaults-tabs" in sys.argv else 4
run = Run(tag, outdir)


def txt(page, sel):
    try:
        return page.locator(sel).first.inner_text(timeout=2000).strip()
    except Exception:  # noqa: BLE001
        return None


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    page = ctx.new_page()
    run.attach(page)
    page.goto(base + "/portable")
    ver = wait_for(lambda: txt(page, "#ver"), 30)
    run.notes["version"] = ver
    body = page.inner_text("body")
    run.check("/portable: get_fields()['_items'].default_value() + ClassVar render", all(s in body for s in ("a\n", "b\n", "https://example.com/api")), body[:200])
    resp = page.goto(base + "/sample")
    if resp is not None and resp.status == 200 and "0.10" in (ver or ""):
        time.sleep(1.5)
        body = page.inner_text("body")
        run.check("/sample: guide sample 1 verbatim renders a, b and the ClassVar", all(s in body for s in ("a\n", "b\n", "https://example.com/api")), body[:200])
        run.shot(page, "sample")
    else:
        run.check("/sample: not registered on 0.9 (default_value() missing)", "skipped", f"status {resp.status if resp else None}")
    page.goto(base + "/bg")
    wait_for(lambda: txt(page, "#c2count") is not None, 30)
    time.sleep(1.5)

    def click_and_read(btn, expect_change_of=None, wait=3.0):
        before = txt(page, "#result")
        page.click(btn)
        time.sleep(wait)
        page.click("#b_refresh")
        time.sleep(0.8)
        return {"result": txt(page, "#result"), "c2": txt(page, "#c2count"), "c1": txt(page, "#c1count"), "c3": txt(page, "#c3count"), "p": txt(page, "#pcount"), "before": before}

    r = click_and_read("#b_verbatim")
    run.check("guide verbatim Child.work (self.bump() outside the lock)", "pass", r)
    run.notes["verbatim"] = r
    r = click_and_read("#b_fix")
    run.check("guide verbatim fix Child3.work (async with self: self.bump()) increments", r["c3"] == "1", r)
    for name, btn in [("outside", "#b_outside"), ("inside", "#b_inside"), ("readonly", "#b_readonly"), ("type", "#b_type"), ("own_outside", "#b_own")]:
        r = click_and_read(btn)
        run.notes[name] = r
        run.check(f"bg {name}", "pass", r)
    run.shot(page, "bg")
    # runtime default assignment
    page.goto(base + "/defaults")
    wait_for(lambda: txt(page, "#level") is not None, 30)
    time.sleep(1)
    page.click("#b_reconf")
    time.sleep(1.5)
    a_level, a_pid = txt(page, "#level"), txt(page, "#pid")
    seen = []
    for i in range(ntabs):
        c2 = b.new_context()
        p2 = c2.new_page()
        run.attach(p2, f"tab{i}")
        p2.goto(base + "/defaults")
        wait_for(lambda: txt(p2, "#level") is not None, 30)
        time.sleep(1.0)
        p2.click("#b_whoami")
        time.sleep(1.0)
        seen.append((txt(p2, "#level"), txt(p2, "#pid")))
        c2.close()
    run.notes["defaults"] = {"tabA": (a_level, a_pid), "new_tabs": seen}
    run.check("runtime type(self).level = 77: new sessions (level, worker pid)", "pass", {"tabA": (a_level, a_pid), "new_tabs": seen})
    run.shot(page, "defaults")
    b.close()
sys.exit(run.finish())

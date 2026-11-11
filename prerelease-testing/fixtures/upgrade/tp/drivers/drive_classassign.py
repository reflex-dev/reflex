"""F-004 e2e: a package assigns a declared backend var on the CLASS at import (ConstState._CACHE = ...).

Does the instance keep reading the assigned value after the state manager serialises it (disk: debounce ~2 s;
redis: on every update)?  tp_patterns /classattr page.

Usage: drive_classassign.py <base_url> <out_json> <label>
"""
import json
import sys

from tpdrive import Capture, browser, wait_text

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
LABEL = sys.argv[3]
cap = Capture()
res = {}
with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")
    page.goto(BASE + "/classattr", wait_until="networkidle")
    wait_text(page, "#classattr", "class-level")
    page.click("#show_instance")
    res["shown_1"] = wait_text(page, "#shown", r"shown=\S")
    page.wait_for_timeout(4500)  # past the disk manager debounce / redis write
    page.click("#show_instance")
    page.wait_for_timeout(1200)
    res["shown_2_after_4.5s"] = page.locator("#shown").inner_text()
    # second tab = second client token = fresh state instance
    p2 = cap.attach(ctx.new_page(), "tab2")
    ctx2 = b.new_context()
    p3 = cap.attach(ctx2.new_page(), "ctx2")
    p3.goto(BASE + "/classattr", wait_until="networkidle")
    wait_text(p3, "#classattr", "class-level")
    p3.click("#show_instance")
    res["shown_new_client"] = wait_text(p3, "#shown", r"shown=\S")
    p3.wait_for_timeout(4500)
    p3.click("#show_instance")
    p3.wait_for_timeout(1200)
    res["shown_new_client_after_4.5s"] = p3.locator("#shown").inner_text()
    res["classattr_report"] = page.locator("#classattr").inner_text()[:300]
    res["from_const"] = page.locator("#from_const").inner_text()[:200]
want = "cache='configured-at-import'"
for k in ("shown_1", "shown_2_after_4.5s", "shown_new_client", "shown_new_client_after_4.5s"):
    cap.check(f"F-004 {k} keeps class-assigned backend default", want in res[k], res[k])
print(json.dumps(res, indent=1))
cap.dump(OUT, {"results": res, "label": LABEL})

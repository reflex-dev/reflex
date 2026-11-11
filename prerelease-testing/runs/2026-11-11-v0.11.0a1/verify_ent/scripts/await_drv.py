"""PASS re-check (#7782): anonymous `await Vault.secret_action()` from a public handler.

Usage: await_drv.py <frontend url> <label>
Expect (anonymous): result "None", ran stays 0, browser sent to /login; direct protected click also does not run.
"""

import json
import sys

import playwright
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__
U, L = sys.argv[1].rstrip("/"), sys.argv[2]
out = {"console_errors": [], "page_errors": [], "urls": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: out["console_errors"].append(m.text[:200]) if m.type == "error" else None)
    pg.on("pageerror", lambda e: out["page_errors"].append(str(e)[:300]))
    pg.on("framenavigated", lambda f: out["urls"].append(f.url) if f == pg.main_frame else None)
    pg.goto(U + "/await")
    pg.wait_for_selector("#result", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.click("#call")
    pg.wait_for_timeout(3000)
    out["url_after_call"] = pg.url
    # come back and read the state
    pg.goto(U + "/await")
    pg.wait_for_selector("#result", timeout=60000)
    pg.wait_for_timeout(1500)
    out["result_after_call"] = pg.locator("#result").inner_text()
    pg.click("#readran")
    pg.wait_for_timeout(1000)
    out["ran_after_call"] = pg.locator("#ran").inner_text()
    pg.click("#direct")
    pg.wait_for_timeout(3000)
    out["url_after_direct"] = pg.url
    pg.goto(U + "/await")
    pg.wait_for_selector("#result", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.click("#readran")
    pg.wait_for_timeout(1000)
    out["ran_after_direct"] = pg.locator("#ran").inner_text()
    pg.click("#public")
    pg.wait_for_timeout(1500)
    out["control_public_result"] = pg.locator("#result").inner_text()
    b.close()
ok = out["control_public_result"] == "'public-value'" and out["ran_after_call"] == "0" and out["ran_after_direct"] == "0" and out["result_after_call"] in ("unset", "None")
print("[PASS]" if ok else "[FAIL]", L, json.dumps(out)[:2000])

"""drive_noinit.py <base_url> <out.json> [label]: STATE-36 / #7304 check on the noinit app (package without __init__.py).

Driver venv. Loads /, waits for hydration, expects on_load text, clicks inc twice (count: 2), clicks note ("note 2"),
reloads and expects count kept; captures console errors (the registry symptom is
"Cannot process state update: no dispatch function for substate(s) ...").
"""

import json
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

assert ("/envs/" + os.environ.get("DRIVER", "driver") + "/") in sys.executable, sys.executable
base, out = sys.argv[1].rstrip("/"), sys.argv[2]
label = sys.argv[3] if len(sys.argv) > 3 else "noinit"
checks = []
console = []


def check(name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + (f": {detail}" if detail else ""))


def wait_text(page, sel, pred, timeout=20.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        t = page.locator(sel).inner_text()
        if pred(t):
            return t
        time.sleep(0.15)
    return page.locator(sel).inner_text()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda ex: console.append(f"pageerror: {ex}"))
    page.goto(base + "/", wait_until="load")
    t = wait_text(page, "#hyd", lambda s: "yes" in s, 30)
    check("hydrated", "yes" in t, t)
    t = wait_text(page, "#loaded", lambda s: "loaded pid=" in s, 15)
    check("on_load_delta_rendered", "loaded pid=" in t, t)
    page.click("#inc")
    page.click("#inc")
    t = wait_text(page, "#count", lambda s: "count: 2" in s, 15)
    check("click_updates_state", "count: 2" in t, t)
    page.click("#notebtn")
    t = wait_text(page, "#note", lambda s: "note 2" in s, 15)
    check("substate_handler", "note 2" in t, t)
    page.reload(wait_until="load")
    t = wait_text(page, "#count", lambda s: "count: 2" in s, 20)
    check("reload_keeps_state", "count: 2" in t, t)
    bad = [c for c in console if not re.search(r"Hey developer|HydrateFallback|\[vite\]|React DevTools|favicon|Failed to load resource.*404", c)]
    check("console_clean", not bad, " | ".join(bad)[:400])
    check("no_dispatch_error_absent", not any("no dispatch function" in c for c in console), "")
    browser.close()
res = {"label": label, "checks": checks, "console": console, "pass": sum(c["ok"] for c in checks), "fail": sum(not c["ok"] for c in checks)}
json.dump(res, open(out, "w"), indent=1)
print(f"== {label}: pass={res['pass']} fail={res['fail']}")

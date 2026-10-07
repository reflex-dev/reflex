"""Drive the n024doc app: one click per docs claim, record outcomes. Usage: drive_n024.py BASE OUT_JSON SERVER_LOG"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

base, out, log = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
res = {"steps": {}, "console": [], "page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_page()
    page.on("console", lambda m: m.type in ("error", "warning") and res["console"].append(f"{m.type}: {m.text[:300]}"))
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)[:300]))
    page.goto(base + "/", wait_until="networkidle", timeout=180000)
    page.wait_for_function("() => (document.querySelector('#token')?.textContent || '').length > 10", timeout=120000)
    page.click("#btn-reset_all")
    page.wait_for_timeout(1500)

    def snap():
        page.click("#btn-refresh")
        page.wait_for_timeout(700)
        t = lambda i: page.locator(f"#{i}").inner_text()
        return {"count": t("count"), "exc": t("exc"), "seen": t("seen"), "results": json.loads(t("results") or "{}")}

    for btn in ["work", "work_locked", "outside_modify", "outside_readonly", "outside_own_handler",
                "inside_describe", "fg_describe", "own_bg_outside",
                "oc-write_own", "oc-append_own", "oc-write_inherited", "oc-own_write", "oc-read_own", "oc-bump", "oc-peek", "dw-own", "dw-inherited", "dw-inherited_list"]:
        page.click(f"#btn-{btn}")
        page.wait_for_timeout(2500)
        res["steps"][btn] = snap()
    page.reload(wait_until="networkidle")
    page.wait_for_function("() => (document.querySelector('#token')?.textContent || '').length > 10", timeout=120000)
    page.wait_for_timeout(1500)
    res["after_reload"] = snap()
    b.close()
txt = open(log, errors="replace").read()
res["server_backend_exc"] = re.findall(r"N024_BACKEND_EXC [^\n]{0,200}", txt)
res["server_peek"] = re.findall(r"N024 [\d.]+ peek [^\n]{0,200}", txt)
res["server_tracebacks"] = txt.count("Traceback")
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1)[:6000])

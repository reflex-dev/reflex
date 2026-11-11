"""Drive classattr_app in Chromium: claim A (class constants in the UI) and claim B (class-assigned backend var).

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_classattr.py <url> <outdir> <label>
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

url, outdir, label = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
outdir.mkdir(parents=True, exist_ok=True)
console, bad, res = [], [], {}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}"))
    page.on("requestfailed", lambda r: bad.append(f"FAILED {r.url} {r.failure}"))
    page.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(url, wait_until="networkidle", timeout=120000)
    page.wait_for_selector("#shown", state="attached", timeout=60000)
    res["fstring_label"] = page.inner_text("#fstring_label")
    res["cs_btn_label"] = page.inner_text("#cs_btn")
    page.click("#cs_btn")
    page.wait_for_function("document.querySelector('#cs_count').innerText.trim() !== '0'", timeout=30000)
    res["cs_count_after_click"] = page.inner_text("#cs_count")

    def step(name, btn, wait=1.5):
        page.click(btn)
        time.sleep(wait)
        res[name] = {"shown": page.inner_text("#shown"), "log": page.inner_text("#log")}

    step("1_show", "#show")
    time.sleep(3.5)  # longer than the 2 s disk-manager debounce
    step("2_show_after_3.5s", "#show")
    step("3_set_instance", "#set_instance")
    step("4_show", "#show")
    step("5_reset", "#reset")
    step("6_show", "#show")
    page.reload(wait_until="networkidle")
    page.wait_for_selector("#shown", state="attached")
    time.sleep(2)
    res["7_after_reload"] = {"shown": page.inner_text("#shown"), "log": page.inner_text("#log")}
    page.screenshot(path=str(outdir / f"{label}.png"), full_page=True)
    browser.close()
res["console"] = console
res["bad_responses"] = bad
(outdir / f"{label}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))

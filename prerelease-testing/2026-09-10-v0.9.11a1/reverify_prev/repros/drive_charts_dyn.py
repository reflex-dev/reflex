"""Drive the /charts (FINDING-020) and /dyn (FINDING-017) pages of rvapp.

Usage: python drive_charts_dyn.py <base_url> <shots_dir>

/charts: rx.plotly(..., id="the-plot") plus a control rx.box(id="control-box").
         Reports whether the id reaches the DOM, whether any element carries
         divId/id, and whether the plot actually rendered (.js-plotly-plot).
/dyn:    bundle_library("lucide-react") at module scope + a computed
         rx.Component var containing rx.icon("apple"); reports console errors
         ("Failed to resolve module specifier"), whether the dynamic block
         rendered, and whether window.__reflex carries lucide-react.
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = sys.argv[2]
os.makedirs(SHOTS, exist_ok=True)

out: dict = {}
console: list[str] = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    page.on("console", lambda m: console.append(f"{m.type}:{m.text}"))
    page.on("pageerror", lambda e: console.append(f"pageerror:{e}"))
    failed: list[str] = []
    page.on("requestfailed", lambda r: failed.append(f"{r.url} {r.failure}"))
    bad_status: list[str] = []
    page.on(
        "response",
        lambda r: bad_status.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )

    # ---------------- /charts
    page.goto(BASE + "/charts", wait_until="load", timeout=90000)
    page.wait_for_selector("#hd", timeout=60000)
    page.wait_for_timeout(4000)
    out["charts_control_box_present"] = page.evaluate(
        "!!document.getElementById('control-box')"
    )
    out["charts_the_plot_by_id"] = page.evaluate(
        "!!document.getElementById('the-plot')"
    )
    out["charts_plotly_rendered"] = page.evaluate(
        "document.querySelectorAll('.js-plotly-plot').length"
    )
    out["charts_any_divid_attr"] = page.evaluate(
        "document.querySelectorAll('[divid]').length"
    )
    out["charts_plot_container_ids"] = page.evaluate(
        "Array.from(document.querySelectorAll('.js-plotly-plot')).map(e => e.id)"
    )
    page.screenshot(path=f"{SHOTS}/charts_before_bump.png")
    page.click("#btn-bump")
    page.wait_for_timeout(2000)
    out["charts_the_plot_by_id_after_bump"] = page.evaluate(
        "!!document.getElementById('the-plot')"
    )
    page.screenshot(path=f"{SHOTS}/charts_after_bump.png")

    # ---------------- /dyn
    console_before = len(console)
    page.goto(BASE + "/dyn", wait_until="load", timeout=90000)
    page.wait_for_selector("#hd", timeout=60000)
    page.wait_for_timeout(4000)
    out["dyn_static_icon"] = page.evaluate("!!document.getElementById('static-icon')")
    out["dyn_icon_rendered"] = page.evaluate("!!document.getElementById('dyn-icon')")
    out["dyn_label_text"] = page.evaluate(
        "document.getElementById('dyn-label') ? document.getElementById('dyn-label').innerText : null"
    )
    out["dyn_window_reflex_keys"] = page.evaluate(
        "window.__reflex ? Object.keys(window.__reflex) : null"
    )
    page.screenshot(path=f"{SHOTS}/dyn_initial.png")
    page.click("#btn-relabel")
    page.wait_for_timeout(2000)
    out["dyn_label_after_click"] = page.evaluate(
        "document.getElementById('dyn-label') ? document.getElementById('dyn-label').innerText : null"
    )
    page.screenshot(path=f"{SHOTS}/dyn_after_click.png")
    out["dyn_console_new"] = console[console_before:]

    out["console_all"] = console
    out["failed_requests"] = failed
    out["bad_status"] = bad_status
    browser.close()

for k, v in out.items():
    if k in ("console_all", "dyn_console_new"):
        continue
    print(f"RESULT {k}: {v}")
print("MODULE_SPECIFIER_ERRORS:", sum("resolve module specifier" in c for c in console))
print("JSON:" + json.dumps(out)[:12000])

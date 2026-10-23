"""Dev hot reload: with `reflex run` (dev) serving the app, load a page, then add a
frontend var to the state source and check the page settles without a stale-schema
loop (no reload, bounded number of mismatch warnings, new var rendered).

Usage: t_dev_hotreload.py <frontend_url> <app_source_file> <report.json> <shots_prefix>
"""
import sys
import time
from pathlib import Path

from pwlib import Capture, browser, sync_playwright

url, src, report, shots = sys.argv[1:5]
src = Path(src)
original = src.read_text()
MARK = "    sub_text: str = \"sub\"\n"
assert MARK in original
results = {}
with sync_playwright() as p:
    b = browser(p)
    page = b.new_page()
    cap = Capture(page)
    page.goto(url)
    page.wait_for_selector("#inc")
    page.click("#inc")
    page.wait_for_selector("#count:has-text('count: 1')", timeout=20000)
    results["schema_before"] = page.evaluate("() => fetch('/utils/context.jsx').then(r => r.text()).then(t => (t.match(/stateSchema = \"([0-9a-f]+)\"/) || [])[1]).catch(e => String(e))")
    n_console = len(cap.console)
    t_edit = time.time()
    # add a frontend var and render it on the index page
    edited = original.replace(MARK, MARK + "    hot_var: str = \"hot-added\"\n")
    edited = edited.replace('rx.text(Sub.sub_text, id="sub"),', 'rx.text(Sub.sub_text, id="sub"),\n        rx.text(Sub.hot_var, id="hot"),')
    src.write_text(edited)
    try:
        appeared = None
        for _ in range(60):
            page.wait_for_timeout(1000)
            if page.locator("#hot").count() and "hot-added" in page.locator("#hot").inner_text():
                appeared = round(time.time() - t_edit, 1)
                break
        results["hot_var_rendered_after_s"] = appeared
        page.wait_for_timeout(10000)  # let any reconnect churn settle
        new_console = cap.console[n_console:]
        results["mismatch_warnings_after_edit"] = sum("built for another version" in m["text"] for m in new_console)
        results["console_after_edit"] = [f"{m['type']}: {m['text'][:160]}" for m in new_console if m["type"] in ("warning", "error")][:30]
        results["loads"] = list(cap.loads)
        results["banner_present"] = page.locator("#reflex-new-version-banner").count() > 0
        results["connect_frames_total"] = sum(1 for f in cap.ws if f["event"] == "sent" and f["payload"].startswith("40"))
        results["mismatch_frames_total"] = sum(1 for f in cap.ws if f["event"] == "recv" and "state_mismatch" in f["payload"])
        results["schema_after"] = page.evaluate("() => fetch('/utils/context.jsx').then(r => r.text()).then(t => (t.match(/stateSchema = \"([0-9a-f]+)\"/) || [])[1]).catch(e => String(e))")
        page.click("#inc")
        page.wait_for_timeout(1500)
        results["count_after"] = page.locator("#count").inner_text()
        page.screenshot(path=f"{shots}_after_edit.png")
    finally:
        src.write_text(original)
    page.wait_for_timeout(12000)  # revert triggers another reload cycle; make sure it settles
    results["mismatch_warnings_after_revert"] = sum("built for another version" in m["text"] for m in cap.console) - results["mismatch_warnings_after_edit"]
    results["loads_final"] = len(cap.loads)
    results["anomalies"] = cap.anomalies()
    cap.dump(report, results=results)
    b.close()
for k, v in results.items():
    print(k, "=", v)

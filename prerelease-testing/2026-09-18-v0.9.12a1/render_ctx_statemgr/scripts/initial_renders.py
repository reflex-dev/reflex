"""Load the page N times, record window.__renders after the on_load settles."""
import json, sys, time, statistics
from playwright.sync_api import sync_playwright
BASE, N, LABEL = sys.argv[1].rstrip("/"), int(sys.argv[2]), sys.argv[3]
runs = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for i in range(N):
        ctx = b.new_context()
        ctx.add_init_script("window.__renders = window.__renders || {};")
        pg = ctx.new_page()
        pg.goto(BASE + "/", wait_until="load")
        pg.wait_for_selector("#dual-value", timeout=60000)
        try:
            pg.wait_for_function("() => { const e=document.querySelector('#dual-value'); return e && e.textContent && e.textContent !== '0/0'; }", timeout=30000)
        except Exception as exc:
            print("  WARN run", i, "dual stayed", pg.inner_text('#dual-value'))
        time.sleep(2.5)
        runs.append(dict(pg.evaluate("() => window.__renders"), _dual=pg.inner_text('#dual-value')))
        ctx.close()
    b.close()
keys = sorted(runs[0])
print(LABEL, "n=", N)
for k in keys:
    vals = [r.get(k, 0) for r in runs]
    print(f"  {k:16s} {vals}  mean={statistics.mean(vals):.1f}")
print(json.dumps(runs))

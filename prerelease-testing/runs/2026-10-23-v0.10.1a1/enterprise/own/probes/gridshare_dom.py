"""Debug helper: dump the DOM around the gridshare grids (ids, row counts) after load. Usage: gridshare_dom.py <frontend_base>"""
import os, sys
import playwright  # noqa: F401
from playwright.sync_api import sync_playwright
assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)[:300]))
    p.on("console", lambda m: m.type == "error" and errs.append(m.text[:200]))
    p.goto(sys.argv[1] + "/", wait_until="networkidle")
    p.wait_for_timeout(6000)
    print(p.evaluate("""() => ({ids: [...document.querySelectorAll('[id]')].map(e => e.id).slice(0, 40),
      wrappers: document.querySelectorAll('.ag-root-wrapper').length, rows: document.querySelectorAll('.ag-row').length,
      ga: !!document.getElementById('ga'), ga_html: (document.getElementById('ga') || {}).outerHTML?.slice(0, 600),
      json: document.getElementById('json')?.innerText?.slice(0, 200), body: document.body.innerText.slice(0, 400)})"""))
    print("errors:", errs[:5])
    p.screenshot(path=os.path.join(os.path.dirname(__file__), "..", "out", "gridshare_dom.png"))
    b.close()

"""HYD-15 / CMP-05 in dev: bundled-library metadata on the reload worker (#7113 forks it from the supervisor now).

Usage: hyd15_drive.py <frontend_base> <label> <app_py_to_touch>
Loads entr /lit and /var (lambda renderers = LambdaVar via bundled Radix), records headers/cells and hydrate errors,
then appends a comment to the app module to trigger a backend hot reload, waits, reloads both pages, repeats.
"""
import json
import os
import sys
import time
from pathlib import Path

import playwright  # noqa: F401
from playwright.sync_api import sync_playwright

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__
BASE, LABEL, APPFILE = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
OUT = Path(__file__).resolve().parent.parent / "out"
checks = []


def check(name, ok, info=None):
    checks.append({"name": name, "ok": bool(ok), "info": info})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f": {json.dumps(info, default=str)[:400]}"))


def grids(p):
    return p.evaluate("""() => [...document.querySelectorAll('.ag-root-wrapper')].map(g => ({
      headers: [...g.querySelectorAll('.ag-header-cell-text')].map(e => e.innerText),
      cells: g.querySelectorAll('.ag-cell, [role=gridcell]').length,
      text: (g.querySelector('.ag-body-viewport') || g).innerText.replace(/\s+/g, ' ').slice(0, 120),
      badges: g.querySelectorAll('.rt-Badge').length}))""")


def probe(p, route, label):
    p.goto(BASE + route, wait_until="networkidle")
    try:
        p.wait_for_selector(".ag-center-cols-container .ag-cell", timeout=20000)
    except Exception:
        pass
    p.wait_for_timeout(800)
    g = grids(p)
    hyd = p.locator("#hydrated").inner_text() if p.locator("#hydrated").count() else "n/a"
    check(f"{label} {route}: every grid has headers and cells", bool(g) and all(x["headers"] and x["cells"] > 0 for x in g), {"grids": g, "hydrated": hyd})
    return g


def main():
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        p = b.new_page()
        p.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))
        p.on("console", lambda m: m.type == "error" and not any(k in m.text for k in ("***", "AG Grid", "ag-grid", "watermark", "trial")) and errors.append(f"console: {m.text[:200]}"))
        before = {r: probe(p, r, "before-reload") for r in ("/lit", "/var", "/detail2", "/memo2")}
        with open(APPFILE, "a") as fh:
            fh.write(f"\n# hyd15 touch {time.time()}\n")
        p.wait_for_timeout(9000)  # backend reload (fork from supervisor) + vite
        after = {r: probe(p, r, "after-hot-reload") for r in ("/lit", "/var", "/detail2", "/memo2")}
        check("grids identical before/after hot reload", before == after, {"before": before, "after": after})
        b.close()
    ok = sum(1 for c in checks if c["ok"])
    json.dump({"checks": checks, "errors": errors}, open(OUT / f"hyd15_{LABEL}.json", "w"), indent=1)
    print(f"SUMMARY {LABEL} hyd15: {ok}/{len(checks)} pass; errors={errors[:5]}")


main()

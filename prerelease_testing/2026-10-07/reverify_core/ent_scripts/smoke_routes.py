"""Visit every route of a running app, screenshot it and capture console/network anomalies.

Usage: smoke_routes.py <base_url> <out_dir> <report_name> <expected_venv> <route> [<route> ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, name, venv, *routes = sys.argv[1:]
info = assert_driver_and_server(venv)
with Session(name, Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    page = s.new_page(label="smoke")
    for r in routes:
        url = base.rstrip("/") + r
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2500)
            grids = page.locator(".ag-root-wrapper").count()
            rows = page.locator(".ag-grid-scrolling-container .ag-row").count()
            body = page.inner_text("body")[:300].replace("\n", " | ")
            s.check(f"route {r}", resp is not None and resp.status == 200, {"status": resp.status if resp else None, "ag_grids": grids, "center_rows": rows, "text": body})
            s.shot(page, "route" + r.replace("/", "_"))
        except Exception as e:  # noqa: BLE001
            s.check(f"route {r}", False, repr(e)[:500])

"""Capture abstract-wrapper-data responses (status + body head) for a page."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session  # noqa: E402

url, out = sys.argv[1:3]
with Session("probe_data", Path(out)) as s:
    p = s.new_page(label="probe")
    bodies = []

    def on_resp(r):
        if "abstract-wrapper-data" in r.url:
            try:
                b = r.text()[:300]
            except Exception as e:  # noqa: BLE001
                b = repr(e)
            bodies.append((r.status, r.request.headers.get("x-reflex-client-token"), b))

    p.on("response", on_resp)
    p.goto(url, wait_until="networkidle")
    p.wait_for_timeout(4000)
    for b in bodies:
        print("RESP", b)
    print("rows:", p.locator(".ag-center-cols-container .ag-row").count())
    print(p.evaluate("() => [...document.querySelectorAll('.ag-center-cols-container .ag-row')].slice(0,3).map(r => r.outerHTML.slice(0,600)).join('\\n')"))
    s.shot(p, "workaround")

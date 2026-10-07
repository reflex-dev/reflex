"""Login on /model-ssrm and report which row containers hold the rendered rows."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv = sys.argv[1:4]
info = assert_driver_and_server(venv)
JS = """() => {
  const sel = {
    any: '.ag-row .ag-cell[col-id="name"]',
    scrolling: '.ag-grid-scrolling-container .ag-row .ag-cell[col-id="name"]',
    center: '.ag-center-cols-container .ag-row .ag-cell[col-id="name"]',
  };
  const o = {};
  for (const [k, v] of Object.entries(sel)) o[k] = [...document.querySelectorAll(v)].filter(c => c.innerText.trim()).length;
  const r = document.querySelector('.ag-row .ag-cell[col-id="name"]');
  o.ancestors = [];
  let e = r; while (e && o.ancestors.length < 8) { o.ancestors.push(e.className.toString().slice(0, 80)); e = e.parentElement; }
  return o;
}"""
with Session("probe_ssrm_dom", Path(out)) as s:
    p = s.new_page(label="dom")
    p.goto(base + "/model-ssrm", wait_until="networkidle")
    p.wait_for_timeout(2000)
    if p.locator("button:has-text('Login')").count():
        p.click("button:has-text('Login')")
    p.wait_for_timeout(4000)
    s.note(f"after login: {p.evaluate(JS)}")
    p.goto(base + "/qa-model-workaround", wait_until="networkidle")
    p.wait_for_timeout(3000)
    s.note(f"infinite page: {p.evaluate(JS)}")

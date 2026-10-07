"""Dump selected DOM structure of a page (exploration helper)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session  # noqa: E402

url, out, *clicks = sys.argv[1:]
with Session("probe", Path(out)) as s:
    p = s.new_page(label="probe")
    p.goto(url, wait_until="networkidle")
    p.wait_for_timeout(2000)
    for c in clicks:
        if c.startswith("wait:"):
            p.wait_for_timeout(int(c[5:]))
            continue
        p.click(c, timeout=10000)
        p.wait_for_timeout(1500)
    print(p.evaluate("""() => {
      const out = [];
      const hdr = document.querySelector('.ag-header-cell[col-id="name"]') || document.querySelector('.ag-header-cell');
      out.push('HEADER: ' + (hdr ? hdr.outerHTML.slice(0, 1500) : 'none'));
      const row = document.querySelector('.ag-grid-scrolling-container .ag-row');
      out.push('ROW: ' + (row ? row.outerHTML.slice(0, 1500) : 'none'));
      const sel = document.querySelector('.ag-pinned-left-cols-container .ag-row');
      out.push('PINNED-LEFT ROW: ' + (sel ? sel.outerHTML.slice(0, 800) : 'none'));
      out.push('ROWS: ' + document.querySelectorAll('.ag-grid-scrolling-container .ag-row').length);
      out.push('BUTTONS: ' + [...document.querySelectorAll('button')].map(b => (b.innerText || b.getAttribute('aria-label') || b.className).slice(0,40)).join(' || '));
      return out.join('\\n\\n');
    }"""))

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session  # noqa: E402
url, out = sys.argv[1:3]
with Session("probe_rows", Path(out)) as s:
    p = s.new_page(label="probe")
    p.goto(url, wait_until="networkidle")
    p.wait_for_timeout(3000)
    print(p.evaluate("""() => {
      const r = document.querySelector('[role=row][row-index]');
      if (!r) return 'no role=row';
      const chain = [];
      let n = r;
      for (let i = 0; i < 6 && n; i++) { chain.push(n.tagName + '.' + (n.className || '').toString().split(' ').join('.') ); n = n.parentElement; }
      return chain.join('\\n  <- ') + '\\n\\nROW: ' + r.outerHTML.slice(0, 900);
    }"""))

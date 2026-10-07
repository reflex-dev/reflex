import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session  # noqa: E402
url, out = sys.argv[1:3]
with Session("probe_attrs", Path(out)) as s:
    p = s.new_page(label="probe")
    p.goto(url, wait_until="networkidle")
    p.wait_for_timeout(3000)
    print(p.evaluate("""() => [...document.querySelectorAll('.ag-root-wrapper')].map(w => {
        const attrs = [...w.attributes].map(a => a.name + '=' + a.value.slice(0,60)).join(' ');
        const pin = [...w.querySelectorAll('[class*=floating], [class*=pinned-top], [class*=pinned-bottom]')].slice(0,4).map(e => e.className.toString().slice(0,80));
        const ov = [...w.querySelectorAll('[class*=overlay]')].map(e => e.className.toString().slice(0,60) + ':' + e.innerText.slice(0,30));
        return attrs + '\\n   pinned:' + JSON.stringify(pin) + '\\n   overlay:' + JSON.stringify(ov);
    }).join('\\n')"""))

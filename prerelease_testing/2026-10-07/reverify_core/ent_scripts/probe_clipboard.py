import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session  # noqa: E402
base, out = sys.argv[1:3]
with Session("probe_clip", Path(out)) as s:
    ctx = s.new_context("clip")
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
    p = ctx.new_page()
    p.goto(base + "/fill-handle", wait_until="networkidle")
    p.wait_for_timeout(2000)
    G = '[grid-id="fill-handle-grid"] .ag-grid-scrolling-container'
    p.locator(f'{G} .ag-row[row-index="0"] .ag-cell[col-id="gold"]').click()
    p.keyboard.press("ControlOrMeta+c")
    p.wait_for_timeout(800)
    print("clipboard after copy:", repr(p.evaluate("() => navigator.clipboard.readText()")))
    p.locator(f'{G} .ag-row[row-index="4"] .ag-cell[col-id="gold"]').click()
    p.keyboard.press("ControlOrMeta+v")
    p.wait_for_timeout(1500)
    print("gold row4 after paste:", p.locator(f'{G} .ag-row[row-index="4"] .ag-cell[col-id="gold"]').inner_text())
    print("toasts:", p.locator("[data-sonner-toast]").all_inner_texts())
    # try explicit clipboard write + paste
    p.evaluate("() => navigator.clipboard.writeText('9')")
    p.locator(f'{G} .ag-row[row-index="5"] .ag-cell[col-id="gold"]').click()
    p.keyboard.press("ControlOrMeta+v")
    p.wait_for_timeout(1500)
    print("gold row5 after paste of '9':", p.locator(f'{G} .ag-row[row-index="5"] .ag-cell[col-id="gold"]').inner_text())
    print("toasts:", p.locator("[data-sonner-toast]").all_inner_texts())
    print([c['text'][:200] for c in s.console if not c['benign']][-8:])

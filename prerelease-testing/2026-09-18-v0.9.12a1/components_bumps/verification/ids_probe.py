import json, sys
from playwright.sync_api import sync_playwright
BASE=sys.argv[1].rstrip("/")
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg=b.new_context(viewport={"width":1100,"height":700}).new_page()
    pg.goto(f"{BASE}/ids", wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(1200)
    out={
     "foreach_ids": pg.eval_on_selector_all("#ids-box .foreach-input","els=>els.map(e=>e.id)"),
     "foreach_label_for": pg.eval_on_selector_all("#ids-box .foreach-label","els=>els.map(e=>e.htmlFor)"),
     "memo_ids": pg.eval_on_selector_all("#memo-box .memo-input","els=>els.map(e=>e.id)"),
     "html_ids_box": pg.evaluate("()=>document.getElementById('ids-box').innerHTML.slice(0,600)"),
    }
    print(json.dumps(out, indent=2))
    b.close()

import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
msgs=[]; mismatch={"t":None}; t0=time.time()
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
    pg=b.new_page()
    def oc(m):
        msgs.append(f"[{m.type}] {m.text}")
        if "Cannot process state update" in m.text and mismatch["t"] is None: mismatch["t"]=time.time()-t0
    pg.on("console", oc)
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_function("() => { const t=document.querySelector('#token'); return t && t.value; }", timeout=30000)
    print("TOKEN_OK counter_before=", pg.eval_on_selector("#counter","e=>e.textContent"))
    t0=time.time()
    pg.click("#bump-btn")
    dl=time.time()+8
    while time.time()<dl and mismatch["t"] is None: pg.wait_for_timeout(200)
    c1=pg.eval_on_selector("#counter","e=>e.textContent")
    print(f"AFTER_BUMP counter={c1} mismatch_at={mismatch['t']}")
    # try another bump: fatal => no change
    pg.click("#bump-btn"); pg.wait_for_timeout(1200)
    c2=pg.eval_on_selector("#counter","e=>e.textContent")
    print(f"AFTER_2ND_BUMP counter={c2} (equal to prev => fatal)")
    pg.screenshot(path=str(out/"stale_extra.png"))
    b.close()
(out/"stale_extra_console.log").write_text("\n".join(msgs))
mm=[m for m in msgs if "Cannot process state update" in m]
print(f"MISMATCH_CONSOLE_COUNT={len(mm)}")
for m in mm: print("  ", m)
print("--- non-mismatch console errors ---")
for m in msgs:
    if m.startswith("[error]") and "Cannot process" not in m: print("  ", m[:160])

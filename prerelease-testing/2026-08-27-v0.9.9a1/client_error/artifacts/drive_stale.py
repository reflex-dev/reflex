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
    # wait up to 8s for mismatch console error
    dl=time.time()+8
    while time.time()<dl and mismatch["t"] is None: pg.wait_for_timeout(200)
    tok=pg.eval_on_selector("#token","el=>el.value") if pg.query_selector("#token") else "NO_TOKEN_ELEM"
    print(f"MISMATCH_AT={mismatch['t']} TOKEN_VALUE={tok!r}")
    pg.screenshot(path=str(out/"stale_frontend.png"))
    b.close()
(out/"stale_console.log").write_text("\n".join(msgs))
mm=[m for m in msgs if "Cannot process state update" in m]
print(f"MISMATCH_CONSOLE_COUNT={len(mm)}")
for m in mm: print("  ", m)
print("--- other console errors ---")
for m in msgs:
    if m.startswith("[error]") and "Cannot process" not in m: print("  ", m)

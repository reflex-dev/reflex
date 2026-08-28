import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
msgs=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
    pg=b.new_page()
    pg.on("console", lambda m: msgs.append(f"[{m.type}] {m.text}"))
    pg.on("pageerror", lambda e: msgs.append(f"[pageerror] {e}"))
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_timeout(6000)  # let hydration + mismatch happen
    tok = pg.eval_on_selector("#token","e=>e.value") if pg.query_selector("#token") else "NO_ELEM"
    print(f"TOKEN_VALUE={tok!r}")
    pg.screenshot(path=str(out/"stale_extra.png"))
    b.close()
(out/"stale_extra_console.log").write_text("\n".join(msgs))
mm=[m for m in msgs if "Cannot process state update" in m]
print(f"MISMATCH_CONSOLE_COUNT={len(mm)}")
for m in mm: print("  MISMATCH:", m)
print(f"TOTAL_CONSOLE={len(msgs)}")
for m in msgs:
    if m.startswith("[error]") or m.startswith("[pageerror]"):
        print("  ERR:", m[:200])

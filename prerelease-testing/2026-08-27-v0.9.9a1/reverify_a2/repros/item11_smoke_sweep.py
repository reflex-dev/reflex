"""Item 11: general Chromium smoke sweep of an a2 dev app (console/network/errors)."""
import sys
from playwright.sync_api import sync_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3140/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else "shots/item11"
import os; os.makedirs(SHOTS, exist_ok=True)

BENIGN = ["HydrateFallback", "React DevTools", "[vite] connecting", "[vite] connected", "Download the React DevTools"]
console, page_errors, failed, responses = [], [], [], []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_context().new_page()
    pg.on("console", lambda m: console.append((m.type, m.text)))
    pg.on("pageerror", lambda e: page_errors.append(str(e)))
    pg.on("requestfailed", lambda r: failed.append(f"{r.url} :: {r.failure}"))
    pg.on("response", lambda r: responses.append((r.status, r.url)))
    pg.goto(URL, wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=f"{SHOTS}/load.png")
    # exercise: click a button (state event round-trip)
    try:
        pg.click("#btn-week", timeout=5000); pg.wait_for_timeout(500)
    except Exception as e:
        console.append(("note", f"click: {e}"))
    pg.screenshot(path=f"{SHOTS}/after.png")
    b.close()

errs = [c for c in console if c[0] in ("error",) and not any(x in c[1] for x in BENIGN)]
warns = [c for c in console if c[0] == "warning" and not any(x in c[1] for x in BENIGN)]
bad_resp = [(s,u) for (s,u) in responses if s >= 400]
print(f"console total={len(console)} errors(non-benign)={len(errs)} warnings(non-benign)={len(warns)}")
for e in errs[:10]: print("  ERROR:", e[1][:160])
for w in warns[:10]: print("  WARN :", w[1][:160])
print(f"page_errors={len(page_errors)}"); [print("  PAGEERR:", e[:160]) for e in page_errors[:10]]
print(f"failed_requests={len(failed)}"); [print("  FAILREQ:", f[:160]) for f in failed[:10]]
print(f"http>=400 responses={len(bad_resp)}"); [print("  BADRESP:", s, u[:140]) for (s,u) in bad_resp[:10]]
print("VERDICT:", "CLEAN" if (not errs and not page_errors and not failed and not bad_resp) else "DIRTY")

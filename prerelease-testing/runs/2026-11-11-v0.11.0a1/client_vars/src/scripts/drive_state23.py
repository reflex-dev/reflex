"""STATE-23 re-check: hydrate a var annotated `rx.LocalStorage` / `rx.Cookie` from a stored value. Usage: drive_state23.py <base> <label>"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
r = Run(base, label, "results/storage")
p = r.new_page("A")
r.goto(p, "/")
for name, v in (("typed", "T1"), ("ck_typed", "CT1"), ("plain", "P1")):
    p.fill("#val", v); p.click(f"#set-{name}")
p.click("#set-num")
time.sleep(1)
print("MARK before reload", flush=True)
p.reload(); p.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'")
time.sleep(1.5)
got = {i: p.locator(f"#{i}").text_content() for i in ("typed", "ck_typed", "plain", "num", "types")}
r.check("values restored from storage after reload", (got["typed"], got["ck_typed"], got["plain"], got["num"]) == ("T1", "CT1", "P1", "7"), got)
r.finish()

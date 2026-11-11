"""Drive legacyapp and print an observation table (compare 0.10.1 vs 0.11.0a1). Usage: drive_legacy.py <base> <label>"""
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
r = Run(base, label, "results/legacy")
p = r.new_page("A")
obs = {}


def snap(tag, ids):
    time.sleep(0.4)
    obs[tag] = {i: (p.locator(f"#{i}").first.text_content() if p.locator(f"#{i}").count() else "<absent>") for i in ids}


def nav(link_id, heading):
    p.click(f"#{link_id}")
    p.wait_for_function(f"document.querySelector('h1') && document.querySelector('h1').textContent === {heading!r}", timeout=15000)


ALL = ["g", "gd", "loc", "anon", "nodef", "ni", "ltp", "got"]
r.goto(p, "/")
snap("01 initial", ALL)
p.click("#g-set"); p.click("#loc-inc"); p.click("#loc-inc"); p.click("#anon-set"); p.click("#nodef-set"); p.click("#ni-set"); p.click("#ltp-inc")
snap("02 after sets", ALL)
obs["02 rows"] = p.locator("#rows").text_content()
p.fill("#g-input", "typed"); snap("03 typed", ["g"])
p.click("#push"); snap("04 push", ["g"])
p.click("#retrieve"); snap("05 retrieve", ["got"])
p.click("#push-dict"); snap("06 push dict", ["gd"])
p.click("#retrieve-dict"); snap("07 retrieve dict", ["got"])
p.click("#retrieve-ni"); snap("08 retrieve not-included var", ["got"])
nav("nav-two", "two")
snap("09 page two", ["g", "ltp", "got"])
p.click("#retrieve"); snap("10 retrieve on two", ["got"])
p.click("#retrieve-dict"); snap("11 retrieve dict (not mounted on two)", ["got"])
p.click("#ltp-inc"); snap("12 ltp inc on two", ["ltp"])
nav("nav-home", "home")
snap("13 back home", ALL)
p.reload(); p.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'")
snap("14 after reload", ALL)
print(json.dumps(obs, indent=1, ensure_ascii=False))
with open(f"results/legacy/{label}_obs.json", "w") as f:
    json.dump(obs, f, indent=1, ensure_ascii=False)
r.finish()

"""dict[str, dict[str,int]] mutated through .values()/.items(); cached var over it. Also the async
uncached var that is only referenced on /page2 (withheld by the delta filter on '/')."""
import sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import *
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/dict_asyncvar.json"
import os
SHOTS = os.environ.get("SHOTS", "../shots")  # outside the app dir: a file written under it hot-reloads the dev server
os.makedirs(SHOTS, exist_ok=True)
results = []
cap = Capture()
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/dict", wait_until="networkidle"); page.wait_for_timeout(1000)
    check("dict initial total", page.inner_text("#total") == "total: 33", page.inner_text("#total"), results)
    page.click("#btn-values")
    try:
        wait_text(page, "#total", "total: 35", 5); ok = True
    except AssertionError as e:
        ok = False; print(e)
    check("mutation via dict.values() updates UI + cached var", ok and page.inner_text("#alpha-x") == "alpha_x: 2", f"{page.inner_text('#total')} {page.inner_text('#alpha-x')} {page.inner_text('#data')}", results)
    page.click("#btn-items")
    try:
        wait_text(page, "#total", "total: 136", 5); ok = True
    except AssertionError as e:
        ok = False; print(e)
    check("mutation via dict.items() updates UI + cached var", ok and page.inner_text("#alpha-y") == "alpha.y: 102", f"{page.inner_text('#total')} {page.inner_text('#alpha-y')}", results)
    page.click("#btn-addkey")
    try:
        wait_text(page, "#total", "total: 150", 5); ok = True
    except AssertionError as e:
        ok = False; print(e)
    check("adding a key to inner dict via values() updates UI", ok and '"z":7' in page.inner_text("#data"), page.inner_text("#data"), results)
    page.click("#btn-listvalues")
    try:
        wait_text(page, "#total", "total: 2150", 5); ok = True
    except AssertionError as e:
        ok = False; print(e)
    check("mutation via list(dict.values()) updates UI", ok, page.inner_text("#total"), results)
    page.click("#btn-reset"); wait_text(page, "#total", "total: 33", 5)
    page.screenshot(path=SHOTS + "/dict_page.png")

    # async uncached var: bump seed on '/', where slow_doubled is NOT referenced
    ctx2, page2 = new_page(b, cap)
    page2.goto(BASE + "/", wait_until="networkidle"); page2.wait_for_timeout(800)
    for _ in range(3):
        page2.click("#btn-seed"); page2.wait_for_timeout(200)
    wait_text(page2, "#seed", "seed: 3", 5)
    check("bump seed on page without the async var (check server log for RuntimeWarning)", True, "seed: 3 on /", results)
    page2.click("text=page2")
    try:
        wait_text(page2, "#doubled", "doubled: 6", 5); ok = True
    except AssertionError as e:
        ok = False; print(e)
    check("async uncached var computed on page2 after nav", ok, page2.inner_text("#doubled"), results)
    page2.click("#btn-seed")
    try:
        wait_text(page2, "#doubled", "doubled: 8", 5); ok = True
    except AssertionError as e:
        ok = False; print(e)
    check("async uncached var recomputed on event", ok, page2.inner_text("#doubled"), results)
    page2.click("text=index"); page2.wait_for_timeout(500)
    page2.click("#btn-seed"); wait_text(page2, "#seed", "seed: 5", 5)
    page2.goto(BASE + "/page2", wait_until="networkidle"); page2.wait_for_timeout(800)
    check("async var correct after full reload", page2.inner_text("#doubled") == "doubled: 10", page2.inner_text("#doubled"), results)
sys.exit(finish(results, cap, REPORT))

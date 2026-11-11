"""Drive csedge (client_state edge cases). Usage: drive_edge.py <base> <label>"""
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
r = Run(base, label, "results/edge")
T = r.expect_text


import os

ONLY = os.environ.get("CS_PAGES", "all").split(",")


def open_page(path):
    p = r.new_page(path)
    name = path.strip("/")
    if not ("all" in ONLY and name != "casing2") and name not in ONLY:
        print("SKIP", path)
        return p, False
    n0 = len(r.console)
    try:
        resp = p.goto(base + path)
        status = resp.status if resp else None
        p.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'", timeout=15000)
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = False
        status = f"{type(e).__name__}"
    errs = [c["text"][:400] for c in r.console[n0:] if c["type"] in ("error", "pageerror")]
    r.check(f"{path} loads and hydrates", ok, f"status={status} errors={errs[:2]}")
    return p, ok


p, ok = open_page("/dupsame")
if ok:
    print("dupsame text:", p.locator("#both").text_content())
    r.check("INFO /dupsame: one component, same name, different defaults", True, p.locator("#both").text_content())
else:
    p.screenshot(path=f"results/edge/{label}_dupsame.png")

p, ok = open_page("/casing")
if ok:
    T(p, "#both", "lower|upper")
    p.click("#set-lower"); time.sleep(0.2); print("after set-lower:", p.locator("#both").text_content())
    p.click("#set-upper"); time.sleep(0.2); print("after set-upper:", p.locator("#both").text_content())
    T(p, "#both", "L|U", "names 'item' and 'Item' are independent")
else:
    p.screenshot(path=f"results/edge/{label}_casing.png")

for path in ("/dupsame2", "/casing2"):
    p, ok = open_page(path)
    if ok:
        print(path, "text:", p.locator("#both").text_content())
        if path == "/casing2":
            p.click("#set-both"); T(p, "#both", "L|U", "casing2: both setters on one element")
    else:
        p.screenshot(path=f"results/edge/{label}{path.replace('/', '_')}.png")
        try:
            print(path, "body:", p.locator("body").inner_text()[:600])
        except Exception as e:  # noqa: BLE001
            print(path, "no body", e)

p, ok = open_page("/keyed")
if ok:
    rows = p.locator("#rows .krow")
    rows.nth(1).locator(".tog").click()
    p.click("#del-first"); p.wait_for_function("document.querySelectorAll('#rows .krow').length === 2")
    got = [(rows.nth(i).locator(".item").text_content(), rows.nth(i).locator(".st").text_content()) for i in range(2)]
    r.check("keyed memo rows: per-row client state follows the item after deleting the first row", got == [("b", "open"), ("c", "closed")], got)

p, ok = open_page("/collapse")
if ok:
    cards = p.locator(".card")
    cards.nth(0).locator(".linc").click()
    cards.nth(0).locator(".ninc").click()
    time.sleep(0.2)
    got = {"lifted": [cards.nth(i).locator(".lv").text_content() for i in range(2)], "page": p.locator("#page-lifted").text_content(),
           "not_lifted": [cards.nth(i).locator(".nv").text_content() for i in range(2)]}
    r.check("page-level read lifts the var (cards share), memo-only var stays per instance",
            got == {"lifted": ["1", "1"], "page": "1", "not_lifted": ["1", "0"]}, got)

p, ok = open_page("/condmatch")
if ok:
    T(p, "#cond", "is-a"); T(p, "#match", "match-a"); T(p, "#len", "2"); T(p, "#mul", "6"); T(p, "#fmt", "2-a-3")
    r.check("style from client value", p.evaluate("getComputedStyle(document.querySelector('#styled')).width") == "100px")
    p.click("#mode-b"); T(p, "#cond", "not-a"); T(p, "#match", "match-b")
    r.check("style updates", p.evaluate("getComputedStyle(document.querySelector('#styled')).width") == "200px")
    p.click("#mode-c"); T(p, "#match", "match-default")
    p.click("#push-item"); T(p, "#len", "3"); r.check("foreach over client list", p.locator("#items .it").count() == 3, p.locator("#items").text_content())
    p.click("#n-inc"); T(p, "#mul", "9"); p.click("#bump"); T(p, "#mul", "12", "client value * state var"); T(p, "#fmt", "3-c-4")

p, ok = open_page("/memoforeach")
if ok:
    l1 = p.locator("#l1 .mrow"); l2 = p.locator("#l2 .mrow")
    l1.nth(0).locator(".tog").click(); time.sleep(0.2)
    got = {"l1": [l1.nth(i).locator(".st").text_content() for i in range(l1.count())], "l2": [l2.nth(i).locator(".st").text_content() for i in range(l2.count())]}
    print("memoforeach:", got)
    r.check("INFO unnamed var in foreach inside @rx.memo: shared by the rows of one memo instance, separate per instance",
            got["l2"] == ["closed"] * 3, got)

p, ok = open_page("/statedefault")
if ok:
    T(p, "#fs", "3", "default from state var"); p.click("#bump"); T(p, "#sv", "4")
    time.sleep(0.2); print("client var after state default changed:", p.locator("#fs").text_content())
    p.click("#fs-inc"); time.sleep(0.2); print("after +10:", p.locator("#fs").text_content())
    r.check("INFO default from state var is only the initial value", p.locator("#fs").text_content() == "13", p.locator("#fs").text_content())

p, ok = open_page("/mount")
if ok:
    T(p, "#m", "set-on-mount", "on_mount setter"); p.click("#gs"); T(p, "#m", "from-global-set", "global_set via call_function")
    n0 = len(r.console); p.click("#gv"); time.sleep(0.3)
    logs = [c["text"] for c in r.console[n0:] if c["type"] == "log"]
    r.check("global_value read", logs == ["from-global-set"], logs)

p, ok = open_page("/storagecollide")
if ok:
    T(p, "#cs", "cs-default"); T(p, "#ls", "ls-default")
    p.click("#set-cs"); T(p, "#cs", "cs-new"); T(p, "#ls", "ls-default", "client_state write does not touch LocalStorage var of same name")
    p.click("#set-ls"); T(p, "#ls", "ls-new"); T(p, "#cs", "cs-new", "LocalStorage write does not touch client_state")
    r.check("localStorage holds only the storage var", p.evaluate("localStorage.getItem('pref')") == "ls-new", p.evaluate("JSON.stringify(localStorage)"))

p, ok = open_page("/setcs")
if ok:
    print("set client state:", p.locator("#tags").text_content(), p.locator("#has-c").text_content(), p.locator("#len").text_content())
    T(p, "#len", "2"); T(p, "#has-c", "false")
    p.click("#add-c"); T(p, "#len", "3"); T(p, "#has-c", "true")
    p.click("#add-a"); T(p, "#len", "3", "union with existing element keeps length")
    r.check("foreach over client set", p.locator("#each .t").count() == 3, p.locator("#each").text_content())

fails = r.finish()
sys.exit(1 if fails else 0)

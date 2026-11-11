"""Drive varsapp / and /setnone (SetVar). Usage: drive_sets.py <base> <label> [old]"""
import json
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from drvlib import Run

base, label = sys.argv[1], sys.argv[2]
OLD = len(sys.argv) > 3 and sys.argv[3] == "old"
r = Run(base, label, "results/sets")
p = r.new_page("A")
r.goto(p, "/")


def norm(v):
    if isinstance(v, list):
        return sorted((norm(e) if not isinstance(e, list) else e for e in v), key=lambda e: json.dumps(e))
    return v


def texts(sel):
    return p.eval_on_selector_all(sel, "els => els.map(e => e.textContent)")


def compare(tag):
    time.sleep(0.25)
    exp = json.loads(p.locator("#expected").text_content())
    bad = {}
    n = 0
    for k, v in exp.items():
        loc = p.locator(f"#{k}")
        if not loc.count():
            continue
        n += 1
        got_txt = loc.text_content()
        try:
            got = json.loads(got_txt)
        except Exception:  # noqa: BLE001
            got = got_txt
        if norm(got) != norm(json.loads(v)):
            bad[k] = {"frontend": got_txt, "python": v}
    # foreach renders exactly the JSON order
    tags_json = json.loads(p.locator("#tags").text_content())
    each = texts("#each .t")
    if each != tags_json:
        bad["foreach_order"] = {"dom": each, "json": tags_json}
    if not OLD:
        arr = texts("#each-arr .t")
        if arr != tags_json:
            bad["foreach_to_array"] = {"dom": arr, "json": tags_json}
    r.check(f"[{tag}] {n} set results equal Python", not bad, bad if bad else f"tags={tags_json}")
    return tags_json


def click(i, n_expected=None):
    before = int(p.locator("#n-events").text_content())
    p.click(f"#{i}")
    p.wait_for_function(f"parseInt(document.querySelector('#n-events').textContent) >= {before + (n_expected or 1)}", timeout=10000)


order0 = compare("initial")
print("initial DOM order:", order0, "| pairs:", texts("#each-pairs .t"), "| upper:", texts("#each-upper .t"))
r.expect_text(p, "#cond-x", "no-x"); r.expect_text(p, "#truthy", "nonempty"); r.expect_text(p, "#match", "match-default")
print("deprecated ops:", {k: p.locator(f"#{k}").text_content() for k in ("dep_join", "dep_index", "dep_map", "dep_reverse", "dep_slice")})
r.check("deprecated join == ','.join(order)", p.locator("#dep_join").text_content() == ",".join(order0))
r.check("deprecated [0] == first in order", p.locator("#dep_index").text_content() == order0[0])
# a delta that touches no set must not reorder
click("bump"); o = compare("after unrelated delta"); r.check("order stable across unrelated delta", o == order0, f"{order0} -> {o}")
orders = [order0]
for step, n in (("add-x", 1), ("add-a", 1), ("discard-none", 1), ("discard-a", 1), ("ior", 1), ("symdiff-update", 1), ("add-many", 10), ("add-pair", 1), ("add-color", 1),
                ("nums-replace", 1), ("dc-add", 1), ("pm-add", 1), ("set-maybe", 1)):
    click(step, n)
    orders.append(compare(f"after {step}"))
r.expect_text(p, "#cond-x", "has-x", "rx.cond(tags.contains('x')) follows add")
r.check("foreach over Optional set after assignment", texts("#each-maybe .t") == ["m"], texts("#each-maybe .t"))
r.check("pairs foreach renders 3 tuples", sorted(texts("#each-pairs .t")) == ["1-a", "2-b", "3-c"], texts("#each-pairs .t"))
r.check("colors foreach renders enum values", sorted(texts("#each-colors .t")) == ["blue", "red"], texts("#each-colors .t"))
# relative order of surviving elements across mutations (reshuffle = DOM flicker)
moved = 0
for a, b in zip(orders, orders[1:]):
    common = [x for x in a if x in b]
    if common != [x for x in b if x in a]:
        moved += 1
print(f"mutations that changed the relative order of surviving elements: {moved}/{len(orders) - 1}")
r.check("INFO relative order of surviving elements across mutations", True, f"reordered in {moved}/{len(orders) - 1} mutations")
# select items from a set
p.click("#sel"); time.sleep(0.3)
opts = texts("[role=option]")
r.check("rx.select(set) lists every element", sorted(opts) == sorted(orders[-1]), opts)
p.keyboard.press("Escape")
# event args
click("take-list"); r.check("set var passed to a list[str] handler arg", p.locator("#taken").text_content() == f"list:{sorted(orders[-1])}", p.locator("#taken").text_content())
click("take-set-plain")
r.check("INFO set var passed to a set[str] handler arg: type received", True, p.locator("#taken").text_content()[:12])
if not OLD:
    click("take-set")
    want = sorted(set(orders[-1]) | {"c", "d"})
    r.check("set var passed to a set[str] handler arg arrives as set", p.locator("#taken").text_content() == f"set:{want}", p.locator("#taken").text_content())
click("reassign"); compare("after reassign"); r.expect_text(p, "#match", "match-only", "rx.match on a set (single element)")
click("copy-other"); o = compare("after copy-other")
got = p.locator("#match").text_content()
r.check("rx.match on a 2-element set matches regardless of serialization order", got == "match-cd", f"tags JSON order={o} match={got}")
click("clear"); compare("after clear"); r.expect_text(p, "#truthy", "empty", "empty set is falsy in rx.cond")
click("unset-maybe")
r.check("foreach over None set renders nothing", texts("#each-maybe .t") == [], texts("#each-maybe .t"))

# Optional set that is None
p2 = r.new_page("none")
n0 = len(r.console)
p2.goto(base + "/setnone")
try:
    p2.wait_for_function("document.querySelector('#hyd') && document.querySelector('#hyd').textContent === 'hydrated'", timeout=15000)
    hyd = True
except Exception:  # noqa: BLE001
    hyd = False
time.sleep(0.5)
errs = [c["text"][:300] for c in r.console[n0:] if c["type"] in ("error", "pageerror")]
vals = {k: (p2.locator(f"#{k}").text_content() if p2.locator(f"#{k}").count() else "<absent>") for k in ("none_len_guard", "none_contains", "none_union", "none_subset")}
r.check("INFO /setnone with maybe=None", True, f"hydrated={hyd} values={vals} errors={errs[:2]}")
p2.screenshot(path=f"results/sets/{label}_setnone.png")
fails = r.finish()
sys.exit(1 if fails else 0)

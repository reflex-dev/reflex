"""on_load as tuple/list/single/typed list var; on_click tuple; handlers returning tuples,
typed lists, event_sequence() results, generators yielding tuples."""

import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common import Capture, browser, check, finish, new_page, wait_text

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3180"
REPORT = sys.argv[2] if len(sys.argv) > 2 else "logs/onload_sequences.json"


import os
SHOTS = os.environ.get("SHOTS", "../shots")  # outside the app dir: a file written under it hot-reloads the dev server
os.makedirs(SHOTS, exist_ok=True)
results = []
cap = Capture()
with browser() as b:
    ctx, page = new_page(b, cap)
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(1500)
    a = page.inner_text("#a-log")
    bb = page.inner_text("#b-log")
    check("on_load tuple runs both events", a == "A.log: A.load_tuple_a" and bb == "B.log: B.load_tuple_b", f"{a!r} {bb!r}", results)
    page.screenshot(path=f"{SHOTS}/index_loaded.png")

    page.click("#clear")
    wait_text(page, "#a-log", "A.log:")
    page.click("#btn-tuple")
    wait_text(page, "#b-log", "B.log: B.h2")
    check("on_click tuple (A.h1, B.h2)", page.inner_text("#a-log") == "A.log: A.h1", page.inner_text("#a-log") + " / " + page.inner_text("#b-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("#btn-rt")
    wait_text(page, "#b-log", "B.log: B.h2")
    check("handler returns tuple (A.h1, B.h2)", page.inner_text("#a-log") == "A.log: A.returns_tuple|A.h1", page.inner_text("#a-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("#btn-rtl")
    wait_text(page, "#b-log", "B.log: B.h2")
    check("handler returns list[EventSpec] var", page.inner_text("#a-log") == "A.log: A.returns_typed_list|A.h1|A.h1", page.inner_text("#a-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("#btn-es1")
    wait_text(page, "#b-log", "B.log: B.h2")
    check("event_sequence(single) returned", page.inner_text("#a-log") == "A.log: A.returns_event_sequence_single", page.inner_text("#a-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("#btn-est")
    wait_text(page, "#a-log", "A.log: A.returns_event_sequence_tuple|A.h1|A.h1")
    check("event_sequence(tuple) returned", page.inner_text("#b-log") == "B.log: B.h2", page.inner_text("#b-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("#btn-gen")
    wait_text(page, "#b-log", "B.log: B.h2|B.h2")
    check("generator yielding tuple then list", page.inner_text("#a-log") == "A.log: A.returns_generator_tuple|A.h1" and page.inner_text("#counter") == "counter: 1", page.inner_text("#a-log") + " / " + page.inner_text("#counter"), results)

    # client-side navigation to other on_load variants
    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("text=list")
    wait_text(page, "#b-log", "B.log: B.load_list_b")
    check("on_load list (client nav)", page.inner_text("#a-log") == "A.log: A.load_list_a", page.inner_text("#a-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("text=single")
    wait_text(page, "#a-log", "A.log: A.load_single")
    check("on_load single event (client nav)", page.inner_text("#b-log") == "B.log:", page.inner_text("#b-log"), results)

    page.click("#clear"); wait_text(page, "#a-log", "A.log:")
    page.click("text=typed")
    wait_text(page, "#b-log", "B.log: B.load_tuple_b")
    check("on_load typed list[EventSpec] (client nav)", page.inner_text("#a-log") == "A.log: A.load_tuple_a", page.inner_text("#a-log"), results)

    # hard reload of each
    for route, exp_a, exp_b in [("/list", "A.log: A.load_list_a", "B.log: B.load_list_b"), ("/single", "A.log: A.load_single", "B.log:"), ("/typed", "A.log: A.load_tuple_a", "B.log: B.load_tuple_b")]:
        page.click("#clear"); wait_text(page, "#a-log", "A.log:")
        page.goto(BASE + route, wait_until="networkidle")
        page.wait_for_timeout(1200)
        check(f"on_load full load {route}", page.inner_text("#a-log") == exp_a and page.inner_text("#b-log") == exp_b, page.inner_text("#a-log") + " / " + page.inner_text("#b-log"), results)
    page.screenshot(path=f"{SHOTS}/typed_loaded.png")
sys.exit(finish(results, cap, REPORT))

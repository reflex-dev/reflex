"""Drive pyapp: initial values of every annotation shape, mutation round trip, bg task, ABC mixin,
postponed-annotation state, navigation + reload, second tab.

Usage: driver-python drive_pyapp.py <frontend_url> <out_dir> <label> <expected_py_prefix>
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from pwkit import CHROMIUM, Sink, expect, summarize

base, out, label, pyprefix = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
out.mkdir(parents=True, exist_ok=True)
sink = Sink()
vals = {}


def txt(page, sel):
    return page.locator(sel).first.inner_text(timeout=15000)


def wait_text(page, sel, value, timeout=15000):
    page.wait_for_function(
        "([s, v]) => document.querySelector(s)?.textContent === v", arg=[sel, value], timeout=timeout
    )


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1000, "height": 1400})
    page = ctx.new_page()
    sink.attach(page, "t1")
    page.goto(base + "/", wait_until="networkidle", timeout=120000)
    sink.check("renders", lambda: page.wait_for_selector("#page-shapes", timeout=60000) and True)
    sink.check("backend python version", lambda: expect(txt(page, "#pyver").startswith(pyprefix), txt(page, "#pyver")))
    for key in ["l_opt", "d_nested", "ann", "point", "pm", "lit", "color", "when", "fld", "uni", "tup", "td"]:
        vals[f"init.{key}"] = txt(page, f"#v-{key}")
    vals["init.o_str"] = txt(page, "#o_str")
    vals["init.cond-list"] = txt(page, "#cond-list")
    vals["init.rows"] = [r.inner_text() for r in page.locator(".row").all()]
    vals["init.f_summary"] = txt(page, "#f_summary")
    vals["init.greeting"] = txt(page, "#greeting")
    sink.check("init Optional list None -> cond false", lambda: expect(vals["init.cond-list"] == "no list" and vals["init.o_str"] == "none", vals))
    sink.check("init dataclass/pydantic/enum/datetime", lambda: expect(
        '"x":1' in vals["init.point"].replace(" ", "") and '"name":"pm"' in vals["init.pm"].replace(" ", "") and vals["init.color"].strip('"') == "red" and "2026-10-06" in vals["init.when"],
        {k: vals[k] for k in ("init.point", "init.pm", "init.color", "init.when")}))
    sink.check("init future-annotations state", lambda: expect(vals["init.f_summary"] == "None|fut|5|green|2030", vals["init.f_summary"]))
    page.screenshot(path=str(out / f"{label}-init.png"), full_page=True)

    def mutate():
        page.click("#mutate")
        wait_text(page, "#o_str", "now set")
        for key in ["l_opt", "d_nested", "ann", "point", "pm", "lit", "color", "when", "fld", "uni", "tup", "td"]:
            vals[f"mut.{key}"] = txt(page, f"#v-{key}")
        vals["mut.rows"] = [r.inner_text() for r in page.locator(".row").all()]
        vals["mut.fld-items"] = [r.inner_text() for r in page.locator(".fld-item").all()]
        return expect(
            "7" in vals["mut.l_opt"] and "v3" in vals["mut.d_nested"] and vals["mut.ann"] == "6"
            and '"x":11' in vals["mut.point"].replace(" ", "") and "t2" in vals["mut.point"]
            and '"b"' in vals["mut.pm"] and "2026-01-01" in vals["mut.pm"]
            and vals["mut.lit"].strip('"') == "b" and vals["mut.color"].strip('"') == "green" and "2026-10-07" in vals["mut.when"]
            and vals["mut.fld-items"] == ["f1", "f2"] and vals["mut.uni"].strip('"') == "two" and "two" in vals["mut.tup"] and "bee2" in vals["mut.td"]
            and len(vals["mut.rows"]) == 2,
            {k: v for k, v in vals.items() if k.startswith("mut.")},
        )

    sink.check("mutate every shape (incl. in-place dataclass/pydantic/list mutations)", mutate)

    def bg():
        page.click("#bg")
        wait_text(page, "#counter", "3", timeout=20000)
        wait_text(page, "#bg_running", "false", timeout=20000)

    sink.check("background task with async with self", bg)
    sink.check("ABC mixin state event", lambda: (page.click("#greet"), wait_text(page, "#greeting", "hello world")) and True)
    sink.check("postponed-annotation state event", lambda: (page.click("#bump"), wait_text(page, "#f_summary", "[0]|fut|6|green|2030")) and True)
    sink.check("reset Optional back to None", lambda: (page.click("#reset"), wait_text(page, "#o_str", "none"), wait_text(page, "#cond-list", "no list")) and True)
    page.screenshot(path=str(out / f"{label}-mutated.png"), full_page=True)
    page.click("#to-other")
    sink.check("client nav keeps state", lambda: (page.wait_for_selector("#page-other"), wait_text(page, "#other-counter", "3"), wait_text(page, "#other-f_summary", "[0]|fut|6|green|2030")) and True)
    page.reload(wait_until="networkidle")
    sink.check("reload on /other keeps state", lambda: (wait_text(page, "#other-counter", "3", 30000)) or True)
    page2 = ctx.new_page()
    sink.attach(page2, "t2")
    page2.goto(base + "/", wait_until="networkidle")
    # the client token lives in per-tab sessionStorage: a new tab is a fresh state
    sink.check("second tab gets its own fresh state", lambda: (page2.wait_for_selector("#page-shapes"), wait_text(page2, "#counter", "0", 30000), wait_text(page2, "#greeting", "hello")) and True)
    sink.check("first tab still has its state", lambda: (wait_text(page, "#other-counter", "3", 15000)) or True)
    browser.close()

report = sink.dump(out / f"{label}-report.json", label=label, values=vals)
print(summarize(report))

"""Drive formsapp in Chromium: fill every form the same way, submit, record what the handler got.

Usage: drive_forms.py <base_url> <out.json> [--new] [--file /path/to/upload]
Records per form: the handler's record (from pre#results), the socket.io frame that carried the
submit event (raw wire payload), console messages and page errors.
"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = re.compile(r"Hey developer|HydrateFallback|\[vite\]|React DevTools|favicon")


def actions_legacy():
    base = [
        ("fill", "input.rt-TextFieldInput", "em@x"),
        ("fill", "textarea", "ta-text"),
        ("click", "button[role=checkbox]"),
        ("click", "button[role=switch]"),
        ("rselect", "b"),
        ("clicknth", "button[role=radio]", 1),
        ("slide", 0, 5),
    ]
    return {
        "id_only": [*base, ("check", "#io_hcb")],
        "name_only": [*base, ("check", "input[name=hcb]")],
        "id_eq_name": [*base, ("check", "#ien_hcb")],
        "id_ne_name": [
            ("fill", "input.rt-TextFieldInput", "x-typed"),
            ("click", "button[role=checkbox]"),
            ("click", "button[role=switch]"),
            ("check", "#hcbid"),
            ("slide", 0, 5),
        ],
        "groups": [
            ("clicknth", "button[role=checkbox]", 0),
            ("clicknth", "button[role=checkbox]", 2),
            ("check", "input[name=topping][value=cheese]"),
            ("check", "input[name=topping][value=olives]"),
            ("clicknth", "button[role=radio]", 1),
            ("check", "input[name=hr][value=x2]"),
            ("nselect", "select[name=hsel]", ["o1", "o3"]),
        ],
        "group_id_eq_name": [
            ("clicknth", "button[role=checkbox]", 0),
            ("clicknth", "button[role=checkbox]", 2),
            ("check", "#topping"),
            ("check", "input[name=topping][value=olives]"),
        ],
        "sliders": [("slide", 0, 5), ("slide", 1, 3), ("slide", 2, 2), ("slide", 3, 1), ("slide", 4, 1), ("slide", 5, 1), ("slide", 6, 1)],
        "controlled": [
            ("fill", "input[name=ctrl]", "c1-typed"),
            ("fill", "#ctrl2", "c2-typed"),
            ("fill", "#ctrl3", "c3-typed"),
            ("fill", "input[name=ctrl4]", "c4-typed"),
            ("fill", "textarea", "ta-typed"),
            ("wait", 600),
        ],
        "reset": [("fill", "input.rt-TextFieldInput", "will-reset"), ("click", "button[role=checkbox]")],
        "foreach": [],
        "el_form": [],
        "radix_root": [("fill", "input[type=email]", "f@x.io"), ("fill", "input[name=explicit]", "expl")],
        "dynamic": [("click", "button[role=checkbox]")],
        "unannotated": [("click", "button[role=checkbox]")],
        "dict_any": [],
        "lambda": [],
        "chain": [],
        "file": [("file", "input[type=file]")],
        "selects": [("rselect", "i2"), ("nselect", "select[name=hsel_single]", ["o1"]), ("nselect", "#hsel_id", ["o1"]), ("clicknth", "button[role=radio]", 0)],
        "brackets": [],
        "mapping": [],
        "optdict": [],
        "anyarg": [],
    }


def actions_new():
    return {
        "formdata": [
            ("check", "input[name=topping][value=cheese]"),
            ("check", "input[name=topping][value=olives]"),
            ("slide", 0, 2),
            ("slide", 1, 1),
            ("clicknth", "button[role=checkbox]", 0),
            ("clicknth", "button[role=checkbox]", 1),
            ("clicknth", "button[role=checkbox]", 3),
        ],
        "formdata_optional": [],
        "passon": [],
        "typed": [
            ("check", "input[name=toppings][value=cheese]"),
            ("check", "input[name=toppings][value=olives]"),
            ("clicknth", "button[role=checkbox]", 0),  # agree
            ("clicknth", "button[role=switch]", 0),  # sw on; maybe stays off
            ("check", "input[name=opt_list]"),
            ("slide", 0, 1),
            ("slide", 1, 1),
        ],
        "typed_tags": [],
        "typed_generic": [],
        "typed_dynamic": [],
        "cg_controlled": [("clicknth", "button[role=checkbox]", 0), ("wait", 1500)],
    }


def actions_future():
    return {
        "future": [("check", "input[name=toppings]"), ("clicknth", "button[role=checkbox]", 0)],
        "future_fd": [],
    }


EXPECT_SEQ = {"chain": 2, "passon": 4}


def main():
    base = sys.argv[1].rstrip("/")
    out = sys.argv[2]
    new = "--new" in sys.argv
    upload = None
    if "--file" in sys.argv:
        upload = sys.argv[sys.argv.index("--file") + 1]
    report = {"base": base, "pages": {}, "console": [], "errors": [], "ws_sent": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.on("console", lambda m: report["console"].append(f"[{m.type}] {m.text}") if not BENIGN.search(m.text) else None)
        page.on("pageerror", lambda e: report["errors"].append(str(e)))

        def on_ws(ws):
            ws.on("framesent", lambda f: report["ws_sent"].append(f if isinstance(f, str) else f"<binary {len(f)}>"))

        page.on("websocket", on_ws)
        pages = [("/legacy", actions_legacy())]
        if new:
            pages += [("/new", actions_new()), ("/future", actions_future())]
        for route, acts in pages:
            page.goto(base + route)
            page.wait_for_selector("#results", timeout=60000)
            page.wait_for_timeout(1500)
            page_report = {}
            for key, steps in acts.items():
                rec = {"steps": [], "error": None}
                try:
                    box = page.locator(f'[data-form="{key}"]')
                    box.scroll_into_view_if_needed()
                    for step in steps:
                        kind = step[0]
                        if kind == "fill":
                            box.locator(step[1]).first.fill(step[2])
                        elif kind == "click":
                            box.locator(step[1]).first.click()
                        elif kind == "clicknth":
                            box.locator(step[1]).nth(step[2]).click()
                        elif kind == "check":
                            box.locator(step[1]).first.check(force=True)
                        elif kind == "rselect":
                            box.locator("button[role=combobox]").first.click()
                            page.locator("[role=option]", has_text=re.compile(f"^{step[1]}$")).first.click()
                        elif kind == "nselect":
                            box.locator(step[1]).first.select_option(step[2])
                        elif kind == "slide":
                            thumb = box.locator("[role=slider]").nth(step[1])
                            thumb.focus()
                            for _ in range(step[2]):
                                thumb.press("ArrowRight")
                        elif kind == "file":
                            box.locator(step[1]).first.set_input_files(upload or __file__)
                        elif kind == "wait":
                            page.wait_for_timeout(step[1])
                        rec["steps"].append(step)
                    forms = box.locator("form")
                    nforms = forms.count()
                    sent_before = len(report["ws_sent"])
                    for i in range(nforms):
                        seq0 = int(page.locator("#seq").inner_text())
                        want = seq0 + EXPECT_SEQ.get(key, 1)
                        forms.nth(i).locator("button[type=submit]").first.click()
                        deadline = time.time() + 15
                        while time.time() < deadline:
                            if int(page.locator("#seq").inner_text()) >= want:
                                break
                            page.wait_for_timeout(100)
                        else:
                            rec["error"] = f"timeout waiting seq {want} (form {i}) got {page.locator('#seq').inner_text()}"
                    page.wait_for_timeout(300)
                    rec["ws_sent"] = [f for f in report["ws_sent"][sent_before:] if '"event"' in f or "event" in f[:30]]
                    results = json.loads(page.locator("#results").inner_text())
                    rec["results"] = {k: json.loads(v) for k, v in results.items() if k == key or k.startswith(key + "_") or k in ("chain_first", "chain_second", "passon_fd", "passon_dict", "passon_td", "passon_fd2") and key in ("chain", "passon")}
                    if key == "reset":
                        rec["after_reset"] = {
                            "input": box.locator("input.rt-TextFieldInput").first.input_value(),
                            "checkbox": box.locator("button[role=checkbox]").first.get_attribute("aria-checked"),
                        }
                    if key == "cg_controlled":
                        rec["cg_value_text"] = page.locator("#cg_value").inner_text()
                except Exception as e:  # noqa: BLE001
                    rec["error"] = f"{type(e).__name__}: {e}"[:500]
                page_report[key] = rec
            report["pages"][route] = page_report
            page.screenshot(path=out.replace(".json", route.replace("/", "_") + ".png"), full_page=True)
        browser.close()
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
    bad = [(r, k) for r, pr in report["pages"].items() for k, v in pr.items() if v.get("error")]
    print("forms with errors:", bad)
    print("console:", len(report["console"]), "pageerrors:", len(report["errors"]))
    for c in report["console"][:30]:
        print("  ", c[:300])
    for e in report["errors"][:10]:
        print("  ERR", e[:300])


if __name__ == "__main__":
    main()

"""Drive the forms cluster app end-to-end in Chromium and print observed form data.

Usage (from any neutral directory, with the driver venv):

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python test_forms.py http://localhost:3100 <shots_dir> <report.json> [pages...]

Prints each page's observed JSON and a list of console errors/warnings, page
errors, failed requests and 4xx/5xx responses. Exit 1 on any anomaly or
assertion mismatch (mismatches are listed in the report as "mismatches").
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]

base = sys.argv[1].rstrip("/")
shots = Path(sys.argv[2])
shots.mkdir(parents=True, exist_ok=True)
report_path = Path(sys.argv[3])
only = set(sys.argv[4:])

observed: dict[str, object] = {}
mismatches: list[str] = []
console: list[dict] = []
page_errors: list[str] = []
failed: list[dict] = []
bad_status: list[dict] = []


def expect(label: str, cond: bool, detail: object = "") -> None:
    print(("  ok   " if cond else "  MISMATCH ") + label, "" if cond else detail)
    if not cond:
        mismatches.append(f"{label}: {detail}")


def wait_json(page: Page, selector: str, prev: str = "") -> object:
    page.wait_for_function(
        "([sel, prev]) => { const el = document.querySelector(sel); return el && el.innerText.trim() && el.innerText.trim() !== prev; }",
        arg=[selector, prev],
        timeout=15000,
    )
    text = page.inner_text(selector).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def goto(page: Page, path: str) -> None:
    page.goto(f"{base}{path}", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)


def run_index(page: Page) -> None:
    goto(page, "/")
    page.screenshot(path=str(shots / "index-before.png"), full_page=True)
    # Untyped form: check 'remember', toggle switch on, add hobby c, type into second and press Enter.
    page.click("#remember")
    page.click("#dark")
    page.click("text=hobby c")
    page.fill("input[name=second]", "typed-second")
    page.press("input[name=second]", "Enter")
    data = wait_json(page, "#untyped-json")
    observed["index.untyped"] = data
    print("index.untyped:", json.dumps(data))
    page.wait_for_timeout(800)
    observed["index.chained"] = wait_json(page, "#chained-json")
    print("index.chained:", observed["index.chained"])
    observed["index.display"] = page.inner_text("#display")
    observed["index.toast_visible"] = page.locator("text=submitted").count() > 0
    # PR #7386 says id-ref values still replace the same-name entry in 0.10.x (True/False), the
    # changelog says "on"/nothing; record which one the build does.
    observed["index.remember_shape"] = repr(data.get("remember"))
    expect("untyped: remember checked (True per PR text, 'on' per changelog)", data.get("remember") in (True, "on"), data.get("remember"))
    expect("untyped: dark switch checked (True or 'on')", data.get("dark") in (True, "on"), data.get("dark"))
    expect("untyped: hobby is last value 'c' (dict)", data.get("hobby") == "c", data.get("hobby"))
    expect("untyped: second typed", data.get("second") == "typed-second", data.get("second"))
    expect("untyped: pick=='y'", data.get("pick") == "y", data.get("pick"))
    expect("untyped: radio=='r2'", data.get("radio") == "r2", data.get("radio"))
    expect("untyped: group present", "group" in data, data)
    expect("untyped: range keys", "range[]" in data or "range" in data, list(data))
    expect("untyped: toast shown", observed["index.toast_visible"])
    expect("untyped: chained handler got dict with same keys", isinstance(observed["index.chained"], dict) and set(observed["index.chained"]) == set(data), observed["index.chained"])
    # reset_on_submit: the 'second' input should be empty now and count==1
    page.wait_for_timeout(500)
    observed["index.second_after_reset"] = page.input_value("input[name=second]")
    expect("reset_on_submit cleared second", observed["index.second_after_reset"] == "", observed["index.second_after_reset"])
    observed["index.remember_after_reset"] = page.get_attribute("#remember", "aria-checked") or page.get_attribute("#remember", "data-state")
    print("remember after reset:", observed["index.remember_after_reset"])
    page.screenshot(path=str(shots / "index-after-untyped.png"), full_page=True)
    # Second submit via button to check count increments and Enter vs button parity.
    page.click("#untyped-submit")
    page.wait_for_function("() => document.querySelector('#untyped-count').innerText.includes('2')", timeout=15000)
    data2 = json.loads(page.inner_text("#untyped-json"))
    observed["index.untyped_second_submit"] = data2
    print("index.untyped(2):", json.dumps(data2))
    expect("after reset: remember unchecked (False via id ref, or absent)", data2.get("remember") in (False, None), data2.get("remember"))
    expect("after reset: hobby back to default last 'b'", data2.get("hobby") == "b", data2.get("hobby"))
    # dict form with 3 x hobby
    page.click("#dict-submit")
    d = wait_json(page, "#dict-json")
    observed["index.dict"] = d
    print("index.dict:", json.dumps(d))
    expect("dict: hobby last 'h3'", d.get("hobby") == "h3", d)
    # FormData form
    page.click("#fd-submit")
    items = wait_json(page, "#fd-items")
    observed["index.fd_items"] = items
    observed["index.fd_getlist"] = wait_json(page, "#fd-getlist")
    observed["index.fd_dict"] = wait_json(page, "#fd-dict")
    page.wait_for_timeout(800)
    observed["index.fd_chained"] = wait_json(page, "#chained-json")
    print("index.fd_items:", json.dumps(items))
    print("index.fd_getlist:", observed["index.fd_getlist"])
    print("index.fd_dict:", observed["index.fd_dict"])
    print("index.fd_chained:", observed["index.fd_chained"])
    expect("FormData getlist hobby == [h1,h2,h3]", observed["index.fd_getlist"] == ["h1", "h2", "h3"], observed["index.fd_getlist"])
    expect("FormData multi_items in order", [i[1] for i in items if i[0] == "hobby"] == ["h1", "h2", "h3"], items)
    expect("FormData dict() keeps last", observed["index.fd_dict"].get("hobby") == "h3", observed["index.fd_dict"])
    expect("FormData range[] has two entries", len([i for i in items if i[0] == "range[]"]) == 2, items)
    expect("FormData -> dict chained handler has last values", isinstance(observed["index.fd_chained"], dict) and observed["index.fd_chained"].get("hobby") == "h3", observed["index.fd_chained"])
    page.screenshot(path=str(shots / "index-after-all.png"), full_page=True)


def run_typed(page: Page) -> None:
    goto(page, "/typed")
    page.fill("#controlled-input", "ctrl-edited")
    page.wait_for_timeout(400)
    page.click("#typed-submit")
    data = wait_json(page, "#typed-json")
    observed["typed.first"] = data
    observed["typed.types"] = wait_json(page, "#typed-types")
    observed["typed.error"] = page.inner_text("#typed-error")
    print("typed:", json.dumps(data))
    print("typed types:", observed["typed.types"])
    print("typed error:", observed["typed.error"])
    expect("typed: subscribe False (unchecked)", data.get("subscribe") is False, data.get("subscribe"))
    expect("typed: toggled True (switch checked)", data.get("toggled") is True, data.get("toggled"))
    expect("typed: hobby list [h1,h3]", data.get("hobby") == ["h1", "h3"], data.get("hobby"))
    expect("typed: color (Annotated list) == ['blue']", data.get("color") == ["blue"], data.get("color"))
    expect("typed: range == ['10','30'] from range[]", data.get("range") == ["10", "30"], data.get("range"))
    expect("typed: range[] key removed", "range[]" not in data, list(data))
    expect("typed: size 'm'", data.get("size") == "m", data.get("size"))
    expect("typed: bio present", data.get("bio") == "bio text", data.get("bio"))
    expect("typed: missing_opt_list left out", "missing_opt_list" not in data, list(data))
    expect("typed: opt_list None", "opt_list" in data and data["opt_list"] is None, data.get("opt_list", "<absent>"))
    expect("typed: opt_flag None", "opt_flag" in data and data["opt_flag"] is None, data.get("opt_flag", "<absent>"))
    expect("typed: strflag 'false' -> False", data.get("strflag") is False, data.get("strflag"))
    expect("typed: controlled value edited", data.get("controlled") == "ctrl-edited", data.get("controlled"))
    expect("typed: foreach_val [f1,f2,f3]", data.get("foreach_val") == ["f1", "f2", "f3"], data.get("foreach_val"))
    expect("typed: hidden_req (cond-hidden Required str) absent -> KeyError", "KeyError" in observed["typed.error"], observed["typed.error"])
    page.screenshot(path=str(shots / "typed-1.png"), full_page=True)
    # Now check subscribe, show hidden, select 'yes' and resubmit
    page.click("#subscribe")
    page.click("#toggle-hidden")
    page.wait_for_selector("input[name=hidden_req]")
    page.click("#typed-submit")
    data2 = wait_json(page, "#typed-json", prev=json.dumps(data, sort_keys=True))
    observed["typed.second"] = data2
    print("typed(2):", json.dumps(data2))
    expect("typed2: subscribe True", data2.get("subscribe") is True, data2.get("subscribe"))
    expect("typed2: hidden_req present", data2.get("hidden_req") == "now visible", data2.get("hidden_req"))
    page.screenshot(path=str(shots / "typed-2.png"), full_page=True)


def run_future(page: Page) -> None:
    goto(page, "/future")
    page.click("#future-submit")
    data = wait_json(page, "#future-json")
    observed["future"] = data
    observed["future.keys"] = page.inner_text("#future-keys")
    print("future:", json.dumps(data), observed["future.keys"])
    expect("future: title present", data.get("title") == "hello", data.get("title"))
    expect("future: agree True (Annotated bool, Required)", data.get("agree") is True, data.get("agree"))
    expect("future: nickname left out", "nickname" not in data, list(data))
    expect("future: tags (Annotated NotRequired list) left out", "tags" not in data, list(data))
    expect("future: extras None", "extras" in data and data["extras"] is None, data.get("extras", "<absent>"))
    expect("future: maybe_flag None", "maybe_flag" in data and data["maybe_flag"] is None, data.get("maybe_flag", "<absent>"))
    # uncheck agree and resubmit -> False
    page.click("#agree")
    page.click("#future-submit")
    data2 = wait_json(page, "#future-json", prev=json.dumps(data, sort_keys=True))
    observed["future.second"] = data2
    print("future(2):", json.dumps(data2))
    expect("future2: agree False when unchecked", data2.get("agree") is False, data2.get("agree"))
    page.screenshot(path=str(shots / "future.png"), full_page=True)


def run_deprecated(page: Page) -> None:
    goto(page, "/deprecated")
    page.click("#dep-submit")
    data = wait_json(page, "#dep-json")
    observed["deprecated"] = data
    print("deprecated:", json.dumps(data))
    page.screenshot(path=str(shots / "deprecated.png"), full_page=True)


def run_controlled(page: Page) -> None:
    goto(page, "/controlled")
    for sel in ("#ac-email", "#ac-off", "#ac-true", "#ac-false"):
        observed[f"controlled.autocomplete{sel}"] = page.get_attribute(sel, "autocomplete")
        print(sel, "autocomplete=", observed[f"controlled.autocomplete{sel}"])
    expect("autocomplete email", observed["controlled.autocomplete#ac-email"] == "email", observed["controlled.autocomplete#ac-email"])
    expect("autocomplete off", observed["controlled.autocomplete#ac-off"] == "off", observed["controlled.autocomplete#ac-off"])
    expect("autocomplete True->on", observed["controlled.autocomplete#ac-true"] == "on", observed["controlled.autocomplete#ac-true"])
    expect("autocomplete False->off", observed["controlled.autocomplete#ac-false"] == "off", observed["controlled.autocomplete#ac-false"])
    print("cg state initial:", page.inner_text("#cg-state"), "|", page.inner_text("#cc-state"))
    # click checkbox_group item 'a' and 'c', checkbox_cards 'x'
    page.click("#cg-root >> text=a")
    page.wait_for_function("() => document.querySelector('#cg-state').innerText.includes('changes=1')", timeout=10000)
    page.click("#cg-root >> text=c")
    page.wait_for_function("() => document.querySelector('#cg-state').innerText.includes('changes=2')", timeout=10000)
    page.click("#cc-root >> text=x")
    page.wait_for_function("() => document.querySelector('#cc-state').innerText.includes('changes=1')", timeout=10000)
    observed["controlled.cg_state"] = page.inner_text("#cg-state")
    observed["controlled.cc_state"] = page.inner_text("#cc-state")
    print("cg state:", observed["controlled.cg_state"], "|", observed["controlled.cc_state"])
    expect("cg controlled state has a,b,c", set(observed["controlled.cg_state"].split(" ")[0][3:].split(",")) == {"a", "b", "c"}, observed["controlled.cg_state"])
    page.click("#ctrl-submit")
    data = wait_json(page, "#ctrl-json")
    observed["controlled.submit"] = data
    print("controlled submit:", json.dumps(data))
    expect("controlled cg submitted as list of 3", sorted(data.get("cg") or []) == ["a", "b", "c"], data.get("cg"))
    expect("controlled cc submitted [x,y]", sorted(data.get("cc") or []) == ["x", "y"], data.get("cc"))
    expect("radio_cards rc 'q'", data.get("rc") == "q", data.get("rc"))
    page.screenshot(path=str(shots / "controlled.png"), full_page=True)


def run_cs(page: Page) -> None:
    goto(page, "/cs")
    page.click("#flag-alpha")
    page.click("#cs-alpha >> text=Submit alpha")
    page.wait_for_function("() => document.querySelector('#cs-alpha .cs-last').innerText.trim().length > 0", timeout=15000)
    page.click("#cs-beta >> text=c2")
    page.click("#cs-beta >> text=Submit beta")
    page.wait_for_function("() => document.querySelector('#cs-beta .cs-last').innerText.trim().length > 0", timeout=15000)
    a = json.loads(page.inner_text("#cs-alpha .cs-last"))
    b = json.loads(page.inner_text("#cs-beta .cs-last"))
    observed["cs.alpha"] = a
    observed["cs.beta"] = b
    observed["cs.alpha_n"] = page.inner_text("#cs-alpha .cs-n")
    observed["cs.beta_n"] = page.inner_text("#cs-beta .cs-n")
    print("cs alpha:", json.dumps(a), observed["cs.alpha_n"])
    print("cs beta:", json.dumps(b), observed["cs.beta_n"])
    expect("cs alpha item/flag", a.get("item") == "alpha" and a.get("flag") is True and a.get("checks") == ["c1"], a)
    expect("cs beta item/flag/checks", b.get("item") == "beta" and b.get("flag") is False and b.get("checks") == ["c1", "c2"], b)
    expect("cs independent counters", observed["cs.alpha_n"].endswith("1") and observed["cs.beta_n"].endswith("1"), (observed["cs.alpha_n"], observed["cs.beta_n"]))
    page.screenshot(path=str(shots / "cs.png"), full_page=True)


RUNNERS = {
    "index": run_index,
    "typed": run_typed,
    "future": run_future,
    "deprecated": run_deprecated,
    "controlled": run_controlled,
    "cs": run_cs,
}

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_context().new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append({"url": r.url, "failure": str(r.failure)}))
    page.on("response", lambda r: bad_status.append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
    for name, runner in RUNNERS.items():
        if only and name not in only:
            continue
        print(f"=== {name}")
        try:
            runner(page)
        except Exception as exc:
            print(f"  RUNNER FAILED {name}: {type(exc).__name__}: {exc}")
            mismatches.append(f"{name}: runner failed: {type(exc).__name__}: {exc}")
            try:
                page.screenshot(path=str(shots / f"{name}-failed.png"), full_page=True)
            except Exception:
                pass
    browser.close()

shown = [m for m in console if not any(b.search(m["text"]) for b in BENIGN)]
problems = [m for m in shown if m["type"] in ("error", "warning")]
for m in shown:
    print(f"  [console {m['type']}] {m['text'][:400]}")
for e in page_errors:
    print(f"  PAGE ERROR: {e[:400]}")
for f in failed:
    print(f"  REQUEST FAILED: {f}")
for b in bad_status:
    print(f"  HTTP {b['status']}: {b['url']}")
report = {
    "base": base,
    "observed": observed,
    "mismatches": mismatches,
    "console": shown,
    "page_errors": page_errors,
    "failed_requests": failed,
    "http_4xx_5xx": bad_status,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=2, default=str))
clean = not (problems or page_errors or failed or bad_status or mismatches)
print("RESULT:", "clean" if clean else f"ANOMALIES: {len(mismatches)} mismatches, {len(problems)} console problems, {len(page_errors)} page errors")
sys.exit(0 if clean else 1)

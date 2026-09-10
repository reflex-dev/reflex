"""Playwright driver for the hybrid_property test app.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drive_hp.py http://localhost:3140 <shots_dir> <report.json> [--skip-lazy]

Visits every page, performs the user actions, asserts expected text, and records
console messages / page errors / failed requests / 4xx-5xx responses.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]

base = sys.argv[1].rstrip("/")
shots = Path(sys.argv[2]); shots.mkdir(parents=True, exist_ok=True)
report_path = Path(sys.argv[3])
skip_lazy = "--skip-lazy" in sys.argv

results: list[dict] = []
console: list[dict] = []
page_errors: list[str] = []
failed_requests: list[str] = []
bad_responses: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  -- {detail}" if detail else ""), flush=True)


def wait_text(page, selector: str, predicate, timeout=15.0, attr="innerText") -> str:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = page.locator(selector).first.evaluate(f"e => e.{attr}")
        except Exception as e:  # noqa: BLE001
            last = f"<{type(e).__name__}>"
        if predicate(last):
            return last
        time.sleep(0.15)
    return last


def eq(v):
    return lambda t: t == v


def wait_backend(page):
    # the token input is filled once the websocket delivers the client token
    return wait_text(page, "#token", lambda t: bool(t), attr="value")


def texts(page, selector):
    return page.locator(selector).all_inner_texts()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1100, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text, "url": page.url}))
    page.on("pageerror", lambda e: page_errors.append(f"{page.url}: {e}"))
    page.on("requestfailed", lambda r: failed_requests.append(f"{r.method} {r.url} {r.failure}"))
    page.on("response", lambda r: bad_responses.append(f"{r.status} {r.url}") if r.status >= 400 else None)

    # ---------------- core page ----------------
    page.goto(base + "/")
    tok = wait_backend(page)
    check("core.backend_connected", bool(tok), f"token={tok[:8] if tok else tok}")
    page.screenshot(path=str(shots / "core_initial.png"), full_page=True)
    check("core.full_name.frontend", wait_text(page, "#full_name", eq("Ada Lovelace")) == "Ada Lovelace", texts(page, "#full_name"))
    check("core.full_name.backend", wait_text(page, "#full_name_backend", eq("Ada Lovelace")) == "Ada Lovelace", texts(page, "#full_name_backend"))
    check("core.has_last.cond", wait_text(page, "#has_last", eq("has-last")) == "has-last")
    check("core.has_last.backend", wait_text(page, "#has_last_backend", eq("true")) == "true", texts(page, "#has_last_backend"))
    tags = texts(page, ".tag")
    check("core.upper_tags.foreach(staticmethod var fn)", tags == ["ALPHA", "BETA"], str(tags))
    check("core.upper_tags.backend", wait_text(page, "#upper_tags_backend", eq("ALPHA,BETA")) == "ALPHA,BETA", texts(page, "#upper_tags_backend"))
    check("core.scaled.frontend(var fn under own name, x3)", wait_text(page, "#scaled", eq("3")) == "3", texts(page, "#scaled"))
    check("core.scaled.backend(getter x2)", wait_text(page, "#scaled_backend", eq("2")) == "2", texts(page, "#scaled_backend"))
    check("core.secret_len.backend(var fn returns None)", wait_text(page, "#secret_len_backend", eq("6")) == "6", texts(page, "#secret_len_backend"))
    check("core.plain_full.backend", wait_text(page, "#plain_full_backend", eq("Ada/Lovelace")) == "Ada/Lovelace")

    page.click("#btn_rename")
    check("core.setter.frontend_updates", wait_text(page, "#full_name", eq("Grace Hopper")) == "Grace Hopper", texts(page, "#full_name"))
    check("core.setter.backend_updates", wait_text(page, "#full_name_backend", eq("Grace Hopper")) == "Grace Hopper", texts(page, "#full_name_backend"))
    check("core.setter.log", "rename->Grace Hopper" in wait_text(page, "#log", lambda t: "rename->" in t), texts(page, "#log"))
    page.click("#btn_rename_plain")
    check("core.plain_property_setter.frontend", wait_text(page, "#full_name", eq("Alan Turing")) == "Alan Turing", texts(page, "#full_name"))
    check("core.plain_property_setter.backend", wait_text(page, "#plain_full_backend", eq("Alan/Turing")) == "Alan/Turing", texts(page, "#plain_full_backend"))
    page.fill("#rename_input", "Linus Torvalds")
    page.locator("#rename_input").blur()
    check("core.setter.from_input", wait_text(page, "#full_name", eq("Linus Torvalds")) == "Linus Torvalds", texts(page, "#full_name"))
    page.click("#btn_no_setter")
    log = wait_text(page, "#log", lambda t: "no-setter:" in t)
    check("core.assign_without_setter.raises_AttributeError", "no-setter:AttributeError" in log, log)
    page.click("#btn_clear")
    check("core.deleter.frontend", wait_text(page, "#full_name", eq(" "), attr="textContent") == " ", repr(page.locator("#full_name").evaluate("e => e.textContent")))
    check("core.deleter.cond_flips", wait_text(page, "#has_last", eq("no-last")) == "no-last")
    check("core.deleter.backend_bool", wait_text(page, "#has_last_backend", eq("false")) == "false", texts(page, "#has_last_backend"))
    page.click("#btn_inc")
    check("core.inc.frontend_x3", wait_text(page, "#scaled", eq("6")) == "6", texts(page, "#scaled"))
    check("core.inc.backend_x2", wait_text(page, "#scaled_backend", eq("4")) == "4", texts(page, "#scaled_backend"))
    page.click("#btn_add_tag")
    wait_text(page, "#upper_tags_backend", lambda t: "TAG2" in t)
    tags = texts(page, ".tag")
    check("core.add_tag.foreach_updates", tags == ["ALPHA", "BETA", "TAG2"], str(tags))
    page.screenshot(path=str(shots / "core_after.png"), full_page=True)
    page.click("#btn_reset")
    check("core.reset", wait_text(page, "#full_name", eq("Ada Lovelace")) == "Ada Lovelace", texts(page, "#full_name"))

    # ---------------- inherit page ----------------
    page.goto(base + "/inherit")
    wait_backend(page)
    check("inherit.label.frontend(plain base hybrid, annotated on state)", wait_text(page, "#label", eq("reflex!")) == "reflex!", texts(page, "#label"))
    check("inherit.label.backend", wait_text(page, "#label_backend", eq("reflex!")) == "reflex!", texts(page, "#label_backend"))
    check("inherit.shout.frontend(mixin hybrid, annotated)", wait_text(page, "#shout", eq("REFLEX")) == "REFLEX", texts(page, "#shout"))
    check("inherit.shout.backend", wait_text(page, "#shout_backend", eq("REFLEX")) == "REFLEX", texts(page, "#shout_backend"))
    check("inherit.backend_var.default_factory_from_base", wait_text(page, "#cache_hits", eq("0")) == "0", texts(page, "#cache_hits"))
    check("inherit.backend_var.default_from_base", wait_text(page, "#level", eq("7")) == "7", texts(page, "#level"))
    check("inherit.substate.label.frontend", wait_text(page, "#child_label", eq("reflex!")) == "reflex!", texts(page, "#child_label"))
    check("inherit.substate.label.backend", wait_text(page, "#child_label_backend", eq("reflex!child")) == "reflex!child", texts(page, "#child_label_backend"))
    check("inherit.sibling.own_var_fn.frontend", wait_text(page, "#sibling_label", eq("bee?")) == "bee?", texts(page, "#sibling_label"))
    check("inherit.sibling.getter_unchanged.backend", wait_text(page, "#sibling_label_backend", eq("bee!")) == "bee!", texts(page, "#sibling_label_backend"))
    page.click("#btn_hit")
    check("inherit.backend_var.mutation", wait_text(page, "#cache_hits", eq("1")) == "1", texts(page, "#cache_hits"))
    check("inherit.backend_var.level_incr", wait_text(page, "#level", eq("8")) == "8", texts(page, "#level"))
    page.click("#btn_set_label")
    check("inherit.inherited_setter", wait_text(page, "#label", eq("pynecone!")) == "pynecone!", texts(page, "#label"))
    check("inherit.inherited_setter.substate", wait_text(page, "#child_label", eq("pynecone!")) == "pynecone!", texts(page, "#child_label"))
    page.screenshot(path=str(shots / "inherit.png"), full_page=True)

    # ---------------- combo page ----------------
    page.goto(base + "/combo")
    wait_backend(page)
    check("combo.full_label", wait_text(page, "#full_label", eq("a-b")) == "a-b", texts(page, "#full_label"))
    check("combo.doubled", wait_text(page, "#doubled", eq("6")) == "6", texts(page, "#doubled"))
    check("combo.computed_var_depends_on_hybrid", wait_text(page, "#summary", eq("A-B#6")) == "A-B#6", texts(page, "#summary"))
    check("combo.memo_props_bound_to_hybrid", wait_text(page, "#memo_badge", eq("a-b:6")) == "a-b:6", texts(page, "#memo_badge"))
    check("combo.client_state_alongside", wait_text(page, "#mixed", eq("a-b / note")) == "a-b / note", texts(page, "#mixed"))
    page.fill("#note_input", "hi")
    check("combo.client_state_update", wait_text(page, "#mixed", eq("a-b / hi")) == "a-b / hi", texts(page, "#mixed"))
    page.click("#btn_set_first")
    check("combo.dep_tracking.first->summary", wait_text(page, "#summary", eq("ZZ-B#6")) == "ZZ-B#6", texts(page, "#summary"))
    check("combo.memo_updates", wait_text(page, "#memo_badge", eq("zz-b:6")) == "zz-b:6", texts(page, "#memo_badge"))
    page.click("#btn_inc_n")
    check("combo.dep_tracking.n->summary", wait_text(page, "#summary", eq("ZZ-B#8")) == "ZZ-B#8", texts(page, "#summary"))
    page.click("#btn_bg")
    check("combo.background_setter", wait_text(page, "#full_label", eq("bg-task")) == "bg-task", texts(page, "#full_label"))
    check("combo.background_setter.summary", wait_text(page, "#summary", eq("BG-TASK#20")) == "BG-TASK#20", texts(page, "#summary"))
    log = wait_text(page, "#log", lambda t: "doubled=" in t)
    check("combo.background_getter_log", "bg:bg-task | bg:doubled=20" == log, log)
    # component state x2
    disp = texts(page, ".cs_display"); nxt = texts(page, ".cs_next"); dispb = texts(page, ".cs_display_backend")
    check("combo.component_state.initial", disp == ["count=0", "count=0"] and nxt == ["2", "2"] and dispb == ["count=0", "count=0"], f"{disp} {nxt} {dispb}")
    page.locator(".cs_bump").nth(0).click()
    wait_text(page, "#c1 .cs_display", eq("count=1"))
    disp = texts(page, ".cs_display"); nxt = texts(page, ".cs_next"); dispb = texts(page, ".cs_display_backend")
    check("combo.component_state.independent", disp == ["count=1", "count=0"] and nxt == ["3", "2"] and dispb == ["count=1", "count=0"], f"{disp} {nxt} {dispb}")
    page.locator(".cs_jump").nth(1).click()
    wait_text(page, "#c2 .cs_display", eq("count=8"))
    disp = texts(page, ".cs_display"); nxt = texts(page, ".cs_next")
    check("combo.component_state.setter", disp == ["count=1", "count=8"] and nxt == ["3", "10"], f"{disp} {nxt}")
    page.screenshot(path=str(shots / "combo.png"), full_page=True)

    # ---------------- dc page ----------------
    page.goto(base + "/dc")
    wait_backend(page)
    check("dc.initial", wait_text(page, "#pt", eq("pt=(1,2)")) == "pt=(1,2)" and texts(page, "#fz") == ["fz=(f,1)"], f"{texts(page, '#pt')} {texts(page, '#fz')}")
    page.click("#btn_inspect")
    wait_text(page, "#checks", lambda t: "replace" in t)
    checks = {}
    for row in texts(page, ".check"):
        k, _, v = row.partition(" = ")
        checks[k] = v
    errors = texts(page, "#errors")
    check("dc.inspect.no_errors", errors == [""], str(errors))
    for name, frozen in (("pt", "False"), ("fz", "True"), ("shape", "False"), ("shape0", "False")):
        check(f"dc.{name}.is_dataclass", checks.get(f"{name}.is_dataclass") == "True", checks.get(f"{name}.is_dataclass"))
        check(f"dc.{name}.type_is_dataclass", checks.get(f"{name}.type_is_dataclass") == "True", checks.get(f"{name}.type_is_dataclass"))
        check(f"dc.{name}.__dataclass_params__.frozen", checks.get(f"{name}.frozen") == frozen, checks.get(f"{name}.frozen"))
        check(f"dc.{name}.__dataclass_params__.eq", checks.get(f"{name}.eq") == "True", checks.get(f"{name}.eq"))
        check(f"dc.{name}.__match_args__", (checks.get(f"{name}.match_args") or "").startswith("("), checks.get(f"{name}.match_args"))
        check(f"dc.{name}.fields", not (checks.get(f"{name}.fields") or "ERR").startswith("ERR"), checks.get(f"{name}.fields"))
        check(f"dc.{name}.asdict", not (checks.get(f"{name}.asdict") or "ERR").startswith("ERR"), checks.get(f"{name}.asdict"))
        check(f"dc.{name}.astuple", not (checks.get(f"{name}.astuple") or "ERR").startswith("ERR"), checks.get(f"{name}.astuple"))
        check(f"dc.{name}.proxy_type", checks.get(f"{name}.proxy_type", ""), checks.get(f"{name}.proxy_type"))
    check("dc.match_pt", checks.get("match_pt") == "1,2", checks.get("match_pt"))
    check("dc.match_fz", checks.get("match_fz") == "f/1", checks.get("match_fz"))
    check("dc.match_nested_x", checks.get("match_nested_x") == "1", checks.get("match_nested_x"))
    check("dc.replace", checks.get("replace") == "pt.x=11 fz.n=2", checks.get("replace"))
    check("dc.replace.ui", wait_text(page, "#pt", eq("pt=(11,2)")) == "pt=(11,2)" and wait_text(page, "#fz", eq("fz=(f,2)")) == "fz=(f,2)", f"{texts(page, '#pt')} {texts(page, '#fz')}")
    page.click("#btn_mutate")
    wait_text(page, "#pt", eq("pt=(11,3)"))
    spts = texts(page, ".spt"); s0 = texts(page, ".s0pt")
    check("dc.mutate_nested.ui", spts == ["(1,0)", "(1,1)", "(9,9)"] and s0 == ["(5,5)", "(6,11)"] and texts(page, "#pt") == ["pt=(11,3)"], f"{spts} {s0} {texts(page, '#pt')}")
    page.click("#btn_frozen")
    wait_text(page, "#checks", lambda t: "frozen_setattr" in t)
    checks = {}
    for row in texts(page, ".check"):
        k, _, v = row.partition(" = ")
        checks[k] = v
    check("dc.frozen_stays_frozen", checks.get("frozen_setattr") == "FrozenInstanceError", checks.get("frozen_setattr"))
    page.screenshot(path=str(shots / "dc.png"), full_page=True)
    json.dump(checks, open(shots.parent / "logs" / "dc_checks.json", "w"), indent=1) if (shots.parent / "logs").exists() else None

    # ---------------- fwd page ----------------
    page.goto(base + "/fwd")
    wait_backend(page)
    check("fwd.banner", wait_text(page, "#banner", eq("fwd:fwd")) == "fwd:fwd", texts(page, "#banner"))
    check("fwd.weighted_name(computed var over unresolvable dataclass)", wait_text(page, "#weighted_name", eq("w")) == "w", texts(page, "#weighted_name"))
    page.click("#btn_add")
    check("fwd.add", wait_text(page, "#item_count", eq("1")) == "1" and wait_text(page, "#current", eq("i0/t0")) == "i0/t0", f"{texts(page, '#item_count')} {texts(page, '#current')}")
    page.click("#btn_async_add")
    check("fwd.async_add", wait_text(page, "#item_count", eq("2")) == "2" and texts(page, ".item") == ["i0", "i1"], f"{texts(page, '#item_count')} {texts(page, '.item')}")
    page.screenshot(path=str(shots / "fwd.png"), full_page=True)

    if not skip_lazy:
        page.goto(base + "/lazy")
        wait_backend(page)
        check("lazy.initial", wait_text(page, "#item_count", eq("0")) == "0" and texts(page, "#weighted_name") == ["lw"], f"{texts(page, '#item_count')} {texts(page, '#weighted_name')}")
        page.click("#btn_add")
        check("lazy.add", wait_text(page, "#item_count", eq("1")) == "1" and texts(page, ".item") == ["l0/lt"], f"{texts(page, '#item_count')} {texts(page, '.item')}")
        page.screenshot(path=str(shots / "lazy.png"), full_page=True)

    browser.close()

shown = [m for m in console if not any(b.search(m["text"]) for b in BENIGN)]
problems = [m for m in shown if m["type"] in ("error", "warning")]
report = {
    "base": base,
    "results": results,
    "n_pass": sum(r["ok"] for r in results),
    "n_fail": sum(not r["ok"] for r in results),
    "console_non_benign": shown,
    "console_problems": problems,
    "page_errors": page_errors,
    "failed_requests": failed_requests,
    "bad_responses": bad_responses,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(report, indent=1))
print(f"\n{report['n_pass']} passed, {report['n_fail']} failed; console problems={len(problems)} page_errors={len(page_errors)} failed_requests={len(failed_requests)} bad_responses={len(bad_responses)}")
for m in problems:
    print("CONSOLE", m["type"], m["text"][:300])
for e in page_errors:
    print("PAGEERROR", e[:300])
for r in failed_requests + bad_responses:
    print("NET", r[:300])
sys.exit(0 if report["n_fail"] == 0 and not problems and not page_errors else 1)

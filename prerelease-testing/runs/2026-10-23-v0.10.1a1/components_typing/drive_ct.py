"""Drive the ctapp pages in Chromium and record per-check results plus console/network anomalies.

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_ct.py --base http://localhost:3240 --out results/dev_new.json \
      --shots shots/dev_new [--pages cbg,moment]

Each page runs in a fresh browser context (timezone America/New_York). Every check is
{"page", "name", "ok", "detail"}; per page the raw console messages, page errors, failed
requests and 4xx/5xx responses are kept so a failing check can be read with its context.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
    re.compile(r"favicon\.ico"),
]


def benign(text: str) -> bool:
    return any(p.search(text) for p in BENIGN)


class Run:
    def __init__(self, base: str, shots: Path):
        self.base = base.rstrip("/")
        self.shots = shots
        self.shots.mkdir(parents=True, exist_ok=True)
        self.checks: list[dict] = []
        self.pages: dict[str, dict] = {}
        self.is_new: bool | None = None

    def check(self, page: str, name: str, ok: bool, detail: str = ""):
        self.checks.append({"page": page, "name": name, "ok": bool(ok), "detail": str(detail)[:600]})
        print(f"  [{'ok ' if ok else 'FAIL'}] {page}/{name}: {str(detail)[:200]}")

    def open(self, browser, name: str, route: str | None = None) -> Page:
        ctx = browser.new_context(timezone_id="America/New_York", locale="en-US", viewport={"width": 1100, "height": 1600})
        page = ctx.new_page()
        rec = {"console": [], "pageerrors": [], "failed": [], "http": []}
        self.pages[name] = rec
        page.on("console", lambda m: rec["console"].append({"type": m.type, "text": m.text[:1500]}))
        page.on("pageerror", lambda e: rec["pageerrors"].append(str(e)[:1500]))
        page.on("requestfailed", lambda r: rec["failed"].append({"url": r.url, "failure": str(r.failure)}))
        page.on("response", lambda r: rec["http"].append({"url": r.url, "status": r.status}) if r.status >= 400 else None)
        page.goto(f"{self.base}/{route if route is not None else name}", wait_until="networkidle", timeout=90000)
        try:
            page.wait_for_selector("#is-new", timeout=30000)
            txt = page.inner_text("#is-new")
            self.is_new = "NEW=True" in txt
        except Exception as e:  # noqa: BLE001
            self.check(name, "page_loaded", False, f"#is-new missing: {e}")
        page.wait_for_timeout(800)
        return page

    def shot(self, page: Page, name: str):
        try:
            page.screenshot(path=str(self.shots / f"{name}.png"), full_page=True)
        except Exception:  # noqa: BLE001
            pass


def wait_text(page: Page, sel: str, pred, timeout=8000):
    deadline = time.time() + timeout / 1000
    last = "<missing>"
    while time.time() < deadline:
        try:
            last = page.inner_text(sel)
        except Exception:  # noqa: BLE001
            last = "<missing>"
        if pred(last):
            return True, last
        page.wait_for_timeout(150)
    return False, last


def eq(page: Page, sel: str, expected: str, timeout=8000):
    return wait_text(page, sel, lambda t: t.strip() == expected, timeout)


def contains(page: Page, sel: str, needle: str, timeout=8000):
    return wait_text(page, sel, lambda t: needle in t, timeout)


def attr(page: Page, sel: str, name: str):
    try:
        return page.get_attribute(sel, name, timeout=3000)
    except Exception:  # noqa: BLE001
        return "<missing>"


def t_cbg(page: Page, R: Run):
    P = "cbg"
    ok, t = eq(page, "#group-value", "group=a")
    R.check(P, "initial_group_value", ok, t)
    boxes = page.locator("#cg [role=checkbox]")
    R.check(P, "group_items_rendered", boxes.count() == 3, f"count={boxes.count()}")
    R.check(P, "item_a_checked", attr(page, "#cg [role=checkbox] >> nth=0", "aria-checked") == "true", attr(page, "#cg [role=checkbox] >> nth=0", "aria-checked"))
    b_dis = attr(page, "#cg [role=checkbox] >> nth=1", "disabled")
    R.check(P, "item_b_disabled_attr", b_dis is not None and b_dis != "<missing>", f"disabled={b_dis!r} data-disabled={attr(page, '#cg [role=checkbox] >> nth=1', 'data-disabled')!r}")
    hidden = page.locator("#cg-form input[name=grp]").count()
    R.check(P, "hidden_inputs_named_grp", hidden >= 1, f"count={hidden}")
    if not R.is_new:
        R.check(P, "controlled_skipped_on_prev", True, "prev: no value/on_value_change")
    else:
        page.click("#cg [role=checkbox] >> nth=2")
        ok, t = eq(page, "#group-value", "group=a,c")
        R.check(P, "click_c_updates_state", ok, t)
        ok, t = eq(page, "#group-payload", 'payload=["a", "c"]')
        R.check(P, "on_value_change_payload_list", ok, t)
        ok, t = eq(page, "#group-changes", "group_changes=1")
        R.check(P, "one_change_event", ok, t)
        try:
            page.click("#cg [role=checkbox] >> nth=1", force=True, timeout=2000)
        except Exception as e:  # noqa: BLE001
            pass
        page.wait_for_timeout(500)
        ok, t = eq(page, "#group-value", "group=a,c", timeout=1500)
        R.check(P, "disabled_item_click_ignored", ok, t)
        page.click("#cg-reset")
        ok, t = eq(page, "#group-value", "group=")
        R.check(P, "server_reset_state", ok, t)
        page.wait_for_timeout(300)
        states = [attr(page, f"#cg [role=checkbox] >> nth={i}", "aria-checked") for i in range(3)]
        R.check(P, "server_reset_reaches_dom", states == ["false", "false", "false"], str(states))
        page.click("#cg-preset")
        ok, t = eq(page, "#group-value", "group=a,c")
        page.wait_for_timeout(300)
        states = [attr(page, f"#cg [role=checkbox] >> nth={i}", "aria-checked") for i in range(3)]
        R.check(P, "server_preset_reaches_dom", ok and states == ["true", "false", "true"], f"{t} {states}")
        page.click("#cg-toggle")
        ok, t = eq(page, "#group-disabled", "disabled=true")
        page.wait_for_timeout(300)
        dis = [attr(page, f"#cg [role=checkbox] >> nth={i}", "disabled") for i in range(3)]
        R.check(P, "root_disabled_var_disables_items", ok and all(d not in (None, "<missing>") for d in dis), f"{t} disabled attrs={dis}")
        try:
            page.click("#cg [role=checkbox] >> nth=0", force=True, timeout=2000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(400)
        ok, t = eq(page, "#group-value", "group=a,c", timeout=1000)
        R.check(P, "root_disabled_blocks_clicks", ok, t)
        page.click("#cg-toggle")
        eq(page, "#group-disabled", "disabled=false")
        # cards: the whole card is a <label> that intercepts the pointer, so click it.
        html = page.evaluate("() => { const e = document.getElementById('cc'); return e ? e.outerHTML.slice(0, 1200) : '<missing>' }")
        R.check(P, "info_cards_dom", True, html)
        # Start from an empty cards selection (preset above set ["x", "z"]).
        page.click("#cg-reset")
        eq(page, "#cards-value", "cards=")
        page.click("#cg-preset")
        eq(page, "#group-value", "group=a,c")
        page.click("#cg-reset")
        eq(page, "#cards-value", "cards=")
        page.wait_for_timeout(300)
        # The card <label> wraps a hidden button[role=checkbox]; force-click the button itself.
        page.click("#cc button[value=z]", force=True)
        ok, t = contains(page, "#cards-value", "z")
        R.check(P, "cards_click_z", ok, t)
        page.click("#cc button[value=x]", force=True)
        ok, t = wait_text(page, "#cards-value", lambda s: "x" in s and "z" in s)
        R.check(P, "cards_click_x_keeps_z", ok, t)
        ok, t = eq(page, "#cards-changes", "cards_changes=2")
        R.check(P, "cards_two_change_events", ok, t)
        y_dis = attr(page, "#cc [role=checkbox] >> nth=1", "disabled")
        R.check(P, "card_y_disabled", y_dis not in (None, "<missing>"), f"disabled={y_dis!r}")
    d2 = attr(page, "#cg-default [role=checkbox] >> nth=1", "aria-checked")
    R.check(P, "default_value_group_checked", d2 == "true", f"D2 aria-checked={d2}")
    page.click("#cg-submit")
    ok, t = wait_text(page, "#submitted", lambda s: "grp" in s)
    R.check(P, "form_submit_includes_group", ok, t)
    if R.is_new:
        R.check(P, "form_submit_all_values", '"grp": ["a", "c"]' in t and '"dgrp": ["d2"]' in t and '"cards": [' in t and '"x"' in t.split('"cards"')[1][:30] and '"z"' in t.split('"cards"')[1][:30], t)
    R.check(P, "info_id_based_keys_in_submit", True, f"id keys present: cg={'\"cg\"' in t} cc={'\"cc\"' in t} cg_default={'\"cg_default\"' in t} :: {t}")
    R.shot(page, "cbg")


def t_radio(page: Page, R: Run):
    P = "radio"
    radios = page.locator("#rc [role=radio]")
    R.check(P, "radio_cards_rendered", radios.count() == 3, f"count={radios.count()}")
    page.click("#rc [role=radio] >> nth=1")
    ok, t = eq(page, "#rc-value", "rc=2")
    R.check(P, "radio_cards_controlled_change", ok, t)
    R.check(P, "radio_two_checked", attr(page, "#rc [role=radio] >> nth=1", "aria-checked") == "true", attr(page, "#rc [role=radio] >> nth=1", "aria-checked"))


def t_radio_aschild(page: Page, R: Run):
    P = "radio_aschild"
    ok, t = eq(page, "#rc-aschild-ok", "aschild page loaded", timeout=5000)
    R.check(P, "page_renders", ok, t)
    n = page.locator("#rc-aschild [role=radio]").count()
    R.check(P, "three_radios_rendered", n == 3, f"count={n}")
    grid = page.evaluate("() => { const e = document.querySelector('#rc-aschild'); return e ? getComputedStyle(e).display : null }")
    R.check(P, "root_grid_container_present", grid == "grid", f"display={grid}")
    errs = R.pages[P]["pageerrors"]
    R.check(P, "no_page_errors", not errs, str(errs)[:300])
    R.shot(page, "radio_aschild")


def t_input(page: Page, R: Run):
    P = "input"

    def ac(id_):
        v = page.evaluate("(id) => { const e = document.getElementById(id); if (!e) return '<missing>'; const i = e.tagName === 'INPUT' ? e : e.querySelector('input'); return i ? i.getAttribute('autocomplete') : '<no input>' }", id_)
        return v

    expectations = {"ac-true": "on", "ac-false": "off", "ac-boolvar": "off", "ac-none": None, "ac-el": "off"}
    if R.is_new:
        expectations.update({"ac-off": "off", "ac-email": "email", "ac-strvar": "email", "ac-controlled": "off"})
    for id_, exp in expectations.items():
        got = ac(id_)
        R.check(P, f"autocomplete_{id_}", got == exp, f"expected={exp!r} got={got!r}")
    page.click("#ac-toggle")
    ok, t = eq(page, "#ac-bool", "ac_bool=true")
    page.wait_for_timeout(300)
    got = ac("ac-boolvar")
    R.check(P, "autocomplete_boolvar_toggles_to_on", ok and got == "on", f"{t} got={got!r}")
    if R.is_new:
        page.fill("input#ac-controlled", "hello")
        ok, t = eq(page, "#typed", "typed=hello")
        R.check(P, "controlled_input_roundtrip", ok, t)


def t_progress(page: Page, R: Run):
    P = "progress"

    def aria(id_):
        return page.evaluate("(id) => { const e = document.getElementById(id); if (!e) return null; return {now: e.getAttribute('aria-valuenow'), max: e.getAttribute('aria-valuemax'), state: e.getAttribute('data-state'), value: e.getAttribute('data-value'), role: e.getAttribute('role')} }", id_)

    a = aria("prim-progress")
    R.check(P, "primitive_root_aria_initial", a and a["now"] == "25" and a["max"] == "100", str(a))
    R.check(P, "primitive_root_role_progressbar", a and a["role"] == "progressbar", str(a))
    lit = aria("prim-progress-lit")
    R.check(P, "primitive_literal_aria", lit and lit["now"] == "60" and lit["max"] == "200", str(lit))
    dflt = aria("prim-progress-default")
    R.check(P, "primitive_default_aria", dflt and dflt["now"] == "0" and dflt["max"] == "100", str(dflt))
    th = aria("themes-progress")
    R.check(P, "themes_progress_aria", th and th["now"] == "25", str(th))
    page.click("#bump")
    ok, t = eq(page, "#pv", "pv=50")
    page.wait_for_timeout(300)
    a2 = aria("prim-progress")
    R.check(P, "primitive_root_aria_updates", ok and a2 and a2["now"] == "50", f"{t} {a2}")
    th2 = aria("themes-progress")
    R.check(P, "themes_progress_aria_updates", th2 and th2["now"] == "50", str(th2))
    tr = page.evaluate("() => { const e = document.querySelector('#prim-progress > *'); return e ? getComputedStyle(e).transform : null }")
    R.check(P, "primitive_indicator_transform", bool(tr and tr != "none"), str(tr))
    R.shot(page, "progress")


def t_accordion(page: Page, R: Run):
    P = "accordion"
    console = R.pages[P]["console"]
    emo = [m for m in console if "first-child" in m["text"] and ("emotion" in m["text"].lower() or "pseudo class" in m["text"].lower() or "server-rendered" in m["text"].lower())]
    R.check(P, "no_emotion_first_child_warning", not emo, emo[0]["text"][:200] if emo else "none")
    trig = page.locator("#acc button[data-state]")
    R.check(P, "triggers_rendered", trig.count() == 3, f"count={trig.count()}")
    page.click("#acc button[data-state] >> nth=0")
    page.wait_for_timeout(400)
    s0 = attr(page, "#acc button[data-state] >> nth=0", "data-state")
    page.click("#acc button[data-state] >> nth=1")
    page.wait_for_timeout(400)
    s = [attr(page, f"#acc button[data-state] >> nth={i}", "data-state") for i in range(3)]
    R.check(P, "multiple_two_open", s0 == "open" and s[:2] == ["open", "open"], str(s))
    ok, t = contains(page, "#acc", "M first content")
    R.check(P, "content_visible", ok, t[:80])
    page.click("#acc-ghost button[data-state] >> nth=0")
    page.wait_for_timeout(300)
    page.click("#acc-ghost button[data-state] >> nth=1")
    page.wait_for_timeout(400)
    g = [attr(page, f"#acc-ghost button[data-state] >> nth={i}", "data-state") for i in range(3)]
    R.check(P, "single_only_one_open", g == ["closed", "open", "closed"], str(g))
    sf = attr(page, "#acc-surface button[data-state] >> nth=1", "data-state")
    R.check(P, "default_value_open", sf == "open", str(sf))
    styles = page.evaluate("""() => { const items = document.querySelectorAll('#acc > [data-state]'); return Array.from(items).map(e => { const cs = getComputedStyle(e); return {btw: cs.borderTopWidth, tl: cs.borderTopLeftRadius, mt: cs.marginTop} }) }""")
    R.check(P, "first_item_styled_first_of_type", len(styles) == 3 and styles[0]["mt"] == "0px" and styles[0]["tl"] not in ("0px", "") and styles[1]["mt"] == "1px" and styles[1]["tl"] == "0px", str(styles))
    page.focus("#acc button[data-state] >> nth=0")
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(200)
    active = page.evaluate("() => document.activeElement && document.activeElement.textContent")
    R.check(P, "keyboard_arrow_down_moves_focus", bool(active and "Second" in active), str(active))
    R.shot(page, "accordion")


def t_dialog(page: Page, R: Run):
    P = "dialog"
    page.click("#open-dialog")
    page.wait_for_selector("#outer-content", state="visible", timeout=5000)
    ok, t = eq(page, "#dialog-open", "open=true")
    R.check(P, "dialog_opens_controlled", ok, t)
    inside = []
    for _ in range(7):
        page.keyboard.press("Tab")
        inside.append(page.evaluate("() => !!document.activeElement.closest('#outer-content')"))
    R.check(P, "focus_trapped_in_dialog", all(inside), str(inside))
    page.click("#open-nested")
    page.wait_for_selector("#nested-content", state="visible", timeout=5000)
    R.check(P, "nested_dialog_opens", page.locator("#nested-content").is_visible() and page.locator("#outer-content").count() == 1, "")
    page.fill("#nested-input", "n")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    R.check(P, "escape_closes_only_nested", page.locator("#nested-content").count() == 0 and page.locator("#outer-content").is_visible(), f"nested={page.locator('#nested-content').count()} outer_visible={page.locator('#outer-content').is_visible()}")
    ok, t = eq(page, "#dialog-open", "open=true", timeout=1500)
    R.check(P, "outer_state_still_open", ok, t)
    page.click("#close-dialog")
    page.wait_for_timeout(500)
    ok, t = eq(page, "#dialog-open", "open=false")
    R.check(P, "close_button_updates_state", ok and page.locator("#outer-content").count() == 0, f"{t} count={page.locator('#outer-content').count()}")
    page.click("#open-dialog")
    page.wait_for_selector("#outer-content", state="visible", timeout=5000)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    ok, t = eq(page, "#dialog-open", "open=false")
    R.check(P, "escape_closes_outer", ok and page.locator("#outer-content").count() == 0, t)
    ok, t = eq(page, "#dialog-opens", "opens=2")
    R.check(P, "open_count", ok, t)
    page.click("#open-alert")
    page.wait_for_selector("#alert-content", state="visible", timeout=5000)
    page.click("#alert-cancel")
    page.wait_for_timeout(400)
    R.check(P, "alert_dialog_open_cancel", page.locator("#alert-content").count() == 0, "")
    page.click("#open-drawer")
    page.wait_for_selector("#drawer-content", state="visible", timeout=5000)
    R.check(P, "drawer_opens", True, "")
    page.click("#close-drawer")
    page.wait_for_timeout(700)
    R.check(P, "drawer_closes", page.locator("#drawer-content").count() == 0 or not page.locator("#drawer-content").is_visible(), "")
    page.click("#open-popover")
    page.wait_for_selector("#popover-body", state="visible", timeout=5000)
    R.check(P, "popover_opens", True, "")
    page.keyboard.press("Escape")
    R.shot(page, "dialog")


def t_slider(page: Page, R: Run):
    P = "slider"
    thumb = "#slider-single [role=slider]"
    R.check(P, "single_thumb_initial", attr(page, thumb, "aria-valuenow") == "50", attr(page, thumb, "aria-valuenow"))
    page.focus(thumb)
    for _ in range(3):
        # Controlled slider: each press must round-trip through the backend first.
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(400)
    page.wait_for_timeout(300)
    R.check(P, "single_keyboard_dom", attr(page, thumb, "aria-valuenow") == "53", attr(page, thumb, "aria-valuenow"))
    ok, t = eq(page, "#single-value", "single=53")
    R.check(P, "single_on_change_state", ok, t)
    ok, t = eq(page, "#committed-value", "committed=53")
    R.check(P, "single_on_value_commit", ok, t)
    thumbs = page.locator("#slider-range [role=slider]")
    R.check(P, "range_two_thumbs", thumbs.count() == 2, f"count={thumbs.count()}")
    page.focus("#slider-range [role=slider] >> nth=1")
    page.keyboard.press("ArrowLeft")
    page.wait_for_timeout(300)
    ok, t = eq(page, "#range-value", "range=20,79")
    R.check(P, "range_on_change", ok, t)
    # Radix: Home always moves thumb 0 to min (updateValues(min, 0)), whichever thumb is focused.
    page.keyboard.press("Home")
    page.wait_for_timeout(400)
    v0 = attr(page, "#slider-range [role=slider] >> nth=0", "aria-valuenow")
    ok, t = eq(page, "#range-value", "range=0,79")
    R.check(P, "range_home_moves_first_thumb", ok and v0 == "0", f"{t} thumb0={v0}")
    box = page.locator("#slider-single").bounding_box()
    if box:
        page.mouse.click(box["x"] + box["width"] * 0.1, box["y"] + box["height"] / 2)
        page.wait_for_timeout(400)
        ok, t = wait_text(page, "#single-value", lambda s: s != "single=53")
        R.check(P, "single_mouse_click_track", ok, t)
    R.shot(page, "slider")


def t_rform(page: Page, R: Run):
    P = "rform"
    page.click("#f-submit")
    ok, t = contains(page, "#rform", "Email is required")
    R.check(P, "value_missing_message", ok, t[:120])
    ok, t = eq(page, "#f-submits", "submits=0", timeout=1000)
    R.check(P, "invalid_not_submitted", ok, t)
    page.fill("input#f-email", "nope")
    page.click("#f-submit")
    ok, t = contains(page, "#rform", "Not an email")
    R.check(P, "type_mismatch_message", ok, t[:120])
    page.fill("input#f-email", "a@b.co")
    page.fill("input#f-age", "10")
    page.click("#f-submit")
    ok, t = contains(page, "#rform", "Must be 18+")
    R.check(P, "range_underflow_message", ok, t[:120])
    page.fill("input#f-age", "21")
    page.click("#f-submit")
    ok, t = wait_text(page, "#f-data", lambda s: "a@b.co" in s and "21" in s)
    R.check(P, "valid_submit_reaches_state", ok, t)
    page.wait_for_timeout(400)
    v = page.input_value("input#f-email")
    R.check(P, "reset_on_submit", v == "", f"email value after submit={v!r}")
    R.shot(page, "rform")


def t_moment(page: Page, R: Run):
    P = "moment"
    exp = {
        "plain": "Thursday 14 March 2024",
        "plain2": "Thursday 14 March 2024",
        "english": "Thursday 14 March 2024",
        "french": "jeudi 14 mars 2024",
        "titled": "Thursday 14 March 2024",
    }
    for id_, e in exp.items():
        ok, t = eq(page, f"#{id_}", e)
        R.check(P, f"cmp11_{id_}", ok, t)
    ok, t = wait_text(page, "#fromnow", lambda s: "years ago" in s)
    R.check(P, "cmp11_fromnow_english", ok, t)
    R.check(P, "with_title_attr", bool(attr(page, "#titled", "title")), str(attr(page, "#titled", "title")))
    console = R.pages[P]["console"]
    dl = [m for m in console if "defineLocale" in m["text"]]
    R.check(P, "info_defineLocale_warnings", True, f"{len(dl)} defineLocale messages (CMP-14 known)")
    if not R.is_new:
        R.check(P, "provider_skipped_on_prev", True, "")
        return
    exp2 = {
        "prov-default": "14 mars 2024",
        "prov-en": "14 Mar 2024",
        "prov-fmt": "2024",
        "prov-tz": "2024-03-15 00:30",
        "outside": "14 Mar 2024",
        "prov-var": "Donnerstag",
        "prov-var-fr": "jeudi",
        "utc": "2024-03-14 23:30",
        "noutc": "2024-03-14 19:30",
        "calendar": "03/14/2024",
        "from": "in 4 days",
        "from-ago": "4 days",
        "to": "in 6 days",
        "element": "2024",
        "fallback": "INVALID",
        "filters": "MARCH",
        "renderers": "R:2024",
        "onchange": "2024",
    }
    for id_, e in exp2.items():
        ok, t = eq(page, f"#{id_}", e, timeout=4000)
        R.check(P, f"opt_{id_}", ok, f"expected={e!r} got={t!r}")
    # react-moment output precedence: a provider `format` beats a child's `from_now`.
    ok, t = eq(page, "#prov-fromnow", "1 janv. 2020", timeout=3000)
    R.check(P, "info_provider_format_overrides_child_from_now", True, f"got={t!r} (react-moment precedence: format > fromNow)")
    ok, t = wait_text(page, "#prov-var-fromnow", lambda s: "Jahren" in s)
    R.check(P, "provider_locale_applies_to_fromnow", ok, t)
    ok, t = wait_text(page, "#ago", lambda s: s.strip().endswith("years") and "ago" not in s)
    R.check(P, "opt_ago_fromnow", ok, t)
    tag = page.evaluate("() => { const e = document.getElementById('element'); return e && e.tagName }")
    R.check(P, "opt_element_span", tag == "SPAN", str(tag))
    tag2 = page.evaluate("() => { const e = document.getElementById('plain'); return e && e.tagName }")
    R.check(P, "default_element_time", tag2 == "TIME", str(tag2))
    ok, t = wait_text(page, "#moment-changes", lambda s: s != "changes=0")
    R.check(P, "on_change_fired", ok, t)
    ok, t = eq(page, "#moment-last", "last=2024")
    R.check(P, "on_change_payload", ok, t)
    c1a, c2a = page.inner_text("#clock1"), page.inner_text("#clock2")
    page.wait_for_timeout(2300)
    c1b, c2b = page.inner_text("#clock1"), page.inner_text("#clock2")
    R.check(P, "pooled_clocks_tick", c1a != c1b and c2a != c2b, f"{c1a}->{c1b} {c2a}->{c2b}")
    R.check(P, "pooled_clocks_in_sync", c1b == c2b, f"{c1b} vs {c2b}")
    page.click("#loc-es")
    ok, t = eq(page, "#prov-var", "jueves")
    R.check(P, "provider_var_locale_switch_es", ok, t)
    ok, t = eq(page, "#plain", "Thursday 14 March 2024", timeout=1500)
    R.check(P, "siblings_stay_english_after_switch", ok, t)
    ok, t = eq(page, "#prov-var-fr", "jeudi", timeout=1500)
    R.check(P, "component_locale_overrides_provider", ok, t)
    page.click("#loc-en")
    ok, t = eq(page, "#prov-var", "Thursday")
    R.check(P, "provider_var_locale_switch_en", ok, t)
    css_leak = page.evaluate("() => { const e = document.getElementById('utc'); if (!e) return null; const cs = getComputedStyle(e); return {utc: e.style.utc, cls: e.className} }")
    R.check(P, "info_utc_css_leak", True, str(css_leak))
    R.shot(page, "moment")


def t_de(page: Page, R: Run):
    P = "de"
    page.wait_for_selector("#de1-box canvas", timeout=20000)
    for i in (1, 2, 3, 4):
        n = page.locator(f"#de{i}-box canvas").count()
        R.check(P, f"editor_{i}_canvas", n >= 1, f"canvases={n}")
    errs = list(R.pages[P]["pageerrors"])
    R.check(P, "no_page_errors_on_load", not errs, str(errs)[:300])
    undefined_type = [m for m in R.pages[P]["console"] if "column.type is undefined" in m["text"]]
    R.check(P, "no_column_type_undefined_warning", not undefined_type, f"{len(undefined_type)} messages")
    portal = page.evaluate("() => !!document.getElementById('portal')")
    R.check(P, "portal_div_present", portal, f"portal={portal}")
    wraps = page.evaluate("() => ({badge: !!document.querySelector('a[href*=\"reflex.dev\"], [class*=\"badge\"], img[alt*=\"Built with\"]'), portalChildren: document.getElementById('portal') ? document.getElementById('portal').children.length : -1})")
    R.check(P, "info_app_wraps", True, str(wraps))
    # Edit cell (0,0) of de1: double-click opens the overlay editor in #portal.
    box = page.locator("#de1-box canvas").first.bounding_box()
    if box:
        x, y = box["x"] + 40, box["y"] + 36 + 17
        page.mouse.click(x, y)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        try:
            page.wait_for_selector("#portal textarea, #portal input", timeout=5000)
            editor = page.evaluate("() => { const p = document.getElementById('portal'); const a = document.activeElement; return {html: p.innerHTML.slice(0, 300), active: a && (a.tagName + '.' + a.className), value: a && a.value} }")
            R.check(P, "info_overlay_editor", True, str(editor))
            page.keyboard.press("Control+A")
            page.keyboard.type("Zed")
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            ok, t = eq(page, "#de-edits", "edits=0,0=Zed", timeout=6000)
            R.check(P, "cell_edit_roundtrip", ok, t)
            ok, t = eq(page, "#de-row0", "row0=Zed|30|1990-01-01")
            R.check(P, "cell_edit_updates_row", ok, t)
        except Exception as e:  # noqa: BLE001
            R.check(P, "cell_edit_roundtrip", False, f"overlay editor did not open: {e}")
        page.keyboard.press("Escape")
        # Same edit through the mouse: double-click the Age cell (col 1, row 1) and type a number.
        page.mouse.dblclick(box["x"] + 190, box["y"] + 36 + 34 + 17)
        try:
            page.wait_for_selector("#portal textarea, #portal input", timeout=5000)
            page.keyboard.press("Control+A")
            page.keyboard.type("99")
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            ok, t = wait_text(page, "#de-edits", lambda s: re.fullmatch(r"edits=[12],1=99", s.strip()) is not None, timeout=6000)
            R.check(P, "cell_edit_dblclick_number", ok, t)
        except Exception as e:  # noqa: BLE001
            R.check(P, "cell_edit_dblclick_number", False, f"overlay editor did not open: {e}")
        page.keyboard.press("Escape")
    page.click("#de-add-row")
    ok, t = eq(page, "#de-nrows", "nrows=4")
    R.check(P, "add_row_state", ok, t)
    page.click("#de-add-col")
    ok, t = eq(page, "#de-ncols", "ncols=4")
    page.wait_for_timeout(800)
    errs2 = [e for e in R.pages[P]["pageerrors"] if e not in errs]
    R.check(P, "add_untyped_column_no_error", ok and not errs2, f"{t} errors={errs2}")
    undefined_type = [m for m in R.pages[P]["console"] if "column.type is undefined" in m["text"]]
    R.check(P, "no_column_type_undefined_after_add", not undefined_type, f"{len(undefined_type)} messages")
    # CMP-31: open the image overlay of de3 cell (0,0) with Enter.
    box3 = page.locator("#de3-box canvas").first.bounding_box()
    if box3:
        page.mouse.click(box3["x"] + 40, box3["y"] + 36 + 30)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        try:
            page.wait_for_selector("#portal img, #portal .carousel, #portal [class*=carousel]", timeout=5000)
            info = page.evaluate("() => { const p = document.getElementById('portal'); return {imgs: p.querySelectorAll('img').length, carousel: !!p.querySelector('.carousel, [class*=carousel]'), text: p.innerText.slice(0, 80)} }")
            R.check(P, "cmp31_image_overlay_opens", info["imgs"] >= 1, str(info))
            R.shot(page, "de_overlay")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            still = page.evaluate("() => document.getElementById('portal').querySelectorAll('img').length")
            R.check(P, "info_overlay_closes_on_escape", True, f"imgs after escape={still} (CMP-48 known)")
        except Exception as e:  # noqa: BLE001
            R.check(P, "cmp31_image_overlay_opens", False, f"no overlay in #portal: {e}")
            R.shot(page, "de_overlay_fail")
    R.shot(page, "de")


def t_icons(page: Page, R: Run):
    P = "icons"
    errs = list(R.pages[P]["pageerrors"])
    R.check(P, "no_page_errors_on_load", not errs, str(errs)[:300])

    def svg_class(id_):
        return page.evaluate("(id) => { const e = document.getElementById(id); if (!e) return '<missing>'; const s = e.tagName === 'svg' ? e : e.querySelector('svg'); return s ? s.getAttribute('class') : '<no svg>' }", id_)

    R.check(P, "static_icon", "lucide-apple" in str(svg_class("static-icon")), svg_class("static-icon"))
    R.check(P, "button_icon", "lucide" in str(svg_class("btn-icon")), svg_class("btn-icon"))
    R.check(P, "badge_icon", "lucide-check" in str(svg_class("badge-icon")), svg_class("badge-icon"))
    R.check(P, "callout_icon", "lucide" in str(svg_class("callout-icon")), svg_class("callout-icon"))
    R.check(P, "input_slot_icon", page.locator("svg.lucide-mail").count() == 1, f"count={page.locator('svg.lucide-mail').count()}")
    def paths(id_):
        # DynamicIcon renders class="lucide" only, so compare the SVG paths with a static reference icon.
        return page.evaluate("(id) => { const e = document.getElementById(id); if (!e) return '<missing>'; const s = e.tagName === 'svg' ? e : e.querySelector('svg'); return s ? s.innerHTML : '<no svg>' }", id_)

    R.check(P, "dynamic_icon_initial", paths("dyn-icon") == paths("static-icon") and paths("dyn-icon") != "<no svg>", f"class={svg_class('dyn-icon')} same_paths_as_apple={paths('dyn-icon') == paths('static-icon')}")
    R.check(P, "foreach_icons", page.locator("#foreach-icons svg").count() == 3, f"count={page.locator('#foreach-icons svg').count()}")
    page.click("#icon-next")
    eq(page, "#icon-name", "name=banana")
    page.wait_for_timeout(800)
    R.check(P, "dynamic_icon_switches", paths("dyn-icon") == paths("ref-banana"), f"same_paths_as_banana={paths('dyn-icon') == paths('ref-banana')}")
    page.click("#icon-next")
    eq(page, "#icon-name", "name=wifi_off")
    page.wait_for_timeout(800)
    R.check(P, "dynamic_icon_underscore_name", paths("dyn-icon") == paths("ref-wifi-off"), f"same_paths_as_wifi_off={paths('dyn-icon') == paths('ref-wifi-off')}")

    def width(id_):
        return page.evaluate("(id) => { const e = document.getElementById(id); return e ? e.getAttribute('width') : null }", id_)

    R.check(P, "size_var_icon", width("size-icon") == "24", str(width("size-icon")))
    page.click("#icon-bigger")
    eq(page, "#icon-size", "size=32")
    page.wait_for_timeout(300)
    R.check(P, "size_var_updates", width("size-icon") == "32", str(width("size-icon")))
    R.check(P, "same_library_prop_import_static", width("libprop-icon") == "40", f"width={width('libprop-icon')}")
    R.check(P, "same_library_prop_import_dynamic", width("dyn-libprop-icon") == "40", f"width={width('dyn-libprop-icon')}")
    color = page.evaluate("() => { const e = document.getElementById('cm-icon'); return e ? getComputedStyle(e).color : null }")
    R.check(P, "color_mode_cond_icon_light", color == "rgb(255, 0, 0)", str(color))
    page.click("#toggle-icon")
    page.wait_for_timeout(600)
    color2 = page.evaluate("() => { const e = document.getElementById('cm-icon'); return e ? getComputedStyle(e).color : null }")
    R.check(P, "toggle_color_mode_on_icon", color2 == "rgb(0, 0, 255)", str(color2))
    keys = page.evaluate("() => window.__reflex ? Object.keys(window.__reflex).filter(k => k.includes('lucide')) : null")
    R.check(P, "info_bundled_lucide_modules", True, str(keys))
    R.shot(page, "icons")


def t_code(page: Page, R: Run):
    P = "code"
    page.wait_for_selector("#shiki-t pre, #shiki-t code", timeout=20000)
    page.wait_for_timeout(1500)

    def count(sel):
        return page.locator(sel).count()

    R.check(P, "transformer_highlight_line", count("#shiki-t .line.highlighted") == 1, f"count={count('#shiki-t .line.highlighted')}")
    R.check(P, "transformer_diff_add", count("#shiki-t .line.diff.add") == 1, f"count={count('#shiki-t .line.diff.add')}")
    R.check(P, "transformer_diff_remove", count("#shiki-t .line.diff.remove") == 1, f"count={count('#shiki-t .line.diff.remove')}")
    txt_t = page.inner_text("#shiki-t")
    R.check(P, "transformer_notation_stripped", "[!code" not in txt_t, txt_t[:120])
    bg = page.evaluate("() => { const e = document.querySelector('#shiki-t .line.highlighted'); return e ? getComputedStyle(e).backgroundColor : null }")
    R.check(P, "transformer_highlight_styled", bool(bg and bg not in ('rgba(0, 0, 0, 0)', 'transparent')), str(bg))
    R.check(P, "plain_block_no_transformers", count("#shiki-plain .highlighted") == 0 and "[!code highlight]" in page.inner_text("#shiki-plain"), page.inner_text("#shiki-plain")[:80])
    R.check(P, "transformer_block_with_line_numbers", count("#shiki-t-ln .line.highlighted") == 1 and count("#shiki-t-ln button") >= 1, f"hl={count('#shiki-t-ln .line.highlighted')} buttons={count('#shiki-t-ln button')}")
    R.check(P, "rsh_python_tokens", count("#rsh-py code span") > 3 and count("#rsh-py button") >= 1, f"spans={count('#rsh-py code span')} buttons={count('#rsh-py button')}")
    R.check(P, "rsh_js_tokens", count("#rsh-js code span") > 3, f"spans={count('#rsh-js code span')}")
    R.check(P, "rsh_light_theme", count("#rsh-light code span") > 3, f"spans={count('#rsh-light code span')}")
    R.check(P, "markdown_code_blocks", count("#md-code pre") == 2, f"pre={count('#md-code pre')}")
    R.shot(page, "code")


TESTS = {
    "cbg": t_cbg,
    "radio": t_radio,
    "radio_aschild": t_radio_aschild,
    "input": t_input,
    "progress": t_progress,
    "accordion": t_accordion,
    "dialog": t_dialog,
    "slider": t_slider,
    "rform": t_rform,
    "moment": t_moment,
    "de": t_de,
    "icons": t_icons,
    "code": t_code,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--shots", default="shots")
    ap.add_argument("--pages", default=",".join(TESTS))
    args = ap.parse_args()
    R = Run(args.base, Path(args.shots))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for name in args.pages.split(","):
            print(f"== {name}")
            try:
                page = R.open(browser, name)
                TESTS[name](page, R)
                page.context.close()
            except Exception as e:  # noqa: BLE001
                R.check(name, "driver_exception", False, f"{type(e).__name__}: {e}")
                traceback.print_exc()
                try:
                    R.shot(page, f"{name}_exception")
                    page.context.close()
                except Exception:  # noqa: BLE001
                    pass
        browser.close()
    summary = {}
    for name, rec in R.pages.items():
        bad = [m for m in rec["console"] if m["type"] in ("error", "warning") and not benign(m["text"])]
        summary[name] = {"console_errwarn": len(bad), "pageerrors": len(rec["pageerrors"]), "failed_requests": len(rec["failed"]), "http_4xx_5xx": len(rec["http"])}
        for m in bad[:8]:
            print(f"  [{name}] console.{m['type']}: {m['text'][:220]}")
        for e in rec["pageerrors"][:5]:
            print(f"  [{name}] PAGEERROR: {e[:220]}")
        for f in rec["failed"][:5]:
            print(f"  [{name}] REQFAIL: {f['url']} {f['failure']}")
        for h in rec["http"][:5]:
            print(f"  [{name}] HTTP {h['status']}: {h['url']}")
    fails = [c for c in R.checks if not c["ok"]]
    out = {"base": args.base, "is_new": R.is_new, "checks": R.checks, "pages": R.pages, "summary": summary, "fail_count": len(fails), "check_count": len(R.checks)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"RESULT: {len(R.checks) - len(fails)}/{len(R.checks)} checks passed; is_new={R.is_new}")
    for c in fails:
        print(f"  FAIL {c['page']}/{c['name']}: {c['detail'][:200]}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())

"""Playwright driver for the memoapp #6947 cluster.

Usage:
  $SB/envs/driver/bin/python drive_memo.py <base_url> <out_prefix> [--shots DIR]

Checks, per page, with console/network capture:
  /custom   -> both modules' add_custom_code, dynamic imports and CSS imports live
  /samename -> the two same-named @rx.memo cards drive their own module's state
  /props    -> dataclass / IntEnum / enum-match props render correctly
  /foreach  -> memo inside foreach, ComponentState inside a memo, client-state prop
  /page2    -> the same memos after client-side navigation
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
PREFIX = sys.argv[2]
SHOTS = None
if "--shots" in sys.argv:
    SHOTS = sys.argv[sys.argv.index("--shots") + 1]

report = {"base": BASE, "checks": [], "console": [], "network": [], "pageerrors": []}


def check(name, ok, detail=""):
    report["checks"].append({"name": name, "ok": bool(ok), "detail": str(detail)})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


def shot(page, name):
    if SHOTS:
        page.screenshot(path=f"{SHOTS}/{PREFIX}-{name}.png", full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: report["console"].append(
            {"type": m.type, "text": m.text[:400], "url": page.url}
        ),
    )
    page.on("pageerror", lambda e: report["pageerrors"].append(str(e)[:400]))
    page.on(
        "response",
        lambda r: report["network"].append({"status": r.status, "url": r.url})
        if r.status >= 400
        else None,
    )

    def goto(path):
        page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(1500)

    # ---------------- /custom : the collision table, end to end -----------------
    goto("/custom")
    shot(page, "custom")
    markers = page.evaluate(
        "() => ({code_a: window.MEMO_CODE_A ?? null, code_b: window.MEMO_CODE_B ?? null,"
        " dyn_a: globalThis.MEMO_DYN_A ?? null, dyn_b: globalThis.MEMO_DYN_B ?? null})"
    )
    check("custom.add_custom_code.A", markers["code_a"] == "code-A", markers)
    check("custom.add_custom_code.B", markers["code_b"] == "code-B", markers)
    check("custom.dynamic_import.A", markers["dyn_a"] == "dyn-A", markers)
    check("custom.dynamic_import.B", markers["dyn_b"] == "dyn-B", markers)

    css = page.evaluate(
        "() => { const e = document.querySelector('#custom-a .memo-css-target');"
        " if (!e) return null; const s = getComputedStyle(e);"
        " return {color: s.color, background: s.backgroundColor}; }"
    )
    check(
        "custom.tagless_importvar.A_css",
        css and css["color"] == "rgb(1, 2, 3)",
        f"computed={css}",
    )
    check(
        "custom.tagless_importvar.B_css",
        css and css["background"] == "rgb(4, 5, 6)",
        f"computed={css}",
    )

    body = page.inner_text("body")
    check("custom.appwrap.text_a", "\na\n" in f"\n{body}\n" or body.startswith("a"), repr(body[:60]))
    check("custom.appwrap.text_bbbbb", "bbbbb" in body, repr(body[:60]))

    counts = page.evaluate(
        "() => ({a: document.querySelectorAll('#custom-a > div > div').length,"
        " b: document.querySelectorAll('#custom-b > div > div').length})"
    )
    check("custom.four_widgets_each", counts["a"] == 4 and counts["b"] == 4, counts)

    titles = page.evaluate(
        "() => Array.from(document.querySelectorAll('#custom-a > div > div,"
        " #custom-b > div > div')).map(e => e.getAttribute('title'))"
    )
    check(
        "custom.state_bound_prop_initial",
        titles == ["shared"] * 8,
        titles,
    )
    page.click("#relabel")
    page.wait_for_timeout(1200)
    titles2 = page.evaluate(
        "() => Array.from(document.querySelectorAll('#custom-a > div > div,"
        " #custom-b > div > div')).map(e => e.getAttribute('title'))"
    )
    check("custom.state_bound_prop_after_event", titles2 == ["relabelled"] * 8, titles2)
    shot(page, "custom-after-relabel")

    # ---------------- /samename : two same-named @rx.memo cards ------------------
    goto("/samename")
    shot(page, "samename")
    btns = page.query_selector_all("#cards-p1 button")
    check("samename.two_cards", len(btns) == 2, [b.inner_text() for b in btns])
    page.click("#cards-p1 button:nth-of-type(1)")
    page.wait_for_timeout(900)
    a1 = page.inner_text("#a-clicks-p1")
    b1 = page.inner_text("#b-clicks-p1")
    check("samename.card_A_bumps_only_A", (a1, b1) == ("1", "0"), f"A={a1} B={b1}")
    page.click("#cards-p1 button:nth-of-type(2)")
    page.wait_for_timeout(900)
    a2 = page.inner_text("#a-clicks-p1")
    b2 = page.inner_text("#b-clicks-p1")
    check("samename.card_B_bumps_only_B", (a2, b2) == ("1", "10"), f"A={a2} B={b2}")

    page.click("#cs-a-btn-p1")
    page.wait_for_timeout(900)
    page.click("#cs-b-btn-p1")
    page.wait_for_timeout(900)
    ca = page.inner_text("#cs-a-out-p1")
    cb = page.inner_text("#cs-b-out-p1")
    check("samename.componentstate_independent", (ca, cb) == ("1", "10"), f"A={ca} B={cb}")
    shot(page, "samename-clicked")

    # ---------------- /props : dataclass and enum props --------------------------
    goto("/props")
    shot(page, "props")
    vals = page.evaluate(
        "() => Object.fromEntries(Array.from(document.querySelectorAll('#props-panel span'))"
        ".map(e => [e.id, e.innerText]))"
    )
    check(
        "props.dataclass_alpha_beta",
        vals.get("obj-alpha") == "x" and vals.get("obj-beta") == "x",
        vals,
    )
    check(
        "props.local_dataclasses",
        vals.get("obj-local-one") == "x" and vals.get("obj-local-two") == "x",
        vals,
    )
    check(
        "props.intenum_vs_int",
        vals.get("level-enum") == "1"
        and vals.get("level-int") == "1"
        and vals.get("level-enum-two") == "2",
        vals,
    )
    check(
        "props.enum_match_cond",
        vals.get("hue-red", "").startswith("matched-red|cond-red|")
        and vals.get("hue-blue", "").startswith("matched-blue|cond-not-red|"),
        vals,
    )

    # ---------------- /foreach : memo in foreach, CS in memo, client state -------
    goto("/foreach")
    shot(page, "foreach")
    rows = page.evaluate("() => document.querySelectorAll('#foreach-rows > div').length")
    check("foreach.rows", rows == 3, rows)
    labels = page.evaluate(
        "() => Array.from(document.querySelectorAll('#foreach-rows button')).map(b => b.innerText)"
    )
    check(
        "foreach.state_bound_memo_props",
        labels == ["i0", "i0", "i1", "i1", "i2", "i2"],
        labels,
    )
    fa0 = int(page.inner_text("#fe-a-clicks"))
    fb0 = int(page.inner_text("#fe-b-clicks"))
    page.click("#foreach-rows > div:nth-of-type(2) button:nth-of-type(1)")
    page.wait_for_timeout(900)
    page.click("#foreach-rows > div:nth-of-type(3) button:nth-of-type(2)")
    page.wait_for_timeout(900)
    fa = int(page.inner_text("#fe-a-clicks"))
    fb = int(page.inner_text("#fe-b-clicks"))
    check(
        "foreach.memo_handlers_routed",
        (fa - fa0, fb - fb0) == (1, 10),
        f"dA={fa - fa0} dB={fb - fb0} (abs A={fa} B={fb})",
    )

    page.click("#held-a-btn")
    page.wait_for_timeout(900)
    page.click("#held-b-btn")
    page.wait_for_timeout(900)
    ha = page.inner_text("#held-a-out")
    hb = page.inner_text("#held-b-out")
    check("foreach.componentstate_inside_memo", (ha, hb) == ("1", "10"), f"A={ha} B={hb}")

    cs0 = page.inner_text("#cs-out")
    page.click("#cs-btn")
    page.wait_for_timeout(600)
    cs1 = page.inner_text("#cs-out")
    check(
        "foreach.client_state_local_memo_prop",
        cs0 == "cs0" and cs1 == "cs-clicked",
        f"global_ref=False: before={cs0!r} after={cs1!r}",
    )
    csg0 = page.inner_text("#csg-out")
    page.click("#csg-btn")
    page.wait_for_timeout(600)
    csg1 = page.inner_text("#csg-out")
    check(
        "foreach.client_state_global_memo_prop",
        csg0 == "csg0" and csg1 == "csg-clicked",
        f"global_ref=True: before={csg0!r} after={csg1!r}",
    )
    shot(page, "foreach-clicked")

    # ---------------- navigation: client-side route change -----------------------
    page.click("#nav-page2")
    page.wait_for_timeout(2000)
    check("nav.page2_loaded", page.query_selector("#page2-title") is not None, page.url)
    nav_markers = page.evaluate(
        "() => ({code_a: window.MEMO_CODE_A ?? null, code_b: window.MEMO_CODE_B ?? null,"
        " dyn_a: globalThis.MEMO_DYN_A ?? null, dyn_b: globalThis.MEMO_DYN_B ?? null})"
    )
    check(
        "nav.page2_custom_markers",
        nav_markers["code_a"] == "code-A" and nav_markers["code_b"] == "code-B"
        and nav_markers["dyn_a"] == "dyn-A" and nav_markers["dyn_b"] == "dyn-B",
        nav_markers,
    )
    na0 = int(page.inner_text("#a-clicks-p2"))
    nb0 = int(page.inner_text("#b-clicks-p2"))
    page.click("#cards-p2 button:nth-of-type(1)")
    page.wait_for_timeout(900)
    page.click("#cards-p2 button:nth-of-type(2)")
    page.wait_for_timeout(900)
    na = int(page.inner_text("#a-clicks-p2"))
    nb = int(page.inner_text("#b-clicks-p2"))
    check(
        "nav.page2_memo_handlers",
        (na - na0, nb - nb0) == (1, 10),
        f"dA={na - na0} dB={nb - nb0} (abs A={na} B={nb})",
    )
    shot(page, "page2")

    page.click("#nav-samename")
    page.wait_for_timeout(1500)
    check(
        "nav.back_to_samename",
        page.query_selector("#samename-p1") is not None
        and int(page.inner_text("#a-clicks-p1")) == na,
        f"{page.url} a-clicks={page.inner_text('#a-clicks-p1')} expected={na}",
    )

    browser.close()

errs = [c for c in report["console"] if c["type"] == "error"]
warns = [c for c in report["console"] if c["type"] == "warning"]
report["summary"] = {
    "checks": len(report["checks"]),
    "failed": [c["name"] for c in report["checks"] if not c["ok"]],
    "console_errors": len(errs),
    "console_warnings": len(warns),
    "pageerrors": len(report["pageerrors"]),
    "http_errors": len(report["network"]),
}
with open(f"{PREFIX}-report.json", "w") as f:
    json.dump(report, f, indent=2)
print()
print(json.dumps(report["summary"], indent=2))
for e in errs[:10]:
    print("CONSOLE ERROR:", e["text"][:200])
for e in report["pageerrors"][:10]:
    print("PAGE ERROR:", e[:200])
for n in report["network"][:10]:
    print("HTTP", n["status"], n["url"])

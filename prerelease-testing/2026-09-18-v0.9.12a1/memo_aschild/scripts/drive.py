"""Playwright driver for the memo_aschild QA app.

Usage: python drive.py <base_url> <outdir> [--skip-upload]
Captures console messages, page errors, failed requests and >=400 responses.
Prints a JSON-ish report of every check.
"""

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)

console_msgs = []
page_errors = []
failed_reqs = []
bad_resps = []
results = []


def rec(name, ok, detail=""):
    results.append({"name": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(("PASS " if ok else "FAIL ") + name + " :: " + str(detail)[:400], flush=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context(viewport={"width": 1280, "height": 1000})
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: console_msgs.append(
                {"type": m.type, "text": m.text, "url": page.url}
            ),
        )
        page.on("pageerror", lambda e: page_errors.append({"err": str(e), "url": page.url}))
        page.on(
            "requestfailed",
            lambda r: failed_reqs.append(
                {"url": r.url, "failure": str(r.failure), "page": page.url}
            ),
        )
        page.on(
            "response",
            lambda r: bad_resps.append({"url": r.url, "status": r.status})
            if r.status >= 400
            else None,
        )

        # ---------------------------------------------------------- FORMS
        page.goto(f"{BASE}/forms", wait_until="networkidle")
        page.wait_for_timeout(1500)

        inp = page.locator("#inp_name")
        rec("forms: #inp_name exists", inp.count() == 1, f"count={inp.count()}")
        attrs = page.evaluate(
            """() => {
              const e = document.querySelector('#inp_name');
              if (!e) return null;
              const o = {tag: e.tagName};
              for (const a of e.attributes) o[a.name] = a.value;
              o._computedBorder = getComputedStyle(e).borderTopColor;
              o._computedBorderWidth = getComputedStyle(e).borderTopWidth;
              return o;
            }"""
        )
        print("INP_NAME_ATTRS=" + json.dumps(attrs), flush=True)
        rec(
            "forms/#6850: slot-injected name= reaches memoized input",
            attrs and attrs.get("name") == "full_name",
            attrs,
        )
        rec(
            "forms/#6850: own class_name preserved and radix class merged",
            attrs and "own-class" in (attrs.get("class") or ""),
            attrs.get("class") if attrs else None,
        )
        rec(
            "forms/#6850: own style survives slot merge (teal 2px border)",
            attrs and attrs.get("_computedBorderWidth", "").startswith("2"),
            (attrs or {}).get("_computedBorder"),
        )
        rec(
            "forms/#6850: aria-describedby injected by radix Field",
            attrs and "aria-describedby" in attrs,
            (attrs or {}).get("aria-describedby"),
        )

        # form.message force_match (#7133)
        fm = page.evaluate(
            """() => [...document.querySelectorAll('#the_form *')]
               .filter(e => e.hasAttribute('forcematch') || e.hasAttribute('forceMatch')
                            || e.getAttributeNames().some(n => n.toLowerCase()==='forcematch'))
               .map(e => ({tag:e.tagName, txt:e.textContent, attrs:e.getAttributeNames()}))"""
        )
        rec("forms/#7133: no forceMatch attribute on DOM", fm == [], fm)

        # type into as_child input
        inp.fill("Ada Lovelace")
        page.wait_for_timeout(700)
        rec(
            "forms: typing into as_child input updates State",
            page.locator("#out_name").inner_text() == "Ada Lovelace",
            page.locator("#out_name").inner_text(),
        )
        page.locator("#inp_ctl").fill("ctl-typed")
        page.wait_for_timeout(700)
        rec(
            "forms: fully-controlled (debounce) input updates State",
            page.locator("#out_ctl").inner_text() == "ctl-typed",
            page.locator("#out_ctl").inner_text(),
        )
        page.locator("#inp_nick").fill("nick-typed")
        page.wait_for_timeout(500)
        rec(
            "forms: client_state-bound as_child input updates ClientStateVar",
            page.locator("#out_nick").inner_text() == "nick-typed",
            page.locator("#out_nick").inner_text(),
        )
        page.locator("#inp_memoed").fill("memo-typed")
        page.wait_for_timeout(700)
        rec(
            "forms: @rx.memo-wrapped input inside form field updates State",
            page.locator("#out_memoed").inner_text() == "memo-typed",
            page.locator("#out_memoed").inner_text(),
        )
        page.locator("#inp_bio").fill("bio text")
        page.wait_for_timeout(500)
        page.locator("#inp_agree").click()
        page.wait_for_timeout(300)
        page.locator("#inp_notify").click()
        page.wait_for_timeout(300)
        page.locator("#inp_color").get_by_text("green").click()
        page.wait_for_timeout(300)
        # select
        try:
            page.locator("#inp_fruit").click()
            page.wait_for_timeout(400)
            page.get_by_role("option", name="banana").click()
            page.wait_for_timeout(500)
        except Exception as e:  # noqa: BLE001
            rec("forms: select interaction", False, e)
        page.screenshot(path=f"{OUT}/forms_filled.png")
        page.locator("#btn_submit").click()
        page.wait_for_timeout(1500)
        sub = page.locator("#out_submitted").inner_text()
        print("SUBMITTED=" + sub, flush=True)
        rec(
            "forms/#6850: submitted form data contains as_child input value",
            "Ada Lovelace" in sub and "full_name" in sub,
            sub,
        )
        rec("forms: submitted contains controlled", "ctl-typed" in sub, sub)
        rec("forms: submitted contains client_state nickname", "nick-typed" in sub, sub)
        rec("forms: submitted contains non-control fields (bio/fruit/agree)",
            "bio text" in sub and "banana" in sub and "agree" in sub, sub)
        page.screenshot(path=f"{OUT}/forms_submitted.png")

        # ---------------------------------------------------------- TRIGGERS
        page.goto(f"{BASE}/triggers", wait_until="networkidle")
        page.wait_for_timeout(1200)

        def clicks():
            return int(page.locator("#out_clicks").inner_text())

        base_clicks = clicks()
        # dialog
        page.locator("#t_dialog").click()
        page.wait_for_timeout(800)
        dlg_open = page.get_by_text("dialog open").count() > 0
        rec("triggers/#6850: dialog.trigger opens overlay", dlg_open, "")
        rec("triggers/#6850: dialog.trigger also runs child on_click", clicks() == base_clicks + 1,
            f"{base_clicks}->{clicks()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        base_clicks = clicks()
        page.locator("#t_popover").click()
        page.wait_for_timeout(800)
        rec("triggers: popover.trigger opens", page.locator("#popover_body").count() > 0, "")
        rec("triggers: popover.trigger runs on_click", clicks() == base_clicks + 1,
            f"{base_clicks}->{clicks()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        base_clicks = clicks()
        page.locator("#t_tooltip").hover()
        page.wait_for_timeout(900)
        tip = page.get_by_text("tip!").count() > 0
        page.locator("#t_tooltip").click()
        page.wait_for_timeout(700)
        rec("triggers: tooltip shows on hover", tip, "")
        rec("triggers: tooltip child on_click runs", clicks() == base_clicks + 1,
            f"{base_clicks}->{clicks()}")

        base_clicks = clicks()
        page.locator("#t_dropdown").click()
        page.wait_for_timeout(800)
        rec("triggers: dropdown_menu opens", page.locator("#dd_item").count() > 0, "")
        rec("triggers: dropdown trigger on_click runs", clicks() == base_clicks + 1,
            f"{base_clicks}->{clicks()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        base_clicks = clicks()
        page.locator("#t_hover").hover()
        page.wait_for_timeout(1200)
        hc = page.locator("#hover_body").count() > 0
        page.locator("#t_hover").click()
        page.wait_for_timeout(700)
        rec("triggers: hover_card opens on hover", hc, "")
        rec("triggers: hover_card trigger on_click runs", clicks() == base_clicks + 1,
            f"{base_clicks}->{clicks()}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # foreach trigger
        base_clicks = clicks()
        page.locator("#fe_btn_1").click()
        page.wait_for_timeout(900)
        log = page.locator("#out_log").inner_text()
        rec("triggers: foreach popover trigger runs handler with right arg",
            clicks() == base_clicks + 1 and "foreach-b" in log, log)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)

        # ComponentState trigger
        cs_before = page.locator("#cs_btn").inner_text()
        page.locator("#cs_btn").click()
        page.wait_for_timeout(900)
        cs_after = page.locator("#cs_btn").inner_text()
        cs_dialog = page.get_by_text("cs dialog").count() > 0
        rec("triggers: ComponentState dialog trigger opens + increments",
            cs_dialog and cs_before != cs_after, f"{cs_before!r}->{cs_after!r} dialog={cs_dialog}")
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # relabel -> trigger children rerender with new state label
        page.locator("#btn_relabel").click()
        page.wait_for_timeout(900)
        rec("triggers: state-var label re-renders inside as_child trigger",
            page.locator("#t_dialog").inner_text().startswith("label-"),
            page.locator("#t_dialog").inner_text())
        page.screenshot(path=f"{OUT}/triggers.png")

        # ---------------------------------------------------------- MEMOAPP
        page.goto(f"{BASE}/memoapp", wait_until="networkidle")
        page.wait_for_timeout(1500)
        fpath = os.path.join(OUT, "sample_upload.txt")
        with open(fpath, "w") as fh:
            fh.write("hello-from-memo-upload\n" * 3)

        for uid in ("plain", "nested", "cs_up"):
            try:
                inputs = page.locator(f"#{uid} input[type=file]")
                cnt = inputs.count()
                if cnt == 0:
                    inputs = page.locator("input[type=file]")
                    rec(f"memoapp: upload[{uid}] file input located by id", False,
                        f"no input under #{uid}; page has {inputs.count()}")
                    continue
                inputs.first.set_input_files(fpath)
                page.wait_for_timeout(900)
                sel = page.locator(f"#sel_{uid}").inner_text()
                rec(f"memoapp/#7176: selected_files populated for upload[{uid}] in memo",
                    "sample_upload.txt" in sel, sel)
                page.locator(f"#btn_up_{uid}").click()
                page.wait_for_timeout(1800)
                files = page.locator("#out_files").inner_text()
                rec(f"memoapp/#7176: upload_files handler received file for [{uid}]",
                    "sample_upload.txt" in files, files)
            except Exception as e:  # noqa: BLE001
                rec(f"memoapp: upload[{uid}]", False, repr(e))

        # toast inside memo (needs toaster provider app wrap)
        try:
            page.locator("#btn_toast").click()
            page.wait_for_timeout(1400)
            t = page.get_by_text("toast #").count()
            rec("memoapp/#7176: toast from inside a memo renders (toaster provider wrap)",
                t > 0, f"toast elements={t}")
        except Exception as e:  # noqa: BLE001
            rec("memoapp: toast", False, repr(e))
        # foreach memo rows
        try:
            page.locator("#btn_toast_fe2").click()
            page.wait_for_timeout(1200)
            rec("memoapp: foreach-rendered memo row button works",
                int(page.locator("#out_toasts").inner_text()) >= 2,
                page.locator("#out_toasts").inner_text())
        except Exception as e:  # noqa: BLE001
            rec("memoapp: foreach memo row", False, repr(e))
        # color mode consumer inside memo
        try:
            before = page.locator("#cm_text").inner_text()
            page.locator("#cm_btn").click()
            page.wait_for_timeout(900)
            after = page.locator("#cm_text").inner_text()
            rec("memoapp: color_mode_cond inside memo flips with color mode",
                before != after, f"{before}->{after}")
        except Exception as e:  # noqa: BLE001
            rec("memoapp: color mode", False, repr(e))
        page.screenshot(path=f"{OUT}/memoapp.png")

        # ---------------------------------------------------------- SVG
        page.goto(f"{BASE}/svg", wait_until="networkidle")
        page.wait_for_timeout(1200)
        svg_info = page.evaluate(
            """() => {
               const out = {};
               const check = (svgSel, rectSel, gid) => {
                 const svg = document.querySelector(svgSel);
                 const rect = document.querySelector(rectSel);
                 if (!svg || !rect) return {found:false, svg:!!svg, rect:!!rect};
                 const grad = svg.querySelector('#'+CSS.escape(gid));
                 const fill = rect.getAttribute('fill');
                 const bbox = rect.getBoundingClientRect();
                 return {found:true, gradInSameSvg: !!grad,
                         gradStops: grad ? grad.children.length : 0,
                         fill, w: bbox.width, h: bbox.height,
                         stop0: grad && grad.children[0] ? grad.children[0].getAttribute('stop-color') : null};
               };
               out.top = check('#svg_g_top', '#rect_g_top', 'g_top');
               out.memo = check('#svg_g_memo', '#rect_g_memo', 'g_memo');
               out.feCount = document.querySelectorAll('svg linearGradient').length;
               out.feRects = [...document.querySelectorAll('rect')].map(r => r.getAttribute('fill'));
               out.defsCount = document.querySelectorAll('svg defs').length;
               return out;
            }"""
        )
        print("SVG_INFO=" + json.dumps(svg_info), flush=True)
        rec("svg/#6708: top-level gradient defs live in the same <svg> as the rect",
            svg_info["top"].get("gradInSameSvg"), svg_info["top"])
        rec("svg/#6708: memo-wrapped svg keeps defs in the same <svg>",
            svg_info["memo"].get("gradInSameSvg"), svg_info["memo"])
        rec("svg/#6708: foreach svgs each render a linearGradient",
            svg_info["feCount"] >= 5, svg_info["feCount"])
        rec("svg: rect renders with non-zero size", svg_info["top"].get("w", 0) > 0,
            svg_info["top"])
        page.screenshot(path=f"{OUT}/svg_before.png")
        page.locator("#btn_svg_color").click()
        page.wait_for_timeout(1000)
        stop_after = page.evaluate(
            """() => {const g=document.querySelector('#g_top');
                      return g && g.children[0] ? g.children[0].getAttribute('stop-color') : null;}"""
        )
        rec("svg: state-driven stop-color updates inside memoized svg scope",
            stop_after == "#0000ff", stop_after)
        page.screenshot(path=f"{OUT}/svg_after.png")

        # ---------------------------------------------------------- CHAINS
        page.goto(f"{BASE}/chains", wait_until="networkidle")
        page.wait_for_timeout(1500)

        def cnt():
            return int(page.locator("#out_count").inner_text())

        page.locator("#btn_reset").click()
        page.wait_for_timeout(700)
        c0 = cnt()
        page.locator("#bare_0").click()
        page.wait_for_timeout(500)
        page.locator("#bare_99").click()
        page.wait_for_timeout(700)
        rec("chains/#7122: shared bare chain fires from first and last call site",
            cnt() == c0 + 2 and page.locator("#out_last").inner_text() == "bare",
            f"{c0}->{cnt()} last={page.locator('#out_last').inner_text()}")
        page.locator("#btn_reset").click()
        page.wait_for_timeout(600)
        page.locator("#by_7").click()
        page.wait_for_timeout(700)
        rec("chains/#7122: arg-bearing chain passes its own call-site arg (i=7)",
            cnt() == 7 and page.locator("#out_last").inner_text() == "by-7",
            f"count={cnt()} last={page.locator('#out_last').inner_text()}")
        page.locator("#by_42").click()
        page.wait_for_timeout(700)
        rec("chains/#7122: second arg call-site does not leak the first's arg",
            cnt() == 49 and page.locator("#out_last").inner_text() == "by-42",
            f"count={cnt()} last={page.locator('#out_last').inner_text()}")
        page.locator("#btn_reset").click()
        page.wait_for_timeout(600)
        page.locator("#btn_stopprop").click()
        page.wait_for_timeout(600)
        page.locator("#btn_preventdefault").click()
        page.wait_for_timeout(600)
        rec("chains: stop_propagation / prevent_default variants still dispatch",
            cnt() == 2, cnt())
        page.locator("#btn_reset").click()
        page.wait_for_timeout(600)
        for _ in range(5):
            page.locator("#btn_throttle").click()
            page.wait_for_timeout(60)
        page.wait_for_timeout(1200)
        thr = cnt()
        rec("chains: throttle(500) collapses 5 rapid clicks", thr == 1, f"count={thr}")
        page.locator("#btn_reset").click()
        page.wait_for_timeout(600)
        for _ in range(5):
            page.locator("#btn_debounce").click()
            page.wait_for_timeout(60)
        page.wait_for_timeout(1500)
        deb = cnt()
        rec("chains: debounce(300) collapses 5 rapid clicks", deb == 1, f"count={deb}")
        page.locator("#btn_reset").click()
        page.wait_for_timeout(600)
        page.mouse.move(5, 5)
        page.locator("#box_both").hover()
        page.wait_for_timeout(600)
        after_hover = cnt()
        page.locator("#box_both").click()
        page.wait_for_timeout(700)
        rec("chains/#7122: same handler on on_click AND on_mouse_enter fires for both",
            after_hover == 1 and cnt() == 2, f"hover={after_hover} click={cnt()}")
        page.screenshot(path=f"{OUT}/chains.png")

        # ---------------------------------------------------------- BOOM
        page.goto(f"{BASE}/boom", wait_until="networkidle")
        page.wait_for_timeout(1200)
        mark = len(console_msgs)
        page.locator("#btn_boom").click()
        page.wait_for_timeout(2500)
        new_msgs = console_msgs[mark:]
        invalid_dom = [
            m for m in new_msgs
            if "Invalid DOM property" in m["text"] or "invalid DOM property" in m["text"]
        ]
        body_txt = page.locator("body").inner_text()[:400]
        print("BOOM_CONSOLE=" + json.dumps(new_msgs)[:4000], flush=True)
        rec("boom/#7130: no 'Invalid DOM property' warnings from fallback SVG",
            len(invalid_dom) == 0, invalid_dom)
        rec("boom: error boundary fallback rendered",
            ("error" in body_txt.lower() or "went wrong" in body_txt.lower()), body_txt)
        page.screenshot(path=f"{OUT}/boom.png")

        # ---------------------------------------------------------- nav sanity
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(600)
        page.locator("#lnk_memoapp").click()
        page.wait_for_timeout(1500)
        rec("nav: client-side navigation to /memoapp keeps upload working",
            page.locator("#sel_plain").count() == 1, page.url)
        page.locator("input[type=file]").first.set_input_files(fpath)
        page.wait_for_timeout(900)
        rec("nav: selected_files after client-side nav",
            "sample_upload.txt" in page.locator("#sel_plain").inner_text(),
            page.locator("#sel_plain").inner_text())

        ctx.close()
        browser.close()

    report = {
        "results": results,
        "console": console_msgs,
        "page_errors": page_errors,
        "failed_requests": failed_reqs,
        "bad_responses": bad_resps,
    }
    with open(f"{OUT}/report.json", "w") as fh:
        json.dump(report, fh, indent=1)
    npass = sum(1 for r in results if r["ok"])
    print(f"\n==== {npass}/{len(results)} passed ====")
    print("PAGE_ERRORS:", json.dumps(page_errors)[:3000])
    errs = [m for m in console_msgs if m["type"] in ("error", "warning")]
    print("CONSOLE_ERR_WARN_COUNT:", len(errs))
    print(json.dumps(errs, indent=1)[:6000])
    print("FAILED_REQS:", json.dumps(failed_reqs)[:2000])
    print("BAD_RESPS:", json.dumps([b for b in bad_resps])[:2000])


main()

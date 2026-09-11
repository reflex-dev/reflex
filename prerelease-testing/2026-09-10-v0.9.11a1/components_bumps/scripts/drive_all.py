"""Drive every page of the component-bumps app and report per-page results.

Usage:
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_all.py http://localhost:5220 OUTDIR [page ...]

Writes OUTDIR/<page>.json (results + console/network capture) and screenshots.
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


def benign(text: str) -> bool:
    return any(p.search(text) for p in BENIGN)


class Capture:
    def __init__(self, page):
        self.console: list[dict] = []
        self.errors: list[str] = []
        self.failed: list[str] = []
        self.bad_responses: list[str] = []
        page.on("console", self._console)
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.on("requestfailed", lambda r: self.failed.append(f"{r.method} {r.url} {r.failure}"))
        page.on("response", self._response)

    def _console(self, msg):
        text = msg.text
        if benign(text):
            return
        self.console.append({"type": msg.type, "text": text[:2000]})

    def _response(self, resp):
        if resp.status >= 400:
            self.bad_responses.append(f"{resp.status} {resp.url}")

    def dump(self) -> dict:
        return {
            "console": self.console,
            "page_errors": self.errors,
            "failed_requests": self.failed,
            "bad_responses": self.bad_responses,
        }

    def reset(self):
        self.console.clear()
        self.errors.clear()
        self.failed.clear()
        self.bad_responses.clear()


def txt(page, sel: str) -> str:
    try:
        el = page.query_selector(sel)
        if el is None:
            return "<MISSING>"
        return el.inner_text().strip()
    except Exception as e:  # noqa: BLE001
        return f"<ERR {e}>"


def attr(page, sel: str, name: str) -> str:
    try:
        el = page.query_selector(sel)
        if el is None:
            return "<MISSING>"
        return str(el.get_attribute(name))
    except Exception as e:  # noqa: BLE001
        return f"<ERR {e}>"


MOMENT_IDS = [
    "m-static", "m-state-str", "m-state-dt", "m-date-prop", "m-client",
    "m-fromnow", "m-fromnow-short", "m-tonow", "m-fnd-relative", "m-fnd-absolute",
    "m-duration", "m-duration-fmt", "m-duration-notrim", "m-durfromnow",
    "m-unix", "m-tz-ny", "m-tz-tokyo", "m-tz-paris", "m-tz-state",
    "m-locale-fr", "m-locale-es", "m-locale-state", "m-interval", "m-interval0",
    "m-add", "m-sub", "m-parse-list", "m-parse-str", "m-title", "m-diff",
    "m-diff-dec", "m-local", "m-memo",
]


def drive_moment(page, base, out: Path, cap: Capture) -> dict:
    r: dict = {}
    page.goto(f"{base}/moment", wait_until="networkidle")
    page.wait_for_timeout(2500)
    r["initial"] = {i: txt(page, f"#{i}") for i in MOMENT_IDS}
    r["title_attr"] = attr(page, "#m-title", "title")
    r["foreach"] = page.eval_on_selector_all(
        "#m-foreach time, #m-foreach [id^='m-foreach']", "els => els.map(e => e.innerText)"
    )
    r["cstate_initial"] = txt(page, "#m-cstate")
    r["change_count_t0"] = txt(page, "#m-change-count")
    # interval live update
    a = txt(page, "#m-interval")
    page.wait_for_timeout(2500)
    b = txt(page, "#m-interval")
    r["interval_a"], r["interval_b"] = a, b
    r["interval_updates"] = a != b
    i0 = txt(page, "#m-interval0")
    page.wait_for_timeout(1500)
    r["interval0_static"] = i0 == txt(page, "#m-interval0")
    r["change_count_t1"] = txt(page, "#m-change-count")
    r["last_change"] = txt(page, "#m-last-change")
    # state date bump
    page.click("#m-bump")
    page.wait_for_timeout(800)
    r["after_bump_state_str"] = txt(page, "#m-state-str")
    r["after_bump_state_dt"] = txt(page, "#m-state-dt")
    r["after_bump_memo"] = txt(page, "#m-memo")
    # client state bump
    page.click("#m-client-bump")
    page.wait_for_timeout(600)
    r["after_client_bump"] = txt(page, "#m-client")
    # tz rotation
    page.click("#m-tz-btn")
    page.wait_for_timeout(700)
    r["tz_after_1"] = txt(page, "#m-tz-state")
    page.click("#m-tz-btn")
    page.wait_for_timeout(700)
    r["tz_after_2"] = txt(page, "#m-tz-state")
    # locale rotation
    page.click("#m-locale-btn")
    page.wait_for_timeout(700)
    r["locale_after_1"] = txt(page, "#m-locale-state")
    # component state
    page.click("#m-cstate-btn")
    page.wait_for_timeout(700)
    r["cstate_after"] = txt(page, "#m-cstate")
    page.screenshot(path=str(out / "moment.png"), full_page=True)
    r["change_count_end"] = txt(page, "#m-change-count")
    return r


def drive_code(page, base, out: Path, cap: Capture) -> dict:
    r: dict = {}
    page.goto(f"{base}/code", wait_until="networkidle")
    page.wait_for_timeout(3000)
    for box in ["cb-python", "cb-state", "xcb-python", "xcb-ts", "xcb-sql", "xcb-rust", "xcb-bash", "xcb-state", "xcb-long", "cb-markdown"]:
        r[box] = {
            "text_head": txt(page, f"#{box}")[:160],
            "colored_spans": page.eval_on_selector_all(
                f"#{box} span[style*='color']", "els => els.length"
            ),
            "pre_count": page.eval_on_selector_all(f"#{box} pre", "els => els.length"),
        }
    r["shiki_bg"] = page.eval_on_selector(
        "#xcb-python pre", "el => getComputedStyle(el).backgroundColor"
    ) if page.query_selector("#xcb-python pre") else "<MISSING>"
    r["shiki_ts_bg"] = page.eval_on_selector(
        "#xcb-ts pre", "el => getComputedStyle(el).backgroundColor"
    ) if page.query_selector("#xcb-ts pre") else "<MISSING>"
    r["line_numbers_css"] = page.eval_on_selector(
        "#xcb-python pre code", "el => getComputedStyle(el).display"
    ) if page.query_selector("#xcb-python pre code") else "<MISSING>"
    r["copy_buttons"] = page.eval_on_selector_all("#xcb-python button", "els => els.length")
    # state update
    page.click("#cb-update")
    page.wait_for_timeout(1200)
    r["cb_state_after_update"] = txt(page, "#cb-state")[:120]
    r["xcb_state_after_update"] = txt(page, "#xcb-state")[:120]
    page.click("#cb-theme")
    page.wait_for_timeout(1200)
    r["xcb_state_bg_after_theme"] = page.eval_on_selector(
        "#xcb-state pre", "el => getComputedStyle(el).backgroundColor"
    ) if page.query_selector("#xcb-state pre") else "<MISSING>"
    # copy button click
    if page.query_selector("#xcb-python button"):
        page.click("#xcb-python button")
        page.wait_for_timeout(600)
    r["markdown_code_langs"] = page.eval_on_selector_all(
        "#cb-markdown pre", "els => els.map(e => e.innerText.slice(0, 40))"
    )
    page.screenshot(path=str(out / "code.png"), full_page=True)
    return r


def _plot_probe(page):
    return page.evaluate("""() => Array.from(document.querySelectorAll('.js-plotly-plot')).map(gd => ({
        layout_title: JSON.stringify(gd.layout && gd.layout.title),
        full_title: gd._fullLayout && gd._fullLayout.title && gd._fullLayout.title.text,
        paper: gd._fullLayout && gd._fullLayout.paper_bgcolor,
        w: gd._fullLayout && gd._fullLayout.width,
        h: gd._fullLayout && gd._fullLayout.height,
        dragmode: gd._fullLayout && gd._fullLayout.dragmode,
        id: gd.id,
    }))""")


def drive_plotly(page, base, out: Path, cap: Capture) -> dict:
    r: dict = {}
    page.goto(f"{base}/plotly", wait_until="networkidle")
    page.wait_for_timeout(4500)
    r["plot_divs"] = page.eval_on_selector_all(".js-plotly-plot", "els => els.length")
    r["main_has_id_attr"] = page.eval_on_selector_all("#pl-main", "els => els.length")
    r["plotly_div_ids"] = page.eval_on_selector_all(".js-plotly-plot", "els => els.map(e => e.id)")
    r["modebar"] = page.eval_on_selector_all(".modebar", "els => els.length")
    r["logo_btns"] = page.eval_on_selector_all("a[data-title='Produced with Plotly']", "els => els.length")
    r["probe_initial"] = _plot_probe(page)
    pts = page.query_selector_all("#pl-main-box .js-plotly-plot .scatterlayer .points path")
    r["marker_count"] = len(pts)
    if pts:
        target = pts[len(pts) // 2]
        tb = target.bounding_box()
        if tb:
            page.mouse.move(tb["x"] + tb["width"] / 2, tb["y"] + tb["height"] / 2)
            page.wait_for_timeout(900)
            r["last_hover"] = txt(page, "#pl-last-hover")
            page.mouse.click(tb["x"] + tb["width"] / 2, tb["y"] + tb["height"] / 2)
            page.wait_for_timeout(1200)
            r["last_click"] = txt(page, "#pl-last-click")
    # box-select drag on the dragmode=select plot
    sel = page.query_selector("#pl-select-box .js-plotly-plot .nsewdrag")
    r["select_drag_layer_found"] = sel is not None
    if sel:
        sel.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        bb = sel.bounding_box()
        r["select_drag_bbox"] = bb
        page.mouse.move(bb["x"] + 5, bb["y"] + 5)
        page.mouse.down()
        page.mouse.move(bb["x"] + bb["width"] - 5, bb["y"] + bb["height"] - 5, steps=20)
        page.mouse.up()
        page.wait_for_timeout(1800)
        r["last_select_after_drag"] = txt(page, "#pl-last-select")
        page.mouse.dblclick(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
        page.wait_for_timeout(1800)
        r["deselects"] = txt(page, "#pl-deselects")
    page.click("#pl-more")
    page.wait_for_timeout(2200)
    r["probe_after_more"] = _plot_probe(page)
    page.click("#pl-layout")
    page.wait_for_timeout(2200)
    r["probe_after_layout"] = _plot_probe(page)
    page.click("#pl-layout")
    page.wait_for_timeout(2200)
    r["probe_after_layout2"] = _plot_probe(page)
    # resize handler
    page.set_viewport_size({"width": 700, "height": 900})
    page.wait_for_timeout(1800)
    r["probe_after_resize"] = _plot_probe(page)
    page.set_viewport_size({"width": 1280, "height": 900})
    page.wait_for_timeout(1500)
    r["probe_after_resize_back"] = _plot_probe(page)
    page.screenshot(path=str(out / "plotly.png"), full_page=True)
    return r


def drive_recharts(page, base, out: Path, cap: Capture) -> dict:
    r: dict = {}
    page.goto(f"{base}/recharts", wait_until="networkidle")
    page.wait_for_timeout(3500)
    for box in ["rc-line", "rc-bar", "rc-area", "rc-pie", "rc-composed"]:
        r[box] = {
            "svgs": page.eval_on_selector_all(f"#{box} svg", "els => els.length"),
            "paths": page.eval_on_selector_all(f"#{box} svg path", "els => els.length"),
            "legend": page.eval_on_selector_all(f"#{box} .recharts-legend-item", "els => els.length"),
            "ticks": page.eval_on_selector_all(
                f"#{box} .recharts-cartesian-axis-tick-value tspan", "els => els.map(e => e.textContent).slice(0, 8)"
            ),
        }
    line_d0 = page.eval_on_selector_all("#rc-line .recharts-line-curve", "els => els.map(e => e.getAttribute('d'))")
    r["line_d_before"] = [d[:60] if d else d for d in line_d0]
    page.click("#rc-random")
    page.wait_for_timeout(2500)
    line_d1 = page.eval_on_selector_all("#rc-line .recharts-line-curve", "els => els.map(e => e.getAttribute('d'))")
    r["line_d_after"] = [d[:60] if d else d for d in line_d1]
    r["line_changed"] = line_d0 != line_d1
    page.click("#rc-add")
    page.wait_for_timeout(2000)
    r["ticks_after_add"] = page.eval_on_selector_all(
        "#rc-line .recharts-cartesian-axis-tick-value tspan", "els => els.map(e => e.textContent)"
    )
    page.click("#rc-pie-bump")
    page.wait_for_timeout(2000)
    r["pie_sectors"] = page.eval_on_selector_all("#rc-pie .recharts-pie-sector", "els => els.length")
    r["pie_labels"] = page.eval_on_selector_all("#rc-pie .recharts-pie-label-text", "els => els.map(e => e.textContent)")
    # tooltip on hover
    bar = page.query_selector("#rc-bar .recharts-bar-rectangle")
    if bar:
        bb = bar.bounding_box()
        page.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
        page.wait_for_timeout(900)
        r["tooltip"] = page.eval_on_selector_all(
            ".recharts-tooltip-wrapper", "els => els.map(e => e.innerText).filter(Boolean)"
        )
    page.screenshot(path=str(out / "recharts.png"), full_page=True)
    return r


def drive_toast(page, base, out: Path, cap: Capture) -> dict:
    r: dict = {}
    page.goto(f"{base}/toast", wait_until="networkidle")
    page.wait_for_timeout(2500)
    r["onload_count"] = txt(page, "#t-onload-count")
    r["onload_toast_text"] = page.eval_on_selector_all("[data-sonner-toast]", "els => els.map(e => e.innerText)")
    r["toaster_present"] = page.eval_on_selector_all("[data-sonner-toaster]", "els => els.length")
    r["toaster_position"] = attr(page, "[data-sonner-toaster]", "data-y-position") + "/" + attr(page, "[data-sonner-toaster]", "data-x-position")
    r["toaster_rich_colors"] = attr(page, "[data-sonner-toaster]", "data-rich-colors")
    page.click("#t-dismiss-all")
    page.wait_for_timeout(1000)
    for btn, key in [("#t-info", "info"), ("#t-success", "success"), ("#t-error", "error"), ("#t-warning", "warning")]:
        page.click(btn)
        page.wait_for_timeout(900)
        r[f"toast_{key}"] = page.eval_on_selector_all(
            "[data-sonner-toast]", "els => els.map(e => ({t: e.getAttribute('data-type'), txt: e.innerText}))"
        )
    r["visible_after_four"] = page.eval_on_selector_all("[data-sonner-toast]", "els => els.length")
    r["toast_attrs"] = page.eval_on_selector_all(
        "[data-sonner-toast]",
        "els => els.map(e => ({type: e.dataset.type, rich: e.dataset.richColors, "
        "close: !!e.querySelector('[data-close-button]'), bg: getComputedStyle(e).backgroundColor}))",
    )
    r["toaster_roots"] = page.eval_on_selector_all(
        "[data-sonner-toaster]",
        "els => els.map(e => e.dataset.yPosition + '-' + e.dataset.xPosition)",
    )
    page.click("#t-dismiss-all")
    page.wait_for_timeout(1200)
    r["after_dismiss_all"] = page.eval_on_selector_all("[data-sonner-toast]", "els => els.length")
    page.click("#t-loading")
    page.wait_for_timeout(900)
    r["loading_toast"] = page.eval_on_selector_all(
        "[data-sonner-toast]", "els => els.map(e => e.getAttribute('data-type'))"
    )
    page.click("#t-dismiss-one")
    page.wait_for_timeout(1200)
    r["after_dismiss_by_id"] = page.eval_on_selector_all("[data-sonner-toast]", "els => els.length")
    page.click("#t-action")
    page.wait_for_timeout(1000)
    r["action_toast"] = page.eval_on_selector_all("[data-sonner-toast]", "els => els.map(e => e.innerText)")
    btn = page.query_selector("[data-sonner-toast] [data-button]")
    r["action_button_found"] = btn is not None
    if btn:
        btn.click()
        page.wait_for_timeout(1200)
    r["action_clicks"] = txt(page, "#t-action-count")
    page.click("#t-dismiss-all")
    page.wait_for_timeout(800)
    page.click("#t-bg")
    page.wait_for_timeout(3000)
    r["bg_count"] = txt(page, "#t-bg-count")
    r["bg_toasts"] = page.eval_on_selector_all("[data-sonner-toast]", "els => els.map(e => e.innerText)")
    page.screenshot(path=str(out / "toast.png"), full_page=True)
    return r


def _visible_msgs(page):
    return page.eval_on_selector_all(
        "[id^=form-msg]",
        "els => els.filter(e => e.offsetParent !== null).map(e => e.id + ':' + e.innerText)",
    )


def drive_radix(page, base, out: Path, cap: Capture) -> dict:
    r: dict = {}
    page.goto(f"{base}/radix", wait_until="networkidle")
    page.wait_for_timeout(2500)
    r["acc_value_initial"] = txt(page, "#acc-value")
    r["acc_states_initial"] = page.eval_on_selector_all(
        "#acc-controlled [data-state]", "els => els.map(e => e.getAttribute('data-state'))"
    )
    # uncontrolled single collapsible
    page.click("#acc-single button:has-text('uncontrolled one')")
    page.wait_for_timeout(700)
    r["single_after_open"] = page.eval_on_selector_all(
        "#acc-single div[data-state][data-orientation]", "els => els.map(e => e.getAttribute('data-state'))"
    )
    r["single_content_visible"] = page.eval_on_selector_all(
        "#acc-single [data-state='open']", "els => els.length"
    )
    page.click("#acc-single button:has-text('uncontrolled two')")
    page.wait_for_timeout(700)
    r["single_after_switch"] = page.eval_on_selector_all(
        "#acc-single div[data-state][data-orientation]", "els => els.map(e => e.getAttribute('data-state'))"
    )
    page.click("#acc-single button:has-text('uncontrolled two')")
    page.wait_for_timeout(700)
    r["single_after_collapse"] = page.eval_on_selector_all(
        "#acc-single div[data-state][data-orientation]", "els => els.map(e => e.getAttribute('data-state'))"
    )
    # controlled
    page.click("#acc-open-b")
    page.wait_for_timeout(900)
    r["acc_value_after_b"] = txt(page, "#acc-value")
    r["acc_states_after_b"] = page.eval_on_selector_all(
        "#acc-controlled div[data-state][data-orientation]", "els => els.map(e => e.getAttribute('data-state'))"
    )
    page.click("#acc-controlled button:has-text('controlled A')")
    page.wait_for_timeout(1000)
    r["acc_value_after_click_a"] = txt(page, "#acc-value")
    # multiple
    page.click("#acc-multi button:has-text('multi 1')")
    page.wait_for_timeout(500)
    page.click("#acc-multi button:has-text('multi 2')")
    page.wait_for_timeout(700)
    r["multi_states"] = page.eval_on_selector_all(
        "#acc-multi div[data-state][data-orientation]", "els => els.map(e => e.getAttribute('data-state'))"
    )
    # dialog controlled by state
    page.click("#dlg-open")
    page.wait_for_timeout(1000)
    r["dialog_body"] = txt(page, "#dlg-body")
    page.click("#dlg-nested-open")
    page.wait_for_timeout(1000)
    r["nested_body"] = txt(page, "#dlg-nested-body")
    r["dialogs_open"] = page.eval_on_selector_all("[role='dialog']", "els => els.length")
    page.click("#dlg-nested-close")
    page.wait_for_timeout(800)
    r["dialogs_after_nested_close"] = page.eval_on_selector_all("[role='dialog']", "els => els.length")
    r["outer_still_open"] = txt(page, "#dlg-body")
    page.keyboard.press("Escape")
    page.wait_for_timeout(900)
    r["after_escape"] = page.eval_on_selector_all("[role='dialog']", "els => els.length")
    # client-state dialog
    page.click("#dlg-client-open")
    page.wait_for_timeout(900)
    r["client_dialog_body"] = txt(page, "#dlg-client-body")
    page.click("#dlg-client-close")
    page.wait_for_timeout(800)
    r["client_dialog_closed"] = page.eval_on_selector_all("[role='dialog']", "els => els.length")
    # form in dialog
    page.click("#dlg-form-open")
    page.wait_for_timeout(1000)
    page.fill("#dlg-form-note", "hello from the dialog")
    page.click("#dlg-form-submit")
    page.wait_for_timeout(1500)
    r["dialog_form_result"] = txt(page, "#dlg-form-result")
    r["dialog_form_closed"] = page.eval_on_selector_all("[role='dialog']", "els => els.length")
    r["email_input_attrs"] = page.eval_on_selector(
        "#form-email", "el => ({type: el.type, required: el.required, name: el.name})"
    )
    # main form: empty submit -> valueMissing message
    page.click("#form-submit")
    page.wait_for_timeout(1000)
    r["msgs_after_empty_submit"] = _visible_msgs(page)
    r["count_after_empty_submit"] = txt(page, "#form-count")
    # bad email -> typeMismatch
    page.fill("#form-email", "not-an-email")
    page.fill("#form-age", "42")
    page.click("#form-submit")
    page.wait_for_timeout(1200)
    r["msgs_after_bad_email"] = _visible_msgs(page)
    r["count_after_bad_email"] = txt(page, "#form-count")
    # good email -> submit succeeds
    page.fill("#form-email", "user@example.com")
    page.click("#form-submit")
    page.wait_for_timeout(1500)
    r["count_after_good"] = txt(page, "#form-count")
    r["form_data"] = txt(page, "#form-data")
    r["msgs_after_good"] = _visible_msgs(page)
    page.screenshot(path=str(out / "radix.png"), full_page=True)
    return r


DRIVERS = {
    "moment": drive_moment,
    "code": drive_code,
    "plotly": drive_plotly,
    "recharts": drive_recharts,
    "toast": drive_toast,
    "radix": drive_radix,
}


def main() -> int:
    base = sys.argv[1].rstrip("/")
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    pages = sys.argv[3:] or list(DRIVERS)
    rc = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        page = ctx.new_page()
        cap = Capture(page)
        for name in pages:
            cap.reset()
            t0 = time.time()
            try:
                res = DRIVERS[name](page, base, out, cap)
                err = None
            except Exception as e:  # noqa: BLE001
                res, err = {}, f"{type(e).__name__}: {e}"
                rc = 1
                try:
                    page.screenshot(path=str(out / f"{name}-FAIL.png"), full_page=True)
                except Exception:  # noqa: BLE001
                    pass
            payload = {
                "page": name,
                "base": base,
                "elapsed_s": round(time.time() - t0, 1),
                "driver_error": err,
                "results": res,
                **cap.dump(),
            }
            (out / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str))
            print(f"== {name}: err={err} console={len(cap.console)} pageerrors={len(cap.errors)} "
                  f"failed={len(cap.failed)} bad={len(cap.bad_responses)}")
            if cap.errors or cap.console:
                rc = 1
        browser.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())

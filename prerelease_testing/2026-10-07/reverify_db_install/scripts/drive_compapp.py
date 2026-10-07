"""Drive compapp: components on every page, upload, data editor, #7227 form probe, reload.

Usage: driver-python drive_compapp.py <frontend_url> <out_dir> <label>
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from pwkit import CHROMIUM, Sink, expect, summarize

base, out, label = sys.argv[1].rstrip("/"), Path(sys.argv[2]), sys.argv[3]
out.mkdir(parents=True, exist_ok=True)
sink = Sink()
result = {"label": label, "url": base}
upload_file = out / "hello-upload.txt"
upload_file.write_text("hello upload 123\n")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    page = browser.new_page(viewport={"width": 1100, "height": 1300})
    sink.attach(page, "t1")
    page.goto(base + "/", wait_until="networkidle", timeout=120000)
    sink.check("home renders", lambda: page.wait_for_selector("#page-home", timeout=60000) and True)

    def incr():
        page.click("#incr")
        page.click("#incr")
        page.wait_for_function("document.querySelector('#count')?.textContent === '2'", timeout=15000)

    sink.check("state event roundtrip (count=2)", incr)

    def toast():
        page.click("#toast")
        page.wait_for_selector("text=toast count=2", timeout=10000)

    sink.check("rx.toast shows", toast)
    sink.check("rx.icon svg", lambda: page.locator("#icon-star").evaluate("e => e.tagName.toLowerCase()") == "svg")
    sink.check("rx.moment text", lambda: expect((t := page.locator("#moment").inner_text(timeout=10000)) == "2026-10-06", f"got {t!r}"))
    sink.check("rx.code_block", lambda: "hello" in page.locator("#code").inner_text(timeout=10000))
    sink.check("rx.markdown h1", lambda: page.locator("#md h1").inner_text(timeout=10000) == "Markdown Title")
    page.screenshot(path=str(out / f"{label}-home.png"), full_page=True)

    page.click("#nav-charts")
    sink.check("client nav to /charts", lambda: page.wait_for_selector("#page-charts", timeout=30000) and True)
    sink.check("rx.plotly renders", lambda: page.wait_for_selector("#plotly .main-svg", timeout=30000) and True)
    sink.check("plotly title text", lambda: page.locator("#plotly .gtitle").first.text_content(timeout=10000))
    sink.check("rx.recharts surface", lambda: page.wait_for_selector(".recharts-surface", timeout=20000) and page.locator(".recharts-line-curve").count() >= 1)
    sink.check("rx.data_editor canvas", lambda: page.wait_for_selector("canvas[data-testid='data-grid-canvas'], .dvn-scroller canvas, canvas", timeout=20000) and True)

    def edit_cell():
        canvas = page.locator("canvas[data-testid='data-grid-canvas']").first
        page.wait_for_timeout(1500)
        canvas.scroll_into_view_if_needed()
        box = canvas.bounding_box()
        # first data cell: left column, first row under the header (header ~36px, row ~34px)
        page.mouse.click(box["x"] + 25, box["y"] + 36 + 17)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(600)
        active = page.evaluate("document.activeElement?.className || document.activeElement?.tagName")
        if "gdg-input" not in str(active):
            page.screenshot(path=str(out / f"{label}-grid-noeditor.png"))
            raise AssertionError(f"overlay editor not focused; active={active!r} box={box}")
        page.keyboard.press("Control+A")
        page.keyboard.type("gamma")
        page.wait_for_timeout(300)  # let the overlay editor flush its value before committing
        page.keyboard.press("Enter")
        page.wait_for_function("document.querySelector('#edited')?.textContent?.includes('gamma')", timeout=8000)
        return page.locator("#edited").inner_text()

    sink.check("data_editor edit -> on_cell_edited", edit_cell)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(out / f"{label}-charts.png"), full_page=True)

    page.click("#nav-upload")
    sink.check("client nav to /upload", lambda: page.wait_for_selector("#page-upload", timeout=30000) and True)

    def do_upload():
        page.set_input_files("#up1 input[type=file]", str(upload_file))
        page.click("#do-upload")
        page.wait_for_selector(".uploaded", timeout=20000)
        return page.locator(".uploaded").first.inner_text()

    sink.check("rx.upload roundtrip", do_upload)
    page.screenshot(path=str(out / f"{label}-upload.png"), full_page=True)

    page.click("#nav-form")
    sink.check("client nav to /form", lambda: page.wait_for_selector("#page-form", timeout=30000) and True)

    def submit_form():
        page.fill("#memo_input", "typed!")
        page.wait_for_timeout(500)
        page.click("#submit")
        page.wait_for_function("document.querySelector('#form-data')?.textContent?.length > 3", timeout=15000)
        txt = page.locator("#form-data").inner_text()
        result["form_data"] = json.loads(txt)
        return txt

    sink.check("form submits", submit_form)
    fd = result.get("form_data", {})
    # Expectations from the #7227 integration test (alpha behavior)
    sink.check("#7227 form id excluded", lambda: expect("form_id" not in fd, f"form_id={fd.get('form_id')!r}"))
    sink.check("#7227 wrapper id excluded", lambda: expect("form_content_wrapper" not in fd, f"form_content_wrapper={fd.get('form_content_wrapper')!r}"))
    sink.check("#7227 non-control box id excluded", lambda: expect("plain_box" not in fd, f"plain_box={fd.get('plain_box')!r}"))
    sink.check("#7227 submit button id excluded", lambda: expect("submit" not in fd, f"submit={fd.get('submit')!r}"))
    sink.check("#7227 empty_input == ''", lambda: expect(fd.get("empty_input", "<missing>") == "", f"empty_input={fd.get('empty_input', '<missing>')!r}"))
    sink.check("#7227 radio_unset is None", lambda: expect("radio_unset" in fd and fd["radio_unset"] is None, f"radio_unset={fd.get('radio_unset', '<missing>')!r}"))
    sink.check("#7227 native_input == 'native'", lambda: expect(fd.get("native_input") == "native", f"native_input={fd.get('native_input', '<missing>')!r}"))
    sink.check("memoized controlled input submitted", lambda: expect(fd.get("memo_input") == "typed!", f"memo_input={fd.get('memo_input', '<missing>')!r}"))
    sink.check("name_input / named_input / bool_input", lambda: expect(fd.get("name_input") == "foo" and fd.get("named_input") == "named" and fd.get("bool_input") in (True, "on"), f"{fd}"))
    page.screenshot(path=str(out / f"{label}-form.png"), full_page=True)

    page.goto(base + "/", wait_until="networkidle")
    sink.check("reload keeps state (count=2)", lambda: page.wait_for_function("document.querySelector('#count')?.textContent === '2'", timeout=20000) and True)
    browser.close()

report = sink.dump(out / f"{label}-report.json", **result)
print(summarize(report))
print("form_data:", json.dumps(result.get("form_data"), sort_keys=True))

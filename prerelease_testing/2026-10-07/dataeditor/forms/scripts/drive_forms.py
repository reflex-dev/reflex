"""Drive component checks in Chromium or WebKit and retain observable evidence."""

import argparse
import hashlib
import json
import re
import time
import traceback
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

import original_driver as old


def select_matrix(run, page):
    """Compare select payloads for three documented identity shapes.

    Args:
        run: Evidence collector.
        page: Browser page.
    """
    run.goto(page, "/select-matrix", "#submit_matrix")
    page.locator("#submit_matrix").click()
    expect(page.locator("#select_submissions")).to_have_text("1")
    run.group["unset"] = json.loads(page.locator("#select_payload").inner_text())
    for index in range(3):
        page.get_by_role("combobox").nth(index).click()
        page.get_by_role("option", name="b", exact=True).click()
    page.locator("#submit_matrix").click()
    expect(page.locator("#select_submissions")).to_have_text("2")
    values = json.loads(page.locator("#select_payload").inner_text())
    run.group["filled"] = values
    for key in ("select_id", "select_name", "select_both_name"):
        run.check(f"submitted_{key}", values.get(key) == "b", values)
    run.shot(page, "select-matrix")


def forms(run, page):
    """Extend the original form run with nested-control leakage evidence.

    Args:
        run: Evidence collector.
        page: Browser page.
    """
    old.g_forms(run, page)
    unset = json.loads(run.group["payload_unset"])
    run.check("closed_dialog_controls_absent", not {"d_text", "d_check"} & unset.keys(), unset)


def recharts(run, page):
    """Check rendered tick text without assuming adaptive tick placement.

    Args:
        run: Evidence collector.
        page: Browser page.
    """
    run.goto(page, "/recharts", "#rc-run")
    page.wait_for_timeout(1500)
    patterns = {"literal": r"L\d+", "var_create": r"A\d+", "funcstr": r"\d+u", "partial": r"\$\d+", "args": r"\$\d+", "memo": r"\$\d+"}
    for name, pattern in patterns.items():
        values = page.locator(f"#rc_{name} text[orientation=bottom]").all_text_contents()
        run.check(f"formatter_{name}", bool(values) and all(re.fullmatch(pattern, value) for value in values), values)
    rejection = page.locator("#err-rc_untyped").all_text_contents()
    run.check("untyped_function_rejected", bool(rejection) and "FunctionVar" in rejection[0], rejection)
    page.locator("#rc-currency").click()
    expect(page.locator("#rc-cur")).to_contain_text("EUR")
    for name in ("partial", "args", "memo"):
        values = page.locator(f"#rc_{name} text[orientation=bottom]").all_text_contents()
        run.check(f"reactive_formatter_{name}", bool(values) and all(value.startswith("EUR ") for value in values), values)
    path = page.locator("#rc_literal .recharts-line-curve").get_attribute("d")
    page.locator("#rc-run").click()
    expect(page.locator("#rc-ticks")).to_have_text("ticks:20", timeout=30000)
    run.check("chart_updates", page.locator("#rc_literal .recharts-line-curve").get_attribute("d") != path)
    run.shot(page, "recharts", full=True)


def new_components(run, page):
    """Exercise local video, Lucide state and Sonner toast rendering.

    Args:
        run: Evidence collector.
        page: Browser page.
    """
    run.goto(page, "/new-components", "#media-toggle")
    page.locator("#media-toggle").click()
    expect(page.locator("#media-plays")).to_have_text("1", timeout=15000)
    page.wait_for_function("document.querySelector('video').currentTime > 0.1")
    run.check("video_playback", True, page.locator("video").evaluate("element => ({time: element.currentTime, paused: element.paused, ready: element.readyState})"))
    page.locator("#media-toggle").click()
    expect(page.locator("#media-pauses")).to_have_text("1")
    run.check("video_pauses", page.locator("video").evaluate("element => element.paused"))
    page.locator("#icon-toggle").click()
    expect(page.locator("#icon-selected")).to_have_text("true")
    run.check("lucide_icon_updates", page.locator("#icon-toggle svg").count() == 1)
    page.locator("#show-toast").click()
    expect(page.get_by_text("Local toast passed", exact=True)).to_be_visible()
    run.check("sonner_toast", True)
    run.shot(page, "new-components")


def main():
    """Run selected groups and write evidence after every group."""
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("out", type=Path)
    parser.add_argument("--browser", choices=["chromium", "webkit"], default="chromium")
    parser.add_argument("--groups", default="select_matrix,forms,recharts")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    run = old.Run(args.base, args.out, args.browser)
    groups = {**old.GROUPS, "select_matrix": select_matrix, "forms": forms, "recharts": recharts, "new_components": new_components}
    with sync_playwright() as playwright:
        browser = getattr(playwright, args.browser).launch()
        run.results["browser"] = {"engine": args.browser, "version": browser.version}
        for name in args.groups.split(","):
            run.start_group(name)
            context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
            page = context.new_page()
            run.attach(page)
            started = time.monotonic()
            try:
                groups[name](run, page)
            except Exception:
                run.check("exception", False, traceback.format_exc())
                run.shot(page, f"{name}-exception")
            run.group["seconds"] = time.monotonic() - started
            if name == "download":
                run.group["download_hashes"] = {}
                for downloaded in (args.out / "downloads").glob("*"):
                    data = downloaded.read_bytes()
                    run.group["download_hashes"][downloaded.name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                    downloaded.unlink()
            context.close()
            (args.out / "results.json").write_text(json.dumps(run.results, indent=2, default=str))
        browser.close()


if __name__ == "__main__":
    main()

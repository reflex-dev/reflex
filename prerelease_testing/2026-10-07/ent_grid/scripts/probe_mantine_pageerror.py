"""Locate the 'Cannot read properties of null (reading name)' page error on /qa-mantine step by step.

Usage: probe_mantine_pageerror.py <base_url> <expected_venv>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import assert_driver_and_server  # noqa: E402
from playwright.sync_api import sync_playwright

base, venv = sys.argv[1:3]
info = assert_driver_and_server(venv)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page(viewport={"width": 1400, "height": 900})
    errs = []
    p.on("pageerror", lambda e: errs.append(f"{e.message}\n{(e.stack or '')[:1500]}"))
    sent = []
    p.on("websocket", lambda ws: ws.on("framesent", lambda f: sent.append(str(f)[:250])))

    def step(name, fn):
        errs.clear(); sent.clear()
        fn()
        p.wait_for_timeout(1200)
        print(f"== {name}: page errors={len(errs)} sent={[x[:160] for x in sent]}")
        for e in errs:
            print("   ", e.replace("\n", "\n    "))

    step("load", lambda: p.goto(base + "/qa-mantine", wait_until="networkidle"))
    step("autocomplete click+type", lambda: (p.locator("#qa-autocomplete").click(), p.locator("#qa-autocomplete").type("Ba")))
    step("autocomplete option click", lambda: p.locator("[role=option]:has-text('Banana')").first.click())
    step("autocomplete Enter on typed value", lambda: (p.locator("#qa-autocomplete").fill("Cherry"), p.keyboard.press("Enter")))
    step("escape", lambda: p.keyboard.press("Escape"))
    step("multiselect open", lambda: (p.locator("#qa-multiselect").focus(), p.keyboard.press("ArrowDown")))
    step("multiselect click Vue", lambda: p.locator(".mantine-MultiSelect-option:visible:has-text('Vue')").first.click())
    print("fruit:", p.locator("#qa-fruit").inner_text(), "| picks:", p.locator("#qa-picks").inner_text())
    b.close()

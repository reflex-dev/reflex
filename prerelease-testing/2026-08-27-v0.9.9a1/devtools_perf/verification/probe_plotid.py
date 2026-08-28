"""Probe: does the id prop on rx.plotly reach the DOM?"""

import os
import sys

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:4000")
OUT = os.environ.get("OUT", "probe_plotid.png")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context().new_page()
    msgs = []
    page.on("console", lambda m: msgs.append(f"[{m.type}] {m.text[:300]}"))
    page.on("pageerror", lambda e: msgs.append(f"[pageerror] {e}"))
    page.goto(BASE_URL + "/", wait_until="load", timeout=60000)
    try:
        page.wait_for_selector(".js-plotly-plot", timeout=120000)
    except Exception as e:
        print("chart never appeared:", e)
    page.wait_for_timeout(2000)
    print("URL:", page.url)
    print("control-box exists:", page.locator("#control-box").count())
    print("the-plot exists:", page.locator("#the-plot").count())
    print("static-plot exists:", page.locator("#static-plot").count())
    print("plotly plots rendered (.js-plotly-plot):", page.locator(".js-plotly-plot").count())
    print("any element with id containing 'plot':",
          page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id).filter(i => i.includes('plot'))"))
    print("all ids on page:", page.evaluate("[...document.querySelectorAll('[id]')].map(e => e.id).slice(0, 30)"))
    # outerHTML skeleton of first plot container (trimmed)
    html = page.evaluate(
        "() => { const el = document.querySelector('.js-plotly-plot'); return el ? el.outerHTML.slice(0, 500) : null }"
    )
    print("first plot container outerHTML head:", html)
    page.screenshot(path=OUT, full_page=True)
    print("--- console ---")
    for m in msgs:
        print(m)
    browser.close()
sys.exit(0)

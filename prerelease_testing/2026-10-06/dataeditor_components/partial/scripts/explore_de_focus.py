"""Trace focus/overlay editor state while editing a text cell."""
import json
import sys

import playwright

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright  # noqa: E402

base, out = sys.argv[1], sys.argv[2]
W = [90, 60, 70, 60, 130, 80, 80, 80, 80, 70, 90, 60]
STATE = """() => { const a = document.activeElement; const ta = document.querySelector('#portal textarea, #portal input');
  return {active: a ? (a.tagName + '.' + (a.className||'').toString().slice(0,40)) : null, editor: ta ? {tag: ta.tagName, value: ta.value, selStart: ta.selectionStart, selEnd: ta.selectionEnd, focused: ta === a} : null, portal_len: (document.getElementById('portal')||{innerHTML:''}).innerHTML.length}; }"""


def xy(box, col, row):
    return box["x"] + 32 + sum(W[:col]) + W[col] / 2, box["y"] + 36 + row * 60 + 30


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.goto(base + "/de", wait_until="domcontentloaded", timeout=120000)
    pg.wait_for_selector("#de-main-box canvas", timeout=120000)
    pg.wait_for_timeout(4000)
    box = pg.locator("#de-main-box canvas").first.bounding_box()
    log = []
    x, y = xy(box, 0, 1)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(500)
    log.append(("after click", pg.evaluate(STATE)))
    pg.keyboard.press("S")
    for t in (0, 50, 150, 400):
        pg.wait_for_timeout(t)
        log.append((f"after 'S' +{t}ms", pg.evaluate(STATE)))
    pg.screenshot(path=f"{out}-after-S.png")
    pg.keyboard.press("l")
    pg.wait_for_timeout(200)
    log.append(("after 'l'", pg.evaluate(STATE)))
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(500)
    x, y = xy(box, 0, 3)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(400)
    pg.keyboard.press("Enter")
    for t in (0, 100, 400):
        pg.wait_for_timeout(t)
        log.append((f"after Enter +{t}ms", pg.evaluate(STATE)))
    pg.screenshot(path=f"{out}-after-Enter.png")
    pg.keyboard.type("X")
    pg.wait_for_timeout(200)
    log.append(("after typing X in enter-opened editor", pg.evaluate(STATE)))
    print(json.dumps(log, indent=1))
    b.close()

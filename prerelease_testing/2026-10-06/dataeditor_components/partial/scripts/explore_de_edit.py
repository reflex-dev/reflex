"""Calibrate data editor interactions: bool toggle, typing speed, activation."""
import json
import sys

import playwright

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright  # noqa: E402

base = sys.argv[1]
W = [90, 60, 70, 60, 130, 80, 80, 80, 80, 70, 90, 60]


def xy(box, col, row):
    return box["x"] + 32 + sum(W[:col]) + W[col] / 2, box["y"] + 36 + row * 60 + 30


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
    pg.goto(base + "/de", wait_until="domcontentloaded", timeout=120000)
    pg.wait_for_selector("#de-main-box canvas", timeout=120000)
    pg.wait_for_timeout(4000)
    box = pg.locator("#de-main-box canvas").first.bounding_box()
    T = lambda s: pg.locator(s).first.inner_text()  # noqa: E731
    out = {}
    # bool: single click
    x, y = xy(box, 3, 0)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(1200)
    out["bool_after_1_click"] = (T("#edits"), T("#last-edit")[:120])
    pg.mouse.click(x, y)
    pg.wait_for_timeout(1200)
    out["bool_after_2_clicks_1s_apart"] = (T("#edits"), T("#last-edit")[:120])
    # typing slow
    x, y = xy(box, 0, 1)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(500)
    pg.keyboard.type("Slow", delay=120)
    pg.wait_for_timeout(500)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1200)
    out["slow_typing"] = (T("#edits"), T("#last-edit")[:160])
    # typing fast
    x, y = xy(box, 0, 2)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(500)
    pg.keyboard.type("Fast")
    pg.wait_for_timeout(500)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1200)
    out["fast_typing"] = (T("#edits"), T("#last-edit")[:160])
    # Enter-then-type
    x, y = xy(box, 0, 3)
    pg.mouse.click(x, y)
    pg.wait_for_timeout(300)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(800)
    out["activated_after_enter"] = T("#last-activated")
    pg.keyboard.press("Control+a")
    pg.keyboard.type("ViaEnter")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1200)
    out["enter_then_type"] = (T("#edits"), T("#last-edit")[:160])
    # dblclick activation
    x, y = xy(box, 0, 6)
    pg.mouse.dblclick(x, y)
    pg.wait_for_timeout(1000)
    out["activated_after_dblclick_0_6"] = T("#last-activated")
    pg.keyboard.press("Escape")
    out["pageerrors"] = errs
    print(json.dumps(out, indent=1, ensure_ascii=False))
    b.close()

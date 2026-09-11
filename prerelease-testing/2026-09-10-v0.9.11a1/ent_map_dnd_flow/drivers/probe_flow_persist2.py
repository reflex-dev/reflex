"""Probe 2: flow node-position persistence + multi-select delete, using flow
coordinates (the inline `transform: translate()` xyflow writes on each node,
which is viewport-independent) and the "Default Node" that drive_flow.py drags.

Usage: probe_flow_persist2.py <base_url> <shots_dir>
"""

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)
out = {}


def pos_of(node):
    style = node.get_attribute("style") or ""
    m = re.search(r"translate\(([-\d.]+)px,\s*([-\d.]+)px\)", style)
    return [round(float(m.group(1)), 1), round(float(m.group(2)), 1)] if m else None


def default_node(page):
    n = page.locator(".react-flow__node").filter(has_text="Default Node").first
    return n


def center(b):
    return (b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/overview", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)

    n = default_node(page)
    out["before"] = pos_of(n)
    b = n.bounding_box()
    c = center(b)
    page.mouse.move(*c)
    page.mouse.down()
    for i in range(1, 15):
        page.mouse.move(c[0] + 8 * i, c[1] + 5 * i)
        page.wait_for_timeout(35)
    page.mouse.up()
    page.wait_for_timeout(3000)
    out["after_drag"] = pos_of(default_node(page))
    page.screenshot(path=str(SHOTS / "q01_after_drag.png"))

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(4500)
    out["after_hard_reload"] = pos_of(default_node(page))
    page.screenshot(path=str(SHOTS / "q02_after_reload.png"))

    page.goto(BASE + "/nodes/custom-node", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2500)
    page.go_back()
    page.wait_for_timeout(4500)
    out["after_spa_back"] = pos_of(default_node(page))
    page.screenshot(path=str(SHOTS / "q03_after_spa_back.png"))

    # multi-select via shift box-drag, then Backspace (xyflow's deleteKeyCode)
    n_before = page.locator(".react-flow__node").count()
    pane = page.locator(".react-flow__pane").first.bounding_box()
    a = (pane["x"] + 20, pane["y"] + 20)
    z = (pane["x"] + pane["width"] - 20, pane["y"] + pane["height"] - 20)
    page.keyboard.down("Shift")
    page.mouse.move(*a)
    page.mouse.down()
    for i in range(1, 19):
        page.mouse.move(a[0] + (z[0] - a[0]) * i / 18, a[1] + (z[1] - a[1]) * i / 18)
        page.wait_for_timeout(25)
    page.mouse.up()
    page.keyboard.up("Shift")
    page.wait_for_timeout(900)
    sel = page.locator(".react-flow__node.selected").count()
    page.keyboard.press("Backspace")
    page.wait_for_timeout(3000)
    n_after = page.locator(".react-flow__node").count()
    out["multiselect"] = {"selected": sel, "before": n_before, "after": n_after}
    page.screenshot(path=str(SHOTS / "q04_after_multiselect_backspace.png"))

    page.reload(wait_until="networkidle")
    page.wait_for_timeout(4000)
    out["multiselect_after_reload"] = page.locator(".react-flow__node").count()

    print(json.dumps(out, indent=2))
    (SHOTS / "probe_persist2.json").write_text(json.dumps(out, indent=2))
    ctx.close()
    browser.close()

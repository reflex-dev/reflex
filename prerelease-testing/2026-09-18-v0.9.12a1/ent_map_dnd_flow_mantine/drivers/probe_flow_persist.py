"""Probe: does the /overview node drag + delete round-trip into backend state?

Drags node 0, then (a) hard-reloads and (b) navigates away and back, printing the
node's flow-coordinate `transform` and the node count each time. Flow coordinates
are read from the node element's inline `transform: translate(x,y)` which xyflow
sets from the node's own position (independent of the viewport fit_view zoom).

Usage: probe_flow_persist.py <base_url> <shots_dir>
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


def node_state(page):
    els = page.locator(".react-flow__node")
    n = els.count()
    tr = []
    for i in range(n):
        style = els.nth(i).get_attribute("style") or ""
        m = re.search(r"translate\(([-\d.]+)px,\s*([-\d.]+)px\)", style)
        tr.append([round(float(m.group(1)), 1), round(float(m.group(2)), 1)] if m else None)
    return {"count": n, "positions": tr}


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: console.append(f"PAGEERROR: {e}"))

    page.goto(BASE + "/overview", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)
    out["initial"] = node_state(page)

    node = page.locator(".react-flow__node").nth(0)
    b = node.bounding_box()
    cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
    page.mouse.move(cx, cy)
    page.mouse.down()
    for i in range(1, 15):
        page.mouse.move(cx + 8 * i, cy + 5 * i)
        page.wait_for_timeout(35)
    page.mouse.up()
    page.wait_for_timeout(3000)
    out["after_drag"] = node_state(page)
    page.screenshot(path=str(SHOTS / "p01_after_drag.png"))

    # (a) hard reload -> state comes from the backend
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(4000)
    out["after_hard_reload"] = node_state(page)
    page.screenshot(path=str(SHOTS / "p02_after_reload.png"))

    # (b) delete a node, then hard reload
    n0 = page.locator(".react-flow__node").count()
    page.locator(".react-flow__node").nth(n0 - 1).click()
    page.wait_for_timeout(600)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(2500)
    out["after_delete"] = node_state(page)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(4000)
    out["after_delete_reload"] = node_state(page)
    page.screenshot(path=str(SHOTS / "p03_after_delete_reload.png"))

    # (c) SPA navigation away and back
    page.locator('a[href="/nodes/custom-node"]').first.click() if page.locator(
        'a[href="/nodes/custom-node"]'
    ).count() else page.goto(BASE + "/nodes/custom-node")
    page.wait_for_timeout(2500)
    page.go_back()
    page.wait_for_timeout(4000)
    out["after_spa_back"] = node_state(page)
    page.screenshot(path=str(SHOTS / "p04_after_spa_back.png"))

    # (d) Delete key (not Backspace) on a single selected node
    n1 = page.locator(".react-flow__node").count()
    page.locator(".react-flow__node").nth(n1 - 1).click()
    page.wait_for_timeout(600)
    sel = page.locator(".react-flow__node.selected").count()
    page.keyboard.press("Delete")
    page.wait_for_timeout(2500)
    out["delete_key"] = {"selected": sel, **node_state(page)}

    out["console_tail"] = console[-25:]
    print(json.dumps(out, indent=2))
    (SHOTS / "probe_persist.json").write_text(json.dumps(out, indent=2))
    ctx.close()
    browser.close()

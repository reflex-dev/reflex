"""Playwright driver for the reflex-enterprise flow (React Flow / xyflow) demo.

Usage: python drive_flow.py <base_url> <shots_dir>
Exercises: index links, /overview render + node drag (state round-trip),
/nodes/custom-node render, /nodes/drag-handle drag via handle,
/nodes/connection-limit connect + limit enforcement,
/nodes/add-node-on-edge-drop drop-on-pane node creation.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)

results = []
console_lines = []
page_errors = []
req_failures = []

BENIGN_SNIPPETS = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Download the React DevTools",
)


def check(name, ok, details=""):
    results.append({"name": name, "ok": bool(ok), "details": details})
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} :: {details}")


def snap(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)


def drag(page, from_xy, to_xy, steps=12):
    page.mouse.move(*from_xy)
    page.mouse.down()
    dx = (to_xy[0] - from_xy[0]) / steps
    dy = (to_xy[1] - from_xy[1]) / steps
    for i in range(1, steps + 1):
        page.mouse.move(from_xy[0] + dx * i, from_xy[1] + dy * i)
        page.wait_for_timeout(30)
    page.mouse.up()


def center(box):
    return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: console_lines.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "requestfailed",
        lambda r: req_failures.append(f"{r.method} {r.url} :: {r.failure}"),
    )
    page.on(
        "response",
        lambda r: req_failures.append(f"HTTP{r.status} {r.url}")
        if r.status >= 400
        else None,
    )

    # 1. index
    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    snap(page, "01_index")
    nlinks = page.locator("a[href^='/nodes/'], a[href='/overview']").count()
    check("index_renders_links", nlinks >= 6, f"links={nlinks}")

    # 2. /overview render
    page.goto(BASE + "/overview", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)
    snap(page, "02_overview")
    nodes = page.locator(".react-flow__node").count()
    edges = page.locator(".react-flow__edge").count()
    minimap = page.locator(".react-flow__minimap").count()
    controls = page.locator(".react-flow__controls").count()
    check(
        "overview_renders",
        nodes >= 5 and edges >= 1 and minimap == 1 and controls == 1,
        f"nodes={nodes} edges={edges} minimap={minimap} controls={controls}",
    )

    # 3. /overview drag a node, verify position sticks (state round-trip)
    try:
        node = page.locator(".react-flow__node").filter(has_text="Default Node").first
        if node.count() == 0:
            node = page.locator(".react-flow__node").nth(1)
        before = node.bounding_box()
        drag(page, center(before), (center(before)[0] + 80, center(before)[1] + 60))
        page.wait_for_timeout(2500)  # allow server round-trip + re-render
        after = node.bounding_box()
        moved = abs(after["x"] - before["x"]) > 40 and abs(after["y"] - before["y"]) > 30
        snap(page, "03_overview_after_drag")
        check(
            "overview_node_drag_roundtrip",
            moved,
            f"before=({before['x']:.0f},{before['y']:.0f}) after=({after['x']:.0f},{after['y']:.0f})",
        )
    except Exception as e:
        snap(page, "03_overview_drag_fail")
        check("overview_node_drag_roundtrip", False, f"exception: {e}")

    # 4. /overview toolbar emoji node: toolbar is always visible; click the fire emoji
    try:
        tools_node = page.locator(".react-flow__node-tools").first
        btn = page.locator("button[aria-label='Select emoji \U0001f525']").first
        btn.click(timeout=5000)
        page.wait_for_timeout(2000)
        ok = "\U0001f525" in (tools_node.inner_text() or "")
        snap(page, "04_overview_toolbar_emoji")
        check("overview_toolbar_emoji", ok, f"node text now: {tools_node.inner_text()!r}")
    except Exception as e:
        snap(page, "04_overview_toolbar_fail")
        check("overview_toolbar_emoji", False, f"exception: {e}")

    # 5. /nodes/custom-node
    page.goto(BASE + "/nodes/custom-node", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    snap(page, "05_custom_node")
    n = page.locator(".react-flow__node").count()
    check("custom_node_renders", n >= 1, f"nodes={n}")

    # 6. /nodes/drag-handle: drag via the handle span only
    page.goto(BASE + "/nodes/drag-handle", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    snap(page, "06_drag_handle")
    try:
        node = page.locator(".react-flow__node").first
        before = node.bounding_box()
        handle = page.locator(".drag-handle__custom").first
        hb = handle.bounding_box()
        drag(page, center(hb), (center(hb)[0] + 100, center(hb)[1] + 60))
        page.wait_for_timeout(1500)
        after = node.bounding_box()
        moved = abs(after["x"] - before["x"]) > 50
        # also verify dragging the node body does NOT move it
        nb = node.bounding_box()
        body_pt = (nb["x"] + 20, nb["y"] + nb["height"] / 2)
        drag(page, body_pt, (body_pt[0] - 100, body_pt[1] - 50))
        page.wait_for_timeout(1000)
        after2 = node.bounding_box()
        body_static = abs(after2["x"] - after["x"]) < 5 and abs(after2["y"] - after["y"]) < 5
        snap(page, "07_drag_handle_after")
        check("drag_handle_moves_via_handle", moved, f"dx={after['x'] - before['x']:.0f}")
        check("drag_handle_body_not_draggable", body_static, f"dx2={after2['x'] - after['x']:.0f}")
    except Exception as e:
        snap(page, "07_drag_handle_fail")
        check("drag_handle_moves_via_handle", False, f"exception: {e}")

    # 7. /nodes/connection-limit: connect Node1 -> custom, then Node2 -> custom refused
    page.goto(BASE + "/nodes/connection-limit", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    snap(page, "08_connection_limit")
    try:
        src1 = page.locator(".react-flow__node", has_text="Node 1").locator(
            ".react-flow__handle.source"
        ).first
        tgt = page.locator(".react-flow__node", has_text="Only one edge allowed").locator(
            ".react-flow__handle.target"
        ).first
        drag(page, center(src1.bounding_box()), center(tgt.bounding_box()))
        page.wait_for_timeout(2500)
        edges1 = page.locator(".react-flow__edge").count()
        snap(page, "09_connection_limit_first_edge")
        check("connection_limit_first_connect", edges1 == 1, f"edges={edges1}")
        src2 = page.locator(".react-flow__node", has_text="Node 2").locator(
            ".react-flow__handle.source"
        ).first
        drag(page, center(src2.bounding_box()), center(tgt.bounding_box()))
        page.wait_for_timeout(2500)
        edges2 = page.locator(".react-flow__edge").count()
        snap(page, "10_connection_limit_second_refused")
        check("connection_limit_enforced", edges2 == 1, f"edges after 2nd attempt={edges2}")
    except Exception as e:
        snap(page, "10_connection_limit_fail")
        check("connection_limit_first_connect", False, f"exception: {e}")

    # 8. /nodes/add-node-on-edge-drop: drag from source handle to empty pane -> new node
    page.goto(BASE + "/nodes/add-node-on-edge-drop", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    snap(page, "11_edge_drop")
    try:
        n_before = page.locator(".react-flow__node").count()
        handle = page.locator(".react-flow__handle.source").first
        hb = handle.bounding_box()
        drag(page, center(hb), (center(hb)[0] + 150, center(hb)[1] + 180))
        page.wait_for_timeout(3000)
        n_after = page.locator(".react-flow__node").count()
        e_after = page.locator(".react-flow__edge").count()
        snap(page, "12_edge_drop_after")
        check(
            "edge_drop_creates_node",
            n_after == n_before + 1 and e_after == 1,
            f"nodes {n_before}->{n_after}, edges={e_after}",
        )
    except Exception as e:
        snap(page, "12_edge_drop_fail")
        check("edge_drop_creates_node", False, f"exception: {e}")

    # 9. /nodes/intersections: drag node 2 over node 1, others should highlight
    page.goto(BASE + "/nodes/intersections", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    snap(page, "13_intersections")
    try:
        n2 = page.locator(".react-flow__node", has_text="Node 2").first
        n1 = page.locator(".react-flow__node", has_text="Node 1").first
        drag(page, center(n2.bounding_box()), center(n1.bounding_box()))
        page.wait_for_timeout(2000)
        highlighted = page.locator(".react-flow__node.highlight").count()
        snap(page, "14_intersections_after")
        check("intersections_highlight", highlighted >= 1, f"highlighted={highlighted}")
    except Exception as e:
        snap(page, "14_intersections_fail")
        check("intersections_highlight", False, f"exception: {e}")

    browser.close()

interesting_console = [
    line
    for line in console_lines
    if not any(s in line for s in BENIGN_SNIPPETS)
    and line.split(":", 1)[0] in ("error", "warning")
]
print("\n=== CONSOLE (error/warning, non-benign) ===")
for line in interesting_console:
    print("CONSOLE", line)
print("=== PAGE ERRORS ===")
for e in page_errors:
    print("PAGEERROR", e)
print("=== REQUEST FAILURES / 4xx-5xx ===")
for r in req_failures:
    print("REQFAIL", r)

(SHOTS / "results.json").write_text(
    json.dumps(
        {
            "results": results,
            "console_all": console_lines,
            "page_errors": page_errors,
            "req_failures": req_failures,
        },
        indent=2,
    )
)
fails = [r for r in results if not r["ok"]]
print(f"\nSUMMARY: {len(results) - len(fails)}/{len(results)} passed")

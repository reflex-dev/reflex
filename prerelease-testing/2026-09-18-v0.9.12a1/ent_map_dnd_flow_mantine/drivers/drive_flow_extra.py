"""Extra flow-demo checks not covered by drive_flow.py.

Focus: node/edge DELETION through the on_nodes_change / on_edges_change ->
apply_node_changes/apply_edge_changes state round-trip, multi-select box
deletion, SPA navigation between flow routes, and state persistence across
client-side navigation.

Usage: drive_flow_extra.py <base_url> <shots_dir>
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

BENIGN = (
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
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def center(box):
    return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def drag(page, a, b, steps=14):
    page.mouse.move(*a)
    page.mouse.down()
    dx, dy = (b[0] - a[0]) / steps, (b[1] - a[1]) / steps
    for i in range(1, steps + 1):
        page.mouse.move(a[0] + dx * i, a[1] + dy * i)
        page.wait_for_timeout(30)
    page.mouse.up()


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on("console", lambda m: console_lines.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda r: req_failures.append(f"{r.method} {r.url} :: {r.failure}"))
    page.on(
        "response",
        lambda r: req_failures.append(f"HTTP{r.status} {r.url}") if r.status >= 400 else None,
    )

    # ---------------- /overview: delete a node with the keyboard -----------
    page.goto(BASE + "/overview", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)
    n0 = page.locator(".react-flow__node").count()
    e0 = page.locator(".react-flow__edge").count()
    # pick a leaf-ish node: the last one in DOM order
    target = page.locator(".react-flow__node").nth(n0 - 1)
    tbox = target.bounding_box()
    page.mouse.click(*center(tbox))
    page.wait_for_timeout(700)
    selected = page.locator(".react-flow__node.selected").count()
    check("overview_node_selectable", selected == 1, f"selected={selected}")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(2000)
    n1 = page.locator(".react-flow__node").count()
    e1 = page.locator(".react-flow__edge").count()
    check("overview_node_delete", n1 == n0 - 1, f"nodes {n0} -> {n1}")
    snap(page, "x01_overview_after_node_delete")

    # the delete must survive the backend round-trip: nothing snaps back
    page.wait_for_timeout(2500)
    n1b = page.locator(".react-flow__node").count()
    check("overview_node_delete_sticks", n1b == n1, f"nodes after settle={n1b}")

    # ---------------- /overview: delete an edge ---------------------------
    edges = page.locator(".react-flow__edge")
    ecount = edges.count()
    if ecount:
        ebox = edges.nth(0).locator(".react-flow__edge-interaction, path").first.bounding_box()
        if ebox:
            page.mouse.click(*center(ebox))
            page.wait_for_timeout(600)
        sel_e = page.locator(".react-flow__edge.selected").count()
        if sel_e:
            page.keyboard.press("Backspace")
            page.wait_for_timeout(2000)
        e2 = page.locator(".react-flow__edge").count()
        check("overview_edge_delete", e2 < ecount, f"edges {ecount} -> {e2} (selected={sel_e})")
    else:
        check("overview_edge_delete", False, "no edges present to delete")
    snap(page, "x02_overview_after_edge_delete")

    # ---------------- /overview: multi-select box + delete ----------------
    n_before = page.locator(".react-flow__node").count()
    pane = page.locator(".react-flow__pane").first.bounding_box()
    page.keyboard.down("Shift")
    drag(
        page,
        (pane["x"] + 20, pane["y"] + 20),
        (pane["x"] + pane["width"] - 20, pane["y"] + pane["height"] - 20),
        steps=18,
    )
    page.keyboard.up("Shift")
    page.wait_for_timeout(800)
    n_sel = page.locator(".react-flow__node.selected").count()
    # xyflow deleteKeyCode defaults to Backspace (the Delete key is a no-op upstream)
    page.keyboard.press("Backspace")
    page.wait_for_timeout(3000)
    n_after = page.locator(".react-flow__node").count()
    check(
        "overview_multiselect_delete",
        n_sel > 1 and n_after < n_before,
        f"selected={n_sel} nodes {n_before} -> {n_after}",
    )
    snap(page, "x03_overview_after_multi_delete")

    # ---------------- /nodes/connection-limit: connect then delete edge ----
    page.goto(BASE + "/nodes/connection-limit", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3500)
    handles = page.locator(".react-flow__handle")
    src = handles.nth(0).bounding_box()
    # find a target handle on a different node
    tgt = None
    for i in range(1, handles.count()):
        b = handles.nth(i).bounding_box()
        if b and abs(b["y"] - src["y"]) > 30:
            tgt = b
            break
    if tgt:
        drag(page, center(src), center(tgt), steps=16)
        page.wait_for_timeout(2000)
    made = page.locator(".react-flow__edge").count()
    check("cl_connect_creates_edge", made >= 1, f"edges={made}")
    if made:
        eb = page.locator(".react-flow__edge").nth(0).locator("path").first.bounding_box()
        if eb:
            page.mouse.click(*center(eb))
            page.wait_for_timeout(600)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(2000)
    left = page.locator(".react-flow__edge").count()
    check("cl_edge_delete", left < made, f"edges {made} -> {left}")
    snap(page, "x04_connection_limit_after_delete")

    # ---------------- SPA navigation across flow routes -------------------
    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1500)
    routes = [
        "/overview",
        "/nodes/custom-node",
        "/nodes/drag-handle",
        "/nodes/connection-limit",
        "/nodes/add-node-on-edge-drop",
        "/nodes/intersections",
    ]
    nav_problems = []
    for r in routes:
        link = page.locator(f'a[href="{r}"]').first
        if link.count() == 0:
            nav_problems.append(f"no link {r}")
            continue
        link.click()
        page.wait_for_timeout(2500)
        if not page.url.endswith(r):
            nav_problems.append(f"{r}: url={page.url}")
        try:
            page.wait_for_selector(".react-flow__node", timeout=15000)
        except Exception as e:  # noqa: BLE001
            nav_problems.append(f"{r}: no nodes ({e!r})")
        page.go_back()
        page.wait_for_timeout(1800)
    check("flow_spa_nav_all_routes", not nav_problems, "; ".join(nav_problems))
    snap(page, "x05_after_spa_nav")

    # ---------------- state survives SPA navigation away and back ---------
    # Compare xyflow FLOW coordinates (the inline transform: translate() each
    # node carries), not screen coordinates: fit_view=True re-fits the viewport
    # on every remount, so screen coordinates legitimately change.
    import re as _re

    def flow_pos(loc):
        style = loc.get_attribute("style") or ""
        m = _re.search(r"translate\(([-\d.]+)px,\s*([-\d.]+)px\)", style)
        return (round(float(m.group(1)), 1), round(float(m.group(2)), 1)) if m else None

    # fresh context -> fresh session token -> pristine OverviewState (the
    # deletions above are persisted per-session and would remove the node).
    ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx2.new_page()
    page.on("console", lambda m: console_lines.append(f"{m.type}: {m.text}"))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda r: req_failures.append(f"{r.method} {r.url} :: {r.failure}"))
    page.goto(BASE + "/overview", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(4000)
    dn = page.locator(".react-flow__node").filter(has_text="Default Node").first
    p0 = flow_pos(dn)
    b0 = dn.bounding_box()
    drag(page, center(b0), (center(b0)[0] + 90, center(b0)[1] + 60))
    page.wait_for_timeout(3000)
    p1 = flow_pos(page.locator(".react-flow__node").filter(has_text="Default Node").first)
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(4000)
    p2 = flow_pos(page.locator(".react-flow__node").filter(has_text="Default Node").first)
    page.goto(BASE + "/nodes/custom-node", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    page.go_back()
    page.wait_for_timeout(4000)
    p3 = flow_pos(page.locator(".react-flow__node").filter(has_text="Default Node").first)
    check(
        "overview_position_persists_reload_and_nav",
        p0 != p1 and p1 == p2 == p3,
        f"start={p0} dragged={p1} reload={p2} spa_back={p3}",
    )
    snap(page, "x06_position_after_nav_back")

    nonbenign = [
        c
        for c in console_lines
        if (c.startswith("error") or c.startswith("warning"))
        and not any(b in c for b in BENIGN)
    ]
    print("\n=== CONSOLE (error/warning, non-benign) ===")
    for c in nonbenign[:25]:
        print("  ", c[:300])
    print("=== PAGE ERRORS ===")
    for e in page_errors[:15]:
        print("  ", e[:300])
    print("=== REQUEST FAILURES / 4xx-5xx ===")
    for r in req_failures[:15]:
        print("  ", r[:300])

    (SHOTS / "results_extra.json").write_text(
        json.dumps(
            {
                "results": results,
                "console_nonbenign": nonbenign,
                "page_errors": page_errors,
                "req_failures": req_failures,
                "console_all": console_lines,
            },
            indent=2,
        )
    )
    ok = sum(1 for r in results if r["ok"])
    print(f"\nSUMMARY: {ok}/{len(results)} passed")
    ctx2.close()
    ctx.close()
    browser.close()

sys.exit(0 if ok == len(results) else 1)

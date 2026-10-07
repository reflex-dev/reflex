"""Drive the enterprise flow (React Flow) demo with real pointer drags.

Usage: drive_flow.py <base_url> <out_dir> <expected_venv> <label>
"""
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)


def tr(p, nid):
    st = p.locator(f'.react-flow__node[data-id="{nid}"]').get_attribute("style") or ""
    m = re.search(r"translate\(([-\d.]+)px, ([-\d.]+)px\)", st)
    return (float(m.group(1)), float(m.group(2))) if m else None


def center(loc):
    b = loc.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def drag(p, x0, y0, x1, y1, steps=20):
    p.mouse.move(x0, y0)
    p.mouse.down()
    p.mouse.move(x0 + 3, y0 + 3, steps=2)
    p.mouse.move(x1, y1, steps=steps)
    p.wait_for_timeout(150)
    p.mouse.up()


def edges(p):
    return p.locator(".react-flow__edge").count()


def go(p, route):
    p.goto(base + route, wait_until="networkidle")
    p.wait_for_selector(".react-flow__node", timeout=20000)
    p.wait_for_timeout(1200)


def scenario(s, name, fn, *a):
    try:
        fn(*a)
    except Exception:
        s.check(f"{name}: scenario completed", False, traceback.format_exc()[-700:])


def overview(s, ctx, p):
    go(p, "/overview")
    s.check("overview: 11 nodes and 6 edges render", p.locator(".react-flow__node").count() == 11 and edges(p) == 6,
            {"nodes": p.locator(".react-flow__node").count(), "edges": edges(p)})
    s.check("overview: minimap + controls + background present",
            all(p.locator(c).count() for c in (".react-flow__minimap", ".react-flow__controls", ".react-flow__background")))
    before = tr(p, "1-2")
    x, y = center(p.locator('.react-flow__node[data-id="1-2"]'))
    drag(p, x, y, x - 120, y + 60)
    p.wait_for_timeout(1000)
    after = tr(p, "1-2")
    s.check("overview: pointer drag moves Default Node (on_nodes_change -> State.set_nodes)", after and before and after != before, {"before": before, "after": after})
    # toolbar emoji
    p.click("button[aria-label='Select emoji 🔥']")
    p.wait_for_timeout(800)
    s.check("overview: toolbar button sets State.emoji (🔥 shown in tools node)", "🔥" in p.locator('.react-flow__node[data-id="2-2"]').inner_text(),
            p.locator('.react-flow__node[data-id="2-2"]').inner_text())
    # button edge delete (×)
    n0 = edges(p)
    # a pointer click on the first × lands on an overlapping edge-interaction path (see probe_flow_edge_button.py); dispatch the click on the button
    p.locator(".button-edge__button").first.evaluate("e => e.click()")
    p.wait_for_timeout(1000)
    s.check("overview: × on a button edge removes it (run_script set_edges)", edges(p) == n0 - 1, {"before": n0, "after": edges(p)})
    # dimension input -> resizer node width
    w_in = p.locator(".react-flow__node-textinput input").first
    w_in.fill("120")
    p.wait_for_timeout(1200)
    st = p.locator('.react-flow__node[data-id="2-3"]').get_attribute("style")
    s.check("overview: 'Node width' input resizes node 2-3 via State.set_dimensions", "width: 120px" in (st or ""), st)
    # select + Delete key removes a node
    p.locator('.react-flow__node[data-id="1-3"]').click()
    try:
        p.wait_for_selector('.react-flow__node[data-id="1-3"].selected', timeout=5000)
        s.note("overview: Output Node shows .selected after click (controlled nodes round trip)")
    except Exception:
        s.note("overview: Output Node never got .selected within 5s")
    p.keyboard.press("Backspace")
    p.wait_for_timeout(1000)
    s.check("overview: Backspace deletes the selected Output Node", p.locator('.react-flow__node[data-id="1-3"]').count() == 0, p.locator(".react-flow__node").count())
    # zoom control
    vp0 = p.locator(".react-flow__viewport").get_attribute("style")
    p.click(".react-flow__controls-zoomin")
    p.wait_for_timeout(600)
    vp1 = p.locator(".react-flow__viewport").get_attribute("style")
    s.check("overview: controls zoom-in changes the viewport transform", vp0 != vp1, {"before": vp0, "after": vp1})
    s.shot(p, "overview-after")
    moved = tr(p, "1-2")
    p.reload(wait_until="networkidle")
    p.wait_for_selector(".react-flow__node", timeout=20000)
    p.wait_for_timeout(1500)
    s.check("overview: after reload the moved position, deleted node and emoji persist (session state)",
            tr(p, "1-2") == moved and p.locator('.react-flow__node[data-id="1-3"]').count() == 0 and "🔥" in p.locator('.react-flow__node[data-id="2-2"]').inner_text(),
            {"moved": moved, "now": tr(p, "1-2")})


def add_on_drop(s, ctx, p, browser_new_ctx):
    go(p, "/nodes/add-node-on-edge-drop")
    n0 = p.locator(".react-flow__node").count()
    hx, hy = center(p.locator('.react-flow__node[data-id="0"] .react-flow__handle.source'))
    drag(p, hx, hy, hx + 60, hy + 220)
    p.wait_for_timeout(1500)
    n1 = p.locator(".react-flow__node").count()
    s.check("add-node-on-edge-drop: dropping a connection on the pane adds Node 1 + an edge (on_connect_end + screen_to_flow_position)",
            n1 == n0 + 1 and edges(p) == 1 and "Node 1" in p.locator(".react-flow__nodes").inner_text(), {"before": n0, "after": n1, "edges": edges(p)})
    drag(p, hx, hy, hx - 160, hy + 200)
    p.wait_for_timeout(1500)
    s.check("add-node-on-edge-drop: second drop adds Node 2", "Node 2" in p.locator(".react-flow__nodes").inner_text(), p.locator(".react-flow__nodes").inner_text())
    s.shot(p, "add-node-on-edge-drop")
    # another browser context = another session: must start from the initial single node
    q = browser_new_ctx()
    go(q, "/nodes/add-node-on-edge-drop")
    s.check("add-node-on-edge-drop: a new session starts with only the initial node (no cross-session leak of default_factory list)",
            q.locator(".react-flow__node").count() == 1, q.locator(".react-flow__nodes").inner_text())


def connection_limit(s, ctx, p):
    go(p, "/nodes/connection-limit")
    tgt = p.locator('.react-flow__node[data-id="2"] .react-flow__handle.target')
    tx, ty = center(tgt)
    sx, sy = center(p.locator('.react-flow__node[data-id="1"] .react-flow__handle.source'))
    drag(p, sx, sy, tx, ty)
    p.wait_for_timeout(1200)
    s.check("connection-limit: Node 1 -> custom target handle creates an edge", edges(p) == 1, edges(p))
    sx, sy = center(p.locator('.react-flow__node[data-id="3"] .react-flow__handle.source'))
    drag(p, sx, sy, tx, ty)
    p.wait_for_timeout(1200)
    s.check("connection-limit: second connection to the same handle is refused (is_connectable from get_node_connections)", edges(p) == 1, edges(p))
    s.shot(p, "connection-limit")


def custom_node(s, ctx, p):
    go(p, "/nodes/custom-node")
    p.locator('.react-flow__node[data-id="2"] input[type=color]').fill("#ff0000")
    p.wait_for_timeout(1200)
    txt = p.locator('.react-flow__node[data-id="2"]').inner_text()
    bg = p.locator(".react-flow__background").evaluate("e => getComputedStyle(e).backgroundColor")
    s.check("custom-node: color input -> State.on_change_color updates node label", "#ff0000" in txt, txt)
    s.check("custom-node: background bg_color follows State", bg in ("rgb(255, 0, 0)",), bg)
    mm = p.locator(".react-flow__minimap-node").evaluate_all("els => els.map(e => e.style.fill)")
    s.check("custom-node: minimap node_color (ArgsFunctionOperation + rx.match on State var) uses the new color", "rgb(255, 0, 0)" in mm, mm)
    # connect output B target from node 1 source -> new animated edge
    n0 = edges(p)
    sx, sy = center(p.locator('.react-flow__node[data-id="1"] .react-flow__handle.source'))
    tx, ty = center(p.locator('.react-flow__node[data-id="4"] .react-flow__handle.target'))
    drag(p, sx, sy, tx, ty)
    p.wait_for_timeout(1200)
    s.check("custom-node: on_connect adds an animated edge (connection.merge({animated: true}))", edges(p) == n0 + 1 and p.locator(".react-flow__edge.animated").count() == n0 + 1,
            {"before": n0, "after": edges(p), "animated": p.locator(".react-flow__edge.animated").count()})
    s.shot(p, "custom-node")


def drag_handle(s, ctx, p):
    go(p, "/nodes/drag-handle")
    before = tr(p, "2")
    lx, ly = center(p.locator(".drag-handle__label"))
    drag(p, lx - 40, ly, lx - 40 + 80, ly + 80)
    p.wait_for_timeout(600)
    mid = tr(p, "2")
    hx, hy = center(p.locator(".drag-handle__custom"))
    drag(p, hx, hy, hx + 80, hy + 80)
    p.wait_for_timeout(600)
    after = tr(p, "2")
    s.check("drag-handle: dragging the label text does not move the node", mid == before, {"before": before, "after_label_drag": mid})
    s.check("drag-handle: dragging the custom handle moves the node (uncontrolled default_nodes)", after != before, {"before": before, "after": after})


def intersections(s, ctx, p):
    go(p, "/nodes/intersections")
    x, y = center(p.locator('.react-flow__node[data-id="4"]'))
    tx, ty = center(p.locator('.react-flow__node[data-id="3"]'))
    p.mouse.move(x, y)
    p.mouse.down()
    p.mouse.move(x + 3, y + 3, steps=2)
    p.mouse.move(tx, ty, steps=25)
    p.wait_for_timeout(700)
    hl = p.locator(".react-flow__node.highlight").evaluate_all("els => els.map(e => e.dataset.id)")
    p.mouse.up()
    p.wait_for_timeout(700)
    s.check("intersections: dragging node over Node 3 highlights it (on_node_drag throttle + get_intersecting_nodes)", "3" in hl, hl)
    s.shot(p, "intersections")


with Session(f"flow-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    ctx = s.new_context("flow")
    p = s.new_page(ctx, "flow")
    p.goto(base + "/", wait_until="networkidle")
    links = p.locator("a").all_inner_texts()
    s.check("index lists 6 flow demos", len(links) == 6, links)

    def new_ctx_page():
        c = s.new_context("flow-ctx2")
        return s.new_page(c, "flow-ctx2")

    scenario(s, "overview", overview, s, ctx, p)
    scenario(s, "add-node-on-edge-drop", add_on_drop, s, ctx, p, new_ctx_page)
    scenario(s, "connection-limit", connection_limit, s, ctx, p)
    scenario(s, "custom-node", custom_node, s, ctx, p)
    scenario(s, "drag-handle", drag_handle, s, ctx, p)
    scenario(s, "intersections", intersections, s, ctx, p)

"""Driver for the entlab app (map + dnd + flow combined with core reflex).

Usage: drive_entlab.py <base_url> <out_dir> <label>

Key checks:
  * a NON-@rxe.static `can_drop` whose return expression uses an import from a
    `bundle_library()`-bundled package works AT RUNTIME (previous campaign
    FINDING-022, which crashed at construction time on reflex 0.9.9a1);
  * the @rxe.static `can_drop` control behaves the opposite way;
  * rx.foreach-built leaflet markers, rx.cond vector overlay, rx.ComponentState
    and rx._x.client_state next to enterprise components;
  * xyflow nodes from a computed var: add / connect / delete round-trips.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import Harness  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)


def bgcolor(loc):
    return loc.evaluate("el => getComputedStyle(el).backgroundColor")


def drag(page, src, dst, hold_probe=None, steps=18):
    """Real mouse drag; returns whatever hold_probe() saw while over the target."""
    sb, db = src.bounding_box(), dst.bounding_box()
    sx, sy = sb["x"] + sb["width"] / 2, sb["y"] + sb["height"] / 2
    dx, dy = db["x"] + db["width"] / 2, db["y"] + db["height"] / 2
    page.mouse.move(sx, sy)
    page.mouse.down()
    page.mouse.move(sx + 8, sy + 8, steps=3)
    page.mouse.move(dx, dy, steps=steps)
    page.mouse.move(dx + 2, dy + 2, steps=2)
    observed = None
    deadline = time.time() + 2.5
    while time.time() < deadline:
        page.mouse.move(dx - 2, dy - 2, steps=2)
        if hold_probe is not None:
            observed = hold_probe()
            if observed not in (None, "rgb(255, 255, 255)", "false"):
                break
        time.sleep(0.2)
    page.mouse.up()
    time.sleep(1.2)
    return observed


def main():
    base, out_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
    with Harness(base, out_dir, label) as h:
        page = h.page

        # ================= /dnd =================
        h.goto("/dnd")
        page.wait_for_selector("#tray", timeout=25000)
        time.sleep(1.5)
        tray_items = page.locator('#tray [draggable="true"]')
        check("dnd_tray_renders", tray_items.count() == 2, f"n={tray_items.count()}")
        h.shot("dnd_initial")

        bin0 = page.locator("#bin-0")
        bin1 = page.locator("#bin-1")

        def chip(name):
            return page.locator(f'#tray [draggable="true"]').filter(has_text=name).first

        # 1. pricey (130000) onto bin-0 -> bundled-library can_drop says YES
        seen = drag(page, chip("pricey"), bin0, hold_probe=lambda: bgcolor(bin0))
        check(
            "dnd_bundled_can_drop_accepts",
            seen == "rgb(144, 238, 144)",
            f"bg while over = {seen} (want lightgreen)",
        )
        h.shot("dnd_after_pricey_to_bin0")
        log = page.locator("#log").inner_text()
        check("dnd_bundled_drop_applied", "pricey->0" in log, repr(log))
        bg = page.locator("#bgticks").inner_text()
        check("dnd_background_event_ran", "1" in bg, repr(bg))

        # 2. cheap (42) onto bin-0 -> bundled can_drop says NO
        seen = drag(page, chip("cheap"), bin0, hold_probe=lambda: bgcolor(bin0))
        check(
            "dnd_bundled_can_drop_rejects",
            seen == "rgb(250, 128, 114)",
            f"bg while over = {seen} (want salmon)",
        )
        log2 = page.locator("#log").inner_text()
        check("dnd_rejected_drop_not_applied", "cheap->0" not in log2, repr(log2))
        h.shot("dnd_after_cheap_to_bin0_rejected")

        # 3. cheap onto bin-1 -> @rxe.static can_drop says YES
        seen = drag(page, chip("cheap"), bin1, hold_probe=lambda: bgcolor(bin1))
        check(
            "dnd_static_can_drop_accepts",
            seen == "rgb(144, 238, 144)",
            f"bg while over = {seen}",
        )
        log3 = page.locator("#log").inner_text()
        check("dnd_static_drop_applied", "cheap->1" in log3, repr(log3))
        h.shot("dnd_after_cheap_to_bin1")

        hovers = page.locator("#hovers").inner_text()
        check(
            "dnd_client_state_hovers",
            any(c.isdigit() and c != "0" for c in hovers),
            repr(hovers),
        )

        # ================= /map =================
        h.goto("/map")
        page.wait_for_selector(".leaflet-container", timeout=25000)
        time.sleep(2.0)
        m0 = page.locator(".leaflet-marker-icon").count()
        check("map_foreach_markers", m0 == 3, f"markers={m0}")
        paths0 = page.locator(".leaflet-overlay-pane path").count()
        check("map_cond_circle_present", paths0 >= 1, f"paths={paths0}")
        h.shot("map_initial")

        page.locator("#addpoint").click()
        time.sleep(2.0)
        m1 = page.locator(".leaflet-marker-icon").count()
        check("map_foreach_grows", m1 == m0 + 1, f"{m0} -> {m1}")

        page.locator("#togglecircle").click()
        time.sleep(1.5)
        paths1 = page.locator(".leaflet-overlay-pane path").count()
        check("map_cond_circle_toggles", paths1 < paths0, f"{paths0} -> {paths1}")
        h.shot("map_after_toggle")

        page.locator(".leaflet-marker-icon").nth(0).click()
        time.sleep(1.0)
        pick = page.locator(".leaflet-popup button").first
        pick_ok = pick.count() == 1
        if pick_ok:
            pick.click()
            time.sleep(1.5)
        clicked = page.locator("#clicked").inner_text()
        check("map_popup_state_event", "alpha" in clicked, f"popup={pick_ok} clicked={clicked!r}")
        h.shot("map_after_popup_pick")

        cs = page.locator("#clicks")
        cs.click()
        time.sleep(1.2)
        cs.click()
        time.sleep(1.5)
        check("map_component_state", "2" in cs.inner_text(), repr(cs.inner_text()))

        page.locator("#recenter").click()
        time.sleep(1.5)
        check("map_api_fly_to_no_error", not h.page_errors, f"page_errors={h.page_errors}")

        # ================= /flow =================
        h.goto("/flow")
        page.wait_for_selector(".react-flow__node", timeout=25000)
        time.sleep(2.5)
        n0 = page.locator(".react-flow__node").count()
        check("flow_computed_nodes", n0 == 2, f"nodes={n0}")
        h.shot("flow_initial")

        page.locator("#addnode").click()
        time.sleep(2.5)
        n1 = page.locator(".react-flow__node").count()
        counts = page.locator("#counts").inner_text()
        check("flow_add_node", n1 == 3 and "3/0" in counts, f"nodes={n1} counts={counts!r}")

        # connect two handles
        handles = page.locator(".react-flow__handle")
        src = handles.nth(0).bounding_box()
        tgt = None
        for i in range(1, handles.count()):
            b = handles.nth(i).bounding_box()
            if b and (abs(b["y"] - src["y"]) > 25 or abs(b["x"] - src["x"]) > 80):
                tgt = b
                break
        if tgt:
            page.mouse.move(src["x"] + src["width"] / 2, src["y"] + src["height"] / 2)
            page.mouse.down()
            for i in range(1, 17):
                page.mouse.move(
                    src["x"] + (tgt["x"] - src["x"]) * i / 16 + 3,
                    src["y"] + (tgt["y"] - src["y"]) * i / 16 + 3,
                )
                page.wait_for_timeout(25)
            page.mouse.up()
            time.sleep(2.5)
        e1 = page.locator(".react-flow__edge").count()
        counts = page.locator("#counts").inner_text()
        check("flow_on_connect_edge", e1 >= 1 and "/1" in counts, f"edges={e1} counts={counts!r}")
        h.shot("flow_after_connect")

        nb = page.locator(".react-flow__node").count()
        page.locator(".react-flow__node").nth(nb - 1).click()
        time.sleep(0.7)
        page.keyboard.press("Backspace")
        time.sleep(2.5)
        na = page.locator(".react-flow__node").count()
        counts = page.locator("#counts").inner_text()
        check("flow_delete_node", na == nb - 1, f"nodes {nb} -> {na} counts={counts!r}")
        h.shot("flow_after_delete")

        data = h.dump()

    unexpected = [
        c for c in data["unexpected_console"] if "ERR_TUNNEL_CONNECTION_FAILED" not in c["text"]
    ]
    print(f"UNEXPECTED_CONSOLE {len(unexpected)}")
    for c in unexpected[:20]:
        print("  CONSOLE", c["type"], c["text"][:300])
    tiles = [n for n in data["net_fail"] if "tile.openstreetmap.org" in str(n.get("url", ""))]
    other = [n for n in data["net_fail"] if n not in tiles]
    print(f"NET_FAIL {len(data['net_fail'])} (osm={len(tiles)} other={len(other)})")
    for n in other[:20]:
        print("  NET", n)
    print(f"PAGE_ERRORS {len(data['page_errors'])}")
    for e in data["page_errors"][:10]:
        print("  PAGEERR", e[:300])

    npass = sum(1 for _, ok, _ in results if ok)
    print(f"SUMMARY {npass}/{len(results)} passed")
    sys.exit(0 if npass == len(results) else 1)


if __name__ == "__main__":
    main()

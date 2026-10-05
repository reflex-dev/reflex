"""Extra map-demo checks not covered by drive_map.py.

Covers: draggable marker drag round-trip, popup open/close, "Locate and setView",
"Fly to Found Location", client-side (SPA) navigation between all 4 routes plus
browser back/forward, and a hard reload of a deep route.

Usage: drive_map_extra.py <base_url> <out_dir> <label>
"""

import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])

from common import Harness  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} {detail}")


def main():
    base, out_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
    with Harness(base, out_dir, label) as h:
        page = h.page

        # ---- /fly-to-location extras -------------------------------------
        h.goto("/fly-to-location")
        page.wait_for_selector(".leaflet-container", timeout=20000)
        page.wait_for_timeout(1500)

        # draggable marker (the 2nd marker, position 51.515,-0.1) must be
        # movable with the mouse and must stay where it was dropped.
        markers = page.locator(".leaflet-marker-icon")
        check("extra_two_markers", markers.count() == 2, f"n={markers.count()}")
        drag_m = markers.nth(1)
        b0 = drag_m.bounding_box()
        page.mouse.move(b0["x"] + b0["width"] / 2, b0["y"] + b0["height"] - 2)
        page.mouse.down()
        for i in range(1, 11):
            page.mouse.move(
                b0["x"] + b0["width"] / 2 + 12 * i,
                b0["y"] + b0["height"] - 2 + 6 * i,
                steps=2,
            )
        page.mouse.up()
        page.wait_for_timeout(800)
        b1 = page.locator(".leaflet-marker-icon").nth(1).bounding_box()
        moved = abs(b1["x"] - b0["x"]) > 50 and abs(b1["y"] - b0["y"]) > 25
        check("extra_marker_draggable", moved, f"{b0['x']:.0f},{b0['y']:.0f} -> {b1['x']:.0f},{b1['y']:.0f}")
        h.shot("marker_dragged")

        # popup open then close via its close button
        page.locator(".leaflet-marker-icon").nth(0).click()
        page.wait_for_timeout(600)
        popup = page.locator(".leaflet-popup")
        opened = popup.count() == 1
        if opened:
            page.locator(".leaflet-popup-close-button").click()
            page.wait_for_timeout(600)
        check(
            "extra_popup_open_close",
            opened and page.locator(".leaflet-popup").count() == 0,
            f"opened={opened} after_close={page.locator('.leaflet-popup').count()}",
        )

        # "Locate and setView" -> geolocation mocked to 51.6,-0.2 in Harness
        page.get_by_role("button", name="Locate and setView").click()
        page.wait_for_timeout(2500)
        located = page.get_by_text("Located:").inner_text()
        check("extra_locate_setview", "51.6" in located, repr(located))

        # "Fly to Found Location" should not error now that a location exists
        errs_before = len(h.page_errors)
        page.get_by_role("button", name="Fly to Found Location").click()
        page.wait_for_timeout(1500)
        check(
            "extra_fly_to_found",
            len(h.page_errors) == errs_before,
            f"page_errors={h.page_errors[errs_before:]}",
        )
        h.shot("after_fly_to_found")

        # ---- SPA navigation ---------------------------------------------
        h.goto("/")
        page.wait_for_timeout(800)
        routes = ["/map-controls", "/fly-to-location", "/vector-layers"]
        nav_ok = True
        nav_detail = []
        for r in routes:
            link = page.locator(f'a[href="{r}"]').first
            if link.count() == 0:
                nav_ok = False
                nav_detail.append(f"no link {r}")
                continue
            link.click()
            page.wait_for_timeout(2000)
            if not page.url.endswith(r):
                nav_ok = False
                nav_detail.append(f"url={page.url} want {r}")
            # the leaflet map must have (re)mounted on every SPA navigation
            try:
                page.wait_for_selector(".leaflet-container", timeout=10000)
            except Exception as e:  # noqa: BLE001
                nav_ok = False
                nav_detail.append(f"{r}: no map ({e!r})")
            page.go_back()
            page.wait_for_timeout(1500)
            if not (page.url.rstrip("/").endswith(base.rstrip("/").rsplit("/", 1)[-1]) or page.url.rstrip("/") == base.rstrip("/")):
                nav_ok = False
                nav_detail.append(f"back url={page.url}")
        check("extra_spa_nav_roundtrip", nav_ok, "; ".join(nav_detail))
        h.shot("after_spa_nav")

        # ---- hard reload of a deep route --------------------------------
        h.goto("/vector-layers")
        page.wait_for_selector(".leaflet-container", timeout=20000)
        page.reload(wait_until="load")
        page.wait_for_selector(".leaflet-container", timeout=20000)
        page.wait_for_timeout(1200)
        paths = page.locator(".leaflet-overlay-pane path").count()
        check("extra_deep_reload", paths >= 5, f"paths={paths}")
        h.shot("deep_reload")

        data = h.dump()

    unexpected = [
        c
        for c in data["unexpected_console"]
        if "ERR_TUNNEL_CONNECTION_FAILED" not in c["text"]
    ]
    print(f"UNEXPECTED_CONSOLE {len(unexpected)}")
    for c in unexpected[:20]:
        print("  CONSOLE", c["type"], c["text"][:300])
    tile_fail = [n for n in data["net_fail"] if "tile.openstreetmap.org" in str(n.get("url", ""))]
    other_fail = [n for n in data["net_fail"] if n not in tile_fail]
    print(f"NET_FAIL {len(data['net_fail'])} (osm_tiles={len(tile_fail)} other={len(other_fail)})")
    for n in other_fail[:20]:
        print("  NET", n)
    print(f"PAGE_ERRORS {len(data['page_errors'])}")
    for e in data["page_errors"][:10]:
        print("  PAGEERR", e[:300])

    npass = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"SUMMARY {npass}/{len(RESULTS)} passed")
    sys.exit(0 if npass == len(RESULTS) else 1)


if __name__ == "__main__":
    main()

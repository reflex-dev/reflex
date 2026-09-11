"""Playwright driver for the reflex-enterprise map demo.

Usage: python drive_map.py <base_url> <out_dir> <label>

Exercises: index page, /map-controls (controls placement), /fly-to-location
(markers, tooltip, popup, popup-button toast, fly-to buttons, on_click lambda
set_view, scroll-wheel zoom + on_zoom state update, locate w/ mocked
geolocation), /vector-layers (vector shapes render, get_bounds callback ->
console_log). Prints a RESULT line per check.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import Harness

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} {detail}", flush=True)


def main():
    base_url, out_dir, label = sys.argv[1], sys.argv[2], sys.argv[3]
    with Harness(base_url, out_dir, label) as h:
        page = h.page

        # ---- index ----
        h.goto("/")
        page.wait_for_selector("text=Map Demos", timeout=20000)
        try:
            page.wait_for_selector('a[href="/fly-to-location"]', timeout=10000)
            cards_ok = True
        except Exception:
            cards_ok = False
        h.shot("index")
        check("index_renders_cards", cards_ok)

        # ---- map-controls ----
        h.goto("/map-controls")
        try:
            page.wait_for_selector(".leaflet-container", timeout=20000)
            time.sleep(2)
            zoom_tr = page.locator(".leaflet-top.leaflet-right .leaflet-control-zoom")
            scale_bl = page.locator(".leaflet-bottom.leaflet-left .leaflet-control-scale")
            attr_tl = page.locator(
                ".leaflet-top.leaflet-left .leaflet-control-attribution"
            )
            tiles = page.locator(".leaflet-tile").count()
            check(
                "map_controls_renders",
                True,
                f"tiles={tiles} zoomTR={zoom_tr.count()} scaleBL={scale_bl.count()} attrTL={attr_tl.count()}",
            )
            check(
                "map_controls_positions",
                zoom_tr.count() == 1 and scale_bl.count() == 1 and attr_tl.count() == 1,
            )
        except Exception as e:
            check("map_controls_renders", False, repr(e))
        h.shot("map_controls")

        # ---- fly-to-location ----
        h.goto("/fly-to-location")
        try:
            page.wait_for_selector(".leaflet-container", timeout=20000)
            page.wait_for_selector(".leaflet-marker-icon", timeout=15000)
            time.sleep(2)
            markers = page.locator(".leaflet-marker-icon")
            check("fly_markers_render", markers.count() == 2, f"markers={markers.count()}")
            h.shot("fly_initial")

            # tooltip on hover over first marker
            markers.nth(0).hover()
            time.sleep(1)
            tooltip = page.locator(".leaflet-tooltip", has_text="Baz bum")
            check("fly_marker_tooltip", tooltip.count() >= 1)
            h.shot("fly_tooltip")

            # popup on click
            markers.nth(0).click()
            time.sleep(1)
            popup_btn = page.locator(".leaflet-popup button", has_text="Foo bar")
            check("fly_marker_popup", popup_btn.count() == 1)
            h.shot("fly_popup")
            if popup_btn.count():
                popup_btn.click()
                try:
                    page.wait_for_selector(
                        "li[data-sonner-toast] >> text=foo bar from popup", timeout=6000
                    )
                    check("fly_popup_button_toast", True)
                except Exception:
                    # sonner markup fallback
                    ok = page.locator("text=foo bar from popup").count() > 0
                    check("fly_popup_button_toast", ok)
                h.shot("fly_popup_toast")

            # zoom via control-less: use +/- via keyboard on map or wheel
            zoom_text = page.locator("text=Zoom:").first
            before = page.locator("p,span,div", has_text="Zoom:").first.inner_text()
            mapbox = page.locator(".leaflet-container").bounding_box()
            cx, cy = mapbox["x"] + mapbox["width"] / 2, mapbox["y"] + mapbox["height"] / 2
            page.mouse.move(cx, cy)
            page.mouse.wheel(0, -400)  # zoom in
            time.sleep(2.5)
            after = page.locator("p,span,div", has_text="Zoom:").first.inner_text()
            check("fly_wheel_zoom_updates_state", before != after, f"{before!r} -> {after!r}")
            h.shot("fly_after_wheel_zoom")

            # click on map triggers lambda on_click -> my_api.set_view (LambdaVar path)
            page.mouse.click(cx + 150, cy + 80)
            time.sleep(2)
            h.shot("fly_after_map_click_setview")

            # drag/pan the map
            page.mouse.move(cx, cy)
            page.mouse.down()
            page.mouse.move(cx - 200, cy - 120, steps=12)
            page.mouse.up()
            time.sleep(1.5)
            h.shot("fly_after_pan")
            check("fly_pan_no_crash", True)

            # Fly to center button
            page.get_by_role("button", name="Fly to center").click()
            time.sleep(2.5)
            h.shot("fly_to_center")
            check("fly_to_center_no_crash", True)

            # Locate button (mocked geolocation 51.6,-0.2)
            page.get_by_role("button", name="Locate", exact=True).click()
            time.sleep(3)
            located = page.locator("text=Located:").first.inner_text()
            check(
                "fly_locate_locationfound",
                "51.6" in located,
                f"located_text={located!r}",
            )
            h.shot("fly_after_locate")
        except Exception as e:
            check("fly_page", False, repr(e))
            h.shot("fly_error")

        # ---- vector-layers ----
        h.goto("/vector-layers")
        try:
            page.wait_for_selector(".leaflet-container", timeout=20000)
            page.wait_for_selector("path.leaflet-interactive", timeout=15000)
            time.sleep(2)
            paths = page.locator("path.leaflet-interactive").count()
            markers = page.locator(".leaflet-marker-icon").count()
            # circle, circle_marker, polygon, polyline, rectangle = 5 paths + 1 marker
            check("vector_shapes_render", paths >= 5 and markers == 1, f"paths={paths} markers={markers}")
            h.shot("vector_layers")

            # tooltip on circle marker
            page.locator("path.leaflet-interactive").nth(1).hover(force=True)
            time.sleep(1)

            # get_bounds -> rx.console_log callback
            n_console_before = len(h.console)
            page.get_by_role("button", name="Get Bounds").click()
            time.sleep(2)
            new_msgs = [c["text"] for c in h.console[n_console_before:]]
            bounds_logged = any("lat" in m.lower() or "bounds" in m.lower() or "_southWest" in m for m in new_msgs)
            check("vector_get_bounds_console_log", bounds_logged, f"new_console={new_msgs[:5]}")
            h.shot("vector_after_get_bounds")
        except Exception as e:
            check("vector_layers_page", False, repr(e))
            h.shot("vector_error")

        # summary of captures
        unexpected = h.unexpected_console()
        print(f"UNEXPECTED_CONSOLE {len(unexpected)}", flush=True)
        for c in unexpected[:20]:
            print("  CONSOLE", c["type"], c["text"][:300], flush=True)
        print(f"NET_FAIL {len(h.net_fail)}", flush=True)
        for nf in h.net_fail[:20]:
            print("  NET", nf, flush=True)
        print(f"PAGE_ERRORS {len(h.page_errors)}", flush=True)
        for e in h.page_errors[:10]:
            print("  PAGEERROR", e[:300], flush=True)

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"SUMMARY {len(results) - n_fail}/{len(results)} passed", flush=True)
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()

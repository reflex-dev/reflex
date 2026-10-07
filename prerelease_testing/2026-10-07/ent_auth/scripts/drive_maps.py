"""Drive mapsapp (rxe.map): marker drag -> State, layers control, geolocation denied/granted,
200 circle markers re-rendered from a State list every second by a background task.

Usage: drive_maps.py <base_url> <label>
External tile hosts are blocked by the sandbox proxy (tiles 'fail' with ERR_TUNNEL_CONNECTION_FAILED);
checks use the Leaflet DOM (tile <img> src, overlay-pane paths, marker icons) instead of pixels.
"""

import json
import sys
import time
import traceback

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach  # noqa: E402

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
T = 60_000
res = {"label": LABEL, "checks": {}}


def check(name, ok, **detail):
    res["checks"][name] = {"ok": bool(ok), **detail}
    print(json.dumps({name: res["checks"][name]}, default=str)[:700], flush=True)


def wait_hydrated(page):
    page.wait_for_function("() => !!document.querySelector('.leaflet-container')", timeout=T)
    page.wait_for_timeout(1500)


def drag(page, selector, dx, dy):
    box = page.locator(selector).bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] - 4
    page.mouse.move(x, y)
    page.mouse.down()
    for i in range(1, 11):
        page.mouse.move(x + dx * i / 10, y + dy * i / 10)
        page.wait_for_timeout(30)
    page.mouse.up()


def case_markers(browser):
    ctx = browser.new_context(viewport={"width": 1300, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(T)
    diag = res.setdefault("markers_diag", {})
    attach(page, diag)
    long_tasks = []
    page.add_init_script("""
      window.__lt = [];
      try { new PerformanceObserver(l => l.getEntries().forEach(e => window.__lt.push(Math.round(e.duration)))).observe({type: 'longtask', buffered: true}); } catch (e) {}
    """)
    page.goto(BASE + "/")
    wait_hydrated(page)
    n_paths = page.locator("#markers-map .leaflet-overlay-pane path").count()
    check("markers_200_rendered", n_paths == 200, n_paths=n_paths, n_text=page.locator("#n-markers").inner_text())
    # drag the State-positioned marker
    sel = '#markers-map img.leaflet-marker-icon[title="drag-me"]'
    expect(page.locator(sel)).to_be_visible()
    before = page.locator(sel).bounding_box()
    drag(page, sel, 120, 60)
    expect(page.locator("#drag-count")).to_contain_text("1", timeout=10_000)
    last = page.locator("#last-drag").inner_text()
    page.wait_for_timeout(800)
    after = page.locator(sel).bounding_box()
    check("drag_end_to_state", "drags=1" in page.locator("#drag-count").inner_text().replace(" ", "") and last not in ("", "51.505,-0.09"),
          last_drag=last, moved_px=[round(after["x"] - before["x"]), round(after["y"] - before["y"])])
    # second drag: State position must follow, marker must not snap back
    drag(page, sel, -60, -40)
    expect(page.locator("#drag-count")).to_contain_text("2", timeout=10_000)
    last2 = page.locator("#last-drag").inner_text()
    page.wait_for_timeout(800)
    after2 = page.locator(sel).bounding_box()
    check("second_drag_no_snap_back", last2 != last, last_drag=last2, pos=[round(after2["x"]), round(after2["y"])], expected_near=[round(after["x"] - 60), round(after["y"] - 40)])
    # no-arg dragend handler
    drag(page, '#markers-map img.leaflet-marker-icon[title="drag-noarg"]', 50, 50)
    expect(page.locator("#drag-noarg-count")).to_contain_text("1", timeout=10_000)
    check("drag_end_noarg", True, text=page.locator("#drag-noarg-count").inner_text())
    # marker click handler
    page.locator(sel).click()
    page.wait_for_timeout(800)
    check("marker_click", "clicks=1" in page.locator("#clicks").inner_text().replace(" ", ""), text=page.locator("#clicks").inner_text())
    # ticker: 200 markers re-rendered every second from a background task
    first_d = page.locator("#markers-map .leaflet-overlay-pane path").first.get_attribute("d")
    lt_before = page.evaluate("() => window.__lt.length")
    page.locator("#start").click()
    samples = []
    t0 = time.time()
    while time.time() - t0 < 11:
        page.wait_for_timeout(1000)
        samples.append([round(time.time() - t0, 1), page.locator("#tick").inner_text(), page.locator("#running").inner_text(),
                        page.locator("#markers-map .leaflet-overlay-pane path").count(),
                        page.locator("#markers-map .leaflet-overlay-pane path").first.get_attribute("d")[:18]])
    res["ticker_samples"] = samples
    ds = {s[4] for s in samples}
    counts = {s[3] for s in samples}
    final_tick = page.locator("#tick").inner_text()
    check("ticker_bg_updates_live", "tick=8" in final_tick.replace(" ", "") and len(ds) >= 6 and counts == {200},
          final_tick=final_tick, distinct_first_path_d=len(ds), path_counts=sorted(counts), first_d0=first_d[:18])
    lts = page.evaluate("() => window.__lt")[lt_before:]
    res["long_tasks_during_ticker"] = lts
    check("ticker_long_tasks", max(lts or [0]) < 500, n=len(lts), max_ms=max(lts or [0]))
    # drag marker while the ticker runs again
    page.locator("#start").click()
    page.wait_for_timeout(1500)
    drag(page, sel, 40, 40)
    expect(page.locator("#drag-count")).to_contain_text("3", timeout=10_000)
    page.wait_for_timeout(9000)
    check("drag_during_ticker", "drags=3" in page.locator("#drag-count").inner_text().replace(" ", ""), tick=page.locator("#tick").inner_text())
    # reload: State (drag position, tick) restored
    page.reload()
    wait_hydrated(page)
    check("reload_restores_state", page.locator("#tick").inner_text().replace(" ", "") == "tick=16" and page.locator("#markers-map .leaflet-overlay-pane path").count() == 200,
          tick=page.locator("#tick").inner_text(), last_drag=page.locator("#last-drag").inner_text())
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-maps-markers.png"))
    ctx.close()


def case_layers(browser):
    ctx = browser.new_context(viewport={"width": 1300, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(T)
    diag = res.setdefault("layers_diag", {})
    attach(page, diag)
    tile_reqs = []
    page.on("request", lambda r: tile_reqs.append(r.url) if "tile." in r.url else None)
    page.goto(BASE + "/layers")
    wait_hydrated(page)
    ctl = page.locator("#layers-map .leaflet-control-layers")
    expect(ctl).to_be_visible()
    labels = ctl.locator("label").all_inner_texts()
    check("layers_control_rendered", any("OSM" in x for x in labels) and any("Topo" in x for x in labels), labels=[x.strip() for x in labels])
    osm_tiles = page.locator("#layers-map .leaflet-tile-pane img").evaluate_all("els => els.map(e => e.src).filter(s => s.includes('openstreetmap')).length")
    adds0 = page.locator("#layer-adds").inner_text()
    n_req0 = len(tile_reqs)
    ctl.locator("label", has_text="Topo").locator("input").check()
    page.wait_for_timeout(2000)
    topo_tiles = page.locator("#layers-map .leaflet-tile-pane img").evaluate_all("els => els.map(e => e.src).filter(s => s.includes('opentopomap')).length")
    osm_after = page.locator("#layers-map .leaflet-tile-pane img").evaluate_all("els => els.map(e => e.src).filter(s => s.includes('openstreetmap')).length")
    check("base_layer_switch", topo_tiles > 0 and osm_after == 0, osm_tiles_before=osm_tiles, topo_tiles=topo_tiles, osm_after=osm_after,
          topo_requests=sum(1 for u in tile_reqs[n_req0:] if "opentopomap" in u))
    adds1 = page.locator("#layer-adds").inner_text()
    check("on_layeradd_event", adds1 != adds0, before=adds0, after=adds1)
    n_circle = page.locator("#layers-map .leaflet-overlay-pane path").count()
    ctl.locator("label", has_text="Circle").locator("input").uncheck()
    page.wait_for_timeout(800)
    n_circle_off = page.locator("#layers-map .leaflet-overlay-pane path").count()
    ctl.locator("label", has_text="Marker").locator("input").check()
    page.wait_for_timeout(800)
    n_marker = page.locator('#layers-map img.leaflet-marker-icon[title="overlay-marker"]').count()
    check("overlay_toggle", n_circle == 1 and n_circle_off == 0 and n_marker == 1, circle_on=n_circle, circle_off=n_circle_off, marker_on=n_marker)
    ctl.locator("label", has_text="OSM").locator("input").check()
    page.wait_for_timeout(1000)
    back = page.locator("#layers-map .leaflet-tile-pane img").evaluate_all("els => els.map(e => e.src).filter(s => s.includes('openstreetmap')).length")
    check("base_layer_switch_back", back > 0, osm_tiles=back)
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-maps-layers.png"))
    ctx.close()


def case_geo(browser, granted):
    kw = {"geolocation": {"latitude": 48.8566, "longitude": 2.3522}, "permissions": ["geolocation"]} if granted else {"permissions": []}
    ctx = browser.new_context(viewport={"width": 1100, "height": 800}, **kw)
    page = ctx.new_page()
    page.set_default_timeout(T)
    diag = res.setdefault("geo_diag_" + ("granted" if granted else "denied"), {})
    attach(page, diag)
    page.goto(BASE + "/geo")
    wait_hydrated(page)
    page.locator("#locate").click()
    page.wait_for_timeout(6000)
    err = page.locator("#loc-error").inner_text()
    found = page.locator("#loc-found").inner_text()
    if granted:
        check("geolocation_granted", found == "48.8566,2.3522" and not err, found=found, error=err)
    else:
        check("geolocation_denied", err.startswith("code=1") and not found, error=err, found=found)
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-maps-geo-{'granted' if granted else 'denied'}.png"))
    ctx.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for name, fn in (("markers", lambda: case_markers(browser)), ("layers", lambda: case_layers(browser)),
                         ("geo_denied", lambda: case_geo(browser, False)), ("geo_granted", lambda: case_geo(browser, True))):
            try:
                fn()
            except Exception:
                check(name + "_completed", False, traceback=traceback.format_exc()[-1500:])
        browser.close()
    errs = {}
    for k, v in res.items():
        if k.endswith("_diag"):
            errs[k] = {"page_errors": v.get("page_errors"), "console": [c for c in v.get("console", []) if c["type"] in ("error", "warning") and "TUNNEL" not in c["text"]][:10],
                       "http_errors": [h for h in v.get("http_errors", []) if "tile" not in h["url"]][:10],
                       "failed_nontile": [f for f in v.get("failed_requests", []) if "tile" not in f["url"]][:10]}
    res["errors"] = errs
    (W / "logs" / f"maps-{LABEL}.json").write_text(json.dumps(res, indent=2, default=str))
    print("ERRORS", json.dumps(errs, default=str)[:3000])
    print("MAPS", sum(c["ok"] for c in res["checks"].values()), "/", len(res["checks"]))


main()

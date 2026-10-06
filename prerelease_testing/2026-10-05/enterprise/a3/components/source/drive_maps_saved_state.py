"""Exercise maps and advanced saved grid state against the alpha frontend."""

import json
import os
import traceback
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:3131"
BASE = os.environ.get("QA_FRONTEND", BASE)
OUTPUT = Path(os.environ["QA_OUTPUT"])


def is_bounds_message(message) -> bool:
    """Identify a bounds callback by its returned coordinates.

    Args:
        message: Playwright browser console message.

    Returns:
        Whether the first argument contains both Leaflet bounds corners.
    """
    value = message.args[0].json_value() if message.args else None
    return isinstance(value, dict) and {"_southWest", "_northEast"}.issubset(value)


def main() -> None:
    """Drive real Leaflet callbacks, controls, geolocation and persisted grids."""
    results = []
    (OUTPUT / "logs").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "screenshots").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            geolocation={"latitude": 51.515, "longitude": -0.1},
            permissions=["geolocation"],
            viewport={"width": 1400, "height": 1000},
        )
        page = context.new_page()
        console, errors, failed, http_errors = [], [], [], []
        active_case = "initial"
        page.on(
            "console",
            lambda msg: console.append(
                {
                    "case": active_case,
                    "type": msg.type,
                    "text": msg.text,
                    "location": msg.location,
                }
            ),
        )
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "requestfailed",
            lambda req: failed.append(
                {"case": active_case, "url": req.url, "failure": req.failure}
            ),
        )
        page.on(
            "response",
            lambda response: (
                http_errors.append(
                    {
                        "case": active_case,
                        "url": response.url,
                        "status": response.status,
                    }
                )
                if response.status >= 400
                else None
            ),
        )
        for case in [
            "map_controls",
            "map_vectors",
            "map_fly_popup_geolocation",
            "advanced_saved_state",
            "google_font_head",
        ]:
            active_case = case
            try:
                if case == "map_controls":
                    page.goto(BASE + "/map-controls")
                    expect(page.locator(".leaflet-container")).to_be_visible()
                    expect(
                        page.locator(".leaflet-top.leaflet-right .leaflet-control-zoom")
                    ).to_be_visible()
                    expect(page.locator(".leaflet-control-scale")).to_be_visible()
                    expect(
                        page.locator(
                            ".leaflet-top.leaflet-left .leaflet-control-attribution"
                        )
                    ).to_be_visible()
                    initial_scale = page.locator(".leaflet-control-scale").inner_text()
                    page.get_by_role("button", name="Zoom in", exact=True).click()
                    expect(page.locator(".leaflet-control-scale")).not_to_have_text(
                        initial_scale
                    )
                    page.screenshot(path=str(OUTPUT / "screenshots/map-controls.png"))
                elif case == "map_vectors":
                    page.goto(BASE + "/vector-layers")
                    expect(page.locator(".leaflet-overlay-pane path")).to_have_count(5)
                    with page.expect_console_message(is_bounds_message) as bounds:
                        page.get_by_role(
                            "button", name="Get Bounds", exact=True
                        ).click()
                    value = bounds.value.args[0].json_value()
                    assert value["_southWest"]["lat"] < value["_northEast"]["lat"], (
                        value
                    )
                    assert value["_southWest"]["lng"] < value["_northEast"]["lng"], (
                        value
                    )
                    results.append(
                        {
                            "case": "map_bounds_callback",
                            "passed": True,
                            "bounds": value,
                        }
                    )
                    page.screenshot(path=str(OUTPUT / "screenshots/map-vectors.png"))
                elif case == "map_fly_popup_geolocation":
                    page.goto(BASE + "/fly-to-location")
                    expect(page.get_by_text("Zoom: 13", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Zoom in", exact=True).click()
                    expect(page.get_by_text("Zoom: 14", exact=True)).to_be_visible()
                    page.locator(".leaflet-marker-icon").first.click()
                    page.get_by_role("button", name="Foo bar", exact=True).click()
                    expect(
                        page.get_by_text("foo bar from popup", exact=True)
                    ).to_be_visible()
                    page.get_by_role("button", name="Locate", exact=True).click()
                    expect(
                        page.get_by_text(
                            'Located: {"lat":51.515,"lng":-0.1}', exact=True
                        )
                    ).to_be_visible()
                    page.get_by_role(
                        "button", name="Fly to Found Location", exact=True
                    ).click()
                    page.get_by_role("button", name="Fly to center", exact=True).click()
                    page.screenshot(path=str(OUTPUT / "screenshots/map-fly.png"))
                elif case == "advanced_saved_state":
                    page.goto(BASE + "/advanced-serialization")
                    first = page.locator('.ag-row[row-index="0"] [col-id="athlete"]')
                    expect(first).to_have_text("Alpha")
                    page.locator(
                        '.ag-header-cell[col-id="age"] .ag-header-cell-text'
                    ).click()
                    expect(first).to_have_text("Beta")
                    page.wait_for_function(
                        "() => Object.entries(localStorage).some(([k,v]) => k.includes('.grid_state') && v.includes('sortModel'))"
                    )
                    saved = page.evaluate(
                        "() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.includes('.grid_state')))"
                    )
                    page.reload()
                    expect(first).to_have_text("Beta")
                    results.append(
                        {
                            "case": "saved_state_contents",
                            "passed": True,
                            "storage": saved,
                        }
                    )
                    page.screenshot(path=str(OUTPUT / "screenshots/saved-state.png"))
                elif case == "google_font_head":
                    links = page.locator(
                        'head link[href*="fonts.googleapis.com/css2"]'
                    ).all()
                    assert links and any(
                        "family=Inter" in link.get_attribute("href")
                        and "display=swap" in link.get_attribute("href")
                        for link in links
                    )
                    assert (
                        page.locator(
                            'head link[rel="preconnect"][href="https://fonts.gstatic.com"]'
                        ).count()
                        == 1
                    )
                assert not errors, errors
                result = {"case": case, "passed": True}
            except Exception:
                result = {
                    "case": case,
                    "passed": False,
                    "traceback": traceback.format_exc(),
                }
                page.screenshot(
                    path=str(OUTPUT / "screenshots" / f"{case}-failure.png")
                )
            results.append(result)
            print(json.dumps(result), flush=True)
        browser.close()
    (OUTPUT / "logs/maps-saved-state-browser.json").write_text(
        json.dumps(
            {
                "results": results,
                "console": console,
                "page_errors": errors,
                "failed_requests": failed,
                "http_errors": http_errors,
            },
            indent=2,
        )
    )
    assert all(r["passed"] for r in results), "A maps or persistence case failed"


if __name__ == "__main__":
    main()

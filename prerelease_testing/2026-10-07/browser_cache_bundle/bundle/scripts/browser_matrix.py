"""Compare browser-reported production transfers, cache behavior and real actions."""

import gzip
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import playwright

assert (
    str(Path(os.environ["REFLEX_TEST_SB"]) / "envs/driver/lib") in playwright.__file__
), playwright.__file__
from playwright.sync_api import sync_playwright, expect

base, label, outstr = sys.argv[1:]
out = Path(outstr)
out.mkdir(parents=True, exist_ok=True)
HEADERS = (
    "cache-control",
    "content-encoding",
    "content-length",
    "content-type",
    "etag",
    "last-modified",
    "vary",
)


class Recorder:
    """Record actual browser APIs without routing/intercepting requests."""

    def __init__(self, page, browser_name):
        """Attach listeners to the page and optional Chromium CDP session.

        Args:
            page: Browser page.
            browser_name: Browser engine name.
        """
        self.page = page
        self.current = None
        self.phases = {}
        self.requests = {}
        self.browser_name = browser_name
        page.on(
            "console",
            lambda m: self.add("console", {"type": m.type, "text": m.text[:6000]}),
        )
        page.on(
            "pageerror",
            lambda e: self.add("pageerrors", {"message": str(e), "stack": e.stack}),
        )
        page.on(
            "requestfailed",
            lambda r: self.add("failed_requests", {"url": r.url, "failure": r.failure}),
        )
        page.on("requestfinished", self.finished)
        page.on("websocket", self.websocket)
        if browser_name == "chromium":
            cdp = page.context.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.on("Network.requestWillBeSent", self.cdp_request)
            cdp.on("Network.responseReceived", self.cdp_response)
            cdp.on("Network.loadingFinished", self.cdp_finished)
        page.add_init_script("performance.setResourceTimingBufferSize(3000)")

    def add(self, key, value):
        """Append one event to the active phase.

        Args:
            key: Event collection.
            value: Serializable event.
        """
        if self.current:
            self.phases[self.current].setdefault(key, []).append(value)

    def finished(self, request):
        """Record finished response headers and Playwright request sizes.

        Args:
            request: Completed request.
        """
        try:
            response = request.response()
            headers = response.all_headers()
            row = {
                "url": request.url,
                "type": request.resource_type,
                "status": response.status,
                "headers": {h: headers[h] for h in HEADERS if h in headers},
            }
            try:
                row["playwright_sizes"] = request.sizes()
            except Exception as error:
                row["size_error"] = str(error)
            self.add("responses", row)
        except Exception as error:
            self.add("instrumentation_errors", str(error))

    def websocket(self, socket):
        """Capture complete frames and their UTF-8 byte counts.

        Args:
            socket: Open websocket.
        """

        def frame(direction, value):
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            self.add(
                "websocket",
                {
                    "direction": direction,
                    "bytes": len(value.encode()),
                    "payload": value,
                },
            )

        socket.on("framesent", lambda value: frame("sent", value))
        socket.on("framereceived", lambda value: frame("received", value))

    def cdp_request(self, event):
        """Associate request IDs with phases.

        Args:
            event: CDP network request.
        """
        self.requests[event["requestId"]] = {
            "phase": self.current,
            "url": event["request"]["url"],
            "type": event.get("type"),
        }

    def cdp_response(self, event):
        """Record CDP cache flags and response sizes.

        Args:
            event: CDP response.
        """
        row = self.requests.get(event["requestId"])
        if row:
            response = event["response"]
            row.update(
                {
                    k: response[k]
                    for k in (
                        "status",
                        "fromDiskCache",
                        "fromServiceWorker",
                        "encodedDataLength",
                        "protocol",
                    )
                    if k in response
                }
            )

    def cdp_finished(self, event):
        """Record actual CDP encoded transfer length.

        Args:
            event: CDP completion.
        """
        row = self.requests.get(event["requestId"])
        if row and row["phase"] in self.phases:
            self.phases[row["phase"]].setdefault("cdp_requests", []).append(
                {**row, "finished_encoded_bytes": event["encodedDataLength"]}
            )

    def start(self, name):
        """Start an isolated measurement phase.

        Args:
            name: Phase label.
        """
        self.current = name
        self.phases[name] = {"checks": []}
        self.page.evaluate("performance.clearResourceTimings()")

    def check(self, name, ok, detail=None):
        """Record a functional assertion.

        Args:
            name: Assertion label.
            ok: Outcome.
            detail: Supporting evidence.
        """
        self.add("checks", {"name": name, "ok": bool(ok), "detail": detail})
        print(self.browser_name, self.current, name, ok, str(detail)[:150], flush=True)

    def end(self, navigation=False):
        """Collect Resource Timing entries and websocket byte totals.

        Args:
            navigation: Include this phase's document navigation entry.
        """
        self.page.wait_for_timeout(350)
        entries = self.page.evaluate(
            """includeNavigation => [...performance.getEntriesByType('resource'), ...(includeNavigation ? performance.getEntriesByType('navigation'):[])].map(e=>({name:e.name,initiatorType:e.initiatorType,transferSize:e.transferSize,encodedBodySize:e.encodedBodySize,decodedBodySize:e.decodedBodySize,deliveryType:e.deliveryType,responseStatus:e.responseStatus}))""",
            navigation,
        )
        self.phases[self.current]["resource_timing"] = entries
        self.phases[self.current]["reported_transfer_bytes"] = sum(
            e.get("transferSize", 0) for e in entries
        )
        self.phases[self.current]["reported_encoded_body_bytes"] = sum(
            e.get("encodedBodySize", 0) for e in entries
        )
        self.phases[self.current]["websocket_bytes"] = {
            direction: sum(
                f["bytes"]
                for f in self.phases[self.current].get("websocket", [])
                if f["direction"] == direction
            )
            for direction in ("sent", "received")
        }


def settle(page):
    """Wait for complete initial resource downloads.

    Args:
        page: Browser page.
    """
    page.wait_for_load_state("networkidle", timeout=120000)
    page.wait_for_timeout(600)


failed_checks = []
with sync_playwright() as p:
    for browser_name in ("chromium", "webkit"):
        browser = getattr(p, browser_name).launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        rec = Recorder(page, browser_name)
        result = {
            "label": label,
            "base": base,
            "browser": browser_name,
            "browser_version": browser.version,
            "playwright_version": importlib.metadata.version("playwright"),
            "phases": rec.phases,
        }
        try:
            rec.start("cold_home")
            page.goto(base, wait_until="domcontentloaded", timeout=120000)
            settle(page)
            rec.check(
                "home_renders",
                page.locator("#page-title").inner_text() == "Workspace home",
            )
            rec.end(navigation=True)
            rec.start("warm_reload")
            page.reload(wait_until="domcontentloaded", timeout=120000)
            settle(page)
            rec.check(
                "home_renders_after_reload",
                page.locator("#page-title").inner_text() == "Workspace home",
            )
            rec.end(navigation=True)
            rec.start("dashboard_nav")
            page.click("#nav-dashboard")
            expect(page.locator("#page-title")).to_have_text("Operations dashboard")
            settle(page)
            rec.check(
                "dashboard_initial_state",
                "0" in page.locator("#task-count").inner_text(),
            )
            rec.end()
            rec.start("dashboard_event")
            page.click("#complete-task")
            expect(page.locator("#task-count")).to_have_text("Completed tasks: 1")
            rec.check("task_event", True)
            rec.end()
            rec.start("reports_nav")
            page.click("#nav-reports")
            expect(page.locator("#page-title")).to_have_text("Revenue reports")
            page.locator(".js-plotly-plot").wait_for(timeout=120000)
            settle(page)
            rec.check(
                "plotly_six_points",
                page.locator(".js-plotly-plot").evaluate("(e)=>e.data?.[0]?.y.length")
                == 6,
            )
            rec.end()
            rec.start("reports_event")
            page.click("#add-week")
            expect(page.locator("#chart-updates")).to_have_text("1")
            page.wait_for_function(
                "document.querySelector('.js-plotly-plot')?.data?.[0]?.y.length===7"
            )
            rec.check("plotly_update", True)
            rec.end()
            rec.start("editor_nav")
            page.click("#nav-editor")
            expect(page.locator("#page-title")).to_have_text("Catalog editor")
            page.locator("#catalog-grid canvas").first.wait_for(timeout=120000)
            settle(page)
            rec.check(
                "editor_and_code_render",
                page.locator("#catalog-grid canvas").count() > 0
                and "SELECT product" in page.locator("#query-example").inner_text(),
            )
            rec.end()
            rec.start("editor_event")
            box = page.locator("#catalog-grid canvas").first.bounding_box()
            page.mouse.click(box["x"] + 70, box["y"] + 52)
            page.wait_for_timeout(250)
            rec.add(
                "editor_focus",
                page.evaluate(
                    '({tag:document.activeElement?.tagName,role:document.activeElement?.getAttribute("role")})'
                ),
            )
            page.keyboard.press("Enter")
            page.locator("#portal textarea").wait_for()
            page.keyboard.press("ControlOrMeta+a")
            page.keyboard.type("Binder", delay=50)
            page.keyboard.press("Enter")
            expect(page.locator("#edit-count")).to_have_text("1")
            rec.check(
                "catalog_edit", "Binder" in page.locator("#last-edit").inner_text()
            )
            rec.end()
            page.screenshot(path=str(out / f"{browser_name}-editor.png"))
            rec.start("home_return")
            page.click("#nav-home")
            expect(page.locator("#page-title")).to_have_text("Workspace home")
            settle(page)
            rec.check("home_return", True)
            rec.end()
            rec.start("warm_reports")
            page.click("#nav-reports")
            page.locator(".js-plotly-plot").wait_for(timeout=120000)
            settle(page)
            rec.check(
                "chart_state_survives_navigation",
                page.locator(".js-plotly-plot").evaluate("(e)=>e.data?.[0]?.y.length")
                == 7,
            )
            rec.end()
        except Exception as error:
            result["exception"] = repr(error)
            rec.check("driver_exception", False, repr(error))
            page.screenshot(path=str(out / f"{browser_name}-exception.png"))
        finally:
            context.close()
            browser.close()
            full = out / f"{browser_name}-full.json.gz"
            full.write_bytes(
                gzip.compress(json.dumps(result, indent=1).encode(), mtime=0)
            )
            for phase in result["phases"].values():
                phase["websocket_frame_count"] = len(phase.pop("websocket", []))
            result["full_evidence"] = full.name
            (out / f"{browser_name}-summary.json").write_text(
                json.dumps(result, indent=1)
            )

            failed_checks.extend(
                {"browser": browser_name, "phase": phase, "check": check["name"]}
                for phase, group in result["phases"].items()
                for check in group.get("checks", [])
                if not check["ok"]
            )
if failed_checks:
    print("FAILED_CHECKS", json.dumps(failed_checks), flush=True)
sys.exit(1 if failed_checks else 0)

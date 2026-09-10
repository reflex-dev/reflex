"""Shared Playwright plumbing for the up_counter_todo_clock drivers.

Captures console messages, page errors, failed requests, 4xx/5xx responses,
websocket open/close and the frames SENT on the reflex /_event socket (so the
exact event payloads the frontend emits can be compared across versions).
"""

import json
import sys

from playwright.sync_api import sync_playwright

BENIGN = (
    "HydrateFallback",
    "React DevTools",
    "[vite] connecting",
    "[vite] connected",
)


class Capture:
    def __init__(self, url, shot, report):
        self.url = url
        self.shot = shot
        self.report = report
        self.console = []
        self.page_errors = []
        self.failed_requests = []
        self.bad_responses = []
        self.ws_events = []
        self.event_frames = []
        self.steps = []

    def step(self, name, ok, detail=""):
        self.steps.append({"name": name, "ok": bool(ok), "detail": str(detail)})
        print(f"  step {name}: {'OK' if ok else 'FAIL'} {detail}")

    def attach(self, page):
        page.on("console", lambda m: self.console.append((m.type, m.text)))
        page.on("pageerror", lambda e: self.page_errors.append(str(e)))
        page.on(
            "requestfailed",
            lambda r: self.failed_requests.append((r.url, str(r.failure))),
        )
        page.on(
            "response",
            lambda r: self.bad_responses.append((r.status, r.url))
            if r.status >= 400
            else None,
        )

        def on_ws(ws):
            self.ws_events.append(("open", ws.url))
            ws.on("close", lambda w: self.ws_events.append(("close", w.url)))
            if "_event" in ws.url:
                sock_tag = f"ws#{len([e for e in self.ws_events if e[0] == 'open' and '_event' in e[1]])}"
                ws.on(
                    "framesent",
                    lambda payload, tag=sock_tag: self.event_frames.append(
                        tag + " " + (payload[:2000] if isinstance(payload, str) else repr(payload)[:2000])
                    ),
                )

        page.on("websocket", on_ws)

    def finish(self):
        unexpected = [
            (t, m)
            for t, m in self.console
            if t in ("error", "warning") and not any(b in m for b in BENIGN)
        ]
        report = {
            "url": self.url,
            "steps": self.steps,
            "all_steps_ok": all(s["ok"] for s in self.steps),
            "console": self.console,
            "unexpected_console": unexpected,
            "page_errors": self.page_errors,
            "failed_requests": self.failed_requests,
            "http_4xx_5xx": self.bad_responses,
            "websockets": self.ws_events,
            "event_frames_sent": self.event_frames,
        }
        with open(self.report, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print("CONSOLE:")
        for t, m in self.console:
            print(f"  [{t}] {m[:300]}")
        print("UNEXPECTED_CONSOLE:", json.dumps(unexpected, ensure_ascii=False)[:2000])
        print("PAGE_ERRORS:", json.dumps(self.page_errors)[:2000])
        print("FAILED_REQUESTS:", json.dumps(self.failed_requests, default=str)[:2000])
        print("HTTP_4XX_5XX:", json.dumps(self.bad_responses)[:2000])
        print("WEBSOCKETS:", json.dumps(self.ws_events))
        print("ALL_STEPS_OK:", report["all_steps_ok"])
        return report


def run(driver):
    """driver(page, cap) -> None. Usage: <script> <url> <shot_prefix> <report_json>."""
    url, shot, report = sys.argv[1], sys.argv[2], sys.argv[3]
    cap = Capture(url, shot, report)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        ctx = browser.new_context(viewport={"width": 1100, "height": 800})
        page = ctx.new_page()
        cap.attach(page)
        try:
            driver(page, cap)
        except Exception as e:  # keep the report even on a hard failure
            cap.step("DRIVER_CRASH", False, repr(e))
            page.screenshot(path=f"{shot}-crash.png")
        page.wait_for_timeout(800)
        browser.close()
    return cap.finish()

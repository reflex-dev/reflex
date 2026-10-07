"""Reproduce a pure read-only uncached inventory value across full reloads."""

import argparse
import gzip
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from run_matrix import command, stop, wait_server

APP = '''"""Warehouse inventory read from an external store."""
import os
from pathlib import Path
import reflex as rx

assert f"/envs/{os.environ['TEST_REFLEX_ENV']}/" in rx.__file__, rx.__file__
print("PUBLISHED_PACKAGE", rx.__file__, flush=True)

class Stock(rx.State):
    """A warehouse status dashboard that reads an external inventory store."""
    refreshes: int = 0

    @rx.var(cache=False)
    def available(self) -> int:
        """Read available stock, without changing any Reflex state."""
        value = int(Path(os.environ["STOCK_FILE"]).read_text())
        print("READ_STOCK", value, flush=True)
        return value

    @rx.event
    def refresh(self):
        """Trigger a new availability check."""
        self.refreshes += 1

def index():
    """Show the current externally maintained warehouse quantity."""
    return rx.vstack(
        rx.heading("Warehouse availability"),
        rx.text("Available:", Stock.available, id="stock"),
        rx.text(Stock.refreshes, id="refreshes"),
        rx.button("Refresh inventory", id="refresh", on_click=Stock.refresh),
        padding="2em",
    )

app = rx.App()
app.add_page(index)
'''


def main():
    """Run the reproducible external-data reload sequence in both engines."""
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--version", default="alpha2")
    parser.add_argument("--mode", default="dev")
    args = parser.parse_args()
    label = f"{args.version}-{args.mode}"
    app = args.scratch / "apps/uncached-stock" / label
    app.mkdir(parents=True, exist_ok=False)
    output = args.output / label
    output.mkdir(parents=True, exist_ok=False)
    (app / "stock_app").mkdir()
    (app / "stock_app/__init__.py").write_text("")
    (app / "stock_app/stock_app.py").write_text(APP)
    port = 3732
    backend = port if args.mode == "prod" else 8732
    (app / "rxconfig.py").write_text(
        f'import reflex as rx\nconfig = rx.Config(app_name="stock_app", api_url="http://localhost:{backend}", state_manager_mode="memory", telemetry_enabled=False)\n'
    )
    stock = args.scratch / "data/uncached-stock" / f"{label}.txt"
    stock.parent.mkdir(parents=True, exist_ok=True)
    stock.write_text("10")
    environment = os.environ.copy()
    environment.update(
        TEST_REFLEX_ENV=args.version,
        STOCK_FILE=str(stock),
        GRANIAN_WORKERS="1",
        REFLEX_TELEMETRY_ENABLED="false",
        UV_CACHE_DIR=str(args.scratch / "uv-cache"),
    )
    run = command(
        args.scratch,
        args.version,
        "reflex",
        "run",
        "--env",
        args.mode,
        "--frontend-port",
        str(port),
        "--backend-port",
        str(backend),
        "--loglevel",
        "debug",
    )
    report = {
        "version": args.version,
        "mode": args.mode,
        "command": run,
        "browsers": {},
    }
    failed = False
    with (output / "server.log").open("w") as log:
        process = subprocess.Popen(
            run,
            cwd=app,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            wait_server(process, f"http://localhost:{port}/")
            with sync_playwright() as playwright:
                for name in ("chromium", "webkit"):
                    stock.write_text("10")
                    browser = getattr(playwright, name).launch()
                    context = browser.new_context()
                    page = context.new_page()
                    result = {
                        "checks": [],
                        "console": [],
                        "pageerrors": [],
                        "failed_requests": [],
                        "http_errors": [],
                        "frames": [],
                        "browser_version": browser.version,
                    }
                    page.on(
                        "console",
                        lambda msg: result["console"].append(
                            {"type": msg.type, "text": msg.text}
                        ),
                    )
                    page.on(
                        "pageerror", lambda err: result["pageerrors"].append(str(err))
                    )
                    page.on(
                        "requestfailed",
                        lambda req: result["failed_requests"].append(
                            {"url": req.url, "failure": req.failure}
                        ),
                    )
                    page.on(
                        "response",
                        lambda resp: (
                            result["http_errors"].append(
                                {"url": resp.url, "status": resp.status}
                            )
                            if resp.status >= 400
                            else None
                        ),
                    )

                    def opened(socket):
                        """Capture websocket deltas surrounding external inventory edits."""
                        for event, direction in (
                            ("framesent", "sent"),
                            ("framereceived", "received"),
                        ):
                            socket.on(
                                event,
                                lambda data, direction=direction: result[
                                    "frames"
                                ].append(
                                    {
                                        "time": time.time(),
                                        "direction": direction,
                                        "payload": str(data),
                                    }
                                ),
                            )

                    page.on("websocket", opened)

                    def check(label, expected):
                        """Compare the displayed inventory against the external source."""
                        actual = page.locator("#stock").inner_text()
                        result["checks"].append(
                            {
                                "name": label,
                                "actual": actual,
                                "expected": expected,
                                "ok": actual == expected,
                                "time": time.time(),
                            }
                        )

                    try:
                        page.goto(f"http://localhost:{port}/", wait_until="networkidle")
                        page.locator("#refresh").click()
                        page.wait_for_function(
                            "document.querySelector('#refreshes')?.textContent === '1'"
                        )
                        check("first_refresh", "Available:10")
                        stock.write_text("0")
                        page.reload(wait_until="networkidle")
                        page.wait_for_function(
                            "document.querySelector('#stock')?.textContent === 'Available:0'"
                        )
                        check("reload_after_external_sale", "Available:0")
                        stock.write_text("10")
                        page.locator("#refresh").click()
                        page.wait_for_function(
                            "document.querySelector('#refreshes')?.textContent === '2'"
                        )
                        page.wait_for_timeout(250)
                        check("refresh_after_external_restock", "Available:10")
                        page.screenshot(
                            path=str(output / f"{name}-after-restock.png"),
                            full_page=True,
                        )
                        page.reload(wait_until="networkidle")
                        page.wait_for_function(
                            "document.querySelector('#stock')?.textContent === 'Available:10'"
                        )
                        check("full_reload_recovers", "Available:10")
                    except Exception as error:
                        result["exception"] = repr(error)
                    finally:
                        context.close()
                        browser.close()
                        with gzip.open(output / f"{name}-trace.json.gz", "wt") as trace:
                            json.dump(result, trace, indent=2)
                        report["browsers"][name] = {
                            key: value
                            for key, value in result.items()
                            if key not in {"frames", "console"}
                        }
                        failed |= bool(
                            result.get("exception")
                            or result["pageerrors"]
                            or result["http_errors"]
                            or any(not check["ok"] for check in result["checks"])
                        )
        finally:
            report["cleanup_survivors"] = stop(process)
            failed |= bool(report["cleanup_survivors"])
            (output / "result.json").write_text(json.dumps(report, indent=2))
    with gzip.open(output / "server.log.gz", "wb") as log:
        log.write((output / "server.log").read_bytes())
    (output / "server.log").unlink()
    print(json.dumps(report, indent=2))
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())

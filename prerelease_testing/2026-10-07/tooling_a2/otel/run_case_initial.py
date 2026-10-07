"""Drive real plugin exports and outage recovery with owned process groups."""

import argparse
import contextlib
import gzip
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from traces import read_spans

assert "/envs/driver/" in sys.executable, sys.executable


def group(pid):
    """Read a runner-owned process group.

    Args:
        pid: Group leader PID.

    Returns:
        Process rows belonging to this group.
    """
    rows = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    ).splitlines()
    return [
        row.strip()
        for row in rows
        if len(row.split(None, 4)) == 5 and int(row.split(None, 4)[2]) == pid
    ]


def listeners():
    """Read listeners on this task's app and collector ports.

    Returns:
        Matching lsof rows.
    """
    return subprocess.run(
        ["lsof", "-nP", "-iTCP:3586,8586,8588", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
    ).stdout


def browser_case(args, out, engine, stop_collector, start_collector):
    """Exercise the app before, during and after collector refusal.

    Args:
        args: Runner configuration.
        out: Evidence directory.
        engine: Browser engine.
        stop_collector: Stop only the owned collector.
        start_collector: Restore the owned collector.

    Returns:
        Exact assertions, trace evidence and browser diagnostics.
    """
    result = {
        "engine": engine,
        "checks": [],
        "messages": [],
        "frames": [],
        "started": time.time(),
    }
    port = 3586 if args.mode == "dev" else 8586
    marker = f"QA_PAYLOAD_MUST_NOT_EXPORT_{engine}"
    token = ""
    collector = out / "collector.jsonl"

    def record(name, expected, actual):
        """Retain an exact assertion.

        Args:
            name: Assertion label.
            expected: Expected value.
            actual: Observed value.
        """
        result["checks"].append(
            {
                "name": name,
                "passed": expected == actual,
                "expected": expected,
                "actual": actual,
            }
        )
        print(
            f"{engine} {name}: {'PASS' if expected == actual else 'FAIL'}", flush=True
        )

    def check_state(page, name, expected):
        """Poll visible state to a bounded deadline.

        Args:
            page: Browser page.
            name: Assertion label.
            expected: Count, audit count, job increments and status.
        """
        actual = None
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            with contextlib.suppress(Exception):
                actual = page.evaluate(
                    "() => ['count','audited','jobs','status'].map(k => document.getElementById(k).textContent)"
                )
            if actual == expected:
                break
            page.wait_for_timeout(100)
        record(name, expected, actual)

    def spans():
        """Read exports collected during this browser execution.

        Returns:
            Current normalized spans for this execution interval.
        """
        return [
            row
            for row in read_spans(collector)
            if row["collected"] >= result["started"]
        ]

    def attach(page):
        """Capture browser failures and full websocket frames.

        Args:
            page: Browser page.
        """
        page.on(
            "console",
            lambda item: result["messages"].append(
                {
                    "type": item.type,
                    "text": item.text,
                    "time": time.time(),
                }
            ),
        )
        page.on(
            "pageerror",
            lambda error: result["messages"].append(
                {
                    "type": "pageerror",
                    "text": str(error),
                    "time": time.time(),
                }
            ),
        )
        page.on(
            "requestfailed",
            lambda request: result["messages"].append(
                {
                    "type": "requestfailed",
                    "url": request.url,
                    "failure": request.failure,
                    "time": time.time(),
                }
            ),
        )
        page.on(
            "response",
            lambda response: (
                result["messages"].append(
                    {
                        "type": "http_error",
                        "url": response.url,
                        "status": response.status,
                        "time": time.time(),
                    }
                )
                if response.status >= 400
                else None
            ),
        )

        def socket(ws):
            """Record frames and retain the synthetic app's session token.

            Args:
                ws: Browser websocket.
            """
            nonlocal token
            values = urllib.parse.parse_qs(urllib.parse.urlparse(ws.url).query)
            if "token" in values:
                token = values["token"][0]
            for direction in ("framesent", "framereceived"):
                ws.on(
                    direction,
                    lambda payload, direction=direction: result["frames"].append(
                        {
                            "url": ws.url,
                            "direction": direction,
                            "payload": str(payload),
                            "time": time.time(),
                        }
                    ),
                )

        page.on("websocket", socket)

    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch()
        result["browser_version"] = browser.version
        context = browser.new_context(viewport={"width": 1150, "height": 900})
        try:
            page = context.new_page()
            attach(page)
            page.goto(f"http://localhost:{port}")
            page.locator("#add").wait_for()
            check_state(page, "initial", ["0", "0", "0", "idle"])
            page.locator("#note").fill(marker)
            page.wait_for_function(
                "expected => document.getElementById('note-value').textContent === expected",
                arg=marker,
            )
            page.locator("#add").click()
            check_state(page, "foreground-and-chain", ["1", "1", "0", "idle"])
            page.locator("#job").click()
            check_state(page, "background-completion", ["1", "1", "3", "done"])
            page.locator("#route-audit").click()
            page.locator("#page-audit").wait_for()
            page.locator("#add").click()
            check_state(page, "routed-event", ["2", "2", "3", "done"])
            page.locator("#fail").click()
            page.get_by_text("QA deliberate inventory failure", exact=True).wait_for()
            page.locator("#add").click()
            check_state(page, "recovery-after-handler-error", ["3", "3", "3", "done"])
            page.wait_for_timeout(6500)
            result["spans_before_outage"] = spans()
            record(
                "browser-export-before-outage",
                True,
                any(
                    row["service"] == "qa-frontend"
                    for row in result["spans_before_outage"]
                ),
            )
            record(
                "backend-export-before-outage",
                True,
                any(
                    row["service"] == "qa-backend" and row["name"].endswith(".add")
                    for row in result["spans_before_outage"]
                ),
            )
            result["outage_started"] = time.time()
            stop_collector()
            page.locator("#add").click()
            check_state(page, "foreground-during-refusal", ["4", "4", "3", "done"])
            page.locator("#job").click()
            check_state(page, "background-during-refusal", ["4", "4", "6", "done"])
            page.wait_for_timeout(6500)
            page.locator("#add").click()
            check_state(
                page, "foreground-after-export-failure", ["5", "5", "6", "done"]
            )
            page.screenshot(path=str(out / f"{engine}-refusal.png"), full_page=True)
            start_collector()
            result["collector_restored"] = time.time()
            page.locator("#add").click()
            check_state(page, "foreground-after-restore", ["6", "6", "6", "done"])
            page.locator("#route-home").click()
            page.locator("#page-home").wait_for()
            page.reload()
            check_state(page, "reload-retains-all-events", ["6", "6", "6", "done"])
            page.locator("#add").click()
            check_state(
                page, "fresh-interaction-after-restore", ["7", "7", "6", "done"]
            )
            page.wait_for_timeout(6500)
            result["spans_after_restore"] = [
                row
                for row in spans()
                if row["collected"] >= result["collector_restored"]
            ]
            page.screenshot(path=str(out / f"{engine}-final.png"), full_page=True)
        except Exception as error:
            result["driver_error"] = f"{type(error).__name__}: {error}"
            print(result["driver_error"], flush=True)
        finally:
            context.close()
            browser.close()
            start_collector()
    time.sleep(1)
    all_spans = spans()
    result["span_count"] = len(all_spans)
    result["token_sha256_16"] = (
        hashlib.sha256(token.encode()).hexdigest()[:16] if token else ""
    )
    backend = [row for row in all_spans if row["service"] == "qa-backend"]
    frontend = [row for row in all_spans if row["service"] == "qa-frontend"]
    producers = {row["span_id"]: row for row in frontend if row["kind"] == "PRODUCER"}
    consumers = [
        row
        for row in backend
        if row["kind"] == "CONSUMER" and row["name"].endswith(".add")
    ]
    linked = [
        row
        for row in consumers
        if row["parent_id"] in producers
        and producers[row["parent_id"]]["trace_id"] == row["trace_id"]
    ]
    result["linked_add_spans"] = linked
    record("producer-consumer-trace-link", True, bool(linked))
    by_id = {row["span_id"]: row for row in backend}
    audits = [
        row
        for row in backend
        if row["name"].endswith(".audit") and row["kind"] == "INTERNAL"
    ]
    record(
        "chained-event-parent",
        True,
        any(
            row["parent_id"] in by_id
            and by_id[row["parent_id"]]["name"].endswith(".add")
            and by_id[row["parent_id"]]["trace_id"] == row["trace_id"]
            for row in audits
        ),
    )
    record(
        "background-attribute",
        True,
        any(
            row["name"].endswith(".replenish")
            and row["attributes"].get("reflex.event.background") is True
            for row in backend
        ),
    )
    failed = [row for row in backend if row["name"].endswith(".fail")]
    record(
        "handler-error-status",
        True,
        any(
            row["status"].get("code") in (2, "STATUS_CODE_ERROR")
            and any(event["name"] == "exception" for event in row["events"])
            for row in failed
        ),
    )
    record(
        "successful-event-status",
        True,
        bool(consumers)
        and all(
            row["status"].get("code", 0)
            in (0, 1, "STATUS_CODE_UNSET", "STATUS_CODE_OK")
            for row in consumers
        ),
    )
    record(
        "session-pseudonym",
        True,
        bool(token)
        and bool(consumers)
        and all(
            row["attributes"].get("session.id") == result["token_sha256_16"]
            for row in consumers
        ),
    )
    exported = json.dumps(all_spans)
    record("raw-token-not-exported", False, bool(token) and token in exported)
    record("payload-not-exported", False, marker in exported)
    record(
        "react-render-span",
        True,
        any(row["name"] == "react.render" for row in frontend),
    )
    record(
        "web-vital-span",
        True,
        any(row["name"].startswith("web_vital.") for row in frontend),
    )
    record(
        "socket-connect-span",
        True,
        any(row["name"] == "socket.connect" for row in frontend),
    )
    after = result.get("spans_after_restore", [])
    record(
        "browser-export-restored",
        True,
        any(
            row["service"] == "qa-frontend" and row["name"].endswith(".add")
            for row in after
        ),
    )
    record(
        "backend-export-restored",
        True,
        any(
            row["service"] == "qa-backend" and row["name"].endswith(".add")
            for row in after
        ),
    )
    result["anomalies"] = [
        row
        for row in result["messages"]
        if row["type"]
        in {"warning", "error", "pageerror", "requestfailed", "http_error"}
    ]
    result["passed"] = not result.get("driver_error") and all(
        row["passed"] for row in result["checks"]
    )
    for key in ("messages", "frames", "spans_before_outage", "spans_after_restore"):
        (out / f"{engine}-{key}.json.gz").write_bytes(
            gzip.compress(json.dumps(result.pop(key, []), indent=2).encode(), mtime=0)
        )
    (out / f"{engine}-results.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    """Run one dev/prod server with two browsers and collector restarts.

    Returns:
        Nonzero on assertion, startup or cleanup failure.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", required=True, type=Path)
    parser.add_argument("--mode", choices=("dev", "prod"), required=True)
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    label = f"alpha2-{args.mode}-{args.attempt}"
    appdir = args.sb / "apps/tooling_otel" / label
    out = args.out / label
    if appdir.exists() or out.exists() or listeners():
        raise RuntimeError("App/output already exists or reserved ports occupied")
    shutil.copytree(
        source / "app", appdir, ignore=shutil.ignore_patterns("__pycache__")
    )
    out.mkdir(parents=True)
    env = dict(
        os.environ,
        REFLEX_TEST_ENV="otel-a2",
        REFLEX_TELEMETRY_ENABLED="false",
        PYTHONUNBUFFERED="1",
        PYTHONWARNINGS="default",
        UV_CACHE_DIR=str(args.sb / "uv-cache"),
        OTEL_SERVICE_NAME="qa-backend",
        OTEL_TRACES_EXPORTER="otlp",
        OTEL_METRICS_EXPORTER="none",
        OTEL_LOGS_EXPORTER="none",
        OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf",
        OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:8588",
        OTEL_EXPORTER_OTLP_TIMEOUT="1",
        OTEL_BSP_SCHEDULE_DELAY="200",
    )
    for key in ("NO_PROXY", "no_proxy", "PYTHONPATH"):
        env.pop(key, None)
    uv = [
        "uv",
        "--no-config",
        "run",
        "--no-project",
        "--python",
        str(args.sb / "envs/otel-a2/bin/python"),
    ]
    probe = "import json,sys,platform,reflex,reflex_otel,importlib.metadata as m; assert '/envs/otel-a2/' in reflex.__file__; assert '/envs/otel-a2/' in reflex_otel.__file__; print(json.dumps({'python':sys.version,'platform':platform.platform(),'reflex_file':reflex.__file__,'otel_file':reflex_otel.__file__,'packages':{d.metadata['Name']:d.version for d in m.distributions()}}))"
    metadata = json.loads(
        subprocess.check_output(
            [*uv, "python", "-c", probe], cwd=appdir, env=env, text=True
        )
    )
    result = {
        "label": label,
        "cwd": str(appdir),
        "metadata": metadata,
        "processes": [],
        "browsers": {},
    }
    active = {}

    def start(name, command, port):
        """Launch an owned process and await local HTTP readiness.

        Args:
            name: Process role.
            command: Exact command argument vector.
            port: Readiness port.
        """
        if name in active:
            return
        log = (out / f"{name}-{len(result['processes'])}.log").open("w")
        process = subprocess.Popen(
            command,
            cwd=appdir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        row = {
            "name": name,
            "pid": process.pid,
            "command": command,
            "started": time.time(),
        }
        result["processes"].append(row)
        active[name] = (process, log, row)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"{name} exited {process.returncode}")
            try:
                with opener.open(f"http://localhost:{port}", timeout=2) as response:
                    if response.status == 200:
                        return
            except OSError:
                pass
            time.sleep(0.5)
        raise TimeoutError(f"{name} never became ready")

    def stop(name):
        """Stop only the named owned process group.

        Args:
            name: Process role.
        """
        if name not in active:
            return
        process, log, row = active.pop(name)
        row["stopping"] = time.time()
        row["before_cleanup"] = group(process.pid)
        signals = (
            (signal.SIGTERM, signal.SIGKILL)
            if name == "collector"
            else (signal.SIGINT, signal.SIGTERM, signal.SIGKILL)
        )
        for sig in signals:
            process.poll()
            if not group(process.pid):
                break
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, sig)
            time.sleep(2)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=5)
        row["after_cleanup"] = group(process.pid)
        row["returncode"] = process.returncode
        log.close()

    def start_collector():
        """Restore the task-owned receiver, preserving its append-only evidence."""
        start(
            "collector",
            [
                *uv,
                "python",
                str(source / "collector.py"),
                "--out",
                str(out / "collector.jsonl"),
            ],
            8588,
        )

    try:
        start_collector()
        port = 3586 if args.mode == "dev" else 8586
        start(
            "server",
            [
                *uv,
                "reflex",
                "run",
                "--env",
                args.mode,
                "--frontend-port",
                str(port),
                "--backend-port",
                "8586",
                "--loglevel",
                "debug",
            ],
            port,
        )
        for engine in ("chromium", "webkit"):
            browser = browser_case(
                args, out, engine, lambda: stop("collector"), start_collector
            )
            result["browsers"][engine] = {
                "passed": browser["passed"],
                "checks": len(browser["checks"]),
                "failed": [
                    row["name"] for row in browser["checks"] if not row["passed"]
                ],
                "driver_error": browser.get("driver_error"),
                "anomalies": len(browser["anomalies"]),
            }
    except Exception as error:
        result["runner_error"] = f"{type(error).__name__}: {error}"
        print(result["runner_error"], flush=True)
    finally:
        stop("server")
        stop("collector")
        result["listeners_after_cleanup"] = listeners()
        exported = read_spans(out / "collector.jsonl")
        result["compile_spans"] = [
            row for row in exported if row["name"].startswith("reflex.compile")
        ]
        result["all_span_count"] = len(exported)
        result["passed"] = (
            bool(result["browsers"])
            and not result.get("runner_error")
            and not result["listeners_after_cleanup"]
            and all(not row["after_cleanup"] for row in result["processes"])
            and all(row["passed"] for row in result["browsers"].values())
        )
        (out / "run.json").write_text(json.dumps(result, indent=2))
        for path in [*out.glob("*.log"), out / "collector.jsonl"]:
            if path.exists():
                path.with_suffix(path.suffix + ".gz").write_bytes(
                    gzip.compress(path.read_bytes(), mtime=0)
                )
                path.unlink()
    print(json.dumps(result["browsers"]), flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    sys.exit(main())

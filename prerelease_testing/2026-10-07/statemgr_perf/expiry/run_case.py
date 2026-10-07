"""Run browser expiry, long-job or disk restart cases with bounded cleanup."""

import argparse
import contextlib
import gzip
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

from churn import run_churn

assert "/envs/driver/" in sys.executable, sys.executable


def group(pid):
    """Read a runner-owned process group.

    Args:
        pid: Group leader.

    Returns:
        Process table rows for that group.
    """
    rows = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    ).splitlines()
    return [
        row.strip()
        for row in rows
        if len(row.split(None, 4)) == 5 and int(row.split(None, 4)[2]) == pid
    ]


def files(directory):
    """Snapshot only disk-state file metadata.

    Args:
        directory: State file directory.

    Returns:
        Names, sizes and modification times, without pickle content.
    """
    return [
        {"name": path.name, "bytes": path.stat().st_size, "mtime": path.stat().st_mtime}
        for path in sorted(directory.glob("*.pkl"))
    ]


def latest_metrics(path):
    """Read the latest flushed observer row.

    Args:
        path: JSONL observer output.

    Returns:
        The latest complete row, or an empty dictionary.
    """
    if not path.exists():
        return {}
    for line in reversed(path.read_text().splitlines()):
        with contextlib.suppress(json.JSONDecodeError):
            return json.loads(line)
    return {}


def run_browser(args, out, engine, restart, metrics, states):
    """Drive public state events and collect browser/server observations.

    Args:
        args: Parsed case configuration.
        out: Output directory.
        engine: Playwright browser engine.
        restart: Callback for an orderly same-app server restart.
        metrics: Read-only observer output.
        states: Disk-state directory.

    Returns:
        Per-check correctness and captured anomalies.
    """
    result = {"engine": engine, "checks": [], "messages": [], "frames": []}
    defaults = {"root": 0, "child": 0, "a": 0, "b": 0}
    populated = {"root": 2, "child": 3, "a": 2, "b": 1}

    def record(name, expected, actual):
        """Retain an assertion.

        Args:
            name: Check name.
            expected: Expected value.
            actual: Observed value.
        """
        passed = actual == expected
        result["checks"].append({
            "name": name,
            "passed": passed,
            "expected": expected,
            "actual": actual,
        })
        print(f"{engine} {name}: {'PASS' if passed else 'FAIL'}", flush=True)

    def read_counts(page):
        """Read the visible counts atomically.

        Args:
            page: Browser page.

        Returns:
            Parsed counter values.
        """
        return page.evaluate(
            "() => Object.fromEntries(['root','child','a','b'].map(k => "
            "[k, Number(document.getElementById('count-'+k)?.textContent)]))"
        )

    def expect_counts(page, expected, name, timeout=3):
        """Poll displayed counters to a bounded deadline.

        Args:
            page: Browser page.
            expected: Expected counters.
            name: Check name.
            timeout: Convergence timeout in seconds.
        """
        deadline = time.monotonic() + timeout
        actual = None
        while time.monotonic() < deadline:
            actual = read_counts(page)
            if actual == expected:
                break
            page.wait_for_timeout(100)
        record(name, expected, actual)

    def inspect(page, expected, name):
        """Assert values returned from public get_state on the server.

        Args:
            page: Browser page.
            expected: Expected server counters.
            name: Check name.
        """
        page.locator("#inspect").click()
        deadline = time.monotonic() + 3
        actual = None
        while time.monotonic() < deadline:
            with contextlib.suppress(json.JSONDecodeError):
                actual = json.loads(page.locator("#receipt").inner_text())
            if actual == expected:
                break
            page.wait_for_timeout(100)
        record(name, expected, actual)

    def populate(page):
        """Set distinct state/substate/component counts through clicks.

        Args:
            page: Browser page.
        """
        for key, count in populated.items():
            for _ in range(count):
                page.locator(f"#add-{key}").click()
        expect_counts(page, populated, "populated")
        inspect(page, populated, "populated-server")

    def attach(page):
        """Record console, network errors and websocket messages.

        Args:
            page: Browser page.
        """
        page.on(
            "console",
            lambda item: result["messages"].append({
                "type": item.type,
                "text": item.text,
                "time": time.time(),
            }),
        )
        page.on(
            "pageerror",
            lambda error: result["messages"].append({
                "type": "pageerror",
                "text": str(error),
                "time": time.time(),
            }),
        )
        page.on(
            "requestfailed",
            lambda request: result["messages"].append({
                "type": "requestfailed",
                "url": request.url,
                "failure": request.failure,
                "time": time.time(),
            }),
        )
        page.on(
            "response",
            lambda response: (
                result["messages"].append({
                    "type": "http_error",
                    "url": response.url,
                    "status": response.status,
                    "time": time.time(),
                })
                if response.status >= 400
                else None
            ),
        )

        def socket(ws):
            """Attach bounded event-frame capture.

            Args:
                ws: Browser websocket.
            """
            for direction in ("framesent", "framereceived"):
                ws.on(
                    direction,
                    lambda payload, direction=direction: (
                        result["frames"].append({
                            "direction": direction,
                            "payload": str(payload),
                            "time": time.time(),
                        })
                        if len(result["frames"]) < 2000
                        else None
                    ),
                )

        page.on("websocket", socket)

    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch()
        context = browser.new_context(viewport={"width": 1100, "height": 1000})
        page = context.new_page()
        result["browser_version"] = browser.version
        try:
            attach(page)
            page.goto(f"http://localhost:{args.port}")
            page.locator("#add-root").wait_for()
            expect_counts(page, defaults, "initial", timeout=20)
            populate(page)
            page.wait_for_timeout(750)
            result["before"] = {
                "time": time.time(),
                "metrics": latest_metrics(metrics),
                "files": files(states),
            }
            row = result["before"]["metrics"]
            record(
                "resolved-manager",
                "StateManager" + args.manager.title(),
                row.get("manager"),
            )
            record(
                "resolved-expiration", args.expiration, row.get("expiration_seconds")
            )
            if args.manager == "disk":
                record(
                    "resolved-debounce",
                    float(args.debounce_seconds),
                    row.get("debounce_seconds"),
                )
                record("disk-files-written", True, bool(result["before"]["files"]))
            if args.scenario in {"restart", "worker-reload"}:
                result["restart_started"] = time.time()
                result["restart_detail"] = restart()
                result["restart_finished"] = time.time()
                result["after_restart_files"] = files(states)
                page.wait_for_timeout(1000)
                result["navigation_retries"] = []
                for attempt in range(3):
                    try:
                        page.goto(f"http://localhost:{args.port}")
                        break
                    except Exception as error:
                        result["navigation_retries"].append(str(error))
                        if attempt == 2:
                            raise
                        page.wait_for_timeout(500)
                persisted = populated if args.scenario == "worker-reload" else defaults
                expect_counts(page, persisted, "restart-hydration", timeout=20)
                inspect(page, persisted, "restart-server")
                page.locator("#add-child").click()
                expect_counts(
                    page,
                    {**persisted, "child": persisted["child"] + 1},
                    "restart-next-event",
                )
            elif args.scenario == "jobs":
                page.locator("#hold").click()
                page.locator("#add-root").click()
                page.wait_for_timeout((args.expiration + 0.4) * 1000)
                result["during_hold"] = latest_metrics(metrics)
                record(
                    "lock-held-beyond-expiry",
                    True,
                    result["during_hold"].get("locked", 0) > 0,
                )
                expect_counts(
                    page,
                    {**populated, "root": 13},
                    "queued-event-after-held-lock",
                    timeout=8,
                )
                inspect(page, {**populated, "root": 13}, "held-lock-server")
                page.locator("#external-job").click()
                page.wait_for_function(
                    "document.getElementById('job-status').textContent === 'completed'",
                    timeout=(args.expiration + 10) * 1000,
                )
                result["after_job_visible"] = read_counts(page)
                inspect(
                    page,
                    {**defaults, "root": 10},
                    "expired-background-reacquire-server",
                )
                page.reload()
                expect_counts(
                    page,
                    {**defaults, "root": 10},
                    "expired-background-reload",
                    timeout=20,
                )
            else:
                result["idle_started"] = time.time()
                page.wait_for_timeout((args.expiration + 2) * 1000)
                result["after_idle"] = {
                    "time": time.time(),
                    "metrics": latest_metrics(metrics),
                    "files": files(states),
                }
                row = result["after_idle"]["metrics"]
                record("idle-states-purged", 0, row.get("states"))
                record("idle-locks-purged", 0, row.get("locks"))
                if args.manager == "disk":
                    record("idle-files-purged", [], result["after_idle"]["files"])
                page.locator("#add-root").click()
                fresh = {**defaults, "root": 1}
                expect_counts(page, fresh, "post-expiry-click-visible")
                inspect(page, fresh, "post-expiry-click-server")
                page.screenshot(
                    path=str(out / f"{engine}-post-expiry.png"), full_page=True
                )
                page.reload()
                expect_counts(page, fresh, "post-expiry-reload", timeout=20)
                page.wait_for_timeout((args.expiration + 2) * 1000)
                page.reload()
                expect_counts(page, defaults, "idle-then-reload-defaults", timeout=20)
                page.locator("#add-b").click()
                expect_counts(page, {**defaults, "b": 1}, "fresh-component-event")
            page.screenshot(path=str(out / f"{engine}-final.png"), full_page=True)
        except Exception as error:
            result["driver_error"] = f"{type(error).__name__}: {error}"
            print(result["driver_error"], flush=True)
        finally:
            context.close()
            browser.close()
    result["anomalies"] = [
        message
        for message in result["messages"]
        if message["type"]
        in {"warning", "error", "pageerror", "requestfailed", "http_error"}
    ]
    result["passed"] = not result.get("driver_error") and all(
        check["passed"] for check in result["checks"]
    )
    for key in ("messages", "frames"):
        (out / f"{engine}-{key}.json.gz").write_bytes(
            gzip.compress(json.dumps(result.pop(key), indent=2).encode(), mtime=0)
        )
    (out / f"{engine}-results.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    """Launch one published train and clean every owned process group.

    Returns:
        One when assertions, startup or cleanup fail, otherwise zero.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", required=True, type=Path)
    parser.add_argument("--train", choices=("alpha2", "stable"), required=True)
    parser.add_argument("--manager", choices=("memory", "disk"), required=True)
    parser.add_argument(
        "--scenario",
        choices=("expiry", "restart", "worker-reload", "jobs", "churn"),
        default="expiry",
    )
    parser.add_argument("--mode", choices=("dev", "prod"), default="dev")
    parser.add_argument("--debounce-name", choices=("new", "old"), default="new")
    parser.add_argument("--debounce-value", default="250ms")
    parser.add_argument("--debounce-seconds", default="0.25")
    parser.add_argument("--expiration", type=int, default=5)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--browsers", default="chromium")
    parser.add_argument("--contexts", type=int, default=300)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    label = f"{args.train}-{args.manager}-{args.scenario}-{args.debounce_name}-{args.mode}-{args.attempt}"
    source = Path(__file__).resolve().parent
    appdir = args.sb / "apps/statemgr_expiry" / label
    out = args.out / label
    if appdir.exists() or out.exists():
        raise RuntimeError(
            "Choose a fresh attempt: app or output directory already exists"
        )
    shutil.copytree(source / "app", appdir)
    out.mkdir(parents=True)
    metrics = out / "metrics.jsonl"
    states = appdir / ".states"
    env = dict(
        os.environ,
        REFLEX_TEST_ENV=args.train,
        REFLEX_TELEMETRY_ENABLED="false",
        PYTHONUNBUFFERED="1",
        UV_CACHE_DIR=str(args.sb / "uv-cache"),
        REFLEX_STATE_MANAGER_MODE=args.manager,
        REFLEX_REDIS_TOKEN_EXPIRATION=str(args.expiration),
        REFLEX_STATES_WORKDIR=str(states),
        QA_METRICS=str(metrics),
        QA_JOB_DELAY=str(args.expiration + 2),
    )
    for key in (
        "NO_PROXY",
        "no_proxy",
        "REFLEX_STATE_MANAGER_DISK_DEBOUNCE",
        "REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS",
    ):
        env.pop(key, None)
    if args.manager == "disk":
        name = "REFLEX_STATE_MANAGER_DISK_DEBOUNCE" + (
            "_SECONDS" if args.debounce_name == "old" else ""
        )
        env[name] = args.debounce_value
    venv = args.sb / "envs" / args.train
    probe = (
        "import json,sys,platform,reflex,importlib.metadata as m;assert '/envs/"
        + args.train
        + "/' in reflex.__file__,reflex.__file__;print(json.dumps({'python':sys.version,'platform':platform.platform(),'reflex_file':reflex.__file__,'packages':{d.metadata['Name']:d.version for d in m.distributions()}}))"
    )
    metadata = json.loads(
        subprocess.check_output(
            [str(venv / "bin/python"), "-c", probe], cwd=appdir, env=env, text=True
        )
    )
    command = [
        str(venv / "bin/reflex"),
        "run",
        "--env",
        args.mode,
        "--frontend-port",
        str(args.port),
        "--backend-port",
        str(args.backend_port),
        "--loglevel",
        "debug",
    ]
    result = {
        "label": label,
        "args": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "command": command,
        "cwd": str(appdir),
        "metadata": metadata,
        "servers": [],
        "browsers": {},
    }
    server = None
    log = None

    def stop():
        """Stop the current owned server group with a bounded escalation."""
        nonlocal server, log
        if server is None:
            return
        row = result["servers"][-1]
        row["before_cleanup"] = group(server.pid)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            server.poll()
            if not group(server.pid):
                break
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(server.pid, sig)
            time.sleep(2)
        with contextlib.suppress(subprocess.TimeoutExpired):
            server.wait(timeout=5)
        row["after_cleanup"] = group(server.pid)
        row["listeners_after_cleanup"] = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{args.port},{args.backend_port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        ).stdout
        row["returncode"] = server.returncode
        log.close()
        server = None
        if row["after_cleanup"] or row["listeners_after_cleanup"]:
            raise RuntimeError("Server cleanup left processes or listening ports")

    def start():
        """Start the matching published CLI and wait for HTTP readiness."""
        nonlocal server, log
        log = (out / f"server-{len(result['servers']) + 1}.log").open("w")
        server = subprocess.Popen(
            command,
            cwd=appdir,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        result["servers"].append({"pid": server.pid, "started": time.time()})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(
                    f"Server exited {server.returncode} before readiness"
                )
            try:
                with opener.open(
                    f"http://localhost:{args.port}", timeout=2
                ) as response:
                    if response.status == 200 and metrics.exists():
                        return
            except OSError:
                pass
            time.sleep(1)
        raise TimeoutError("No frontend HTTP200 and manager observer within360s")

    def restart():
        """Reload the worker or restart the CLI according to the scenario.

        Returns:
            The restart method and worker identities.
        """
        old_worker = latest_metrics(metrics).get("pid")
        if args.scenario == "worker-reload":
            with (appdir / "expiry_dashboard/expiry_dashboard.py").open("a") as source:
                source.write("\n# QA: request a normal development backend reload.\n")
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                new_worker = latest_metrics(metrics).get("pid")
                if new_worker and new_worker != old_worker:
                    return {
                        "method": "source-edit-worker-reload",
                        "old_worker": old_worker,
                        "new_worker": new_worker,
                    }
                time.sleep(0.2)
            raise TimeoutError("No fresh backend worker observed after source edit")
        stop()
        start()
        return {
            "method": "full-cli-restart-clears-disk-state",
            "old_worker": old_worker,
            "new_worker": latest_metrics(metrics).get("pid"),
        }

    try:
        start()
        for engine in args.browsers.split(","):
            browser = (
                run_churn(args, out, engine, metrics)
                if args.scenario == "churn"
                else run_browser(args, out, engine, restart, metrics, states)
            )
            result["browsers"][engine] = {
                "passed": browser["passed"],
                "checks": len(browser["checks"]),
                "failed": [
                    check["name"] for check in browser["checks"] if not check["passed"]
                ],
                "driver_error": browser.get("driver_error"),
                "anomalies": len(browser["anomalies"]),
            }
    except Exception as error:
        result["runner_error"] = f"{type(error).__name__}: {error}"
        print(result["runner_error"], flush=True)
    finally:
        try:
            stop()
        except Exception as error:
            result["cleanup_error"] = f"{type(error).__name__}: {error}"
        (out / "run.json").write_text(json.dumps(result, indent=2))
        for path in [*out.glob("server-*.log"), metrics]:
            if path.exists():
                path.with_suffix(path.suffix + ".gz").write_bytes(
                    gzip.compress(path.read_bytes(), mtime=0)
                )
                path.unlink()
    print(json.dumps(result["browsers"]), flush=True)
    return int(
        bool(
            result.get("runner_error")
            or result.get("cleanup_error")
            or any(not run["passed"] for run in result["browsers"].values())
        )
    )


if __name__ == "__main__":
    sys.exit(main())

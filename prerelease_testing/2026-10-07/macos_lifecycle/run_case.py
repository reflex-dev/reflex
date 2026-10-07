"""Run a bounded, non-TTY macOS lifecycle and browser experiment."""

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable


def process_table():
    """Read PID, parent, process group, state, and command for running processes.

    Returns:
        Parsed process rows.
    """
    output = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    )
    result = []
    for line in output.splitlines():
        fields = line.strip().split(None, 4)
        if len(fields) == 5:
            result.append(dict(zip(("pid", "ppid", "pgid", "stat", "command"), fields)))
    return result


def group_rows(pid):
    """Get process-group members, including children orphaned by shutdown.

    Args:
        pid: The process-group leader.

    Returns:
        Process rows in the launched group.
    """
    return [row for row in process_table() if int(row["pgid"]) == pid]


def listeners(ports):
    """Read listeners for only this experiment's reserved ports.

    Args:
        ports: Reserved ports.

    Returns:
        lsof output.
    """
    result = subprocess.run(
        ["lsof", "-nP", "-iTCP:" + ",".join(map(str, ports)), "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def main() -> int:
    """Prepare an app, run browser checks, signal the CLI, and clean up.

    Returns:
        One for execution, shutdown or cleanup failures, otherwise zero.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--env", choices=("alpha2", "alpha", "stable"), required=True)
    parser.add_argument("--manager", choices=("npm", "bun"), required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--unicode-path", action="store_true")
    parser.add_argument("--hmr", action="store_true")
    parser.add_argument("--prod", action="store_true")
    parser.add_argument("--attempt", default="1")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    name = f"{args.env}-{args.manager}-{'prod' if args.prod else 'dev'}-{args.attempt}"
    app = (
        args.sb
        / "apps"
        / "macos_lifecycle"
        / ("spaces café 日本語" if args.unicode_path else "ascii")
        / name
    )
    if app.exists():
        raise RuntimeError(f"Refusing to overwrite previous experiment: {app}")
    shutil.copytree(Path(__file__).parent / "app", app)
    env = dict(
        os.environ,
        REFLEX_TEST_ENV=args.env,
        REFLEX_TELEMETRY_ENABLED="false",
        REFLEX_USE_NPM="1" if args.manager == "npm" else "0",
        PYTHONUNBUFFERED="1",
    )
    for key in ("NO_PROXY", "no_proxy"):
        env.pop(key, None)
    venv = args.sb / "envs" / args.env
    metadata_code = (
        "import importlib.metadata as m,json,os,platform,reflex,sys;"
        "assert '/envs/'+os.environ['REFLEX_TEST_ENV']+'/' in reflex.__file__,reflex.__file__;"
        "print(json.dumps({'python':sys.version,'executable':sys.executable,'reflex_file':reflex.__file__,"
        "'platform':platform.platform(),'packages':{d.metadata['Name']:d.version for d in m.distributions()"
        " if d.metadata['Name'].startswith('reflex') or d.metadata['Name'] in ('granian','pydantic','uvicorn')}}))"
    )
    metadata = json.loads(
        subprocess.check_output(
            [str(venv / "bin/python"), "-c", metadata_code], cwd=app, env=env, text=True
        )
    )
    command = [
        str(venv / "bin/reflex"),
        "run",
        "--frontend-port",
        str(args.port),
        "--backend-port",
        str(args.backend_port),
        "--loglevel",
        "debug",
    ]
    if args.prod:
        command += ["--env", "prod"]
    result = dict(
        name=name,
        metadata=metadata,
        command=command,
        app=str(app),
        manager=args.manager,
        hmr=args.hmr,
        prod=args.prod,
        messages=[],
        websockets=[],
    )
    report = args.out / f"{name}.json"
    server = None
    source = app / "lifecycle_app" / "lifecycle_app.py"
    initial_source = source.read_text()
    try:
        with (args.out / f"{name}.server.log").open("w") as log:
            server = subprocess.Popen(
                command,
                cwd=app,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            result["pid"] = server.pid
            result["started_at"] = time.time()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            url = f"http://localhost:{args.port}"
            deadline = time.monotonic() + 360
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError(f"CLI exited before ready: {server.returncode}")
                try:
                    with opener.open(url, timeout=2) as response:
                        if response.status == 200:
                            break
                except (OSError, TimeoutError):
                    pass
                time.sleep(1)
            else:
                raise TimeoutError(
                    "Frontend did not respond HTTP 200 within 360 seconds"
                )
            result["ready_seconds"] = time.time() - result["started_at"]
            print(
                f"{name}: frontend ready in {result['ready_seconds']:.1f}s", flush=True
            )
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                result["browser"] = browser.version
                page = browser.new_page(viewport={"width": 1100, "height": 720})
                page.set_default_timeout(30000)
                page.on(
                    "console",
                    lambda message: result["messages"].append(
                        dict(type=message.type, text=message.text)
                    ),
                )
                page.on(
                    "pageerror",
                    lambda error: result["messages"].append(
                        dict(type="pageerror", text=str(error))
                    ),
                )
                page.on(
                    "requestfailed",
                    lambda request: result["messages"].append(
                        dict(
                            type="requestfailed", url=request.url, error=request.failure
                        )
                    ),
                )
                page.on(
                    "response",
                    lambda response: (
                        result["messages"].append(
                            dict(
                                type="http_error",
                                url=response.url,
                                status=response.status,
                            )
                        )
                        if response.status >= 400
                        else None
                    ),
                )

                def capture_socket(ws):
                    """Capture bounded websocket evidence for this page.

                    Args:
                        ws: Browser websocket.
                    """
                    result["websockets"].append(dict(type="open", url=ws.url))
                    for event in ("framesent", "framereceived"):
                        ws.on(
                            event,
                            lambda payload, kind=event: (
                                result["websockets"].append(
                                    dict(type=kind, text=str(payload)[:1600])
                                )
                                if len(result["websockets"]) < 120
                                else None
                            ),
                        )

                page.on("websocket", capture_socket)
                try:
                    page.goto(url)
                    expect(page.locator("#heading")).to_have_text(
                        "Lifecycle version one"
                    )
                    page.get_by_role("button", name="Increment", exact=True).click()
                    expect(page.locator("#count")).to_have_text("1")
                    page.get_by_placeholder("Name").fill("Café 日本語 🚀")
                    expect(page.locator("#name")).to_have_text("Café 日本語 🚀")
                    result["browser_events_passed"] = True
                    page.screenshot(path=str(args.out / f"{name}-events.png"))
                    page.reload()
                    expect(page.locator("#heading")).to_have_text(
                        "Lifecycle version one"
                    )
                    expect(page.locator("#count")).to_have_text("1")
                    page.get_by_role("button", name="Increment", exact=True).click()
                    expect(page.locator("#count")).to_have_text("2")
                    result["reload_passed"] = True
                    if args.hmr:
                        source.write_text(
                            initial_source.replace(
                                "Lifecycle version one", "Lifecycle version two"
                            ).replace("self.count += 1", "self.count += 2")
                        )
                        expect(page.locator("#heading")).to_have_text(
                            "Lifecycle version two", timeout=60000
                        )
                        page.get_by_role("button", name="Increment", exact=True).click()
                        expect(page.locator("#count")).to_have_text("4", timeout=30000)
                        result["hmr_passed"] = True
                        page.screenshot(path=str(args.out / f"{name}-hmr.png"))
                finally:
                    browser.close()
            result["before_sigterm"] = group_rows(server.pid)
            result["listeners_before_sigterm"] = listeners((
                args.port,
                args.backend_port,
            ))
            signal_at = time.monotonic()
            server.send_signal(signal.SIGTERM)
            try:
                server.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            result["sigterm_wait_seconds"] = time.monotonic() - signal_at
            result["sigterm_cli_exited"] = server.poll() is not None
            result["returncode_after_sigterm"] = server.poll()
            result["after_sigterm"] = group_rows(server.pid)
            result["listeners_after_sigterm"] = listeners((
                args.port,
                args.backend_port,
            ))
            print(
                f"{name}: SIGTERM CLI exited={result['sigterm_cli_exited']}; listeners={bool(result['listeners_after_sigterm'])}",
                flush=True,
            )
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        print(result["error"], flush=True)
    finally:
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        if server is not None:
            result["before_cleanup"] = group_rows(server.pid)
            for cleanup_signal in (signal.SIGTERM, signal.SIGKILL):
                if group_rows(server.pid):
                    try:
                        os.killpg(server.pid, cleanup_signal)
                    except OSError as error:
                        result.setdefault("cleanup_errors", []).append(str(error))
                time.sleep(2)
            with contextlib.suppress(subprocess.TimeoutExpired):
                server.wait(timeout=5)
            time.sleep(1)
            result["after_cleanup"] = group_rows(server.pid)
            result["listeners_after_cleanup"] = listeners((
                args.port,
                args.backend_port,
            ))
        source.write_text(initial_source)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"Evidence: {report}", flush=True)
    return int(
        bool(
            result.get("error")
            or result.get("after_sigterm")
            or result.get("listeners_after_sigterm")
            or result.get("after_cleanup")
            or result.get("listeners_after_cleanup")
            or not result.get("sigterm_cli_exited")
        )
    )


if __name__ == "__main__":
    sys.exit(main())

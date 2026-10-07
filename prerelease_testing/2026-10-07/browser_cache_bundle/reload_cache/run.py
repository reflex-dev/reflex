"""Run published Reflex browsers through source and package-cache changes."""

import argparse
import contextlib
import gzip
import hashlib
import importlib.metadata
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

BASE = {
    "COPY": "Current",
    "CAPTION": "Baseline caption",
    "ACCENT": "rgb(240, 245, 255)",
    "BUTTON_RADIUS": "4px",
    "INCLUDE_MOMENT": False,
    "STATE_DEFAULT": "Original customer",
    "STEP": 1,
}
EDIT = {
    "COPY": "Revised",
    "CAPTION": "Edited default caption",
    "ACCENT": "rgb(232, 250, 238)",
    "BUTTON_RADIUS": "18px",
    "INCLUDE_MOMENT": False,
    "STATE_DEFAULT": "New customer",
    "STEP": 3,
}
PHASES = [
    ("base", BASE),
    ("memo-edit", EDIT),
    ("dependency-add", {**EDIT, "INCLUDE_MOMENT": True}),
    ("dependency-remove", {**EDIT, "STEP": 5}),
    ("json-format", {**EDIT, "STEP": 5}),
]


def group_rows(pgid: int) -> list[str]:
    """Read processes belonging to this server's isolated group.

    Args:
        pgid: Server process group.

    Returns:
        Process rows with matching group IDs.
    """
    lines = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    ).splitlines()
    return [
        line
        for line in lines
        if len(parts := line.split(None, 4)) == 5 and parts[2] == str(pgid)
    ]


def listeners(port: int, backend: int) -> str:
    """Read listeners for this experiment's two reserved ports.

    Args:
        port: Frontend port.
        backend: Backend port.

    Returns:
        lsof's listener listing.
    """
    return subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", f"-iTCP:{backend}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
    ).stdout


def write_settings(app: Path, phase: str, values: dict) -> None:
    """Atomically edit an imported application module as a developer would.

    Args:
        app: Isolated application directory.
        phase: Visible phase name.
        values: Literal settings for this phase.
    """
    destination = app / "cache_app" / "settings.py"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        '"""Imported view settings changed by the browser experiment."""\n\n'
        + "\n".join(
            f"{key} = {value!r}" for key, value in {"PHASE": phase, **values}.items()
        )
        + "\n"
    )
    temporary.replace(destination)


def package_snapshot(app: Path) -> dict:
    """Record package semantics and bytes without saving generated files.

    Args:
        app: Application directory.

    Returns:
        Root/web manifest content, hashes, and matching install-log counts.
    """
    output = {}
    for label, relative in (
        ("root", "reflex.lock/package.json"),
        ("web", ".web/package.json"),
    ):
        path = app / relative
        if path.exists():
            raw = path.read_bytes()
            output[label] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "content": json.loads(raw),
            }
    return output


def attach(page, record: dict) -> None:
    """Attach bounded browser diagnostic capture.

    Args:
        page: The browser page.
        record: Per-browser evidence record.
    """
    page.on(
        "console",
        lambda item: (
            record["console"].append(
                {"phase": record["phase"], "type": item.type, "text": item.text[:1800]}
            )
            if len(record["console"]) < 500
            else None
        ),
    )
    page.on(
        "pageerror",
        lambda item: record["pageerrors"].append(
            {
                "phase": record["phase"],
                "message": item.message,
                "stack": item.stack[:2500],
            }
        ),
    )
    page.on(
        "requestfailed",
        lambda item: (
            record["failed_requests"].append(
                {"phase": record["phase"], "url": item.url, "failure": item.failure}
            )
            if len(record["failed_requests"]) < 300
            else None
        ),
    )
    page.on(
        "response",
        lambda item: (
            record["http_errors"].append(
                {"phase": record["phase"], "url": item.url, "status": item.status}
            )
            if item.status >= 400
            else None
        ),
    )

    def socket(ws):
        """Capture bounded websocket frames for event and HMR evidence.

        Args:
            ws: Browser websocket.
        """
        for kind in ("framesent", "framereceived"):
            ws.on(
                kind,
                lambda frame, event=kind: (
                    record["websocket"].append(
                        {
                            "phase": record["phase"],
                            "kind": event,
                            "frame": str(frame)[:1200],
                        }
                    )
                    if len(record["websocket"]) < 150
                    else None
                ),
            )

    page.on("websocket", socket)


def exercise(page, phase: str, values: dict, fresh: bool, label: str) -> dict:
    """Verify current memo output, browser style, event behavior, and navigation.

    Args:
        page: Browser page to exercise.
        phase: Expected application revision.
        values: Expected current settings.
        fresh: Whether this context should receive fresh state defaults.
        label: Distinct customer name for this browser context.

    Returns:
        Observed revision, style, and state values.
    """
    expect(page.locator("#phase")).to_have_text(
        f"Release dashboard: {phase}", timeout=90000
    )
    expect(page.locator("#card-a .card-title")).to_have_text(
        f"{values['COPY']} Revenue"
    )
    expect(page.locator("#card-a .card-caption")).to_have_text(values["CAPTION"])
    expect(page.locator("#card-b .card-caption")).to_have_text("Explicit caption")
    expect(page.locator("#card-a .metric-card")).to_have_css(
        "background-color", values["ACCENT"]
    )
    expect(page.locator("#card-a .card-add")).to_have_css(
        "border-radius", values["BUTTON_RADIUS"]
    )
    if page.locator("#mount-log").count():
        expect(page.locator("#mount-log")).to_contain_text(f"{phase}:left")
        expect(page.locator("#mount-log")).to_contain_text(f"{phase}:right")
    if fresh:
        expect(page.locator("#card-a .card-customer")).to_have_text(
            values["STATE_DEFAULT"]
        )
    if values["INCLUDE_MOMENT"]:
        expect(page.locator("#card-a .card-moment")).to_have_text("2026-10-07")
    else:
        expect(page.locator(".card-moment")).to_have_count(0)
    before = int(page.locator("#card-a .card-total").inner_text())
    page.locator("#card-a .card-add").click()
    expect(page.locator("#card-a .card-total")).to_have_text(
        str(before + values["STEP"])
    )
    expect(page.locator("#card-b .card-total")).to_have_text(
        str(before + values["STEP"])
    )
    page.locator("#customer-input").fill(label)
    expect(page.locator("#card-a .card-customer")).to_have_text(label)
    page.locator("#report-link").click()
    expect(page.locator("#card-a .card-title")).to_have_text(f"{values['COPY']} Report")
    expect(page.locator("#card-a .card-customer")).to_have_text(label)
    page.locator("#overview-link").click()
    expect(page.locator("#card-a .card-title")).to_have_text(
        f"{values['COPY']} Revenue"
    )
    return {
        "count_before": before,
        "count_after": before + values["STEP"],
        "customer": label,
        "body": page.locator("body").inner_text(),
    }


def reload_page(page, url: str, record: dict) -> None:
    """Reload an old tab while retaining a known DevTools navigation race.

    Args:
        page: Existing browser tab.
        url: The server URL after restart.
        record: Evidence record to retain any protocol-level retry.
    """
    try:
        page.reload(wait_until="domcontentloaded")
    except Exception as error:
        if "Not attached to an active page" not in str(error):
            raise
        record.setdefault("reload_protocol_transients", []).append(str(error))
        page.wait_for_timeout(1000)
        page.goto(url, wait_until="domcontentloaded")


def main() -> int:
    """Run the revision sequence, warm restart, and optional production rebuild.

    Returns:
        Zero if all functional checks pass, otherwise one.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--env", choices=["alpha2", "alpha", "stable"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=3710)
    parser.add_argument("--backend", type=int, default=8710)
    parser.add_argument("--manager", choices=["bun", "npm"], default="bun")
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--hooks", action="store_true")
    parser.add_argument(
        "--format-target", choices=["both", "web", "root"], default="both"
    )
    args = parser.parse_args()
    name = f"{args.env}-{args.manager}-{args.attempt}" + (
        "-hooks" if args.hooks else ""
    )
    app = args.sb / "apps" / "reload_cache" / name
    if app.exists():
        raise RuntimeError(f"Refusing existing experiment directory: {app}")
    shutil.copytree(Path(__file__).parent / ("hooks_app" if args.hooks else "app"), app)
    output = args.out / name
    output.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        SB=str(args.sb),
        QA_ENV=args.env,
        REFLEX_TELEMETRY_ENABLED="false",
        REFLEX_USE_NPM="1" if args.manager == "npm" else "0",
        PYTHONUNBUFFERED="1",
    )
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    result = {
        "name": name,
        "app": str(app),
        "format_target": args.format_target,
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checks": [],
        "browsers": {},
        "packages": {},
        "servers": [],
    }
    result["metadata"] = json.loads(
        subprocess.check_output(
            [
                str(args.sb / "envs" / args.env / "bin/python"),
                "-c",
                "import reflex,importlib.metadata as m,json;print(json.dumps({'reflex_file':reflex.__file__,'packages':{d.metadata['Name']:d.version for d in m.distributions() if d.metadata['Name'].startswith('reflex')}}))",
            ],
            cwd=app,
            env=env,
            text=True,
        )
    )
    server = None
    log_handle = None
    log_path = None

    def save():
        """Persist partial results so interrupted runs remain useful."""
        (output / "results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False)
        )

    def start(mode: str, tag: str):
        """Start one isolated server and wait for its HTTP endpoint.

        Args:
            mode: Development or production mode.
            tag: Evidence log name.
        """
        nonlocal server, log_handle, log_path
        log_path = output / f"{tag}.server.log"
        log_handle = log_path.open("w")
        backend = args.port if mode == "prod" else args.backend
        command = [
            str(args.sb / "envs" / args.env / "bin/reflex"),
            "run",
            "--frontend-port",
            str(args.port),
            "--backend-port",
            str(backend),
            "--loglevel",
            "debug",
        ]
        if mode == "prod":
            command.extend(["--env", "prod"])
        server = subprocess.Popen(
            command,
            cwd=app,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        result["servers"].append({"tag": tag, "pid": server.pid, "command": command})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 360
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(
                    f"Server {tag} exited {server.returncode}; see {log_path}"
                )
            try:
                with opener.open(
                    f"http://localhost:{args.port}", timeout=2
                ) as response:
                    if response.status == 200:
                        print(name, tag, "ready", flush=True)
                        return
            except (OSError, TimeoutError):
                pass
            time.sleep(1)
        raise TimeoutError(f"Server {tag} not ready")

    def stop():
        """Stop and audit only the current server's isolated process group."""
        nonlocal server, log_handle
        if server is None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if group_rows(server.pid):
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(server.pid, sig)
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            time.sleep(1)
        result["servers"][-1]["after_cleanup"] = group_rows(server.pid)
        result["servers"][-1]["listeners_after_cleanup"] = listeners(
            args.port, args.backend
        )
        if log_handle:
            log_handle.close()
        server = None
        log_handle = None
        save()

    sessions = []
    try:
        start("dev", "dev")
        with sync_playwright() as pw:
            try:
                for engine in ("chromium", "webkit"):
                    browser = getattr(pw, engine).launch()
                    context = browser.new_context(
                        viewport={"width": 1040, "height": 720}
                    )
                    page = context.new_page()
                    record = {
                        "version": browser.version,
                        "phase": "base",
                        "console": [],
                        "pageerrors": [],
                        "failed_requests": [],
                        "http_errors": [],
                        "websocket": [],
                    }
                    result["browsers"][engine] = record
                    attach(page, record)
                    sessions.append((engine, browser, context, page, record))
                    page.goto(
                        f"http://localhost:{args.port}", wait_until="domcontentloaded"
                    )
                for phase, values in PHASES:
                    before_install = log_path.read_text().count(
                        "Installing frontend packages"
                    )
                    for *_, record in sessions:
                        record["phase"] = phase
                    if phase == "json-format":
                        paths = {
                            "root": app / "reflex.lock" / "package.json",
                            "web": app / ".web" / "package.json",
                        }
                        for key in (
                            paths
                            if args.format_target == "both"
                            else [args.format_target]
                        ):
                            path = paths[key]
                            path.write_text(
                                json.dumps(
                                    json.loads(path.read_text()),
                                    indent=4,
                                    sort_keys=True,
                                )
                                + "\n"
                            )
                    if phase != "base":
                        write_settings(app, phase, values)
                    for engine, browser, _, page, record in sessions:
                        check = {"phase": phase, "browser": engine}
                        try:
                            check["observed"] = exercise(
                                page,
                                phase,
                                values,
                                phase == "base",
                                f"{engine}-{phase}",
                            )
                            check["pass"] = True
                            if phase in (
                                "base",
                                "memo-edit",
                                "dependency-add",
                                "json-format",
                            ):
                                page.screenshot(
                                    path=str(output / f"{phase}-{engine}.png")
                                )
                            fresh_context = browser.new_context()
                            try:
                                fresh = fresh_context.new_page()
                                fresh.goto(
                                    f"http://localhost:{args.port}",
                                    wait_until="domcontentloaded",
                                )
                                expect(
                                    fresh.locator("#card-a .card-customer")
                                ).to_have_text(values["STATE_DEFAULT"], timeout=30000)
                                check["fresh_default"] = fresh.locator(
                                    "#card-a .card-customer"
                                ).inner_text()
                                if args.hooks:
                                    expect(fresh.locator("#mount-log")).to_contain_text(
                                        f"{phase}:left"
                                    )
                                    expect(fresh.locator("#mount-log")).to_contain_text(
                                        f"{phase}:right"
                                    )
                                    check["fresh_mounts"] = fresh.locator(
                                        "#mount-log"
                                    ).inner_text()
                            finally:
                                fresh_context.close()
                        except Exception as error:
                            check["pass"] = False
                            check["error"] = str(error)
                            with contextlib.suppress(Exception):
                                page.screenshot(
                                    path=str(output / f"{phase}-{engine}-failure.png")
                                )
                        result["checks"].append(check)
                        print(
                            name,
                            phase,
                            engine,
                            "PASS" if check["pass"] else "FAIL",
                            check.get("error", "")[:100],
                            flush=True,
                        )
                    after_install = log_path.read_text().count(
                        "Installing frontend packages"
                    )
                    result["packages"][phase] = {
                        "install_count_before": before_install,
                        "install_count_after": after_install,
                        **package_snapshot(app),
                    }
                    save()
                stop()
                start("dev", "warm-dev")
                for engine, _, _, page, record in sessions:
                    record["phase"] = "warm-restart"
                    check = {"phase": "warm-restart", "browser": engine}
                    try:
                        reload_page(page, f"http://localhost:{args.port}", record)
                        check["observed"] = exercise(
                            page, "json-format", PHASES[-1][1], False, f"{engine}-warm"
                        )
                        check["pass"] = True
                    except Exception as error:
                        check.update({"pass": False, "error": str(error)})
                    result["checks"].append(check)
                    print(name, "warm-restart", engine, check["pass"], flush=True)
                save()
                if args.production:
                    stop()
                    for phase, values in (
                        ("prod-initial", PHASES[-1][1]),
                        (
                            "prod-rebuild",
                            {
                                **BASE,
                                "COPY": "Published",
                                "STEP": 7,
                                "INCLUDE_MOMENT": True,
                            },
                        ),
                    ):
                        write_settings(app, phase, values)
                        start("prod", phase)
                        for engine, _, _, page, record in sessions:
                            record["phase"] = phase
                            check = {"phase": phase, "browser": engine}
                            try:
                                reload_page(
                                    page, f"http://localhost:{args.port}", record
                                )
                                check["observed"] = exercise(
                                    page, phase, values, False, f"{engine}-{phase}"
                                )
                                check["pass"] = True
                                page.screenshot(
                                    path=str(output / f"{phase}-{engine}.png")
                                )
                            except Exception as error:
                                check.update({"pass": False, "error": str(error)})
                            result["checks"].append(check)
                            print(name, phase, engine, check["pass"], flush=True)
                        result["packages"][phase] = package_snapshot(app)
                        save()
                        stop()
            finally:
                for _, browser, _, _, _ in sessions:
                    browser.close()
    except BaseException as error:
        result["harness_error"] = f"{type(error).__name__}: {error}"
        print(result["harness_error"], flush=True)
    finally:
        stop()
        for log in output.glob("*.server.log"):
            with gzip.open(log.with_suffix(log.suffix + ".gz"), "wb") as compressed:
                compressed.write(log.read_bytes())
            log.unlink()
        save()
    return int(
        bool(result.get("harness_error"))
        or any(not check["pass"] for check in result["checks"])
    )


if __name__ == "__main__":
    raise SystemExit(main())

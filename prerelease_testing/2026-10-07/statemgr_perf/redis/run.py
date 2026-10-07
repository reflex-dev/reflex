"""Run real browser Redis pool, substate-write, and duration experiments."""

import argparse
import asyncio
import collections
import contextlib
import gzip
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright, expect

assert "/envs/driver/" in sys.executable, sys.executable


def process_group(pid: int) -> list[str]:
    """Return processes in the experiment's isolated group.

    Args:
        pid: Group leader ID.

    Returns:
        Matching ps rows.
    """
    rows = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    ).splitlines()
    return [
        row
        for row in rows
        if len(parts := row.split(None, 4)) == 5 and parts[2] == str(pid)
    ]


def cleanup(process) -> list[str]:
    """Stop an owned process group and retain any surviving descendants.

    Args:
        process: Owned process with a new session.

    Returns:
        Remaining process rows.
    """
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if process_group(process.pid):
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(process.pid, sig)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=3)
        time.sleep(0.3)
    return process_group(process.pid)


def capture(page, record: dict) -> None:
    """Attach bounded browser diagnostic capture.

    Args:
        page: Browser page.
        record: Mutable session record.
    """
    page.on(
        "console",
        lambda item: (
            record["console"].append({"type": item.type, "text": item.text[:1800]})
            if len(record["console"]) < 100
            else None
        ),
    )
    page.on("pageerror", lambda item: record["pageerrors"].append(str(item)))
    page.on(
        "requestfailed",
        lambda item: (
            record["failed_requests"].append({"url": item.url, "failure": item.failure})
            if len(record["failed_requests"]) < 50
            else None
        ),
    )
    page.on(
        "response",
        lambda item: (
            record["http_errors"].append({"url": item.url, "status": item.status})
            if item.status >= 400
            else None
        ),
    )

    def socket(ws):
        """Record engine handshake and event frames.

        Args:
            ws: Newly opened websocket.
        """
        for kind in ("framesent", "framereceived"):
            ws.on(
                kind,
                lambda frame, event=kind: (
                    record["websocket"].append(
                        {"kind": event, "frame": str(frame)[:1400]}
                    )
                    if len(record["websocket"]) < 200
                    else None
                ),
            )

    page.on("websocket", socket)


def redis_command(port: int, *args: str) -> str:
    """Run a command only against this experiment's dedicated Redis.

    Args:
        port: Owned Redis port.
        args: Redis command and arguments.

    Returns:
        Command output.
    """
    return subprocess.check_output(
        ["/opt/homebrew/bin/redis-cli", "-p", str(port), *args], text=True
    )


def summarize_monitor(raw: str) -> dict:
    """Separate client commands from Lua-internal commands in a marked event.

    Args:
        raw: Redis MONITOR output.

    Returns:
        Command counts and source line references, excluding marker ECHOs.
    """
    active = False
    client = collections.Counter()
    lua = collections.Counter()
    selected = []
    for number, line in enumerate(raw.splitlines(), start=1):
        if '"ECHO" "QA_BATCH_START"' in line:
            active = True
            continue
        if '"ECHO" "QA_BATCH_END"' in line:
            active = False
            continue
        match = re.search(r'\[\d+ ([^]]+)\] "([^" ]+)"', line)
        if active and match:
            origin, command = match.groups()
            (lua if origin == "lua" else client)[command.upper()] += 1
            selected.append(
                {"line": number, "origin": origin, "command": command.upper()}
            )
    return {
        "client_commands": dict(client),
        "lua_commands": dict(lua),
        "commands": selected,
    }


async def browsers(args, result: dict, output: Path) -> None:
    """Drive six separate browser contexts concurrently and verify persistence.

    Args:
        args: Parsed run configuration.
        result: Experiment evidence.
        output: Evidence directory.
    """
    sessions = []
    async with async_playwright() as pw:
        engines = []
        try:
            for engine in ("chromium", "webkit"):
                browser = await getattr(pw, engine).launch()
                engines.append(browser)
                for index in range(3):
                    context = await browser.new_context(
                        viewport={"width": 1040, "height": 720}
                    )
                    page = await context.new_page()
                    identity = f"{engine}-{index}"
                    record = {
                        "identity": identity,
                        "browser_version": browser.version,
                        "console": [],
                        "pageerrors": [],
                        "failed_requests": [],
                        "http_errors": [],
                        "websocket": [],
                    }
                    result["sessions"].append(record)
                    capture(page, record)
                    sessions.append((page, identity, record))
            await asyncio.gather(
                *(page.goto(f"http://localhost:{args.port}") for page, _, _ in sessions)
            )
            await asyncio.gather(
                *(
                    expect(page.locator("#foreground")).to_have_text("0", timeout=30000)
                    for page, _, _ in sessions
                )
            )
            await asyncio.gather(
                *(
                    page.locator("#identity-input").fill(identity)
                    for page, identity, _ in sessions
                )
            )
            await asyncio.gather(
                *(
                    expect(page.locator("#identity")).to_have_text(identity)
                    for page, identity, _ in sessions
                )
            )
            monitor_path = output / "batch.monitor.log"
            with monitor_path.open("w") as monitor_handle:
                monitor = subprocess.Popen(
                    [
                        "/opt/homebrew/bin/redis-cli",
                        "-p",
                        str(args.redis_port),
                        "MONITOR",
                    ],
                    stdout=monitor_handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                try:
                    await asyncio.sleep(0.3)
                    redis_command(args.redis_port, "ECHO", "QA_BATCH_START")
                    await sessions[0][0].locator("#update-all").click()
                    await expect(sessions[0][0].locator("#batch")).to_have_text("1")
                    for index in range(20):
                        await expect(
                            sessions[0][0].locator(f"#leaf-{index}")
                        ).to_have_text("1")
                    await asyncio.sleep(0.6)
                    redis_command(args.redis_port, "ECHO", "QA_BATCH_END")
                    await asyncio.sleep(0.2)
                finally:
                    result["monitor_cleanup"] = cleanup(monitor)
            result["batch_commands"] = summarize_monitor(monitor_path.read_text())
            print(
                args.env,
                "twenty-substate batch PASS",
                result["batch_commands"]["client_commands"],
                flush=True,
            )
            await asyncio.gather(
                *(page.locator("#start-background").click() for page, _, _ in sessions)
            )
            for _ in range(20):
                await asyncio.gather(
                    *(page.locator("#increment").click() for page, _, _ in sessions)
                )
            for session_index, (page, identity, record) in enumerate(sessions):
                await expect(page.locator("#foreground")).to_have_text(
                    "20", timeout=30000
                )
                await expect(page.locator("#background")).to_have_text(
                    "20", timeout=30000
                )
                await expect(page.locator("#finished")).to_have_text("true")
                await expect(page.locator("#identity")).to_have_text(identity)
                for leaf in range(20):
                    await expect(page.locator(f"#leaf-{leaf}")).to_have_text(
                        "1" if session_index == 0 else "0"
                    )
                record["after_load"] = await page.locator("body").inner_text()
                record["load_pass"] = True
            result["redis_clients_after_load"] = redis_command(
                args.redis_port, "CLIENT", "LIST"
            )
            await asyncio.gather(*(page.reload() for page, _, _ in sessions))
            for session_index, (page, identity, record) in enumerate(sessions):
                await expect(page.locator("#identity")).to_have_text(identity)
                await expect(page.locator("#foreground")).to_have_text("20")
                await expect(page.locator("#background")).to_have_text("20")
                for leaf in range(20):
                    await expect(page.locator(f"#leaf-{leaf}")).to_have_text(
                        "1" if session_index == 0 else "0"
                    )
                record["reload_pass"] = True
                handshakes = [
                    json.loads(entry["frame"][1:])
                    for entry in record["websocket"]
                    if entry["frame"].startswith('0{"sid"')
                ]
                record["engine_handshakes"] = handshakes
                assert handshakes and all(
                    item["pingInterval"] == 120000 and item["pingTimeout"] == 10000
                    for item in handshakes
                ), handshakes
                if session_index in (0, 3):
                    await page.screenshot(path=str(output / f"{identity}-final.png"))
            print(
                args.env,
                "six sessions + background + reload + socket durations PASS",
                flush=True,
            )
        finally:
            for browser in engines:
                await browser.close()


def main() -> int:
    """Start dedicated Redis and a published app, then record browser results.

    Returns:
        Nonzero if correctness, startup, or cleanup fails.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--env", choices=["alpha2", "alpha", "stable"], required=True)
    parser.add_argument("--port", type=int, default=3268)
    parser.add_argument("--backend", type=int, default=8268)
    parser.add_argument("--redis-port", type=int, default=8269)
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--validation-wait", type=int, default=15)
    parser.add_argument("--validation-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).parent
    name = f"{args.env}-{args.attempt}"
    app = args.sb / "apps" / "statemgr_perf" / "redis" / name
    if app.exists():
        raise RuntimeError(f"Refusing existing app: {app}")
    ports = [args.port, args.backend, args.redis_port]
    listener_command = [
        "lsof",
        "-nP",
        *(f"-iTCP:{port}" for port in ports),
        "-sTCP:LISTEN",
    ]
    assert not subprocess.run(
        listener_command, capture_output=True, text=True
    ).stdout, "Reserved port already in use"
    shutil.copytree(root / "app", app)
    output = root / "results" / name
    output.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        SB=str(args.sb),
        QA_ENV=args.env,
        REFLEX_TELEMETRY_ENABLED="false",
        REFLEX_USE_NPM="0",
        PYTHONUNBUFFERED="1",
        REFLEX_STATE_MANAGER_MODE="redis",
        REFLEX_REDIS_URL=f"redis://127.0.0.1:{args.redis_port}",
        REFLEX_REDIS_MAX_CONNECTIONS="3",
        REFLEX_REDIS_POOL_TIMEOUT="500ms",
        REFLEX_SOCKET_INTERVAL="120" if args.env == "stable" else "2m",
        REFLEX_SOCKET_TIMEOUT="10" if args.env == "stable" else "10s",
    )
    result = {
        "name": name,
        "validation_only": args.validation_only,
        "sessions": [],
        "settings": {
            key: value for key, value in env.items() if key.startswith("REFLEX_")
        },
        "processes": [],
    }
    processes = []
    handles = []
    try:
        redis_handle = (output / "redis.server.log").open("w")
        handles.append(redis_handle)
        redis_server = subprocess.Popen(
            [
                "/opt/homebrew/bin/redis-server",
                "--port",
                str(args.redis_port),
                "--bind",
                "127.0.0.1",
                "--save",
                "",
                "--appendonly",
                "no",
                "--dir",
                str(app),
            ],
            stdout=redis_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        processes.append(("redis", redis_server))
        for _ in range(30):
            try:
                if redis_command(args.redis_port, "PING").strip() == "PONG":
                    break
            except subprocess.CalledProcessError:
                time.sleep(0.2)
        python = args.sb / "envs" / args.env / "bin/python"
        probe = "import reflex,os,json,importlib.metadata as m;from pathlib import Path;assert Path(reflex.__file__).is_relative_to(Path(os.environ['SB'])/'envs'/os.environ['QA_ENV']);from reflex.utils.prerequisites import get_redis;r=get_redis();p=r.connection_pool;print(json.dumps({'reflex_file':reflex.__file__,'version':m.version('reflex'),'pool_class':type(p).__name__,'max_connections':p.max_connections,'timeout':getattr(p,'timeout',None)}))"
        result["metadata"] = json.loads(
            subprocess.check_output(
                [
                    "uv",
                    "--no-config",
                    "run",
                    "--no-project",
                    "--python",
                    str(python),
                    "python",
                    "-c",
                    probe,
                ],
                cwd=app,
                env=env,
                text=True,
            )
        )
        if not args.validation_only:
            server_handle = (output / "app.server.log").open("w")
            handles.append(server_handle)
            command = [
                str(python.with_name("reflex")),
                "run",
                "--frontend-port",
                str(args.port),
                "--backend-port",
                str(args.backend),
                "--loglevel",
                "debug",
            ]
            result["server_command"] = command
            server = subprocess.Popen(
                command,
                cwd=app,
                env=env,
                stdout=server_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            processes.append(("app", server))
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(240):
                if server.poll() is not None:
                    raise RuntimeError(f"App exited {server.returncode}")
                try:
                    with opener.open(
                        f"http://localhost:{args.port}", timeout=2
                    ) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError("Frontend did not start")
            asyncio.run(browsers(args, result, output))
            result["processes"].append(
                {"tag": "app", "pid": server.pid, "after_cleanup": cleanup(server)}
            )
            processes.remove(("app", server))
        if args.env != "stable":
            for tag, overrides in (
                ("cap2", {"REFLEX_REDIS_MAX_CONNECTIONS": "2"}),
                ("timeout-longer-than-lock", {"REFLEX_REDIS_POOL_TIMEOUT": "11s"}),
            ):
                bad_log = output / f"invalid-{tag}.server.log"
                with bad_log.open("w") as handle:
                    bad = subprocess.Popen(
                        [
                            str(python.with_name("reflex")),
                            "run",
                            "--backend-only",
                            "--backend-port",
                            str(args.backend),
                            "--loglevel",
                            "debug",
                        ],
                        cwd=app,
                        env={**env, **overrides},
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    timed_out = False
                    try:
                        bad.wait(timeout=args.validation_wait)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                    finally:
                        before_cleanup = process_group(bad.pid)
                        rows = cleanup(bad)
                text = bad_log.read_text()
                expected = (
                    "must be at least 3"
                    if tag == "cap2"
                    else "must be greater than 0 and shorter than"
                )
                result.setdefault("invalid", {})[tag] = {
                    "returncode": bad.returncode,
                    "wait_seconds": args.validation_wait,
                    "timed_out": timed_out,
                    "expected_error_found": expected in text,
                    "before_cleanup": before_cleanup,
                    "after_cleanup": rows,
                }
    except BaseException as error:
        result["error"] = f"{type(error).__name__}: {error}"
        print(result["error"], flush=True)
    finally:
        for tag, process in reversed(processes):
            result["processes"].append(
                {"tag": tag, "pid": process.pid, "after_cleanup": cleanup(process)}
            )
        for handle in handles:
            handle.close()
        result["listeners_after_cleanup"] = subprocess.run(
            listener_command, capture_output=True, text=True
        ).stdout
        for log in output.glob("*.log"):
            log.with_suffix(log.suffix + ".gz").write_bytes(
                gzip.compress(log.read_bytes(), mtime=0)
            )
            log.unlink()
        (output / "results.json").write_text(json.dumps(result, indent=2))
    return int(
        bool(
            result.get("error")
            or result["listeners_after_cleanup"]
            or any(item["after_cleanup"] for item in result["processes"])
            or any(
                not item["expected_error_found"]
                for item in result.get("invalid", {}).values()
            )
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

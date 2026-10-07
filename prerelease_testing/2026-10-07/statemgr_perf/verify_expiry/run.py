"""Independently verify expiry recovery through browser and public state APIs."""

import argparse
import asyncio
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

from playwright.async_api import async_playwright, expect

assert "/envs/driver/" in sys.executable, sys.executable

SEED = {"root": 7, "section": 11, "left": 13, "right": 17}


def group_members(pid: int) -> list[str]:
    """Read the live members of an owned server process group.

    Args:
        pid: Process group leader.

    Returns:
        Matching process rows.
    """
    rows = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    ).splitlines()
    return [
        row
        for row in rows
        if len(parts := row.split(None, 4)) == 5 and parts[2] == str(pid)
    ]


def stop_server(process) -> dict:
    """Stop only the owned server group and verify its descendants are gone.

    Args:
        process: Server started with a new process session.

    Returns:
        Signals and the final process-group observation.
    """
    actions = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        before = group_members(process.pid)
        if before:
            actions.append({"signal": sig.name, "before": before})
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                if group_members(process.pid):
                    raise
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=3)
        time.sleep(0.3)
    return {"actions": actions, "remaining": group_members(process.pid)}


def attach(page, record: dict) -> None:
    """Capture browser diagnostics with phase labels and elapsed times.

    Args:
        page: Browser page.
        record: The case's mutable evidence object.
    """
    started = time.monotonic()

    def stamp() -> dict:
        """Return phase and elapsed time for an observed browser event.

        Returns:
            Current diagnostic position.
        """
        return {"phase": record["phase"], "elapsed_seconds": time.monotonic() - started}

    page.on(
        "console",
        lambda item: (
            record["console"].append(
                {**stamp(), "type": item.type, "text": item.text[:2000]}
            )
            if len(record["console"]) < 100
            else None
        ),
    )
    page.on(
        "pageerror",
        lambda item: record["pageerrors"].append({**stamp(), "text": str(item)}),
    )
    page.on(
        "requestfailed",
        lambda item: (
            record["failed_requests"].append(
                {**stamp(), "url": item.url, "failure": item.failure}
            )
            if len(record["failed_requests"]) < 60
            else None
        ),
    )
    page.on(
        "response",
        lambda item: (
            record["http_errors"].append(
                {**stamp(), "url": item.url, "status": item.status}
            )
            if item.status >= 400
            else None
        ),
    )

    def socket(ws):
        """Capture actual state deltas around expiry and completion.

        Args:
            ws: Browser websocket.
        """
        for kind in ("framesent", "framereceived"):
            ws.on(
                kind,
                lambda frame, event=kind: (
                    record["websocket"].append(
                        {**stamp(), "kind": event, "frame": str(frame)}
                    )
                    if len(record["websocket"]) < 300
                    else None
                ),
            )

    page.on("websocket", socket)


async def visible(page) -> dict:
    """Read the four visible counts without sending a backend event.

    Args:
        page: Browser page.

    Returns:
        The currently rendered counters.
    """
    return {key: int(await page.locator(f"#value-{key}").inner_text()) for key in SEED}


async def check_case(
    page, engine: str, kind: str, args, record: dict, output: Path
) -> None:
    """Compare observed DOM, a public server receipt, and a subsequent reload.

    Args:
        page: Isolated case page.
        engine: Browser engine name.
        kind: Background completion or ordinary idle-control case.
        args: Parsed verifier configuration.
        record: Evidence for this case.
        output: Artifact directory.
    """
    label = f"{engine}-{kind}"
    try:
        await page.goto(f"http://localhost:{args.port}", wait_until="domcontentloaded")
        await expect(page.locator("#value-root")).to_have_text("0", timeout=30000)
        record["phase"] = "seed"
        await page.locator("#seed").click()
        for key, value in SEED.items():
            await expect(page.locator(f"#value-{key}")).to_have_text(str(value))
        record["seed_visible"] = await visible(page)
        started = time.monotonic()
        if kind == "background":
            record["phase"] = "background-wait"
            await page.locator("#export").click()
            await expect(page.locator("#job-status")).to_have_text("exporting")
            await expect(page.locator("#job-status")).to_have_text(
                "complete", timeout=int((args.delay + 20) * 1000)
            )
            expected = {"root": 100, "section": 0, "left": 0, "right": 0}
            record["visible_at_completion"] = await visible(page)
            await page.wait_for_timeout(200)
        else:
            record["phase"] = "idle-wait"
            await asyncio.sleep(args.delay + 1)
            record["before_recovery_visible"] = await visible(page)
            record["phase"] = "foreground-recovery"
            await page.locator("#increment").click()
            await expect(page.locator("#value-root")).to_have_text("1")
            expected = {"root": 1, "section": 0, "left": 0, "right": 0}
            for key, value in expected.items():
                await expect(page.locator(f"#value-{key}")).to_have_text(str(value))
        record["elapsed_until_recovery_seconds"] = time.monotonic() - started
        record["phase"] = "before-inspection"
        record["visible_before_inspection"] = await visible(page)
        record["status_before_inspection"] = await page.locator(
            "#job-status"
        ).inner_text()
        await page.screenshot(path=str(output / f"{label}-before-inspection.png"))
        assert record["visible_before_inspection"]["root"] == expected["root"], record[
            "visible_before_inspection"
        ]
        record["phase"] = "public-inspection"
        await page.locator("#inspect").click()
        await expect(page.locator("#receipt")).to_have_text(
            json.dumps(expected, sort_keys=True)
        )
        record["public_server_receipt"] = json.loads(
            await page.locator("#receipt").inner_text()
        )
        record["visible_after_inspection"] = await visible(page)
        record["visible_backend_mismatch"] = {
            key: {"visible": record["visible_before_inspection"][key], "backend": value}
            for key, value in expected.items()
            if record["visible_before_inspection"][key] != value
        }
        record["phase"] = "reload"
        await page.reload(wait_until="domcontentloaded")
        for key, value in expected.items():
            await expect(page.locator(f"#value-{key}")).to_have_text(str(value))
        record["visible_after_reload"] = await visible(page)
        await page.screenshot(path=str(output / f"{label}-after-reload.png"))
        if kind == "idle":
            assert not record["visible_backend_mismatch"], record[
                "visible_backend_mismatch"
            ]
        record["expiry_and_persistence_checks_pass"] = True
        print(
            label,
            "completed",
            "mismatch",
            record["visible_backend_mismatch"],
            flush=True,
        )
    except Exception as error:
        record["error"] = f"{type(error).__name__}: {error}"
        record["expiry_and_persistence_checks_pass"] = False
        with contextlib.suppress(Exception):
            await page.screenshot(path=str(output / f"{label}-failure.png"))
        print(label, record["error"], flush=True)


async def browser_cases(args, output: Path, result: dict) -> None:
    """Run background and idle controls in separate Chromium/WebKit contexts.

    Args:
        args: Parsed verifier configuration.
        output: Artifact directory.
        result: Mutable run evidence.
    """
    async with async_playwright() as pw:
        browsers = []
        jobs = []
        try:
            for engine in ("chromium", "webkit"):
                browser = await getattr(pw, engine).launch()
                browsers.append(browser)
                for kind in ("background", "idle"):
                    context = await browser.new_context(
                        viewport={"width": 1100, "height": 720}
                    )
                    page = await context.new_page()
                    record = {
                        "engine": engine,
                        "browser_version": browser.version,
                        "kind": kind,
                        "phase": "load",
                        "console": [],
                        "pageerrors": [],
                        "http_errors": [],
                        "failed_requests": [],
                        "websocket": [],
                    }
                    result["cases"].append(record)
                    attach(page, record)
                    jobs.append(check_case(page, engine, kind, args, record, output))
            await asyncio.gather(*jobs)
        finally:
            for browser in browsers:
                await browser.close()


def main() -> int:
    """Start an isolated published app only after explicit execution authorization.

    Returns:
        Nonzero for harness, control, persistence, or browser errors. Observed
        background DOM mismatches are separately recorded findings, not hidden.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--env", choices=["stable", "alpha2"], required=True)
    parser.add_argument("--manager", choices=["memory", "disk"], required=True)
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev")
    parser.add_argument("--ttl", type=int, default=5)
    parser.add_argument("--delay", type=float, default=8)
    parser.add_argument("--port", type=int, default=3266)
    parser.add_argument("--backend", type=int, default=8266)
    parser.add_argument("--attempt", default="1")
    args = parser.parse_args()
    assert os.environ.get("EXPIRY_VERIFY_AUTHORIZED") == "1", (
        "Prepared verifier: parent must authorize execution after performance finishes."
    )
    assert args.ttl > 0 and args.delay > args.ttl + 1, (
        "External job must exceed the positive session TTL."
    )
    root = Path(__file__).parent
    name = f"{args.env}-{args.manager}-{args.mode}-{args.attempt}"
    app = args.sb / "apps" / "verify_expiry" / name
    if app.exists():
        raise RuntimeError(f"Refusing existing app: {app}")
    listener_command = [
        "lsof",
        "-nP",
        f"-iTCP:{args.port}",
        f"-iTCP:{args.backend}",
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
        VERIFY_SB=str(args.sb),
        VERIFY_ENV=args.env,
        VERIFY_MANAGER=args.manager,
        VERIFY_TTL=str(args.ttl),
        VERIFY_JOB_SECONDS=str(args.delay),
        REFLEX_TELEMETRY_ENABLED="false",
        REFLEX_USE_NPM="0",
        PYTHONUNBUFFERED="1",
    )
    for key in (
        "NO_PROXY",
        "no_proxy",
        "REFLEX_REDIS_URL",
        "REDIS_URL",
        "REFLEX_STATE_MANAGER_MODE",
        "STATE_MANAGER_MODE",
        "REFLEX_REDIS_TOKEN_EXPIRATION",
        "REDIS_TOKEN_EXPIRATION",
    ):
        env.pop(key, None)
    if args.env == "alpha2":
        env["REFLEX_STATE_MANAGER_DISK_DEBOUNCE"] = "250ms"
        env.pop("REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS", None)
    else:
        env["REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS"] = "0.25"
        env.pop("REFLEX_STATE_MANAGER_DISK_DEBOUNCE", None)
    backend = args.port if args.mode == "prod" else args.backend
    command = [
        str(args.sb / "envs" / args.env / "bin/reflex"),
        "run",
        "--env",
        args.mode,
        "--frontend-port",
        str(args.port),
        "--backend-port",
        str(backend),
        "--loglevel",
        "debug",
    ]
    result = {
        "name": name,
        "command": command,
        "ttl_seconds": args.ttl,
        "external_job_seconds": args.delay,
        "seed": SEED,
        "cases": [],
    }
    log = output / "server.log"
    with log.open("w") as handle:
        server = subprocess.Popen(
            command,
            cwd=app,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        result["server_pid"] = server.pid
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(240):
                if server.poll() is not None:
                    raise RuntimeError(f"Server exited {server.returncode}")
                try:
                    with opener.open(
                        f"http://localhost:{args.port}", timeout=2
                    ) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError("Frontend did not become ready")
            asyncio.run(browser_cases(args, output, result))
        except BaseException as error:
            result["harness_error"] = f"{type(error).__name__}: {error}"
            print(result["harness_error"], flush=True)
        finally:
            result["cleanup"] = stop_server(server)
    result["listeners_after_cleanup"] = subprocess.run(
        listener_command, capture_output=True, text=True
    ).stdout
    full = json.dumps(result, indent=2).encode()
    (output / "results.json.gz").write_bytes(gzip.compress(full, mtime=0))
    summary = {
        **result,
        "cases": [
            {
                key: value
                for key, value in case.items()
                if key not in ("console", "websocket", "failed_requests")
            }
            for case in result["cases"]
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    log.with_suffix(".log.gz").write_bytes(gzip.compress(log.read_bytes(), mtime=0))
    log.unlink()
    return int(
        bool(
            result.get("harness_error")
            or result["listeners_after_cleanup"]
            or result["cleanup"]["remaining"]
            or len(result["cases"]) != 4
            or any(
                not case.get("expiry_and_persistence_checks_pass")
                or case["pageerrors"]
                or case["http_errors"]
                for case in result["cases"]
            )
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

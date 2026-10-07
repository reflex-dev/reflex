"""Launch one isolated published environment and clean its process group."""

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

from drive import run_browser

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


def listeners(port, backend_port):
    """Read listeners on the two reserved ports.

    Args:
        port: Frontend port.
        backend_port: Backend port.

    Returns:
        Matching lsof rows, empty when the ports are free.
    """
    return subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port},{backend_port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
    ).stdout


def main():
    """Run one matrix case with strict assertion and cleanup exit status.

    Returns:
        Zero only if startup, both browsers and cleanup succeed.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", required=True, type=Path)
    parser.add_argument("--python", choices=("311", "313", "314"), required=True)
    parser.add_argument("--mode", choices=("dev", "prod"), required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--browsers", default="chromium,webkit")
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    label = f"py{args.python}-{args.mode}-{args.attempt}"
    source = Path(__file__).resolve().parent
    appdir = args.sb / "apps/pymatrix_a2" / label
    out = args.out / label
    if appdir.exists() or out.exists():
        raise RuntimeError("Choose a fresh attempt; app or output directory exists")
    if listeners(args.port, args.backend_port):
        raise RuntimeError("Reserved ports are occupied; refusing to start")
    shutil.copytree(
        source / "app", appdir, ignore=shutil.ignore_patterns("__pycache__")
    )
    out.mkdir(parents=True)
    envname = "pymatrix-a2-" + args.python
    env = dict(
        os.environ,
        REFLEX_TEST_ENV=envname,
        REFLEX_TELEMETRY_ENABLED="false",
        PYTHONUNBUFFERED="1",
        PYTHONWARNINGS="default",
        UV_CACHE_DIR=str(args.sb / "uv-cache"),
    )
    for key in ("NO_PROXY", "no_proxy", "PYTHONPATH"):
        env.pop(key, None)
    venv = args.sb / "envs" / envname
    uv = [
        "uv",
        "--no-config",
        "run",
        "--no-project",
        "--python",
        str(venv / "bin/python"),
    ]
    metadata = json.loads(
        subprocess.check_output(
            [*uv, "python", str(source / "probe.py")], cwd=appdir, env=env, text=True
        )
    )
    command = [
        *uv,
        "reflex",
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
        "command": command,
        "cwd": str(appdir),
        "metadata": metadata,
        "pythonwarnings": "default",
        "browsers": {},
    }
    server = None
    with (out / "server.log").open("w") as log:
        try:
            server = subprocess.Popen(
                command,
                cwd=appdir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            result["pid"] = server.pid
            result["started"] = time.time()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 360
            ready = False
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError(
                        f"Server exited {server.returncode} before readiness"
                    )
                try:
                    with opener.open(
                        f"http://localhost:{args.port}", timeout=2
                    ) as response:
                        if response.status == 200:
                            ready = True
                            break
                except OSError:
                    pass
                time.sleep(1)
            if not ready:
                raise TimeoutError("No frontend HTTP200 within 360 seconds")
            for engine in args.browsers.split(","):
                browser = run_browser(args, out, engine, metadata["python"].split()[0])
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
            if server:
                result["before_cleanup"] = group(server.pid)
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
                    server.poll()
                    if not group(server.pid):
                        break
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(server.pid, sig)
                    time.sleep(2)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    server.wait(timeout=5)
                result["after_cleanup"] = group(server.pid)
                result["returncode"] = server.returncode
            result["listeners_after_cleanup"] = listeners(args.port, args.backend_port)
            result["finished"] = time.time()
    result["passed"] = (
        bool(result["browsers"])
        and not result.get("runner_error")
        and not result.get("after_cleanup")
        and not result["listeners_after_cleanup"]
        and all(row["passed"] for row in result["browsers"].values())
    )
    (out / "run.json").write_text(json.dumps(result, indent=2))
    logpath = out / "server.log"
    logpath.with_suffix(".log.gz").write_bytes(
        gzip.compress(logpath.read_bytes(), mtime=0)
    )
    logpath.unlink()
    print(json.dumps(result["browsers"]), flush=True)
    return int(not result["passed"])


if __name__ == "__main__":
    sys.exit(main())

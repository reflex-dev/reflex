"""Run one isolated published train and capture both browser engines."""

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

from drive_dashboard import run_browser

assert "/envs/driver/" in sys.executable, sys.executable


def group(pid):
    """Read members of a process group created by this runner.

    Args:
        pid: Group leader PID.

    Returns:
        Process rows belonging to that group.
    """
    data = subprocess.check_output(
        ["ps", "-axo", "pid=,ppid=,pgid=,stat=,command="], text=True
    )
    return [
        row.strip()
        for row in data.splitlines()
        if len(row.split(None, 4)) == 5 and int(row.split(None, 4)[2]) == pid
    ]


def main():
    """Execute one server/browser matrix and ensure bounded owned-group cleanup.

    Returns:
        One if any browser assertion or cleanup fails.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--train", choices=("alpha2", "alpha", "stable"), required=True)
    parser.add_argument("--mode", choices=("dev", "prod"), default="dev")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--backend-port", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--browsers", default="chromium,webkit")
    args = parser.parse_args()
    label = f"{args.train}-{args.mode}-{args.attempt}"
    source = Path(__file__).resolve().parent
    app = args.sb / "apps/state_cache" / label
    out = args.out / label
    if app.exists() or out.exists():
        raise RuntimeError("Choose a fresh attempt: app or output already exists")
    shutil.copytree(source / "app", app)
    out.mkdir(parents=True)
    env = dict(
        os.environ,
        REFLEX_TEST_ENV=args.train,
        REFLEX_TELEMETRY_ENABLED="false",
        PYTHONUNBUFFERED="1",
        UV_CACHE_DIR=str(args.sb / "uv-cache"),
    )
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    venv = args.sb / "envs" / args.train
    probe = (
        "import json,sys,platform,reflex,importlib.metadata as m;assert '/envs/"
        + args.train
        + "/' in reflex.__file__,reflex.__file__;print(json.dumps({'python':sys.version,'platform':platform.platform(),'reflex_file':reflex.__file__,'packages':{d.metadata['Name']:d.version for d in m.distributions()}}))"
    )
    metadata = json.loads(
        subprocess.check_output(
            [str(venv / "bin/python"), "-c", probe], cwd=app, env=env, text=True
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
        "command": command,
        "cwd": str(app),
        "metadata": metadata,
        "browsers": {},
    }
    server = None
    log_path = out / "server.log"
    try:
        with log_path.open("w") as log:
            server = subprocess.Popen(
                command,
                cwd=app,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            result["server_pid"] = server.pid
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
                        if response.status == 200:
                            break
                except OSError:
                    pass
                time.sleep(1)
            else:
                raise TimeoutError("No frontend HTTP200 within360s")
            for engine in args.browsers.split(","):
                browser = run_browser(f"http://localhost:{args.port}", out, engine)
                result["browsers"][engine] = {
                    "passed": browser["passed"],
                    "checks": len(browser["checks"]),
                    "failed": [
                        item["name"] for item in browser["checks"] if not item["passed"]
                    ],
                    "anomalies": len(browser["anomalies"]),
                    "driver_error": browser.get("driver_error"),
                }
    except Exception as error:
        result["runner_error"] = f"{type(error).__name__}: {error}"
        print(result["runner_error"], flush=True)
    finally:
        if server is not None:
            result["before_cleanup"] = group(server.pid)
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
                server.poll()
                if not group(server.pid):
                    break
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(server.pid, sig)
                time.sleep(2)
            with contextlib.suppress(subprocess.TimeoutExpired):
                server.wait(timeout=5)
            result["after_cleanup"] = group(server.pid)
            result["listeners_after_cleanup"] = subprocess.run(
                [
                    "lsof",
                    "-nP",
                    f"-iTCP:{args.port},{args.backend_port}",
                    "-sTCP:LISTEN",
                ],
                capture_output=True,
                text=True,
            ).stdout
        (out / "run.json").write_text(json.dumps(result, indent=2))
        if log_path.exists():
            (out / "server.log.gz").write_bytes(
                gzip.compress(log_path.read_bytes(), mtime=0)
            )
            log_path.unlink()
    print(json.dumps(result.get("browsers", {})), flush=True)
    return int(
        bool(
            result.get("runner_error")
            or result.get("after_cleanup")
            or result.get("listeners_after_cleanup")
            or any(not run["passed"] for run in result["browsers"].values())
        )
    )


if __name__ == "__main__":
    sys.exit(main())

"""Run isolated published component apps and clean their process groups."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

assert "/envs/driver/" in sys.executable, sys.executable


def main():
    """Start one server at a time and save browser and server evidence."""
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--version", choices=["alpha2", "alpha", "stable"], default="alpha2")
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev")
    parser.add_argument("--browsers", default="chromium,webkit")
    parser.add_argument("--groups", default="select_matrix,forms,recharts")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    label = f"{args.version}-{args.mode}"
    app = args.scratch / "apps/forms" / label
    out = source / "runs" / label
    app.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / "app", app, dirs_exist_ok=True)
    environment = os.environ.copy()
    environment.update(REFLEX_TEST_ENV=f"forms-{args.version}", REFLEX_TELEMETRY_ENABLED="false", UV_CACHE_DIR=str(args.scratch / "uv-cache"))
    fp, bp = (3430, 8430) if args.mode == "dev" else (3431, 3431)
    environment["CLUSTER_API_URL"] = f"http://localhost:{bp}"
    command = ["uv", "--no-config", "run", "--no-project", "--python", str(args.scratch / f"envs/forms-{args.version}/bin/python"), "reflex", "run", "--env", args.mode, "--frontend-port", str(fp), "--backend-port", str(bp), "--loglevel", "debug"]
    summary = {"command": command, "cwd": str(app), "environment": {key: environment[key] for key in ("REFLEX_TEST_ENV", "REFLEX_TELEMETRY_ENABLED", "CLUSTER_API_URL")}, "drivers": []}
    with (out / "server.log").open("w") as server_log:
        process = subprocess.Popen(command, cwd=app, env=environment, stdout=server_log, stderr=subprocess.STDOUT, start_new_session=True)
        summary["pid"] = process.pid
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            deadline = time.monotonic() + 360
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Server exited {process.returncode}; see server.log")
                try:
                    with opener.open(f"http://localhost:{fp}/", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError("Frontend did not become ready in 360 seconds")
            for browser in args.browsers.split(","):
                driver = ["uv", "--no-config", "run", "--no-project", "--python", str(args.scratch / "envs/driver/bin/python"), "python", str(source / "scripts/drive_forms.py"), f"http://localhost:{fp}", str(out / browser), "--browser", browser, "--groups", args.groups]
                print(f"RUN {label} {browser}", flush=True)
                with (out / f"{browser}.log").open("w") as log:
                    result = subprocess.run(driver, cwd=app, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=600, check=False)
                summary["drivers"].append({"command": driver, "returncode": result.returncode})
                print(f"DONE {label} {browser}: {result.returncode}", flush=True)
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
                process.poll()
                listing = subprocess.check_output(["ps", "-axo", "pid=,pgid="], text=True)
                members = [int(line.split()[0]) for line in listing.splitlines() if int(line.split()[1]) == process.pid]
                if not members:
                    break
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    break
                time.sleep(2)
            process.wait(timeout=10)
            summary["server_returncode"] = process.returncode
            summary["cleanup_remaining_pids"] = members
            (out / "run.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

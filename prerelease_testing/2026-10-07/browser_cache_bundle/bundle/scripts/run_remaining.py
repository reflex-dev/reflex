"""Run remaining version/configuration comparisons one production server at a time."""

import os
import signal
import sys
import subprocess
import time
from pathlib import Path
import httpx
import playwright

SB = Path(os.environ["REFLEX_TEST_SB"])
assert str(SB / "envs/driver/lib") in playwright.__file__, playwright.__file__
ROOT = SB / "apps/browser-bundle"
UV = [
    "uv",
    "--no-config",
    "run",
    "--no-project",
    "--python",
    str(SB / "envs/driver/bin/python"),
    "python",
]

failed_cases = []
for train, lazy, port in [
    ("alpha2", 1, 8701),
    ("alpha", 0, 8702),
    ("alpha", 1, 8703),
    ("stable", 0, 8704),
    ("stable", 1, 8705),
]:
    label = f"{train}-lazy{lazy}"
    with (ROOT / f"logs/{label}-server.log").open("w") as log:
        server = subprocess.Popen(
            ["bash", str(ROOT / "scripts/start.sh"), train, str(lazy), str(port)],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        print("START", label, "PID", server.pid, flush=True)
        try:
            with httpx.Client(trust_env=False, timeout=2) as client:
                for attempt in range(360):
                    if server.poll() is not None:
                        raise RuntimeError(f"{label} exited {server.returncode}")
                    try:
                        response = client.get(f"http://localhost:{port}/")
                        if response.status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(1)
                else:
                    raise RuntimeError(f"{label} startup timeout")
            print("READY", label, flush=True)
            env = {
                **os.environ,
                "NO_PROXY": "localhost,127.0.0.1",
                "no_proxy": "localhost,127.0.0.1",
            }
            with (ROOT / f"logs/{label}-browser.log").open("w") as browserlog:
                completed = subprocess.run(
                    UV
                    + [
                        str(ROOT / "scripts/browser_matrix.py"),
                        f"http://localhost:{port}",
                        label,
                        str(ROOT / f"runs/{label}"),
                    ],
                    cwd=ROOT,
                    env=env,
                    stdout=browserlog,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                if completed.returncode:
                    failed_cases.append(
                        {"label": label, "returncode": completed.returncode}
                    )
                    print("BROWSER_FAILED", label, completed.returncode, flush=True)
            subprocess.run(
                UV
                + [
                    str(ROOT / "scripts/measure_assets.py"),
                    str(ROOT / label),
                    str(ROOT / f"runs/{label}/assets.json"),
                ],
                cwd=ROOT,
                check=True,
            )
            print("DONE", label, flush=True)
        finally:
            try:
                os.killpg(server.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(server.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                server.wait(timeout=10)
            try:
                os.killpg(server.pid, 0)
            except ProcessLookupError:
                pass
            else:
                os.killpg(server.pid, signal.SIGTERM)
            print("STOPPED", label, flush=True)

if failed_cases:
    print("FAILED_CASES", failed_cases, flush=True)
sys.exit(1 if failed_cases else 0)

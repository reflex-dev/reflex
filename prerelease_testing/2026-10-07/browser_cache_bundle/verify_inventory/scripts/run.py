"""Run independent inventory verification on stable and alpha2 sequentially."""

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
import httpx
import playwright

SB = Path(os.environ["REFLEX_TEST_SB"])
ROOT = SB / "apps/inventory-verifier"
assert str(SB / "envs/driver/lib") in playwright.__file__, playwright.__file__
UV = [
    "uv",
    "--no-config",
    "run",
    "--no-project",
    "--python",
    str(SB / "envs/driver/bin/python"),
    "python",
]
for train in ("stable", "alpha2"):
    app = ROOT / train
    if not app.exists():
        shutil.copytree(ROOT / "source", app)
    env = {
        **os.environ,
        "REFLEX_EXPECT_ENV": str(SB / "envs" / train),
        "REFLEX_TELEMETRY_ENABLED": "false",
    }
    with (ROOT / f"logs/{train}-server.log").open("w") as log:
        server = subprocess.Popen(
            [
                "uv",
                "--no-config",
                "run",
                "--no-project",
                "--python",
                str(SB / "envs" / train / "bin/python"),
                "reflex",
                "run",
                "--frontend-port",
                "3734",
                "--backend-port",
                "8734",
                "--loglevel",
                "debug",
            ],
            cwd=app,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        print("START", train, server.pid, flush=True)
        try:
            with httpx.Client(trust_env=False, timeout=2) as client:
                for _ in range(360):
                    if server.poll() is not None:
                        raise RuntimeError("server exited")
                    try:
                        if client.get("http://localhost:3734/").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(1)
                else:
                    raise RuntimeError("startup timeout")
            print("READY", train, flush=True)
            driverenv = {
                **os.environ,
                "NO_PROXY": "localhost,127.0.0.1",
                "no_proxy": "localhost,127.0.0.1",
            }
            with (ROOT / f"logs/{train}-browser.log").open("w") as browserlog:
                subprocess.run(
                    UV
                    + [
                        str(ROOT / "scripts/check_inventory.py"),
                        "http://localhost:3734",
                        train,
                        str(ROOT / f"runs/{train}"),
                    ],
                    cwd=ROOT,
                    env=driverenv,
                    stdout=browserlog,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            print("DONE", train, flush=True)
        finally:
            try:
                os.killpg(server.pid, signal.SIGINT)
            except ProcessLookupError:
                pass
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=10)
            try:
                os.killpg(server.pid, 0)
            except ProcessLookupError:
                pass
            else:
                os.killpg(server.pid, signal.SIGTERM)

"""Serial, reproducible benchmark matrix with an explicit quiet-machine gate."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import httpx
import playwright

SB = Path(os.environ["REFLEX_TEST_SB"])
ROOT = SB / "apps/statemgr-performance"
assert str(SB / "envs/driver/lib") in playwright.__file__, playwright.__file__
parser = argparse.ArgumentParser()
parser.add_argument("--smoke", action="store_true")
parser.add_argument(
    "--phase", choices=("all", "compile", "browser", "isolated"), default="all"
)
args = parser.parse_args()
assert args.smoke or os.environ.get("PERF_QUIET_CONFIRMED") == "1", (
    "No timing until parent explicitly confirms the machine is quiet."
)
(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "runs").mkdir(exist_ok=True)
records = []
failed = []


def uv(train):
    """Build an isolated interpreter command.

    Args:
        train: Published environment name.

    Returns:
        A uv argv prefix without project resolution.
    """
    return [
        "uv",
        "--no-config",
        "run",
        "--no-project",
        "--python",
        str(SB / "envs" / train / "bin/python"),
    ]


def environment(train, shared=0, mode="prod"):
    """Return explicit application configuration.

    Args:
        train: Published release environment.
        shared: Whether the unused SharedState exists.
        mode: Reflex development or production mode.

    Returns:
        The child-process environment.
    """
    env = {
        **os.environ,
        "REFLEX_EXPECT_ENV": str(SB / "envs" / train),
        "REFLEX_TELEMETRY_ENABLED": "false",
        "REFLEX_ENV_MODE": mode,
        "PERF_SHARED": str(shared),
        "PERF_API_URL": "http://localhost:8274",
        "PERF_QUIET_CONFIRMED": "0" if args.smoke else "1",
    }
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    return env


def appdir(train, shared=0):
    """Refresh only app source in a reusable scratch installation.

    Args:
        train: Release train.
        shared: Unused SharedState control.

    Returns:
        Neutral scratch app directory.
    """
    app = ROOT / f"{train}-shared{shared}"
    shutil.copytree(ROOT / "source", app, dirs_exist_ok=True)
    return app


def run_command(label, command, cwd, env, measured=False):
    """Capture a command, optionally measuring complete process wall time.

    Args:
        label: Unique output label.
        command: Argument vector.
        cwd: Neutral working directory.
        env: Child environment.
        measured: Whether this is an authorized measured repetition.

    Returns:
        The captured result record.
    """
    print("START", label, flush=True)
    load_before = os.getloadavg()
    started = time.perf_counter_ns() if measured else None
    with (ROOT / f"logs/{label}.log").open("w") as handle:
        child = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    elapsed = time.perf_counter_ns() - started if measured else None
    log = (ROOT / f"logs/{label}.log").read_text()
    row = {
        "label": label,
        "returncode": child.returncode,
        "wall_ns": elapsed,
        "compile_pages_seconds": re.findall(r"Compile pages: ([0-9.]+)", log),
        "full_python_compile_seconds": re.findall(
            r"App compiled successfully in ([0-9.]+) seconds", log
        ),
        "load_average_before": load_before,
        "load_average_after": os.getloadavg(),
        "package_install_log_lines": [
            line
            for line in log.splitlines()
            if any(
                marker in line.lower()
                for marker in (
                    "bun install",
                    "installing frontend",
                    "installed [",
                    "packages installed",
                    "checked ",
                    "no changes",
                )
            )
        ],
    }
    records.append(row)
    if child.returncode:
        failed.append(label)
    (ROOT / "runs/commands.json").write_text(json.dumps(records, indent=2))
    print("DONE", label, "returncode", child.returncode, flush=True)
    return row


def process_group_members(pgid):
    """Read process membership without macOS empty-group permission probes.

    Args:
        pgid: Dedicated process group created for our server.

    Returns:
        Live process IDs belonging to the group.
    """
    listing = subprocess.run(
        ["ps", "-axo", "pid=,pgid="], capture_output=True, text=True, check=True
    )
    return [
        int(pid)
        for line in listing.stdout.splitlines()
        for pid, group in [line.split()]
        if int(group) == pgid
    ]


def stop_server(server):
    """Escalate only against populated owned groups and verify no survivors.

    Args:
        server: Parent subprocess running a Reflex server.

    Raises:
        RuntimeError: Owned descendants survived SIGKILL.
    """
    for sig, grace in ((signal.SIGINT, 10), (signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        server.poll()
        members = process_group_members(server.pid)
        if not members:
            break
        print("CLEANUP_SIGNAL", server.pid, sig.name, members, flush=True)
        try:
            os.killpg(server.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # macOS can report EPERM after the last group member exits.
            if process_group_members(server.pid):
                raise
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            server.poll()
            if not process_group_members(server.pid):
                break
            time.sleep(0.25)
    server.wait(timeout=2)
    survivors = process_group_members(server.pid)
    if survivors:
        raise RuntimeError(
            f"Owned process group {server.pid} survived cleanup: {survivors}"
        )
    print("CLEANUP_VERIFIED_EMPTY", server.pid, flush=True)


if args.phase in ("all", "isolated"):
    for repeat in range(1 if args.smoke else 3):
        trains = ("stable", "alpha2") if repeat % 2 == 0 else ("alpha2", "stable")
        for mode in ("dev", "prod"):
            for train in trains:
                run_command(
                    f"{train}-{mode}-direct-{repeat}"
                    + ("-smoke" if args.smoke else ""),
                    uv(train)
                    + [
                        "python",
                        str(ROOT / "scripts/direct_probe.py"),
                        "--repeats",
                        "1",
                    ]
                    + (["--smoke"] if args.smoke else []),
                    ROOT,
                    environment(train, mode=mode),
                )
        for train in trains:
            run_command(
                f"{train}-vars-{repeat}" + ("-smoke" if args.smoke else ""),
                uv(train)
                + ["python", str(ROOT / "scripts/var_probe.py"), "--repeats", "1"]
                + (["--smoke"] if args.smoke else []),
                ROOT,
                environment(train),
            )

if args.phase in ("all", "compile"):
    for train in ("stable", "alpha2"):
        run_command(
            f"{train}-compile-setup",
            uv(train)
            + [
                "reflex",
                "export",
                "--frontend-only",
                "--no-zip",
                "--env",
                "prod",
                "--loglevel",
                "debug",
            ],
            appdir(train),
            environment(train),
        )
    for train in ("stable", "alpha2"):
        run_command(
            f"{train}-python-compile-setup",
            uv(train)
            + ["reflex", "compile", "--dry", "--no-rich", "--loglevel", "debug"],
            appdir(train),
            environment(train),
        )
    if not args.smoke:
        for repeat in range(3):
            for train in (
                ("stable", "alpha2") if repeat % 2 == 0 else ("alpha2", "stable")
            ):
                run_command(
                    f"{train}-python-compile-{repeat}",
                    uv(train)
                    + [
                        "reflex",
                        "compile",
                        "--dry",
                        "--no-rich",
                        "--loglevel",
                        "debug",
                    ],
                    appdir(train),
                    environment(train),
                    measured=True,
                )
                run_command(
                    f"{train}-compile-{repeat}",
                    uv(train)
                    + [
                        "reflex",
                        "export",
                        "--frontend-only",
                        "--no-zip",
                        "--env",
                        "prod",
                        "--loglevel",
                        "debug",
                    ],
                    appdir(train),
                    environment(train),
                    measured=True,
                )

if args.phase in ("all", "browser"):
    # Reverse version/configuration order on alternate repeats to reduce ordering bias.
    cases = [("stable", 0), ("alpha2", 0), ("stable", 1), ("alpha2", 1)]
    for repeat in range(1 if args.smoke else 3):
        for train, shared in cases if repeat % 2 == 0 else reversed(cases):
            label = f"{train}-shared{shared}-browser-{repeat}" + (
                "-smoke" if args.smoke else ""
            )
            env = environment(train, shared)
            with (ROOT / f"logs/{label}-server.log").open("w") as handle:
                server = subprocess.Popen(
                    uv(train)
                    + [
                        "reflex",
                        "run",
                        "--env",
                        "prod",
                        "--frontend-port",
                        "8274",
                        "--backend-port",
                        "8274",
                        "--loglevel",
                        "debug",
                    ],
                    cwd=appdir(train, shared),
                    env=env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                print("SERVER", label, server.pid, flush=True)
                try:
                    with httpx.Client(trust_env=False, timeout=2) as client:
                        for _ in range(600):
                            if server.poll() is not None:
                                raise RuntimeError(
                                    f"{label} server exited {server.returncode}"
                                )
                            try:
                                if (
                                    client.get("http://localhost:8274/").status_code
                                    == 200
                                ):
                                    break
                            except httpx.HTTPError:
                                pass
                            time.sleep(1)
                        else:
                            raise RuntimeError(f"{label} startup timeout")
                    driverenv = {
                        **env,
                        "NO_PROXY": "localhost,127.0.0.1",
                        "no_proxy": "localhost,127.0.0.1",
                    }
                    run_command(
                        label,
                        uv("driver")
                        + [
                            "python",
                            str(ROOT / "scripts/browser_probe.py"),
                            "http://localhost:8274",
                            str(ROOT / f"runs/{label}"),
                            "--repeats",
                            "1",
                        ]
                        + (["--smoke"] if args.smoke else []),
                        ROOT,
                        driverenv,
                    )
                except Exception as error:
                    failed.append(label)
                    records.append({"label": label, "exception": repr(error)})
                    print("FAILED", label, repr(error), flush=True)
                finally:
                    stop_server(server)
                    print("STOPPED", label, flush=True)
(ROOT / "runs/commands.json").write_text(json.dumps(records, indent=2))
print("FAILED_CASES", failed, flush=True)
raise SystemExit(1 if failed else 0)

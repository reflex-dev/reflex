"""Isolate npm install invalidation on an ordinary text-only source edit."""

import argparse
import contextlib
import gzip
import hashlib
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

from run import attach, group_rows, listeners

assert "/envs/driver/" in sys.executable, sys.executable


def snapshot(app: Path, python: Path, env: dict) -> dict:
    """Capture manifest semantics and lock hashes without retaining node_modules.

    Args:
        app: Running application's directory.
        python: Published Reflex environment interpreter.
        env: Application environment.

    Returns:
        Manifests, lockfile hashes, and the compiler's next rendered manifest.
    """
    output = {}
    for prefix in ("reflex.lock", ".web"):
        for name in ("package.json", "package-lock.json"):
            path = app / prefix / name
            raw = path.read_bytes()
            content = json.loads(raw)
            output[f"{prefix}/{name}"] = {
                "sha256": hashlib.sha256(raw).hexdigest(),
                "semantic_sha256": hashlib.sha256(
                    json.dumps(content, sort_keys=True).encode()
                ).hexdigest(),
                "content": content
                if name == "package.json"
                else {"root_package": content["packages"][""]},
            }
    script = "import json;from reflex.utils.frontend_skeleton import _compile_package_json;print(json.dumps(json.loads(_compile_package_json())))"
    output["next_rendered_manifest"] = json.loads(
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
                script,
            ],
            cwd=app,
            env=env,
            text=True,
        )
    )
    current = output[".web/package.json"]["content"]
    rendered = output["next_rendered_manifest"]
    output["semantic_differences"] = {
        key: {"current": current.get(key), "rendered": rendered.get(key)}
        for key in current.keys() | rendered.keys()
        if current.get(key) != rendered.get(key)
    }
    return output


def main():
    """Run cold load, source-only edit, and empty-devDependencies control.

    Returns:
        Nonzero when browser assertions or cleanup fail.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--sb", type=Path, required=True)
    parser.add_argument("--env", choices=["alpha2", "alpha", "stable"], required=True)
    parser.add_argument("--attempt", default="1")
    parser.add_argument("--port", type=int, default=3710)
    parser.add_argument("--backend", type=int, default=8710)
    args = parser.parse_args()
    root = Path(__file__).parent
    name = f"{args.env}-minimal-{args.attempt}"
    app = args.sb / "apps" / "reload_cache" / name
    if app.exists():
        raise RuntimeError(f"Refusing existing app: {app}")
    shutil.copytree(root / "minimal_app", app)
    output = root / "minimal_results" / name
    output.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        SB=str(args.sb),
        QA_ENV=args.env,
        REFLEX_USE_NPM="1",
        REFLEX_TELEMETRY_ENABLED="false",
        PYTHONUNBUFFERED="1",
    )
    python = args.sb / "envs" / args.env / "bin/python"
    result = {"name": name, "checks": [], "snapshots": {}, "browsers": {}}
    log = output / "server.log"
    with log.open("w") as handle:
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
        server = subprocess.Popen(
            command,
            cwd=app,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        result.update(command=command, pid=server.pid)
        sessions = []
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(240):
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
            with sync_playwright() as pw:
                try:
                    for engine in ("chromium", "webkit"):
                        browser = getattr(pw, engine).launch()
                        page = browser.new_page()
                        record = {
                            "version": browser.version,
                            "phase": "revision-A",
                            "console": [],
                            "pageerrors": [],
                            "failed_requests": [],
                            "http_errors": [],
                            "websocket": [],
                        }
                        attach(page, record)
                        result["browsers"][engine] = record
                        sessions.append((engine, browser, page, record))
                        page.goto(f"http://localhost:{args.port}")
                    for phase in ("revision-A", "revision-B", "revision-C"):
                        before = log.read_text().count("Installing frontend packages")
                        if phase == "revision-C":
                            path = app / ".web/package.json"
                            content = json.loads(path.read_text())
                            content["devDependencies"] = {}
                            path.write_text(json.dumps(content))
                            result["snapshots"]["control-before-edit"] = snapshot(
                                app, python, env
                            )
                        for _, _, _, record in sessions:
                            record["phase"] = phase
                        if phase != "revision-A":
                            (app / "minimal_app/label.py").write_text(
                                f'LABEL = "{phase}"\n'
                            )
                        for engine, _, page, _ in sessions:
                            expect(page.locator("#phase")).to_have_text(
                                phase, timeout=90000
                            )
                            previous = int(page.locator("#count").inner_text())
                            page.locator("#increment").click()
                            expect(page.locator("#count")).to_have_text(
                                str(previous + 1)
                            )
                            result["checks"].append(
                                {
                                    "phase": phase,
                                    "browser": engine,
                                    "pass": True,
                                    "count_after": previous + 1,
                                }
                            )
                        result["snapshots"][phase] = {
                            "installs_before": before,
                            "installs_after": log.read_text().count(
                                "Installing frontend packages"
                            ),
                            **snapshot(app, python, env),
                        }
                        print(
                            name,
                            phase,
                            "PASS",
                            result["snapshots"][phase]["installs_before"],
                            result["snapshots"][phase]["installs_after"],
                            flush=True,
                        )
                    sessions[-1][2].screenshot(path=str(output / "final-webkit.png"))
                finally:
                    for _, browser, _, _ in sessions:
                        browser.close()
        except BaseException as error:
            result["error"] = f"{type(error).__name__}: {error}"
            print(result["error"], flush=True)
        finally:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                if group_rows(server.pid):
                    with contextlib.suppress(ProcessLookupError, PermissionError):
                        os.killpg(server.pid, sig)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    server.wait(timeout=3)
                time.sleep(1)
            result["after_cleanup"] = group_rows(server.pid)
            result["listeners_after_cleanup"] = listeners(args.port, args.backend)
    (output / "results.json").write_text(json.dumps(result, indent=2))
    log.with_suffix(".log.gz").write_bytes(gzip.compress(log.read_bytes(), mtime=0))
    log.unlink()
    return int(
        bool(
            result.get("error")
            or result["after_cleanup"]
            or result["listeners_after_cleanup"]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

"""Compare old static builds with current published backends and history restores."""

import argparse
import functools
import gzip
import hashlib
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
SOURCE = Path(__file__).resolve().parent


def command(scratch, version, *arguments):
    """Return an isolated uv invocation for a published environment."""
    return ["uv", "--no-config", "run", "--no-project", "--python",
            str(scratch / f"envs/{version}/bin/python"), *arguments]


def members(group):
    """Return existing process IDs in a task-owned process group."""
    output = subprocess.check_output(["ps", "-axo", "pid=,pgid="], text=True)
    return [int(row.split()[0]) for row in output.splitlines()
            if int(row.split()[1]) == group]


def stop(process):
    """Stop a task-owned process group and return surviving members."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        process.poll()
        if not members(process.pid):
            break
        os.killpg(process.pid, sig)
        time.sleep(2)
    process.wait(timeout=10)
    return members(process.pid)


def wait_server(process, url):
    """Wait for the requested server or report an early process failure."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited {process.returncode}")
        try:
            with opener.open(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError(url)


class StaticHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the previously exported frontend without framework recompilation."""

    def log_message(self, format, *args):
        """Suppress routine static access logs captured by browser tracing."""


def drive(browser_type, out, revision, build_revision="A", bfcache=False):
    """Exercise hydration, persisted preferences and browser history restoration."""
    out.mkdir(parents=True, exist_ok=False)
    evidence = {"browser": browser_type.name, "checks": [], "console": [],
                "pageerrors": [], "failed_requests": [], "http_errors": [],
                "websockets": [], "navigation": []}
    launch_options = {"ignore_default_args": ["--disable-back-forward-cache"]} if bfcache and browser_type.name == "chromium" else {}
    browser = browser_type.launch(**launch_options)
    evidence["bfcache_requested"] = bfcache
    evidence["browser_version"] = browser.version
    context = browser.new_context()
    context.add_init_script("""globalThis.__historyEvents = [];
      for (const type of ['pageshow','pagehide']) addEventListener(type, e => {
        globalThis.__historyEvents.push({type, persisted:e.persisted, time:Date.now()});
        console.log('HISTORY_'+type+':'+e.persisted);
      });""")
    page = context.new_page()
    page.on("console", lambda msg: evidence["console"].append({"type": msg.type, "text": msg.text}))
    page.on("pageerror", lambda error: evidence["pageerrors"].append(str(error)))
    page.on("requestfailed", lambda req: evidence["failed_requests"].append({"url": req.url, "failure": req.failure}))
    page.on("response", lambda resp: evidence["http_errors"].append({"url": resp.url, "status": resp.status}) if resp.status >= 400 else None)

    def socket_open(socket):
        """Record each websocket's actual messages and closure time."""
        record = {"url": socket.url, "frames": []}
        evidence["websockets"].append(record)
        for event, direction in (("framesent", "sent"), ("framereceived", "received")):
            socket.on(event, lambda payload, direction=direction: record["frames"].append({
                "time": time.time(), "direction": direction, "payload": str(payload)}))
        socket.on("close", lambda: record.update(closed=time.time()))

    page.on("websocket", socket_open)

    def check(name, actual, expected):
        """Record a semantic comparison without discarding later evidence."""
        evidence["checks"].append({"name": name, "actual": actual, "expected": expected, "ok": actual == expected})

    try:
        quota = 100 if revision == "A" else 250
        tier = "Starter" if revision == "A" else "Professional"
        page.goto("http://localhost:3730/", wait_until="networkidle")
        page.wait_for_function("document.querySelector('#hydrated')?.textContent === 'true'", timeout=30000)
        check("static_build", page.locator("#build").inner_text(), f"Frontend build {build_revision}")
        check("live_quota_before_event", page.locator("#quota").inner_text(), str(quota))
        check("live_tier_before_event", page.locator("#tier").inner_text(), tier)
        check("computed_remaining_before_event", page.locator("#remaining").inner_text(), str(quota))
        check("dict_insertion_order", page.locator(".feature").all_inner_texts(),
              ["reports", "exports"] if revision == "A" else ["exports", "reports"])
        first_identity = page.locator("#identity").inner_text()
        check("factory_identity_length", len(first_identity), 32)
        check("default_not_persisted", page.evaluate("localStorage.getItem('dashboard-density')"), None)
        page.locator("#use").click()
        page.wait_for_function("document.querySelector('#used')?.textContent === '1'")
        check("backend_echo", page.locator("#observed").inner_text(), f"{revision}:{tier}:{quota}:1")
        check("remaining_after_event", page.locator("#remaining").inner_text(), str(quota - 1))
        page.locator("#roomy").click()
        page.wait_for_function("localStorage.getItem('dashboard-density') === 'roomy'")
        page.reload(wait_until="networkidle")
        page.wait_for_function("document.querySelector('#hydrated')?.textContent === 'true'")
        check("reload_keeps_used", page.locator("#used").inner_text(), "1")
        check("reload_keeps_identity", page.locator("#identity").inner_text(), first_identity)
        check("reload_restores_storage", page.locator("#density").inner_text(), "roomy")
        page.locator("#help").click()
        page.wait_for_url("**/help.html")
        page.wait_for_function("document.querySelector('h1')?.textContent === 'Dashboard help'")
        check("external_document_loaded", page.locator("h1").inner_text(), "Dashboard help")
        page.go_back(wait_until="networkidle")
        page.wait_for_function("document.querySelector('#hydrated')?.textContent === 'true'")
        evidence["navigation"].append(page.evaluate("performance.getEntriesByType('navigation').map(x=>({type:x.type,name:x.name}))"))
        check("history_keeps_used", page.locator("#used").inner_text(), "1")
        check("history_keeps_identity", page.locator("#identity").inner_text(), first_identity)
        page.locator("#use").click()
        page.wait_for_function("document.querySelector('#used')?.textContent === '2'")
        check("history_event_works", page.locator("#observed").inner_text(), f"{revision}:{tier}:{quota}:2")
        evidence["history_state"] = page.evaluate("globalThis.__historyEvents")
        page.screenshot(path=str(out / "dashboard.png"), full_page=True)
        other = browser.new_context()
        other_page = other.new_page()
        other_page.goto("http://localhost:3730/", wait_until="networkidle")
        other_page.wait_for_function("document.querySelector('#hydrated')?.textContent === 'true'")
        check("independent_session_used", other_page.locator("#used").inner_text(), "0")
        check("independent_factory_identity", other_page.locator("#identity").inner_text() != first_identity, True)
        check("independent_storage", other_page.locator("#density").inner_text(), "compact")
        other.close()
    except Exception as error:
        evidence["exception"] = repr(error)
        try:
            page.screenshot(path=str(out / "failure.png"), full_page=True)
        except Exception:
            pass
    finally:
        context.close()
        browser.close()
        with gzip.open(out / "trace.json.gz", "wt") as output:
            json.dump(evidence, output, indent=2)
        summary = {key: value for key, value in evidence.items() if key not in {"console", "websockets"}}
        summary["console_errors"] = [row for row in evidence["console"] if row["type"] == "error"]
        summary["history_events"] = [row for row in evidence["console"] if row["text"].startswith("HISTORY_")]
        (out / "result.json").write_text(json.dumps(summary, indent=2))
    return bool(evidence.get("exception") or evidence["pageerrors"] or evidence["http_errors"]
                or any(not row["ok"] for row in evidence["checks"]))


def main():
    """Build three published frontends and compare deployment combinations."""
    parser = argparse.ArgumentParser()
    parser.add_argument("scratch", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--build-revision", default="A")
    parser.add_argument("--build-extra-state", action="store_true")
    parser.add_argument("--bfcache", action="store_true")
    parser.add_argument("--browsers", default="chromium,webkit")
    parser.add_argument("--cases", default="stable-stable-A,alpha-alpha-A,alpha2-alpha2-A,stable-alpha2-A,alpha-alpha2-A,alpha2-alpha2-B,alpha2-alpha2-B-extra,stable-stable-B-extra,alpha-alpha-B-extra")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    failed = False
    with sync_playwright() as playwright:
        for case in args.cases.split(","):
            front, back, revision, *extra = case.split("-")
            output = args.output / case
            output.mkdir(exist_ok=False)
            source_hash = hashlib.sha256((SOURCE / "app/deploy_app/deploy_app.py").read_bytes()).hexdigest()
            app = args.scratch / f"apps/deploy-cache-{source_hash[:8]}-{args.build_revision}-{int(args.build_extra_state)}" / f"Account Café {front}"
            environment = os.environ.copy()
            environment.update(TEST_REFLEX_ENV=front, DEPLOY_REVISION=args.build_revision, DEPLOY_EXTRA_STATE="1" if args.build_extra_state else "0",
                               REFLEX_TELEMETRY_ENABLED="false", GRANIAN_WORKERS="1", UV_CACHE_DIR=str(args.scratch / "uv-cache"))
            if not (app / "build-finished.json").exists():
                app.mkdir(parents=True, exist_ok=False)
                shutil.copytree(SOURCE / "app", app, dirs_exist_ok=True)
                build_command = command(args.scratch, front, "reflex", "export", "--no-zip", "--frontend-only", "--loglevel", "debug")
                with (output / "build.log").open("w") as log:
                    result = subprocess.run(build_command, cwd=app, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=600)
                if result.returncode:
                    raise RuntimeError(f"Build failed: {case}")
                (app / "build-finished.json").write_text(json.dumps({"command": build_command, "source_hash": hashlib.sha256((SOURCE / "app/deploy_app/deploy_app.py").read_bytes()).hexdigest()}))
            static = app / ".web/build/client"
            (static / "help.html").write_text("<!doctype html><title>Help</title><h1>Dashboard help</h1><p>Use browser Back to return.</p>")
            server = http.server.ThreadingHTTPServer(("127.0.0.1", 3730), functools.partial(StaticHandler, directory=str(static)))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            environment.update(TEST_REFLEX_ENV=back, DEPLOY_REVISION=revision, DEPLOY_EXTRA_STATE="1" if extra else "0")
            backend_command = command(args.scratch, back, "reflex", "run", "--env", "prod", "--backend-only", "--backend-port", "8730", "--loglevel", "debug")
            record = {"frontend": front, "backend": back, "revision": revision, "build_revision": args.build_revision, "build_extra_state": args.build_extra_state, "extra_state": bool(extra), "command": backend_command, "browsers": {}, "build": json.loads((app / "build-finished.json").read_text())}
            print("RUN", case, flush=True)
            with (output / "backend.log").open("w") as log:
                process = subprocess.Popen(backend_command, cwd=app, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    wait_server(process, "http://localhost:8730/ping")
                    for name in args.browsers.split(","):
                        browser_failed = drive(getattr(playwright, name), output / name, revision, args.build_revision, args.bfcache)
                        record["browsers"][name] = {"failed": browser_failed}
                        failed |= browser_failed
                except Exception as error:
                    record["exception"] = repr(error)
                    failed = True
                finally:
                    record["cleanup_survivors"] = stop(process)
                    failed |= bool(record["cleanup_survivors"])
                    server.shutdown()
                    server.server_close()
                    (output / "run.json").write_text(json.dumps(record, indent=2))
                    for log_path in output.glob("*.log"):
                        with gzip.open(log_path.with_suffix(".log.gz"), "wb") as compressed:
                            compressed.write(log_path.read_bytes())
                        log_path.unlink()
            print("DONE", case, record["browsers"], flush=True)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())

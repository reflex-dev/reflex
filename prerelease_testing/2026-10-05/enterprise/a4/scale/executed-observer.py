"""Run published-package cookie and bounded State-scale browser comparisons."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

import reflex
import reflex_base
import reflex_enterprise
from playwright.sync_api import expect, sync_playwright

UV = "/Users/masenf/.local/bin/uv"
BUN = "/private/tmp/reflex-pre-js-runtime-20261005/bun/bin/bun"


def save(path: Path, value: dict) -> None:
    """Save observations before cleanup or optional screenshots.

    Args:
        path: Evidence destination.
        value: Serializable observations.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def provenance() -> dict:
    """Verify isolated import origins and inventory published installations.

    Returns:
        Runtime identity and exact installed graph.
    """
    origins = {
        module.__name__: module.__file__
        for module in (reflex, reflex_base, reflex_enterprise)
    }
    assert all(Path(path).is_relative_to(sys.prefix) for path in origins.values())
    distributions = list(importlib.metadata.distributions())
    direct = [
        dist.metadata["Name"] for dist in distributions if dist.read_text("direct_url.json")
    ]
    assert not direct, direct
    assert importlib.metadata.version("reflex-enterprise") == "0.9.7a4"
    return {
        "executable": sys.executable,
        "prefix": sys.prefix,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "origins": origins,
        "graph": sorted(
            [{"name": dist.metadata["Name"], "version": dist.version} for dist in distributions],
            key=lambda item: item["name"].lower(),
        ),
        "direct_url_installations": direct,
        "bun": subprocess.check_output([BUN, "--version"], text=True).strip(),
    }


def stop(process: subprocess.Popen) -> None:
    """Stop the owned process group, including exited frontend descendants.

    Args:
        process: Public CLI process launched in a new session.
    """
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            continue
        time.sleep(0.5)


def observe_scale(base_url: str, output: Path, graph: str) -> dict:
    """Observe direct routing, memoized navigation and a backend event.

    Args:
        base_url: Owned application origin.
        output: Evidence directory.
        graph: Framework graph; stable has a known direct-route HTTP 404.

    Returns:
        Assertions and browser/network diagnostics, including failures.
    """
    result = {"passed": False, "console": [], "page_errors": [], "http_errors": [],
              "failed_requests": [], "steps": []}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(15_000)
        page.on("console", lambda msg: result["console"].append(
            {"type": msg.type, "text": msg.text, "location": msg.location}))
        page.on("pageerror", lambda err: result["page_errors"].append(str(err)))
        page.on("requestfailed", lambda req: result["failed_requests"].append(
            {"url": req.url, "failure": req.failure}))
        page.on("response", lambda res: result["http_errors"].append(
            {"url": res.url, "status": res.status}) if res.status >= 400 else None)
        try:
            response = page.goto(base_url + "/articles/7?self=1", wait_until="networkidle")
            result["document_status"] = response.status
            assert response.status in ({200} if graph == "alpha" else {200, 404})
            expect(page.get_by_role("heading", name="Article 7", exact=True)).to_be_visible()
            result["steps"].append("direct dynamic route and memoized article")
            page.get_by_role("link", name="Home", exact=True).click()
            expect(page.get_by_role("heading", name="Runtime QA", exact=True)).to_be_visible()
            expect(page.locator("#count")).to_have_text("0")
            page.get_by_role("button", name="Increment", exact=True).click()
            expect(page.locator("#count")).to_have_text("1")
            result["steps"].append("client navigation and backend counter 0→1")
            assert not result["page_errors"], result["page_errors"]
            unexpected_http = [item for item in result["http_errors"]
                               if item["url"] != base_url + "/articles/7?self=1"]
            assert not unexpected_http, unexpected_http
            result["passed"] = True
        except Exception:
            result["failure"] = traceback.format_exc()
            try:
                page.goto(base_url + "/", wait_until="networkidle")
                expect(page.get_by_role("heading", name="Runtime QA", exact=True)).to_be_visible()
                result["root_route_renders"] = True
                expect(page.locator("#count")).to_have_text("0")
                page.get_by_role("button", name="Increment", exact=True).click()
                expect(page.locator("#count")).to_have_text("1")
                result["root_event_passed"] = True
            except Exception:
                result["root_route_failure"] = traceback.format_exc()
        finally:
            result["browser_version"] = browser.version
            result["body"] = page.locator("body").inner_text(timeout=3000)
            save(output / "browser.json", result)
            try:
                page.screenshot(path=str(output / "browser.png"), full_page=True, timeout=5000)
            except Exception as error:
                result["screenshot_error"] = str(error)
                save(output / "browser.json", result)
            context.close()
            browser.close()
    return result


def run_case(args, count: int | None) -> dict:
    """Copy unchanged fixture source and exercise the public production CLI.

    Args:
        args: Parsed lane, source and evidence settings.
        count: Number of dormant States, or None for cookies.

    Returns:
        Startup and browser observations for this case.
    """
    name = f"{args.graph}-{count}" if count is not None else args.graph
    output = args.output / name
    output.mkdir(parents=True, exist_ok=True)
    result = {"lane": args.lane, "graph": args.graph, "extra_states": count, "passed": False}
    with tempfile.TemporaryDirectory(prefix=f"reflex-a4-{args.lane}-", dir="/private/tmp") as temp:
        app_dir = Path(temp) / "app"
        source = args.campaign / ("enterprise/many_states/alpha" if count is not None
                                  else "enterprise/a3/cookies/app")
        shutil.copytree(source, app_dir, ignore=shutil.ignore_patterns(
            ".web", ".states", "reflex.lock", "__pycache__", "*.pyc", "node_modules",
            "requirements.txt", "external"))
        if count is not None:
            (app_dir / "rxconfig.py").write_text(
                'from pathlib import Path\nimport reflex as rx\n'
                'config = rx.Config(app_name="lifecycle_app", frontend_port=3146, '
                'backend_port=3146, api_url="http://localhost:3146", '
                'telemetry_enabled=False, state_manager_mode="disk", '
                f'bun_path=Path("{BUN}"), plugins=[rx.plugins.RadixThemesPlugin()])\n')
        evidence_source = output / "source"
        shutil.copytree(app_dir, evidence_source, dirs_exist_ok=True)
        result["source_hashes"] = {
            str(path.relative_to(app_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in app_dir.rglob("*") if path.is_file()
        }
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env["CI"] = "true"
        env["REFLEX_DIR"] = "/private/tmp/reflex-pre-js-runtime-20261005"
        if count is not None:
            env["QA_EXTRA_STATES"] = str(count)
        base_url = "http://localhost:3146" if count is not None else "http://127.0.0.1:3145"
        command = [UV, "--no-config", "run", "--no-project", "--python", sys.executable,
                   "reflex", "run", "--env", "prod", "--loglevel", "debug"]
        if count is None:
            command.extend(["--frontend-port", "3145", "--backend-port", "3145"])
        result.update({"command": command, "neutral_app": str(app_dir), "ci_bypass": True})
        save(output / "result.json", result)
        with (output / "server.log").open("w") as log:
            process = subprocess.Popen(command, cwd=app_dir, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            try:
                deadline = time.monotonic() + 240
                ready = False
                while process.poll() is None and time.monotonic() < deadline:
                    try:
                        with urllib.request.urlopen(base_url + "/", timeout=1) as response:
                            ready = response.status == 200
                    except (urllib.error.URLError, TimeoutError, ConnectionError):
                        pass
                    if ready:
                        break
                    time.sleep(0.5)
                result["ready"] = ready
                result["startup_exit"] = process.poll()
                save(output / "result.json", result)
                if ready and count is not None:
                    result["browser"] = observe_scale(base_url, output, args.graph)
                    result["passed"] = result["browser"]["passed"]
                elif ready:
                    driver = Path(temp) / "browser.py"
                    shutil.copy2(args.campaign / "enterprise/a3/cookies/browser.py", driver)
                    shutil.copy2(driver, output / "browser.py")
                    probe = subprocess.run(
                        [UV, "--no-config", "run", "--no-project", "--python", sys.executable,
                         "python", str(driver), "--output", str(output)],
                        cwd=temp, env=env, capture_output=True, text=True, timeout=120)
                    (output / "driver.log").write_text(probe.stdout + probe.stderr)
                    result["driver_exit"] = probe.returncode
                    result["browser"] = json.loads((output / "browser.json").read_text())
                    result["passed"] = probe.returncode == 0 and result["browser"]["passed"]
            except Exception:
                result["failure"] = traceback.format_exc()
            finally:
                save(output / "result.json", result)
                stop(process)
                result["stopped_cli_exit"] = process.poll()
                save(output / "result.json", result)
    print(json.dumps({key: result[key] for key in ("lane", "graph", "extra_states", "passed")}), flush=True)
    return result


def main() -> None:
    """Run the specified exploratory cases and retain their partial evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lane", choices=("scale", "cookies"))
    parser.add_argument("--graph", choices=("alpha", "stable"), required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--counts", type=int, nargs="+", default=[1200])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    save(args.output / f"{args.graph}-provenance.json", provenance())
    results = [run_case(args, count) for count in (args.counts if args.lane == "scale" else [None])]
    save(args.output / f"{args.graph}-summary.json", {"cases": results})


if __name__ == "__main__":
    main()

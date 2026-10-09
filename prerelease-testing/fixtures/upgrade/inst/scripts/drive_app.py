r"""Drive a running Reflex app in Chromium and report anomalies.

Loads a page, optionally runs a small action script against it, and captures the four
channels worth watching on every run: console messages, page errors, failed requests, and
4xx/5xx responses. Known-benign dev-server noise is filtered out by default so that a
clean run really means clean.

Run it with the driver venv (playwright installed), not the app's venv:

    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \\
      $SB/envs/driver/bin/python drive_app.py http://localhost:3100/ \\
      --screenshot shots/index.png --report logs/index.json

Actions are JSON, either inline or in a file, applied in order after load:

    [{"click": "text=Increment"},
     {"expect_text": "Count: 1"},
     {"fill": ["input[name=todo]", "buy milk"]},
     {"press": ["input[name=todo]", "Enter"]},
     {"goto": "http://localhost:3100/about"},
     {"wait": 500},
     {"screenshot": "shots/after.png"},
     {"expect_missing": "text=Error"}]

Exit status is 0 when every action succeeded and nothing anomalous was captured, 1
otherwise — so it works directly as a check in a loop.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"

# Dev-server chatter that appears on healthy runs; see references/agent-brief.md.
BENIGN_CONSOLE = [
    re.compile(
        r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"
    ),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def is_benign(text: str) -> bool:
    """Report whether a console message is known dev-server noise.

    Args:
        text: The console message text.

    Returns:
        ``True`` when the message matches a known-benign pattern.
    """
    return any(pattern.search(text) for pattern in BENIGN_CONSOLE)


def load_actions(raw: str | None) -> list[dict]:
    """Parse the action script.

    Args:
        raw: Inline JSON, a path to a JSON file, or ``None``.

    Returns:
        The list of actions to apply, empty when none were given.

    Raises:
        ValueError: The JSON is malformed or is not a list of actions.
    """
    if not raw:
        return []
    try:
        candidate = Path(raw)
        if candidate.is_file():
            raw = candidate.read_text()
    except OSError:
        # Inline JSON longer than the filesystem's filename limit makes the stat itself
        # raise, so treat any path error as "this was not a path".
        pass
    actions = json.loads(raw)
    if not isinstance(actions, list):
        msg = f"expected a JSON list of actions, got {type(actions).__name__}"
        raise ValueError(msg)
    for action in actions:
        # run_action unpacks exactly one (verb, value) pair, so anything else would fail
        # mid-run, after a browser launch and a page load that a caller typo did not earn.
        if not isinstance(action, dict) or len(action) != 1:
            msg = f"each action must be a single-key object, got {action!r}"
            raise ValueError(msg)
    return actions


def run_action(page: Page, action: dict, timeout: int) -> str:
    """Apply one action to the page.

    Args:
        page: The Playwright page to act on.
        action: A single-entry mapping of verb to its argument(s).
        timeout: Per-action timeout in milliseconds.

    Returns:
        A human-readable description of what was done.
    """
    ((verb, value),) = action.items()
    if verb == "click":
        page.click(value, timeout=timeout)
    elif verb == "fill":
        page.fill(value[0], value[1], timeout=timeout)
    elif verb == "press":
        page.press(value[0], value[1], timeout=timeout)
    elif verb == "goto":
        page.goto(value, wait_until="networkidle", timeout=timeout)
    elif verb == "wait":
        page.wait_for_timeout(value)
    elif verb == "wait_for":
        page.wait_for_selector(value, timeout=timeout)
    elif verb == "expect_text":
        page.wait_for_selector(f"text={value}", timeout=timeout)
    elif verb == "expect_missing":
        page.wait_for_selector(value, state="detached", timeout=timeout)
    elif verb == "screenshot":
        Path(value).parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=value, full_page=True)
    elif verb == "eval":
        return f"eval -> {page.evaluate(value)!r}"
    else:
        msg = f"unknown action {verb!r}"
        raise ValueError(msg)
    return f"{verb}: {value!r}"


def try_action(page: Page, action: dict, timeout: int) -> tuple[str | None, str | None]:
    """Run one action, turning a failure into a value rather than an exception.

    Reporting the failure this way keeps the record of the actions that already
    succeeded, which is usually the most useful part of a failed run.

    Args:
        page: The Playwright page to act on.
        action: A single-entry mapping of verb to its argument(s).
        timeout: Per-action timeout in milliseconds.

    Returns:
        A ``(description, error)`` tuple; exactly one side is set.
    """
    try:
        return run_action(page, action, timeout), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def main() -> int:
    """Drive the app and print a report.

    Returns:
        ``0`` when the run was clean, ``1`` when anything anomalous was captured.
    """
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="page to load, e.g. http://localhost:3100/")
    parser.add_argument("--actions", help="JSON list of actions, inline or a file path")
    parser.add_argument(
        "--screenshot", help="path for a screenshot after the actions run"
    )
    parser.add_argument("--report", help="path to write the full JSON report to")
    parser.add_argument(
        "--timeout", type=int, default=15000, help="per-action timeout in ms"
    )
    parser.add_argument(
        "--settle", type=int, default=1500, help="ms to wait after load for hydration"
    )
    parser.add_argument(
        "--headed", action="store_true", help="run with a visible browser"
    )
    parser.add_argument(
        "--all-console", action="store_true", help="do not filter benign console noise"
    )
    args = parser.parse_args()

    try:
        actions = load_actions(args.actions)
    except ValueError as exc:
        # Parsing after the browser is up spends a launch and a page load before failing,
        # and leaves a traceback where the report should be. A malformed --actions is a
        # usage error, so say so up front and exit with the documented failure status.
        print(f"INVALID --actions: {exc}", file=sys.stderr)
        return 1

    console: list[dict] = []
    page_errors: list[str] = []
    failed: list[dict] = []
    bad_status: list[dict] = []
    performed: list[str] = []
    action_error: str | None = None
    load_error: str | None = None
    screenshot_error: str | None = None
    read_error: str | None = None

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, headless=not args.headed)
        page = browser.new_context().new_page()
        page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.on(
            "requestfailed",
            lambda r: failed.append({"url": r.url, "failure": str(r.failure)}),
        )
        page.on(
            "response",
            lambda r: (
                bad_status.append({"url": r.url, "status": r.status})
                if r.status >= 400
                else None
            ),
        )

        try:
            page.goto(args.url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(args.settle)
        except Exception as exc:
            # A server that never came up is the most common failure here, and it still
            # deserves a report and the documented exit status rather than a traceback.
            load_error = f"{type(exc).__name__}: {exc}"

        for action in [] if load_error else actions:
            done, action_error = try_action(page, action, args.timeout)
            if done is not None:
                performed.append(done)
            if action_error:
                break

        if performed or action_error:
            # Playwright returns as soon as an action's own wait resolves, but the
            # resulting state update, network call and any error it triggers land after
            # that; without this the last action's fallout is invisible to the report.
            # A failed action counts: the click that raised on its assertion may still
            # have reached the server, and that response is often the whole finding.
            try:
                page.wait_for_timeout(args.settle)
            except Exception as exc:
                # An action can close the page or navigate it away. That is an anomaly to
                # record, not a reason to abandon the report the caller is waiting on.
                action_error = action_error or f"{type(exc).__name__}: {exc}"

        try:
            title = page.title()
            body = page.inner_text("body")[:2000]
        except Exception as exc:
            # Never fold this into the body text alone: a page that cannot be read is a
            # run that inspected nothing, and reporting that as clean is the one result
            # this driver must never produce.
            title, body = "", f"<unreadable: {type(exc).__name__}>"
            read_error = f"{type(exc).__name__}: {exc}"
        if args.screenshot:
            try:
                Path(args.screenshot).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=args.screenshot, full_page=True)
            except Exception as exc:
                # A closed page, or a destination that cannot be created. Either way a
                # missing screenshot must not cost the report.
                screenshot_error = f"{type(exc).__name__}: {exc}"
        browser.close()

    shown = (
        console
        if args.all_console
        else [m for m in console if not is_benign(m["text"])]
    )
    problems = [m for m in shown if m["type"] in ("error", "warning")]
    clean = not (
        problems
        or page_errors
        or failed
        or bad_status
        or action_error
        or load_error
        or screenshot_error
        or read_error
    )

    report = {
        "url": args.url,
        "title": title,
        "clean": clean,
        "load_error": load_error,
        "actions_performed": performed,
        "action_error": action_error,
        "screenshot_error": screenshot_error,
        "read_error": read_error,
        "console": shown,
        "page_errors": page_errors,
        "failed_requests": failed,
        "http_4xx_5xx": bad_status,
        "body_text": body,
    }
    if args.report:
        try:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps(report, indent=2))
        except OSError as exc:
            # Losing the file must not also lose the findings: the summary below is
            # printed either way. It must not be reported as a pass either — a caller
            # that asked for a report and got none has no result to trust.
            print(f"  REPORT NOT WRITTEN: {exc}", file=sys.stderr)
            clean = False

    if load_error:
        print(f"  LOAD FAILED: {load_error}")
    print(f"TITLE: {title}")
    print(f"BODY:  {body[:300].replace(chr(10), ' | ')}")
    for item in performed:
        print(f"  did  {item}")
    if action_error:
        print(f"  ACTION FAILED: {action_error}")
    if read_error:
        print(f"  PAGE UNREADABLE: {read_error}")
    if screenshot_error:
        print(f"  SCREENSHOT FAILED: {screenshot_error}")
    for m in shown:
        print(f"  [{m['type']}] {m['text'][:300]}")
    for e in page_errors:
        print(f"  PAGE ERROR: {e[:300]}")
    for f in failed:
        print(f"  REQUEST FAILED: {f['url']} ({f['failure']})")
    for b in bad_status:
        print(f"  HTTP {b['status']}: {b['url']}")
    print("RESULT:", "clean" if clean else "ANOMALIES FOUND")
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())

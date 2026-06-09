"""Conftest for Playwright integration tests.

Records browser-side activity (console messages, page errors, websocket
frames) for each test's page and attaches it to the test report on failure,
so CI logs contain enough context to diagnose flaky frontend behavior
post-mortem.
"""

import time

import pytest

# Cap recorded entries per test so a chatty page can't bloat memory or logs.
_MAX_DIAGNOSTIC_ENTRIES = 500
_MAX_ENTRY_LENGTH = 300


@pytest.fixture(autouse=True)
def _page_diagnostics(request):
    """Capture console/pageerror/websocket activity from the ``page`` fixture.

    Args:
        request: The pytest fixture request object.

    Yields:
        Control to the test function.
    """
    if "page" not in request.fixturenames:
        yield
        return
    page = request.getfixturevalue("page")
    log: list[str] = []
    t0 = time.monotonic()

    def stamp(message: str) -> None:
        if len(log) < _MAX_DIAGNOSTIC_ENTRIES:
            log.append(f"+{time.monotonic() - t0:.3f}s {message[:_MAX_ENTRY_LENGTH]}")

    page.on("console", lambda msg: stamp(f"console.{msg.type}: {msg.text}"))
    page.on("pageerror", lambda exc: stamp(f"pageerror: {exc}"))

    def _on_websocket(ws) -> None:
        stamp(f"ws open: {ws.url}")
        ws.on("framesent", lambda frame: stamp(f"ws sent: {frame}"))
        ws.on("framereceived", lambda frame: stamp(f"ws recv: {frame}"))
        ws.on("close", lambda _ws: stamp("ws close"))

    page.on("websocket", _on_websocket)
    request.node._page_diagnostics = log
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Attach recorded page diagnostics to failed (or rerun) call reports.

    Args:
        item: The test item being reported on.
        call: The call info for the current test phase.

    Yields:
        Control to other report hooks.
    """
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not (report.failed or report.outcome == "rerun"):
        return
    log = getattr(item, "_page_diagnostics", None)
    if log:
        report.sections.append((f"page diagnostics ({report.outcome})", "\n".join(log)))

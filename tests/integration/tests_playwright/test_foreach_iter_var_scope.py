"""Integration test for the "c_rx_state_ is not defined" runtime ReferenceError.

A snapshot-boundary component (e.g. ``rx.upload.root``) placed inside an
``rx.foreach`` carries internal React hooks (``useDropzone``, ``useCallback``)
whose Var arguments reference the foreach iter var. The current compiler
collects these via ``_get_all_hooks`` and emits them at the top of the
generated snapshot memo body — above the ``.map`` callback that introduces
the iter var name into scope. The browser hits a ``ReferenceError`` the
moment the memo component renders.

This integration test loads such a page and fails if any
``ReferenceError`` whose message names a foreach iter var (``*_rx_state_``)
reaches the browser console. Marked xfail until the compiler either:
- wraps the foreach body in a per-iteration memo so the hook lives at that
  component's top level with the iter var threaded as a prop, OR
- refuses the pattern at compile time with a clear, actionable error.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ForeachIterVarScopeApp():
    """App with rx.upload.root inside rx.foreach (closes over iter var)."""
    import reflex as rx

    class IterVarState(rx.State):
        rows: list[dict[str, str]] = [
            {"id": "row-1", "label": "Alpha"},
            {"id": "row-2", "label": "Bravo"},
        ]

    def index():
        return rx.el.main(
            rx.el.h1("foreach + upload regression", id="title"),
            rx.foreach(
                IterVarState.rows,
                lambda c: rx.el.div(
                    rx.el.span(c["label"]),
                    # rx.upload.root is a MemoizationLeaf snapshot boundary
                    # whose internal useDropzone hook embeds the ``id`` prop's
                    # value. With ``id=c["id"]`` the hook line references the
                    # foreach iter var, which only exists inside the .map
                    # callback the outer snapshot memo body generates.
                    rx.upload.root(
                        rx.el.div("Drop here"),
                        id=c["id"],
                    ),
                ),
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def foreach_iter_var_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Run the ForeachIterVarScopeApp under an AppHarness.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        The running harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("foreach_iter_var_scope"),
        app_source=ForeachIterVarScopeApp,
    ) as harness:
        yield harness


@pytest.mark.xfail(
    reason=(
        "Bug: snapshot-boundary component (rx.upload.root) inside rx.foreach "
        "hoists its hooks above the .map callback, so the iter var (e.g. "
        "c_rx_state_) is undefined at hook-eval time and the page crashes "
        "with ReferenceError before mounting. Fix should wrap the foreach "
        "body in a per-iteration memo or reject the pattern at compile time."
    ),
    strict=True,
)
def test_no_iter_var_reference_error(
    foreach_iter_var_app: AppHarness, page: Page
) -> None:
    """Loading the page must not throw ``ReferenceError`` for an iter var.

    Args:
        foreach_iter_var_app: Running app harness.
        page: Playwright page.
    """
    assert foreach_iter_var_app.frontend_url is not None

    iter_var_errors: list[str] = []

    def _record_pageerror(exc: Exception) -> None:
        message = str(exc)
        if "_rx_state_" in message and "is not defined" in message:
            iter_var_errors.append(message)

    def _record_console(msg) -> None:  # type: ignore[no-untyped-def]
        if msg.type != "error":
            return
        text = msg.text
        if "_rx_state_" in text and "is not defined" in text:
            iter_var_errors.append(text)

    page.on("pageerror", _record_pageerror)
    page.on("console", _record_console)

    page.goto(foreach_iter_var_app.frontend_url)
    # The title only renders once the page bundle executes; if a top-of-memo
    # hook throws ReferenceError the React tree never mounts and this locator
    # times out (also acceptable as a failure mode for the regression).
    expect(page.locator("#title")).to_have_text("foreach + upload regression")

    assert not iter_var_errors, (
        "Foreach iter var leaked outside its .map() scope at runtime. "
        "Captured browser errors:\n  - " + "\n  - ".join(iter_var_errors)
    )

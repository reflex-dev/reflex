"""Test that the frontend dev server starts on an install without Node."""

import os
import shutil
from collections.abc import Generator

import httpx
import pytest

import reflex.testing as reflex_testing
from reflex.testing import AppHarness
from reflex.utils import js_runtimes, path_ops
from reflex.utils.exec import _DEV_CONDITION_FLAG


def NodelessApp():
    """App whose only requirement is that the dev server serves its page."""
    import reflex as rx

    def index():
        return rx.text("nodeless frontend is up")

    app = rx.App()
    app.add_page(index)


def _path_without_node() -> str:
    """Build a PATH with every directory that provides `node` removed.

    Returns:
        The PATH value with node-providing directories filtered out.
    """
    return os.pathsep.join(
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and shutil.which("node", path=entry) is None
    )


@pytest.fixture(scope="module")
def nodeless_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start NodelessApp with `node` unavailable, as on a bun-only install.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture.

    Yields:
        The running AppHarness.
    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("PATH", _path_without_node())
        if shutil.which("node") is not None:
            pytest.skip("node is still resolvable after filtering it off PATH")
        if path_ops.get_bun_path() is None:
            pytest.skip("bun is unavailable once node is off PATH")
        # The node probe is cached per process, so an earlier test may have
        # found node; it is off PATH now.
        monkeypatch.setattr(js_runtimes, "get_node_version", lambda: None)
        # Drop the `development` condition Reflex puts in the dev server's
        # environment. Bun applies neither NODE_OPTIONS nor BUN_OPTIONS to the
        # process it spawns for a package script, so node-less installs never
        # had that assist -- the condition has to reach bun as a flag on the
        # dev server command.
        monkeypatch.setattr(reflex_testing, "_with_development_condition", dict)
        harness = AppHarness.create(
            root=tmp_path_factory.mktemp("nodeless_app"), app_source=NodelessApp
        )
        # Started outside the `with` form on purpose: `__enter__` *is* `start()`,
        # so a failure to bring the frontend up skips `__exit__` and leaks the
        # backend thread, which then keeps the interpreter alive. This test
        # fails precisely that way, so it has to stop the harness itself.
        try:
            harness.start()
            yield harness
        finally:
            harness.stop()


def test_nodeless_frontend_serves(nodeless_app: AppHarness):
    """The dev server starts and serves a page with no Node installed.

    `react-router dev` needs the `development` export condition and relaunches
    itself to enable it. Bun runs the CLI here and ignores the condition in the
    environment, and on Windows the relaunched process does not apply it
    either, so the CLI relaunches a second time, trips its own restart guard,
    and the frontend never comes up. Reflex has to hand bun the condition as a
    flag up front.

    Args:
        nodeless_app: The harness running without node on PATH.
    """
    assert nodeless_app.frontend_process is not None
    args = nodeless_app.frontend_process.args
    assert isinstance(args, list)
    assert _DEV_CONDITION_FLAG in args
    assert nodeless_app.frontend_url is not None
    response = httpx.get(nodeless_app.frontend_url, timeout=60)
    assert response.status_code == 200
    # The page is hydrated client-side, so assert on the react-router document
    # the dev server rendered rather than on the app's own text.
    assert "__reactRouterContext" in response.text

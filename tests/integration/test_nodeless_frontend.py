"""Test that the frontend starts on installs where bun, not node, is the runtime."""

import contextlib
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn
from urllib.parse import urljoin

import httpx
import pytest
from packaging import version
from reflex_base import constants

import reflex.testing as reflex_testing
from reflex.testing import AppHarness, AppHarnessProd
from reflex.utils import js_runtimes, path_ops
from reflex.utils.exec import _DEV_CONDITION_FLAG

_APP_TEXT = "nodeless frontend is up"


def NodelessApp():
    """App whose only requirement is that the frontend serves its page."""
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


def _require(reason: str) -> NoReturn:
    """Skip a scenario whose runtime is missing, or fail the job that requires it.

    Args:
        reason: Why the scenario cannot run.
    """
    if os.environ.get("REQUIRE_BUN_NODELESS_TEST") == "true":
        pytest.fail(reason)
    pytest.skip(reason)


@pytest.fixture(params=["nodeless", "outdated_node"])
def bun_runtime(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Set up an environment where bun is the frontend runtime.

    `nodeless` drops node from PATH, as on a bun-only install. `outdated_node`
    keeps an unsupported node on PATH, which bun has to take over from.

    Args:
        request: The pytest request carrying the scenario name.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The bun executable Reflex runs the frontend with.
    """
    monkeypatch.delenv("REFLEX_USE_NPM", raising=False)
    node_version = None
    if request.param == "nodeless":
        monkeypatch.setenv("PATH", _path_without_node())
        if shutil.which("node") is not None:
            _require("node is still resolvable after filtering it off PATH")
    else:
        node_version = js_runtimes._get_version_of_executable(path_ops.get_node_path())
        if node_version is None:
            _require("node is not installed")
        if node_version >= version.parse(constants.Node.MIN_VERSION):
            _require(f"node {node_version} is supported, not outdated")
    bun_path = path_ops.get_bun_path()
    if bun_path is None:
        _require("bun is not installed")
    # The node probe is cached once per process, possibly under another PATH.
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: node_version)
    # Reflex picks bun, and forces it over an outdated node with `--bun`.
    assert js_runtimes.get_js_package_executor()[0] == [
        str(bun_path),
        *(["--bun"] if node_version else []),
    ]
    return bun_path


@contextlib.contextmanager
def _started(harness_cls: type[AppHarness], root: Path) -> Iterator[AppHarness]:
    """Run NodelessApp in a harness that is stopped even when it fails to start.

    `__enter__` *is* `start()`, so a failure to bring the frontend up skips
    `__exit__` and leaks the backend thread, which then keeps the interpreter
    alive.

    Args:
        harness_cls: The harness class that runs the app.
        root: The directory to create the app in.

    Yields:
        The running harness.
    """
    harness = harness_cls.create(root=root, app_source=NodelessApp)
    try:
        harness.start()
        yield harness
    finally:
        harness.stop()


def test_dev_frontend_serves(
    bun_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
):
    """The dev server starts and compiles the page with bun as the runtime.

    `react-router dev` needs the `development` export condition and relaunches
    itself to enable it. Bun runs the CLI here and ignores the condition in the
    environment, and on Windows the relaunched process does not apply it
    either, so the CLI relaunches a second time, trips its own restart guard,
    and the frontend never comes up. Reflex has to hand bun the condition as a
    flag up front.

    Args:
        bun_runtime: The bun executable the scenario runs the frontend with.
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path_factory: The pytest temporary path factory.
    """
    # Drop the `development` condition Reflex puts in the dev server's
    # environment. Bun applies neither NODE_OPTIONS nor BUN_OPTIONS to the
    # process it spawns for a package script, so the condition has to reach
    # bun as a flag on the dev server command.
    monkeypatch.setattr(reflex_testing, "_with_development_condition", dict)
    with _started(AppHarness, tmp_path_factory.mktemp("nodeless_app")) as harness:
        assert harness.frontend_process is not None
        args = harness.frontend_process.args
        assert isinstance(args, list)
        assert args[:2] == [str(bun_runtime), _DEV_CONDITION_FLAG]
        assert harness.frontend_url is not None
        document = httpx.get(harness.frontend_url, timeout=60)
        assert document.status_code == 200
        assert "window.__reactRouterContext" in document.text
        # The page renders client-side, so check the route module the dev
        # server compiles for it.
        route = httpx.get(
            urljoin(harness.frontend_url, "/app/routes/_index.jsx"), timeout=60
        )
        assert route.status_code == 200
        assert _APP_TEXT in route.text


@pytest.mark.usefixtures("bun_runtime")
def test_prod_frontend_serves(tmp_path_factory: pytest.TempPathFactory):
    """The production build runs and serves the page with bun as the runtime.

    Args:
        tmp_path_factory: The pytest temporary path factory.
    """
    with _started(AppHarnessProd, tmp_path_factory.mktemp("nodeless_app")) as harness:
        assert harness.frontend_url is not None
        response = httpx.get(harness.frontend_url, timeout=60)
        assert response.status_code == 200
        assert _APP_TEXT in response.text

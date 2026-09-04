"""Tests for development backend launchers in ``reflex.utils.exec``."""

import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from reflex_base.environment import environment

from reflex.utils import exec as exec_utils
from reflex.utils.precompressed_staticfiles import PrecompressedStaticFiles

DEV_BACKEND_RELOAD_ENV_NAME = environment.REFLEX_DEV_BACKEND_RELOAD_ACTIVE.name


def test_run_uvicorn_backend_sets_reload_env_var_and_clears_marker(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """``run_uvicorn_backend`` initializes reload worker process context."""
    marker = tmp_path / exec_utils.DEV_BACKEND_RELOAD_MARKER
    marker.touch()
    monkeypatch.delenv(DEV_BACKEND_RELOAD_ENV_NAME, raising=False)
    mocker.patch.object(
        exec_utils, "get_dev_backend_reload_marker", return_value=marker
    )
    mocker.patch.object(exec_utils, "get_app_instance", return_value="app:app")
    mocker.patch.object(exec_utils, "get_reload_paths", return_value=[])

    seen: dict[str, str | None] = {}

    def fake_run(*_args, **_kwargs):
        seen["value"] = os.environ.get(DEV_BACKEND_RELOAD_ENV_NAME)
        assert not marker.exists()

    uvicorn = pytest.importorskip("uvicorn")
    mocker.patch.object(uvicorn, "run", side_effect=fake_run)

    exec_utils.run_uvicorn_backend(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    assert seen["value"] == "True"


def test_run_granian_backend_sets_reload_env_var_and_clears_marker(
    tmp_path: Path, mocker: MockerFixture, monkeypatch: pytest.MonkeyPatch
):
    """``run_granian_backend`` initializes reload worker process context."""
    marker = tmp_path / exec_utils.DEV_BACKEND_RELOAD_MARKER
    marker.touch()
    monkeypatch.delenv(DEV_BACKEND_RELOAD_ENV_NAME, raising=False)
    mocker.patch.object(
        exec_utils, "get_dev_backend_reload_marker", return_value=marker
    )
    mocker.patch.object(
        exec_utils, "get_app_instance_from_file", return_value="app:app"
    )
    mocker.patch.object(exec_utils, "get_reload_paths", return_value=[])

    seen: dict[str, str | None] = {}

    granian_server = pytest.importorskip("granian.server")

    class FakeGranian:
        def __init__(self, *_args, **_kwargs):
            seen["value"] = os.environ.get(DEV_BACKEND_RELOAD_ENV_NAME)
            assert not marker.exists()

        def on_reload(self, _callback):
            pass

        def serve(self):
            pass

    mocker.patch.object(granian_server, "Server", FakeGranian)

    exec_utils.run_granian_backend(
        host="0.0.0.0", port=8000, loglevel=exec_utils.LogLevel.INFO
    )

    assert seen["value"] == "True"


def test_with_development_condition_sets_node_and_bun_options():
    """Both runtime option vars gain the development condition flag."""
    env = exec_utils._with_development_condition({})
    assert env["NODE_OPTIONS"] == "--conditions=development"
    assert env["BUN_OPTIONS"] == "--conditions=development"


def test_with_development_condition_preserves_existing_options():
    """Existing runtime options are kept, the flag is appended once, and the
    base environment is not mutated.
    """
    environ = {
        "NODE_OPTIONS": "--max-old-space-size=4096",
        "BUN_OPTIONS": "--conditions=development",
    }
    env = exec_utils._with_development_condition(environ)
    assert env["NODE_OPTIONS"] == "--max-old-space-size=4096 --conditions=development"
    # Already-present flag is not duplicated.
    assert env["BUN_OPTIONS"] == "--conditions=development"
    # The dev condition must not leak into the parent environment.
    assert environ["NODE_OPTIONS"] == "--max-old-space-size=4096"


def test_arbitrate_ssr_stores_flag_when_env_unset(monkeypatch: pytest.MonkeyPatch):
    """The flag value is stored in the environment when REFLEX_SSR is unset."""
    monkeypatch.setenv(environment.REFLEX_SSR.name, "")

    assert exec_utils.arbitrate_ssr(False) is False
    assert environment.REFLEX_SSR.get() is False


def test_arbitrate_ssr_env_var_wins(monkeypatch: pytest.MonkeyPatch):
    """An already-set REFLEX_SSR env var overrides the flag value."""
    monkeypatch.setenv(environment.REFLEX_SSR.name, "False")

    assert exec_utils.arbitrate_ssr(True) is False


def test_get_routes_manifest_router_missing_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Return None when no routes manifest has been written."""
    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    assert exec_utils.get_routes_manifest_router() is None


def test_get_routes_manifest_router_invalid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Return None when the routes manifest is not valid JSON."""
    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    (tmp_path / "routes.json").write_text("not valid json{")
    assert exec_utils.get_routes_manifest_router() is None


def test_get_routes_manifest_router_matches_dynamic_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Build a matcher from the manifest that resolves dynamic routes."""
    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    (tmp_path / "routes.json").write_text(
        '["index", "articles/[id]", "posts/[[...splat]]", "404"]'
    )

    router = exec_utils.get_routes_manifest_router()

    assert router is not None
    assert router("/") == "index"
    assert router("/articles/7") == "articles/[id]"
    assert router("/posts/a/b") == "posts/[[...splat]]"
    assert router("/definitely-not-a-page") is None


def test_get_frontend_mount_builds_router_from_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The frontend mount picks up the routes manifest when no router is given."""
    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    (tmp_path / "build" / "client").mkdir(parents=True)
    (tmp_path / "routes.json").write_text('["index", "articles/[id]"]')

    mount = exec_utils.get_frontend_mount()

    static_files = mount.app
    assert isinstance(static_files, PrecompressedStaticFiles)
    router = static_files._router
    assert router is not None
    assert router("/articles/7") == "articles/[id]"
    assert router("/missing") is None


def test_get_frontend_mount_router_respects_frontend_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The mount-relative path is matched with the frontend path restored."""
    from reflex_base.config import get_config

    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    monkeypatch.setattr(get_config(), "frontend_path", "/sub")
    (tmp_path / "build" / "client" / "sub").mkdir(parents=True)
    (tmp_path / "routes.json").write_text('["index", "articles/[id]"]')

    mount = exec_utils.get_frontend_mount()

    static_files = mount.app
    assert isinstance(static_files, PrecompressedStaticFiles)
    router = static_files._router
    assert router is not None
    assert router("/articles/7") == "articles/[id]"
    assert router("/") == "index"
    assert router("/missing") is None


def test_get_frontend_mount_router_excludes_synthetic_404_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A literal /404 request stays a 404 despite the compiled 404 page route."""
    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    (tmp_path / "build" / "client").mkdir(parents=True)
    (tmp_path / "routes.json").write_text('["index", "articles/[id]", "404"]')

    mount = exec_utils.get_frontend_mount()

    static_files = mount.app
    assert isinstance(static_files, PrecompressedStaticFiles)
    router = static_files._router
    assert router is not None
    assert router("/404") is None
    assert router("/404/") is None
    assert router("/articles/7") == "articles/[id]"


def test_get_frontend_mount_explicit_router_excludes_synthetic_404_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An explicitly passed app router is also filtered for the 404 page route."""
    from reflex.route import get_router

    monkeypatch.setenv(environment.REFLEX_WEB_WORKDIR.name, str(tmp_path))
    (tmp_path / "build" / "client").mkdir(parents=True)

    mount = exec_utils.get_frontend_mount(
        router=get_router(["index", "articles/[id]", "404"])
    )

    static_files = mount.app
    assert isinstance(static_files, PrecompressedStaticFiles)
    router = static_files._router
    assert router is not None
    assert router("/404") is None
    assert router("/articles/7") == "articles/[id]"

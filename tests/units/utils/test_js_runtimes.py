"""Tests for reflex.utils.js_runtimes install gating."""

from pathlib import Path
from unittest import mock

import pytest

from reflex.utils import js_runtimes


@pytest.fixture
def install_mocks(monkeypatch):
    """Replace every side effect of install_frontend_packages with recorders.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A dict of recorder lists keyed by side-effect name.
    """
    calls: dict[str, list] = {
        "sync_to_web": [],
        "install": [],
        "drop": [],
        "sync_to_root": [],
    }
    monkeypatch.setattr(
        js_runtimes,
        "_sync_root_lockfiles_for_frontend_install",
        lambda: calls["sync_to_web"].append(1),
    )
    monkeypatch.setattr(
        js_runtimes,
        "_install_frontend_packages",
        lambda *args: calls["install"].append(args),
    )
    monkeypatch.setattr(
        js_runtimes,
        "_drop_lockfile_of_other_package_manager",
        lambda manager: calls["drop"].append(manager),
    )
    monkeypatch.setattr(
        js_runtimes.frontend_skeleton,
        "sync_web_lockfiles_to_root",
        lambda: calls["sync_to_root"].append(1),
    )
    return calls


def _fake_config() -> mock.Mock:
    """Build a minimal config for install_frontend_packages.

    Returns:
        A mock config with no plugins and frozen lockfile installs.
    """
    return mock.Mock(plugins=[], frozen_lockfile=True)


def _patch_manager_paths(monkeypatch, bun: bool, npm: bool) -> None:
    """Point package-manager discovery at fake executables.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        bun: Whether bun is discoverable.
        npm: Whether npm is discoverable.
    """
    monkeypatch.setattr(
        js_runtimes.path_ops,
        "get_bun_path",
        lambda: Path("/usr/bin/bun") if bun else None,
    )
    monkeypatch.setattr(
        js_runtimes.path_ops,
        "get_npm_path",
        lambda: Path("/usr/bin/npm") if npm else None,
    )


def _patch_unsupported_node(monkeypatch) -> None:
    """Make the node version check fail with no detected version.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(js_runtimes, "check_node_version", lambda: False)
    monkeypatch.setattr(js_runtimes, "get_node_version", lambda: None)


def test_install_never_starts_with_unsupported_node(monkeypatch, install_mocks):
    """A failed node-version preflight must leave no lockfile side effects.

    Regression test for #6976: an npm install that the run later rejects
    persisted npm lockfile state into reflex.lock/, silently switching the
    project to npm and breaking later bun runs.
    """
    monkeypatch.setattr(js_runtimes, "prefer_npm_over_bun", lambda: True)
    _patch_manager_paths(monkeypatch, bun=True, npm=True)
    _patch_unsupported_node(monkeypatch)

    with pytest.raises(SystemExit):
        js_runtimes.install_frontend_packages({"react"}, _fake_config())

    assert install_mocks["sync_to_web"] == [], "lockfiles were synced to .web"
    assert install_mocks["install"] == [], "npm install ran despite the gate"
    assert install_mocks["sync_to_root"] == [], "lockfiles were persisted"


def test_install_gates_npm_selected_as_fallback(monkeypatch, install_mocks):
    """The fallback to npm is gated the same way as explicit npm.

    The gate must key on the manager that will actually run, not on the
    npm preference flag: with bun missing, selection falls back to npm
    while prefer_npm_over_bun() stays False.
    """
    monkeypatch.setattr(js_runtimes, "prefer_npm_over_bun", lambda: False)
    _patch_manager_paths(monkeypatch, bun=False, npm=True)
    _patch_unsupported_node(monkeypatch)

    with pytest.raises(SystemExit):
        js_runtimes.install_frontend_packages({"react"}, _fake_config())

    assert install_mocks["sync_to_web"] == [], "lockfiles were synced to .web"
    assert install_mocks["install"] == [], "npm install ran despite the gate"
    assert install_mocks["sync_to_root"] == [], "lockfiles were persisted"


def test_install_proceeds_with_supported_node(monkeypatch, install_mocks):
    """The gate does not block npm installs when the node version is supported."""
    monkeypatch.setattr(js_runtimes, "prefer_npm_over_bun", lambda: True)
    _patch_manager_paths(monkeypatch, bun=True, npm=True)
    monkeypatch.setattr(js_runtimes, "check_node_version", lambda: True)

    js_runtimes.install_frontend_packages({"react"}, _fake_config())

    assert install_mocks["install"] != [], "install did not run"
    assert install_mocks["sync_to_root"] != [], "lockfiles were not persisted"


def test_install_ignores_node_version_under_bun(monkeypatch, install_mocks):
    """The bun path never gated on node version and still does not."""
    monkeypatch.setattr(js_runtimes, "prefer_npm_over_bun", lambda: False)
    _patch_manager_paths(monkeypatch, bun=True, npm=True)
    _patch_unsupported_node(monkeypatch)

    js_runtimes.install_frontend_packages({"react"}, _fake_config())

    assert install_mocks["install"] != [], "bun install was blocked"


def test_validate_gates_npm_selected_as_fallback(monkeypatch):
    """Run-time validation rejects old node when npm is the selected manager."""
    monkeypatch.setattr(js_runtimes, "prefer_npm_over_bun", lambda: False)
    _patch_manager_paths(monkeypatch, bun=False, npm=True)
    _patch_unsupported_node(monkeypatch)

    with pytest.raises(SystemExit):
        js_runtimes.validate_frontend_dependencies()


def test_validate_does_not_gate_bun(monkeypatch):
    """Run-time validation stays node-agnostic while bun is selected."""
    monkeypatch.setattr(js_runtimes, "prefer_npm_over_bun", lambda: False)
    _patch_manager_paths(monkeypatch, bun=True, npm=True)
    _patch_unsupported_node(monkeypatch)

    js_runtimes.validate_frontend_dependencies()

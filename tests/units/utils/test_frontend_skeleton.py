"""Tests for frontend dependency manifest synchronization."""

import json

import pytest

from reflex.utils import frontend_skeleton, js_runtimes


@pytest.fixture
def package_files(tmp_path, monkeypatch):
    """Create persisted and rendered package manifests with isolated paths.

    Returns:
        The frontend directory and persisted package manifest path.
    """
    web = tmp_path / ".web"
    root = tmp_path / "reflex.lock"
    web.mkdir()
    root.mkdir()
    monkeypatch.setattr(frontend_skeleton, "get_web_dir", lambda: web)
    monkeypatch.setattr(js_runtimes, "get_web_dir", lambda: web)
    monkeypatch.setattr(
        frontend_skeleton, "get_root_lockfile_path", lambda name: root / name
    )
    manifest = root / "package.json"
    manifest.write_text(
        json.dumps({"dependencies": {"react": "19.2.8"}, "custom": True})
    )
    (web / "package.json").write_text(frontend_skeleton._compile_package_json())
    return web, manifest


@pytest.mark.parametrize("sorted_keys", [False, True])
def test_package_formatting_preserves_install_cache(package_files, sorted_keys):
    """Package manager whitespace/key formatting must not invalidate installed dependencies."""
    web, _ = package_files
    package = web / "package.json"
    formatted = (
        json.dumps(json.loads(package.read_text()), indent=2, sort_keys=sorted_keys)
        + "\n"
    )
    package.write_text(formatted)
    marker = web / "reflex.install_frontend_packages.cached"
    marker.write_bytes(b"unchanged install cache")
    before = package.stat().st_mtime_ns

    assert frontend_skeleton.sync_root_package_json_to_web() is False
    js_runtimes._sync_root_lockfiles_for_frontend_install()

    assert package.read_text() == formatted
    assert package.stat().st_mtime_ns == before
    assert marker.read_bytes() == b"unchanged install cache"


@pytest.mark.parametrize("value", [False, 1, "true", [True]])
def test_package_value_changes_invalidate(package_files, value):
    """Manifest changes remain significant, including JSON boolean versus number types."""
    web, manifest = package_files
    data = json.loads(manifest.read_text())
    data["custom"] = value
    manifest.write_text(json.dumps(data))
    assert frontend_skeleton.sync_root_package_json_to_web() is True
    assert type(json.loads((web / "package.json").read_text())["custom"]) is type(value)


def test_invalid_rendered_package_is_repaired(package_files):
    """Malformed generated package JSON must not be treated as a formatting-only change."""
    web, _ = package_files
    (web / "package.json").write_text("{bad json")
    assert frontend_skeleton.sync_root_package_json_to_web() is True
    assert json.loads((web / "package.json").read_text())["custom"] is True

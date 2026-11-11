"""Tests for frontend package manifest synchronization."""

import json
from pathlib import Path

import pytest
from reflex_base import constants

from reflex.utils import frontend_skeleton


@pytest.fixture
def package_json_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create isolated persisted and rendered package manifests.

    Args:
        tmp_path: Temporary app directory.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        The rendered package.json path.
    """
    monkeypatch.chdir(tmp_path)
    web_dir = tmp_path / constants.Dirs.WEB
    web_dir.mkdir()
    monkeypatch.setattr(frontend_skeleton, "get_web_dir", lambda: web_dir)
    root_package = frontend_skeleton.get_root_lockfile_path(constants.PackageJson.PATH)
    root_package.parent.mkdir()
    root_package.write_text(
        json.dumps({"dependencies": {"test-pkg": "1.0.0"}, "description": "Test app"})
    )
    package_path = web_dir / constants.PackageJson.PATH
    package_path.write_text(frontend_skeleton._compile_package_json())
    return package_path


@pytest.mark.parametrize(
    ("indent", "sort_keys", "newline"),
    [(None, False, ""), (2, False, "\n"), (None, True, ""), (2, True, "\n")],
)
def test_sync_root_package_json_ignores_formatting(
    package_json_path: Path, indent: int | None, sort_keys: bool, newline: str
):
    """Formatting and key order changes preserve the existing file.

    Args:
        package_json_path: The rendered package.json path.
        indent: JSON indentation used by the package manager.
        sort_keys: Whether to reorder JSON object keys.
        newline: Trailing whitespace added by the package manager.
    """
    formatted = (
        json.dumps(
            json.loads(package_json_path.read_text()),
            indent=indent,
            sort_keys=sort_keys,
        )
        + newline
    )
    package_json_path.write_text(formatted)
    frontend_skeleton.sync_web_lockfiles_to_root()
    original_mtime = package_json_path.stat().st_mtime_ns

    for _ in range(2):
        assert frontend_skeleton.sync_root_package_json_to_web() is False
        assert package_json_path.read_text() == formatted
        assert package_json_path.stat().st_mtime_ns == original_mtime


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dependencies", {"test-pkg": "2.0.0"}),
        ("devDependencies", {"test-dev-pkg": "1.0.0"}),
        ("overrides", {"test-pkg": "2.0.0"}),
        ("scripts", {}),
        ("description", "Changed app"),
    ],
)
def test_sync_root_package_json_restores_content(package_json_path: Path, field, value):
    """Content differences still restore the persisted manifest and required scripts.

    Args:
        package_json_path: The rendered package.json path.
        field: Manifest field to change.
        value: Changed field value.
    """
    original = json.loads(package_json_path.read_text())
    package_json_path.write_text(json.dumps({**original, field: value}, indent=2))

    assert frontend_skeleton.sync_root_package_json_to_web() is True
    assert json.loads(package_json_path.read_text()) == original


@pytest.mark.parametrize("content", [None, "", "{invalid", "[]", "null"])
def test_sync_root_package_json_repairs_unusable_file(
    package_json_path: Path, content: str | None
):
    """Missing or invalid rendered manifests are replaced with the compiled object.

    Args:
        package_json_path: The rendered package.json path.
        content: Invalid file content, or None to remove the file.
    """
    original = json.loads(package_json_path.read_text())
    if content is None:
        package_json_path.unlink()
    else:
        package_json_path.write_text(content)

    assert frontend_skeleton.sync_root_package_json_to_web() is (content is not None)
    assert json.loads(package_json_path.read_text()) == original

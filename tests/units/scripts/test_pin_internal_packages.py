"""Tests for .github/scripts/publish/pin_internal_packages.py."""

import importlib.util
from pathlib import Path

import pytest
from packaging.version import Version

_SCRIPT = (
    Path(__file__).parents[3]
    / ".github"
    / "scripts"
    / "publish"
    / "pin_internal_packages.py"
)
_spec = importlib.util.spec_from_file_location("pin_internal_packages", _SCRIPT)
assert _spec is not None
assert _spec.loader is not None
pin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pin)


def test_internal_dependencies_filters_workspace_and_specifier():
    pyproject = {
        "project": {
            "dependencies": [
                "reflex-base >= 0.9.0",
                "reflex-hosting-cli",
                "click >=8.2",
                "reflex-components-lucide >= 0.9.0",
            ]
        },
        "tool": {
            "uv": {
                "sources": {
                    "reflex-base": {"workspace": True},
                    "reflex-hosting-cli": {"workspace": True},
                    "reflex-components-lucide": {"workspace": True},
                    "click": {"git": "https://example.com"},
                }
            }
        },
    }
    result = pin.internal_dependencies(pyproject)
    names = [req.name for _, req in result]
    assert names == ["reflex-base", "reflex-components-lucide"]
    assert result[0][0] == "reflex-base >= 0.9.0"


def test_internal_dependencies_empty_when_no_sources():
    pyproject = {"project": {"dependencies": ["reflex-base >= 0.9.0"]}}
    assert pin.internal_dependencies(pyproject) == []


@pytest.mark.parametrize(
    ("tags", "allow_prerelease", "expected"),
    [
        (
            ["reflex-base-v0.9.1", "reflex-base-v0.9.3", "reflex-base-v0.9.2"],
            False,
            "0.9.3",
        ),
        (
            ["reflex-base-v0.9.3", "reflex-base-v0.9.3a1", "reflex-base-v0.9.4a1"],
            False,
            "0.9.3",
        ),
        (
            ["reflex-base-v0.9.3", "reflex-base-v0.9.4a1"],
            True,
            "0.9.4a1",
        ),
        (
            ["reflex-base-v0.9.2.post1", "reflex-base-v0.9.2"],
            False,
            "0.9.2.post1",
        ),
    ],
)
def test_latest_version_selection(tags, allow_prerelease, expected):
    assert pin.latest_version(
        "reflex-base", tags, allow_prerelease=allow_prerelease
    ) == Version(expected)


def test_latest_version_ignores_other_packages_and_invalid():
    tags = [
        "reflex-base-v0.9.1",
        "reflex-components-lucide-v9.9.9",
        "reflex-base-vnot-a-version",
    ]
    assert pin.latest_version("reflex-base", tags, allow_prerelease=False) == Version(
        "0.9.1"
    )


def test_latest_version_none_when_only_prereleases_disallowed():
    tags = ["reflex-base-v0.9.0a1", "reflex-base-v0.9.0a2"]
    assert pin.latest_version("reflex-base", tags, allow_prerelease=False) is None


def test_pin_dependencies_replaces_specifier_preserving_formatting():
    text = '  "reflex-base >= 0.9.0",\n  "reflex-hosting-cli",\n'
    result = pin.pin_dependencies(
        text, [("reflex-base", "reflex-base >= 0.9.0", Version("0.9.3"))]
    )
    assert result == '  "reflex-base == 0.9.3",\n  "reflex-hosting-cli",\n'


def test_pin_dependencies_raises_when_not_found():
    with pytest.raises(RuntimeError, match="found 0"):
        pin.pin_dependencies(
            "", [("reflex-base", "reflex-base >= 0.9.0", Version("0.9.3"))]
        )

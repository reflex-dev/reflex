"""Guards on how the workspace packages derive their versions from git tags.

A package that needs an unreleased change in a sibling floors it at a ``*.dev``
version, which only works if every build of the branch numbers the sibling above
all of its published releases. dunamai's default PEP 440 serialization does not:
after a post-release tag such as ``reflex-components-core-v0.9.10.post1`` it
derives ``0.9.10.post1.devN``, a development release *of* the published version
that sorts below it, so no floor can both exclude ``0.9.10.post1`` and be met by
the workspace. ``bump = true`` derives ``0.9.10.post2.devN`` there instead, and
``0.9.13.devN`` after a final ``0.9.12``, so ``>= <next>.dev0`` always works.
"""

import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = pytest.importorskip("tomli", reason="requires tomli on Python < 3.11")

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(project: Path) -> dict:
    """Parse a project's ``pyproject.toml``.

    Args:
        project: The project directory.

    Returns:
        The parsed document.
    """
    return tomllib.loads((project / "pyproject.toml").read_text())


def _workspace_projects() -> list[Path]:
    """Return the root project and every workspace member's directory.

    Returns:
        The directories holding a ``pyproject.toml``, root first.
    """
    members = _load(REPO_ROOT)["tool"]["uv"]["workspace"]["members"]
    return [
        REPO_ROOT,
        *sorted(
            path
            for pattern in members
            for path in REPO_ROOT.glob(pattern)
            if (path / "pyproject.toml").is_file()
        ),
    ]


TAG_VERSIONED = [
    path
    for path in _workspace_projects()
    if _load(path).get("tool", {}).get("hatch", {}).get("version", {}).get("source")
    == "uv-dynamic-versioning"
]


def test_workspace_has_tag_versioned_packages():
    """The discovery finds the packages, so the guard below is not vacuous."""
    names = {_load(path)["project"]["name"] for path in TAG_VERSIONED}
    assert {"reflex", "reflex-base", "reflex-components-core"} <= names


@pytest.mark.parametrize(
    "project",
    TAG_VERSIONED,
    ids=[str(path.relative_to(REPO_ROOT)) or "." for path in TAG_VERSIONED],
)
def test_dynamic_versioning_bumps(project: Path):
    """Every commit after a tag builds as a dev release of the next version."""
    config = _load(project)["tool"].get("uv-dynamic-versioning", {})
    assert config.get("bump") is True, (
        f"{project.relative_to(REPO_ROOT)}/pyproject.toml must set `bump = true` "
        "under [tool.uv-dynamic-versioning], or a post-release tag leaves no "
        "satisfiable *.dev floor on the package"
    )

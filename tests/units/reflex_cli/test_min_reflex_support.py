"""Guards on the reflex versions reflex-hosting-cli claims to support.

The hosting CLI advertises support down to
``ReflexHostingCli.MINIMUM_REFLEX_VERSION``, which predates the reflex release
that split the framework into workspace packages. Depending on any of those
packages is therefore unsatisfiable on the oldest reflex the CLI claims to
support -- and it fails quietly rather than loudly: reflex 0.8.x declares no
reflex-base dependency of its own, so pip has no conflict to report and simply
installs a second, mismatched framework base alongside reflex.

The companion runtime guard is ``test_cli_imports_without_reflex_base`` in
``tests/units/reflex_cli/utils/test_log.py``, which covers the other half --
importing a workspace package that older reflex does not ship.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
from reflex_cli.constants.hosting import ReflexHostingCli

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PYPROJECT = REPO_ROOT / "packages" / "reflex-hosting-cli" / "pyproject.toml"

ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"

# The reflex release that first shipped the framework runtime packages:
# reflex-base was carved out in #6281 and its earliest tag is reflex-base-v0.9.0.
# None of them can be depended on from a reflex older than this.
REFLEX_WORKSPACE_SPLIT_VERSION = Version("0.9.0")


def _load(pyproject: Path) -> dict:
    """Parse a pyproject.toml file.

    Args:
        pyproject: The file to parse.

    Returns:
        The parsed document.
    """
    with pyproject.open("rb") as f:
        return tomllib.load(f)


def _dependency_names(pyproject: Path) -> set[str]:
    """Collect the canonicalized names a package declares as dependencies.

    Args:
        pyproject: The pyproject.toml to read.

    Returns:
        The canonicalized distribution names.
    """
    return {
        canonicalize_name(Requirement(dep).name)
        for dep in _load(pyproject)["project"]["dependencies"]
    }


def _workspace_package_names() -> set[str]:
    """Collect the distribution name of every package in the workspace.

    Returns:
        The canonicalized distribution names.
    """
    names = set()
    for pyproject in sorted((REPO_ROOT / "packages").glob("*/pyproject.toml")):
        if name := _load(pyproject).get("project", {}).get("name"):
            names.add(canonicalize_name(name))
    return names


def _framework_runtime_packages() -> set[str]:
    """Collect the workspace packages that reflex itself pulls in.

    These are the framework runtime: their presence and version are decided by
    whichever reflex the user installed, so the hosting CLI depending on one is
    either unsatisfiable on old reflex or silently resolves to a second,
    mismatched copy alongside it. Workspace *utilities* reflex does not depend
    on (reflex-release, reflex-docgen) are ordinary PyPI distributions and are
    perfectly fine to depend on -- they are excluded here.

    Derived from the checkout rather than hard-coded, so a framework package
    added later is covered without touching this test.

    Returns:
        The canonicalized distribution names, excluding the hosting CLI itself.
    """
    return (_dependency_names(ROOT_PYPROJECT) & _workspace_package_names()) - {
        canonicalize_name("reflex-hosting-cli")
    }


def test_framework_runtime_packages_are_discoverable():
    """The scan finds the right packages, so the guards below are not vacuous."""
    framework = _framework_runtime_packages()
    # Shipped by reflex, so gated on the user's reflex version.
    assert canonicalize_name("reflex-base") in framework
    assert canonicalize_name("reflex-components-core") in framework
    # Independent distributions, and the CLI itself: not gated, not banned.
    assert canonicalize_name("reflex-release") not in framework
    assert canonicalize_name("reflex-docgen") not in framework
    assert canonicalize_name("reflex-hosting-cli") not in framework


def test_no_dependency_that_the_minimum_reflex_cannot_satisfy():
    """The CLI must not require a package older reflex does not ship.

    Adding one (as #6866 did with reflex-base) makes the advertised floor a
    lie, so this fails until either the dependency goes or
    MINIMUM_REFLEX_VERSION is raised past the workspace split.
    """
    minimum = ReflexHostingCli.MINIMUM_REFLEX_VERSION
    offenders = sorted(_dependency_names(CLI_PYPROJECT) & _framework_runtime_packages())

    if minimum >= REFLEX_WORKSPACE_SPLIT_VERSION:
        pytest.skip(
            f"MINIMUM_REFLEX_VERSION is {minimum}, at or past the workspace "
            f"split ({REFLEX_WORKSPACE_SPLIT_VERSION}); framework packages are "
            "satisfiable and this guard no longer applies."
        )

    assert not offenders, (
        f"reflex-hosting-cli advertises reflex >= {minimum} "
        f"(ReflexHostingCli.MINIMUM_REFLEX_VERSION) but declares {offenders}, "
        f"which reflex only ships from {REFLEX_WORKSPACE_SPLIT_VERSION} on. "
        "Reach for it through an optional import instead (see "
        "reflex_cli.utils.log), or raise MINIMUM_REFLEX_VERSION and "
        "RECOMMENDED_REFLEX_VERSION to match what is actually supported."
    )


def test_no_workspace_dependency_sources():
    """No ``[tool.uv.sources]`` workspace entry may smuggle a sibling package in.

    A workspace source resolves locally, so a dependency added this way can look
    fine in the monorepo while being unsatisfiable for an installed user.
    """
    sources = _load(CLI_PYPROJECT).get("tool", {}).get("uv", {}).get("sources", {})
    workspace_sources = sorted(
        name for name, spec in sources.items() if spec.get("workspace")
    )
    assert not workspace_sources, (
        f"reflex-hosting-cli declares workspace sources for {workspace_sources}. "
        "The published package cannot resolve them; drop the source and the "
        "matching dependency."
    )


def test_recommended_version_is_reachable_from_the_minimum():
    """The upgrade the CLI recommends must be a real step up from the floor.

    ``v2/deployments.py`` tells users below the recommended version to upgrade
    to it, so it has to be a version that both exists and satisfies the CLI's
    own dependencies.
    """
    minimum = ReflexHostingCli.MINIMUM_REFLEX_VERSION
    recommended = ReflexHostingCli.RECOMMENDED_REFLEX_VERSION
    assert minimum <= recommended, (
        f"MINIMUM_REFLEX_VERSION ({minimum}) is above "
        f"RECOMMENDED_REFLEX_VERSION ({recommended}), so the CLI gates on a "
        "version it then tells the user is too old."
    )

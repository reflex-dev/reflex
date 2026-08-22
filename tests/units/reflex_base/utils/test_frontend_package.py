"""Tests for the bundled frontend npm package manifest and its locator."""

import json
from pathlib import Path

import pytest
from packaging import version
from reflex_base import constants
from reflex_base.utils import frontend_package
from reflex_base.utils.frontend_package import (
    FrontendPackageMissingError,
    FrontendPackageMode,
    clear_frontend_package_cache,
    frontend_package_dir,
    get_frontend_package,
)

# Baselines declared by the pinned react-router release (its package.json
# `peerDependencies.react` and the Vite floor from its release notes). These
# live only in the upstream manifest, so mirror them here to catch a partial
# bump that would otherwise surface as an install warning or runtime failure.
REACT_ROUTER_MIN_REACT = "19.2.7"
REACT_ROUTER_MIN_VITE = "7"


@pytest.fixture
def manifest() -> dict:
    """The source manifest of the bundled frontend package.

    Returns:
        The parsed package.json of the in-repo frontend package source.
    """
    return json.loads((frontend_package_dir() / "package.json").read_text())


@pytest.fixture
def clear_cache():
    """Clear the frontend package cache around a test.

    Yields:
        None.
    """
    clear_frontend_package_cache()
    yield
    clear_frontend_package_cache()


def _all_pins(manifest: dict) -> dict[str, str]:
    return {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}


def test_react_router_packages_share_one_version(manifest: dict):
    """Every react-router package is pinned to the same version."""
    pins = {
        name: pin
        for name, pin in _all_pins(manifest).items()
        if name == "react-router" or name.startswith("@react-router/")
    }
    assert pins["react-router"], "react-router must be pinned"
    assert len(set(pins.values())) == 1, f"mismatched react-router pins: {pins}"


def test_react_router_dom_is_not_a_dependency(manifest: dict):
    """The `react-router-dom` re-export package was removed in react-router 8."""
    assert "react-router-dom" not in _all_pins(manifest)


@pytest.mark.parametrize("package", ["react", "react-dom"])
def test_react_pin_satisfies_react_router_peer(manifest: dict, package: str):
    """The pinned React packages satisfy react-router's peer requirement."""
    assert version.parse(manifest["dependencies"][package]) >= version.parse(
        REACT_ROUTER_MIN_REACT
    )


def test_vite_pin_satisfies_react_router(manifest: dict):
    """The pinned Vite version meets the floor required by `@react-router/dev`."""
    assert version.parse(manifest["devDependencies"]["vite"]) >= version.parse(
        REACT_ROUTER_MIN_VITE
    )


def test_constants_match_manifest_name(manifest: dict):
    """The Python-side package name constant matches the manifest."""
    assert manifest["name"] == constants.FrontendPackage.NAME


def test_constant_specifiers_resolve_to_shipped_files(manifest: dict):
    """Every FrontendPackage specifier maps to a file the exports map serves."""
    name = constants.FrontendPackage.NAME
    specifiers = [
        value
        for key, value in vars(constants.FrontendPackage).items()
        if key.isupper() and key != "NAME" and isinstance(value, str)
    ]
    assert specifiers, "no specifiers found on constants.FrontendPackage"
    for specifier in specifiers:
        subpath = specifier.removeprefix(f"{name}/")
        assert subpath != specifier, f"{specifier} does not start with {name}/"
        relative = subpath if subpath.endswith((".js", ".css")) else f"{subpath}.js"
        target = frontend_package_dir() / relative
        assert target.is_file(), f"{specifier} does not resolve to {target}"


def test_optional_peers_are_marked_optional(manifest: dict):
    """Component-backed peer deps must be optional so they never auto-install."""
    meta = manifest.get("peerDependenciesMeta", {})
    for peer in manifest.get("peerDependencies", {}):
        assert meta.get(peer, {}).get("optional") is True, (
            f"{peer} must be an optional peer"
        )


def test_get_frontend_package_source_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clear_cache
):
    """A source directory with package.json is detected as SOURCE mode."""
    (tmp_path / "package.json").write_text(
        json.dumps({
            "name": "@reflex-dev/reflex-base",
            "version": "0.0.0",
            "dependencies": {"react": "1.0.0"},
            "devDependencies": {"vite": "2.0.0"},
        })
    )
    monkeypatch.setattr(frontend_package, "frontend_package_dir", lambda: tmp_path)

    package = get_frontend_package()

    assert package.mode is FrontendPackageMode.SOURCE
    assert package.path == tmp_path
    assert package.name == "@reflex-dev/reflex-base"
    assert package.dependencies == {"react": "1.0.0"}
    assert package.dev_dependencies == {"vite": "2.0.0"}
    with pytest.raises(FrontendPackageMissingError):
        _ = package.tarball_basename


def test_get_frontend_package_tarball_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clear_cache
):
    """A single packed tarball is detected as TARBALL mode and its manifest read."""
    hatch_build = _load_hatch_build()
    source = tmp_path / "src"
    source.mkdir()
    (source / "package.json").write_text(
        json.dumps({
            "name": "@reflex-dev/reflex-base",
            "version": "0.0.0",
            "files": ["state.js"],
            "dependencies": {"react": "1.0.0"},
        })
    )
    (source / "state.js").write_text("export const x = 1;\n")
    install_dir = tmp_path / "installed"
    tgz = install_dir / hatch_build.npm_tarball_basename(
        "@reflex-dev/reflex-base", "1.2.3"
    )
    hatch_build.build_frontend_tarball(source, "1.2.3", tgz)
    monkeypatch.setattr(frontend_package, "frontend_package_dir", lambda: install_dir)

    package = get_frontend_package()

    assert package.mode is FrontendPackageMode.TARBALL
    assert package.path == tgz
    assert package.version == "1.2.3"
    assert package.tarball_basename == "reflex-dev-reflex-base-1.2.3.tgz"
    assert package.dependencies == {"react": "1.0.0"}


def test_get_frontend_package_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clear_cache
):
    """Neither source nor tarball raises a descriptive error."""
    monkeypatch.setattr(
        frontend_package, "frontend_package_dir", lambda: tmp_path / "nope"
    )

    with pytest.raises(FrontendPackageMissingError, match="Reinstall reflex-base"):
        get_frontend_package()


def _load_hatch_build():
    """Load the reflex-base build hook module by path.

    Returns:
        The loaded hatch_build module.
    """
    import importlib.util

    hook_path = (
        Path(__file__).parents[4] / "packages/reflex-base/scripts/hatch_build.py"
    )
    spec = importlib.util.spec_from_file_location("reflex_base_hatch_build", hook_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

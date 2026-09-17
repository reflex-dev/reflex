"""Tests for the frontend toolchain version constants."""

import pytest
from packaging import version
from reflex_base.constants.installer import Node, PackageJson

# Baselines declared by the pinned react-router release (its package.json
# `engines.node` and `peerDependencies.react`, plus the Vite floor from its
# release notes). These live only in the upstream manifest, so mirror them
# here to catch a partial bump that would otherwise surface as an install
# warning or a runtime failure.
REACT_ROUTER_MIN_NODE = "22.22.0"
REACT_ROUTER_MIN_REACT = "19.2.7"
REACT_ROUTER_MIN_VITE = "7"


def test_react_router_packages_share_one_version():
    """Every react-router package is pinned to the same version."""
    pins = {
        name: pin
        for name, pin in (
            *PackageJson.DEPENDENCIES.items(),
            *PackageJson.DEV_DEPENDENCIES.items(),
        )
        if name == "react-router" or name.startswith("@react-router/")
    }
    assert pins["react-router"], "react-router must be pinned"
    assert len(set(pins.values())) == 1, f"mismatched react-router pins: {pins}"


def test_react_router_dom_is_not_a_dependency():
    """The `react-router-dom` re-export package was removed in react-router 8."""
    assert "react-router-dom" not in PackageJson.DEPENDENCIES
    assert "react-router-dom" not in PackageJson.DEV_DEPENDENCIES


def test_node_min_version_satisfies_react_router():
    """The minimum Node version covers react-router's `engines.node` floor."""
    assert version.parse(Node.MIN_VERSION) >= version.parse(REACT_ROUTER_MIN_NODE)


@pytest.mark.parametrize("package", ["react", "react-dom"])
def test_react_pin_satisfies_react_router_peer(package: str):
    """The pinned React packages satisfy react-router's peer requirement."""
    assert version.parse(PackageJson.DEPENDENCIES[package]) >= version.parse(
        REACT_ROUTER_MIN_REACT
    )


def test_vite_pin_satisfies_react_router():
    """The pinned Vite version meets the floor required by `@react-router/dev`."""
    assert version.parse(PackageJson.DEV_DEPENDENCIES["vite"]) >= version.parse(
        REACT_ROUTER_MIN_VITE
    )

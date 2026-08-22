"""Tests for the frontend toolchain version constants."""

from packaging import version
from reflex_base.constants.installer import Node

# Baseline declared by the pinned react-router release (its package.json
# `engines.node`). It lives only in the upstream manifest, so mirror it here
# to catch a partial bump that would otherwise surface as an install warning
# or a runtime failure. The react/vite floors are asserted against the
# frontend package manifest in tests/units/reflex_base/utils/test_frontend_package.py.
REACT_ROUTER_MIN_NODE = "22.22.0"


def test_node_min_version_satisfies_react_router():
    """The minimum Node version covers react-router's `engines.node` floor."""
    assert version.parse(Node.MIN_VERSION) >= version.parse(REACT_ROUTER_MIN_NODE)

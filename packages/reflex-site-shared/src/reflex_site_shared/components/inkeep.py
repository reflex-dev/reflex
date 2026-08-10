"""Backward-compatible entry points for the former Inkeep search module."""

from typing import Any

from reflex_base.utils import console

from reflex_site_shared.components.algolia import AlgoliaSearch, Search, algolia_search


def _warn_inkeep_deprecation(feature_name: str) -> None:
    """Warn that a legacy Inkeep entry point now renders Algolia search.

    Args:
        feature_name: The legacy entry point used by the caller.
    """
    console.deprecate(
        feature_name=feature_name,
        reason="Use the keyword-only Algolia search API instead.",
        deprecation_version="0.0.42",
        removal_version="1.0.0",
    )


class InkeepSearchBar(AlgoliaSearch):
    """Deprecated compatibility component for the former Inkeep search bar."""

    @classmethod
    def create(cls, *children: Any, **props: Any) -> "InkeepSearchBar":
        """Create the Algolia replacement and warn legacy callers.

        Args:
            children: Child components passed to the search component.
            props: Props passed to the search component.

        Returns:
            The keyword-only Algolia search component.
        """
        _warn_inkeep_deprecation("InkeepSearchBar")
        return super().create(*children, **props)


def inkeep(**props: Any) -> Search:
    """Create shared search through the deprecated Inkeep API.

    Args:
        props: Props applied to the shared search wrapper.

    Returns:
        The shared keyword-only Algolia search control.
    """
    _warn_inkeep_deprecation("inkeep()")
    return algolia_search(**props)


__all__ = ["InkeepSearchBar", "Search", "inkeep"]

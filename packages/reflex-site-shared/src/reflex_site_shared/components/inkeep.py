"""Backward-compatible aliases for the former Inkeep search module."""

from reflex_site_shared.components.algolia import AlgoliaSearch, Search, algolia_search

InkeepSearchBar = AlgoliaSearch
inkeep = algolia_search

__all__ = ["InkeepSearchBar", "Search", "inkeep"]

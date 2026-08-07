"""Tests for compatibility with the former shared search imports."""

from reflex_site_shared.components.algolia import AlgoliaSearch, Search, algolia_search
from reflex_site_shared.components.inkeep import InkeepSearchBar, inkeep


def test_inkeep_imports_alias_keyword_search() -> None:
    """Keep downstream imports working without loading the Inkeep package."""
    assert InkeepSearchBar is AlgoliaSearch
    assert inkeep == algolia_search
    assert Search.create().children[0].library == AlgoliaSearch.library

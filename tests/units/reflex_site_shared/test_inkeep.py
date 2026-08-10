"""Tests for compatibility with the former shared search imports."""

from pytest_mock import MockerFixture
from reflex_site_shared.components.algolia import AlgoliaSearch, Search
from reflex_site_shared.components.inkeep import InkeepSearchBar, inkeep


def test_inkeep_imports_render_keyword_search() -> None:
    """Keep downstream imports working without loading the Inkeep package."""
    assert issubclass(InkeepSearchBar, AlgoliaSearch)
    assert Search.create().children[0].library == AlgoliaSearch.library


def test_inkeep_search_bar_warns_before_rendering(mocker: MockerFixture) -> None:
    """Warn legacy class callers before rendering the Algolia replacement."""
    mock_deprecate = mocker.patch(
        "reflex_site_shared.components.inkeep.console.deprecate"
    )

    search_bar = InkeepSearchBar.create()

    assert search_bar.library == AlgoliaSearch.library
    mock_deprecate.assert_called_once()
    assert mock_deprecate.call_args.kwargs["feature_name"] == "InkeepSearchBar"


def test_inkeep_function_warns_before_rendering(mocker: MockerFixture) -> None:
    """Warn legacy function callers before rendering the Algolia replacement."""
    mock_deprecate = mocker.patch(
        "reflex_site_shared.components.inkeep.console.deprecate"
    )

    search = inkeep()

    assert search.children[0].library == AlgoliaSearch.library
    mock_deprecate.assert_called_once()
    assert mock_deprecate.call_args.kwargs["feature_name"] == "inkeep()"

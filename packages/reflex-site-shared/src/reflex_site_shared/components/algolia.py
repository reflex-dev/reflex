"""Keyword-only Algolia search shared by Reflex sites."""

import reflex as rx


class AlgoliaSearch(rx.NoSSRComponent):
    """Client-only search component backed by Algolia's Search API."""

    library = "$/public/components/AlgoliaSearch"
    lib_dependencies = [
        "@hugeicons/react",
        "@hugeicons/core-free-icons",
    ]
    tag = "AlgoliaSearch"
    is_default = True


class Search(rx.el.Div):
    """Wrap the shared search component for navbar compatibility."""

    @classmethod
    def create(cls, **props) -> rx.Component:
        """Create the shared keyword-search control.

        Args:
            props: Props applied to the wrapper element.

        Returns:
            The Algolia search control inside its navbar wrapper.
        """
        return super().create(AlgoliaSearch.create(), **props)


algolia_search = Search.create

__all__ = ["AlgoliaSearch", "Search", "algolia_search"]

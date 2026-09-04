"""Search bar component for the navbar."""

import reflex as rx

from .algolia import algolia_search


@rx.memo
def search_bar() -> rx.Component:
    return algolia_search()

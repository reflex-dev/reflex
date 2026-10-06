"""Keep upstream map demos unchanged while registering their routes."""

import reflex as rx


def demo(route: str, title: str, description: str, **kwargs):
    """Register an upstream demo page.

    Args:
        route: Page route.
        title: Page title.
        description: Page description.
        **kwargs: Additional page options.

    Returns:
        The Reflex page decorator.
    """
    return rx.page(route=route, title=title, description=description, **kwargs)

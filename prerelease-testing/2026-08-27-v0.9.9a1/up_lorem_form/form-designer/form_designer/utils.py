"""Miscellaneous utility functions."""

import reflex as rx

from reflex_local_auth import LoginState


def require_login(page: rx.app.ComponentCallable) -> rx.app.ComponentCallable:
    """Decorator to require authentication before rendering a page.

    If the user is not authenticated, then redirect to the login page.

    Args:
        page: The page to wrap.

    Returns:
        The wrapped page component.
    """

    def protected_page():
        return rx.cond(
            LoginState.is_authenticated,
            page(),
            rx.center(
                rx.spinner(on_mount=LoginState.redir),
                width="100vw",
                height="100vh",
            ),
        )

    protected_page.__name__ = page.__name__
    return protected_page


def focus_input_in_class(class_name: str) -> rx.event.EventSpec:
    """Focus the last input in the last class.

    Args:
        class_name: The class name to search for.

    Returns:
        A reflex component.
    """
    # Use window.setTimeout to allow react enough time to add new input elements.
    return rx.call_script(
        "window.setTimeout("
        f"() => Array.from(document.querySelectorAll('.{class_name} input')).pop().focus(),"
        "100)"
    )

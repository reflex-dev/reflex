"""A component module that publishes two shared assets (#7039)."""

import reflex as rx

CSS_PATH = rx.asset("shared.css", shared=True)
JS_PATH = rx.asset("shared.js", shared=True)


def widget() -> rx.Component:
    """A widget that pulls in both shared assets.

    Returns:
        The widget component.
    """
    return rx.fragment(
        rx.el.link(rel="stylesheet", href=CSS_PATH),
        rx.el.script(src=JS_PATH),
        rx.el.div("shared widget", class_name="shared-marker", id="widget"),
    )

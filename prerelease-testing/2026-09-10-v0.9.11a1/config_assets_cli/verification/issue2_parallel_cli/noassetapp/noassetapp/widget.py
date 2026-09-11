"""Same shape as sharedapp.widget but with no rx.asset(shared=True)."""

import reflex as rx

CSS_PATH = "/shared.css"
JS_PATH = "/shared.js"


def widget() -> rx.Component:
    """A widget that pulls in two static assets.

    Returns:
        The widget component.
    """
    return rx.fragment(
        rx.el.link(rel="stylesheet", href=CSS_PATH),
        rx.el.script(src=JS_PATH),
        rx.el.div("shared widget", class_name="shared-marker", id="widget"),
    )

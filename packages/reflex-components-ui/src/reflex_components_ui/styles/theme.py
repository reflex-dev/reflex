"""The look of the element that carries the theme of an app."""

from reflex_components_ui.base import ComponentStyles

# What Radix Themes gives its root theme: the background covers the page, and
# the content stacks under what is rendered beside it, such as a toast.
APP_THEME: ComponentStyles = {
    "base": {
        "position": "relative",
        "zIndex": 0,
        "minHeight": "100vh",
    },
}

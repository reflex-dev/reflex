"""The look of the elements of a theme, beside what the theme itself sets."""

from reflex_components_ui.style import ComponentStyles

# What Radix Themes gives its root theme: the background covers the page, and
# the content stacks under what is rendered beside it, such as a toast.
APP_THEME: ComponentStyles = {
    "base": {
        "position": "relative",
        "zIndex": 0,
        "minHeight": {
            "default": "100vh",
            "@supports (min-height: 100dvh)": "100dvh",
        },
    },
}

# The element that carries the class of an appearance has no box of its own.
APPEARANCE: ComponentStyles = {
    "base": {
        "display": "contents",
    },
}

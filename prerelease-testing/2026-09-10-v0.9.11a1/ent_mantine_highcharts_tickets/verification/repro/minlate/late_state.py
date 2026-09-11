"""A state class defined only when the plugin's post_compile hook runs."""

import reflex as rx


class LateState(rx.State):
    """State the compiled frontend never hears about."""

    late_value: str = "late"

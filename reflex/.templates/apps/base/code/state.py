"""Base state for the app."""

import reflex as rx


class State(rx.State):
    """State for the app."""

    # Whether the sidebar is displayed.
    sidebar_displayed: bool = True

    def toggle_sidebar_displayed(self) -> None:
        """Toggle the sidebar displayed."""
        self.sidebar_displayed = not self.sidebar_displayed
        print(self.router.page.full_raw_path)
        print(self.router.page.raw_path)
        print(self.router.page.path)

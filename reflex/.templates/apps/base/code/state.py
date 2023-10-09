import reflex as rx


class State(rx.State):
    """State for the app."""

    current_page: str = "Dashboard"

    def set_page(self, page: str):
        """Set the current page.

        Args:
            page: The page to set.
        """
        self.current_page = page

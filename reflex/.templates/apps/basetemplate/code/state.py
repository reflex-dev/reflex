import reflex as rx


class State(rx.State):
    """State for the app."""

    show_sidebar: bool = False

    current_page: str = "Dashboard"

    def toggle_sidebar(self):
        """Toggle the sidebar."""
        self.show_sidebar = not self.show_sidebar

    def set_page(self, page: str):
        """Set the current page.

        Args:
            page: The page to set.
        """
        self.current_page = page

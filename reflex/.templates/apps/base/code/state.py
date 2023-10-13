"""Base state for the app."""

import reflex as rx


class State(rx.State):
    """State for the app."""

    @rx.var
    def origin_url(self) -> str:
        """Get the url of the current page.

        Returns:
            str: The url of the current page.
        """
        return self.router_data.get("asPath", "")

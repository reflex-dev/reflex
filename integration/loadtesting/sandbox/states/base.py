import reflex as rx


class BaseState(rx.State):

    query_component_toggle: str = "none"

    is_request: str = "New Request"

    def toggle_query(self):
        self.query_component_toggle = (
            "flex" if self.query_component_toggle == "none" else "none"
        )

        self.is_request = (
            "New Request" if self.query_component_toggle == "none" else "Close Request"
        )

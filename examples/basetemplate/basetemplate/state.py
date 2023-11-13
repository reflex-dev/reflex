import reflex as rx


class State(rx.State):
    show_sidebar: bool = False

    current_page: str = "Dashboard"

    def toggle_sidebar(self):
        self.show_sidebar = not self.show_sidebar

    def set_page(self, page: str):
        self.current_page = page

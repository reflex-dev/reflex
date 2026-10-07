"""A state module shared by several AppHarness apps in one process (like an installed package's states)."""
import reflex as rx


class SharedCfg(rx.State):
    count: int = 0
    theme: str = rx.LocalStorage("light", name="h_theme")

    @rx.event
    def bump(self):
        self.count += 1
        self.theme = f"{self.theme}+"

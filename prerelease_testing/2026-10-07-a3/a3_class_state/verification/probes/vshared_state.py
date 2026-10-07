"""A state living in a plain module that is not part of any AppHarness app package."""

import reflex as rx


class SharedCounter(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1

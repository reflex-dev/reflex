"""A state module shared by both harness apps (imported by the test module first: the reflex#7479 workaround)."""
import reflex as rx


class SharedCounter(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1

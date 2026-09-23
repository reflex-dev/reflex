"""State of the playground app, including the hooks the benchmarks drive."""

import reflex as rx

HANDLER_MARKER = "m-initial-handler"  # bench:hmr-target handler


class PlaygroundState(rx.State):
    """State behind the counter and the item list."""

    count: int = 0
    items: list[str] = ["alpha", "beta", "gamma"]

    @rx.event
    def increment(self):
        """Increase the counter by one."""
        self.count += 1

    @rx.event
    def decrement(self):
        """Decrease the counter by one."""
        self.count -= 1


class BenchState(rx.State):
    """State the macro benchmarks drive and read back."""

    last_seq: int = 0
    handler_value: str = ""

    @rx.event
    def set_seq(self, seq: int):
        """Record the sequence number of a benchmark event.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.last_seq = seq

    @rx.event
    def bench_value(self):
        """Show the handler marker, which the hot reload benchmarks rewrite."""
        self.handler_value = HANDLER_MARKER

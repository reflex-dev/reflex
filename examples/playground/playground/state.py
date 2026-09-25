"""State of the playground app, including the hooks the benchmarks drive."""

import asyncio

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
    part_a: int = 0
    part_b: int = 0
    part_c: int = 0

    @rx.var
    def parts_total(self) -> int:
        """Add up the parts that set_seq_complex sets.

        Returns:
            The sum of the three parts.
        """
        return self.part_a + self.part_b + self.part_c

    @rx.var
    def parts_scaled(self) -> int:
        """Scale the total, the second link of the computed var chain.

        Returns:
            The total times ten.
        """
        return self.parts_total * 10

    @rx.var
    def parts_label(self) -> str:
        """Describe the scaled total, the last link of the computed var chain.

        Returns:
            The scaled total as text.
        """
        return f"scaled total {self.parts_scaled}"

    @rx.event
    def set_seq(self, seq: int):
        """Record the sequence number of a benchmark event.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.last_seq = seq

    @rx.event
    def set_seq_complex(self, seq: int):
        """Record the sequence number and set the parts behind the computed var chain.

        Args:
            seq: The sequence number the benchmark sent.
        """
        self.part_a = seq
        self.part_b = seq + 1
        self.part_c = seq + 2
        self.last_seq = seq

    @rx.event
    async def set_seq_cross(self, seq: int):
        """Record the sequence number after incrementing the counter of another state.

        Args:
            seq: The sequence number the benchmark sent.
        """
        playground = await self.get_state(PlaygroundState)
        playground.count += 1
        self.last_seq = seq

    @rx.event(background=True)
    async def set_seq_background(self, seq: int):
        """Record the sequence number from a background task.

        Args:
            seq: The sequence number the benchmark sent.
        """
        await asyncio.sleep(0)
        async with self:
            self.last_seq = seq

    @rx.event
    def bench_value(self):
        """Show the handler marker, which the hot reload benchmarks rewrite."""
        self.handler_value = HANDLER_MARKER

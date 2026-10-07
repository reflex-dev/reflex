"""Compare background completion and foreground recovery after session expiry."""

import asyncio
import importlib.metadata
import json
import os
from pathlib import Path

import reflex as rx
from rxconfig import config

assert Path(rx.__file__).is_relative_to(
    Path(os.environ["VERIFY_SB"]) / "envs" / os.environ["VERIFY_ENV"]
), rx.__file__
print(
    "VERIFY_ORIGIN",
    json.dumps(
        {
            "reflex_file": rx.__file__,
            "version": importlib.metadata.version("reflex"),
            "manager": str(config.state_manager_mode),
            "ttl_seconds": config.redis_token_expiration,
        }
    ),
    flush=True,
)


class ExportDesk(rx.State):
    """Track completed work and expose a public server snapshot for verification."""

    processed: int = 0
    status: str = "idle"
    receipt: str = ""

    @rx.event
    async def seed_workspace(self):
        """Initialize distinct values through ordinary public state APIs."""
        selection = await self.get_state(Selection)
        left = await self.get_state(left_counter.State)
        right = await self.get_state(right_counter.State)
        self.processed = 7
        selection.count = 11
        left.count = 13
        right.count = 17
        self.status = "ready"
        self.receipt = ""

    @rx.event
    def foreground_increment(self):
        """Apply an ordinary foreground update after the idle control period."""
        self.processed += 1

    @rx.event(background=True)
    async def run_export(self):
        """Wait for simulated external work without retaining the state lock."""
        async with self:
            self.status = "exporting"
        await asyncio.sleep(float(os.environ["VERIFY_JOB_SECONDS"]))
        async with self:
            self.processed += 100
            self.status = "complete"

    @rx.event
    async def inspect_server(self):
        """Read root, child, and component states without modifying their counters."""
        selection = await self.get_state(Selection)
        left = await self.get_state(left_counter.State)
        right = await self.get_state(right_counter.State)
        self.receipt = json.dumps(
            {
                "root": self.processed,
                "section": selection.count,
                "left": left.count,
                "right": right.count,
            },
            sort_keys=True,
        )


class Selection(ExportDesk):
    """Keep one child-state selection count."""

    count: int = 0


class LocalCounter(rx.ComponentState):
    """Keep a separately generated component-state counter."""

    count: int = 0

    @classmethod
    def get_component(cls, label: str, **props):
        """Render one independently identifiable component instance.

        Args:
            label: Stable instance name for DOM observations.
            **props: Additional layout properties.

        Returns:
            A labeled component-state counter.
        """
        return rx.hstack(
            rx.text(f"{label.title()} panel:"),
            rx.text(cls.count, id=f"value-{label}"),
            **props,
        )


left_counter = LocalCounter.create(label="left")
right_counter = LocalCounter.create(label="right")


def index():
    """Render the export workspace and diagnostic controls.

    Returns:
        A small page with four independently stored counters.
    """
    return rx.vstack(
        rx.heading("Export workspace"),
        rx.hstack(
            rx.text("Processed units:"), rx.text(ExportDesk.processed, id="value-root")
        ),
        rx.hstack(rx.text("Selection:"), rx.text(Selection.count, id="value-section")),
        left_counter,
        right_counter,
        rx.text(ExportDesk.status, id="job-status"),
        rx.hstack(
            rx.button(
                "Load demo workspace", id="seed", on_click=ExportDesk.seed_workspace
            ),
            rx.button(
                "Run external export", id="export", on_click=ExportDesk.run_export
            ),
            rx.button(
                "Add processed unit",
                id="increment",
                on_click=ExportDesk.foreground_increment,
            ),
        ),
        rx.button(
            "Read server snapshot", id="inspect", on_click=ExportDesk.inspect_server
        ),
        rx.text(ExportDesk.receipt, id="receipt"),
        spacing="3",
        padding="24px",
    )


app = rx.App()
app.add_page(index)

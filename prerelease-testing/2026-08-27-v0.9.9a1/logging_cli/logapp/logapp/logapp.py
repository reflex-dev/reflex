"""Test app for the 0.9.9a1 logging pipeline cluster.

Exercises: deprecated console.* shims called from event handlers (server-side
DeprecationWarning), user-code logging.getLogger records, framework logger
records, a background task that logs, and normal state interactivity so the
app can be driven end-to-end in a browser.
"""

import asyncio
import logging

import reflex as rx
from reflex.utils import console

user_logger = logging.getLogger("logapp.user")


class LogState(rx.State):
    """State with handlers that emit through every logging surface."""

    count: int = 0
    status: str = "idle"
    bg_done: bool = False

    @rx.event
    def increment(self):
        """Increment and log through the deprecated console helpers."""
        self.count += 1
        # Deprecated shims: must still work and emit a DeprecationWarning once.
        console.info(f"console.info from event handler, count={self.count}")
        console.warn(f"console.warn from event handler, count={self.count}")
        # New-style per-module user logger (not under the reflex hierarchy).
        user_logger.warning("user_logger.warning from event handler count=%s", self.count)
        # A framework-hierarchy logger, to see how app-process records render.
        logging.getLogger("reflex_base.fake.module").warning(
            "reflex_base-hierarchy warning from app code count=%s", self.count
        )
        self.status = f"clicked {self.count}"

    @rx.event(background=True)
    async def bg_log(self):
        """Background task that logs and updates state."""
        async with self:
            self.status = "bg running"
        user_logger.warning("background task user log")
        console.debug("console.debug from background task (hidden unless debug)")
        await asyncio.sleep(0.2)
        async with self:
            self.bg_done = True
            self.status = "bg done"

    @rx.event
    def diag(self):
        """Report logging pipeline state inside the serving process."""
        import os

        import reflex_base.utils.log as _log

        self.status = (
            f"diag|managed={_log.is_managed_mode()}"
            f"|configured={_log._configured}"
            f"|logfile_env={os.environ.get('REFLEX_LOG_FILE')}"
            f"|full={os.environ.get('REFLEX_ENABLE_FULL_LOGGING')}"
            f"|pid={os.getpid()}"
        )

    @rx.event
    def diag2(self):
        """Report the resolved file-handler stream in this process."""
        import reflex_base.utils.log as _log

        import sys

        try:
            fh = _log._file_handler()
            stream = fh.stream
            name = getattr(stream, "name", "?")
            base = getattr(fh, "baseFilename", "?")
            is_stdout = stream is sys.stdout
            closed = getattr(stream, "closed", "?")
            info = (
                f"type={type(stream).__name__} name={name} base={base} "
                f"is_stdout={is_stdout} closed={closed}"
            )
        except Exception as e:  # noqa: BLE001
            info = f"ERROR {e!r}"
        handlers = _log._REFLEX_LOGGER.handlers
        self.status = f"diag2|{info}|handlers={[type(h).__name__ for h in handlers]}"

    @rx.event
    def chain(self):
        """Event chain: log then trigger increment."""
        user_logger.info("chain handler fired")
        yield LogState.increment()


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("Logging cluster test app", size="7"),
            rx.text("count: ", LogState.count, id="count"),
            rx.text(LogState.status, id="status"),
            rx.cond(
                LogState.bg_done,
                rx.text("background finished", id="bg-done"),
                rx.text("background pending", id="bg-pending"),
            ),
            rx.button("increment", id="btn-inc", on_click=LogState.increment),
            rx.button("background", id="btn-bg", on_click=LogState.bg_log),
            rx.button("chain", id="btn-chain", on_click=LogState.chain),
            rx.button("diag", id="btn-diag", on_click=LogState.diag),
            rx.button("diag2", id="btn-diag2", on_click=LogState.diag2),
            spacing="4",
        )
    )


app = rx.App()
app.add_page(index)

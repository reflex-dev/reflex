"""Errors: every way an awaited call can fail, and what the handler sees."""

import reflex as rx
from reflex.utils.exceptions import (
    BrowserDisconnectedError,
    BrowserResultSerializationError,
    BrowserScriptError,
    EventHandlerTypeError,
    EventHandlerValueError,
)

from .common import LogMixin, layout, row

# Label -> script whose awaited result raises. Each is caught and logged.
FAILING_SCRIPTS = {
    "throws": "missing_function()",
    "rejects": "Promise.reject(new Error('nope'))",
    "throws a non-Error": "(() => { throw 'a string' })()",
    "returns a DOM node": "document.body",
    "returns window": "window",
    "returns a function": "() => 1",
    "returns a symbol": "Symbol('x')",
    "returns 2MB": "'x'.repeat(2_000_000)",
    "nests 10k deep": "JSON.parse('['.repeat(10000) + ']'.repeat(10000))",
    "circular": "(() => { const a = {}; a.self = a; return a })()",
}


class ErrorState(LogMixin, rx.State):
    """State for the errors page."""

    @rx.event(background=True)
    async def fail(self, label: str):
        """Await a failing script and log the exception type and message."""
        async with self:
            self.mark()
        try:
            result = await rx.call_script(FAILING_SCRIPTS[label])
        except BrowserResultSerializationError as e:
            # Subclass of BrowserScriptError: the script ran, its value cannot travel.
            outcome = f"BrowserResultSerializationError: {e}"
        except BrowserScriptError as e:
            outcome = f"BrowserScriptError: {e}\n  name={e.name!r}\n  stack={e.stack[:120]!r}..."
        else:
            outcome = f"no error, got {result!r}"
        async with self:
            self.log(f"{label}: {outcome}")

    @rx.event(background=True)
    async def timeout_short(self):
        """Per-call timeout= beats rxconfig's browser_call_timeout."""
        async with self:
            self.mark()
        try:
            await rx.call_script("new Promise(() => {})", timeout=1.5)
        except TimeoutError as e:
            async with self:
                self.log(f"TimeoutError: {e}")

    @rx.event(background=True)
    async def late_result_dropped(self):
        """A result that arrives after the timeout is ignored, not misdelivered."""
        async with self:
            self.mark()
        try:
            await rx.call_script(
                "new Promise(r => setTimeout(() => r('too late'), 2000))", timeout=1
            )
        except TimeoutError:
            async with self:
                self.log("timed out at 1s; the 2s result will be dropped on arrival")
        value = await rx.call_script("'next call, right answer'")
        async with self:
            self.log(f"next awaited call got {value!r}")

    @rx.event(background=True)
    async def bad_timeout(self):
        """timeout= is validated when the EventSpec is built, before anything runs."""
        async with self:
            self.mark()
        for bad in (0, -1, float("inf"), float("nan")):
            try:
                rx.call_script("1", timeout=bad)
            except EventHandlerValueError as e:
                async with self:
                    self.log(f"timeout={bad}: EventHandlerValueError: {e}")

    @rx.event(background=True)
    async def callback_and_await(self):
        """Passing callback= and awaiting is a programming error."""
        async with self:
            self.mark()
        try:
            await rx.call_script("1", callback=ErrorState.clear)
        except EventHandlerTypeError as e:
            async with self:
                self.log(f"EventHandlerTypeError: {e}")

    @rx.event(background=True)
    async def await_under_lock(self):
        """Awaiting inside `async with self` is refused: it would block the tab."""
        async with self:
            self.mark()
            try:
                await rx.call_script("1")
            except EventHandlerTypeError as e:
                self.log(f"EventHandlerTypeError: {e}")

    @rx.event
    async def await_in_regular_handler(self):
        """A regular handler holds the lock too, so it gets the same refusal."""
        self.mark()
        try:
            await rx.call_script("1")
        except EventHandlerTypeError as e:
            self.log(f"EventHandlerTypeError: {e}")

    @rx.event(background=True)
    async def uncaught(self):
        """Nothing catches this one: see the backend console / exception handler."""
        async with self:
            self.mark()
            self.log("raising BrowserScriptError uncaught; check the terminal")
        await rx.call_script("throw new TypeError('uncaught on purpose')")

    @rx.event(background=True)
    async def disconnected_type(self):
        """BrowserDisconnectedError is a ConnectionError; see the Disconnects page."""
        async with self:
            self.mark()
            self.log(
                f"BrowserDisconnectedError bases: "
                f"{[c.__name__ for c in BrowserDisconnectedError.__mro__[1:4]]}"
            )


@rx.page(route="/errors", title="Await playground: errors")
def errors() -> rx.Component:
    """The errors page.

    Returns:
        The page.
    """
    return layout(
        ErrorState,
        "Errors",
        "Script failures surface as Python exceptions at the await. Each button is caught "
        "and logged, except 'Uncaught', which shows what an unhandled one looks like.",
        rx.text("Script errors and unserializable results", weight="bold"),
        row(
            *[
                rx.button(label, on_click=ErrorState.fail(label), variant="soft")
                for label in FAILING_SCRIPTS
            ]
        ),
        rx.text("Timeouts", weight="bold"),
        row(
            rx.button(
                "timeout=1.5 on a never-settling promise",
                on_click=ErrorState.timeout_short,
            ),
            rx.button(
                "Late result is dropped", on_click=ErrorState.late_result_dropped
            ),
            rx.button("Invalid timeout values", on_click=ErrorState.bad_timeout),
        ),
        rx.text("Misuse", weight="bold"),
        row(
            rx.button("callback= and await", on_click=ErrorState.callback_and_await),
            rx.button(
                "await inside async with self", on_click=ErrorState.await_under_lock
            ),
            rx.button(
                "await in a regular handler",
                on_click=ErrorState.await_in_regular_handler,
            ),
            rx.button("Uncaught", on_click=ErrorState.uncaught, color_scheme="red"),
            rx.button(
                "BrowserDisconnectedError MRO",
                on_click=ErrorState.disconnected_type,
                variant="outline",
            ),
        ),
    )

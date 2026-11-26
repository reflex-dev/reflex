"""Basics: await a script's result and get Python data back."""

import time

import reflex as rx
from reflex.utils.exceptions import BrowserScriptError

from .common import LogMixin, layout, row

# One value of each JSON type, plus the ones JSON cannot carry as themselves.
TYPES_JS = """({
    int: 1, float: 1.5, str: "text", bool: true, nil: null, undef: undefined,
    arr: [1, "two", undefined, null], nested: {a: {b: [{c: "deep"}]}},
    date: new Date(0), big: 2 ** 53,
})"""


class BasicsState(LogMixin, rx.State):
    """State for the basics page."""

    counter: rx.Field[int] = rx.field(7)

    @rx.event
    def increment(self):
        """Bump the counter the var-interpolation demo reads."""
        self.counter += 1

    @rx.event(background=True)
    async def measure(self):
        """Await an object: it arrives as a dict."""
        async with self:
            self.mark()
        size = await rx.call_script("({w: window.innerWidth, h: window.innerHeight})")
        async with self:
            self.log(f"viewport {size['w']} x {size['h']}  ({type(size).__name__})")

    @rx.event(background=True)
    async def round_trip_types(self):
        """Await every JSON type: null -> None, Date -> ISO string, undefined dropped."""
        async with self:
            self.mark()
        result = await rx.call_script(TYPES_JS)
        async with self:
            for key, value in result.items():
                self.log(f"{key:>7} = {value!r:<40} {type(value).__name__}")
            # JSON.stringify drops undefined object properties but nulls them in arrays.
            self.log(f"'undef' in result: {'undef' in result}")

    @rx.event(background=True)
    async def await_promise(self):
        """A promise's resolved value is the result; the handler waits for it."""
        async with self:
            self.mark()
            self.log("waiting on a 1.5s promise...")
        value = await rx.call_script(
            "new Promise(r => setTimeout(() => r('resolved after 1.5s'), 1500))"
        )
        async with self:
            self.log(value)

    @rx.event(background=True)
    async def chain(self):
        """Feed each awaited result into the next script: plain Python control flow."""
        async with self:
            self.mark()
        title = await rx.call_script("document.title")
        async with self:
            self.log(f"1. title = {title!r}")
        # Python data goes to the browser as a JS literal: repr() for simple
        # values, json.dumps() for anything else.
        length = await rx.call_script(f"{title!r}.length")
        async with self:
            self.log(f"2. length = {length}")
        shouted = await rx.call_function(f"() => {title!r}.toUpperCase() + '!'")
        async with self:
            self.log(f"3. shouted = {shouted!r}")
        # The three spellings: call_script evals an expression, call_function evals
        # to a function and calls it, run_script wraps a statement list in one.
        ua = await rx.call_function("() => navigator.userAgent.slice(0, 40)")
        lang = await rx.run_script("navigator.language")
        async with self:
            self.log(f"4. call_function {ua!r}, run_script {lang!r}")

    @rx.event(background=True)
    async def var_interpolation(self):
        """Vars in a script: a raw JS Var works, a state Var does not (gotcha)."""
        async with self:
            self.mark()
        cores = await rx.call_script(f"{rx.Var('navigator.hardwareConcurrency')} * 2")
        async with self:
            self.log(f"rx.Var('navigator.hardwareConcurrency') * 2 = {cores}")
        # A script sent from the backend is evaluated outside any component, so a
        # compiled state Var's React name is not in scope. Same as call_script
        # with a callback today; interpolate the Python value instead.
        try:
            await rx.call_script(f"{BasicsState.counter} * 2")
        except BrowserScriptError as e:
            async with self:
                self.log(f"BasicsState.counter in a script: {e}")
        doubled = await rx.call_script(f"{self.counter} * 2")
        async with self:
            self.log(f"f-string of self.counter ({self.counter}) * 2 = {doubled}")

    @rx.event(background=True)
    async def benchmark(self):
        """Round-trip latency of 20 sequential awaited calls."""
        n = 20
        async with self:
            self.mark()
        t0 = time.perf_counter()
        for i in range(n):
            await rx.call_script(f"{i}")
        elapsed = time.perf_counter() - t0
        async with self:
            self.log(
                f"{n} round trips in {elapsed * 1000:.0f} ms, "
                f"{elapsed / n * 1000:.1f} ms each"
            )

    @rx.event(background=True)
    async def streaming_progress(self):
        """Await in a loop and push each step to the UI as it arrives."""
        async with self:
            self.mark()
        for step in range(1, 6):
            ms = await rx.call_script(
                f"new Promise(r => setTimeout(() => r(performance.now()), {step * 200}))"
            )
            async with self:
                self.log(f"step {step}/5, performance.now() = {ms:.0f}")


@rx.page(route="/", title="Await playground: basics")
def basics() -> rx.Component:
    """The basics page.

    Returns:
        The page.
    """
    return layout(
        BasicsState,
        "Basics",
        "A background handler awaits rx.call_script / call_function / run_script "
        "and gets the script's value back as Python data, instead of wiring a callback.",
        row(
            rx.button("Measure viewport", on_click=BasicsState.measure),
            rx.button(
                "Round-trip every JSON type", on_click=BasicsState.round_trip_types
            ),
            rx.button("Await a promise", on_click=BasicsState.await_promise),
            rx.button("Chain three calls", on_click=BasicsState.chain),
        ),
        row(
            rx.button(
                "Await a script with Vars", on_click=BasicsState.var_interpolation
            ),
            rx.button(
                f"counter = {BasicsState.counter}, +1",
                on_click=BasicsState.increment,
                variant="soft",
            ),
        ),
        row(
            rx.button("Benchmark 20 round trips", on_click=BasicsState.benchmark),
            rx.button(
                "Stream progress from a loop", on_click=BasicsState.streaming_progress
            ),
        ),
    )

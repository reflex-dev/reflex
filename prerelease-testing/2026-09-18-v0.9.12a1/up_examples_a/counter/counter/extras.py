"""Extra page added by the 0.9.12a1 upgrade QA on top of the counter example.

Covers: uncached-var delta suppression (#6946), the router base-var split and the
`deps=["router"]` deprecation (#7068), `@rx.memo` wrapping a provider-backed
component (#7176), `rx._x.client_state`, `rx.ComponentState`, `rx.foreach`/`rx.cond`,
an event chain and a background task.
"""

import asyncio

import reflex as rx

from .counter import State as CounterState


class ExtraState(rx.State):
    """State exercising cached vs uncached computed vars and the router."""

    clicks: int = 0
    log: list[str] = []
    bg_ticks: int = 0

    @rx.var(cache=False)
    def bucket_uncached(self) -> int:
        """Changes only every 3 clicks.

        Returns:
            The click bucket.
        """
        return self.clicks // 3

    @rx.var(cache=True)
    def bucket_cached(self) -> int:
        """Same value, cached.

        Returns:
            The click bucket.
        """
        return self.clicks // 3

    @rx.var(cache=False)
    def clicks_uncached(self) -> int:
        """Changes on every click.

        Returns:
            The click count.
        """
        return self.clicks

    @rx.var(cache=True, deps=["router"])
    def current_path_legacy_deps(self) -> str:
        """Uses the deprecated `deps=["router"]` form on purpose.

        Returns:
            The current path.
        """
        return str(self.router.url.path)

    @rx.event
    def bump(self):
        """Increment the click counter."""
        self.clicks += 1

    @rx.event
    def chain(self):
        """Chain into another state's handler and then a background task.

        Yields:
            The chained events.
        """
        self.log.append(f"chain@{self.clicks}")
        yield CounterState.increment
        yield ExtraState.background_ticks

    @rx.event(background=True)
    async def background_ticks(self):
        """Tick three times from a background task."""
        for _ in range(3):
            await asyncio.sleep(0.3)
            async with self:
                self.bg_ticks += 1

    @rx.event
    async def handle_memo_upload(self, files: list[rx.UploadFile]):
        """Read files uploaded through the memoized upload component.

        Args:
            files: The uploaded files.
        """
        for file in files:
            data = await file.read()
            self.log.append(f"uploaded {file.name} {len(data)}b")


cs = rx._x.client_state(default="client-initial", var_name="extras_cs")


class Toggler(rx.ComponentState):
    """A ComponentState toggle to confirm per-instance substates still compile."""

    on: bool = False

    @rx.event
    def flip(self):
        """Flip the toggle."""
        self.on = not self.on

    @classmethod
    def get_component(cls, label: str, **props) -> rx.Component:
        """Build the toggle component.

        Args:
            label: Text shown on the button.
            props: Extra props for the wrapper.

        Returns:
            The rendered toggle.
        """
        return rx.hstack(
            rx.button(label, on_click=cls.flip, id=f"toggle-{label}"),
            rx.text(rx.cond(cls.on, "ON", "OFF"), id=f"togglestate-{label}"),
            **props,
        )


@rx.memo
def memo_upload(border: str) -> rx.Component:
    """An `rx.upload` inside an `rx.memo` -- provider-backed component, see #7176.

    Args:
        border: CSS border for the drop zone.

    Returns:
        The memoized upload component.
    """
    return rx.vstack(
        rx.upload(
            rx.text("drop here", id="memo-upload-text"),
            id="memo_upload",
            border=border,
            padding="1em",
        ),
        rx.button(
            "Memo Upload",
            id="memo-upload-btn",
            on_click=ExtraState.handle_memo_upload(
                rx.upload_files(upload_id="memo_upload")
            ),
        ),
    )


def extras() -> rx.Component:
    """The extras page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading("extras", size="5"),
        rx.hstack(
            rx.text("clicks:"),
            rx.text(ExtraState.clicks, id="clicks"),
            rx.text("uncached-bucket:"),
            rx.text(ExtraState.bucket_uncached, id="bucket-uncached"),
            rx.text("cached-bucket:"),
            rx.text(ExtraState.bucket_cached, id="bucket-cached"),
            rx.text("uncached-clicks:"),
            rx.text(ExtraState.clicks_uncached, id="clicks-uncached"),
        ),
        rx.hstack(
            rx.button("Bump", on_click=ExtraState.bump, id="bump"),
            rx.button("Chain", on_click=ExtraState.chain, id="chain"),
            rx.text("counter:"),
            rx.text(CounterState.count, id="counter-count"),
            rx.text("bg:"),
            rx.text(ExtraState.bg_ticks, id="bg-ticks"),
        ),
        rx.hstack(
            rx.text("legacy-deps-path:"),
            rx.text(ExtraState.current_path_legacy_deps, id="legacy-path"),
            rx.text("raw-path:"),
            rx.text(rx.State.router.url.path, id="raw-path"),
        ),
        rx.hstack(
            cs,
            rx.text(cs.value, id="cs-value"),
            rx.button(
                "set client state", id="cs-set", on_click=cs.set_value("client-updated")
            ),
        ),
        Toggler.create("a"),
        Toggler.create("b"),
        rx.vstack(
            rx.foreach(ExtraState.log, lambda entry: rx.text(entry, class_name="logentry"))
        ),
        rx.cond(
            ExtraState.clicks > 2,
            rx.text("many clicks", id="many"),
            rx.text("few clicks", id="few"),
        ),
        memo_upload(border="1px dashed green"),
        rx.link("home", href="/", id="home-link"),
        spacing="3",
        padding="2em",
    )

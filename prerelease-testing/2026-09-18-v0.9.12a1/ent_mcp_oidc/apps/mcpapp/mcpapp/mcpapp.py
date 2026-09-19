"""MCP plugin exercise app: substates, computed vars, memo, ComponentState, background events."""

import asyncio

import reflex as rx

import reflex_enterprise as rxe


class CounterState(rx.State):
    """Root-level counter with a computed var and an argument-taking handler."""

    count: int = 0
    label: str = "start"
    history: list[int] = []

    @rx.var
    def doubled(self) -> int:
        """Twice the count."""
        return self.count * 2

    @rx.var(cache=False)
    def uncached_marker(self) -> str:
        """An uncached computed var."""
        return f"c={self.count}"

    @rx.event
    def increment(self):
        """Bump the count by one."""
        self.count += 1
        self.history.append(self.count)

    @rx.event
    def add(self, amount: int):
        """Add an arbitrary amount to the count."""
        self.count += amount
        self.history.append(self.count)

    @rx.event
    def set_label(self, value: str):
        """Set the label."""
        self.label = value

    @rx.event(background=True)
    async def slow_bump(self):
        """Bump the count from a background task."""
        await asyncio.sleep(0.2)
        async with self:
            self.count += 100
            self.history.append(self.count)


class ProfileState(rx.State):
    """A second, sibling substate."""

    name: str = "anon"
    tags: list[str] = ["a", "b"]

    @rx.var
    def greeting(self) -> str:
        """Greeting derived from name."""
        return f"hello {self.name}"

    @rx.event
    def rename(self, name: str):
        """Rename the profile."""
        self.name = name


class ChildState(CounterState):
    """A child of CounterState to test nested state addressing."""

    note: str = ""

    @rx.var
    def note_upper(self) -> str:
        """Uppercased note."""
        return self.note.upper()

    @rx.event
    def set_note(self, note: str):
        """Set the note."""
        self.note = note


class MemoCounter(rx.ComponentState):
    """ComponentState instance state reachable over MCP."""

    ticks: int = 0

    @rx.event
    def tick(self):
        """Increment the per-instance tick counter."""
        self.ticks += 1

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        """Render the component."""
        return rx.vstack(
            rx.text(f"ticks: {cls.ticks}", id=props.pop("text_id", "cs-text")),
            rx.button("tick", on_click=cls.tick, id=props.pop("btn_id", "cs-btn")),
            **props,
        )


@rx.memo
def memo_row(value: int, label: str) -> rx.Component:
    """A memoized row."""
    return rx.hstack(rx.text(f"{label}:"), rx.text(value.to_string()))


def index() -> rx.Component:
    """Index page."""
    return rx.container(
        rx.vstack(
            rx.heading("MCP plugin exercise"),
            rx.text(CounterState.count, id="count"),
            rx.text(CounterState.doubled, id="doubled"),
            rx.text(CounterState.uncached_marker, id="uncached"),
            rx.text(ProfileState.greeting, id="greeting"),
            rx.text(ChildState.note_upper, id="note-upper"),
            memo_row(value=CounterState.count, label="memo"),
            MemoCounter.create(),
            rx.button("inc", on_click=CounterState.increment, id="inc"),
            rx.button("bg", on_click=CounterState.slow_bump, id="bg"),
        )
    )


app = rxe.App()
app.add_page(index)

"""Multi-var, multi-state app for the FINDING-030 delta-ordering comparison."""

import reflex as rx


class Counter(rx.State):
    """Several vars plus cached and uncached computed vars."""

    count: int = 0
    label: str = "start"
    history: list[int] = []
    flags: dict[str, bool] = {"a": True}

    @rx.var
    def doubled(self) -> int:
        """Twice the count."""
        return self.count * 2

    @rx.var(cache=False)
    def marker(self) -> str:
        """An uncached marker."""
        return f"c={self.count}"

    @rx.event
    def bump(self):
        """Mutate several vars at once, and a sibling state."""
        self.count += 1
        self.label = f"n{self.count}"
        self.history.append(self.count)
        self.flags = {"a": not self.flags["a"], "b": True}


class Sibling(rx.State):
    """A second state mutated by the same event chain."""

    seen: int = 0
    note: str = ""

    @rx.var
    def note_upper(self) -> str:
        """Uppercased note."""
        return self.note.upper()

    @rx.event
    def touch(self):
        """Mutate this state too."""
        self.seen += 1
        self.note = f"seen{self.seen}"


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(
        rx.text(Counter.count, id="count"),
        rx.text(Counter.doubled, id="doubled"),
        rx.text(Counter.marker, id="marker"),
        rx.text(Counter.label, id="label"),
        rx.text(Sibling.note_upper, id="note"),
        rx.button("bump", id="btn-en", on_click=[Counter.bump, Sibling.touch]),
        rx.text("ready", id="ready"),
    )


app = rx.App()
app.add_page(index, route="/reactive")
app.add_page(index, route="/")

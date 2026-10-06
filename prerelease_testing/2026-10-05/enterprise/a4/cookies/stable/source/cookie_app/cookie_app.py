"""Exercise HTTP-only cookie descriptors through real State events."""

import reflex as rx
from reflex_enterprise.auth.cookie import HTTPCookie


class CookieState(rx.State):
    """Own two fictional HTTP-only cookies and their mutation controls."""

    _first: HTTPCookie = HTTPCookie("", name="qa_first", secure=False)
    _second: HTTPCookie = HTTPCookie("", name="qa_second", secure=False)
    generation: int = 0
    reads: int = 0

    @rx.var
    def first(self) -> str:
        """Return the synthetic first cookie value for the test view."""
        return str(self._first)

    @rx.var
    def second(self) -> str:
        """Return the synthetic second cookie value for the test view."""
        return str(self._second)

    @rx.event
    def set_pair(self) -> None:
        """Set two cookies in one event to exercise concurrent sync triggers."""
        self.generation += 1
        self._first = f"first-{self.generation}"
        self._second = f"second-{self.generation}"

    @rx.event
    def read(self) -> None:
        """Mark completion of an explicit browser-to-server cookie sync."""
        self.reads += 1

    @rx.event
    def clear_pair(self) -> None:
        """Explicitly delete the synthetic cookies rather than resetting State."""
        del self._first
        del self._second

    @rx.event
    def reset_backend_state(self) -> None:
        """Reset ordinary State through a registered event handler."""
        self.reset()


class ChildCookieState(CookieState):
    """Read an inherited cookie through a cached computed value."""

    @rx.var
    def inherited(self) -> str:
        """Return a label that must invalidate when the parent cookie changes."""
        return "child:" + str(self._first)


@rx.memo
def inherited_view(value: rx.Var[str]) -> rx.Component:
    """Render an inherited computed cookie value inside a memo component.

    Args:
        value: Synthetic inherited-cookie label.

    Returns:
        The visible test value.
    """
    return rx.text(value, id="inherited")


def index() -> rx.Component:
    """Render controls and computed values for browser assertions.

    Returns:
        The cookie exploration page.
    """
    return rx.vstack(
        rx.heading("HTTP cookie QA"),
        rx.text(CookieState.first, id="first"),
        rx.text(CookieState.second, id="second"),
        inherited_view(value=ChildCookieState.inherited),
        rx.text(CookieState.reads, id="reads"),
        rx.button("Set pair", on_click=CookieState.set_pair),
        rx.button("Sync browser", on_click=HTTPCookie.sync(callback=CookieState.read)),
        rx.button("Delete pair", on_click=CookieState.clear_pair),
        rx.button("Reset State", on_click=CookieState.reset_backend_state),
    )


app = rx.App()
app.add_page(index)

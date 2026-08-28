"""Test app for the @rx.memo auto-memoization cluster (reflex 0.9.9a1).

Covers:
- #6949 auto-memoization: memo call sites with state-bound props compile state
  hooks into a generated wrapper; page function must not re-render on state
  changes; inner memo re-renders only when its prop values change.
- #6605 RestProp CSS classification: undeclared props (font_weight=) forwarded
  through rx.RestProp become styles, merged with explicit style=.
- #6945 displayName: memo components, contexts, pages (route label),
  NoSSRComponent ClientSide(<Tag>) wrappers.
- #6730 wrapper= config on @rx.memo.
- Combinations: memo in rx.foreach, memo + client_state var, memo wrapping a
  ComponentState instance, two memos sharing a name across modules.

Render counting: see probe.py — globalThis.__renders[name] counts renders of
each rendering domain.
"""

import reflex as rx
from reflex.event import passthrough_event_spec

from .mod_a import badge as badge_a
from .mod_b import badge as badge_b
from .probe import probe, probe_var


class ABState(rx.State):
    """Two independent vars in the same state, plus an event recorder."""

    a: str = "a0"
    b: str = "b0"
    a_n: int = 0
    b_n: int = 0
    last_event: str = ""

    @rx.event
    def bump_a(self):
        """Change var a only."""
        self.a_n += 1
        self.a = f"a{self.a_n}"

    @rx.event
    def bump_b(self):
        """Change var b only."""
        self.b_n += 1
        self.b = f"b{self.b_n}"

    @rx.event
    def record(self, value: str):
        """Record an event payload sent from a memo's EventHandler prop.

        Args:
            value: The payload.
        """
        self.last_event = value


class ListState(rx.State):
    """Backs the rx.foreach of memo rows."""

    items: list[str] = ["red", "green", "blue"]

    @rx.event
    def reverse(self):
        """Reverse the items."""
        self.items = list(reversed(self.items))

    @rx.event
    def append_item(self):
        """Append a new item."""
        self.items = [*self.items, f"item{len(self.items)}"]


class CounterCS(rx.ComponentState):
    """Per-instance counter used inside a memo body."""

    count: int = 0

    @rx.event
    def increment(self):
        """Increment the counter."""
        self.count += 1

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        """Build the counter UI.

        Args:
            props: Extra props for the root div.

        Returns:
            The counter component.
        """
        return rx.el.div(
            rx.el.span(cls.count, id="ccs-count"),
            rx.el.button("ccs+", id="ccs-btn", on_click=cls.increment),
            **props,
        )


clicks = rx._x.client_state(default=0, var_name="clicks")


@rx.memo
def memo_one(
    text: rx.Var[str],
    marker: rx.Var[str],
    on_ping: rx.EventHandler[passthrough_event_spec(str)],
) -> rx.Component:
    """Memo with a state-bound prop AND an event handler prop.

    Args:
        text: State-bound text.
        marker: Probe var whose hook counts the auto-memo wrapper's renders.
        on_ping: Event handler prop.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(text, id="one-text"),
        rx.el.button("ping", id="one-btn", on_click=on_ping("pinged-from-one")),
        probe("body_one"),
        custom_attrs={"data-marker": marker},
        id="memo-one",
    )


@rx.memo
def memo_two(text: rx.Var[str], marker: rx.Var[str]) -> rx.Component:
    """Memo bound to ABState.b — must NOT re-render when only a changes.

    Args:
        text: State-bound text.
        marker: Probe var whose hook counts the auto-memo wrapper's renders.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(text, id="two-text"),
        probe("body_two"),
        custom_attrs={"data-marker": marker},
        id="memo-two",
    )


@rx.memo
def memo_status(last: rx.Var[str]) -> rx.Component:
    """Displays the last recorded event payload.

    Args:
        last: The payload var.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(last, id="last-event"),
        probe("body_status"),
    )


@rx.memo
def memo_row(label: rx.Var[str]) -> rx.Component:
    """Row memo used under rx.foreach.

    Args:
        label: Row label.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(label, class_name="row-label"),
        probe("body_row"),
        class_name="memo-row",
    )


@rx.memo
def memo_cs(count: rx.Var[int]) -> rx.Component:
    """Memo receiving a client_state (ClientStateVar) value.

    Args:
        count: The client-state click count.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(count, id="cs-count"),
        probe("body_cs"),
        id="memo-cs",
    )


@rx.memo
def counter_island(title: rx.Var[str]) -> rx.Component:
    """Memo whose body instantiates a ComponentState counter.

    Args:
        title: State-bound title.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(title, id="island-title"),
        CounterCS.create(id="ccs-root"),
        probe("body_island"),
        id="counter-island",
    )


@rx.memo
def styled_note(text: rx.Var[str], rest: rx.RestProp) -> rx.Component:
    """Memo forwarding undeclared props via RestProp (#6605).

    Args:
        text: Note text.
        rest: Forwarded rest props.

    Returns:
        The component.
    """
    return rx.el.div(rx.el.span(text, class_name="note-text"), rest)


@rx.memo(wrapper=None)
def unwrapped_label(value: rx.Var[str]) -> rx.Component:
    """Memo compiled WITHOUT the React memo wrapper (#6730 wrapper=None).

    Args:
        value: State-bound text.

    Returns:
        The component.
    """
    return rx.el.div(
        rx.el.span(value, id="unwrapped-value"),
        probe("body_unwrapped"),
        id="unwrapped-label",
    )


@rx.memo
def token_display(token: rx.Var[str]) -> rx.Component:
    """Shows the websocket client token (hydration/connection signal).

    Args:
        token: The client token var.

    Returns:
        The component.
    """
    return rx.el.input(value=token, read_only=True, id="token")


def index() -> rx.Component:
    """Main page.

    Returns:
        The page component.
    """
    return rx.el.div(
        probe("page"),
        token_display(token=rx.State.router.session.client_token),
        rx.el.span("static sibling", id="static-sibling"),
        rx.el.div(
            rx.el.button("bump a", id="bump-a", on_click=ABState.bump_a),
            rx.el.button("bump b", id="bump-b", on_click=ABState.bump_b),
            rx.el.button("reverse", id="reverse", on_click=ListState.reverse),
            rx.el.button("append", id="append", on_click=ListState.append_item),
            rx.el.button(
                "cs+", id="cs-btn", on_click=clicks.set_value(clicks.value + 1)
            ),
        ),
        memo_one(
            text=ABState.a,
            marker=probe_var("wrapper_one"),
            on_ping=ABState.record,
        ),
        memo_two(text=ABState.b, marker=probe_var("wrapper_two")),
        memo_status(last=ABState.last_event),
        rx.el.div(
            rx.foreach(ListState.items, lambda item: memo_row(label=item)),
            id="rows",
        ),
        memo_cs(count=clicks.value),
        counter_island(title=ABState.a),
        styled_note(
            text="styled!",
            id="styled-note",
            class_name="note-extra",
            title="notetitle",
            font_weight="bold",
            style={"padding": "10px", "font_style": "italic"},
        ),
        unwrapped_label(value=ABState.a),
        rx.el.div(
            badge_a(label=ABState.a),
            badge_b(label=ABState.b),
            id="badges",
        ),
        rx.moment("2026-08-28T12:00:00Z", format="YYYY", id="moment"),
        id="page-root",
    )


def about() -> rx.Component:
    """Secondary page (route displayName check).

    Returns:
        The page component.
    """
    return rx.el.div(
        rx.el.span("about page", id="about-marker"),
        memo_two(text=ABState.b, marker=probe_var("wrapper_two_about")),
        id="about-root",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(about, route="/about")

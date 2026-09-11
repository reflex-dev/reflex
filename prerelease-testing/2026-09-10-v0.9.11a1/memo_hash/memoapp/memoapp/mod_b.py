"""Module B: a same-named ``@rx.memo`` and ``ComponentState``.

Generated from ``mod_template.py.in``; ``mod_a.py`` and ``mod_b.py`` differ only
in the substituted marker, so the two ``card`` memos have the same function
name and the same JSX shape and differ only in the handler they bind.
"""

import reflex as rx


class StateB(rx.State):
    """Per-module state; the only thing that differs between the two cards."""

    clicks: int = 0

    @rx.event
    def bump(self):
        """Bump this module's counter."""
        self.clicks += 10


@rx.memo
def card(label: str) -> rx.Component:
    """A memo with the same name in both modules and the same JSX shape.

    Args:
        label: The button label.

    Returns:
        The button.
    """
    return rx.el.button(label, on_click=StateB.bump, class_name="memo-card")


class Counter(rx.ComponentState):
    """A same-named ComponentState in both modules; only the step differs."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment by this module's step."""
        self.count += 10

    @classmethod
    def get_component(cls, **props):
        """Render the counter.

        Args:
            props: Extra props.

        Returns:
            The component.
        """
        return rx.el.div(
            rx.el.button("inc", on_click=cls.inc, id=props.pop("btn_id", None)),
            rx.el.span(cls.count.to_string(), id=props.pop("out_id", None)),
            **props,
        )


class CounterB(rx.ComponentState):
    """Distinctly-named twin of ``Counter``.

    ``Counter`` has the same class name in both modules, and reflex derives the
    dynamic substate name from ``cls.__name__`` alone, so instantiating both
    raises ``StateValueError`` (see NOTES.md, ISSUE cs-name-collision). This
    twin lets the app still exercise ComponentState inside a memo.
    """

    count: int = 0

    @rx.event
    def inc(self):
        """Increment by this module's step."""
        self.count += 10

    @classmethod
    def get_component(cls, **props):
        """Render the counter.

        Args:
            props: Extra props.

        Returns:
            The component.
        """
        return rx.el.div(
            rx.el.button("inc", on_click=cls.inc, id=props.pop("btn_id", None)),
            rx.el.span(cls.count.to_string(), id=props.pop("out_id", None)),
            **props,
        )

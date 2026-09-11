"""Left-hand widget module, written by a user."""

import reflex as rx


class Counter(rx.ComponentState):
    """A counter widget."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1

    @classmethod
    def get_component(cls, **props):
        """Render the counter.

        Args:
            props: Extra props.

        Returns:
            The component.
        """
        return rx.el.div(
            rx.el.button("inc A", on_click=cls.inc, id="btn-a"),
            rx.el.span(cls.count.to_string(), id="out-a"),
            **props,
        )

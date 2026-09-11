"""Module one: defines a ComponentState named Counter."""

import reflex as rx


class Counter(rx.ComponentState):
    """A counter."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1

    @classmethod
    def get_component(cls, **props):
        """Render.

        Args:
            props: extra props.

        Returns:
            The component.
        """
        return rx.el.div(
            rx.el.button("inc-one", on_click=cls.inc),
            rx.el.span(cls.count.to_string()),
            **props,
        )

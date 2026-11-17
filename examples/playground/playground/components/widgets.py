"""Reusable widgets: a custom React component, memoized components and a component with its own state."""

import reflex as rx


class LiveClock(rx.Component):
    """A ticking clock: a React component defined in custom code, with a page hook."""

    tag = "PlaygroundClock"

    def add_imports(self) -> dict[str, list[rx.ImportVar]]:
        """Import the React hooks the custom code and the page hook use.

        Returns:
            The imports.
        """
        return {
            "react": [
                rx.ImportVar(tag="createElement"),
                rx.ImportVar(tag="useEffect"),
                rx.ImportVar(tag="useState"),
            ]
        }

    def add_custom_code(self) -> list[str]:
        """Define the clock component at the page module's top level.

        Returns:
            The component's JavaScript.
        """
        return [
            """function PlaygroundClock(props) {
  // Empty until mounted, so the prerendered page matches the first render.
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString());
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, []);
  return createElement("span", props, now);
}"""
        ]

    def add_hooks(self) -> list[str | rx.Var]:
        """Mark the document once the page rendering the clock mounted.

        Returns:
            The hook.
        """
        return [
            "useEffect(() => { document.documentElement.dataset.playgroundClock = 'mounted'; }, []);"
        ]


@rx.memo
def stat_card(label: rx.Var[str], value: rx.Var[str]) -> rx.Component:
    """Render a labelled value, memoized so it renders again only when its props change.

    Args:
        label: What the value is.
        value: The value.

    Returns:
        A card.
    """
    return rx.card(
        rx.vstack(
            rx.text(label, size="1", color_scheme="gray"),
            rx.text(value, size="5", weight="bold"),
            spacing="1",
        ),
        class_name="min-w-32",
    )


class Stepper(rx.ComponentState):
    """A counter with its own state per instance on the page."""

    value: int = 0

    @rx.event
    def step(self, delta: int):
        """Move the counter.

        Args:
            delta: How far.
        """
        self.value += delta

    @classmethod
    def get_component(cls, **props) -> rx.Component:
        """Render one stepper.

        Args:
            **props: ``label`` and ``prefix`` (the prefix of the element ids).

        Returns:
            The label, the value and the buttons.
        """
        label, prefix = props.pop("label"), props.pop("prefix")
        return rx.hstack(
            rx.text(label, weight="medium"),
            rx.button("-", on_click=cls.step(-1), id=f"{prefix}-decrement"),
            rx.text(cls.value, id=f"{prefix}-value"),
            rx.button("+", on_click=cls.step(1), id=f"{prefix}-increment"),
            align="center",
        )

---
components:
    - rx.segmented_control.root
    - rx.segmented_control.item
---

```python exec
import reflex as rx

class SegmentedState(rx.State):
    """The app state."""

    control: str = "test"

    @rx.event
    def set_control(self, value: str | list[str]):
        self.control = value


```

# Segmented Control

Segmented Control offers a clear and accessible way to switch between predefined values and views, e.g., "Inbox," "Drafts," and "Sent."

With Segmented Control, you can make mutually exclusive choices, where only one option can be active at a time, clear and accessible. Without Segmented Control, end users might have to deal with controls like dropdowns or multiple buttons that don't clearly convey state or group options together visually.

## Basic Example

The `Segmented Control` component is made up of a `rx.segmented_control.root` which groups `rx.segmented_control.item`.

The `rx.segmented_control.item` components define the individual segments of the control, each with a label and a unique value.

```python demo
rx.vstack(
    rx.segmented_control.root(
        rx.segmented_control.item("Home", value="home"),
        rx.segmented_control.item("About", value="about"),
        rx.segmented_control.item("Test", value="test"),
        on_change=SegmentedState.set_control,
        value=SegmentedState.control,
    ),
    rx.card(
        rx.text(SegmentedState.control, align="left"),
        rx.text(SegmentedState.control, align="center"),
        rx.text(SegmentedState.control, align="right"),
        width="100%",
    ),
)
```

**In the example above:**

`on_change` is used to specify a callback function that will be called when the user selects a different segment. In this case, the `SegmentedState.setvar("control")` function is used to update the `control` state variable when the user changes the selected segment.

`value` prop is used to specify the currently selected segment, which is bound to the `SegmentedState.control` state variable.

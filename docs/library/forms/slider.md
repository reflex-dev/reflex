---
components:
  - rx.slider

Slider: |
  lambda **props: rx.center(rx.slider(default_value=40, height="100%", **props), height="4em", width="100%")
---

```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# Slider

Provides user selection from a range of values. The

## Basic Example

The slider can be controlled by a single value or a range of values. Slider can be hooked to state to control its value. Passing a list of two values creates a range slider.

```python demo exec
class SliderState(rx.State):
    value: int = 50

    @rx.event
    def set_end(self, value: list[int | float]):
        self.value = value[0]

def slider_intro():
    return rx.vstack(
        rx.heading(SliderState.value),
        rx.slider(on_value_commit=SliderState.set_end),
        width="100%",
    )
```

## Range Slider

Range slider is created by passing a list of two values to the `default_value` prop. The list should contain two values that are in the range of the slider.

```python demo exec
class RangeSliderState(rx.State):
    value_start: int = 25
    value_end: int = 75

    @rx.event
    def set_end(self, value: list[int | float]):
        self.value_start = value[0]
        self.value_end = value[1]

def range_slider_intro():
    return rx.vstack(
        rx.hstack(
            rx.heading(RangeSliderState.value_start),
            rx.heading(RangeSliderState.value_end),
        ),
        rx.slider(
            default_value=[25, 75],
            min_=0,
            max=100,
            size="1",
            on_value_commit=RangeSliderState.set_end,
        ),
        width="100%",
    )
```

## Live Updating Slider

You can use the `on_change` prop to update the slider value as you interact with it. The `on_change` prop takes a function that will be called with the new value of the slider.

Here we use the `throttle` method to limit the rate at which the function is called, which is useful to prevent excessive updates. In this example, the slider value is updated every 100ms.

```python demo exec
class LiveSliderState(rx.State):
    value: int = 50

    @rx.event
    def set_end(self, value: list[int | float]):
        self.value = value[0]

def live_slider_intro():
    return rx.vstack(
        rx.heading(LiveSliderState.value),
        rx.slider(
            default_value=50,
            min_=0,
            max=100,
            on_change=LiveSliderState.set_end.throttle(100),
        ),
        width="100%",
    )
```

## Slider in forms

Here we show how to use a slider in a form. We use the `name` prop to identify the slider in the form data. The form data is then passed to the `handle_submit` method to be processed.

```python demo exec
class FormSliderState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def slider_form_example():
    return rx.card(
            rx.vstack(
                rx.heading("Example Form"),
                rx.form.root(
                    rx.hstack(
                        rx.slider(default_value=40, name="slider"),
                        rx.button("Submit", type="submit"),
                        width="100%",
                    ),
                    on_submit=FormSliderState.handle_submit,
                    reset_on_submit=True,
                ),
                rx.divider(),
                rx.hstack(
                    rx.heading("Results:"),
                    rx.badge(FormSliderState.form_data.to_string()),
                ),
                align_items="left",
                width="100%",
            ),
        width="50%",
    )
```

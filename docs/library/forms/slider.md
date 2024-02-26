---
components:
    - rx.radix.slider

Slider: |
    lambda **props: rx.radix.themes.slider(default_value=40, height="50%", **props)

---


```python exec
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# Slider

Provides user selection from a range of values.

## Basic Example

```python demo
rx.slider(default_value=40)
```

### Setting slider defaults

We can set the `min` and `max` values for the range of the slider. The defaults for `min` and `max` are 0 and 100.

The stepping interval can also be adjusted by using the `step` prop. It defaults to 1.

The `on_value_commit` event is called when the value changes at the end of an interaction. Useful when you only need to capture a final value e.g. to update a backend service.

```python demo exec
class SliderVariationState(rx.State):
    value: int = 50

    def set_end(self, value: int):
        self.value = value

def slider_max_min_step():
    return rx.vstack(
        rx.heading(SliderVariationState.value),
        rx.text("Min=20 Max=240"),
        rx.slider(default_value=40, min=20, max=240, on_value_commit=SliderVariationState.set_end),
        rx.text("Step=5"),
        rx.slider(default_value=40, step=5, on_value_commit=SliderVariationState.set_end),
        rx.text("Step=0.5"),
        rx.slider(default_value=40, step=0.5, on_value_commit=SliderVariationState.set_end),
        width="100%",
    )
```

### Disabling

When the `disabled` prop is set to `True`, it prevents the user from interacting with the slider.

```python demo
rx.slider(default_value=40, disabled=True)
```

### Control the value

The `default_value` is the value of the slider when initially rendered. It can be a `float` or if multiple thumbs to drag are required then it can be passed as a `List[float]`. Providing multiple values creates a range slider.

```python demo
rx.slider(default_value=45.5)
```

```python demo
rx.slider(default_value=[40, 60])
```

The `on_change` event is called when the `value` of the slider changes.

```python demo exec
class SliderVariationState2(rx.State):
    value: int = 50

    def set_end(self, value: int):
        self.value = value


def slider_on_change():
    return rx.vstack(
        rx.heading(SliderVariationState2.value),
        rx.slider(default_value=40, on_change=SliderVariationState2.set_end),
        width="100%",
    )
```

### Submitting a form using slider

The `name` of the slider. Submitted with its owning form as part of a name/value pair.

```python demo exec
class FormSliderState(rx.State):
    form_data: dict = {}

    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def form_example2():
    return rx.vstack(
        rx.form.root(
            rx.vstack(
                rx.slider(default_value=40, name="slider"),
                rx.button("Submit", type="submit"),
                width="100%",
            ),
            on_submit=FormSliderState.handle_submit,
            reset_on_submit=True,
            width="100%",
        ),
        rx.chakra.divider(),
        rx.heading("Results"),
        rx.text(FormSliderState.form_data.to_string()),
        width="100%",
    )
```

### Orientation

Use the `orientation` prop to change the orientation of the slider.

```python demo
rx.slider(default_value=40, orientation="horizontal")
```

```python demo
rx.slider(default_value=40, height="4em", orientation="vertical")
```

## Styling

```python eval
style_grid(component_used=rx.slider, component_used_str="slider", variants=["classic", "surface", "soft"], disabled=True, default_value=40)
```

### size

```python demo
rx.flex(
    rx.slider(default_value=25, size="1"),
    rx.slider(default_value=25, size="2"),
    rx.slider(default_value=25, size="3"),
    direction="column",
    spacing="4",
    width="100%",
)
```

### high contrast

```python demo
rx.flex(
    rx.slider(default_value=25),
    rx.slider(default_value=25, high_contrast=True),
    direction="column",
    spacing="4",
    width="100%",
)
```

### radius

```python demo
rx.flex(
    rx.slider(default_value=25, radius="none"),
    rx.slider(default_value=25, radius="small"),
    rx.slider(default_value=25, radius="full"),
    direction="column",
    spacing="4",
    width="100%",
)
```

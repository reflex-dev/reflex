---
components:
    - rx.chakra.Slider
    - rx.chakra.SliderTrack
    - rx.chakra.SliderFilledTrack
    - rx.chakra.SliderThumb
    - rx.chakra.SliderMark
---

```python exec
import reflex as rx
```

# Slider

The Slider is used to allow users to make selections from a range of values.

```python demo exec
class SliderState(rx.State):
    value: int = 50


def slider_example():
    return rx.chakra.vstack(
        rx.chakra.heading(SliderState.value),
        rx.chakra.slider(
            on_change=SliderState.set_value
        ),
        width="100%",
    )
```

You can also combine all three event handlers: `on_change`, `on_change_start`, and `on_change_end`.

```python demo exec
class SliderCombo(rx.State):
    value: int = 50
    color: str = "black"

    def set_start(self, value):
        self.color = "#68D391" 

    def set_end(self, value):
        self.color = "#F56565" 


def slider_combo_example():
    return rx.chakra.vstack(
        rx.chakra.heading(SliderCombo.value, color=SliderCombo.color),
        rx.chakra.slider(
            on_change_start=SliderCombo.set_start,
            on_change=SliderCombo.set_value,
            on_change_end=SliderCombo.set_end,
        ),
        width="100%",
    )
```

You can also customize the appearance of the slider by passing in custom components for the track and thumb.

```python demo exec
class SliderManual(rx.State):
    value: int = 50

    def set_end(self, value: int):
        self.value = value


def slider_manual_example():
    return rx.chakra.vstack( 
        rx.chakra.heading(f"Weather is {SliderManual.value} degrees"),
        rx.chakra.slider(
            rx.chakra.slider_track(
                rx.chakra.slider_filled_track(bg="tomato"),
                bg='red.100'
            ),
            rx.chakra.slider_thumb(
                rx.chakra.icon(tag="sun", color="white"),
                box_size="1.5em",
                bg="tomato",
            ),
            on_change_end=SliderManual.set_end,
        ),
        width="100%",
    )
```

If you want to trigger state change on every slider movement, you can use the `on_change` event handler.

For performance reasons, you may want to trigger state change only when the user releases the slider by using the `on_change_end` event handler, but if you need perform an event on every slider movement, you can use the `on_change` event handler.

```python demo
rx.chakra.vstack(
    rx.chakra.heading(SliderState.value),
    rx.chakra.slider(
        on_change=SliderState.set_value
    ),
    width="100%",
)
```

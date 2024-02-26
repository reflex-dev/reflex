---
components:
    - rx.chakra.PinInput
---

```python exec
import reflex as rx
```

# PinInput

The PinInput component is similar to the Input component, but it is optimized for entering sequences of digits

```python demo exec
class PinInputState(rx.State):
    pin: str


def basic_pininput_example():
    return rx.chakra.vstack(
        rx.chakra.heading(PinInputState.pin),
        rx.chakra.box(
            rx.chakra.pin_input(
                length=4,
                on_change=PinInputState.set_pin,
                mask=True,
            ),
        ),
    )
```

The PinInput component can also be customized as seen below.

```python demo
rx.chakra.center(
    rx.chakra.pin_input(
        rx.chakra.pin_input_field(color="red"),
        rx.chakra.pin_input_field(border_color="green"),
        rx.chakra.pin_input_field(shadow="md"),
        rx.chakra.pin_input_field(color="blue"),
        rx.chakra.pin_input_field(border_radius="md"),
        on_change=PinInputState.set_pin,
    )
)
```

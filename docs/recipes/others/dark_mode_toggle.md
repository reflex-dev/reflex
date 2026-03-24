```python exec
import reflex as rx
from reflex.style import set_color_mode, color_mode
```

# Dark Mode Toggle

The Dark Mode Toggle component lets users switch between light and dark themes.

```python demo exec toggle
import reflex as rx
from reflex.style import set_color_mode, color_mode

def dark_mode_toggle() -> rx.Component:
    return rx.segmented_control.root(
        rx.segmented_control.item(
            rx.icon(tag="monitor", size=20),
            value="system",
        ),
        rx.segmented_control.item(
            rx.icon(tag="sun", size=20),
            value="light",
        ),
        rx.segmented_control.item(
            rx.icon(tag="moon", size=20),
            value="dark",
        ),
        on_change=set_color_mode,
        variant="classic",
        radius="large",
        value=color_mode,
    )
```

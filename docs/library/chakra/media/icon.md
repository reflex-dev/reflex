---
components:
    - rx.chakra.Icon
---

```python exec
import reflex as rx
from reflex.components.media.icon import ICON_LIST
```

# Icon

The Icon component is used to display an icon from a library of icons.

```python demo
rx.chakra.icon(tag="calendar")
```

Use the tag prop to specify the icon to display.

```md alert success
Below is a list of all available icons.
```

```python eval
rx.chakra.box(
    rx.chakra.divider(),
    rx.chakra.responsive_grid(
        *[
            rx.chakra.vstack(
                rx.chakra.icon(tag=icon),
                rx.chakra.text(icon),
                bg="white",
                border="1px solid #EAEAEA",
                border_radius="0.5em",
                padding=".75em",
            )
            for icon in ICON_LIST
        ],
        columns=[2, 2, 3, 3, 4],
        spacing="1em",
    )
)
```

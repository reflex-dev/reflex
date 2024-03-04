---
components:
    - rx.radix.drawer.root
    - rx.radix.drawer.trigger
    - rx.radix.drawer.overlay
    - rx.radix.drawer.portal
    - rx.radix.drawer.content
    - rx.radix.drawer.close

only_low_level:
    - True
---

```python exec
import reflex as rx
```


# Drawer

```python demo
rx.drawer.root(
        rx.drawer.trigger(
            rx.button("Open Drawer")    
        ),
        rx.drawer.overlay(),
        rx.drawer.portal(
            rx.drawer.content(
                rx.flex(
                    rx.drawer.close(rx.box(rx.button("Close"))),
                    align_items="start",
                    direction="column",
                ),
                top="auto",
                right="auto",
                height="100%",
                width="20em",
                padding="2em",
                background_color="#FFF"
                #background_color=rx.color("green", 3)
            )
        ),
        direction="left",
)
```
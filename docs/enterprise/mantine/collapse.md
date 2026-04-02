---
title: Collapse
---

# Collapse component

`rxe.mantine.collapse` is a component that allows you to create collapsible sections in your application. It is useful for hiding or showing content based on user interaction, such as clicking a button or a link.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class CollapseState(rx.State):
    is_open: bool = False

    @rx.event
    def toggle_collapse(self):
        self.is_open = not self.is_open

def collapse_example():
    return rx.vstack(
        rxe.mantine.collapse(
            rx.text(
                "This is a collapsible section. Click the button to toggle the collapse.",
                font_size="lg",
            ),
            in_=CollapseState.is_open,
            label="Collapsible Section",
            description="Click the button to toggle the collapse.",
        ),
        rx.button(
            "Toggle Collapse", 
            on_click=lambda: CollapseState.toggle_collapse,
        ),
    )
```

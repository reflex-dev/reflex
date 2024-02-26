---
components:
    - rx.chakra.Accordion
    - rx.chakra.AccordionItem
    - rx.chakra.AccordionButton
    - rx.chakra.AccordionPanel
    - rx.chakra.AccordionIcon
---

```python exec
import reflex as rx
```

# Accordion

Accordions allow you to hide and show content in a container under a header.

Accordion consist of an outer accordion component and inner accordion items.
Each item has a optional button and panel. The button is used to toggle the panel's visibility.

```python demo
rx.chakra.accordion(
    rx.chakra.accordion_item(
        rx.chakra.accordion_button(
            rx.chakra.heading("Example"),
            rx.chakra.accordion_icon(),
        ),
        rx.chakra.accordion_panel(
            rx.chakra.text("This is an example of an accordion component.")
        )
    ),
    allow_toggle = True,
    width = "100%"
)
```

An accordion can have multiple items.

```python demo
rx.chakra.accordion(
    rx.chakra.accordion_item(
        rx.chakra.accordion_button(
            rx.chakra.heading("Example 1"),
            rx.chakra.accordion_icon(),
        ),
        rx.chakra.accordion_panel(
            rx.chakra.text("This is an example of an accordion component.")
        ),
    ),
    rx.chakra.accordion_item(
        rx.chakra.accordion_button(
            rx.chakra.heading("Example 2"),
            rx.chakra.accordion_icon(),
        ),
        rx.chakra.accordion_panel(
            rx.chakra.text("This is an example of an accordion component.")
        ),
    ),
    allow_multiple = True,
    bg="black",
    color="white",
    width = "100%"
)
```

You can create multilevel accordions by nesting accordions within the outer accordion panel.

```python demo
rx.chakra.accordion(
    rx.chakra.accordion_item(
        rx.chakra.accordion_button(
            rx.chakra.accordion_icon(),
            rx.chakra.heading("Outer"),
            
        ),
        rx.chakra.accordion_panel(
            rx.chakra.accordion(
            rx.chakra.accordion_item(
                rx.chakra.accordion_button(
                    rx.chakra.accordion_icon(),
                    rx.chakra.heading("Inner"),    
                ),
                rx.chakra.accordion_panel(
                    rx.chakra.badge("Inner Panel", variant="solid", color_scheme="green"),
                )
            )
            ),
        )  
    ),
    width = "100%"
)
```

You can also create an accordion using the shorthand syntax.
Pass a list of tuples to the `items` prop.
Each tuple should contain a label and a panel.

```python demo
rx.chakra.accordion(
   items=[("Label 1", rx.chakra.center("Panel 1")), ("Label 2", rx.chakra.center("Panel 2"))],
   width="100%"
)
```

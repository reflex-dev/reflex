---
components:
    - rx.chakra.Tabs
    - rx.chakra.TabList
    - rx.chakra.Tab
    - rx.chakra.TabPanel
    - rx.chakra.TabPanels
---

```python exec
import reflex as rx
```

# Tabs

Tab components allow you display content in multiple pages within a container.
These page are organized by a tab list and the corresponding tab panel can take in children components if needed.

```python demo
rx.chakra.tabs(
    rx.chakra.tab_list(
        rx.chakra.tab("Tab 1"),
        rx.chakra.tab("Tab 2"),
        rx.chakra.tab("Tab 3"),
    ),
    rx.chakra.tab_panels(
        rx.chakra.tab_panel(rx.chakra.text("Text from tab 1.")),
        rx.chakra.tab_panel(rx.chakra.checkbox("Text from tab 2.")),
        rx.chakra.tab_panel(rx.chakra.button("Text from tab 3.", color="black")),
    ),
    bg="black",
    color="white",
    shadow="lg",
)
```

You can create a tab component using the shorthand syntax.
Pass a list of tuples to the `items` prop.
Each tuple should contain a label and a panel.

```python demo
rx.chakra.tabs(
    items = [("Tab 1", rx.chakra.text("Text from tab 1.")), ("Tab 2", rx.chakra.checkbox("Text from tab 2.")), ("Tab 3", rx.chakra.button("Text from tab 3.", color="black"))],
    bg="black",
    color="white",
    shadow="lg",
)
```

```python exec
import reflex as rx

```

# Chips

Chips are compact elements that represent small pieces of information, such as tags or categories. They are commonly used to select multiple items from a list or to filter content.

## Status

```python demo exec toggle
from reflex.components.radix.themes.base import LiteralAccentColor

status_chip_props = {
    "radius": "full",
    "variant": "outline",
    "size": "3",
}

def status_chip(status: str, icon: str, color: LiteralAccentColor) -> rx.Component:
    return rx.badge(
        rx.icon(icon, size=18),
        status,
        color_scheme=color,
        **status_chip_props,
    )

def status_chips_group() -> rx.Component:
    return rx.hstack(
        status_chip("Info", "info", "blue"),
        status_chip("Success", "circle-check", "green"),
        status_chip("Warning", "circle-alert", "yellow"),
        status_chip("Error", "circle-x", "red"),
        wrap="wrap",
		spacing="2",
    )
```

## Single selection

```python demo exec toggle
chip_props = {
    "radius": "full",
    "variant": "soft",
    "size": "3",
    "cursor": "pointer",
    "style": {"_hover": {"opacity": 0.75}},
}

available_items = ["2:00", "3:00", "4:00", "5:00"]

class SingleSelectionChipsState(rx.State):
    selected_item: str = ""

    @rx.event
    def set_selected_item(self, value: str):
        self.selected_item = value

def unselected_item(item: str) -> rx.Component:
    return rx.badge(
        item,
        color_scheme="gray",
        **chip_props,
        on_click=SingleSelectionChipsState.set_selected_item(item),
    )

def selected_item(item: str) -> rx.Component:
    return rx.badge(
        rx.icon("check", size=18),
        item,
        color_scheme="mint",
        **chip_props,
        on_click=SingleSelectionChipsState.set_selected_item(""),
    )

def item_chip(item: str) -> rx.Component:
    return rx.cond(
        SingleSelectionChipsState.selected_item == item,
        selected_item(item),
        unselected_item(item),
    )

def item_selector() -> rx.Component:
    return rx.vstack(
        rx.hstack(
			rx.icon("clock", size=20),
			rx.heading(
				"Select your reservation time:", size="4"
			),
			spacing="2",
			align="center",
			width="100%",
        ),
        rx.hstack(
            rx.foreach(available_items, item_chip),
            wrap="wrap",
            spacing="2",
        ),
		align_items="start",
        spacing="4",
        width="100%",
    )
```

## Multiple selection

This example demonstrates selecting multiple skills from a list. It includes buttons to add all skills, clear selected skills, and select a random number of skills.

```python demo exec toggle
import random
from reflex.components.radix.themes.base import LiteralAccentColor

chip_props = {
    "radius": "full",
    "variant": "surface",
    "size": "3",
    "cursor": "pointer",
    "style": {"_hover": {"opacity": 0.75}},
}

skills = [
    "Data Management",
    "Networking",
    "Security",
    "Cloud",
    "DevOps",
    "Data Science",
    "AI",
    "ML",
    "Robotics",
    "Cybersecurity",
]

class BasicChipsState(rx.State):
    selected_items: list[str] = skills[:3]

    @rx.event
    def add_selected(self, item: str):
        self.selected_items.append(item)

    @rx.event
    def remove_selected(self, item: str):
        self.selected_items.remove(item)

    @rx.event
    def add_all_selected(self):
        self.selected_items = list(skills)

    @rx.event
    def clear_selected(self):
        self.selected_items.clear()

    @rx.event
    def random_selected(self):
        self.selected_items = random.sample(skills, k=random.randint(1, len(skills)))

def action_button(icon: str, label: str, on_click: callable, color_scheme: LiteralAccentColor) -> rx.Component:
    return rx.button(
        rx.icon(icon, size=16),
        label,
        variant="soft",
        size="2",
        on_click=on_click,
        color_scheme=color_scheme,
        cursor="pointer",
    )

def selected_item_chip(item: str) -> rx.Component:
    return rx.badge(
        item,
        rx.icon("circle-x", size=18),
        color_scheme="green",
        **chip_props,
        on_click=BasicChipsState.remove_selected(item),
    )

def unselected_item_chip(item: str) -> rx.Component:
    return rx.cond(
        BasicChipsState.selected_items.contains(item),
        rx.fragment(),
        rx.badge(
            item,
            rx.icon("circle-plus", size=18),
            color_scheme="gray",
            **chip_props,
            on_click=BasicChipsState.add_selected(item),
        ),
    )

def items_selector() -> rx.Component:
    return rx.vstack(
        rx.flex(
            rx.hstack(
                rx.icon("lightbulb", size=20),
                rx.heading(
                    "Skills" + f" ({BasicChipsState.selected_items.length()})", size="4"
                ),
                spacing="1",
                align="center",
                width="100%",
				justify_content=["end", "start"],
            ),
            rx.hstack(
                action_button(
                    "plus", "Add All", BasicChipsState.add_all_selected, "green"
                ),
                action_button(
                    "trash", "Clear All", BasicChipsState.clear_selected, "tomato"
                ),
                action_button(
                    "shuffle", "", BasicChipsState.random_selected, "gray"
                ),
                spacing="2",
                justify="end",
                width="100%",
            ),
            justify="between",
            flex_direction=["column", "row"],
            align="center",
			spacing="2",
			margin_bottom="10px",
            width="100%",
        ),
        # Selected Items
        rx.flex(
            rx.foreach(
                BasicChipsState.selected_items,
                selected_item_chip,
            ),
            wrap="wrap",
			spacing="2",
			justify_content="start",
        ),
        rx.divider(),
        # Unselected Items
        rx.flex(
            rx.foreach(skills, unselected_item_chip),
            wrap="wrap",
			spacing="2",
			justify_content="start",
        ),
		justify_content="start",
		align_items="start",
        width="100%",
    )
```

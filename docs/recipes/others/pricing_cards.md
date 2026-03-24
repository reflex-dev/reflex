```python exec
import reflex as rx
```

# Pricing Cards

A pricing card shows the price of a product or service. It typically includes a title, description, price, features, and a purchase button.

## Basic

```python demo exec toggle
def feature_item(text: str) -> rx.Component:
    return rx.hstack(rx.icon("check", color=rx.color("grass", 9)), rx.text(text, size="4"))

def features() -> rx.Component:
    return rx.vstack(
        feature_item("24/7 customer support"),
        feature_item("Daily backups"),
        feature_item("Advanced analytics"),
        feature_item("Customizable templates"),
        feature_item("Priority email support"),
        width="100%",
        align_items="start",
    )

def pricing_card_beginner() -> rx.Component:
    return rx.vstack(
        rx.vstack(
            rx.text("Beginner", weight="bold", size="6"),
            rx.text("Ideal choice for personal use & for your next project.", size="4", opacity=0.8, align="center"),
            rx.hstack(
                rx.text("$39", weight="bold", font_size="3rem", trim="both"),
                rx.text("/month", size="4", opacity=0.8, trim="both"),
                width="100%",
                align_items="end",
                justify="center"
            ),
            width="100%",
            align="center",
            spacing="6",
        ),
        features(),
        rx.button("Get started", size="3", variant="solid", width="100%", color_scheme="blue"),
        spacing="6",
        border=f"1.5px solid {rx.color('gray', 5)}",
        background=rx.color("gray", 1),
        padding="28px",
        width="100%",
        max_width="400px",
        justify="center",
        border_radius="0.5rem",
    )
```

## Comparison cards

```python demo exec toggle
def feature_item(feature: str) -> rx.Component:
    return rx.hstack(
        rx.icon("check", color=rx.color("blue", 9), size=21),
        rx.text(feature, size="4", weight="regular"),
    )


def standard_features() -> rx.Component:
    return rx.vstack(
        feature_item("40 credits for image generation"),
        feature_item("Credits never expire"),
        feature_item("High quality images"),
        feature_item("Commercial license"),
        spacing="3",
        width="100%",
        align_items="start",
    )


def popular_features() -> rx.Component:
    return rx.vstack(
        feature_item("250 credits for image generation"),
        feature_item("+30% Extra free credits"),
        feature_item("Credits never expire"),
        feature_item("High quality images"),
        feature_item("Commercial license"),
        spacing="3",
        width="100%",
        align_items="start",
    )


def pricing_card_standard() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.hstack(
                rx.text(
                    "$14.99",
                    trim="both",
                    as_="s",
                    size="3",
                    weight="regular",
                    opacity=0.8,
                ),
                rx.text("$3.99", trim="both", size="6", weight="regular"),
                width="100%",
                spacing="2",
                align_items="end",
            ),
            height="35px",
            align_items="center",
            justify="between",
            width="100%",
        ),
        rx.text(
            "40 Image Credits",
            weight="bold",
            size="7",
            width="100%",
            text_align="left",
        ),
        standard_features(),
        rx.spacer(),
        rx.button(
            "Purchase",
            size="3",
            variant="outline",
            width="100%",
            color_scheme="blue",
        ),
        spacing="6",
        border=f"1.5px solid {rx.color('gray', 5)}",
        background=rx.color("gray", 1),
        padding="28px",
        width="100%",
        max_width="400px",
        min_height="475px",
        border_radius="0.5rem",
    )


def pricing_card_popular() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.hstack(
                rx.text(
                    "$69.99",
                    trim="both",
                    as_="s",
                    size="3",
                    weight="regular",
                    opacity=0.8,
                ),
                rx.text("$18.99", trim="both", size="6", weight="regular"),
                width="100%",
                spacing="2",
                align_items="end",
            ),
            rx.badge(
                "POPULAR",
                size="2",
                radius="full",
                variant="soft",
                color_scheme="blue",
            ),
            align_items="center",
            justify="between",
            height="35px",
            width="100%",
        ),
        rx.text(
            "250 Image Credits",
            weight="bold",
            size="7",
            width="100%",
            text_align="left",
        ),
        popular_features(),
        rx.spacer(),
        rx.button("Purchase", size="3", width="100%", color_scheme="blue"),
        spacing="6",
        border=f"1.5px solid {rx.color('blue', 6)}",
        background=rx.color("blue", 1),
        padding="28px",
        width="100%",
        max_width="400px",
        min_height="475px",
        border_radius="0.5rem",
    )


def pricing_cards() -> rx.Component:
    return rx.flex(
        pricing_card_standard(),
        pricing_card_popular(),
        spacing="4",
        flex_direction=["column", "column", "row"],
        width="100%",
        align_items="center",
    )
```


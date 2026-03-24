```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
```

# Footer Bar

A footer bar is a common UI element located at the bottom of a webpage. It typically contains information about the website, such as contact details and links to other pages or sections of the site.

## Basic

```python demo exec toggle
def footer_item(text: str, href: str) -> rx.Component:
    return rx.link(rx.text(text, size="3"), href=href)

def footer_items_1() -> rx.Component:
    return rx.flex(
        rx.heading("PRODUCTS", size="4", weight="bold", as_="h3"),
        footer_item("Web Design", "/#"),
        footer_item("Web Development", "/#"),
        footer_item("E-commerce", "/#"),
        footer_item("Content Management", "/#"),
        footer_item("Mobile Apps", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def footer_items_2() -> rx.Component:
    return rx.flex(
        rx.heading("RESOURCES", size="4", weight="bold", as_="h3"),
        footer_item("Blog", "/#"),
        footer_item("Case Studies", "/#"),
        footer_item("Whitepapers", "/#"),
        footer_item("Webinars", "/#"),
        footer_item("E-books", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def social_link(icon: str, href: str) -> rx.Component:
    return rx.link(rx.icon(icon), href=href)

def socials() -> rx.Component:
    return rx.flex(
        social_link("instagram", "/#"),
        social_link("twitter", "/#"),
        social_link("facebook", "/#"),
        social_link("linkedin", "/#"),
        spacing="3",
        justify="end",
        width="100%"
    )

def footer() -> rx.Component:
    return rx.el.footer(
        rx.vstack(
            rx.flex(
                rx.vstack(
                    rx.hstack(
                        rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2.25em", height="auto", border_radius="25%"),
                        rx.heading("Reflex", size="7", weight="bold"),
                        align_items="center"
                    ),
                    rx.text("© 2024 Reflex, Inc", size="3", white_space="nowrap", weight="medium"),
                    spacing="4",
                    align_items=["center", "center", "start"]
                ),
                footer_items_1(),
                footer_items_2(),
                justify="between",
                spacing="6",
                flex_direction=["column", "column", "row"],
                width="100%"
            ),
            rx.divider(),
            rx.hstack(
                rx.hstack(
                    footer_item("Privacy Policy", "/#"),
                    footer_item("Terms of Service", "/#"),
                    spacing="4",
                    align="center",
                    width="100%"
                ),
                socials(),
                justify="between",
                width="100%"
            ),
            spacing="5",
            width="100%"
        ),
        width="100%"
    )
```

## Newsletter form

```python demo exec toggle
def footer_item(text: str, href: str) -> rx.Component:
    return rx.link(rx.text(text, size="3"), href=href)

def footer_items_1() -> rx.Component:
    return rx.flex(
        rx.heading("PRODUCTS", size="4", weight="bold", as_="h3"),
        footer_item("Web Design", "/#"),
        footer_item("Web Development", "/#"),
        footer_item("E-commerce", "/#"),
        footer_item("Content Management", "/#"),
        footer_item("Mobile Apps", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def footer_items_2() -> rx.Component:
    return rx.flex(
        rx.heading("RESOURCES", size="4", weight="bold", as_="h3"),
        footer_item("Blog", "/#"),
        footer_item("Case Studies", "/#"),
        footer_item("Whitepapers", "/#"),
        footer_item("Webinars", "/#"),
        footer_item("E-books", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def social_link(icon: str, href: str) -> rx.Component:
    return rx.link(rx.icon(icon), href=href)

def socials() -> rx.Component:
    return rx.flex(
        social_link("instagram", "/#"),
        social_link("twitter", "/#"),
        social_link("facebook", "/#"),
        social_link("linkedin", "/#"),
        spacing="3",
        justify_content=["center", "center", "end"],
        width="100%"
    )

def footer_newsletter() -> rx.Component:
    return rx.el.footer(
        rx.vstack(
            rx.flex(
                footer_items_1(),
                footer_items_2(),
                rx.vstack(
                    rx.text("JOIN OUR NEWSLETTER", size="4",
                            weight="bold"),
                    rx.hstack(
                        rx.input(placeholder="Your email address", type="email", size="3"),
                        rx.icon_button(rx.icon("arrow-right", padding="0.15em"), size="3"),
                        spacing="1",
                        justify="center",
                        width="100%"
                    ),
                    align_items=["center", "center", "start"],
                    justify="center",
                    height="100%"
                ),
                justify="between",
                spacing="6",
                flex_direction=["column", "column", "row"],
                width="100%"
            ),
            rx.divider(),
            rx.flex(
                rx.hstack(
                    rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
                    rx.text("© 2024 Reflex, Inc", size="3", white_space="nowrap", weight="medium"),
                    spacing="2",
                    align="center",
                    justify_content=["center", "center", "start"],
                    width="100%"
                ),
                socials(),
                spacing="4",
                flex_direction=["column", "column", "row"],
                width="100%"
            ),
            spacing="5",
            width="100%"
        ),
        width="100%"
    )
```

## Three columns

```python demo exec toggle
def footer_item(text: str, href: str) -> rx.Component:
    return rx.link(rx.text(text, size="3"), href=href)

def footer_items_1() -> rx.Component:
    return rx.flex(
        rx.heading("PRODUCTS", size="4", weight="bold", as_="h3"),
        footer_item("Web Design", "/#"),
        footer_item("Web Development", "/#"),
        footer_item("E-commerce", "/#"),
        footer_item("Content Management", "/#"),
        footer_item("Mobile Apps", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def footer_items_2() -> rx.Component:
    return rx.flex(
        rx.heading("RESOURCES", size="4", weight="bold", as_="h3"),
        footer_item("Blog", "/#"),
        footer_item("Case Studies", "/#"),
        footer_item("Whitepapers", "/#"),
        footer_item("Webinars", "/#"),
        footer_item("E-books", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def footer_items_3() -> rx.Component:
    return rx.flex(
        rx.heading("ABOUT US", size="4", weight="bold", as_="h3"),
        footer_item("Our Team", "/#"),
        footer_item("Careers", "/#"),
        footer_item("Contact Us", "/#"),
        footer_item("Privacy Policy", "/#"),
        footer_item("Terms of Service", "/#"),
        spacing="4",
        text_align=["center", "center", "start"],
        flex_direction="column"
    )

def social_link(icon: str, href: str) -> rx.Component:
    return rx.link(rx.icon(icon), href=href)

def socials() -> rx.Component:
    return rx.flex(
        social_link("instagram", "/#"),
        social_link("twitter", "/#"),
        social_link("facebook", "/#"),
        social_link("linkedin", "/#"),
        spacing="3",
        justify_content=["center", "center", "end"],
        width="100%"
    )

def footer_three_columns() -> rx.Component:
    return rx.el.footer(
        rx.vstack(
            rx.flex(
                footer_items_1(),
                footer_items_2(),
                footer_items_3(),
                justify="between",
                spacing="6",
                flex_direction=["column", "column", "row"],
                width="100%"
            ),
            rx.divider(),
            rx.flex(
                rx.hstack(
                    rx.image(src=f"{REFLEX_ASSETS_CDN}other/logo.jpg", width="2em", height="auto", border_radius="25%"),
                    rx.text("© 2024 Reflex, Inc", size="3", white_space="nowrap", weight="medium"),
                    spacing="2",
                    align="center",
                    justify_content=["center", "center", "start"],
                    width="100%"
                ),
                socials(),
                spacing="4",
                flex_direction=["column", "column", "row"],
                width="100%"
            ),
            spacing="5",
            width="100%"
        ),
        width="100%"
    )
```

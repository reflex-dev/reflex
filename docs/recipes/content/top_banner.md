```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
```

# Top Banner

Top banners are used to highlight important information or features at the top of a page. They are typically designed to grab the user's attention and can be used for announcements, navigation, or key messages.

## Basic

```python demo exec toggle
class TopBannerBasic(rx.ComponentState):
    hide: bool = False

    @rx.event
    def toggle(self):
        self.hide = not self.hide

    @classmethod
    def get_component(cls, **props):
        return rx.cond(
            ~cls.hide,
            rx.hstack(
                rx.flex(
                    rx.badge(
                        rx.icon("megaphone", size=18),
                        padding="0.30rem",
                        radius="full",
                    ),
                    rx.text(
                        "ReflexCon 2024 - ",
                        rx.link(
                            "Join us at the event!",
                            href="#",
                            underline="always",
                            display="inline",
                            underline_offset="2px",
                        ),
                        weight="medium",
                    ),
                    align="center",
                    margin="auto",
                    spacing="3",
                ),
                rx.icon(
                    "x",
                    cursor="pointer",
                    justify="end",
                    flex_shrink=0,
                    on_click=cls.toggle,
                ),
                wrap="nowrap",
                # position="fixed",
                justify="between",
                width="100%",
                # top="0",
                align="center",
                left="0",
                # z_index="50",
                padding="1rem",
                background=rx.color("accent", 4),
                **props,
            ),
            # Remove this in production
            rx.icon_button(
                rx.icon("eye"),
                cursor="pointer",
                on_click=cls.toggle,
            ),
        )

top_banner_basic = TopBannerBasic.create
```

## Sign up

```python demo exec toggle
class TopBannerSignup(rx.ComponentState):
    hide: bool = False

    @rx.event
    def toggle(self):
        self.hide = not self.hide

    @classmethod
    def get_component(cls, **props):
        return rx.cond(
            ~cls.hide,
                rx.flex(
                    rx.image(
                        src=f"{REFLEX_ASSETS_CDN}other/logo.jpg",
                        width="2em",
                        height="auto",
                        border_radius="25%",
                    ),
                    rx.text(
                        "Web apps in pure Python. Deploy with a single command.",
                        weight="medium",
                    ),
                    rx.flex(
                        rx.button(
                            "Sign up",
                            cursor="pointer",
                            radius="large",
                        ),
                        rx.icon(
                            "x",
                            cursor="pointer",
                            justify="end",
                            flex_shrink=0,
                            on_click=cls.toggle,
                        ),
                        spacing="4",
                        align="center",
                    ),
                wrap="nowrap",
                # position="fixed",
                flex_direction=["column", "column", "row"],
                justify_content=["start", "space-between"],
                width="100%",
                # top="0",
                spacing="2",
                align_items=["start", "start", "center"],
                left="0",
                # z_index="50",
                padding="1rem",
                background=rx.color("accent", 4),
                **props,
            ),
            # Remove this in production
            rx.icon_button(
                rx.icon("eye"),
                cursor="pointer",
                on_click=cls.toggle,
            ),
        )

top_banner_signup = TopBannerSignup.create
```

## Gradient

```python demo exec toggle
class TopBannerGradient(rx.ComponentState):
    hide: bool = False

    @rx.event
    def toggle(self):
        self.hide = not self.hide

    @classmethod
    def get_component(cls, **props):
        return rx.cond(
            ~cls.hide,
                rx.flex(
                    rx.text(
                        "The new Reflex version is now available! ",
                        rx.link(
                            "Read the release notes",
                            href="#",
                            underline="always",
                            display="inline",
                            underline_offset="2px",
                        ),
                        align_items=["start", "center"],
                        margin="auto",
                        spacing="3",
                        weight="medium",
                    ),
                    rx.icon(
                        "x",
                        cursor="pointer",
                        justify="end",
                        flex_shrink=0,
                        on_click=cls.toggle,
                ),
                wrap="nowrap",
                # position="fixed",
                justify="between",
                width="100%",
                # top="0",
                align="center",
                left="0",
                # z_index="50",
                padding="1rem",
                background=f"linear-gradient(99deg, {rx.color('blue', 4)}, {rx.color('pink', 3)}, {rx.color('mauve', 3)})",
                **props,
            ),
            # Remove this in production
            rx.icon_button(
                rx.icon("eye"),
                cursor="pointer",
                on_click=cls.toggle,
            ),
        )

top_banner_gradient = TopBannerGradient.create
```

## Newsletter

```python demo exec toggle
class TopBannerNewsletter(rx.ComponentState):
    hide: bool = False

    @rx.event
    def toggle(self):
        self.hide = not self.hide

    @classmethod
    def get_component(cls, **props):
        return rx.cond(
            ~cls.hide,
            rx.flex(
                rx.text(
                    "Join our newsletter",
                    text_wrap="nowrap",
                    weight="medium",
                ),
                rx.input(
                    rx.input.slot(rx.icon("mail")),
                    rx.input.slot(
                        rx.icon_button(
                            rx.icon(
                                "arrow-right",
                                padding="0.15em",
                            ),
                            cursor="pointer",
                            radius="large",
                            size="2",
                            justify="end",
                        ),
                        padding_right="0",
                    ),
                    placeholder="Your email address",
                    type="email",
                    size="2",
                    radius="large",
                ),
                rx.icon(
                    "x",
                    cursor="pointer",
                    justify="end",
                    flex_shrink=0,
                    on_click=cls.toggle,
                ),
                wrap="nowrap",
                # position="fixed",
                flex_direction=["column", "row", "row"],
                justify_content=["start", "space-between"],
                width="100%",
                # top="0",
                spacing="2",
                align_items=["start", "center", "center"],
                left="0",
                # z_index="50",
                padding="1rem",
                background=rx.color("accent", 4),
                **props,
            ),
            # Remove this in production
            rx.icon_button(
                rx.icon("eye"),
                cursor="pointer",
                on_click=cls.toggle,
            ),
        )

top_banner_newsletter = TopBannerNewsletter.create
```
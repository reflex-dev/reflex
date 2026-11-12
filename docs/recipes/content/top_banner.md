```python exec
import reflex as rx
```

# Top Banner

Top banners are used to highlight important information or features at the top of a page. They are typically designed to grab the user's attention and can be used for announcements, navigation, or key messages.

## Basic

```python demo exec
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

```python test
def test_basic_banner_hides_and_shows(demo):
    view = demo.get_by_role("tabpanel", name="View")
    message = view.get_by_text("ReflexCon 2024 -")
    expect(message).to_have_text("ReflexCon 2024 - Join us at the event!")
    view.locator("svg.lucide-x").click()
    expect(message).to_be_hidden()
    view.get_by_role("button").click()
    expect(message).to_be_visible()
```

## Sign up

```python demo exec
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
                    src="https://web.reflex-assets.dev/other/logo.jpg",
                    alt="Reflex logo",
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

```python test
def test_signup_banner_hides_and_shows(demo):
    view = demo.get_by_role("tabpanel", name="View")
    message = view.get_by_text("Web apps in pure Python.")
    expect(view.get_by_role("img", name="Reflex logo")).to_be_visible()
    expect(view.get_by_role("button", name="Sign up")).to_be_visible()
    view.locator("svg.lucide-x").click()
    expect(message).to_be_hidden()
    view.get_by_role("button").click()
    expect(message).to_be_visible()
```

## Gradient

```python demo exec
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

```python test
def test_gradient_banner_hides_and_shows(demo):
    view = demo.get_by_role("tabpanel", name="View")
    message = view.get_by_text("The new Reflex version is now available!")
    expect(view.get_by_role("link")).to_have_text("Read the release notes")
    view.locator("svg.lucide-x").click()
    expect(message).to_be_hidden()
    view.get_by_role("button").click()
    expect(message).to_be_visible()
```

## Newsletter

```python demo exec
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

```python test
def test_newsletter_banner_hides_and_shows(demo):
    view = demo.get_by_role("tabpanel", name="View")
    email = view.get_by_placeholder("Your email address")
    expect(view.get_by_text("Join our newsletter")).to_be_visible()
    email.fill("ada@reflex.dev")
    expect(email).to_have_value("ada@reflex.dev")
    view.locator("svg.lucide-x").click()
    expect(email).to_be_hidden()
    view.get_by_role("button").click()
    expect(email).to_be_visible()
```

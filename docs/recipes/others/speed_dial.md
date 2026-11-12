```python exec
import reflex as rx
```

# Speed Dial

A speed dial is a component that allows users to quickly access frequently used actions or pages. It is often used in the bottom right corner of the screen.

## Vertical

```python demo exec
class SpeedDialVertical(rx.ComponentState):
    is_open: bool = False

    @rx.event
    def toggle(self, value: bool):
        self.is_open = value

    @classmethod
    def get_component(cls, **props):
        def menu_item(icon: str, text: str) -> rx.Component:
            return rx.tooltip(
                rx.icon_button(
                    rx.icon(icon, padding="2px"),
                    variant="soft",
                    color_scheme="gray",
                    size="3",
                    cursor="pointer",
                    radius="full",
                ),
                side="left",
                content=text,
            )

        def menu() -> rx.Component:
            return rx.vstack(
                menu_item("copy", "Copy"),
                menu_item("download", "Download"),
                menu_item("share-2", "Share"),
                position="absolute",
                bottom="100%",
                spacing="2",
                padding_bottom="10px",
                left="0",
                direction="column-reverse",
                align_items="center",
            )

        return rx.box(
            rx.box(
                rx.icon_button(
                    rx.icon(
                        "plus",
                        style={
                            "transform": rx.cond(
                                cls.is_open, "rotate(45deg)", "rotate(0)"
                            ),
                            "transition": "transform 150ms cubic-bezier(0.4, 0, 0.2, 1)",
                        },
                    ),
                    variant="solid",
                    color_scheme="blue",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    position="relative",
                ),
                rx.cond(
                    cls.is_open,
                    menu(),
                ),
                position="relative",
            ),
            on_mouse_enter=cls.toggle(True),
            on_mouse_leave=cls.toggle(False),
            on_click=cls.toggle(~cls.is_open),
            style={"bottom": "15px", "right": "15px"},
            position="absolute",
            # z_index="50",
            **props,
        )


speed_dial_vertical = SpeedDialVertical.create


def render_vertical():
    return rx.box(
        speed_dial_vertical(),
        height="250px",
        position="relative",
        width="100%",
    )
```

```python test
def test_vertical_speed_dial(page, demo):
    view = demo.get_by_role("tabpanel", name="View")
    buttons = view.get_by_role("button")
    expect(buttons).to_have_count(1)
    buttons.first.hover()
    expect(buttons).to_have_count(4)
    buttons.nth(1).hover()
    expect(page.get_by_role("tooltip")).to_have_text("Copy")
```

## Horizontal

```python demo exec
class SpeedDialHorizontal(rx.ComponentState):
    is_open: bool = False

    @rx.event
    def toggle(self, value: bool):
        self.is_open = value

    @classmethod
    def get_component(cls, **props):
        def menu_item(icon: str, text: str) -> rx.Component:
            return rx.tooltip(
                rx.icon_button(
                    rx.icon(icon, padding="2px"),
                    variant="soft",
                    color_scheme="gray",
                    size="3",
                    cursor="pointer",
                    radius="full",
                ),
                side="top",
                content=text,
            )

        def menu() -> rx.Component:
            return rx.hstack(
                menu_item("copy", "Copy"),
                menu_item("download", "Download"),
                menu_item("share-2", "Share"),
                position="absolute",
                bottom="0",
                spacing="2",
                padding_right="10px",
                right="100%",
                direction="row-reverse",
                align_items="center",
            )

        return rx.box(
            rx.box(
                rx.icon_button(
                    rx.icon(
                        "plus",
                        style={
                            "transform": rx.cond(
                                cls.is_open, "rotate(45deg)", "rotate(0)"
                            ),
                            "transition": "transform 150ms cubic-bezier(0.4, 0, 0.2, 1)",
                        },
                        class_name="dial",
                    ),
                    variant="solid",
                    color_scheme="green",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    position="relative",
                ),
                rx.cond(
                    cls.is_open,
                    menu(),
                ),
                position="relative",
            ),
            on_mouse_enter=cls.toggle(True),
            on_mouse_leave=cls.toggle(False),
            on_click=cls.toggle(~cls.is_open),
            style={"bottom": "15px", "right": "15px"},
            position="absolute",
            # z_index="50",
            **props,
        )


speed_dial_horizontal = SpeedDialHorizontal.create


def render_horizontal():
    return rx.box(
        speed_dial_horizontal(),
        height="250px",
        position="relative",
        width="100%",
    )
```

```python test
def test_horizontal_speed_dial(page, demo):
    view = demo.get_by_role("tabpanel", name="View")
    buttons = view.get_by_role("button")
    expect(buttons).to_have_count(1)
    buttons.first.hover()
    expect(buttons).to_have_count(4)
    buttons.nth(3).hover()
    expect(page.get_by_role("tooltip")).to_have_text("Share")
```

## Vertical with text

```python demo exec
class SpeedDialVerticalText(rx.ComponentState):
    is_open: bool = False

    @rx.event
    def toggle(self, value: bool):
        self.is_open = value

    @classmethod
    def get_component(cls, **props):
        def menu_item(icon: str, text: str) -> rx.Component:
            return rx.hstack(
                rx.text(text, weight="medium"),
                rx.icon_button(
                    rx.icon(icon, padding="2px"),
                    variant="soft",
                    color_scheme="gray",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    position="relative",
                ),
                opacity="0.75",
                _hover={
                    "opacity": "1",
                },
                align_items="center",
            )

        def menu() -> rx.Component:
            return rx.vstack(
                menu_item("copy", "Copy"),
                menu_item("download", "Download"),
                menu_item("share-2", "Share"),
                position="absolute",
                bottom="100%",
                spacing="2",
                padding_bottom="10px",
                right="0",
                direction="column-reverse",
                align_items="end",
                justify_content="end",
            )

        return rx.box(
            rx.box(
                rx.icon_button(
                    rx.icon(
                        "plus",
                        style={
                            "transform": rx.cond(
                                cls.is_open, "rotate(45deg)", "rotate(0)"
                            ),
                            "transition": "transform 150ms cubic-bezier(0.4, 0, 0.2, 1)",
                        },
                        class_name="dial",
                    ),
                    variant="solid",
                    color_scheme="crimson",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    position="relative",
                ),
                rx.cond(
                    cls.is_open,
                    menu(),
                ),
                position="relative",
            ),
            on_mouse_enter=cls.toggle(True),
            on_mouse_leave=cls.toggle(False),
            on_click=cls.toggle(~cls.is_open),
            style={"bottom": "15px", "right": "15px"},
            position="absolute",
            # z_index="50",
            **props,
        )


speed_dial_vertical_text = SpeedDialVerticalText.create


def render_vertical_text():
    return rx.box(
        speed_dial_vertical_text(),
        height="250px",
        position="relative",
        width="100%",
    )
```

```python test
def test_vertical_text_speed_dial(demo):
    view = demo.get_by_role("tabpanel", name="View")
    expect(view.get_by_text("Copy")).to_have_count(0)
    view.get_by_role("button").first.hover()
    expect(view.get_by_role("paragraph")).to_have_text(["Copy", "Download", "Share"])
    expect(view.get_by_role("button")).to_have_count(4)
```

## Reveal animation

```python demo exec
class SpeedDialReveal(rx.ComponentState):
    is_open: bool = False

    @rx.event
    def toggle(self, value: bool):
        self.is_open = value

    @classmethod
    def get_component(cls, **props):
        def menu_item(icon: str, text: str) -> rx.Component:
            return rx.tooltip(
                rx.icon_button(
                    rx.icon(icon, padding="2px"),
                    variant="soft",
                    color_scheme="gray",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    style={
                        "animation": rx.cond(
                            cls.is_open, "reveal 0.3s ease both", "none"
                        ),
                        "@keyframes reveal": {
                            "0%": {
                                "opacity": "0",
                                "transform": "scale(0)",
                            },
                            "100%": {
                                "opacity": "1",
                                "transform": "scale(1)",
                            },
                        },
                    },
                ),
                side="left",
                content=text,
            )

        def menu() -> rx.Component:
            return rx.vstack(
                menu_item("copy", "Copy"),
                menu_item("download", "Download"),
                menu_item("share-2", "Share"),
                position="absolute",
                bottom="100%",
                spacing="2",
                padding_bottom="10px",
                left="0",
                direction="column-reverse",
                align_items="center",
            )

        return rx.box(
            rx.box(
                rx.icon_button(
                    rx.icon(
                        "plus",
                        style={
                            "transform": rx.cond(
                                cls.is_open, "rotate(45deg)", "rotate(0)"
                            ),
                            "transition": "transform 150ms cubic-bezier(0.4, 0, 0.2, 1)",
                        },
                        class_name="dial",
                    ),
                    variant="solid",
                    color_scheme="violet",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    position="relative",
                ),
                rx.cond(
                    cls.is_open,
                    menu(),
                ),
                position="relative",
            ),
            on_mouse_enter=cls.toggle(True),
            on_mouse_leave=cls.toggle(False),
            on_click=cls.toggle(~cls.is_open),
            style={"bottom": "15px", "right": "15px"},
            position="absolute",
            # z_index="50",
            **props,
        )


speed_dial_reveal = SpeedDialReveal.create


def render_reveal():
    return rx.box(
        speed_dial_reveal(),
        height="250px",
        position="relative",
        width="100%",
    )
```

```python test
def test_reveal_speed_dial(page, demo):
    view = demo.get_by_role("tabpanel", name="View")
    buttons = view.get_by_role("button")
    expect(buttons).to_have_count(1)
    buttons.first.hover()
    expect(buttons).to_have_count(4)
    expect(buttons.nth(1)).to_have_css("opacity", "1")
    buttons.nth(2).hover()
    expect(page.get_by_role("tooltip")).to_have_text("Download")
```

## Menu

```python demo exec
class SpeedDialMenu(rx.ComponentState):
    is_open: bool = False

    @rx.event
    def toggle(self, value: bool):
        self.is_open = value

    @classmethod
    def get_component(cls, **props):
        def menu_item(icon: str, text: str) -> rx.Component:
            return rx.hstack(
                rx.icon(icon, padding="2px"),
                rx.text(text, weight="medium"),
                align="center",
                opacity="0.75",
                cursor="pointer",
                position="relative",
                _hover={
                    "opacity": "1",
                },
                width="100%",
                align_items="center",
            )

        def menu() -> rx.Component:
            return rx.box(
                rx.card(
                    rx.vstack(
                        menu_item("copy", "Copy"),
                        rx.divider(margin="0"),
                        menu_item("download", "Download"),
                        rx.divider(margin="0"),
                        menu_item("share-2", "Share"),
                        direction="column-reverse",
                        align_items="end",
                        justify_content="end",
                    ),
                    box_shadow="0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)",
                ),
                position="absolute",
                bottom="100%",
                right="0",
                padding_bottom="10px",
            )

        return rx.box(
            rx.box(
                rx.icon_button(
                    rx.icon(
                        "plus",
                        style={
                            "transform": rx.cond(
                                cls.is_open, "rotate(45deg)", "rotate(0)"
                            ),
                            "transition": "transform 150ms cubic-bezier(0.4, 0, 0.2, 1)",
                        },
                        class_name="dial",
                    ),
                    variant="solid",
                    color_scheme="orange",
                    size="3",
                    cursor="pointer",
                    radius="full",
                    position="relative",
                ),
                rx.cond(
                    cls.is_open,
                    menu(),
                ),
                position="relative",
            ),
            on_mouse_enter=cls.toggle(True),
            on_mouse_leave=cls.toggle(False),
            on_click=cls.toggle(~cls.is_open),
            style={"bottom": "15px", "right": "15px"},
            position="absolute",
            # z_index="50",
            **props,
        )


speed_dial_menu = SpeedDialMenu.create


def render_menu():
    return rx.box(
        speed_dial_menu(),
        height="250px",
        position="relative",
        width="100%",
    )
```

```python test
def test_menu_speed_dial(demo):
    view = demo.get_by_role("tabpanel", name="View")
    expect(view.get_by_role("paragraph")).to_have_count(0)
    view.get_by_role("button").hover()
    expect(view.get_by_role("paragraph")).to_have_text(["Copy", "Download", "Share"])
```

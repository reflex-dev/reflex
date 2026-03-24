```python exec
import reflex as rx
from pcweb.constants import REFLEX_ASSETS_CDN
from pcweb.pages.docs import library
from pcweb.styles.styles import get_code_style_rdx, cell_style
```

# Theming

As of Reflex `v0.4.0`, you can now theme your Reflex applications. The core of our theming system is directly based on the [Radix Themes](https://www.radix-ui.com) library. This allows you to easily change the theme of your application along with providing a default light and dark theme. Themes cause all the components to have a unified color appearance.

## Overview

The `Theme` component is used to change the theme of the application. The `Theme` can be set directly in your rx.App.

```python
app = rx.App(
    theme=rx.theme(
        appearance="light", has_background=True, radius="large", accent_color="teal"
    )
)
```

Here are the props that can be passed to the `rx.theme` component:

```python eval
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Name", class_name="table-header"),
            rx.table.column_header_cell("Type", class_name="table-header"),
            rx.table.column_header_cell("Description", class_name="table-header"),
        ),
    ),
    rx.table.body(
        rx.table.row(
            rx.table.row_header_cell(rx.code("has_background", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code("Bool", style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("Whether to apply the themes background color to the theme node. Defaults to True.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("appearance", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code('"inherit" | "light" | "dark"', style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("The appearance of the theme. Can be 'light' or 'dark'. Defaults to 'light'.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("accent_color", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code("Str", style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("The primary color used for default buttons, typography, backgrounds, etc.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("gray_color", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code("Str", style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("The secondary color used for default buttons, typography, backgrounds, etc.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("panel_background", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code('"solid" | "translucent"', style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell('Whether panel backgrounds are translucent: "solid" | "translucent" (default).', style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("radius", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code('"none" | "small" | "medium" | "large" | "full"', style=get_code_style_rdx("gray"))),
            rx.table.cell("The radius of the theme. Can be 'small', 'medium', or 'large'. Defaults to 'medium'.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("scaling", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code('"90%" | "95%" | "100%" | "105%" | "110%"', style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("Scale of all theme items.", style=cell_style),
        ),
    ),
    variant="surface",
    margin_y="1em",
)

```

Additionally you can modify the theme of your app through using the `Theme Panel` component which can be found in the [Theme Panel docs]({library.other.theme.path}).


## Colors

### Color Scheme

On a high-level, component `color_scheme` inherits from the color specified in the theme. This means that if you change the theme, the color of the component will also change. Available colors can be found [here](https://www.radix-ui.com/colors).

You can also specify the `color_scheme` prop.

```python demo
rx.flex(
    rx.button(
        "Hello World",
        color_scheme="tomato",
    ),
    rx.button(
        "Hello World",
        color_scheme="teal",
    ),
    spacing="2"
)
```

### Shades

Sometime you may want to use a specific shade of a color from the theme. This is recommended vs using a hex color directly as it will automatically change when the theme changes appearance change from light/dark.


To access a specific shade of color from the theme, you can use the `rx.color`. When switching to light and dark themes, the color will automatically change. Shades can be accessed by using the color name and the shade number. The shade number ranges from 1 to 12. Additionally, they can have their alpha value set by using the `True` parameter it defaults to `False`. A full list of colors can be found [here](https://www.radix-ui.com/colors).

```python demo
rx.flex(
    rx.button(
        "Hello World",
        color=rx.color("grass", 1),
        background_color=rx.color("grass", 7),
        border_color=f"1px solid {rx.color('grass', 1)}",
    ),
    spacing="2"
)
```

```python eval
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Name"),
            rx.table.column_header_cell("Type"),
            rx.table.column_header_cell("Description"),
        ),
    ),
    rx.table.body(
        rx.table.row(
            rx.table.row_header_cell(rx.code("color", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code("Str", style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("The color to use. Can be any valid accent color or 'accent' to reference the current theme color.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("shade", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.link(rx.code('1 - 12', style=get_code_style_rdx("gray"), class_name="code-style"), href="https://www.radix-ui.com/colors")),
            rx.table.cell("The shade of the color to use. Defaults to 7.", style=cell_style),
        ),
        rx.table.row(
            rx.table.row_header_cell(rx.code("alpha", style=get_code_style_rdx("violet"), class_name="code-style")),
            rx.table.cell(rx.code("Bool", style=get_code_style_rdx("gray"), class_name="code-style")),
            rx.table.cell("Whether to use the alpha value of the color. Defaults to False.", style=cell_style),
        )
    ),
    variant="surface",
    margin_y="1em",
)

```

### Regular Colors

You can also use standard hex, rgb, and rgba colors.

```python demo
rx.flex(
    rx.button(
        "Hello World",
        color="white",
        background_color="#87CEFA",
        border="1px solid rgb(176,196,222)",
    ),
    spacing="2"
)
```

## Toggle Appearance

To toggle between the light and dark mode manually, you can use the `toggle_color_mode` with the desired event trigger of your choice.

```python

from reflex.style import toggle_color_mode



def index():
    return rx.button(
        "Toggle Color Mode",
        on_click=toggle_color_mode,
    )
```

## Appearance Conditional Rendering

To render a different component depending on whether the app is in `light` mode or `dark` mode, you can use the `rx.color_mode_cond` component. The first component will be rendered if the app is in `light` mode and the second component will be rendered if the app is in `dark` mode.

```python demo
rx.color_mode_cond(
    light=rx.image(src=f"{REFLEX_ASSETS_CDN}logos/light/reflex.svg", alt="Reflex Logo light", height="4em"),
    dark=rx.image(src=f"{REFLEX_ASSETS_CDN}logos/dark/reflex.svg", alt="Reflex Logo dark", height="4em"),
)
```

This can also be applied to props.

```python demo
rx.button(
    "Hello World",
    color=rx.color_mode_cond(light="black", dark="white"),
    background_color=rx.color_mode_cond(light="white", dark="black"),
)
```

```python exec
import reflex as rx

cell_style = {
    "font_family": "Instrument Sans",
    "font_style": "normal",
    "font_weight": "500",
    "font_size": "14px",
    "line_height": "1.5",
    "letter_spacing": "-0.0125em",
    "color": "var(--muted-foreground)",
}
```

# Responsive

Reflex apps can be made responsive to look good on mobile, tablet, and desktop.

You can pass a list of values to any style property to specify its value on different screen sizes.

```python demo
rx.text(
    "Hello World",
    color=["orange", "red", "purple", "blue", "green"],
)
```

```python test
@pytest.mark.parametrize(
    ("width", "color"),
    [
        (400, "rgb(255, 165, 0)"),
        (500, "rgb(255, 0, 0)"),
        (800, "rgb(128, 0, 128)"),
        (1000, "rgb(0, 0, 255)"),
        (1300, "rgb(0, 128, 0)"),
    ],
)
def test_list_breakpoint_colors(demo, page, width, color):
    page.set_viewport_size({"width": width, "height": 800})
    expect(demo.get_by_text("Hello World")).to_have_css("color", color)
```

The text will change color based on your screen size. If you are on desktop, try changing the size of your browser window to see the color change.

_New in 0.5.6_

Responsive values can also be specified using `rx.breakpoints`. Each size maps to a corresponding key, the value of which will be applied when the screen size is greater than or equal to the named breakpoint.

```python demo
rx.text(
    "Hello World",
    color=rx.breakpoints(
        initial="orange",
        sm="purple",
        lg="green",
    ),
)
```

```python test
@pytest.mark.parametrize(
    ("width", "color"),
    [
        (400, "rgb(255, 165, 0)"),
        (800, "rgb(128, 0, 128)"),
        (1300, "rgb(0, 128, 0)"),
    ],
)
def test_named_breakpoint_colors(demo, page, width, color):
    page.set_viewport_size({"width": width, "height": 800})
    expect(demo.get_by_text("Hello World")).to_have_css("color", color)
```

Custom breakpoints in CSS units can be mapped to values per component using a dictionary instead of named parameters.

```python
rx.text(
    "Hello World",
    color=rx.breakpoints({
        "0px": "orange",
        "48em": "purple",
        "80em": "green",
    }),
)
```

For the Radix UI components' fields that supports responsive value, you can also use `rx.breakpoints` (note that custom breakpoints and list syntax aren't supported).

```python demo
rx.grid(
    rx.foreach(
        list(range(6)),
        lambda _: rx.box(bg_color="#a7db76", height="100px", width="100px"),
    ),
    columns=rx.breakpoints(initial="2", sm="4", lg="6"),
    spacing="4",
)
```

```python test
@pytest.mark.parametrize(("width", "columns"), [(400, 2), (800, 4), (1300, 6)])
def test_grid_columns_per_breakpoint(demo, page, width, columns):
    page.set_viewport_size({"width": width, "height": 800})
    grid = demo.locator(".rt-Grid")
    expect(grid).to_have_css(
        "grid-template-columns", re.compile(rf"^(?:[\d.]+px ?){{{columns}}}$")
    )
```

## Setting Defaults

The default breakpoints are shown below.

```python eval notest
rx.table.root(
    rx.table.header(
        rx.table.row(
            rx.table.column_header_cell("Size"),
            rx.table.column_header_cell("Width"),
        ),
    ),
    rx.table.body(
        rx.table.row(
            rx.table.cell(
                rx.code(
                    "initial",
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
            rx.table.cell("0px", style=cell_style),
        ),
        rx.table.row(
            rx.table.cell(
                rx.code(
                    "xs",
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
            rx.table.cell("30em", style=cell_style),
        ),
        rx.table.row(
            rx.table.cell(
                rx.code(
                    "sm",
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
            rx.table.cell("48em", style=cell_style),
        ),
        rx.table.row(
            rx.table.cell(
                rx.code(
                    "md",
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
            rx.table.cell("62em", style=cell_style),
        ),
        rx.table.row(
            rx.table.cell(
                rx.code(
                    "lg",
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
            rx.table.cell("80em", style=cell_style),
        ),
        rx.table.row(
            rx.table.cell(
                rx.code(
                    "xl",
                    style={
                        "color": rx.color("violet", 11),
                        "border_radius": "0.25rem",
                        "border": f"1px solid {rx.color('violet', 5)}",
                        "background": rx.color("violet", 3),
                    },
                )
            ),
            rx.table.cell("96em", style=cell_style),
        ),
    ),
    margin_bottom="1em",
)
```

You can customize them using the style property.

```python
app = rx.App(style={"breakpoints": ["520px", "768px", "1024px", "1280px", "1640px"]})
```

## Showing Components Based on Display

A common use case for responsive is to show different components based on the screen size.

Reflex provides useful helper components for this.

```python demo
rx.vstack(
    rx.desktop_only(
        rx.text("Desktop View"),
    ),
    rx.tablet_only(
        rx.text("Tablet View"),
    ),
    rx.mobile_only(
        rx.text("Mobile View"),
    ),
    rx.mobile_and_tablet(
        rx.text("Visible on Mobile and Tablet"),
    ),
    rx.tablet_and_desktop(
        rx.text("Visible on Desktop and Tablet"),
    ),
)
```

```python test
@pytest.mark.parametrize(
    ("width", "shown"),
    [
        (400, ["Mobile View", "Visible on Mobile and Tablet"]),
        (
            800,
            [
                "Tablet View",
                "Visible on Mobile and Tablet",
                "Visible on Desktop and Tablet",
            ],
        ),
        (1300, ["Desktop View", "Visible on Desktop and Tablet"]),
    ],
)
def test_show_by_screen_size(demo, page, width, shown):
    page.set_viewport_size({"width": width, "height": 800})
    expect(
        demo.get_by_text(
            re.compile(r"^(Mobile|Tablet|Desktop) View$|^Visible on")
        ).filter(visible=True)
    ).to_have_text(shown)
```

## Specifying Display Breakpoints

You can specify the breakpoints to use for the responsive components by using the `display` style property.

```python demo
rx.vstack(
    rx.text(
        "Hello World",
        color="green",
        display=["none", "none", "none", "none", "flex"],
    ),
    rx.text(
        "Hello World",
        color="blue",
        display=["none", "none", "none", "flex", "flex"],
    ),
    rx.text(
        "Hello World",
        color="red",
        display=["none", "none", "flex", "flex", "flex"],
    ),
    rx.text(
        "Hello World",
        color="orange",
        display=["none", "flex", "flex", "flex", "flex"],
    ),
    rx.text(
        "Hello World",
        color="yellow",
        display=["flex", "flex", "flex", "flex", "flex"],
    ),
)
```

```python test
@pytest.mark.parametrize(
    ("width", "colors"),
    [
        (400, ["yellow"]),
        (500, ["orange", "yellow"]),
        (800, ["red", "orange", "yellow"]),
        (1000, ["blue", "red", "orange", "yellow"]),
        (1300, ["green", "blue", "red", "orange", "yellow"]),
    ],
)
def test_display_per_breakpoint(demo, page, width, colors):
    page.set_viewport_size({"width": width, "height": 800})
    visible = demo.get_by_text("Hello World").filter(visible=True)
    expect(visible).to_have_count(len(colors))
    rgb = {
        "green": "rgb(0, 128, 0)",
        "blue": "rgb(0, 0, 255)",
        "red": "rgb(255, 0, 0)",
        "orange": "rgb(255, 165, 0)",
        "yellow": "rgb(255, 255, 0)",
    }
    for i, color in enumerate(colors):
        expect(visible.nth(i)).to_have_css("color", rgb[color])
```

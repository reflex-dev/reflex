---
components:
  - rx.lucide.Icon
---

```python exec
import reflex as rx

from reflex_components_lucide.icon import LUCIDE_ICON_LIST
from reflex.experimental.client_state import ClientStateVar

icon_search_cs = ClientStateVar.create("icon_search", default="")


@rx.memo
def lucide_icons():
    return rx.box(
        rx.box(
            rx.box(
                rx.icon(
                    tag="search",
                    size=20,
                    class_name="shrink-0 !text-slate-11",
                ),
                class_name="absolute left-2 top-1/2 transform -translate-y-1/2 z-[1] shrink-0 flex items-center justify-center pb-2",
            ),
            rx.el.input(
                placeholder="Search icons...",
                on_change=icon_search_cs.set_value,
                class_name="relative box-border border-slate-4 focus:border-violet-9 focus:border-1 bg-slate-2 p-[0.5rem_0.75rem] border rounded-xl font-base text-slate-11 placeholder:text-slate-9 outline-none focus:outline-none w-full mb-2 pl-10",
            ),
            class_name="relative flex items-center",
        ),
        rx.el.div(
            rx.box(
                rx.foreach(
                    LUCIDE_ICON_LIST,
                    lambda icon: rx.cond(
                        icon.startswith(icon_search_cs.value),
                        rx.tooltip(
                            rx.box(
                                rx.icon(tag=icon),
                                class_name="flex items-center justify-center rounded-md hover:bg-slate-3 transition-bg p-2 cursor-pointer",
                                on_click=[
                                    rx.set_clipboard(icon),
                                    rx.toast.success(f"Copied {icon} to clipboard"),
                                ],
                                key=icon,
                            ),
                            content=icon,
                        ),
                        None,
                    ),
                ),
                class_name="flex flex-wrap justify-start gap-4 mb-4",
            ),
            class_name="overflow-y-auto max-h-[500px]",
        ),
        class_name="flex flex-col gap-4",
    )
```

# Icon

The Icon component is used to display an icon from a library of icons. This implementation is based on the [Lucide Icons](https://lucide.dev/icons) where you can find a list of all available icons.

## Icons List

```python eval
lucide_icons()
```

## Basic Example

To display an icon, specify the `tag` prop from the list of available icons.
Passing the tag as the first children is also supported and will be assigned to the `tag` prop.

The `tag` is expected to be in `snake_case` format, but `kebab-case` is also supported to allow copy-paste from [https://lucide.dev/icons](https://lucide.dev/icons).

```python demo
rx.flex(
    rx.icon("calendar"),
    rx.icon(tag="calendar"),
    gap="2",
)
```

## Dynamic Icons

There are two ways to use dynamic icons in Reflex:

### Using rx.match

If you have a specific subset of icons you want to use dynamically, you can define an `rx.match` with them:

```python
def dynamic_icon_with_match(icon_name):
    return rx.match(
        icon_name,
        ("plus", rx.icon("plus")),
        ("minus", rx.icon("minus")),
        ("equal", rx.icon("equal")),
    )
```

```python exec
def dynamic_icon_with_match(icon_name):
    return rx.match(
        icon_name,
        ("plus", rx.icon("plus")),
        ("minus", rx.icon("minus")),
        ("equal", rx.icon("equal")),
    )
```

### Using Dynamic Icon Tags

Reflex also supports using dynamic values directly as the `tag` prop in `rx.icon()`. This allows you to use any icon from the Lucide library dynamically at runtime.

```python exec
class DynamicIconState(rx.State):
    current_icon: str = "heart"

    def change_icon(self):
        icons = ["heart", "star", "bell", "calendar", "settings"]
        import random

        self.current_icon = random.choice(icons)
```

```python demo
rx.vstack(
    rx.heading("Dynamic Icon Example"),
    rx.icon(DynamicIconState.current_icon, size=30, color="red"),
    rx.button("Change Icon", on_click=DynamicIconState.change_icon),
    spacing="4",
    align="center",
)
```

Under the hood, when a dynamic value is passed as the `tag` prop to `rx.icon()`, Reflex automatically uses a special `DynamicIcon` component that can load icons at runtime.

```md alert
When using dynamic icons, make sure the icon names are valid. Invalid icon names will cause runtime errors.
```

## Styling

Icon from Lucide can be customized with the following props `stroke_width`, `size` and `color`.

### Stroke Width

```python demo
rx.flex(
    rx.icon("moon", stroke_width=1),
    rx.icon("moon", stroke_width=1.5),
    rx.icon("moon", stroke_width=2),
    rx.icon("moon", stroke_width=2.5),
    gap="2",
)
```

### Size

```python demo
rx.flex(
    rx.icon("zoom_in", size=15),
    rx.icon("zoom_in", size=20),
    rx.icon("zoom_in", size=25),
    rx.icon("zoom_in", size=30),
    align="center",
    gap="2",
)
```

### Color

Here is an example using basic colors in icons.

```python demo
rx.flex(
    rx.icon("zoom_in", size=18, color="indigo"),
    rx.icon("zoom_in", size=18, color="cyan"),
    rx.icon("zoom_in", size=18, color="orange"),
    rx.icon("zoom_in", size=18, color="crimson"),
    gap="2",
)
```

A radix color with a scale may also be specified using `rx.color()` as seen below.

```python demo
rx.flex(
    rx.icon("zoom_in", size=18, color=rx.color("purple", 1)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 2)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 3)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 4)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 5)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 6)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 7)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 8)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 9)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 10)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 11)),
    rx.icon("zoom_in", size=18, color=rx.color("purple", 12)),
    gap="2",
)
```

Here is another example using the `accent` color with scales. The `accent` is the most dominant color in your theme.

```python demo
rx.flex(
    rx.icon("zoom_in", size=18, color=rx.color("accent", 1)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 2)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 3)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 4)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 5)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 6)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 7)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 8)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 9)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 10)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 11)),
    rx.icon("zoom_in", size=18, color=rx.color("accent", 12)),
    gap="2",
)
```

## Final Example

Icons can be used as child components of many other components. For example, adding a magnifying glass icon to a search bar.

```python demo
rx.badge(
    rx.flex(
        rx.icon("search", size=18),
        rx.text("Search documentation...", size="3", weight="medium"),
        direction="row",
        gap="1",
        align="center",
    ),
    size="2",
    radius="full",
    color_scheme="gray",
)
```

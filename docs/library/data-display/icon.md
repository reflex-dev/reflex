---
components:
  - rx.lucide.Icon
---

```python exec
import reflex as rx

from reflex_components_lucide.icon import LUCIDE_ICON_LIST

icon_search_cs = rx.client_state("", name="icon_search")


@rx.memo
def lucide_icons() -> rx.Component:
    return rx.box(
        rx.box(
            rx.box(
                rx.icon(
                    tag="search",
                    size=20,
                    class_name="shrink-0 !text-muted-foreground",
                ),
                class_name="absolute left-2 top-1/2 transform -translate-y-1/2 z-[1] shrink-0 flex items-center justify-center pb-2",
            ),
            rx.el.input(
                placeholder="Search icons...",
                on_change=icon_search_cs.set,
                class_name="relative box-border border-border-subtle focus:border-border-strong focus:border-1 bg-muted p-[0.5rem_0.75rem] border rounded-xl font-base text-muted-foreground placeholder:text-subtle-foreground outline-none focus:outline-none w-full mb-2 pl-10",
            ),
            class_name="relative flex items-center",
        ),
        rx.el.div(
            rx.box(
                rx.foreach(
                    LUCIDE_ICON_LIST,
                    lambda icon: rx.cond(
                        icon.startswith(icon_search_cs.value),
                        rx.box(
                            rx.icon(tag=icon),
                            title=icon,
                            class_name="flex items-center justify-center rounded-md hover:bg-accent transition-bg p-2 cursor-pointer",
                            on_click=[
                                rx.set_clipboard(icon),
                                rx.toast.success(f"Copied {icon} to clipboard"),
                            ],
                            key=icon,
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

```python test
def test_icon_list_search_filters_and_copies(page, demo):
    demo.get_by_placeholder("Search icons...").fill("zoom")
    icons = demo.locator("[title]")
    expect(icons).to_have_count(2)
    expect(demo.get_by_title("zoom_in")).to_be_visible()
    expect(demo.get_by_title("zoom_out")).to_be_visible()
    demo.get_by_title("zoom_in").click()
    expect(page.get_by_text("Copied zoom_in to clipboard")).to_be_visible()
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

```python test
def test_icon_tag_as_child_or_prop(demo):
    expect(demo.locator("svg.lucide-calendar")).to_have_count(2)
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
    rx.heading("Dynamic Icon Example", as_="h2"),
    rx.icon(DynamicIconState.current_icon, size=30, color="red"),
    rx.button("Change Icon", on_click=DynamicIconState.change_icon),
    spacing="4",
    align="center",
)
```

```python test
def test_icon_dynamic_tag_changes(demo):
    expect(demo.get_by_role("heading")).to_have_text("Dynamic Icon Example")
    icon = demo.locator('svg[width="30"]')
    expect(icon).to_have_css("color", "rgb(255, 0, 0)")
    path = icon.locator("path").first
    expect(path).to_be_attached()
    initial = path.get_attribute("d")
    # The next icon is random, so click until it differs from the heart.
    for _ in range(20):
        demo.get_by_role("button", name="Change Icon").click()
        try:
            expect(path).not_to_have_attribute("d", initial, timeout=1000)
            break
        except AssertionError:
            continue
    else:
        pytest.fail("The icon never changed")
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

```python test
def test_icon_stroke_widths(demo):
    icons = demo.locator("svg.lucide-moon")
    expect(icons).to_have_count(4)
    for i, width in enumerate(["1px", "1.5px", "2px", "2.5px"]):
        expect(icons.nth(i)).to_have_css("stroke-width", width)
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

```python test
def test_icon_sizes(demo):
    icons = demo.locator("svg.lucide-zoom-in")
    expect(icons).to_have_count(4)
    for i, size in enumerate(["15", "20", "25", "30"]):
        expect(icons.nth(i)).to_have_attribute("width", size)
        expect(icons.nth(i)).to_have_attribute("height", size)
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

```python test
def test_icon_colors(demo):
    icons = demo.locator("svg.lucide-zoom-in")
    colors = [
        "rgb(75, 0, 130)",
        "rgb(0, 255, 255)",
        "rgb(255, 165, 0)",
        "rgb(220, 20, 60)",
    ]
    expect(icons).to_have_count(4)
    for i, color in enumerate(colors):
        expect(icons.nth(i)).to_have_css("color", color)
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

```python test
def test_icon_purple_scale(demo):
    icons = demo.locator("svg.lucide-zoom-in")
    expect(icons).to_have_count(12)
    # Each step of the purple scale is a different color.
    colors = icons.evaluate_all("els => els.map(el => getComputedStyle(el).color)")
    assert len(set(colors)) == 12
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

```python test
def test_icon_accent_scale(demo):
    icons = demo.locator("svg.lucide-zoom-in")
    expect(icons).to_have_count(12)
    # Each step of the accent scale is a different color.
    accents = icons.evaluate_all("els => els.map(el => getComputedStyle(el).color)")
    assert len(set(accents)) == 12
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

```python test
def test_icon_in_search_badge(demo):
    badge = demo.locator(".rt-Badge")
    expect(badge).to_have_text("Search documentation...")
    expect(badge.locator("svg.lucide-search")).to_have_attribute("width", "18")
```

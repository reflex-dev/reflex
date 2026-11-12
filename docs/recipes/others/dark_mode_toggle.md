```python exec
import reflex as rx
from reflex.style import set_color_mode, color_mode
```

# Dark Mode Toggle

The Dark Mode Toggle component lets users switch between light and dark themes.

```python demo exec
import reflex as rx
from reflex.style import set_color_mode, color_mode


def dark_mode_toggle() -> rx.Component:
    return rx.segmented_control.root(
        rx.segmented_control.item(
            rx.icon(tag="monitor", size=20),
            value="system",
        ),
        rx.segmented_control.item(
            rx.icon(tag="sun", size=20),
            value="light",
        ),
        rx.segmented_control.item(
            rx.icon(tag="moon", size=20),
            value="dark",
        ),
        on_change=set_color_mode,
        variant="classic",
        radius="large",
        value=color_mode,
    )
```

```python test
def test_toggle_switches_color_mode(page, demo):
    radios = demo.get_by_role("tabpanel", name="View").get_by_role("radio")
    expect(radios).to_have_count(3)
    html = page.locator("html")
    radios.nth(2).click()
    expect(radios.nth(2)).to_be_checked()
    expect(html).to_have_css("color-scheme", "dark")
    radios.nth(1).click()
    expect(radios.nth(1)).to_be_checked()
    expect(html).to_have_css("color-scheme", "light")
```

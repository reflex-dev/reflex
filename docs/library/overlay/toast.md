---
components:
  - rx.toast.provider
---

```python exec
import reflex as rx
```

# Toast

A `rx.toast` is a non-blocking notification that disappears after a certain amount of time. It is often used to show a message to the user without interrupting their workflow.

## Usage

You can use `rx.toast` as an event handler for any component that triggers an action.

```python demo
rx.button("Show Toast", on_click=rx.toast("Hello, World!"))
```

```python test
def test_toast_shows_message(demo, page):
    demo.get_by_role("button", name="Show Toast").click()
    expect(page.get_by_text("Hello, World!")).to_be_visible()
```

### Usage in State

You can also use `rx.toast` in a state to show a toast when a specific action is triggered, using `yield`.

```python demo exec
import asyncio


class ToastState(rx.State):
    @rx.event
    async def fetch_data(self):
        # Simulate fetching data for a 2-second delay
        await asyncio.sleep(2)
        # Shows a toast when the data is fetched
        yield rx.toast("Data fetched!")


def render():
    return rx.button("Get Data", on_click=ToastState.fetch_data)
```

```python test
def test_toast_from_state(demo, page):
    demo.get_by_role("button", name="Get Data").click()
    # The handler sleeps for 2 seconds before yielding the toast.
    expect(page.get_by_text("Data fetched!")).to_be_visible(timeout=10000)
```

## Interaction

If you want to interact with a toast, a few props are available to customize the behavior.

By passing a dict with `label` and `on_click` keys to the `action` or `cancel` prop, you can trigger an action when that button is clicked. To react when the toast is closed or swiped away, use `on_dismiss`.

```python demo
rx.button(
    "Show Toast",
    on_click=rx.toast(
        "Item deleted",
        action={"label": "Undo", "on_click": rx.console_log("Undo clicked")},
        cancel={"label": "Dismiss", "on_click": rx.console_log("Dismiss clicked")},
    ),
)
```

```python test
def test_toast_action_and_cancel(demo, page):
    demo.get_by_role("button", name="Show Toast").click()
    toast = page.locator("[data-sonner-toast]").filter(has_text="Item deleted")
    expect(toast.get_by_role("button")).to_have_text(["Dismiss", "Undo"])
    with page.expect_console_message(lambda m: m.text == "Undo clicked"):
        toast.get_by_role("button", name="Undo").click()
    expect(toast).to_have_count(0)

    demo.get_by_role("button", name="Show Toast").click()
    with page.expect_console_message(lambda m: m.text == "Dismiss clicked"):
        toast.get_by_role("button", name="Dismiss").click()
    expect(toast).to_have_count(0)
```

### Presets

`rx.toast` has some presets that you can use to show different types of toasts.

```python demo
rx.hstack(
    rx.button("Success", on_click=rx.toast.success("Success!"), color_scheme="green"),
    rx.button("Error", on_click=rx.toast.error("Error!"), color_scheme="red"),
    rx.button("Warning", on_click=rx.toast.warning("Warning!"), color_scheme="orange"),
    rx.button("Info", on_click=rx.toast.info("Info!"), color_scheme="blue"),
)
```

```python test
def test_toast_presets(demo, page):
    for preset in ["Success", "Error", "Warning", "Info"]:
        demo.get_by_role("button", name=preset).click()
        toast = page.locator("[data-sonner-toast]").filter(has_text=f"{preset}!")
        expect(toast).to_have_attribute("data-type", preset.lower())
```

### Customization

If the presets don't fit your needs, you can customize the toasts by passing to `rx.toast` or to `rx.toast.options` some kwargs.

```python demo
rx.button(
    "Custom",
    on_click=rx.toast(
        "Custom Toast!",
        position="top-right",
        style={
            "background-color": "green",
            "color": "white",
            "border": "1px solid green",
            "border-radius": "0.53m",
        },
    ),
)
```

```python test
def test_toast_custom_style(demo, page):
    demo.get_by_role("button", name="Custom").click()
    toast = page.locator("[data-sonner-toast]").filter(has_text="Custom Toast!")
    expect(toast).to_have_css("background-color", "rgb(0, 128, 0)")
    expect(toast).to_have_css("color", "rgb(255, 255, 255)")
    expect(toast).to_have_attribute("data-y-position", "top")
    expect(toast).to_have_attribute("data-x-position", "right")
```

The following props are available for customization:

- `description`: `str | Var`: Toast's description, renders underneath the title.
- `close_button`: `bool`: Whether to show the close button.
- `invert`: `bool`: Dark toast in light mode and vice versa.
- `important`: `bool`: Control the sensitivity of the toast for screen readers.
- `duration`: `int`: Time in milliseconds that should elapse before automatically closing the toast.
- `position`: `LiteralPosition`: Position of the toast.
- `dismissible`: `bool`: If false, it'll prevent the user from dismissing the toast.
- `action`: `dict`: A dict with `label` and `on_click` keys. Renders a primary button, clicking it will close the toast.
- `cancel`: `dict`: A dict with `label` and `on_click` keys. Renders a secondary button, clicking it will close the toast.
- `id`: `str | Var`: Custom id for the toast.
- `unstyled`: `bool`: Removes the default styling, which allows for easier customization.
- `style`: `Style`: Custom style for the toast.
- `on_dismiss`: `Any`: The function gets called when either the close button is clicked, or the toast is swiped.
- `on_auto_close`: `Any`: Function that gets called when the toast disappears automatically after it's timeout (`duration` prop).

## Toast Provider

Using the `rx.toast` function require to have a toast provider in your app.

`rx.toast.provider` is a component that provides a context for displaying toasts. It should be placed at the root of your app.

```md alert warning
# In most case you will not need to include this component directly, as it is already included in `rx.app` as the `overlay_component` for displaying connections errors.
```

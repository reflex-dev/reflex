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

## Interaction

If you want to interact with a toast, a few props are available to customize the behavior.

By passing a `ToastAction` to the `action` or `cancel` prop, you can trigger an action when the toast is clicked or when it is closed.

```python demo
rx.button("Show Toast", on_click=rx.toast("Hello, World!", duration=5000, close_button=True))
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

### Customization

If the presets don't fit your needs, you can customize the toasts by passing to `rx.toast` or to `rx.toast.options` some kwargs.

```python demo
rx.button(
    "Custom",
    on_click=rx.toast(
        "Custom Toast!",
        position="top-right",
        style={"background-color": "green", "color": "white", "border": "1px solid green", "border-radius": "0.53m"}
    )
)
```

The following props are available for customization:

- `description`: `str | Var`: Toast's description, renders underneath the title.
- `close_button`: `bool`: Whether to show the close button.
- `invert`: `bool`: Dark toast in light mode and vice versa.
- `important`: `bool`: Control the sensitivity of the toast for screen readers.
- `duration`: `int`: Time in milliseconds that should elapse before automatically closing the toast.
- `position`: `LiteralPosition`: Position of the toast.
- `dismissible`: `bool`: If false, it'll prevent the user from dismissing the toast.
- `action`: `ToastAction`: Renders a primary button, clicking it will close the toast.
- `cancel`: `ToastAction`: Renders a secondary button, clicking it will close the toast.
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

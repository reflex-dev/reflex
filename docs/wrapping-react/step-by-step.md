---
meta_description: Wrap a React color picker in Reflex, declare typed props and events, connect Python state, and troubleshoot imports and browser-only rendering.
---

# Wrapping React Step by Step

This guide wraps a React color picker as a Reflex component. You will pass a Python state value to a React prop, receive a color-change event, and update the page from Python.

The example uses [react-colorful](https://github.com/omgovich/react-colorful), which is also used in the [wrapping overview](/docs/wrapping-react/overview/). Start with a working Reflex project from the [installation guide](/docs/getting-started/installation/).

## 1. Identify the package and export

The npm package is `react-colorful`, and the named React export is `HexColorPicker`. Reflex needs both names: `library` identifies the package to install, while `tag` identifies the component to import.

This example pins the library to `react-colorful@5.7.0`. Reflex installs this frontend dependency during compilation; you do not install it with a Python package manager.

Use `is_default = True` only for a default export. `HexColorPicker` is a named export, so the example keeps the default value of `False`.

## 2. Declare the component's props

Subclass `NoSSRComponent` for this browser-rendered picker. Declare `color: rx.Var[str]` so a literal string or a reactive Reflex value can be passed as the React `color` prop.

A wrapper's Python field names use snake case. Reflex translates `on_change` to React's `onChange` prop. The event declaration `rx.EventHandler[lambda color: [color]]` extracts the string emitted by the picker and passes it to your Python handler.

Different React components emit different arguments. Check the library's documented callback signature instead of assuming every change event contains a browser event object.

## 3. Connect the event to Python state

The state stores the current hex color. The `set_color` event handler receives the emitted string and updates that state. Passing the state back as the picker's `color` prop makes this a controlled component: the picker and text readout share one value.

## 4. Run the complete example

Move the picker below to update the color value. To use this code in an app, copy the imports, component class, state class, and `wrapped_color_example` function into your app module, then register the function with `app.add_page(wrapped_color_example)`.

```python demo exec
import reflex as rx
from reflex.components.component import NoSSRComponent


class TutorialColorPicker(NoSSRComponent):
    library = "react-colorful@5.7.0"
    tag = "HexColorPicker"
    color: rx.Var[str]
    on_change: rx.EventHandler[lambda color: [color]]


class WrappedColorState(rx.State):
    color: str = "#6750a4"

    @rx.event
    def set_color(self, color: str):
        self.color = color


def wrapped_color_example():
    return rx.vstack(
        TutorialColorPicker.create(
            color=WrappedColorState.color,
            on_change=WrappedColorState.set_color,
        ),
        rx.text("Selected color: ", WrappedColorState.color),
        spacing="4",
        align="center",
    )
```

For a standalone app, add this after the example:

```python
app = rx.App()
app.add_page(wrapped_color_example)
```

Run your app with `reflex run`, open the page, and drag the picker. The text should change along with the picker. A plain `rx.Component` is appropriate for wrappers that support server rendering; use `NoSSRComponent` when a package needs browser APIs during rendering.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| The package or export cannot be found | Check the exact npm package name, version, exported tag, and whether it is a named or default export. |
| The picker moves but Python state does not change | Check that the prop is named `on_change`, that its event specification extracts the callback argument, and that the handler accepts that argument. |
| The text changes but the picker resets | Pass the state value as the `color` prop as well as connecting `on_change`. |
| A package raises `window is not defined` during rendering | Check whether it requires browser-only rendering and whether `NoSSRComponent` is appropriate. |
| A prop type fails to compile | Match the React library's documented type. Use typed `rx.Var` declarations for values that can be reactive. |

## Next steps

Add only the props and callbacks you need, and test them against the React library's public API. For reusable packaging, see [custom components](/docs/custom-components/overview/). For state and event behavior, see [events](/docs/events/events-overview/) and the [state overview](/docs/state/overview/).

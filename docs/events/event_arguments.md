```python exec
import reflex as rx
```

# Event Arguments

The event handler signature needs to match the event trigger definition argument count. If the event handler takes two arguments, the event trigger must be able to provide two arguments.

Here is a simple example:

```python demo exec

class EventArgStateSlider(rx.State):
    value: int = 50

    @rx.event
    def set_end(self, value: list[int | float]):
        self.value = value[0]


def slider_max_min_step():
    return rx.vstack(
        rx.heading(EventArgStateSlider.value),
        rx.slider(
            default_value=40,
            on_value_commit=EventArgStateSlider.set_end,
        ),
        width="100%",
    )

```

The event trigger here is `on_value_commit` and it is called when the value changes at the end of an interaction. This event trigger passes one argument, which is the value of the slider. The event handler which is triggered by the event trigger must therefore take one argument, which is `value` here.

Here is a form example:

```python demo exec

class EventArgState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def event_arg_example():
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.input(
                    placeholder="Name",
                    name="name",
                ),
                rx.checkbox("Checked", name="check"),
                rx.button("Submit", type="submit"),
            ),
            on_submit=EventArgState.handle_submit,
            reset_on_submit=True,
        ),
        rx.divider(),
        rx.heading("Results"),
        rx.text(EventArgState.form_data.to_string()),
    )
```

In this example the event trigger is the `on_submit` event of the form. The event handler is `handle_submit`. The `on_submit` event trigger passes one argument, the form data as a dictionary, to the `handle_submit` event handler. The `handle_submit` event handler must take one argument because the `on_submit` event trigger passes one argument.

When the number of args accepted by an EventHandler differs from that provided by the event trigger, an `EventHandlerArgMismatch` error will be raised.

## Pass Additional Arguments to Event Handlers

In some use cases, you want to pass additional arguments to your event handlers. To do this you can bind an event trigger to a lambda, which can call your event handler with the arguments you want.

Try typing a color in an input below and clicking away from it to change the color of the input.

```python demo exec
class ArgState(rx.State):
    colors: list[str] = ["rgba(245,168,152)", "MediumSeaGreen", "#DEADE3"]

    @rx.event
    def change_color(self, color: str, index: int):
        self.colors[index] = color

def event_arguments_example():
    return rx.hstack(
        rx.input(default_value=ArgState.colors[0], on_blur=lambda c: ArgState.change_color(c, 0), bg=ArgState.colors[0]),
        rx.input(default_value=ArgState.colors[1], on_blur=lambda c: ArgState.change_color(c, 1), bg=ArgState.colors[1]),
        rx.input(default_value=ArgState.colors[2], on_blur=lambda c: ArgState.change_color(c, 2), bg=ArgState.colors[2]),
    )

```

In this case, in we want to pass two arguments to the event handler `change_color`, the color and the index of the color to change.

The `on_blur` event trigger passes the text of the input as an argument to the lambda, and the lambda calls the `change_color` event handler with the text and the index of the input.

When the number of args accepted by a lambda differs from that provided by the event trigger, an `EventFnArgMismatch` error will be raised.

```md alert warning
# Event Handler Parameters should provide type annotations.

Like state vars, be sure to provide the right type annotations for the parameters in an event handler.
```

## Events with Partial Arguments (Advanced)

_Added in v0.5.0_

Event arguments in Reflex are passed positionally. Any additional arguments not
passed to an EventHandler will be filled in by the event trigger when it is
fired.

The following two code samples are equivalent:

```python
# Use a lambda to pass event trigger args to the EventHandler.
rx.text(on_blur=lambda v: MyState.handle_update("field1", v))

# Create a partial that passes event trigger args for any args not provided to the EventHandler.
rx.text(on_blur=MyState.handle_update("field1"))
```

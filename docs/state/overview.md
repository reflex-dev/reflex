```python exec
import reflex as rx
from pcweb.templates.docpage import definition
```

# State

State allows us to create interactive apps that can respond to user input.
It defines the variables that can change over time, and the functions that can modify them.

```md video https://youtube.com/embed/ITOZkzjtjUA?start=1206&end=1869
# Video: State Overview
```

## State Basics

You can define state by creating a class that inherits from `rx.State`:

```python
import reflex as rx


class State(rx.State):
    """Define your app state here."""
```

A state class is made up of two parts: vars and event handlers.

**Vars** are variables in your app that can change over time.

**Event handlers** are functions that modify these vars in response to events.

These are the main concepts to understand how state works in Reflex:

```python eval
rx.grid(
    definition(
        "Base Var",
        rx.list.unordered(
            rx.list.item("Any variable in your app that can change over time."),
            rx.list.item(
                "Defined as a field in a ", rx.code("State"), " class"
            ),
            rx.list.item("Can only be modified by event handlers."),
        ),
    ),
    definition(
        "Computed Var",
        rx.list.unordered(
            rx.list.item("Vars that change automatically based on other vars."),
            rx.list.item(
                "Defined as functions using the ",
                rx.code("@rx.var"),
                " decorator.",
            ),
            rx.list.item(
                "Cannot be set by event handlers, are always recomputed when the state changes."
            ),
        ),
    ),
    definition(
        "Event Trigger",
        rx.list.unordered(
            rx.list.item(
                "A user interaction that triggers an event, such as a button click."
            ),
            rx.list.item(
                "Defined as special component props, such as ",
                rx.code("on_click"),
                ".",
            ),
            rx.list.item("Can be used to trigger event handlers."),
        ),
    ),
    definition(
        "Event Handlers",
        rx.list.unordered(
            rx.list.item(
                "Functions that update the state in response to events."
            ),
            rx.list.item(
                "Defined as methods in the ", rx.code("State"), " class."
            ),
            rx.list.item(
                "Can be called by event triggers, or by other event handlers."
            ),
        ),
    ),
    margin_bottom="1em",
    spacing="2",
    columns="2",
)
```

## Example

Here is a example of how to use state within a Reflex app.
Click the text to change its color.

```python demo exec
class ExampleState(rx.State):

    # A base var for the list of colors to cycle through.
    colors: list[str] = ["black", "red", "green", "blue", "purple"]

    # A base var for the index of the current color.
    index: int = 0

    @rx.event
    def next_color(self):
        """An event handler to go to the next color."""
        # Event handlers can modify the base vars.
        # Here we reference the base vars `colors` and `index`.
        self.index = (self.index + 1) % len(self.colors)

    @rx.var
    def color(self)-> str:
        """A computed var that returns the current color."""
        # Computed vars update automatically when the state changes.
        return self.colors[self.index]


def index():
    return rx.heading(
        "Welcome to Reflex!",
        # Event handlers can be bound to event triggers.
        on_click=ExampleState.next_color,
        # State vars can be bound to component props.
        color=ExampleState.color,
        _hover={"cursor": "pointer"},
    )
```

The base vars are `colors` and `index`. They are the only vars in the app that
may be directly modified within event handlers.

There is a single computed var, `color`, that is a function of the base vars. It
will be computed automatically whenever the base vars change.

The heading component links its `on_click` event to the
`ExampleState.next_color` event handler, which increments the color index.

```md alert success
# With Reflex, you never have to write an API.

All interactions between the frontend and backend are handled through events.
```

```md alert info
# State vs. Instance?

When building the UI of your app, reference vars and event handlers via the state class (`ExampleState`).

When writing backend event handlers, access and set vars via the instance (`self`).
```

```md alert warning
# Cannot print a State var.

The code `print(ExampleState.index)` will not work because the State var values are only known at compile time.
```

## Client States

Each user who opens your app has a unique ID and their own copy of the state.
This means that each user can interact with the app and modify the state
independently of other users.

Because Reflex internally creates a new instance of the state for each user, your code should
never directly initialize a state class.

```md alert info
# Try opening an app in multiple tabs to see how the state changes independently.
```

All user state is stored on the server, and all event handlers are executed on
the server. Reflex uses websockets to send events to the server, and to send
state updates back to the client.

## Helper Methods

Similar to backend vars, any method defined in a State class that begins with an
underscore `_` is considered a helper method. Such methods are not usable as
event triggers, but may be called from other event handler methods within the
state.

Functionality that should only be available on the backend, such as an
authenticated action, should use helper methods to ensure it is not accidentally
or maliciously triggered by the client.

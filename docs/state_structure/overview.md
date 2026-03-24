```python exec
import reflex as rx
from typing import Any
```

# Substates

Substates allow you to break up your state into multiple classes to make it more manageable. This is useful as your app
grows, as it allows you to think about each page as a separate entity. Substates also allow you to share common state
resources, such as variables or event handlers.

When a particular state class becomes too large, breaking it up into several substates can bring performance
benefits by only loading parts of the state that are used to handle a certain event.

## Multiple States

One common pattern is to create a substate for each page in your app.
This allows you to think about each page as a separate entity, and makes it easier to manage your code as your app grows.

To create a substate, simply inherit from `rx.State` multiple times:

```python
# index.py
import reflex as rx

class IndexState(rx.State):
    """Define your main state here."""
    data: str = "Hello World"


@rx.page()
def index():
    return rx.box(rx.text(IndexState.data))

# signup.py
import reflex as rx


class SignupState(rx.State):
    """Define your signup state here."""
    username: str = ""
    password: str = ""

    def signup(self):
        ...


@rx.page()
def signup_page():
    return rx.box(
        rx.input(value=SignupState.username),
        rx.input(value=SignupState.password),
    )

# login.py
import reflex as rx

class LoginState(rx.State):
    """Define your login state here."""
    username: str = ""
    password: str = ""

    def login(self):
        ...

@rx.page()
def login_page():
    return rx.box(
        rx.input(value=LoginState.username),
        rx.input(value=LoginState.password),
    )
```

Separating the states is purely a matter of organization. You can still access the state from other pages by importing the state class.

```python
# index.py

import reflex as rx

from signup import SignupState

...

def index():
    return rx.box(
        rx.text(IndexState.data),
        rx.input(value=SignupState.username),
        rx.input(value=SignupState.password),
    )
```

## Accessing Arbitrary States

An event handler in a particular state can access and modify vars in another state instance by calling
the `get_state` async method and passing the desired state class. If the requested state is not already loaded,
it will be loaded and deserialized on demand.

In the following example, the `GreeterState` accesses the `SettingsState` to get the `salutation` and uses it
to update the `message` var.

Notably, the widget that sets the salutation does NOT have to load the `GreeterState` when handling the
input `on_change` event, which improves performance.

```python demo exec
class SettingsState(rx.State):
     salutation: str = "Hello"

     def set_salutation(self, value: str):
        self.salutation = value

def set_salutation_popover():
    return rx.popover.root(
        rx.popover.trigger(
            rx.icon_button(rx.icon("settings")),
        ),
        rx.popover.content(
            rx.input(
                value=SettingsState.salutation,
                on_change=SettingsState.set_salutation
            ),
        ),
    )


class GreeterState(rx.State):
    message: str = ""

    @rx.event
    async def handle_submit(self, form_data: dict[str, Any]):
        settings = await self.get_state(SettingsState)
        self.message = f"{settings.salutation} {form_data['name']}"


def index():
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.hstack(
                    rx.input(placeholder="Name", id="name"),
                    set_salutation_popover(),
                ),
                rx.button("Submit"),
            ),
            reset_on_submit=True,
            on_submit=GreeterState.handle_submit,
        ),
        rx.text(GreeterState.message),
    )
```

### Accessing Individual Var Values

In addition to accessing entire state instances with `get_state`, you can retrieve individual variable values using the `get_var_value` method:

```python
# Access a var value from another state
value = await self.get_var_value(OtherState.some_var)
```

This async method is particularly useful when you only need a specific value rather than loading the entire state. Using `get_var_value` can be more efficient than `get_state` when:

1. You only need to access a single variable from another state
2. The other state contains a large amount of data
3. You want to avoid loading unnecessary data into memory

Here's an example that demonstrates how to use `get_var_value` to access data between states:

```python demo exec
# Define a state that holds a counter value
class CounterState(rx.State):
    # This variable will be accessed from another state
    count: int = 0

    @rx.event
    async def increment(self):
        # Increment the counter when the button is clicked
        self.count += 1

# Define a separate state that will display information
class DisplayState(rx.State):
    # This will show the current count value
    message: str = ""

    @rx.event
    async def show_count(self):
        # Use get_var_value to access just the count variable from CounterState
        # This is more efficient than loading the entire state with get_state
        current = await self.get_var_value(CounterState.count)
        self.message = f"Current count: {current}"

def var_value_example():
    return rx.vstack(
        rx.heading("Get Var Value Example"),
        rx.hstack(
            # This button calls DisplayState.show_count to display the current count
            rx.button("Get Count Value", on_click=DisplayState.show_count),
            # This button calls CounterState.increment to increase the counter
            rx.button("Increment", on_click=CounterState.increment),
        ),
        # Display the message from DisplayState
        rx.text(DisplayState.message),
        width="100%",
        align="center",
        spacing="4",
    )
```

In this example:
1. We have two separate states: `CounterState` which manages a counter, and `DisplayState` which displays information
2. When you click "Increment", it calls `CounterState.increment()` to increase the counter value
3. When you click "Show Count", it calls `DisplayState.show_count()` which uses `get_var_value` to retrieve just the count value from `CounterState` without loading the entire state
4. The current count is then displayed in the message

This pattern is useful when you have multiple states that need to interact with each other but don't need to access all of each other's data.

If the var is not retrievable, `get_var_value` will raise an `UnretrievableVarValueError`.

## Performance Implications

When an event handler is called, Reflex will load the data not only for the substate containing
the event handler, but also all of its substates and parent states as well.
If a state has a large number of substates or contains a large amount of data, it can slow down processing
of events associated with that state.

For optimal performance, keep a flat structure with most substate classes directly inheriting from `rx.State`.
Only inherit from another state when the parent holds data that is commonly used by the substate.
Implementing different parts of the app with separate, unconnected states ensures that only the necessary
data is loaded for processing events for a particular page or component.

Avoid defining computed vars inside a state that contains a large amount of data, as
states with computed vars are always loaded to ensure the values are recalculated.
When using computed vars, it better to define them in a state that directly inherits from `rx.State` and
does not have other states inheriting from it, to avoid loading unnecessary data.

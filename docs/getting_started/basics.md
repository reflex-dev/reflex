```python exec
from pcweb.pages.docs import components, getting_started
from pcweb.pages.docs.library import library
from pcweb.pages.docs.custom_components import custom_components
from pcweb.pages import docs
import reflex as rx
```

# Reflex Basics

This page gives an introduction to the most common concepts that you will use to build Reflex apps.

```md section
# You will learn how to:

- Create and nest components
- Customize and style components
- Distinguish between compile-time and runtime
- Display data that changes over time
- Respond to events and update the screen
- Render conditions and lists
- Create pages and navigate between them
```

[Install]({docs.getting_started.installation.path}) `reflex` using pip.

```bash
pip install reflex
```

Import the `reflex` library to get started.

```python
import reflex as rx
```

## Creating and nesting components

[Components]({docs.ui.overview.path}) are the building blocks for your app's user interface (UI). They are the visual elements that make up your app, like buttons, text, and images. Reflex has a wide selection of [built-in components]({library.path}) to get you started quickly.

Components are created using functions that return a component object.

```python demo exec
def my_button():
    return rx.button("Click Me")
```

Components can be nested inside each other to create complex UIs.

To nest components as children, pass them as positional arguments to the parent component. In the example below, the `rx.text` and `my_button` components are children of the `rx.box` component.

```python demo exec
def my_page():
    return rx.box(
        rx.text("This is a page"),
        # Reference components defined in other functions.
        my_button()
    )
```

You can also use any base HTML element through the [`rx.el`]({docs.library.other.html.path}) namespace. This allows you to use standard HTML elements directly in your Reflex app when you need more control or when a specific component isn't available in the Reflex component library.

```python demo exec
def my_div():
    return rx.el.div(
        rx.el.p("Use base html!"),
    )
```

If you need a component not provided by Reflex, you can check the [3rd party ecosystem]({custom_components.path}) or [wrap your own React component]({docs.wrapping_react.library_and_tags.path}).

## Customizing and styling components

Components can be customized using [props]({docs.components.props.path}), which are passed in as keyword arguments to the component function.

Each component has props that are specific to that component. Check the docs for the component you are using to see what props are available.

```python demo exec
def half_filled_progress():
    return rx.progress(value=50)
```

In addition to component-specific props, components can also be styled using CSS properties passed as props.

```python demo exec
def round_button():
    return rx.button("Click Me", border_radius="15px", font_size="18px")
```

```md alert
Use the `snake_case` version of the CSS property name as the prop name.
```

See the [styling guide]({docs.styling.overview.path}) for more information on how to style components

In summary, components are made up of children and props.

```md definition
# Children

- Text or other Reflex components nested inside a component.
- Passed as **positional arguments**.

# Props

- Attributes that affect the behavior and appearance of a component.
- Passed as **keyword arguments**.
```

## Displaying data that changes over time

Apps need to store and display data that changes over time. Reflex handles this through [State]({docs.state.overview.path}), which is a Python class that stores variables that can change when the app is running, as well as the functions that can change those variables.

To define a state class, subclass `rx.State` and define fields that store the state of your app. The state variables ([vars]({docs.vars.base_vars.path})) should have a type annotation, and can be initialized with a default value.

```python
class MyState(rx.State):
    count: int = 0
```

### Referencing state vars in components

To reference a state var in a component, you can pass it as a child or prop. The component will automatically update when the state changes.

Vars are referenced through class attributes on your state class. For example, to reference the `count` var in a component, use `MyState.count`.

```python demo exec
class MyState(rx.State):
    count: int = 0
    color: str = "red"

def counter():
    return rx.hstack(
        # The heading `color` prop is set to the `color` var in MyState.
        rx.heading("Count: ", color=MyState.color),
        # The `count` var in `MyState` is passed as a child to the heading component.
        rx.heading(MyState.count),
    )
```

Vars can be referenced in multiple components, and will automatically update when the state changes.

## Responding to events and updating the screen

So far, we've defined state vars but we haven't shown how to change them. All state changes are handled through functions in the state class, called [event handlers]({docs.events.events_overview.path}).

```md alert
Event handlers are the ONLY way to change state in Reflex.
```

Components have special props, such as `on_click`, called event triggers that can be used to make components interactive. Event triggers connect components to event handlers, which update the state.

```python demo exec
class CounterState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

def counter_increment():
    return rx.hstack(
        rx.heading(CounterState.count),
        rx.button("Increment", on_click=CounterState.increment)
    )
```

When an event trigger is activated, the event handler is called, which updates the state. The UI is automatically re-rendered to reflect the new state. 


```md alert info
# What is the `@rx.event` decorator?
Adding the `@rx.event` decorator above the event handler is strongly recommended. This decorator enables proper static type checking, which ensures event handlers receive the correct number and types of arguments. This was introduced in Reflex version 0.6.5.
```

### Event handlers with arguments

Event handlers can also take in arguments. For example, the `increment` event handler can take an argument to increment the count by a specific amount.

```python demo exec
class CounterState2(rx.State):
    count: int = 0

    @rx.event
    def increment(self, amount: int):
        self.count += amount

def counter_variable():
    return rx.hstack(
        rx.heading(CounterState2.count),
        rx.button("Increment by 1", on_click=lambda: CounterState2.increment(1)),
        rx.button("Increment by 5", on_click=lambda: CounterState2.increment(5)),
    )
```

The `on_click` event trigger doesn't pass any arguments here, but some event triggers do. For example, the `on_blur` event trigger passes the text of an input as an argument to the event handler.

```python demo exec
class TextState(rx.State):
    text: str = ""

    @rx.event
    def update_text(self, new_text: str):
        self.text = new_text

def text_input():
    return rx.vstack(
        rx.heading(TextState.text),
        rx.input(default_value=TextState.text, on_blur=TextState.update_text),
    )
```

```md alert
Make sure that the event handler has the same number of arguments as the event trigger, or an error will be raised.
```

## Compile-time vs. runtime (IMPORTANT)

Before we dive deeper into state, it's important to understand the difference between compile-time and runtime in Reflex.

When you run your app, the frontend gets compiled to Javascript code that runs in the browser (compile-time). The backend stays in Python and runs on the server during the lifetime of the app (runtime).

### When can you not use pure Python?

We cannot compile arbitrary Python code, only the components that you define. What this means importantly is that you cannot use arbitrary Python operations and functions on state vars in components.

However, since any event handlers in your state are on the backend, you **can use any Python code or library** within your state.

### Examples that work

Within an event handler, use any Python code or library.

```python demo exec
def check_even(num: int):
    return num % 2 == 0

class MyState3(rx.State):
    count: int = 0
    text: str = "even"

    @rx.event
    def increment(self):
        # Use any Python code within state.
        # Even reference functions defined outside the state.
        if check_even(self.count):
            self.text = "even"
        else:
            self.text = "odd"
        self.count += 1

def count_and_check():
    return rx.box(
        rx.heading(MyState3.text),
        rx.button("Increment", on_click=MyState3.increment)
    )
```

Use any Python function within components, as long as it is defined at compile time (i.e. does not reference any state var)

```python demo exec
def show_numbers():
    return rx.vstack(
        *[
            rx.hstack(i, check_even(i))
            for i in range(10)
        ]
    )
```

### Examples that don't work

You cannot do an `if` statement on vars in components, since the value is not known at compile time.

```python
class BadState(rx.State):
    count: int = 0

def count_if_even():
    return rx.box(
        rx.heading("Count: "),
        # This will raise a compile error, as BadState.count is a var and not known at compile time.
        rx.text(BadState.count if BadState.count % 2 == 0 else "Odd"),
        # Using an if statement with a var as a prop will NOT work either.
        rx.text("hello", color="red" if BadState.count % 2 == 0 else "blue"),
    )
```

You cannot do a `for` loop over a list of vars.

```python
class BadState(rx.State):
    items: list[str] = ["Apple", "Banana", "Cherry"]

def loop_over_list():
    return rx.box(
        # This will raise a compile error, as BadState.items is a list and not known at compile time.
        *[rx.text(item) for item in BadState.items]
    )
```

You cannot do arbitrary Python operations on state vars in components.

```python
class BadTextState(rx.State):
    text: str = "Hello world"

def format_text():
    return rx.box(
        # Python operations such as `len` will not work on state vars.
        rx.text(len(BadTextState.text)),
    )
```

In the next sections, we will show how to handle these cases.

## Conditional rendering

As mentioned above, you cannot use Python `if/else` statements with state vars in components. Instead, use the [`rx.cond`]({docs.components.conditional_rendering.path}) function to conditionally render components.

```python demo exec
class LoginState(rx.State):
    logged_in: bool = False

    @rx.event
    def toggle_login(self):
        self.logged_in = not self.logged_in

def show_login():
    return rx.box(
        rx.cond(
            LoginState.logged_in,
            rx.heading("Logged In"),
            rx.heading("Not Logged In"),
        ),
        rx.button("Toggle Login", on_click=LoginState.toggle_login)
    )
```

## Rendering lists

To iterate over a var that is a list, use the [`rx.foreach`]({docs.components.rendering_iterables.path}) function to render a list of components.

Pass the list var and a function that returns a component as arguments to `rx.foreach`.

```python demo exec
class ListState(rx.State):
    items: list[str] = ["Apple", "Banana", "Cherry"]

def render_item(item: rx.Var[str]):
    """Render a single item."""
    # Note that item here is a Var, not a str!
    return rx.list.item(item)

def show_fruits():
    return rx.box(
        rx.foreach(ListState.items, render_item),
    )
```

The function that renders each item takes in a `Var`, since this will get compiled up front.

## Var Operations

You can't use arbitrary Python operations on state vars in components, but Reflex has [var operations]({docs.vars.var_operations.path}) that you can use to manipulate state vars.

For example, to check if a var is even, you can use the `%` and `==` var operations.

```python demo exec
class CountEvenState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

def count_if_even():
    return rx.box(
        rx.heading("Count: "),
        rx.cond(
            # Here we use the `%` and `==` var operations to check if the count is even.
            CountEvenState.count % 2 == 0,
            rx.text("Even"),
            rx.text("Odd"),
        ),
        rx.button("Increment", on_click=CountEvenState.increment),
    )
```

## App and Pages

Reflex apps are created by instantiating the `rx.App` class. Pages are linked to specific URL routes, and are created by defining a function that returns a component.

```python
def index():
    return rx.text('Root Page')

rx.app = rx.App()
app.add_page(index, route="/")
```

## Next Steps

Now that you have a basic understanding of how Reflex works, the next step is to start coding your own apps. Try one of the following tutorials:

- [Dashboard Tutorial]({getting_started.dashboard_tutorial.path})
- [Chatapp Tutorial]({getting_started.chatapp_tutorial.path})

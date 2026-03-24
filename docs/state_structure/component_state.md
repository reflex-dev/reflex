```python exec
import reflex as rx
from pcweb.pages.docs import events, ui, vars
```

# Component State

_New in version 0.4.6_.

Defining a subclass of `rx.ComponentState` creates a special type of state that is tied to an
instance of a component, rather than existing globally in the app. A Component State combines
[UI code]({ui.overview.path}) with state [Vars]({vars.base_vars.path}) and
[Event Handlers]({events.events_overview.path}),
and is useful for creating reusable components which operate independently of each other.

```md alert warning
# ComponentState cannot be used inside `rx.foreach()` as it will only create one state instance for all elements in the loop. Each iteration of the foreach will share the same state, which may lead to unexpected behavior.
```

## Using ComponentState

```python demo exec
class ReusableCounter(rx.ComponentState):
    count: int = 0

    @rx.event
    def set_count(self, value: int):
        self.count = value

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1

    @classmethod
    def get_component(cls, **props):
        return rx.hstack(
            rx.button("Decrement", on_click=cls.decrement),
            rx.text(cls.count),
            rx.button("Increment", on_click=cls.increment),
            **props,
        )

reusable_counter = ReusableCounter.create

def multiple_counters():
    return rx.vstack(
        reusable_counter(),
        reusable_counter(),
        reusable_counter(),
    )
```

The vars and event handlers defined on the `ReusableCounter`
class are treated similarly to a normal State class, but will be scoped to the component instance. Each time a
`reusable_counter` is created, a new state class for that instance of the component is also created.

The `get_component` classmethod is used to define the UI for the component and link it up to the State, which
is accessed via the `cls` argument. Other states may also be referenced by the returned component, but
`cls` will always be the instance of the `ComponentState` that is unique to the component being returned.

## Passing Props

Similar to a normal Component, the `ComponentState.create` classmethod accepts the arbitrary
`*children` and `**props` arguments, and by default passes them to your `get_component` classmethod.
These arguments may be used to customize the component, either by applying defaults or
passing props to certain subcomponents.

```python eval
rx.divider()
```

In the following example, we implement an editable text component that allows the user to click on
the text to turn it into an input field. If the user does not provide their own `value` or `on_change`
props, then the defaults defined in the `EditableText` class will be used.

```python demo exec
class EditableText(rx.ComponentState):
    text: str = "Click to edit"
    original_text: str
    editing: bool = False

    @rx.event
    def set_text(self, value: str):
        self.text = value

    @rx.event
    def start_editing(self, original_text: str):
        self.original_text = original_text
        self.editing = True

    @rx.event
    def stop_editing(self):
        self.editing = False
        self.original_text = ""

    @classmethod
    def get_component(cls, **props):
        # Pop component-specific props with defaults before passing **props
        value = props.pop("value", cls.text)
        on_change = props.pop("on_change", cls.set_text)
        cursor = props.pop("cursor", "pointer")

        # Set the initial value of the State var.
        initial_value = props.pop("initial_value", None)
        if initial_value is not None:
            # Update the pydantic model to use the initial value as default.
            cls.__fields__["text"].default = initial_value

        # Form elements for editing, saving and reverting the text.
        edit_controls = rx.hstack(
            rx.input(
                value=value,
                on_change=on_change,
                **props,
            ),
            rx.icon_button(
                rx.icon("x"),
                on_click=[
                    on_change(cls.original_text),
                    cls.stop_editing,
                ],
                type="button",
                color_scheme="red",
            ),
            rx.icon_button(rx.icon("check")),
            align="center",
            width="100%",
        )

        # Return the text or the form based on the editing Var.
        return rx.cond(
            cls.editing,
            rx.form(
                edit_controls,
                on_submit=lambda _: cls.stop_editing(),
            ),
            rx.text(
                value,
                on_click=cls.start_editing(value),
                cursor=cursor,
                **props,
            ),
        )


editable_text = EditableText.create


def editable_text_example():
    return rx.vstack(
        editable_text(),
        editable_text(initial_value="Edit me!", color="blue"),
        editable_text(initial_value="Reflex is fun", font_family="monospace", width="100%"),
    )
```

```python eval
rx.divider()
```

Because this `EditableText` component is designed to be reusable, it can handle the case
where the `value` and `on_change` are linked to a normal global state.

```python exec
# Hack because flexdown re-inits modules
EditableText._per_component_state_instance_count = 4
```

```python demo exec
class EditableTextDemoState(rx.State):
    value: str = "Global state text"

    @rx.event
    def set_value(self, value: str):
        self.value = value

def editable_text_with_global_state():
    return rx.vstack(
        editable_text(value=EditableTextDemoState.value, on_change=EditableTextDemoState.set_value),
        rx.text(EditableTextDemoState.value.upper()),
    )
```

## Accessing the State

The underlying state class of a `ComponentState` is accessible via the `.State` attribute. To use it,
assign an instance of the component to a local variable, then include that instance in the page.

```python exec
# Hack because flexdown re-inits modules
ReusableCounter._per_component_state_instance_count = 4
```

```python demo exec
def counter_sum():
    counter1 = reusable_counter()
    counter2 = reusable_counter()
    return rx.vstack(
        rx.text(f"Total: {counter1.State.count + counter2.State.count}"),
        counter1,
        counter2,
    )
```

```python eval
rx.divider()
```

Other components can also affect a `ComponentState` by referencing its event handlers or vars
via the `.State` attribute.

```python exec
# Hack because flexdown re-inits modules
ReusableCounter._per_component_state_instance_count = 6
```

```python demo exec
def extended_counter():
    counter1 = reusable_counter()
    return rx.vstack(
        counter1,
        rx.hstack(
            rx.icon_button(rx.icon("step_back"), on_click=counter1.State.set_count(0)),
            rx.icon_button(rx.icon("plus"), on_click=counter1.State.increment),
            rx.button("Double", on_click=counter1.State.set_count(counter1.State.count * 2)),
            rx.button("Triple", on_click=counter1.State.set_count(counter1.State.count * 3)),
        ),
    )
```

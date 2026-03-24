---
title: Props - Wrapping React 
---

# Props

When wrapping a React component, you want to define the props that will be accepted by the component.
This is done by defining the props and annotating them with a `rx.Var`.

Broadly, there are three kinds of props you can encounter when wrapping a React component:
1. **Simple Props**: These are props that are passed directly to the component. They can be of any type, including strings, numbers, booleans, and even lists or dictionaries.
2. **Callback Props**: These are props that expect to receive a function. That function will usually be called by the component as a callback. (This is different from event handlers.)
3. **Component Props**: These are props that expect to receive a components themselves. They can be used to create more complex components by composing them together.
4. **Event Handlers**: These are props that expect to receive a function that will be called when an event occurs. They are defined as `rx.EventHandler` with a signature function to define the spec of the event.

## Simple Props

Simple props are the most common type of props you will encounter when wrapping a React component. They are passed directly to the component and can be of any type (but most commonly strings, numbers, booleans, and structures).

For custom types, you can use `TypedDict` to define the structure of the custom types. However, if you need the attributes to be automatically converted to camelCase once compiled in JS, you can use `rx.PropsBase` instead of `TypedDict`.

```python
class CustomReactType(TypedDict):
    """Custom React type."""

    # Define the structure of the custom type to match the Javascript structure.
    attribute1: str
    attribute2: bool
    attribute3: int


class CustomReactType2(rx.PropsBase):
    """Custom React type."""

    # Define the structure of the custom type to match the Javascript structure.
    attr_foo: str # will be attrFoo in JS
    attr_bar: bool # will be attrBar in JS
    attr_baz: int # will be attrBaz in JS

class SimplePropsComponent(MyBaseComponent):
    """MyComponent."""

    # Type the props according the component documentation.
    
    # props annotated as `string` in javascript
    prop1: rx.Var[str] 
    
    # props annotated as `number` in javascript
    prop2: rx.Var[int]
    
    # props annotated as `boolean` in javascript
    prop3: rx.Var[bool] 
    
    # props annotated as `string[]` in javascript
    prop4: rx.Var[list[str]] 
    
    # props annotated as `CustomReactType` in javascript
    props5: rx.Var[CustomReactType] 

    # props annotated as `CustomReactType2` in javascript
    props6: rx.Var[CustomReactType2]

    # Sometimes a props will accept multiple types. You can use `|` to specify the types.
    # props annotated as `string | boolean` in javascript
    props7: rx.Var[str | bool] 
```

## Callback Props

Callback props are used to handle events or to pass data back to the parent component. They are defined as `rx.Var` with a type of `FunctionVar` or `Callable`.

```python
from typing import Callable
from reflex.vars.function import FunctionVar

class CallbackPropsComponent(MyBaseComponent):
    """MyComponent."""

    # A callback prop that takes a single argument.
    callback_props: rx.Var[Callable]
```

## Component Props
Some components will occasionally accept other components as props, usually annotated as `ReactNode`. In Reflex, these are defined as `rx.Component`.

```python
class ComponentPropsComponent(MyBaseComponent):
    """MyComponent."""

    # A prop that takes a component as an argument.
    component_props: rx.Var[rx.Component]
```

## Event Handlers
Event handlers are props that expect to receive a function that will be called when an event occurs. They are defined as `rx.EventHandler` with a signature function to define the spec of the event.

```python
from reflex.vars.event_handler import EventHandler
from reflex.vars.function import FunctionVar
from reflex.vars.object import ObjectVar

class InputEventType(TypedDict):
    """Input event type."""

    # Define the structure of the input event.
    foo: str
    bar: int

class OutputEventType(TypedDict):
    """Output event type."""

    # Define the structure of the output event.
    baz: str
    qux: int


def custom_spec1(event: ObjectVar[InputEventType]) -> tuple[str, int]:
    """Custom event spec using ObjectVar with custom type as input and tuple as output."""
    return (
        event.foo.to(str),
        event.bar.to(int),
    )

def custom_spec2(event: ObjectVar[dict]) -> tuple[Var[OutputEventType]]:
    """Custom event spec using ObjectVar with dict as input and custom type as output."""
    return Var.create(
        {
            "baz": event["foo"],
            "qux": event["bar"],
        },
    ).to(OutputEventType)

class EventHandlerComponent(MyBaseComponent):
    """MyComponent."""

    # An event handler that take no argument.
    on_event: rx.EventHandler[rx.event.no_args_event_spec]

    # An event handler that takes a single string argument.
    on_event_with_arg: rx.EventHandler[rx.event.passthrough_event_spec(str)]

    # An event handler specialized for input events, accessing event.target.value from the event.
    on_input_change: rx.EventHandler[rx.event.input_event]

    # An event handler specialized for key events, accessing event.key from the event and provided modifiers (ctrl, alt, shift, meta).
    on_key_down: rx.EventHandler[rx.event.key_event]

    # An event handler that takes a custom spec. (Event handler must expect a tuple of two values [str and int])
    on_custom_event: rx.EventHandler[custom_spec1]

    # Another event handler that takes a custom spec. (Event handler must expect a tuple of one value, being a OutputEventType)
    on_custom_event2: rx.EventHandler[custom_spec2]
```

```md alert info
# Custom event specs have a few use case where they are particularly useful. If the event returns non-serializable data, you can filter them out so the event can be sent to the backend. You can also use them to transform the data before sending it to the backend.
```

### Emulating Event Handler Behavior Outside a Component

In some instances, you may need to replicate the special behavior applied to
event handlers from outside of a component context. For example if the component
to be wrapped requires event callbacks passed in a dictionary, this can be
achieved by directly instantiating an `EventChain`.

A real-world example of this is the `onEvents` prop of
[`echarts-for-react`](https://www.npmjs.com/package/echarts-for-react) library,
which, unlike a normal event handler, expects a mapping of event handlers like:

```javascript
<ReactECharts
  option={this.getOption()}
  style={{ height: '300px', width: '100%' }}
  onEvents={{
    'click': this.onChartClick,
    'legendselectchanged': this.onChartLegendselectchanged
  }}
/>
```

To achieve this in Reflex, you can create an explicit `EventChain` for each
event handler:

```python
@classmethod
def create(cls, *children, **props):
    on_events = props.pop("on_events", {})

    event_chains = {}
    for event_name, handler in on_events.items():
        # Convert the EventHandler/EventSpec/lambda to an EventChain
        event_chains[event_name] = rx.EventChain.create(
            handler,
            args_spec=rx.event.no_args_event_spec,
            key=event_name,
        )
    if on_events:
        props["on_events"] = event_chains

    # Create the component instance
    return super().create(*children, **props)
```
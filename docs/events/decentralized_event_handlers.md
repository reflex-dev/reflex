```python exec
import reflex as rx
```

# Decentralized Event Handlers

## Overview

Decentralized event handlers allow you to define event handlers outside of state classes, providing more flexible code organization. This feature was introduced in Reflex v0.7.10 and enables a more modular approach to event handling.

With decentralized event handlers, you can:
- Organize event handlers by feature rather than by state class
- Separate UI logic from state management
- Create more maintainable and scalable applications

## Basic Usage

To create a decentralized event handler, use the `@rx.event` decorator on a function that takes a state instance as its first parameter:

```python demo exec
import reflex as rx

class MyState(rx.State):
    count: int = 0

@rx.event
def increment(state: MyState, amount: int):
    state.count += amount

def decentralized_event_example():
    return rx.vstack(
        rx.heading(f"Count: {MyState.count}"),
        rx.hstack(
            rx.button("Increment by 1", on_click=increment(1)),
            rx.button("Increment by 5", on_click=increment(5)),
            rx.button("Increment by 10", on_click=increment(10)),
        ),
        spacing="4",
        align="center",
    )
```

In this example:
1. We define a `MyState` class with a `count` variable
2. We create a decentralized event handler `increment` that takes a `MyState` instance as its first parameter
3. We use the event handler in buttons, passing different amounts to increment by

## Compared to Traditional Event Handlers

Here's a comparison between traditional event handlers defined within state classes and decentralized event handlers:

```python box
# Traditional event handler within a state class
class TraditionalState(rx.State):
    count: int = 0

    @rx.event
    def increment(self, amount: int = 1):
        self.count += amount

# Usage in components
rx.button("Increment", on_click=TraditionalState.increment(5))

# Decentralized event handler outside the state class
class DecentralizedState(rx.State):
    count: int = 0

@rx.event
def increment(state: DecentralizedState, amount: int = 1):
    state.count += amount

# Usage in components
rx.button("Increment", on_click=increment(5))
```

Key differences:
- Traditional event handlers use `self` to reference the state instance
- Decentralized event handlers explicitly take a state instance as the first parameter
- Both approaches use the same syntax for triggering events in components
- Both can be decorated with `@rx.event` respectively

## Best Practices

### When to Use Decentralized Event Handlers

Decentralized event handlers are particularly useful in these scenarios:

1. **Large applications** with many event handlers that benefit from better organization
2. **Feature-based organization** where you want to group related event handlers together
3. **Separation of concerns** when you want to keep state definitions clean and focused

### Type Annotations

Always use proper type annotations for your state parameter and any additional parameters:

```python box
@rx.event
def update_user(state: UserState, name: str, age: int):
    state.name = name
    state.age = age
```

### Naming Conventions

Follow these naming conventions for clarity:

1. Use descriptive names that indicate the action being performed
2. Use the state class name as the type annotation for the first parameter
3. Name the state parameter consistently across your codebase (e.g., always use `state` or the first letter of the state class)

### Organization

Consider these approaches for organizing decentralized event handlers:

1. Group related event handlers in the same file
2. Place event handlers near the state classes they modify
3. For larger applications, create a dedicated `events` directory with files organized by feature

```python box
# Example organization in a larger application
# events/user_events.py
@rx.event
def update_user(state: UserState, name: str, age: int):
    state.name = name
    state.age = age

@rx.event
def delete_user(state: UserState):
    state.name = ""
    state.age = 0
```

### Combining with Other Event Features

Decentralized event handlers work seamlessly with other Reflex event features:

```python box
# Background event
@rx.event(background=True)
async def long_running_task(state: AppState):
    # Long-running task implementation
    pass

# Event chaining
@rx.event
def process_form(state: FormState, data: dict):
    # Process form data
    return validate_data  # Chain to another event
```

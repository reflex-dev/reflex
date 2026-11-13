```python exec
import random
import time
import asyncio

import reflex as rx
```

# Computed Vars

Computed vars have values derived from other properties on the backend. They are
defined as methods in your State class with the `@rx.var` decorator.

Try typing in the input box and clicking out.

```python demo exec id=upper
class UppercaseState(rx.State):
    text: str = "hello"

    def set_text(self, value: str):
        self.text = value

    @rx.var
    def upper_text(self) -> str:
        # This will be recomputed whenever `text` changes.
        return self.text.upper()


def uppercase_example():
    return rx.vstack(
        rx.heading(UppercaseState.upper_text, as_="h2"),
        rx.input(on_blur=UppercaseState.set_text, placeholder="Type here..."),
    )
```

```python test
def test_computed_var_uppercases_on_blur(demo):
    heading = demo.get_by_role("heading")
    expect(heading).to_have_text("HELLO")
    field = demo.get_by_placeholder("Type here...")
    field.fill("reflex rocks")
    expect(heading).to_have_text("HELLO")
    field.blur()
    expect(heading).to_have_text("REFLEX ROCKS")
```

Here, `upper_text` is a computed var that always holds the upper case version of `text`.

We recommend always using type annotations for computed vars.

## Cached Vars

By default, all computed vars are cached (`cache=True`). A cached var is only
recomputed when the other state vars it depends on change. This is useful for
expensive computations, but in some cases it may not update when you expect it to.

To create a computed var that recomputes on every state update regardless of
dependencies, use `@rx.var(cache=False)`.

An uncached var is recomputed for every state update, but the recomputed value is
only sent to the frontend when it differs from the value that was last sent, so a
recomputation that yields the same value does not trigger a re-render.

Previous versions of Reflex had a `@rx.cached_var` decorator, which is now replaced
by the `cache` argument of `@rx.var` (which defaults to `True`).

```python demo exec
class CachedVarState(rx.State):
    counter_a: int = 0
    counter_b: int = 0

    @rx.var(cache=False)
    def last_touch_time(self) -> str:
        # This is updated anytime the state is updated.
        return time.strftime("%H:%M:%S")

    @rx.event
    def increment_a(self):
        self.counter_a += 1

    @rx.var(cache=True)
    def last_counter_a_update(self) -> str:
        # This is updated only when `counter_a` changes.
        return f"{self.counter_a} at {time.strftime('%H:%M:%S')}"

    @rx.event
    def increment_b(self):
        self.counter_b += 1

    @rx.var(cache=True)
    def last_counter_b_update(self) -> str:
        # This is updated only when `counter_b` changes.
        return f"{self.counter_b} at {time.strftime('%H:%M:%S')}"


def cached_var_example():
    return rx.vstack(
        rx.text(f"State touched at: {CachedVarState.last_touch_time}"),
        rx.text(f"Counter A: {CachedVarState.last_counter_a_update}"),
        rx.text(f"Counter B: {CachedVarState.last_counter_b_update}"),
        rx.hstack(
            rx.button("Increment A", on_click=CachedVarState.increment_a),
            rx.button("Increment B", on_click=CachedVarState.increment_b),
        ),
    )
```

```python test
def test_cached_vars_update_only_on_dependency(demo):
    time_re = r"\d\d:\d\d:\d\d"
    counter_a = demo.get_by_text("Counter A:")
    counter_b = demo.get_by_text("Counter B:")
    expect(demo.get_by_text("State touched at:")).to_have_text(
        re.compile(rf"^State touched at: {time_re}$")
    )
    expect(counter_a).to_have_text(re.compile(rf"^Counter A: 0 at {time_re}$"))
    expect(counter_b).to_have_text(re.compile(rf"^Counter B: 0 at {time_re}$"))
    demo.get_by_role("button", name="Increment B").click()
    expect(counter_b).to_have_text(re.compile(rf"^Counter B: 1 at {time_re}$"))
    counter_b_before = counter_b.inner_text()
    demo.get_by_role("button", name="Increment A").click()
    expect(counter_a).to_have_text(re.compile(rf"^Counter A: 1 at {time_re}$"))
    expect(counter_b).to_have_text(counter_b_before)
```

In this example `last_touch_time` uses `cache=False` to ensure it updates any
time the state is modified. `last_counter_a_update` is a cached computed var (using
the default `cache=True`) that only depends on `counter_a`, so it only gets recomputed
when `counter_a` changes. Similarly `last_counter_b_update` only depends on `counter_b`,
and thus is updated only when `counter_b` changes.

## Async Computed Vars

Async computed vars allow you to use asynchronous operations in your computed vars.
They are defined as async methods in your State class with the same `@rx.var` decorator.
Async computed vars are useful for operations that require asynchronous processing, such as:

- Fetching data from external APIs
- Database operations
- File I/O operations
- Any other operations that benefit from async/await

```python demo exec
class AsyncVarState(rx.State):
    count: int = 0

    @rx.var
    async def delayed_count(self) -> int:
        # Simulate an async operation like an API call
        await asyncio.sleep(0.5)
        return self.count * 2

    @rx.event
    def increment(self):
        self.count += 1


def async_var_example():
    return rx.vstack(
        rx.heading("Async Computed Var Example", as_="h2"),
        rx.text(f"Count: {AsyncVarState.count}"),
        rx.text(f"Delayed count (x2): {AsyncVarState.delayed_count}"),
        rx.button("Increment", on_click=AsyncVarState.increment),
        spacing="4",
    )
```

```python test
def test_async_computed_var(demo):
    expect(demo.get_by_role("heading")).to_have_text("Async Computed Var Example")
    expect(demo.get_by_text("Count:", exact=False).first).to_have_text("Count: 0")
    delayed = demo.get_by_text("Delayed count (x2):")
    expect(delayed).to_have_text("Delayed count (x2): 0")
    demo.get_by_role("button", name="Increment").click()
    demo.get_by_role("button", name="Increment").click()
    expect(demo.get_by_text("Count:", exact=False).first).to_have_text("Count: 2")
    expect(delayed).to_have_text("Delayed count (x2): 4")
```

In this example, `delayed_count` is an async computed var that returns the count multiplied by 2 after a simulated delay.
When the count changes, the async computed var is automatically recomputed.

### Caching Async Computed Vars

Just like regular computed vars, async computed vars can also be cached. This is especially
useful for expensive async operations like API calls or database queries.

```python demo exec
class AsyncCachedVarState(rx.State):
    user_id: int = 1
    refresh_trigger: int = 0

    @rx.var(cache=True)
    async def user_data(self) -> dict:
        # In a real app, this would be an API call
        await asyncio.sleep(1)  # Simulate network delay

        # Simulate different user data based on user_id
        users = {
            1: {"name": "Alice", "email": "alice@example.com"},
            2: {"name": "Bob", "email": "bob@example.com"},
            3: {"name": "Charlie", "email": "charlie@example.com"},
        }

        return users.get(self.user_id, {"name": "Unknown", "email": "unknown"})

    @rx.event
    def change_user(self):
        # Cycle through users 1-3
        self.user_id = (self.user_id % 3) + 1

    @rx.event
    def force_refresh(self):
        # This will not affect user_data dependencies, but will trigger a state update
        self.refresh_trigger += 1


def async_cached_var_example():
    return rx.vstack(
        rx.heading("Cached Async Computed Var Example", as_="h2"),
        rx.text(f"User ID: {AsyncCachedVarState.user_id}"),
        rx.text(f"User Name: {AsyncCachedVarState.user_data['name']}"),
        rx.text(f"User Email: {AsyncCachedVarState.user_data['email']}"),
        rx.hstack(
            rx.button("Change User", on_click=AsyncCachedVarState.change_user),
            rx.button(
                "Force Refresh (No Effect)", on_click=AsyncCachedVarState.force_refresh
            ),
        ),
        rx.text(
            "Note: The cached async var only updates when user_id changes, not when refresh_trigger changes."
        ),
        spacing="4",
    )
```

```python test
def test_cached_async_computed_var(demo):
    user = demo.get_by_text(re.compile(r"^User (ID|Name|Email):"))
    expect(demo.get_by_role("heading")).to_have_text(
        "Cached Async Computed Var Example"
    )
    expect(user).to_have_text([
        "User ID: 1",
        "User Name: Alice",
        "User Email: alice@example.com",
    ])
    demo.get_by_role("button", name="Change User").click()
    expect(user).to_have_text([
        "User ID: 2",
        "User Name: Bob",
        "User Email: bob@example.com",
    ])
    demo.get_by_role("button", name="Force Refresh (No Effect)").click()
    expect(user).to_have_text([
        "User ID: 2",
        "User Name: Bob",
        "User Email: bob@example.com",
    ])
```

In this example, `user_data` is a cached async computed var that simulates fetching user data.
It is only recomputed when `user_id` changes, not when other state variables like `refresh_trigger` change.
This demonstrates how caching works with async computed vars to optimize performance for expensive operations.

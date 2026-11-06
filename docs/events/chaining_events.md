```python exec
import reflex as rx
```

# Chaining events

## Calling Event Handlers From Event Handlers

You can call other event handlers from event handlers to keep your code modular. Just use the `self.call_handler` syntax to run another event handler. As always, you can yield within your function to send incremental updates to the frontend.

```python demo exec id=call-handler
import asyncio


class CallHandlerState(rx.State):
    count: int = 0
    progress: int = 0

    @rx.event
    def set_progress(self, value: int):
        self.progress = value

    @rx.event
    async def run(self):
        # Reset the count.
        self.set_progress(0)
        yield

        # Count to 10 while showing progress.
        for i in range(10):
            # Wait and increment.
            await asyncio.sleep(0.5)
            self.count += 1

            # Update the progress.
            self.set_progress(i + 1)

            # Yield to send the update.
            yield


def call_handler_example():
    return rx.vstack(
        rx.badge(CallHandlerState.count, font_size="1.5em", color_scheme="green"),
        rx.progress(value=CallHandlerState.progress, max=10, width="100%"),
        rx.button("Run", on_click=CallHandlerState.run),
    )
```

## Awaiting Event Handlers

An event handler accessed through its state class is awaitable. `await` runs it
right away, inside the current event, and gives back its return value. The
awaited handler runs on the same locked state as the caller, its `yield`s send
updates to the frontend as usual, and any backend events it yields or returns
are queued after the current event, as if the caller had yielded them;
frontend-only events are sent to the frontend immediately.

```python demo exec id=await-handler
class AwaitHandlerState(rx.State):
    total: int = 0
    last_added: int = 0

    @rx.event
    def add(self, amount: int) -> int:
        """Add to the total and return the new total."""
        self.total += amount
        self.last_added = amount
        return self.total

    @rx.event
    async def add_twice(self, amount: int):
        first = await type(self).add(amount)
        second = await type(self).add(amount)
        yield rx.toast(f"{first} then {second}")


def await_handler_example():
    return rx.vstack(
        rx.text(f"Total: {AwaitHandlerState.total}"),
        rx.button("Add 5 twice", on_click=AwaitHandlerState.add_twice(5)),
    )
```

Compared to calling the handler as a method of `self`, awaiting it converts
the arguments like an event from the frontend, sends an update when it yields,
and works for a handler of any state in the app, not only the caller's own
state.

```md alert info
# Rules for awaiting event handlers

- Only inside an event handler (or `app.modify_state`); awaiting a handler anywhere else raises an error.
- Calling the handler, like `State.add(5)`, only binds its arguments. Nothing runs until it is awaited, so it can still be returned or yielded as before. Each `await` runs it again.
- A background task awaiting a handler outside `async with self` queues the event and waits for it to finish; inside `async with self` the handler runs right away on the locked state.
- A background handler cannot be awaited while the state lock is held, as it would wait for that lock. `yield` it instead.
- Frontend-only events like `rx.redirect` cannot be awaited. `yield` or return them.
- Awaiting several handlers at once with `asyncio.gather` works, but they run concurrently on the same state and interleave at every `await` inside them. Await them one at a time when order matters.
- A task started from a handler, like `asyncio.ensure_future(State.add(1))`, keeps the state lock held until it finishes when it starts before the handler returns. If the handler returns first, the task's handler is queued like a yielded event and runs under its own lock.
```

## Returning Events From Event Handlers

So far, we have only seen events that are triggered by components. However, an event handler can also return events.

In Reflex, event handlers run synchronously, so only one event handler can run at a time, and the events in the queue will be blocked until the current event handler finishes. The difference between returning an event and calling an event handler is that a returned event is queued and runs after the current handler finishes.

```md alert info
# Be sure to use the class name `State` (or any substate) rather than `self` when returning events.
```

Try entering an integer in the input below then clicking out.

```python demo exec id=collatz
class CollatzState(rx.State):
    count: int = 1

    @rx.event
    def start_collatz(self, count: str):
        """Run the collatz conjecture on the given number."""
        self.count = abs(int(count if count else 1))
        return CollatzState.run_step

    @rx.event
    async def run_step(self):
        """Run a single step of the collatz conjecture."""

        while self.count > 1:
            await asyncio.sleep(0.5)

            if self.count % 2 == 0:
                # If the number is even, divide by 2.
                self.count //= 2
            else:
                # If the number is odd, multiply by 3 and add 1.
                self.count = self.count * 3 + 1
            yield


def collatz_example():
    return rx.vstack(
        rx.badge(CollatzState.count, font_size="1.5em", color_scheme="green"),
        rx.input(on_blur=CollatzState.start_collatz),
    )
```

In this example, we run the [Collatz Conjecture](https://en.wikipedia.org/wiki/Collatz_conjecture) on a number entered by the user.

When the `on_blur` event is triggered, the event handler `start_collatz` is called. It sets the initial count, then calls `run_step` which runs until the count reaches `1`.

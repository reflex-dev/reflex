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

## Returning Events From Event Handlers

So far, we have only seen events that are triggered by components. However, an event handler can also return events.

In Reflex, event handlers run synchronously, so only one event handler can run at a time, and the events in the queue will be blocked until the current event handler finishes.The difference between returning an event and calling an event handler is that returning an event will send the event to the frontend and unblock the queue.

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

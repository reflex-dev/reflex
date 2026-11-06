```python exec
import reflex as rx
```

# Yielding Updates

A regular event handler will send a `StateUpdate` when it has finished running. This works fine for basic event, but sometimes we need more complex logic. To update the UI multiple times in an event handler, we can `yield` when we want to send an update.

To do so, we can use the Python keyword `yield`. For every yield inside the function, a `StateUpdate` will be sent to the frontend with the changes up to this point in the execution of the event handler.

A foreground event handler that raises an exception or is cancelled keeps the state changes it made, as long as it still holds the state lock. This includes updates already yielded to the frontend before another invocation of an `@rx.event(supersedes=True)` handler cancels it. When using Redis, a change made after the handler's last `yield` is stored, but the frontend receives it only when a later update changes the same var, or after a page reload.

This example below shows how to yield 100 updates to the UI.

```python demo exec
class MultiUpdateState(rx.State):
    count: int = 0

    @rx.event
    def timed_update(self):
        for i in range(100):
            self.count += 1
            yield


def multi_update():
    return rx.vstack(
        rx.text(MultiUpdateState.count),
        rx.button("Start", on_click=MultiUpdateState.timed_update),
    )
```

Here is another example of yielding multiple updates with a loading icon.

```python demo exec
import asyncio


class ProgressExampleState(rx.State):
    count: int = 0
    show_progress: bool = False

    @rx.event
    async def increment(self):
        self.show_progress = True
        yield
        # Think really hard.
        await asyncio.sleep(0.5)
        self.count += 1
        self.show_progress = False


def progress_example():
    return rx.button(
        ProgressExampleState.count,
        on_click=ProgressExampleState.increment,
        loading=ProgressExampleState.show_progress,
    )
```

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6463&end=6835
# Video: Asyncio with Yield
```

## Yielding Other Events

Events can also yield other events. This is useful when you want to chain events together. To do this, you can yield the event handler function itself.

```md alert
# Reference other Event Handler via class

When chaining another event handler with `yield`, access it via the state class, not `self`.
```

```python demo exec
import asyncio


class YieldEventsState(rx.State):
    count: int = 0
    show_progress: bool = False

    @rx.event
    async def add_five(self):
        self.show_progress = True
        yield
        # Think really hard.
        await asyncio.sleep(1)
        self.count += 5
        self.show_progress = False

    @rx.event
    async def increment(self):
        yield YieldEventsState.add_five
        yield YieldEventsState.add_five
        yield YieldEventsState.add_five


def multiple_yield_example():
    return rx.button(
        YieldEventsState.count,
        on_click=YieldEventsState.increment,
        loading=YieldEventsState.show_progress,
    )
```

## Yielding Values to the Frontend

A handler can also `yield` or `return` a value that is not an event: a string,
a number, a list, a dict, a dataclass, or anything else Reflex can serialize
for a state var. Each such value is sent to the frontend code that dispatched
the event, after the state changes made before it.

```python
class SearchState(rx.State):
    searching: bool = False

    @rx.event
    async def search(self, query: str):
        self.searching = True
        yield
        async for hit in search_service.stream(query):
            yield hit
        self.searching = False

    @rx.event
    def load_rows(self, page: int) -> list[dict]:
        return db.rows(page)
```

In the browser, dispatching an event returns a result stream. Iterate it with
`for await` to receive each value as it arrives, or `await` it to get the last
value. It rejects if the handler raises.

```javascript
for await (const hit of addEvents([searchEvent])) {
  render(hit);
}
const rows = await addEvents([loadRowsEvent]);
```

Here `searchEvent` and `loadRowsEvent` stand for the rendered events, such as
`rx.Var.create(SearchState.load_rows(2))`, which renders the
`ReflexEvent(...)` for that call.

An event trigger made of a single event handler returns this stream too, so it
can be passed to a React prop that expects an async callback. See
[Async Callback Props](/docs/wrapping-react/props/#async-callback-props).

```md alert info
# Rules for values sent to the frontend

- Events are still events, not values: a backend event, event handler, or a list of them is queued, and a frontend-only event like `rx.redirect` is sent to the browser to run. A list that mixes events with other values raises a `TypeError`, and so does a coroutine the handler did not await.
- An empty list is a value, not an empty list of events.
- An `async` generator cannot `return` a value; `yield` the last one instead.
- The stream ends when the handler finishes. It does not include values from the events the handler chains, and does not wait for them.
- A handler run with `await` from another handler gives its value to that handler, not to the frontend.
- When the handler is cancelled, the stream ends normally with the values sent so far. When the connection drops before the handler finishes, the stream rejects.
- In production, a rejected stream says only "Contact the website administrator."; the details are in the backend logs.
```

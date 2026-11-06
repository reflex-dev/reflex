Event handlers are awaitable: `await State.handler(args)` inside another event handler runs it right away on the same locked state and returns its result, so a handler may return a value to the backend code awaiting it (returned events still chain, and a returned coroutine still raises). `@rx.event` returns the `EventHandler` itself, a function without a state parameter registers as a stateless handler that a frontend event runs without taking the state lock (awaited from another handler, it runs inline under the caller's lock), and `self.handler()` keeps calling the plain method as before.

```python
@rx.event
def add(self, amount: int) -> int:
    self.total += amount
    return self.total


@rx.event
async def add_twice(self, amount: int):
    first = await type(self).add(amount)
    yield rx.toast(f"total is now {await type(self).add(amount)}")
```

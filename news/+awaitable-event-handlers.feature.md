Event handlers are awaitable: `await State.handler(args)` inside another event handler runs it right away on the same locked state and returns its result, and a handler may now return any value rather than only events. `@rx.event` returns the `EventHandler` itself, a function without a state parameter registers as a stateless handler that runs without the state lock, and `self.handler()` keeps calling the plain method as before.

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

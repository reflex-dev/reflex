An event handler's non-event `yield` and `return` values now reach the frontend code that dispatched the event: `addEvents(...)` returns a result stream to iterate with `for await` or `await` for the last value, and it rejects when the handler raises. A trigger made of one event handler returns the stream too, so it can be passed to a React prop expecting an async callback (like `loadOptions`). Yielding a non-event value no longer raises `TypeError`. See [Yielding Values to the Frontend](https://reflex.dev/docs/events/yield-events/#yielding-values-to-the-frontend).

```python
@rx.event
def load_rows(self, page: int) -> list[dict]:
    return db.rows(page)
```

```javascript
const rows = await addEvents([ReflexEvent("state.load_rows", { page })]);
```

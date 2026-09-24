```python exec
import reflex as rx
```

# Special Events

Reflex also has built-in special events can be found in the [reference](/docs/api-reference/special-events/).

For example, an event handler can trigger an alert on the browser.

```python demo exec
class SpecialEventsState(rx.State):
    @rx.event
    def alert(self):
        return rx.window_alert("Hello World!")


def special_events_example():
    return rx.button("Alert", on_click=SpecialEventsState.alert)
```

Special events can also be triggered directly in the UI by attaching them to an event trigger.

```python
def special_events_example():
    return rx.button("Alert", on_click=rx.window_alert("Hello World!"))
```

## Speculative Updates

A round trip to the backend takes a while for distant users. To keep the app
feeling snappy, `dispatch_value` shows a value for a state var on the frontend
right away, like a spinner as soon as a button is clicked. The value stays
until the backend sends a value for the var, which replaces it.

```python demo exec
import asyncio


class SpeculativeState(rx.State):
    loading: rx.Field[bool] = rx.field(False)

    @rx.event
    async def work(self):
        await asyncio.sleep(1)
        self.loading = False


def speculative_example():
    return rx.button(
        "Work",
        loading=SpeculativeState.loading,
        on_click=[SpeculativeState.loading.dispatch_value(True), SpeculativeState.work],
    )
```

Only state vars sent to the client can be dispatched; backend vars have no
value on the frontend. Since the backend only sends the vars that changed, a
handler should set any var it lets the frontend change, as `work` sets
`loading` above.

Events keep their order: a value dispatched after other frontend events, like
`rx.call_script`, is shown once they have run, so put `dispatch_value` first to
show it right away, even before the app has connected to the backend.

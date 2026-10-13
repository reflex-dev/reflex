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
feeling snappy, `dispatch_value` can be used to set a value
for a state var on the frontend immediately, for example, to show a spinner as
soon as a button is clicked. The value stays
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

Only state vars sent to the client can be dispatched: backend vars have no
value on the frontend, and only the backend computes computed vars. A computed
var that depends on a dispatched var keeps its old value until the backend
sends it, which it does once a handler sets the var it depends on.

Since the backend only sends the vars that changed, a handler should set any
var it lets the frontend change, as `work` sets `loading` above. A handler that
raises sends no update, unless it is a background task, so it should catch its
errors and still set the var.

The next value the backend sends for the var replaces the dispatched one, even
when it comes from an older event. For example, with
`on_change=lambda value: [State.text.dispatch_value(value), State.echo(value)]`,
where `echo` takes a second to set `text`, typing "abc" quickly shows `abc` right
away, then `a` and `ab` as the older events finish, before `abc` again. Avoid
dispatching a var that slow handlers of earlier events also set.

Events keep their order: a value dispatched after other frontend events, like
`rx.call_script`, is shown once they have run, so put `dispatch_value` first to
show it right away, even before the app has connected to the backend.

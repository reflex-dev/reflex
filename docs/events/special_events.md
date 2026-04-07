```python exec
import reflex as rx
```

# Special Events

Reflex also has built-in special events can be found in the [reference](/docs/api-reference/special_events).

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

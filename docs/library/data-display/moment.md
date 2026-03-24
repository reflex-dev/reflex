---
components:
    - rx.moment

---

# Moment

Displaying date and relative time to now sometimes can be more complicated than necessary.

To make it easy, Reflex is wrapping [react-moment](https://www.npmjs.com/package/react-moment)  under `rx.moment`.


```python exec
import reflex as rx
from reflex.utils.serializers import serialize_datetime
from pcweb.templates.docpage import docdemo, docdemobox, doccode, docgraphing
```

## Examples

Using a date from a state var as a value, we will display it in a few different
way using `rx.moment`.

The `date_now` state var is initialized when the site was deployed. The
button below can be used to update the var to the current datetime, which will
be reflected in the subsequent examples.

```python demo exec
from datetime import datetime, timezone

class MomentState(rx.State):
    date_now: datetime = datetime.now(timezone.utc)

    @rx.event
    def update(self):
        self.date_now = datetime.now(timezone.utc)


def moment_update_example():
    return rx.button("Update", rx.moment(MomentState.date_now), on_click=MomentState.update)
```

### Display the date as-is:

```python demo
rx.moment(MomentState.date_now)
```

### Humanized interval

Sometimes we don't want to display just a raw date, but we want something more instinctive to read. That's when we can use `from_now` and `to_now`.

```python demo
rx.moment(MomentState.date_now, from_now=True)
```

```python demo
rx.moment(MomentState.date_now, to_now=True)
```
You can also set a duration (in milliseconds) with `from_now_during` where the date will display as relative, then after that, it will be displayed as defined in `format`.

```python demo
rx.moment(MomentState.date_now, from_now_during=100000)  # after 100 seconds, date will display normally
```

### Formatting dates

```python demo
rx.moment(MomentState.date_now, format="YYYY-MM-DD")
```

```python demo
rx.moment(MomentState.date_now, format="HH:mm:ss")
```

### Offset Date

With the props `add` and `subtract`, you can pass an `rx.MomentDelta` object to modify the displayed date without affecting the stored date in your state.

```python exec
add_example = """rx.vstack(
    rx.moment(MomentState.date_now, add=rx.MomentDelta(years=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(quarters=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(months=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(months=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(months=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(weeks=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(days=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(hours=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(minutes=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, add=rx.MomentDelta(seconds=2), format="YYYY-MM-DD - HH:mm:ss"),
)
"""
subtract_example = """rx.vstack(
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(years=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(quarters=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(months=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(months=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(months=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(weeks=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(days=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(hours=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(minutes=2), format="YYYY-MM-DD - HH:mm:ss"),
    rx.moment(MomentState.date_now, subtract=rx.MomentDelta(seconds=2), format="YYYY-MM-DD - HH:mm:ss"),
)
"""
```

```python eval
rx.tabs(
    rx.tabs.list(
        rx.tabs.trigger("Add", value="add"),
        rx.tabs.trigger("Subtract", value="subtract")
    ),
    rx.tabs.content(docdemo(add_example, comp=eval(add_example)), value="add"),
    rx.tabs.content(docdemo(subtract_example, comp=eval(subtract_example)), value="subtract"),
    default_value="add",
)
```

### Timezones

You can also set dates to display in a specific timezone:

```python demo
rx.vstack(
    rx.moment(MomentState.date_now, tz="America/Los_Angeles"),
    rx.moment(MomentState.date_now, tz="Europe/Paris"),
    rx.moment(MomentState.date_now, tz="Asia/Tokyo"),
)
```

### Client-side periodic update

If a date is not passed to `rx.moment`, it will use the client's current time.

If you want to update the date every second, you can use the `interval` prop.

```python demo
rx.moment(interval=1000, format="HH:mm:ss")
```

Even better, you can actually link an event handler to the `on_change` prop that will be called every time the date is updated:

```python demo exec
class MomentLiveState(rx.State):
    updating: bool = False

    @rx.event
    def on_update(self, date):
        return rx.toast(f"Date updated: {date}")

    @rx.event
    def set_updating(self, value: bool):
        self.updating = value

def moment_live_example():
    return rx.hstack(
        rx.moment(
            format="HH:mm:ss",
            interval=rx.cond(MomentLiveState.updating, 5000, 0),
            on_change=MomentLiveState.on_update,
        ),
        rx.switch(
            is_checked=MomentLiveState.updating,
            on_change=MomentLiveState.set_updating,
        ),
    )
```

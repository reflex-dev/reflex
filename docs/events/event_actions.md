```python exec
import reflex as rx
import datetime
```

# Event Actions

In Reflex, an event action is a special behavior that occurs during or after
processing an event on the frontend.

Event actions can modify how the browser handles DOM events or throttle and
debounce events before they are processed by the backend.

An event action is specified by accessing attributes and methods present on all
EventHandlers and EventSpecs.

## DOM Event Propagation

_Added in v0.3.2_

### prevent_default

The `.prevent_default` action prevents the default behavior of the browser for
the action. This action can be added to any existing event, or it can be used on its own by
specifying `rx.prevent_default` as an event handler.

A common use case for this is to prevent navigation when clicking a link.

```python demo
rx.link("This Link Does Nothing", href="https://reflex.dev/", on_click=rx.prevent_default)
```

```python demo exec
class LinkPreventDefaultState(rx.State):
    status: bool = False

    @rx.event
    def toggle_status(self):
        self.status = not self.status

def prevent_default_example():
    return rx.vstack(
        rx.heading(f"The value is {LinkPreventDefaultState.status}"),
        rx.link(
            "Toggle Value",
            href="https://reflex.dev/",
            on_click=LinkPreventDefaultState.toggle_status.prevent_default,
        ),
    )
```

### stop_propagation

The `.stop_propagation` action stops the event from propagating to parent elements.

This action is often used when a clickable element contains nested buttons that
should not trigger the parent element's click event.

In the following example, the first button uses `.stop_propagation` to prevent
the click event from propagating to the outer vstack. The second button does not
use `.stop_propagation`, so the click event will also be handled by the on_click
attached to the outer vstack.

```python demo exec
class StopPropagationState(rx.State):
    where_clicked: list[str] = []

    @rx.event
    def handle_click(self, where: str):
        self.where_clicked.append(where)

    @rx.event
    def handle_reset(self):
        self.where_clicked = []

def stop_propagation_example():
    return rx.vstack(
        rx.button(
            "btn1 - Stop Propagation",
            on_click=StopPropagationState.handle_click("btn1").stop_propagation,
        ),
        rx.button(
            "btn2 - Normal Propagation",
            on_click=StopPropagationState.handle_click("btn2"),
        ),
        rx.foreach(StopPropagationState.where_clicked, rx.text),
        rx.button(
            "Reset",
            on_click=StopPropagationState.handle_reset.stop_propagation,
        ),
        padding="2em",
        border=f"1px dashed {rx.color('accent', 5)}",
        on_click=StopPropagationState.handle_click("outer")
    )
```

## Throttling and Debounce

_Added in v0.5.0_

For events that are fired frequently, it can be useful to throttle or debounce
them to avoid network latency and improve performance. These actions both take a
single argument which specifies the delay time in milliseconds.

### throttle

The `.throttle` action limits the number of times an event is processed within a
a given time period. It is useful for `on_scroll` and `on_mouse_move` events which are
fired very frequently, causing lag when handling them in the backend.

```md alert warning
# Throttled events are discarded.

There is no eventual delivery of any event that is triggered while the throttle
period is active. Throttle is not appropriate for events when the final payload
contains data that must be processed, like `on_change`.
```

In the following example, the `on_scroll` event is throttled to only fire every half second.

```python demo exec
class ThrottleState(rx.State):
    last_scroll: datetime.datetime | None

    @rx.event
    def handle_scroll(self):
        self.last_scroll = datetime.datetime.now(datetime.timezone.utc)

def scroll_box():
    return rx.scroll_area(
        rx.heading("Scroll Me"),
        *[rx.text(f"Item {i}") for i in range(100)],
        height="75px",
        width="50%",
        border=f"1px solid {rx.color('accent', 5)}",
        on_scroll=ThrottleState.handle_scroll.throttle(500),
    )

def throttle_example():
    return (
        scroll_box(),
        rx.text(
            f"Last Scroll Event: ",
            rx.moment(ThrottleState.last_scroll, format="HH:mm:ss.SSS"),
        ),
    )
```

```md alert info
# Event Actions are Chainable

Event actions can be chained together to create more complex event handling
behavior. For example, you can throttle an event and prevent its default
behavior in the same event handler: `on_click=MyState.handle_click.throttle(500).prevent_default`.
```

### debounce

The `.debounce` action delays the processing of an event until the specified
timeout occurs. If another event is triggered during the timeout, the timer is
reset and the original event is discarded.

Debounce is useful for handling the final result of a series of events, such as
moving a slider.

```md alert warning
# Debounced events are discarded.

When a new event is triggered during the debounce period, the original event is
discarded. Debounce is not appropriate for events where each payload contains
unique data that must be processed, like `on_key_down`.
```

In the following example, the slider's `on_change` handler, `update_value`, is
only triggered on the backend when the slider value has not changed for half a
second.

```python demo exec
class DebounceState(rx.State):
    settled_value: int = 50

    @rx.event
    def update_value(self, value: list[int | float]):
        self.settled_value = value[0]


def debounced_slider():
    return rx.slider(
        key=rx.State.router.session.session_id,
        default_value=[DebounceState.settled_value],
        on_change=DebounceState.update_value.debounce(500),
        width="100%",
    )

def debounce_example():
    return rx.vstack(
        debounced_slider(),
        rx.text(f"Settled Value: {DebounceState.settled_value}"),
    )
```

```md alert info
# Why set key on the slider?

Setting `key` to the `session_id` with a dynamic `default_value` ensures that
when the page is refreshed, the component will be re-rendered to reflect the
updated default_value from the state.

Without the `key` set, the slider would always display the original
`settled_value` after a page reload, instead of its current value.
```

## Temporal Events

_Added in [v0.6.6](https://github.com/reflex-dev/reflex/releases/tag/v0.6.6)_

### temporal

The `.temporal` action prevents events from being queued when the backend is down.
This is useful for non-critical events where you do not want them to pile up if there is
a temporary connection issue.

```md alert warning
# Temporal events are discarded when the backend is down.

When the backend is unavailable, events with the `.temporal` action will be
discarded rather than queued for later processing. Only use this for events
where it is acceptable to lose some interactions during connection issues.
```

In the following example, the `rx.moment` component with `interval` and `on_change` uses `.temporal` to
prevent periodic updates from being queued when the backend is down:

```python demo exec
class TemporalState(rx.State):
    current_time: str = ""

    @rx.event
    def update_time(self):
        self.current_time = datetime.datetime.now().strftime("%H:%M:%S")

def temporal_example():
    return rx.vstack(
        rx.heading("Current Time:"),
        rx.heading(TemporalState.current_time),
        rx.moment(
            interval=1000,
            on_change=TemporalState.update_time.temporal,
        ),
        rx.text("Time updates will not be queued if the backend is down."),
    )
```

---
components:
  - rx.recharts.FunnelChart
  - rx.recharts.Funnel
---

```python exec
import reflex as rx
import random
rx.toast.provider()
```

# Funnel Chart

A funnel chart is a graphical representation used to visualize how data moves through a process. In a funnel chart, the dependent variable’s value diminishes in the subsequent stages of the process. It can be used to demonstrate the flow of users through a business or sales process.

## Simple Example

```python demo graphing
data = [
  {
    "value": 100,
    "name": "Sent",
    "fill": "#8884d8"
  },
  {
    "value": 80,
    "name": "Viewed",
    "fill": "#83a6ed"
  },
  {
    "value": 50,
    "name": "Clicked",
    "fill": "#8dd1e1"
  },
  {
    "value": 40,
    "name": "Add to Cart",
    "fill": "#82ca9d"
  },
  {
    "value": 26,
    "name": "Purchased",
    "fill": "#a4de6c"
  }
]

def funnel_simple():
    return rx.recharts.funnel_chart(
        rx.recharts.funnel(
            rx.recharts.label_list(
                position="right",
                data_key="name",
                fill="#000",
                stroke="none",
            ),
            data_key="value",
            data=data,
        ),
        width="100%",
        height=250,
    )
```

## Event Triggers

Funnel chart supports `on_click`, `on_mouse_enter`, `on_mouse_leave` and `on_mouse_move` event triggers, allows you to interact with the funnel chart and perform specific actions based on user interactions.

```python demo graphing
data = [
  {
    "value": 100,
    "name": "Sent",
    "fill": "#8884d8"
  },
  {
    "value": 80,
    "name": "Viewed",
    "fill": "#83a6ed"
  },
  {
    "value": 50,
    "name": "Clicked",
    "fill": "#8dd1e1"
  },
  {
    "value": 40,
    "name": "Add to Cart",
    "fill": "#82ca9d"
  },
  {
    "value": 26,
    "name": "Purchased",
    "fill": "#a4de6c"
  }
]

def funnel_events():
    return rx.recharts.funnel_chart(
        rx.recharts.funnel(
            rx.recharts.label_list(
                position="right",
                data_key="name",
                fill="#000",
                stroke="none",
            ),
            data_key="value",
            data=data,
        ),
        on_click=rx.toast("Clicked on funnel chart"),
        on_mouse_enter=rx.toast("Mouse entered"),
        on_mouse_leave=rx.toast("Mouse left"),
        width="100%",
        height=250,
    )
```

## Dynamic Data

Here is an example of a funnel chart with a `State`. Here we have defined a function `randomize_data`, which randomly changes the data when the graph is clicked on using `on_click=FunnelState.randomize_data`.

```python exec
data = [
  {
    "value": 100,
    "name": "Sent",
    "fill": "#8884d8"
  },
  {
    "value": 80,
    "name": "Viewed",
    "fill": "#83a6ed"
  },
  {
    "value": 50,
    "name": "Clicked",
    "fill": "#8dd1e1"
  },
  {
    "value": 40,
    "name": "Add to Cart",
    "fill": "#82ca9d"
  },
  {
    "value": 26,
    "name": "Purchased",
    "fill": "#a4de6c"
  }
]
```

```python demo exec
class FunnelState(rx.State):
    data = data

    @rx.event
    def randomize_data(self):
        self.data[0]["value"] = 100
        for i in range(len(self.data) - 1):
            self.data[i + 1]["value"] = self.data[i][
                "value"
            ] - random.randint(0, 20)


def funnel_state():
  return rx.recharts.funnel_chart(
    rx.recharts.funnel(
      rx.recharts.label_list(
        position="right",
        data_key="name",
        fill="#000",
        stroke="none",
      ),
      data_key="value",
      data=FunnelState.data,
      on_click=FunnelState.randomize_data,
    ),
    rx.recharts.graphing_tooltip(),
    width="100%",
    height=250,
  )
```

## Changing the Chart Animation

The `is_animation_active` prop can be used to turn off the animation, but defaults to `True`. `animation_begin` sets the delay before animation starts, `animation_duration` determines how long the animation lasts, and `animation_easing` defines the speed curve of the animation for smooth transitions.

```python demo graphing
data = [
        {"name": "Visits", "value": 5000, "fill": "#8884d8"},
        {"name": "Cart", "value": 3000, "fill": "#83a6ed"},
        {"name": "Checkout", "value": 2500, "fill": "#8dd1e1"},
        {"name": "Purchase", "value": 1000, "fill": "#82ca9d"},
    ]

def funnel_animation():
    return rx.recharts.funnel_chart(
        rx.recharts.funnel(
            data_key="value",
            data=data,
            animation_begin=300,
            animation_duration=9000,
            animation_easing="ease-in-out",
        ),
        rx.recharts.graphing_tooltip(),
        rx.recharts.legend(),
        width="100%",
        height=300,
    )
```

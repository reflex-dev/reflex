---
components:
  - rx.recharts.PieChart
  - rx.recharts.Pie
---

# Pie Chart

```python exec
import reflex as rx
```

A pie chart is a circular statistical graphic which is divided into slices to illustrate numerical proportion.

For a pie chart we must define an `rx.recharts.pie()` component for each set of values we wish to plot. Each `rx.recharts.pie()` component has a `data`, a `data_key` and a `name_key` which clearly states which data and which variables in our data we are tracking. In this simple example we plot `value` column as our `data_key` against the `name` column which we set as our `name_key`.
We also use the `fill` prop to set the color of the pie slices.

```python demo graphing

data01 = [
  {
    "name": "Group A",
    "value": 400
  },
  {
    "name": "Group B",
    "value": 300,
    "fill":"#AC0E08FF"
  },
  {
    "name": "Group C",
    "value": 300,
    "fill":"rgb(80,40, 190)"
  },
  {
    "name": "Group D",
    "value": 200,
    "fill":rx.color("yellow", 10)
  },
  {
    "name": "Group E",
    "value": 278,
    "fill":"purple"
  },
  {
    "name": "Group F",
    "value": 189,
    "fill":"orange"
  }
]

def pie_simple():
  return rx.recharts.pie_chart(
            rx.recharts.pie(
                data=data01,
                data_key="value",
                name_key="name",
                fill="#8884d8",
                label=True,
            ),
            width="100%",
            height=300,
        )
```

We can also add two pies on one chart by using two `rx.recharts.pie` components.

In this example `inner_radius` and `outer_radius` props are used. They define the doughnut shape of a pie chart: `inner_radius` creates the hollow center (use "0%" for a full pie), while `outer_radius` sets the overall size. The `padding_angle` prop, used on the green pie below, adds space between pie slices, enhancing visibility of individual segments.

```python demo graphing

data01 = [
  {
    "name": "Group A",
    "value": 400
  },
  {
    "name": "Group B",
    "value": 300
  },
  {
    "name": "Group C",
    "value": 300
  },
  {
    "name": "Group D",
    "value": 200
  },
  {
    "name": "Group E",
    "value": 278
  },
  {
    "name": "Group F",
    "value": 189
  }
]
data02 = [
  {
    "name": "Group A",
    "value": 2400
  },
  {
    "name": "Group B",
    "value": 4567
  },
  {
    "name": "Group C",
    "value": 1398
  },
  {
    "name": "Group D",
    "value": 9800
  },
  {
    "name": "Group E",
    "value": 3908
  },
  {
    "name": "Group F",
    "value": 4800
  }
]


def pie_double():
  return rx.recharts.pie_chart(
            rx.recharts.pie(
                data=data01,
                data_key="value",
                name_key="name",
                fill="#82ca9d",
                inner_radius="60%",
                padding_angle=5,
            ),
            rx.recharts.pie(
                data=data02,
                data_key="value",
                name_key="name",
                fill="#8884d8",
                outer_radius="50%",
            ),
            rx.recharts.graphing_tooltip(),
            width="100%",
            height=300,
        )
```

## Dynamic Data

Chart data tied to a State var causes the chart to automatically update when the
state changes, providing a nice way to visualize data in response to user
interface elements. View the "Data" tab to see the substate driving this
half-pie chart.

```python demo exec
from typing import Any


class PieChartState(rx.State):
    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @rx.var(cache=True)
    def resource_types(self) -> list[str]:
        return [r["type_"] for r in self.resources]

    @rx.event
    def increment(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_:
                resource["count"] += 1
                break

    @rx.event
    def decrement(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_ and resource["count"] > 0:
                resource["count"] -= 1
                break


def dynamic_pie_example():
    return rx.hstack(
        rx.recharts.pie_chart(
            rx.recharts.pie(
                data=PieChartState.resources,
                data_key="count",
                name_key="type_",
                cx="50%",
                cy="50%",
                start_angle=180,
                end_angle=0,
                fill="#8884d8",
                label=True,
            ),
            rx.recharts.graphing_tooltip(),
        ),
        rx.vstack(
            rx.foreach(
                PieChartState.resource_types,
                lambda type_, i: rx.hstack(
                    rx.button("-", on_click=PieChartState.decrement(type_)),
                    rx.text(type_, PieChartState.resources[i]["count"]),
                    rx.button("+", on_click=PieChartState.increment(type_)),
                ),
            ),
        ),
        width="100%",
        height="15em",
    )
```

---
components:
    - rx.recharts.PieChart
---

# Pie Chart

```python exec
import reflex as rx
from pcweb.templates.docpage import docgraphing

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

pie_chart_simple_example = """rx.recharts.pie_chart(
                rx.recharts.pie(
                    data=data01,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    fill="#8884d8",
                    label=True,
                    )
                    )"""

pie_chart_complex_example = """rx.recharts.pie_chart(
                  rx.recharts.pie(
                    data=data01,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    fill="#82ca9d",
                    inner_radius="60%",
                    ),
                    rx.recharts.pie(
                    data=data02,
                    data_key="value",
                    name_key="name",
                    cx="50%",
                    cy="50%",
                    fill="#8884d8",
                    outer_radius="50%",
                    ),
                    rx.recharts.graphing_tooltip(),
                    )"""

```

A pie chart is a circular statistical graphic which is divided into slices to illustrate numerical proportion.

For a pie chart we must define an `rx.recharts.pie()` component for each set of values we wish to plot. Each `rx.recharts.pie()` component has a `data`, a `data_key` and a `name_key` which clearly states which data and which variables in our data we are tracking. In this simple example we plot `value` column as our `data_key` against the `name` column which we set as our `name_key`.

```python eval
docgraphing(pie_chart_simple_example, comp=eval(pie_chart_simple_example),  data =  "data01=" + str(data01))
```

We can also add two pies on one chart by using two `rx.recharts.pie` components.

```python eval
docgraphing(pie_chart_complex_example, comp=eval(pie_chart_complex_example),  data =  "data01=" + str(data01) + "&data02=" + str(data02))
```

# Dynamic Data

Chart data tied to a State var causes the chart to automatically update when the
state changes, providing a nice way to visualize data in response to user
interface elements. View the "Data" tab to see the substate driving this
half-pie chart.

```python exec
from typing import Any


class PieChartState(rx.State):
    resources: list[dict[str, Any]] = [
        dict(type_="🏆", count=1),
        dict(type_="🪵", count=1),
        dict(type_="🥑", count=1),
        dict(type_="🧱", count=1),
    ]

    @rx.cached_var
    def resource_types(self) -> list[str]:
        return [r["type_"] for r in self.resources]

    def increment(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_:
                resource["count"] += 1
                break

    def decrement(self, type_: str):
        for resource in self.resources:
            if resource["type_"] == type_ and resource["count"] > 0:
                resource["count"] -= 1
                break


pie_chart_state_example = """
rx.hstack(
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
)"""
```

```python eval
docgraphing(
    pie_chart_state_example,
    comp=eval(pie_chart_state_example),
    # data=inspect.getsource(PieChartState),
)
```

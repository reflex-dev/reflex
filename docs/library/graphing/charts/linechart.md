---
components:
  - rx.recharts.LineChart
  - rx.recharts.Line
---

# Line Chart

```python exec
import random
from typing import Any
from pcweb.pages.docs import library
import reflex as rx
```

A line chart is a type of chart used to show information that changes over time. Line charts are created by plotting a series of several points and connecting them with a straight line.

## Simple Example

For a line chart we must define an `rx.recharts.line()` component for each set of values we wish to plot. Each `rx.recharts.line()` component has a `data_key` which clearly states which variable in our data we are tracking. In this simple example we plot `pv` and `uv` as separate lines against the `name` column which we set as the `data_key` in `rx.recharts.x_axis`.

```python demo graphing
data = [
  {
    "name": "Page A",
    "uv": 4000,
    "pv": 2400,
    "amt": 2400
  },
  {
    "name": "Page B",
    "uv": 3000,
    "pv": 1398,
    "amt": 2210
  },
  {
    "name": "Page C",
    "uv": 2000,
    "pv": 9800,
    "amt": 2290
  },
  {
    "name": "Page D",
    "uv": 2780,
    "pv": 3908,
    "amt": 2000
  },
  {
    "name": "Page E",
    "uv": 1890,
    "pv": 4800,
    "amt": 2181
  },
  {
    "name": "Page F",
    "uv": 2390,
    "pv": 3800,
    "amt": 2500
  },
  {
    "name": "Page G",
    "uv": 3490,
    "pv": 4300,
    "amt": 2100
  }
]

def line_simple():
  return rx.recharts.line_chart(
    rx.recharts.line(
        data_key="pv",
    ),
    rx.recharts.line(
        data_key="uv",
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    data=data,
    width = "100%",
    height = 300,
  )
```

## Example with Props

Our second example uses exactly the same data as our first example, except now we add some extra features to our line graphs. We add a `type_` prop to `rx.recharts.line` to style the lines differently. In addition, we add an `rx.recharts.cartesian_grid` to get a grid in the background, an `rx.recharts.legend` to give us a legend for our graphs and an `rx.recharts.graphing_tooltip` to add a box with text that appears when you pause the mouse pointer on an element in the graph.

```python demo graphing

data = [
  {
    "name": "Page A",
    "uv": 4000,
    "pv": 2400,
    "amt": 2400
  },
  {
    "name": "Page B",
    "uv": 3000,
    "pv": 1398,
    "amt": 2210
  },
  {
    "name": "Page C",
    "uv": 2000,
    "pv": 9800,
    "amt": 2290
  },
  {
    "name": "Page D",
    "uv": 2780,
    "pv": 3908,
    "amt": 2000
  },
  {
    "name": "Page E",
    "uv": 1890,
    "pv": 4800,
    "amt": 2181
  },
  {
    "name": "Page F",
    "uv": 2390,
    "pv": 3800,
    "amt": 2500
  },
  {
    "name": "Page G",
    "uv": 3490,
    "pv": 4300,
    "amt": 2100
  }
]

def line_features():
  return rx.recharts.line_chart(
    rx.recharts.line(
        data_key="pv",
        type_="monotone",
        stroke="#8884d8",),
    rx.recharts.line(
        data_key="uv",
        type_="monotone",
        stroke="#82ca9d",),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
    rx.recharts.graphing_tooltip(),
    rx.recharts.legend(),
    data=data,
    width = "100%",
    height = 300,
  )
```

## Layout

The `layout` prop allows you to set the orientation of the graph to be vertical or horizontal. The `margin` prop defines the spacing around the graph,

```md alert info
# Include margins around your graph to ensure proper spacing and enhance readability. By default, provide margins on all sides of the chart to create a visually appealing and functional representation of your data.
```

```python demo graphing

data = [
  {
    "name": "Page A",
    "uv": 4000,
    "pv": 2400,
    "amt": 2400
  },
  {
    "name": "Page B",
    "uv": 3000,
    "pv": 1398,
    "amt": 2210
  },
  {
    "name": "Page C",
    "uv": 2000,
    "pv": 9800,
    "amt": 2290
  },
  {
    "name": "Page D",
    "uv": 2780,
    "pv": 3908,
    "amt": 2000
  },
  {
    "name": "Page E",
    "uv": 1890,
    "pv": 4800,
    "amt": 2181
  },
  {
    "name": "Page F",
    "uv": 2390,
    "pv": 3800,
    "amt": 2500
  },
  {
    "name": "Page G",
    "uv": 3490,
    "pv": 4300,
    "amt": 2100
  }
]

def line_vertical():
    return rx.recharts.line_chart(
        rx.recharts.line(
            data_key="pv",
            stroke=rx.color("accent", 9),
        ),
        rx.recharts.line(
            data_key="uv",
            stroke=rx.color("green", 9),
        ),
        rx.recharts.x_axis(type_="number"),
        rx.recharts.y_axis(data_key="name", type_="category"),
        layout="vertical",
        margin={
            "top": 20,
            "right": 20,
            "left": 20,
            "bottom": 20
        },
        data = data,
        height = 300,
        width = "100%",
    )
```

## Dynamic Data

Chart data can be modified by tying the `data` prop to a State var. Most other
props, such as `type_`, can be controlled dynamically as well. In the following
example the "Munge Data" button can be used to randomly modify the data, and the
two `select` elements change the line `type_`. Since the data and style is saved
in the per-browser-tab State, the changes will not be visible to other visitors.

```python demo exec

initial_data = data

class LineChartState(rx.State):
    data: list[dict[str, Any]] = initial_data
    pv_type: str = "monotone"
    uv_type: str = "monotone"

    @rx.event
    def set_pv_type(self, pv_type: str):
        self.pv_type = pv_type

    @rx.event
    def set_uv_type(self, uv_type: str):
        self.uv_type = uv_type

    @rx.event
    def munge_data(self):
        for row in self.data:
            row["uv"] += random.randint(-500, 500)
            row["pv"] += random.randint(-1000, 1000)

def line_dynamic():
  return rx.vstack(
    rx.recharts.line_chart(
      rx.recharts.line(
        data_key="pv",
        type_=LineChartState.pv_type,
        stroke="#8884d8",
      ),
      rx.recharts.line(
        data_key="uv",
        type_=LineChartState.uv_type,
        stroke="#82ca9d",
      ),
      rx.recharts.x_axis(data_key="name"),
      rx.recharts.y_axis(),
      data=LineChartState.data,
      margin={
        "top": 20,
        "right": 20,
        "left": 20,
        "bottom": 20
      },
      width = "100%",
      height = 300,
    ),
    rx.hstack(
      rx.button("Munge Data", on_click=LineChartState.munge_data),
      rx.select(
        ["monotone", "linear", "step", "stepBefore", "stepAfter"],
        value=LineChartState.pv_type,
        on_change=LineChartState.set_pv_type
      ),
      rx.select(
          ["monotone", "linear", "step", "stepBefore", "stepAfter"],
          value=LineChartState.uv_type,
          on_change=LineChartState.set_uv_type
      ),
    ),
    width="100%",
  )
```

To learn how to use the `sync_id`, `x_axis_id` and `y_axis_id` props check out the of the area chart [documentation]({library.graphing.charts.areachart.path}), where these props are all described with examples.

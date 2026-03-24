---
components:
  - rx.recharts.BarChart
  - rx.recharts.Bar
---

# Bar Chart

```python exec
import reflex as rx
import random
from pcweb.pages.docs import library
```

A bar chart presents categorical data with rectangular bars with heights or lengths proportional to the values that they represent.

For a bar chart we must define an `rx.recharts.bar()` component for each set of values we wish to plot. Each `rx.recharts.bar()` component has a `data_key` which clearly states which variable in our data we are tracking. In this simple example we plot `uv` as a bar against the `name` column which we set as the `data_key` in `rx.recharts.x_axis`.

## Simple Example

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

def bar_simple():
  return rx.recharts.bar_chart(
    rx.recharts.bar(
        data_key="uv",
        stroke=rx.color("accent", 9),
        fill=rx.color("accent", 8),
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    data=data,
    width = "100%",
    height = 250,
  )
```

## Multiple Bars

Multiple bars can be placed on the same `bar_chart`, using multiple `rx.recharts.bar()` components.

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

def bar_double():
  return rx.recharts.bar_chart(
    rx.recharts.bar(
        data_key="uv",
        stroke=rx.color("accent", 9),
        fill=rx.color("accent", 8),
    ),
    rx.recharts.bar(
        data_key="pv",
        stroke=rx.color("green", 9),
        fill=rx.color("green", 8),
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    data=data,
    width = "100%",
    height = 250,
  )
```

## Ranged Charts

You can also assign a range in the bar by assigning the data_key in the `rx.recharts.bar` to a list with two elements, i.e. here a range of two temperatures for each date.

```python demo graphing
range_data = [
  {
    "day": "05-01",
    "temperature": [
      -1,
      10
    ]
  },
  {
    "day": "05-02",
    "temperature": [
      2,
      15
    ]
  },
  {
    "day": "05-03",
    "temperature": [
      3,
      12
    ]
  },
  {
    "day": "05-04",
    "temperature": [
      4,
      12
    ]
  },
  {
    "day": "05-05",
    "temperature": [
      12,
      16
    ]
  },
  {
    "day": "05-06",
    "temperature": [
      5,
      16
    ]
  },
  {
    "day": "05-07",
    "temperature": [
      3,
      12
    ]
  },
  {
    "day": "05-08",
    "temperature": [
      0,
      8
    ]
  },
  {
    "day": "05-09",
    "temperature": [
      -3,
      5
    ]
  }
]

def bar_range():
  return rx.recharts.bar_chart(
    rx.recharts.bar(
        data_key="temperature",
        stroke=rx.color("accent", 9),
        fill=rx.color("accent", 8),
    ),
    rx.recharts.x_axis(data_key="day"),
    rx.recharts.y_axis(),
    data=range_data,
    width = "100%",
    height = 250,
  )
```

## Stateful Charts

Here is an example of a bar graph with a `State`. Here we have defined a function `randomize_data`, which randomly changes the data for both graphs when the first defined `bar` is clicked on using `on_click=BarState.randomize_data`.

```python demo exec
class BarState(rx.State):
    data = data

    @rx.event
    def randomize_data(self):
        for i in range(len(self.data)):
            self.data[i]["uv"] = random.randint(0, 10000)
            self.data[i]["pv"] = random.randint(0, 10000)
            self.data[i]["amt"] = random.randint(0, 10000)

def bar_with_state():
  return rx.recharts.bar_chart(
    rx.recharts.cartesian_grid(
      stroke_dasharray="3 3",
    ),
    rx.recharts.bar(
      data_key="uv",
      stroke=rx.color("accent", 9),
      fill=rx.color("accent", 8),
    ),
    rx.recharts.bar(
      data_key="pv",
      stroke=rx.color("green", 9),
      fill=rx.color("green", 8),
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    rx.recharts.legend(),
    on_click=BarState.randomize_data,
    data=BarState.data,
    width = "100%",
    height = 300,
  )
```

## Example with Props

Here's an example demonstrates how to customize the appearance and layout of bars using the `bar_category_gap`, `bar_gap`, `bar_size`, and `max_bar_size` props. These props accept values in pixels to control the spacing and size of the bars.

```python demo graphing

data = [
    {'name': 'Page A', 'value': 2400},
    {'name': 'Page B', 'value': 1398},
    {'name': 'Page C', 'value': 9800},
    {'name': 'Page D', 'value': 3908},
    {'name': 'Page E', 'value': 4800},
    {'name': 'Page F', 'value': 3800},
]

def bar_features():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data,
        bar_category_gap="15%",
        bar_gap=6,
        bar_size=100,
        max_bar_size=40,
        width="100%",
        height=300,
    )
```

## Vertical Example

The `layout` prop allows you to set the orientation of the graph to be vertical or horizontal, it is set horizontally by default.

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

def bar_vertical():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="uv",
            stroke=rx.color("accent", 8),
            fill=rx.color("accent", 3),
        ),
        rx.recharts.x_axis(type_="number"),
        rx.recharts.y_axis(data_key="name", type_="category"),
        data=data,
        layout="vertical",
        margin={
            "top": 20,
            "right": 20,
            "left": 20,
            "bottom": 20
        },
        width = "100%",
        height = 300,

    )
```

To learn how to use the `sync_id`, `stack_id`,`x_axis_id` and `y_axis_id` props check out the of the area chart [documentation]({library.graphing.charts.areachart.path}), where these props are all described with examples.

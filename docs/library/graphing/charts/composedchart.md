---
components:
    - rx.recharts.ComposedChart
---

```python exec
import reflex as rx
from pcweb.pages.docs import library
```
# Composed Chart

A `composed_chart` is a higher-level component chart that is composed of multiple charts, where other charts are the children of the `composed_chart`. The charts are placed on top of each other in the order they are provided in the `composed_chart` function.


```md alert info
# To learn more about individual charts, checkout: **[area_chart]({library.graphing.charts.areachart.path})**, **[line_chart]({library.graphing.charts.linechart.path})**, or **[bar_chart]({library.graphing.charts.barchart.path})**. 
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

def composed():
  return rx.recharts.composed_chart(
    rx.recharts.area(
        data_key="uv",
        stroke="#8884d8",
        fill="#8884d8"
    ), 
    rx.recharts.bar(
        data_key="amt",
        bar_size=20,
        fill="#413ea0"
    ),
    rx.recharts.line(
        data_key="pv",
        type_="monotone",
        stroke="#ff7300"
    ), 
    rx.recharts.x_axis(data_key="name"), 
    rx.recharts.y_axis(),
    rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
    rx.recharts.graphing_tooltip(),
    data=data,
    height=250,
    width="100%",
  )
```

---
components:
    - rx.recharts.Legend
---

# Legend

```python exec
import reflex as rx
```

A legend tells what each plot represents. Just like on a map, the legend helps the reader understand what they are looking at. For a line graph for example it tells us what each line represents.

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

def legend_simple():
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
    rx.recharts.legend(),
    data=data,
    width = "100%",
    height = 300,
  )
```

## Example with Props

The style and layout of the legend can be customized using a set of props. `width` and `height` set the dimensions of the container that wraps the legend, and `layout` can set the legend to display vertically or horizontally. `align` and `vertical_align` set the position relative to the chart container. The type and size of icons can be set using `icon_size` and `icon_type`.

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

def legend_props():
  return rx.recharts.composed_chart(
    rx.recharts.line(
      data_key="pv",
      type_="monotone",
      stroke=rx.color("accent", 7),
    ), 
    rx.recharts.line(
      data_key="amt",
      type_="monotone",
      stroke=rx.color("green", 7),
    ), 
    rx.recharts.line(
      data_key="uv",
      type_="monotone",
      stroke=rx.color("red", 7),
    ), 
    rx.recharts.x_axis(data_key="name"), 
    rx.recharts.y_axis(),
    rx.recharts.legend(
      width=60,
      height=100,
      layout="vertical",
      align="right",
      vertical_align="top",
      icon_size=15,
      icon_type="square",
    ),
    data=data,
    width="100%",
    height=300,
  )

```
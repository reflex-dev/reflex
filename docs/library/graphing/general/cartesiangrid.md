---
components:
    - rx.recharts.CartesianGrid
    # - rx.recharts.CartesianAxis
---

```python exec
import reflex as rx
```

# Cartesian Grid

The Cartesian Grid is a component in Recharts that provides a visual reference for data points in charts. It helps users to better interpret the data by adding horizontal and vertical lines across the chart area.

## Simple Example

The `stroke_dasharray` prop in Recharts is used to create dashed or dotted lines for various chart elements like lines, axes, or grids. It's based on the SVG stroke-dasharray attribute. The `stroke_dasharray` prop accepts a comma-separated string of numbers that define a repeating pattern of dashes and gaps along the length of the stroke.

- `stroke_dasharray="5,5"`:  creates a line with 5-pixel dashes and 5-pixel gaps
- `stroke_dasharray="10,5,5,5"`:  creates a more complex pattern with 10-pixel dashes, 5-pixel gaps, 5-pixel dashes, and 5-pixel gaps

Here's a simple example using it on a Line component:

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

def cgrid_simple():
  return rx.recharts.line_chart(
    rx.recharts.line(
        data_key="pv",
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    rx.recharts.cartesian_grid(stroke_dasharray="4 4"),
    data=data,
    width = "100%",
    height = 300,
  )
```

## Hidden Axes

A `cartesian_grid` component can be used to hide the horizontal and vertical grid lines in a chart by setting the `horizontal` and `vertical` props to `False`. This can be useful when you want to show the grid lines only on one axis or when you want to create a cleaner look for the chart.

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

def cgrid_hidden():
  return rx.recharts.area_chart(
    rx.recharts.area(
        data_key="uv",
        stroke="#8884d8",
        fill="#8884d8"
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    rx.recharts.cartesian_grid(
      stroke_dasharray="2 4",
      vertical=False,
      horizontal=True,
    ),
    data=data,
    width = "100%",
    height = 300,
  )
```

## Custom Grid Lines

The `horizontal_points` and `vertical_points` props allow you to specify custom grid lines on the chart, offering fine-grained control over the grid's appearance.

These props accept arrays of numbers, where each number represents a pixel offset:
- For `horizontal_points`, the offset is measured from the top edge of the chart
- For `vertical_points`, the offset is measured from the left edge of the chart

```md alert info
# **Important**: The values provided to these props are not directly related to the axis values. They represent pixel offsets within the chart's rendering area.
```

Here's an example demonstrating custom grid lines in a scatter chart:

```python demo graphing

data2 = [
    {"x": 100, "y": 200, "z": 200},
    {"x": 120, "y": 100, "z": 260},
    {"x": 170, "y": 300, "z": 400},
    {"x": 170, "y": 250, "z": 280},
    {"x": 150, "y": 400, "z": 500},
    {"x": 110, "y": 280, "z": 200},
    {"x": 200, "y": 150, "z": 300},
    {"x": 130, "y": 350, "z": 450},
    {"x": 90, "y": 220, "z": 180},
    {"x": 180, "y": 320, "z": 350},
    {"x": 140, "y": 230, "z": 320},
    {"x": 160, "y": 180, "z": 240},
]

def cgrid_custom():
    return rx.recharts.scatter_chart(
        rx.recharts.scatter(
            data=data2,
            fill="#8884d8",
        ),
        rx.recharts.x_axis(data_key="x", type_="number"),
        rx.recharts.y_axis(data_key="y"),
        rx.recharts.cartesian_grid(
            stroke_dasharray="3 3",
            horizontal_points=[0, 25, 50],
            vertical_points=[65, 90, 115],
        ),
        width = "100%",
        height = 200,
    )
```

Use these props judiciously to enhance data visualization without cluttering the chart. They're particularly useful for highlighting specific data ranges or creating visual reference points.

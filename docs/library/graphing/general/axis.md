---
components:
  - rx.recharts.XAxis
  - rx.recharts.YAxis
  - rx.recharts.ZAxis
---

```python exec
import reflex as rx
```

# Axis

The Axis component in Recharts is a powerful tool for customizing and configuring the axes of your charts. It provides a wide range of props that allow you to control the appearance, behavior, and formatting of the axis. Whether you're working with an AreaChart, LineChart, or any other chart type, the Axis component enables you to create precise and informative visualizations.

## Basic Example

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

def axis_simple():
    return rx.recharts.area_chart(
        rx.recharts.area(
            data_key="uv",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(
            data_key="name",
            label={"value": 'Pages', "position": "bottom"},
        ),
        rx.recharts.y_axis(
            data_key="uv",
            label={"value": 'Views', "angle": -90, "position": "left"},
        ),
        data=data,
        width="100%",
        height=300,
        margin={
            "bottom": 40,
            "left": 40,
            "right": 40,
        },
    )
```

## Multiple Axes

Multiple axes can be used for displaying different data series with varying scales or units on the same chart. This allows for a more comprehensive comparison and analysis of the data.

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

def multi_axis():
  return rx.recharts.area_chart(
    rx.recharts.area(
        data_key="uv", stroke="#8884d8", fill="#8884d8", y_axis_id="left",
    ),
    rx.recharts.area(
        data_key="pv", y_axis_id="right", type_="monotone", stroke="#82ca9d", fill="#82ca9d"
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(data_key="uv", y_axis_id="left"),
    rx.recharts.y_axis(data_key="pv", y_axis_id="right", orientation="right"),
    rx.recharts.graphing_tooltip(),
    rx.recharts.legend(),
    data=data,
    width = "100%",
    height = 300,
  )
```

## Choosing Location of Labels for Axes

The axes `label` can take several positions. The example below allows you to try out different locations for the x and y axis labels.

```python demo graphing

class AxisState(rx.State):

    label_positions: list[str] = ["center", "insideTopLeft", "insideTopRight", "insideBottomRight", "insideBottomLeft", "insideTop", "insideBottom", "insideLeft", "insideRight", "outside", "top", "bottom", "left", "right"]

    label_offsets: list[str] = ["-30", "-20", "-10", "0", "10", "20", "30"]

    x_axis_postion: str = "bottom"

    x_axis_offset: int

    y_axis_postion: str = "left"

    y_axis_offset: int

    @rx.event
    @rx.event
    def set_y_axis_position(self, position: str):
        self.y_axis_position = position

    @rx.event
    def set_x_axis_position(self, position: str):
        self.x_axis_position = position

    @rx.event
    def set_x_axis_offset(self, offset: str):
        self.x_axis_offset = int(offset)

    @rx.event
    def set_y_axis_offset(self, offset: str):
        self.y_axis_offset = int(offset)

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

def axis_labels():
    return rx.vstack(
        rx.recharts.area_chart(
            rx.recharts.area(
                data_key="uv",
                stroke=rx.color("accent", 9),
                fill=rx.color("accent", 8),
            ),
            rx.recharts.x_axis(
                data_key="name",
                label={"value": 'Pages', "position": AxisState.x_axis_postion, "offset": AxisState.x_axis_offset},
            ),
            rx.recharts.y_axis(
                data_key="uv",
                label={"value": 'Views', "angle": -90, "position": AxisState.y_axis_postion, "offset": AxisState.y_axis_offset},
            ),
            data=data,
            width="100%",
            height=300,
            margin={
                "bottom": 40,
                "left": 40,
                "right": 40,
              }
        ),
        rx.hstack(
            rx.text("X Label Position: "),
            rx.select(
                AxisState.label_positions,
                value=AxisState.x_axis_postion,
                on_change=AxisState.set_x_axis_postion,
            ),
            rx.text("X Label Offset: "),
            rx.select(
              AxisState.label_offsets,
              value=AxisState.x_axis_offset.to_string(),
              on_change=AxisState.set_x_axis_offset,
            ),
            rx.text("Y Label Position: "),
            rx.select(
                AxisState.label_positions,
                value=AxisState.y_axis_postion,
                on_change=AxisState.set_y_axis_postion,
            ),
            rx.text("Y Label Offset: "),
            rx.select(
              AxisState.label_offsets,
              value=AxisState.y_axis_offset.to_string(),
              on_change=AxisState.set_y_axis_offset,
            ),
        ),
        width="100%",
    )
```

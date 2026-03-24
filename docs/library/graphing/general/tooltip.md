---
components:
    - rx.recharts.GraphingTooltip
---

# Tooltip

```python exec
import reflex as rx
```

Tooltips are the little boxes that pop up when you hover over something. Tooltips are always attached to something, like a dot on a scatter chart, or a bar on a bar chart.

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

def tooltip_simple():
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
    width = "100%",
    height = 300,
  )
```

## Custom Styling

The `rx.recharts.graphing_tooltip` component allows for customization of the tooltip's style, position, and layout. `separator` sets the separator between the data key and value. `view_box` prop defines the dimensions of the chart's viewbox while `allow_escape_view_box` determines whether the tooltip can extend beyond the viewBox horizontally (x) or vertically (y). `wrapper_style` prop allows you to style the outer container or wrapper of the tooltip. `content_style` prop allows you to style the inner content area of the tooltip. `is_animation_active` prop determines if the tooltip animation is active or not.

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

def tooltip_custom_styling():
  return rx.recharts.composed_chart(
    rx.recharts.area(
      data_key="uv", stroke="#8884d8", fill="#8884d8"
    ),
    rx.recharts.bar(
      data_key="amt", bar_size=20, fill="#413ea0"
    ),
    rx.recharts.line(
      data_key="pv", type_="monotone", stroke="#ff7300"
    ),
    rx.recharts.x_axis(data_key="name"),
    rx.recharts.y_axis(),
    rx.recharts.graphing_tooltip(
      separator = " - ",
      view_box = {"width" : 675, " height" : 300 },
      allow_escape_view_box={"x": True, "y": False},
      wrapper_style={
        "backgroundColor": rx.color("accent", 3), 
        "borderRadius": "8px",
        "padding": "10px",
      },
      content_style={
        "backgroundColor": rx.color("accent", 4), 
        "borderRadius": "4px", 
        "padding": "8px",
      },
      position = {"x" : 600, "y" : 0},
      is_animation_active = False,
    ),
    data=data,
    height = 300,
    width = "100%",
  )
```

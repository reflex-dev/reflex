---
components:
    - rx.recharts.RadialBarChart
---

# Radial Bar Chart

```python exec
import reflex as rx
```
## Simple Example

This example demonstrates how to use a `radial_bar_chart` with a `radial_bar`. The `radial_bar_chart` takes in `data` and then the `radial_bar` takes in a `data_key`. A radial bar chart is a circular visualization where data categories are represented by bars extending outward from a central point, with the length of each bar proportional to its value.

```md alert info
# Fill color supports `rx.color()`, which automatically adapts to dark/light mode changes.
```

```python demo graphing
data = [
    {"name": "C", "x": 3, "fill": rx.color("cyan", 9)},
    {"name": "D", "x": 4, "fill": rx.color("blue", 9)},
    {"name": "E", "x": 5, "fill": rx.color("orange", 9)},
    {"name": "F", "x": 6, "fill": rx.color("red", 9)},
    {"name": "G", "x": 7, "fill": rx.color("gray", 9)},
    {"name": "H", "x": 8, "fill": rx.color("green", 9)},
    {"name": "I", "x": 9, "fill": rx.color("accent", 6)},
]

def radial_bar_simple():
    return rx.recharts.radial_bar_chart(
        rx.recharts.radial_bar(
            data_key="x",
            min_angle=15,
        ),
        data=data,
        width = "100%",
        height = 500,
    )
```

## Advanced Example

The `start_angle` and `end_angle` define the circular arc over which the bars are distributed, while `inner_radius` and `outer_radius` determine the radial extent of the bars from the center. 

```python demo graphing

data_radial_bar = [
    {
        "name": "18-24",
        "uv": 31.47,
        "pv": 2400,
        "fill": "#8884d8"
    },
    {
        "name": "25-29",
        "uv": 26.69,
        "pv": 4567,
        "fill": "#83a6ed"
    },
    {
        "name": "30-34",
        "uv": -15.69,
        "pv": 1398,
        "fill": "#8dd1e1"
    },
    {
        "name": "35-39",
        "uv": 8.22,
        "pv": 9800,
        "fill": "#82ca9d"
    },
    {
        "name": "40-49",
        "uv": -8.63,
        "pv": 3908,
        "fill": "#a4de6c"
    },
    {
        "name": "50+",
        "uv": -2.63,
        "pv": 4800,
        "fill": "#d0ed57"
    },
    {
        "name": "unknown",
        "uv": 6.67,
        "pv": 4800,
        "fill": "#ffc658"
    }
]

def radial_bar_advanced():
    return rx.recharts.radial_bar_chart(
        rx.recharts.radial_bar(
            data_key="uv",
            min_angle=90,
            background=True,
            label={"fill": '#666', "position": 'insideStart'},
        ),
        data=data_radial_bar,
        inner_radius="10%",
        outer_radius="80%",
        start_angle=180,
        end_angle=0,
        width="100%",
        height=300,
    )
```
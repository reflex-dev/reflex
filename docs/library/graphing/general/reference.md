---
components:
    - rx.recharts.ReferenceLine
    - rx.recharts.ReferenceDot
    - rx.recharts.ReferenceArea
---

# Reference

```python exec
import reflex as rx
```

The Reference components in Recharts, including ReferenceLine, ReferenceArea, and ReferenceDot, are used to add visual aids and annotations to the chart, helping to highlight specific data points, ranges, or thresholds for better data interpretation and analysis.

## Reference Area

The `rx.recharts.reference_area` component in Recharts is used to highlight a specific area or range on the chart by drawing a rectangular region. It is defined by specifying the coordinates (x1, x2, y1, y2) and can be used to emphasize important data ranges or intervals on the chart.

```python demo graphing
data = [
  {
    "x": 45,
    "y": 100,
    "z": 150,
    "errorY": [
      30,
      20
    ],
    "errorX": 5
  },
  {
    "x": 100,
    "y": 200,
    "z": 200,
    "errorY": [
      20,
      30
    ],
    "errorX": 3
  },
  {
    "x": 120,
    "y": 100,
    "z": 260,
    "errorY": 20,
    "errorX": [
      10,
      3
    ]
  },
  {
    "x": 170,
    "y": 300,
    "z": 400,
    "errorY": [
      15,
      18
    ],
    "errorX": 4
  },
  {
    "x": 140,
    "y": 250,
    "z": 280,
    "errorY": 23,
    "errorX": [
      6,
      7
    ]
  },
  {
    "x": 150,
    "y": 400,
    "z": 500,
    "errorY": [
      21,
      10
    ],
    "errorX": 4
  },
  {
    "x": 110,
    "y": 280,
    "z": 200,
    "errorY": 21,
    "errorX": [
      1,
      8
    ]
  }
]

def reference():
  return rx.recharts.scatter_chart(
    rx.recharts.scatter(
        data=data,
        fill="#8884d8",
        name="A"),
    rx.recharts.reference_area(x1= 150, x2=180, y1=150, y2=300, fill="#8884d8", fill_opacity=0.3),
    rx.recharts.x_axis(data_key="x", name="x", type_="number"), 
    rx.recharts.y_axis(data_key="y", name="y", type_="number"),
    rx.recharts.graphing_tooltip(),
    width = "100%", 
    height = 300,
  )
```

## Reference Line

The `rx.recharts.reference_line` component in rx.recharts is used to draw a horizontal or vertical line on the chart at a specified position. It helps to highlight important values, thresholds, or ranges on the axis, providing visual reference points for better data interpretation.

```python demo graphing
data_2 = [
    {"name": "Page A", "uv": 4000, "pv": 2400, "amt": 2400},
    {"name": "Page B", "uv": 3000, "pv": 1398, "amt": 2210},
    {"name": "Page C", "uv": 2000, "pv": 9800, "amt": 2290},
    {"name": "Page D", "uv": 2780, "pv": 3908, "amt": 2000},
    {"name": "Page E", "uv": 1890, "pv": 4800, "amt": 2181},
    {"name": "Page F", "uv": 2390, "pv": 3800, "amt": 2500},
    {"name": "Page G", "uv": 3490, "pv": 4300, "amt": 2100},
]

def reference_line():
    return rx.recharts.area_chart(
        rx.recharts.area(
            data_key="pv", stroke=rx.color("accent", 8), fill=rx.color("accent", 7),
        ),
        rx.recharts.reference_line(
            x = "Page C",
            stroke = rx.color("accent", 10),
            label="Max PV PAGE",
        ),
        rx.recharts.reference_line(
            y = 9800,
            stroke = rx.color("green", 10),
            label="Max"
        ),
        rx.recharts.reference_line(
            y = 4343,
            stroke = rx.color("green", 10),
            label="Average"
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=data_2,
        height = 300,
        width = "100%",
    )

```

## Reference Dot

The `rx.recharts.reference_dot` component in Recharts is used to mark a specific data point on the chart with a customizable dot. It allows you to highlight important values, outliers, or thresholds by providing a visual reference marker at the specified coordinates (x, y) on the chart.

```python demo graphing

data_3 = [
    {
        "x": 45,
        "y": 100,
        "z": 150,
    },
    {
        "x": 100,
        "y": 200,
        "z": 200,
    },
    {
        "x": 120,
        "y": 100,
        "z": 260,
    },
    {
        "x": 170,
        "y": 300,
        "z": 400,
    },
    {
        "x": 140,
        "y": 250,
        "z": 280,
    },
    {
        "x": 150,
        "y": 400,
        "z": 500,
    },
    {
        "x": 110,
        "y": 280,
        "z": 200,
    },
    {
        "x": 80,
        "y": 150,
        "z": 180,
    },
    {
        "x": 200,
        "y": 350,
        "z": 450,
    },
    {
        "x": 90,
        "y": 220,
        "z": 240,
    },
    {
        "x": 130,
        "y": 320,
        "z": 380,
    },
    {
        "x": 180,
        "y": 120,
        "z": 300,
    },
]

def reference_dot():
    return rx.recharts.scatter_chart(
        rx.recharts.scatter(
            data=data_3, 
            fill=rx.color("accent", 9), 
            name="A",
        ),
        rx.recharts.x_axis(
            data_key="x", name="x", type_="number"
        ),
        rx.recharts.y_axis(
            data_key="y", name="y", type_="number"
        ),
        rx.recharts.reference_dot(
            x = 160,
            y = 350,
            r = 15,
            fill = rx.color("accent", 5),
            stroke = rx.color("accent", 10),
        ),
        rx.recharts.reference_dot(
            x = 170,
            y = 300,
            r = 20,
            fill = rx.color("accent", 7),
        ),
        rx.recharts.reference_dot(
            x = 90,
            y = 220,
            r = 18,
            fill = rx.color("green", 7),
        ),
        height = 200,
        width = "100%",
    )

```
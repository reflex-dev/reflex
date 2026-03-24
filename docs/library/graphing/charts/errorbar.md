---
components:
    - rx.recharts.ErrorBar
---

```python exec
import reflex as rx
```

# Error Bar

An error bar is a graphical representation of the uncertainty or variability of a data point in a chart, depicted as a line extending from the data point parallel to one of the axes. The `data_key`, `width`, `stroke_width`, `stroke`, and `direction` props can be used to customize the appearance and behavior of the error bars, specifying the data source, dimensions, color, and orientation of the error bars.

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
      5,
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
      5,
      6
    ]
  }
]

def error():
  return rx.recharts.scatter_chart(
    rx.recharts.scatter(
        rx.recharts.error_bar(data_key="errorY", direction="y", width=4, stroke_width=2, stroke="red"),
        rx.recharts.error_bar(data_key="errorX", direction="x", width=4, stroke_width=2),
        data=data,
        fill="#8884d8",
        name="A"),
    rx.recharts.x_axis(data_key="x", name="x", type_="number"), 
    rx.recharts.y_axis(data_key="y", name="y", type_="number"),
    width = "100%",
    height = 300,
  )
```

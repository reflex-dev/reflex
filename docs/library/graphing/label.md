---
components:
    - rx.recharts.Label
    - rx.recharts.LabelList
---

# Label

```python exec
import reflex as rx
from pcweb.templates.docpage import docgraphing

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
    "pv": 5800,
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



brush_example = """rx.recharts.bar_chart(
                rx.recharts.bar(
                    rx.recharts.label_list(data_key="uv", position="top"),
                    data_key="uv",
                    stroke="#8884d8",
                    fill="#8884d8"
                    
                ), 
                rx.recharts.bar(
                    rx.recharts.label_list(data_key="pv", position="top"),
                    data_key="pv",
                    stroke="#82ca9d",
                    fill="#82ca9d" 
                ), 
                rx.recharts.x_axis(
                    data_key="name"
                ), 
                rx.recharts.y_axis(),
                margin={"left": 10, "right": 0, "top": 20, "bottom": 10},

                data=data)"""
```

`rx.recharts.label`and `rx.recharts.label_list` add in labels to the graphs. `rx.recharts.label_list` takes in a `data_key` where we define the data column to plot.

```python eval
docgraphing(
  brush_example, 
  comp = eval(brush_example),
  data =  "data=" + str(data)
)
```

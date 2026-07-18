---
components:
  - rx.recharts.Treemap
title: Treemap
meta_description: "Create treemap charts in Python with Reflex. Build interactive Recharts treemaps to visualize hierarchical, part-to-whole data as nested rectangles — all in pure Python, no JavaScript."
---

# Treemap

```python exec
import reflex as rx
```

Treemap charts in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and created in pure Python. A treemap displays hierarchical, part-to-whole data as a set of nested rectangles, where the area of each rectangle is proportional to its value. Treemaps are a space-efficient way to compare many categories at once.

## Simple Example

An `rx.recharts.treemap()` takes a list of dictionaries as its `data` and a `data_key` naming the field that determines each rectangle's size. Use `name_key` to set the label shown on each tile.

```python demo graphing
data = [
    {"name": "Category A", "size": 2400, "fill": rx.color("accent", 8)},
    {"name": "Category B", "size": 4567, "fill": rx.color("blue", 8)},
    {"name": "Category C", "size": 1398, "fill": rx.color("green", 8)},
    {"name": "Category D", "size": 9800, "fill": rx.color("orange", 8)},
    {"name": "Category E", "size": 3908, "fill": rx.color("red", 8)},
    {"name": "Category F", "size": 4800, "fill": rx.color("purple", 8)},
]


def treemap_simple():
    return rx.recharts.treemap(
        data=data,
        data_key="size",
        name_key="name",
        width="100%",
        height=300,
    )
```

## Aspect Ratio

The `aspect_ratio` prop controls the target width-to-height ratio the treemap uses when laying out each rectangle. Lower values produce taller tiles; higher values produce wider ones.

```python demo graphing
data = [
    {"name": "Group A", "size": 2400, "fill": rx.color("accent", 8)},
    {"name": "Group B", "size": 4567, "fill": rx.color("cyan", 8)},
    {"name": "Group C", "size": 1398, "fill": rx.color("grass", 8)},
    {"name": "Group D", "size": 6800, "fill": rx.color("amber", 8)},
    {"name": "Group E", "size": 3908, "fill": rx.color("plum", 8)},
]


def treemap_aspect():
    return rx.recharts.treemap(
        data=data,
        data_key="size",
        name_key="name",
        aspect_ratio=1,
        width="100%",
        height=300,
    )
```

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Pie Chart](/docs/library/graphing/charts/piechart)
- [Bar Chart](/docs/library/graphing/charts/barchart)
- [Funnel Chart](/docs/library/graphing/charts/funnelchart)

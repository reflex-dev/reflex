---
components:
  - rx.recharts.SankeyChart
title: Sankey Chart
meta_description: "Create Sankey charts in Python with Reflex. Build interactive Recharts Sankey diagrams to visualize weighted flows between stages, categories, or systems."
---

# Sankey Chart

```python exec
import random

import reflex as rx
```

Sankey charts in Reflex are built on [Recharts](https://recharts.org/), a React charting library, and created in pure Python. A Sankey chart visualizes weighted flows between nodes, making it useful for showing movement through stages, resource allocation, user journeys, and other source-to-target relationships.

## Simple Example

An `rx.recharts.sankey_chart()` takes a `data` dictionary with `nodes` and `links`. Links refer to nodes by zero-based index.

```python demo graphing
sankey_data = {
    "nodes": [
        {"name": "Website"},
        {"name": "Landing Page"},
        {"name": "Product Page"},
        {"name": "Checkout"},
        {"name": "Purchase"},
    ],
    "links": [
        {"source": 0, "target": 1, "value": 1200},
        {"source": 1, "target": 2, "value": 900},
        {"source": 2, "target": 3, "value": 420},
        {"source": 3, "target": 4, "value": 260},
    ],
}


def sankey_simple():
    return rx.recharts.sankey_chart(
        rx.recharts.graphing_tooltip(),
        data=sankey_data,
        node_padding=24,
        node_width=12,
        link_curvature=0.55,
        width="100%",
        height=320,
    )
```

## Stateful Example

Chart data can be tied to a State var. This example randomizes the flow values when the button is clicked.

```python demo exec
class SankeyState(rx.State):
    data = {
        "nodes": [
            {"name": "Marketing"},
            {"name": "Trial"},
            {"name": "Sales"},
            {"name": "Support"},
            {"name": "Retained"},
        ],
        "links": [
            {"source": 0, "target": 1, "value": 600},
            {"source": 1, "target": 2, "value": 320},
            {"source": 2, "target": 4, "value": 210},
            {"source": 1, "target": 3, "value": 180},
            {"source": 3, "target": 4, "value": 130},
        ],
    }

    @rx.event
    def randomize_flows(self):
        for link in self.data["links"]:
            link["value"] = random.randint(80, 700)


def sankey_stateful():
    return rx.vstack(
        rx.recharts.sankey_chart(
            rx.recharts.graphing_tooltip(),
            data=SankeyState.data,
            node_padding=18,
            node_width=14,
            width="100%",
            height=320,
        ),
        rx.button("Randomize flows", on_click=SankeyState.randomize_flows),
        width="100%",
    )
```

## Custom Node Types And Styles

Use fields on each node to describe node types and per-node styling. Pass `node` or `link` dictionaries to control shared Sankey styling.

```python demo graphing
styled_sankey_data = {
    "nodes": [
        {"name": "Sources", "type": "source", "fill": rx.color("blue", 8)},
        {"name": "Direct", "type": "channel", "fill": rx.color("green", 8)},
        {"name": "Search", "type": "channel", "fill": rx.color("grass", 8)},
        {"name": "Paid", "type": "channel", "fill": rx.color("amber", 8)},
        {"name": "Revenue", "type": "outcome", "fill": rx.color("purple", 8)},
    ],
    "links": [
        {"source": 0, "target": 1, "value": 350},
        {"source": 0, "target": 2, "value": 500},
        {"source": 0, "target": 3, "value": 220},
        {"source": 1, "target": 4, "value": 190},
        {"source": 2, "target": 4, "value": 260},
        {"source": 3, "target": 4, "value": 150},
    ],
}


def sankey_custom_styles():
    return rx.recharts.sankey_chart(
        rx.recharts.graphing_tooltip(),
        data=styled_sankey_data,
        node={
            "stroke": rx.color("gray", 12),
            "strokeWidth": 1,
        },
        link={
            "stroke": rx.color("gray", 8),
            "strokeOpacity": 0.35,
        },
        node_padding=22,
        node_width=16,
        link_curvature=0.45,
        width="100%",
        height=340,
    )
```

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Treemap](/docs/library/graphing/charts/treemap)
- [Funnel Chart](/docs/library/graphing/charts/funnelchart)
- [Pie Chart](/docs/library/graphing/charts/piechart)

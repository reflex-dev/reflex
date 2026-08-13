---
components:
  - rx.recharts.SankeyChart
title: Sankey Chart
meta_description: "Create Sankey charts in Python with Reflex. Build interactive Recharts Sankey diagrams to visualize weighted flows between stages, categories, or systems."
---

# Sankey Chart

```python exec
import random
from typing import Any

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
    data: dict[str, Any] = {
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
            node={
                "fill": rx.color("accent", 7),
                "stroke": rx.color("accent", 10),
                "strokeWidth": 2,
            },
            link={
                "stroke": rx.color("gray", 7),
                "strokeOpacity": 0.35,
            },
            node_padding=18,
            node_width=14,
            width="100%",
            height=320,
        ),
        rx.button("Randomize flows", on_click=SankeyState.randomize_flows),
        width="100%",
    )
```


## Full Node / Link Customization

For complete control over node and link rendering, pass a
`@rx.recharts.sankey_chart.node` or `@rx.recharts.sankey_chart.link` decorated
function that returns an svg-based component. The function receives a
`Var[SankeyNodeProps]` or `Var[SankeyLinkProps]` object with the node or link
data `payload`, as well as the object's position and dimensions. You can use these
properties to construct a custom node or link.

Because the component renders inside the SVG element of the chart, you can only
use `rx.el.svg` components to construct the custom node or link.

The example below also uses `rx.recharts.use_chart_width()` to read the
rendered chart width and `rx.vars.use_id()` to generate a unique id that links
each link's gradient definition to the path that references it.

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


def sankey_custom_render():
    @rx.recharts.sankey_chart.node
    def custom_node(
        node: rx.Var[rx.recharts.sankey_chart.SankeyNodeProps],
    ) -> rx.Component:
        # Determine if the node is at the right edge of the chart to adjust the label position accordingly.
        is_out = node.x + node.width + 6 > rx.recharts.use_chart_width()
        return rx.fragment(
            rx.el.svg.text(
                node.payload.name,
                x=rx.cond(is_out, node.x - 6, node.x + node.width + 6).to(int),
                y=node.y + node.height / 2,
                text_anchor=rx.cond(is_out, "end", "start"),
                fill=rx.color("gray", 12),
                font_size=10,
            ),
            rx.el.svg.rect(
                x=node.x,
                y=node.y,
                width=node.width,
                height=node.height,
                # Accessing custom keys in the payload needs a `dict` cast.
                fill=node.payload.to(dict)["fill"],
                stroke=rx.color("gray", 12),
                stroke_width=1,
            ),
        )

    @rx.recharts.sankey_chart.link
    def custom_link(
        link: rx.Var[rx.recharts.sankey_chart.SankeyLinkProps],
    ) -> rx.Component:
        link_id = rx.vars.use_id()
        source = link.payload.source.to(dict)
        target = link.payload.target.to(dict)
        return rx.fragment(
            rx.el.svg.linear_gradient(
                rx.el.svg.stop(offset="0%", stop_color=source["fill"]),
                rx.el.svg.stop(offset="100%", stop_color=target["fill"]),
                id=link_id,
            ),
            rx.el.svg.path(
                d=(
                    f"M{link.sourceX},{link.sourceY} "
                    f"C{link.sourceControlX},{link.sourceY} "
                    f"{link.targetControlX},{link.targetY} "
                    f"{link.targetX},{link.targetY}"
                ),
                fill="none",
                stroke=f"url(#{link_id})",
                stroke_opacity=0.35,
                stroke_width=link.linkWidth,
            ),
            rx.el.svg.text(
                link.payload.value,
                x=(link.sourceX + link.targetX) / 2,
                y=(link.sourceY + link.targetY) / 2,
                text_anchor="middle",
                fill=rx.color("gray", 12),
                font_size=10,
            ),
        )

    return rx.recharts.sankey_chart(
        data=styled_sankey_data,
        node=custom_node,
        link=custom_link,
        width="100%",
        height=340,
    )
```

## Related Charts

Explore more chart types you can build with Reflex and Recharts in pure Python:

- [Treemap](/docs/library/graphing/charts/treemap)
- [Funnel Chart](/docs/library/graphing/charts/funnelchart)
- [Pie Chart](/docs/library/graphing/charts/piechart)

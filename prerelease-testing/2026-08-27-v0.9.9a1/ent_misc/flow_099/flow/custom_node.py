"""Creating custom nodes is as easy as building a regular React component and passing it to nodeTypes.

Since they’re standard React components, you can display any content and implement any functionality you need. Plus, you’ll have access to a range of props that allow you to extend and customize the default node behavior.
For more details, check out our [Custom Nodes guide](https://reactflow.dev/learn/customization/custom-nodes)."""

from typing import Any

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Connection, Edge, Node


class CustomNodeState(rx.State):
    bg_color: rx.Field[str] = rx.field(default="#c9f1dd")
    nodes: rx.Field[list[Node]] = rx.field(
        default_factory=lambda: [
            {
                "id": "1",
                "type": "input",
                "data": {"label": "An input node"},
                "position": {"x": 0, "y": 50},
                "sourcePosition": "right",
            },
            {
                "id": "2",
                "type": "selectorNode",
                "data": {
                    "color": "#c9f1dd",
                },
                "position": {"x": 300, "y": 50},
            },
            {
                "id": "3",
                "type": "output",
                "data": {"label": "Output A"},
                "position": {"x": 650, "y": 25},
                "targetPosition": "left",
            },
            {
                "id": "4",
                "type": "output",
                "data": {"label": "Output B"},
                "position": {"x": 650, "y": 100},
                "targetPosition": "left",
            },
        ]
    )
    edges: rx.Field[list[Edge]] = rx.field(
        default_factory=lambda: [
            {
                "id": "e1-2",
                "source": "1",
                "target": "2",
                "animated": True,
            },
            {
                "id": "e2a-3",
                "source": "2",
                "target": "3",
                "animated": True,
            },
            {
                "id": "e2b-4",
                "source": "2",
                "target": "4",
                "animated": True,
            },
        ]
    )

    @rx.event
    def on_change_color(self, color: str):
        self.nodes = [
            node
            if node["id"] != "2" or "data" not in node
            else {**node, "data": {**node["data"], "color": color}}
            for node in self.nodes
        ]
        self.bg_color = color

    @rx.event
    def set_nodes(self, nodes: list[Node]):
        self.nodes = nodes

    @rx.event
    def set_edges(self, edges: list[Edge]):
        self.edges = edges


@rx.memo
def color_selector_node(data: rx.Var[dict[str, Any]], isConnectable: rx.Var[bool]):  # noqa: N803
    data = data.to(dict)
    return rx.fragment(
        rxe.flow.handle(
            type="target",
            position="left",
            on_connect=lambda params: rx.console_log(f"handle onConnect {params}"),
            is_connectable=isConnectable,
        ),
        rx.el.div(
            "Custom Color Picker Node: ",
            rx.el.strong(data["color"]),
        ),
        rx.el.input(
            class_name="nodrag",
            type="color",
            on_change=CustomNodeState.on_change_color,
            default_value=data["color"],
        ),
        rxe.flow.handle(
            type="source",
            position="right",
            is_connectable=isConnectable,
        ),
    )


def node_stroke_color(node: rx.vars.ObjectVar[Node]):
    return rx.match(
        node["type"],
        ("input", "#0041d0"),
        (
            "selectorNode",
            CustomNodeState.bg_color,
        ),
        ("output", "#ff0072"),
        None,
    )


def node_color(node: rx.vars.ObjectVar[Node]):
    return rx.match(
        node["type"],
        (
            "selectorNode",
            CustomNodeState.bg_color,
        ),
        "#fff",
    )


@rx.page(route="/nodes/custom-node", title="Custom Node Demo")
def custom_node():
    return rx.box(
        rxe.flow(
            rxe.flow.background(bg_color=CustomNodeState.bg_color),
            rxe.flow.mini_map(
                node_stroke_color=rx.vars.function.ArgsFunctionOperation.create(
                    ("node",), node_stroke_color(rx.Var("node").to(Node))
                ),
                node_color=rx.vars.function.ArgsFunctionOperation.create(
                    ("node",), node_color(rx.Var("node").to(Node))
                ),
            ),
            rxe.flow.controls(),
            nodes=CustomNodeState.nodes,
            edges=CustomNodeState.edges,
            on_nodes_change=lambda changes: CustomNodeState.set_nodes(
                rxe.flow.util.apply_node_changes(CustomNodeState.nodes, changes)
            ),
            on_edges_change=lambda changes: CustomNodeState.set_edges(
                rxe.flow.util.apply_edge_changes(CustomNodeState.edges, changes)
            ),
            on_connect=lambda connection: CustomNodeState.set_edges(
                rxe.flow.util.add_edge(
                    connection.to(dict).merge({"animated": True}).to(Connection),
                    CustomNodeState.edges,
                )
            ),
            node_types={"selectorNode": color_selector_node},
            color_mode="light",
            snap_grid=(20, 20),
            default_viewport={"x": 0, "y": 0, "zoom": 1.5},
            snap_to_grid=True,
            attribution_position="bottom-left",
            fit_view=True,
        ),
        height="100vh",
        width="100vw",
    )

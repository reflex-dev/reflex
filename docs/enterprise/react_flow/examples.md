# Example React Flow Components

This section showcases examples of interactive flow components built with Reflex and Reflex Enterprise. Learn how to create dynamic nodes, edges, and custom behaviors for building flow diagrams in your React apps.

## Add Node on Edge Drop

In this example, we demonstrate how to dynamically add nodes to a flow when a connection is dropped onto the canvas. When the user drops a connection, a new node is created at the drop point, and an edge is added between the source node and the new node.


```python demo exec
import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import (
    ConnectionInProgress,
    Edge,
    NoConnection,
    Node,
    XYPosition,
)

node_style = {
    "color": "#000000",
}

initial_nodes: list[Node] = [
    {
        "id": "0",
        "type": "input",
        "data": {"label": "Node"},
        "position": {"x": 0, "y": 50},
        "style": node_style
    },
]


class AddNodesOnEdgeDropState(rx.State):
    nodes: rx.Field[list[Node]] = rx.field(default_factory=lambda: initial_nodes)
    edges: rx.Field[list[Edge]] = rx.field(default_factory=list)
    node_id: int = 1

    @rx.event
    def increment(self):
        self.node_id += 1

    @rx.event
    def set_nodes(self, nodes: list[Node]):
        self.nodes = nodes

    @rx.event
    def set_edges(self, edges: list[Edge]):
        self.edges = edges

    @rx.event
    def handle_connect_end(
        self,
        connection_status: NoConnection | ConnectionInProgress,
        event: rx.event.PointerEventInfo,
        flow_position: XYPosition,
    ):
        if not connection_status["isValid"]:
            node_id = str(self.node_id)
            self.increment()
            self.nodes.append(
                {
                    "id": node_id,
                    "position": flow_position,
                    "data": {"label": f"Node {node_id}"},
                    "origin": (0.5, 0.0),
                    "style": node_style
                }
            )
            self.edges.append(
                {
                    "id": node_id,
                    "source": connection_status["fromNode"]["id"],
                    "target": node_id,
                    "style": node_style
                }
            )

def add_node_on_edge_drop():
    return rx.box(
        rxe.flow.provider(
            rxe.flow(
                rxe.flow.controls(),
                rxe.flow.mini_map(),
                rxe.flow.background(),
                on_connect=lambda connection: AddNodesOnEdgeDropState.set_edges(
                    rxe.flow.util.add_edge(connection, AddNodesOnEdgeDropState.edges)
                ),
                on_connect_end=(
                    lambda connection_status, event: (
                        AddNodesOnEdgeDropState.handle_connect_end(
                            connection_status,
                            event,
                            rxe.flow.api.screen_to_flow_position(
                                x=event.client_x,
                                y=event.client_y,
                            ),
                        )
                    )
                ),
                nodes=AddNodesOnEdgeDropState.nodes,
                edges=AddNodesOnEdgeDropState.edges,
                default_nodes=AddNodesOnEdgeDropState.nodes,
                default_edges=AddNodesOnEdgeDropState.edges,
                on_nodes_change=lambda changes: AddNodesOnEdgeDropState.set_nodes(
                    rxe.flow.util.apply_node_changes(
                        AddNodesOnEdgeDropState.nodes, changes
                    )
                ),
                on_edges_change=lambda changes: AddNodesOnEdgeDropState.set_edges(
                    rxe.flow.util.apply_edge_changes(
                        AddNodesOnEdgeDropState.edges, changes
                    )
                ),
                fit_view=True,
                fit_view_options={"padding": 2},
                node_origin=(0.5, 0.0),
            )
        ),
        height="100vh",
        width="100vw",
    )

```

## Connection Limit on Custom Node

This example demonstrates how to create a custom node with a connection limit on its handle. The handle can be configured to allow a specific number of connections, or no connections at all, using the isConnectable property. This is useful when you want to restrict the number of connections a node can have.

```python demo exec
import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Edge, HandleType, Node, Position

node_style = {
    "color": "#000000",
}

class ConnectionLimitState(rx.State):
    nodes: rx.Field[list[Node]] = rx.field(
        default_factory=lambda: [
            {
                "id": "1",
                "type": "input",
                "data": {"label": "Node 1"},
                "position": {"x": 0, "y": 25},
                "sourcePosition": "right",
                "style": node_style
            },
            {
                "id": "2",
                "type": "custom",
                "data": {},
                "position": {"x": 250, "y": 50},
                "style": node_style
            },
            {
                "id": "3",
                "type": "input",
                "data": {"label": "Node 2"},
                "position": {"x": 0, "y": 100},
                "sourcePosition": "right",
                "style": node_style
            },
        ]
    )
    edges: rx.Field[list[Edge]] = rx.field(default_factory=list)

    @rx.event
    def set_nodes(self, nodes: list[Node]):
        self.nodes = nodes

    @rx.event
    def set_edges(self, edges: list[Edge]):
        self.edges = edges


@rx.memo
def custom_handle(
    type: rx.Var[HandleType], position: rx.Var[Position], connection_count: rx.Var[int]
):
    connections = rxe.flow.api.get_node_connections()
    return rxe.flow.handle(
        type=type,
        position=position,
        connection_count=connection_count,
        is_connectable=connections.length() < connection_count.guess_type(),
    )


@rx.memo
def custom_node():
    return rx.el.div(
        custom_handle(type="target", position="left", connection_count=1),
        rx.el.div("← Only one edge allowed"),
        class_name="border border-1 p-2 rounded-sm",
        border_color=rx.color_mode_cond("black", ""),
        color="black",
        bg="white",
    )


def connection_limit():
    return rx.box(
        rxe.flow(
            rxe.flow.background(),
            nodes=ConnectionLimitState.nodes,
            edges=ConnectionLimitState.edges,
            default_nodes=ConnectionLimitState.nodes,
            default_edges=ConnectionLimitState.edges,
            on_nodes_change=lambda changes: ConnectionLimitState.set_nodes(
                rxe.flow.util.apply_node_changes(ConnectionLimitState.nodes, changes)
            ),
            on_edges_change=lambda changes: ConnectionLimitState.set_edges(
                rxe.flow.util.apply_edge_changes(ConnectionLimitState.edges, changes)
            ),
            on_connect=lambda connection: ConnectionLimitState.set_edges(
                rxe.flow.util.add_edge(connection, ConnectionLimitState.edges)
            ),
            node_types={
                "custom": rx.vars.function.ArgsFunctionOperation.create(
                    (), custom_node()
                )
            },
            color_mode="light",
            fit_view=True,
        ),
        height="100vh",
        width="100vw",
    )
```

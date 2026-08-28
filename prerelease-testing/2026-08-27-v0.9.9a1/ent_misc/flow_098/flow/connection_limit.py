"""This is an example of a custom node with a custom handle that can limit the amount of connections a handle can have using the isConnectable prop.

You can use a boolean, a number (the number of max. connections the handle should have) or a callback function that returns a boolean as an arg for the isConnectable prop of the CustomHandle component."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Edge, HandleType, Node, Position


class ConnectionLimitState(rx.State):
    nodes: rx.Field[list[Node]] = rx.field(
        default_factory=lambda: [
            {
                "id": "1",
                "type": "input",
                "data": {"label": "Node 1"},
                "position": {"x": 0, "y": 25},
                "sourcePosition": "right",
            },
            {
                "id": "2",
                "type": "custom",
                "data": {},
                "position": {"x": 250, "y": 50},
            },
            {
                "id": "3",
                "type": "input",
                "data": {"label": "Node 2"},
                "position": {"x": 0, "y": 100},
                "sourcePosition": "right",
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
    )


@rx.page(route="/nodes/connection-limit", title="Connection Limit Demo")
def connection_limit():
    return rx.box(
        rxe.flow(
            rxe.flow.background(),
            nodes=ConnectionLimitState.nodes,
            edges=ConnectionLimitState.edges,
            on_nodes_change=lambda changes: ConnectionLimitState.set_nodes(
                rxe.flow.util.apply_node_changes(ConnectionLimitState.nodes, changes)
            ),
            on_edges_change=lambda changes: ConnectionLimitState.set_edges(
                rxe.flow.util.apply_edge_changes(ConnectionLimitState.edges, changes)
            ),
            on_connect=lambda connection: ConnectionLimitState.set_edges(
                rxe.flow.util.add_edge(connection, ConnectionLimitState.edges)
            ),
            node_types={"custom": custom_node},
            color_mode="light",
            fit_view=True,
        ),
        height="100vh",
        width="100vw",
    )

"""You can create a new node when you drop the connection line on the pane by using the onConnectStart and onConnectEnd handlers."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import (
    ConnectionInProgress,
    Edge,
    NoConnection,
    Node,
    XYPosition,
)

initial_nodes: list[Node] = [
    {
        "id": "0",
        "type": "input",
        "data": {"label": "Node"},
        "position": {"x": 0, "y": 50},
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
                }
            )
            self.edges.append(
                {
                    "id": node_id,
                    "source": connection_status["fromNode"]["id"],
                    "target": node_id,
                }
            )


@rx.page(route="/nodes/add-node-on-edge-drop", title="Add Node on Edge Drop Demo")
def add_node_on_edge_drop():
    return rx.box(
        rxe.flow.provider(
            rxe.flow(
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
                color_mode="light",
                fit_view=True,
                fit_view_options={"padding": 2},
                node_origin=(0.5, 0.0),
            )
        ),
        height="100vh",
        width="100vw",
    )

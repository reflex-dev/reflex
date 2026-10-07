import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Edge, Node

initial_nodes: list[Node] = [
    {
        "id": "1",
        "data": {"label": "Node 1"},
        "position": {"x": 0, "y": 0},
        "style": {
            "width": 200,
            "height": 100,
        },
    },
    {
        "id": "2",
        "data": {"label": "Node 2"},
        "position": {"x": 0, "y": 150},
    },
    {
        "id": "3",
        "data": {"label": "Node 3"},
        "position": {"x": 250, "y": 0},
    },
    {
        "id": "4",
        "data": {"label": "Node"},
        "position": {"x": 350, "y": 150},
        "style": {
            "width": 50,
            "height": 50,
        },
    },
]

initial_edges: list[Edge] = []


class IntersectionsState(rx.State):
    nodes: rx.Field[list[Node]] = rx.field(default_factory=lambda: initial_nodes)
    edges: rx.Field[list[Edge]] = rx.field(default_factory=lambda: initial_edges)

    @rx.event
    def set_nodes(self, nodes: list[Node]):
        self.nodes = nodes

    @rx.event
    def set_edges(self, edges: list[Edge]):
        self.edges = edges


@rx.page(route="/nodes/intersections", title="Intersections")
def intersections():
    return rx.box(
        rxe.flow.provider(
            rxe.flow(
                rxe.flow.background(),
                rxe.flow.controls(),
                on_nodes_change=lambda node_changes: IntersectionsState.set_nodes(
                    rxe.flow.util.apply_node_changes(
                        IntersectionsState.nodes, node_changes
                    )
                ),
                on_edges_change=lambda edge_changes: IntersectionsState.set_edges(
                    rxe.flow.util.apply_edge_changes(
                        IntersectionsState.edges, edge_changes
                    )
                ),
                on_node_drag=lambda node: IntersectionsState.set_nodes(
                    IntersectionsState.nodes.foreach(
                        lambda n: n.to(Node).merge(
                            {
                                "className": rx.cond(
                                    rxe.flow.api.get_intersecting_nodes(node)
                                    .foreach(lambda n: n["id"])
                                    .contains(n["id"]),
                                    "highlight",
                                    "",
                                )
                            }
                        )
                    ),
                ).throttle(100),
                nodes=IntersectionsState.nodes,
                edges=IntersectionsState.edges,
                color_mode="light",
                class_name="intersection-flow",
                select_nodes_on_drag=False,
                fit_view=True,
            ),
        ),
        height="100vh",
        width="100vw",
    )

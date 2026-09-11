from typing import Any, Mapping, TypedDict

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Edge, Node, Position

initial_edges: list[Edge] = [
    {
        "id": "e1-2",
        "source": "1-1",
        "target": "1-2",
        "label": "edge",
        "type": "smoothstep",
    },
    {
        "id": "e1-3",
        "source": "1-1",
        "target": "1-3",
        "animated": True,
        "label": "animated edge",
    },
    {
        "id": "e2-2",
        "source": "1-2",
        "target": "2-2",
        "type": "smoothstep",
        "markerEnd": {
            "type": "arrowclosed",
        },
    },
    {
        "id": "e2-3",
        "source": "2-2",
        "target": "2-3",
        "type": "smoothstep",
        "markerEnd": {
            "type": "arrowclosed",
        },
    },
    {
        "id": "e3-3",
        "source": "2-3",
        "sourceHandle": "a",
        "target": "3-2",
        "type": "button",
        "animated": True,
        "style": {"stroke": "rgb(158, 118, 255)"},
    },
    {
        "id": "e3-4",
        "source": "2-3",
        "sourceHandle": "b",
        "target": "3-1",
        "type": "button",
    },
]

initial_nodes: list[Node] = [
    {
        "id": "annotation-1",
        "type": "annotation",
        "draggable": False,
        "selectable": False,
        "data": {
            "level": 1,
            "label": "Built-in node and edge types. Draggable, deletable and connectable!",
            "arrowStyle": {
                "right": 0,
                "bottom": 0,
                "transform": "translate(-30px,10px) rotate(-80deg)",
            },
        },
        "position": {"x": -200, "y": -30},
    },
    {
        "id": "1-1",
        "type": "input",
        "data": {
            "label": "Input Node",
        },
        "position": {"x": 150, "y": 0},
    },
    {
        "id": "1-2",
        "type": "default",
        "data": {
            "label": "Default Node",
        },
        "position": {"x": 0, "y": 100},
    },
    {
        "id": "1-3",
        "type": "output",
        "data": {
            "label": "Output Node",
        },
        "position": {"x": 300, "y": 100},
    },
    {
        "id": "annotation-2",
        "type": "annotation",
        "draggable": False,
        "selectable": False,
        "data": {
            "level": 2,
            "label": "Sub flows, toolbars and resizable nodes!",
            "arrowStyle": {
                "left": 0,
                "bottom": 0,
                "transform": "translate(5px, 25px) scale(1, -1) rotate(100deg)",
            },
        },
        "position": {"x": 220, "y": 200},
    },
    {
        "id": "2-1",
        "type": "group",
        "position": {
            "x": -170,
            "y": 250,
        },
        "style": {
            "width": 380,
            "height": 180,
        },
    },
    {
        "id": "2-2",
        "data": {},
        "type": "tools",
        "position": {"x": 50, "y": 50},
        "style": {
            "width": 80,
            "height": 80,
        },
        "parentId": "2-1",
        "extent": "parent",
    },
    {
        "id": "2-3",
        "type": "resizer",
        "data": {
            "label": "Resize Me",
        },
        "position": {"x": 250, "y": 50},
        "style": {
            "width": 80,
            "height": 80,
        },
        "parentId": "2-1",
        "extent": "parent",
    },
    {
        "id": "annotation-3",
        "type": "annotation",
        "draggable": False,
        "selectable": False,
        "data": {
            "level": 3,
            "label": "Nodes and edges can be anything and are fully customizable!",
            "arrowStyle": {
                "right": 0,
                "bottom": 0,
                "transform": "translate(-35px, 20px) rotate(-80deg)",
            },
        },
        "position": {"x": -40, "y": 570},
    },
    {
        "id": "3-2",
        "type": "textinput",
        "position": {"x": 150, "y": 650},
        "data": {},
    },
    {
        "id": "3-1",
        "type": "circle",
        "position": {"x": 350, "y": 500},
        "data": {},
    },
]


@rx.memo
def button_edge(
    id: rx.Var[str],
    sourceX: rx.Var[float],  # noqa: N803
    sourceY: rx.Var[float],  # noqa: N803
    targetX: rx.Var[float],  # noqa: N803
    targetY: rx.Var[float],  # noqa: N803
    sourcePosition: rx.Var[Position],  # noqa: N803
    targetPosition: rx.Var[Position],  # noqa: N803
    markerEnd: rx.Var[str],  # noqa: N803
):
    bezier_path = rxe.components.flow.util.get_bezier_path(
        source_x=sourceX,
        source_y=sourceY,
        target_x=targetX,
        target_y=targetY,
        source_position=sourcePosition,
        target_position=targetPosition,
    )
    return rx.fragment(
        rxe.flow.base_edge(path=bezier_path.path, markerEnd=markerEnd),
        rxe.flow.edge_label_renderer(
            rx.el.div(
                rx.el.button(
                    "×",  # noqa: RUF001
                    class_name="button-edge__button",
                    on_click=rx.run_script(
                        rxe.flow.api.set_edges(
                            rx.vars.FunctionStringVar.create(
                                "Array.prototype.filter.call"
                            ).call(
                                rxe.flow.api.get_edges(),
                                rx.Var(f"((edge) => edge.id !== {id})"),
                            ),
                        )
                    ),
                ),
                class_name="button-edge__label nodrag nopan",
                transform=f"translate(-50%, -50%) translate({bezier_path.label_x}px,{bezier_path.label_y}px)",
            )
        ),
    )


emojis = ["🚀", "🔥", "✨"]


@rx.memo
def toolbar_node(data: rx.vars.ObjectVar[Mapping[str, Any]]):
    return rx.fragment(
        rxe.flow.node_toolbar(
            *[
                rx.el.button(
                    emoji,
                    key=emoji,
                    on_click=OverviewState.set_emoji(emoji),
                    custom_attrs={"aria-label": f"Select emoji {emoji}"},
                )
                for emoji in emojis
            ],
            is_visible=True,
        ),
        rx.el.div(rx.el.div(OverviewState.emoji)),
        rxe.flow.handle(
            type="source",
            position="left",
        ),
        rxe.flow.handle(
            type="target",
            position="right",
        ),
        rx.el.div(data["label"]),
    )


@rx.memo
def circle_node(
    positionAbsoluteX: rx.vars.Var[float],  # noqa: N803
    positionAbsoluteY: rx.vars.Var[float],  # noqa: N803
):
    label = f"Position x:{round(positionAbsoluteX.guess_type())} y:{round(positionAbsoluteY.guess_type())}"
    return rx.el.div(
        rx.el.div(label),
        rxe.flow.handle(
            type="target",
            position="left",
            class_name="custom-handle",
        ),
    )


@rx.memo
def resizer_node(data: rx.vars.ObjectVar[Mapping[str, Any]]):
    return rx.fragment(
        rxe.flow.node_resizer(
            min_width=1,
            min_height=1,
        ),
        rxe.flow.handle(
            type="target",
            position="left",
            class_name="custom-handle",
        ),
        rx.el.div(data["label"]),
        rx.el.div(
            rxe.flow.handle(
                id="a",
                type="source",
                position="bottom",
                class_name="resizer-node__handle custom-handle",
            ),
            rxe.flow.handle(
                id="b",
                type="source",
                position="bottom",
                class_name="resizer-node__handle custom-handle",
            ),
            class_name="resizer-node__handles",
        ),
    )


@rx.memo
def annotation_node(data: rx.vars.ObjectVar[Mapping[str, Any]]):
    return rx.fragment(
        rx.el.div(
            rx.el.div(data["level"], ".", class_name="annotation-level"),
            rx.el.div(data["label"]),
            class_name="annotation-content",
        ),
        rx.cond(
            data["arrowStyle"],
            rx.el.div(
                "⤹",
                class_name="annotation-arrow",
                style=data["arrowStyle"],
            ),
        ),
    )


dimension_attrs = ["width", "height"]


def dimension_input(attr: str):
    return rx.fragment(
        rx.el.label(f"Node {attr}"),
        rx.el.input(
            type="number",
            value=rx.cond(OverviewState.dimensions, OverviewState.dimensions[attr], 0),
            on_change=lambda value: OverviewState.set_dimensions(attr, value),
            class_name="text-input-node__input xy-theme__input nodrag",
        ),
        key=attr,
    )


@rx.memo
def dimension_node(id: rx.vars.Var[str]):
    return rx.fragment(
        *[dimension_input(attr) for attr in dimension_attrs],
        rxe.flow.handle(
            type="target",
            position="top",
            class_name="custom-handle",
        ),
    )


class Dimensions(TypedDict):
    width: float
    height: float


class OverviewState(rx.State):
    emoji: str = "🚀"

    nodes: rx.Field[list[Node]] = rx.field(default_factory=lambda: initial_nodes)
    edges: rx.Field[list[Edge]] = rx.field(default_factory=lambda: initial_edges)

    @rx.var
    def dimensions(self) -> Dimensions | None:
        node = next((node for node in self.nodes if node["id"] == "2-3"), None)
        if (
            not node
            or not (measured := node.get("measured"))
            or not (height := measured.get("height"))
            or not (width := measured.get("width"))
        ):
            return None
        return {"width": width, "height": height}

    @rx.event
    def set_emoji(self, emoji: str):
        self.emoji = emoji

    @rx.event
    def set_nodes(self, nodes: list[Node]):
        self.nodes = nodes

    @rx.event
    def set_edges(self, edges: list[Edge]):
        self.edges = edges

    @rx.event
    def set_dimensions(self, attr: str, value_str: str):
        value = float(value_str)

        def _updated_node(current_node: Node) -> Node:
            parent_node = next(
                (node for node in self.nodes if node["id"] == "2-1"), None
            )
            parent_width = (
                parent_node.get("style", {}).get("width") if parent_node else None
            ) or float("inf")
            parent_height = (
                parent_node.get("style", {}).get("height") if parent_node else None
            ) or float("inf")

            current_pos_x = current_node.get("position", {}).get("x", 0)
            current_pos_y = current_node.get("position", {}).get("y", 0)

            max_width = max(parent_width - current_pos_x, 0)
            max_height = max(parent_height - current_pos_y, 0)

            new_size = {
                "width": (
                    min(value, max_width)
                    if attr == "width"
                    else current_node.get("style", {}).get("width")
                ),
                "height": (
                    min(value, max_height)
                    if attr == "height"
                    else current_node.get("style", {}).get("height")
                ),
            }

            return {
                **current_node,
                "style": {**current_node.get("style", {}), **new_size},
            }

        self.nodes = [
            node if node["id"] != "2-3" else _updated_node(node) for node in self.nodes
        ]


@rx.page(route="/overview", title="Feature Overview")
def overview():
    return rx.box(
        rxe.flow(
            rxe.flow.mini_map(
                zoomable=True,
                pannable=True,
                node_class_name=rx.Var("((node) => node.type)"),
            ),
            rxe.flow.controls(),
            rxe.flow.background(),
            on_nodes_change=lambda node_changes: OverviewState.set_nodes(
                rxe.flow.util.apply_node_changes(OverviewState.nodes, node_changes)
            ),
            on_edges_change=lambda edge_changes: OverviewState.set_edges(
                rxe.flow.util.apply_edge_changes(OverviewState.edges, edge_changes)
            ),
            nodes=OverviewState.nodes,
            edges=OverviewState.edges,
            node_types={
                "tools": toolbar_node,
                "circle": circle_node,
                "resizer": resizer_node,
                "annotation": annotation_node,
                "textinput": dimension_node,
            },
            edge_types={"button": button_edge},
            color_mode="light",
            fit_view=True,
            attribution_position="top-right",
        ),
        height="100vh",
        width="100vw",
    )

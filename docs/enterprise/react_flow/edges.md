# Edges

Edges connect nodes together in a flow. This page explains how to define, customize, and interact with edges in Reflex Flow.

## The Edge Type

An edge is represented as a Python dictionary with the following fields:

- `id` (`str`) – Unique identifier for the edge.
- `source` (`str`) – ID of the source node.
- `target` (`str`) – ID of the target node.
- `type` (`str`) – Edge type defined in `edge_types`.
- `sourceHandle` (`str | None`) – Optional source handle ID.
- `targetHandle` (`str | None`) – Optional target handle ID.
- `animated` (`bool`) – Whether the edge should animate.
- `hidden` (`bool`) – Whether the edge is hidden.
- `deletable` (`bool`) – Whether the edge can be removed.
- `selectable` (`bool`) – Whether the edge can be selected.
- `data` (`dict`) – Arbitrary metadata.
- `label` (`Any`) – Label rendered along the edge.
- `style` (`dict`) – Custom styles.
- `className` (`str`) – CSS class for the edge.

## Basic Edge Types

Reflex Flow comes with several built-in edge types:

### Default Edge Types

```python
edges: list[Edge] = [
    {"id": "e1", "source": "1", "target": "2", "type": "default"},
    {"id": "e2", "source": "2", "target": "3", "type": "straight"},
    {"id": "e3", "source": "3", "target": "4", "type": "step"},
    {"id": "e4", "source": "4", "target": "5", "type": "smoothstep"},
    {"id": "e5", "source": "5", "target": "6", "type": "bezier"},
]
```

- **default** – Standard curved edge
- **straight** – Direct line between nodes
- **step** – Right-angled path with steps
- **smoothstep** – Smooth right-angled path
- **bezier** – Curved bezier path

## Edge Styling

### Basic Styling

Add visual styling to edges using the `style` property:

```python
edges: list[Edge] = [
    {
        "id": "styled-edge",
        "source": "1",
        "target": "2",
        "style": {
            "stroke": "#ff6b6b",
            "strokeWidth": 3,
        }
    }
]
```

### Animated Edges

Make edges animate with flowing dots:

```python
edges: list[Edge] = [
    {
        "id": "animated-edge",
        "source": "1",
        "target": "2",
        "animated": True,
        "style": {"stroke": "#4dabf7"}
    }
]
```

### Edge Labels

Add text labels to edges:

```python
edges: list[Edge] = [
    {
        "id": "labeled-edge",
        "source": "1",
        "target": "2",
        "label": "Connection",
        "style": {"stroke": "#51cf66"}
    }
]
```

# Custom Edges

React Flow in Reflex also allows you to define custom edge types. This is useful when you want edges to carry extra functionality (like buttons, labels, or dynamic styling) beyond the default straight or bezier connectors.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import (
    ConnectionInProgress,
    Edge,
    NoConnection,
    Node,
    Position,
)

class SimpleEdgeDemoState(rx.State):
    nodes: list[Node] = [
        {"id": "1", "position": {"x": 0, "y": 0}, "data": {"label": "Node A"}, "style": {"color": "#000000",}},
        {"id": "2", "position": {"x": 250, "y": 150}, "data": {"label": "Node B"}, "style": {"color": "#000000",}},
    ]
    edges: list[Edge] = [
        {"id": "e1-2", "source": "1", "target": "2", "type": "button"}
    ]

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
    ):
        if not connection_status["isValid"]:
            new_edge = {
                "id": f"{connection_status['fromNode']['id']}-{connection_status['toNode']['id']}",
                "source": connection_status["fromNode"]["id"],
                "target": connection_status["toNode"]["id"],
                "type": "button",
            }
            self.edges.append(new_edge)



@rx.memo
def button_edge(
    id: rx.Var[str],
    sourceX: rx.Var[float],
    sourceY: rx.Var[float],
    targetX: rx.Var[float],
    targetY: rx.Var[float],
    sourcePosition: rx.Var[Position],
    targetPosition: rx.Var[Position],
    markerEnd: rx.Var[str],
):
    bezier_path = rxe.components.flow.util.get_bezier_path(
        source_x=sourceX,
        source_y=sourceY,
        target_x=targetX,
        target_y=targetY,
        source_position=sourcePosition,
        target_position=targetPosition,
    )

    mid_x = bezier_path.label_x
    mid_y = bezier_path.label_y

    return rx.fragment(
        rxe.flow.base_edge(path=bezier_path.path, markerEnd=markerEnd),
        rxe.flow.edge_label_renderer(
            rx.el.div(
                rx.el.button(
                    "×",
                    class_name=("w-[30px] h-[30px] border-2 border-gray-200 bg-gray-200 text-black rounded-full text-[12px] pt-0 cursor-pointer hover:bg-gray-400 hover:text-white"),
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
                    style={
                        "position": "absolute",
                        "left": f"{mid_x}px",
                        "top": f"{mid_y}px",
                        "transform": "translate(-50%, -50%)",
                        "pointerEvents": "all",
                    },
                ),
            )
        ),
    )

def very_simple_custom_edge_example():
    return rx.box(
        rxe.flow(
            rxe.flow.background(),
            default_nodes=SimpleEdgeDemoState.nodes,
            default_edges=SimpleEdgeDemoState.edges,
            nodes=SimpleEdgeDemoState.nodes,
            edges=SimpleEdgeDemoState.edges,
            on_connect=lambda connection: SimpleEdgeDemoState.set_edges(
                rxe.flow.util.add_edge(connection, SimpleEdgeDemoState.edges)
            ),
            on_connect_end=lambda status, event: SimpleEdgeDemoState.handle_connect_end(status),
            edge_types={"button": button_edge},
            fit_view=True,
        ),
        height="100vh",
        width="100%",
    )

```

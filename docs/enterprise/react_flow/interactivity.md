# Adding Interactivity to Your Flow

This guide shows how to create an interactive flow in Reflex, allowing you to select, drag, and connect nodes and edges.

## Define the State

We start by defining the nodes and edges of the flow. The `FlowState` class holds the nodes and edges as state variables and includes event handlers to respond to changes.

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Node, Edge

class FlowState(rx.State):
    nodes: list[Node] = [
        {"id": "1", "type": "input", "position": {"x": 100, "y": 100}, "data": {"label": "Node 1"}},
        {"id": "2", "type": "default", "position": {"x": 300, "y": 200}, "data": {"label": "Node 2"}},
    ]

    edges: list[Edge] = [
        {"id": "e1-2", "source": "1", "target": "2", "label": "Connection", "type": "step"}
    ]
```

# Add Event Handlers

Event handlers allow the flow to respond to user interactions such as dragging nodes, updating edges, or creating new connections.

```python
@rx.event
def set_nodes(self, nodes: list[Node]):
    self.nodes = nodes

@rx.event
def set_edges(self, edges: list[Edge]):
    self.edges = edges

```

- set_nodes updates nodes when they are moved or edited.

- set_edges updates edges when they are modified or deleted.


## Render the Interactive Flow

Finally, we render the flow using **rxe.flow**, passing in the state and event handlers. Additional UI features include zoom/pan controls, a background grid, and a mini-map for navigation.

```python
def interactive_flow():
    return rx.box(
        rxe.flow(
            rxe.flow.controls(),
            rxe.flow.background(),
            rxe.flow.mini_map(),
            nodes=FlowState.nodes,
            edges=FlowState.edges,
            on_nodes_change=lambda node_changes: FlowState.set_nodes(
                rxe.flow.util.apply_node_changes(FlowState.nodes, node_changes)
            ),
            on_edges_change=lambda edge_changes: FlowState.set_edges(
                rxe.flow.util.apply_edge_changes(FlowState.edges, edge_changes)
            ),
            fit_view=True,

            attribution_position="bottom-right",
        ),
        height="100vh",
        width="100vw",
    )
```

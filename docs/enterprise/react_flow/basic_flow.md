# Basic Flow Example

This example demonstrates a simple flow diagram with three nodes and two edges, showing how nodes can be connected and how edges can be animated.

### Nodes

- Input Node – starting point
- Default Node – standard content node
- Output Node – endpoint of the flow

### Edges

- Input → Default (animated)
- Default → Output

### Interactivity

- Nodes can be moved
- Edges update dynamically
- Users can drag from handles to create new edges
- Zoom, pan, and mini-map controls are available

### Visual Layout

- Flow fits viewport automatically
- Background grid for orientation
- Light and dark color modes supported

### Example Flow

```python demo exec
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.components.flow.types import Node, Edge

# Common style for all nodes
node_style = {
    "backgroundColor": "#ffcc00",
    "color": "#000000",
    "padding": "10px",
    "borderRadius": "5px",
}


class FlowState(rx.State):
    nodes: list[Node] = [
        {
            "id": "1",
            "type": "input",
            "position": {"x": 100, "y": 100},
            "data": {"label": "Input Node"},
            "style": node_style,
        },
        {
            "id": "2",
            "type": "default",
            "position": {"x": 300, "y": 200},
            "data": {"label": "Default Node"},
            "style": node_style,
        },
        {
            "id": "3",
            "type": "output",
            "position": {"x": 500, "y": 100},
            "data": {"label": "Output Node"},
            "style": node_style,
        },
    ]

    edges: list[Edge] = [
        {"id": "e1-2", "source": "1", "target": "2", "animated": True},
        {"id": "e2-3", "source": "2", "target": "3"},
    ]


def flow_example():
    return rx.box(
        rxe.flow(
            # Core flow components
            rxe.flow.controls(),
            rxe.flow.background(),
            rxe.flow.mini_map(),
            # Flow configuration
            default_nodes=FlowState.nodes,
            default_edges=FlowState.edges,
            nodes=FlowState.nodes,
            edges=FlowState.edges,
            # Visual settings
            fit_view=True,
            attribution_position="bottom-right",
        ),
        height="100vh",
        width="100vw",
    )
```

```python test
def test_basic_flow_nodes_edges_and_controls(demo):
    flow = demo.get_by_role("application")
    for label in ["Input Node", "Default Node", "Output Node"]:
        expect(flow.get_by_role("group").filter(has_text=label)).to_have_text(label)
    expect(flow.get_by_role("group", name="Edge from 1 to 2")).to_be_attached()
    expect(flow.get_by_role("group", name="Edge from 2 to 3")).to_be_attached()
    expect(flow.get_by_role("img", name="Mini Map")).to_be_visible()
    zoom_in = flow.get_by_role("button", name="Zoom In")
    expect(zoom_in).to_be_disabled()
    flow.get_by_role("button", name="Zoom Out").click()
    expect(zoom_in).to_be_enabled()
```

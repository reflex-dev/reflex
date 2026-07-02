```python exec
import reflex as rx
from typing import Any
```

# Complex Example

In this more complex example we will be wrapping [React Flow](https://reactflow.dev), a library for building node-based applications like flow charts, diagrams, and graphs.

This example pulls together everything from the previous pages — `library` and `tag`, props, event handlers, and imports — and adds the patterns that make an interactive wrap work well in practice: client-only rendering, event specs that strip non-serializable payloads, and throttling high-frequency events.

## Import

Let's start by importing the library [@xyflow/react](https://www.npmjs.com/package/@xyflow/react). Make a separate file called `react_flow.py` and add the following code:

```python
import reflex as rx
from typing import Any


class ReactFlowLib(rx.Component):
    """Shared base for components from @xyflow/react."""

    # Pin the version so the wrap only changes when you update it
    # intentionally. (The legacy `reactflow` package is deprecated —
    # v12 ships as @xyflow/react.)
    library = "@xyflow/react@12.11.1"

    def add_imports(self):
        # React Flow renders unusably without its stylesheet. Importing it
        # from the component means users of your wrap can't forget it.
        return {"": ["@xyflow/react/dist/style.css"]}
```

Two things to note:

1. The version is **pinned**. This matters extra for wrapped libraries: an unpinned upstream can rename props or components out from under your wrap.
2. The CSS file is imported via `add_imports` with the empty-string key, as described in [imports and styles](/docs/wrapping-react/imports-and-styles/).

## Components

For this tutorial we will wrap three components from React Flow: `ReactFlow`, `Background`, and `Controls`.

The main `ReactFlow` component measures DOM nodes and uses browser APIs like `ResizeObserver`, so it must only render on the client — we subclass `rx.NoSSRComponent` for it (see [Dynamic Imports](/docs/wrapping-react/library-and-tags/)). The simpler subcomponents can stay as regular components.

Here we define the `tag` and the props that we will need. We define `EventHandler` props `on_nodes_change`, `on_connect`, and `on_node_click`; you can find all the events that the component triggers in the [React Flow docs](https://reactflow.dev/api-reference/react-flow).

Each `EventHandler` needs an event spec: a function that maps the arguments the underlying JavaScript callback receives to the payload your Python event handler gets. Two of these callbacks pass plain, JSON-serializable data through unchanged — but `onNodeClick` receives a React synthetic mouse event as its first argument, which is huge, cyclic, and not JSON-serializable. The spec drops it and forwards only the node. Stripping DOM events like this is essential: forwarding them blindly breaks the event at runtime.

```python
import reflex as rx
from typing import Any


class ReactFlowLib(rx.Component): ...


def connection_spec(
    connection: rx.Var[dict[str, Any]],
) -> tuple[rx.Var[dict[str, Any]]]:
    """(connection) — plain data, pass it through."""
    return (connection,)


def changes_spec(
    changes: rx.Var[list[dict[str, Any]]],
) -> tuple[rx.Var[list[dict[str, Any]]]]:
    """(changes) — a list of diffs, e.g. moved node positions."""
    return (changes,)


def node_click_spec(
    event: rx.Var[dict[str, Any]], node: rx.Var[dict[str, Any]]
) -> tuple[rx.Var[dict[str, Any]]]:
    """(event, node) -> (node) — drop the DOM event, forward the node."""
    return (node,)


class ReactFlow(rx.NoSSRComponent, ReactFlowLib):
    tag = "ReactFlow"

    nodes: rx.Var[list[dict[str, Any]]]

    edges: rx.Var[list[dict[str, Any]]]

    fit_view: rx.Var[bool]

    nodes_draggable: rx.Var[bool]

    nodes_connectable: rx.Var[bool]

    on_nodes_change: rx.EventHandler[changes_spec]

    on_connect: rx.EventHandler[connection_spec]

    on_node_click: rx.EventHandler[node_click_spec]
```

Now let's add the `Background` and `Controls` components and create the convenience functions so that we can use the components in our app.

```python
import reflex as rx
from typing import Any


class ReactFlowLib(rx.Component): ...


class ReactFlow(rx.NoSSRComponent, ReactFlowLib): ...


class Background(ReactFlowLib):
    tag = "Background"

    color: rx.Var[str]

    gap: rx.Var[int]

    size: rx.Var[int]

    variant: rx.Var[str]


class Controls(ReactFlowLib):
    tag = "Controls"


react_flow = ReactFlow.create
background = Background.create
controls = Controls.create
```

## Building the App

Now that we have our components, let's build the app.

Let's start by defining the initial nodes and edges that we will use in our app.

```python
import reflex as rx
from .react_flow import react_flow, background, controls
import random
from collections import defaultdict
from typing import Any


initial_nodes = [
    {
        "id": "1",
        "type": "input",
        "data": {"label": "150"},
        "position": {"x": 250, "y": 25},
    },
    {
        "id": "2",
        "data": {"label": "25"},
        "position": {"x": 100, "y": 125},
    },
    {
        "id": "3",
        "type": "output",
        "data": {"label": "5"},
        "position": {"x": 250, "y": 250},
    },
]

initial_edges = [
    {"id": "e1-2", "source": "1", "target": "2", "label": "*", "animated": True},
    {"id": "e2-3", "source": "2", "target": "3", "label": "+", "animated": True},
]
```

Next we will define the state of our app. We have four event handlers: `add_random_node`, `clear_graph`, `on_connect` and `on_nodes_change`.

The `on_nodes_change` event handler receives the **diff** React Flow computed (a list of change dicts), not the whole graph — while a node is dragged, it fires roughly once per animation frame with `position` changes. We apply the position updates to our state.

```python
class State(rx.State):
    """The app state."""

    nodes: list[dict[str, Any]] = initial_nodes
    edges: list[dict[str, Any]] = initial_edges

    @rx.event
    def add_random_node(self):
        new_node_id = f"{len(self.nodes) + 1}"
        node_type = random.choice(["default"])
        # Label is random number
        label = new_node_id
        x = random.randint(0, 500)
        y = random.randint(0, 500)

        new_node = {
            "id": new_node_id,
            "type": node_type,
            "data": {"label": label},
            "position": {"x": x, "y": y},
            "draggable": True,
        }
        self.nodes.append(new_node)

    @rx.event
    def clear_graph(self):
        self.nodes = []  # Clear the nodes list
        self.edges = []  # Clear the edges list

    @rx.event
    def on_connect(self, new_edge):
        # Iterate over the existing edges
        for i, edge in enumerate(self.edges):
            # If we find an edge with the same ID as the new edge
            if edge["id"] == f"e{new_edge['source']}-{new_edge['target']}":
                # Delete the existing edge
                del self.edges[i]
                break

        # Add the new edge
        self.edges.append({
            "id": f"e{new_edge['source']}-{new_edge['target']}",
            "source": new_edge["source"],
            "target": new_edge["target"],
            "label": random.choice(["+", "-", "*", "/"]),
            "animated": True,
        })

    @rx.event
    def on_nodes_change(self, node_changes: list[dict[str, Any]]):
        # Receives a list of changes, e.g. positions while dragging.
        map_id_to_new_position = defaultdict(dict)

        # Loop over the changes and store the new position
        for change in node_changes:
            if change["type"] == "position" and change.get("dragging") == True:
                map_id_to_new_position[change["id"]] = change["position"]

        # Loop over the nodes and update the position
        for i, node in enumerate(self.nodes):
            if node["id"] in map_id_to_new_position:
                new_position = map_id_to_new_position[node["id"]]
                self.nodes[i]["position"] = new_position
```

Now let's define the UI of our app. We will use the `react_flow` component and pass in the `nodes` and `edges` from our state. We will also add the `on_connect` event handler to handle when an edge is connected.

Because the drag stream fires per animation frame, wiring it directly would send dozens of events per second over the websocket and make dragging feel laggy. We throttle it with an [event action](/docs/events/event-actions/): `State.on_nodes_change.throttle(50)` delivers at most one event every 50ms.

```python
def index() -> rx.Component:
    return rx.vstack(
        react_flow(
            background(),
            controls(),
            nodes_draggable=True,
            nodes_connectable=True,
            on_connect=State.on_connect,
            # Throttle the per-frame drag stream to at most one event per 50ms.
            on_nodes_change=State.on_nodes_change.throttle(50),
            nodes=State.nodes,
            edges=State.edges,
            fit_view=True,
        ),
        rx.hstack(
            rx.button("Clear graph", on_click=State.clear_graph, width="100%"),
            rx.button("Add node", on_click=State.add_random_node, width="100%"),
            width="100%",
        ),
        height="30em",
        width="100%",
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
```

```python exec
import reflex as rx
from typing import Any
from collections import defaultdict
import random


class ReactFlowLib(rx.Component):
    """Shared base for components from @xyflow/react."""

    library = "@xyflow/react@12.11.1"

    def add_imports(self):
        return {"": ["@xyflow/react/dist/style.css"]}


def connection_spec(
    connection: rx.Var[dict[str, Any]],
) -> tuple[rx.Var[dict[str, Any]]]:
    return (connection,)


def changes_spec(
    changes: rx.Var[list[dict[str, Any]]],
) -> tuple[rx.Var[list[dict[str, Any]]]]:
    return (changes,)


class ReactFlow(rx.NoSSRComponent, ReactFlowLib):
    tag = "ReactFlow"

    nodes: rx.Var[list[dict[str, Any]]]

    edges: rx.Var[list[dict[str, Any]]]

    fit_view: rx.Var[bool]

    nodes_draggable: rx.Var[bool]

    nodes_connectable: rx.Var[bool]

    on_nodes_change: rx.EventHandler[changes_spec]

    on_connect: rx.EventHandler[connection_spec]


class Background(ReactFlowLib):
    tag = "Background"

    color: rx.Var[str]

    gap: rx.Var[int]

    size: rx.Var[int]

    variant: rx.Var[str]


class Controls(ReactFlowLib):
    tag = "Controls"


react_flow = ReactFlow.create
background = Background.create
controls = Controls.create

initial_nodes = [
    {
        "id": "1",
        "type": "input",
        "data": {"label": "150"},
        "position": {"x": 250, "y": 25},
    },
    {
        "id": "2",
        "data": {"label": "25"},
        "position": {"x": 100, "y": 125},
    },
    {
        "id": "3",
        "type": "output",
        "data": {"label": "5"},
        "position": {"x": 250, "y": 250},
    },
]

initial_edges = [
    {"id": "e1-2", "source": "1", "target": "2", "label": "*", "animated": True},
    {"id": "e2-3", "source": "2", "target": "3", "label": "+", "animated": True},
]


class ReactFlowState(rx.State):
    """The app state."""

    nodes: list[dict[str, Any]] = initial_nodes
    edges: list[dict[str, Any]] = initial_edges

    @rx.event
    def add_random_node(self):
        new_node_id = f"{len(self.nodes) + 1}"
        node_type = random.choice(["default"])
        # Label is random number
        label = new_node_id
        x = random.randint(0, 250)
        y = random.randint(0, 250)

        new_node = {
            "id": new_node_id,
            "type": node_type,
            "data": {"label": label},
            "position": {"x": x, "y": y},
            "draggable": True,
        }
        self.nodes.append(new_node)

    @rx.event
    def clear_graph(self):
        self.nodes = []  # Clear the nodes list
        self.edges = []  # Clear the edges list

    @rx.event
    def on_connect(self, new_edge):
        # Iterate over the existing edges
        for i, edge in enumerate(self.edges):
            # If we find an edge with the same ID as the new edge
            if edge["id"] == f"e{new_edge['source']}-{new_edge['target']}":
                # Delete the existing edge
                del self.edges[i]
                break

        # Add the new edge
        self.edges.append({
            "id": f"e{new_edge['source']}-{new_edge['target']}",
            "source": new_edge["source"],
            "target": new_edge["target"],
            "label": random.choice(["+", "-", "*", "/"]),
            "animated": True,
        })

    @rx.event
    def on_nodes_change(self, node_changes: list[dict[str, Any]]):
        # Receives a list of changes, e.g. positions while dragging.
        map_id_to_new_position = defaultdict(dict)

        # Loop over the changes and store the new position
        for change in node_changes:
            if change["type"] == "position" and change.get("dragging") == True:
                map_id_to_new_position[change["id"]] = change["position"]

        # Loop over the nodes and update the position
        for i, node in enumerate(self.nodes):
            if node["id"] in map_id_to_new_position:
                new_position = map_id_to_new_position[node["id"]]
                self.nodes[i]["position"] = new_position
```

Here is an example of the app running:

```python eval
rx.vstack(
    react_flow(
        background(),
        controls(),
        nodes_draggable=True,
        nodes_connectable=True,
        on_connect=ReactFlowState.on_connect,
        on_nodes_change=ReactFlowState.on_nodes_change.throttle(50),
        nodes=ReactFlowState.nodes,
        edges=ReactFlowState.edges,
        fit_view=True,
    ),
    rx.hstack(
        rx.button("Clear graph", on_click=ReactFlowState.clear_graph, width="50%"),
        rx.button("Add node", on_click=ReactFlowState.add_random_node, width="50%"),
        width="100%",
    ),
    height="30em",
    width="100%",
)
```

For a production-quality wrap of an interactive library like this one — including custom node types, connection validation, and calling the library's imperative API from event handlers — see the patterns in [common pitfalls](/docs/wrapping-react/common-pitfalls/).

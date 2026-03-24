```python exec
import reflex as rx
from typing import Any
```

# Complex Example

In this more complex example we will be wrapping `reactflow` a library for building node based applications like flow charts, diagrams, graphs, etc.

## Import

Lets start by importing the library [reactflow](https://www.npmjs.com/package/reactflow). Lets make a separate file called `reactflow.py` and add the following code:

```python
import reflex as rx
from typing import Any, Dict, List, Union

class ReactFlowLib(rx.Component):
    """A component that wraps a react flow lib."""

    library = "reactflow"

    def _get_custom_code(self) -> str:
        return """import 'reactflow/dist/style.css';
        """
```

Notice we also use the `_get_custom_code` method to import the css file that is needed for the styling of the library.

## Components

For this tutorial we will wrap three components from Reactflow: `ReactFlow`, `Background`, and `Controls`. Lets start with the `ReactFlow` component.

Here we will define the `tag` and the `vars` that we will need to use the component.

For this tutorial we will define `EventHandler` props `on_nodes_change` and `on_connect`, but you can find all the events that the component triggers in the [reactflow docs](https://reactflow.dev/docs/api/react-flow-props/#onnodeschange).

```python
import reflex as rx
from typing import Any, Dict, List, Union

class ReactFlowLib(rx.Component):
    ...

class ReactFlow(ReactFlowLib):

    tag = "ReactFlow"

    nodes: rx.Var[List[Dict[str, Any]]]

    edges: rx.Var[List[Dict[str, Any]]]

    fit_view: rx.Var[bool]

    nodes_draggable: rx.Var[bool]

    nodes_connectable: rx.Var[bool]

    nodes_focusable: rx.Var[bool]

    on_nodes_change: rx.EventHandler[lambda e0: [e0]]

    on_connect: rx.EventHandler[lambda e0: [e0]]
```

Now lets add the `Background` and `Controls` components. We will also create the components using the `create` method so that we can use them in our app.

```python
import reflex as rx
from typing import Any, Dict, List, Union

class ReactFlowLib(rx.Component):
    ...

class ReactFlow(ReactFlowLib):
    ...

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

Now that we have our components lets build the app.

Lets start by defining the initial nodes and edges that we will use in our app.

```python
import reflex as rx
from .react_flow import react_flow, background, controls
import random
from collections import defaultdict
from typing import Any, Dict, List


initial_nodes = [
    \{
        'id': '1',
        'type': 'input',
        'data': \{'label': '150'},
        'position': \{'x': 250, 'y': 25},
    },
    \{
        'id': '2',
        'data': \{'label': '25'},
        'position': \{'x': 100, 'y': 125},
    },
    \{
        'id': '3',
        'type': 'output',
        'data': \{'label': '5'},
        'position': \{'x': 250, 'y': 250},
    },
]

initial_edges = [
    \{'id': 'e1-2', 'source': '1', 'target': '2', 'label': '*', 'animated': True},
    \{'id': 'e2-3', 'source': '2', 'target': '3', 'label': '+', 'animated': True},
]
```

Next we will define the state of our app. We have four event handlers: `add_random_node`, `clear_graph`, `on_connect` and `on_nodes_change`.

The `on_nodes_change` event handler is triggered when a node is selected and dragged. This function is used to update the position of a node during dragging. It takes a single argument `node_changes`, which is a list of dictionaries containing various types of metadata. For updating positions, the function specifically processes changes of type `position`.

```python
class State(rx.State):
    """The app state."""
    nodes: List[Dict[str, Any]] = initial_nodes
    edges: List[Dict[str, Any]] = initial_edges

    @rx.event
    def add_random_node(self):
        new_node_id = f'\{len(self.nodes) + 1\}'
        node_type = random.choice(['default'])
        # Label is random number
        label = new_node_id
        x = random.randint(0, 500)
        y = random.randint(0, 500)

        new_node = {
            'id': new_node_id,
            'type': node_type,
            'data': \{'label': label},
            'position': \{'x': x, 'y': y},
            'draggable': True,
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
            if edge["id"] == f"e\{new_edge['source']}-\{new_edge['target']}":
                # Delete the existing edge
                del self.edges[i]
                break

        # Add the new edge
        self.edges.append({
            "id": f"e\{new_edge['source']}-\{new_edge['target']}",
            "source": new_edge["source"],
            "target": new_edge["target"],
            "label": random.choice(["+", "-", "*", "/"]),
            "animated": True,
        })

    @rx.event
    def on_nodes_change(self, node_changes: List[Dict[str, Any]]):
        # Receives a list of Nodes in case of events like dragging
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

Now lets define the UI of our app. We will use the `react_flow` component and pass in the `nodes` and `edges` from our state. We will also add the `on_connect` event handler to the `react_flow` component to handle when an edge is connected.

```python
def index() -> rx.Component:
    return rx.vstack(
        react_flow(
            background(),
            controls(),
            nodes_draggable=True,
            nodes_connectable=True,
            on_connect=lambda e0: State.on_connect(e0),
            on_nodes_change=lambda e0: State.on_nodes_change(e0),
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
from typing import Any, Dict, List, Union
from collections import defaultdict
import random

class ReactFlowLib(rx.Component):
    """A component that wraps a react flow lib."""

    library = "reactflow"

    def _get_custom_code(self) -> str:
        return """import 'reactflow/dist/style.css';
        """

class ReactFlow(ReactFlowLib):

    tag = "ReactFlow"

    nodes: rx.Var[List[Dict[str, Any]]]

    edges: rx.Var[List[Dict[str, Any]]]

    fit_view: rx.Var[bool]

    nodes_draggable: rx.Var[bool]

    nodes_connectable: rx.Var[bool]

    nodes_focusable: rx.Var[bool]

    on_nodes_change: rx.EventHandler[lambda e0: [e0]]

    on_connect: rx.EventHandler[lambda e0: [e0]]


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
        'id': '1',
        'type': 'input',
        'data': {'label': '150'},
        'position': {'x': 250, 'y': 25},
    },
    {
        'id': '2',
        'data': {'label': '25'},
        'position': {'x': 100, 'y': 125},
    },
    {
        'id': '3',
        'type': 'output',
        'data': {'label': '5'},
        'position': {'x': 250, 'y': 250},
    },
]

initial_edges = [
    {'id': 'e1-2', 'source': '1', 'target': '2', 'label': '*', 'animated': True},
    {'id': 'e2-3', 'source': '2', 'target': '3', 'label': '+', 'animated': True},
]


class ReactFlowState(rx.State):
    """The app state."""
    nodes: List[Dict[str, Any]] = initial_nodes
    edges: List[Dict[str, Any]] = initial_edges

    @rx.event
    def add_random_node(self):
        new_node_id = f'{len(self.nodes) + 1}'
        node_type = random.choice(['default'])
        # Label is random number
        label = new_node_id
        x = random.randint(0, 250)
        y = random.randint(0, 250)

        new_node = {
            'id': new_node_id,
            'type': node_type,
            'data': {'label': label},
            'position': {'x': x, 'y': y},
            'draggable': True,
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
    def on_nodes_change(self, node_changes: List[Dict[str, Any]]):
        # Receives a list of Nodes in case of events like dragging
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
            on_connect=lambda e0: ReactFlowState.on_connect(e0),
            on_nodes_change=lambda e0: ReactFlowState.on_nodes_change(e0),
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

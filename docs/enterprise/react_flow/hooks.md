# Hooks (API)

The `rxe.flow.api` module provides hooks to interact with the Flow instance. These hooks are wrappers around the `useReactFlow` hook from React Flow.

## Node Hooks

- `get_nodes()`: Returns an array of all nodes in the flow.
- `set_nodes(nodes)`: Sets the nodes in the flow.
- `add_nodes(nodes)`: Adds nodes to the flow.
- `get_node(id)`: Returns a node by its ID.
- `update_node(id, node_update, replace=False)`: Updates a node in the flow.
- `update_node_data(id, data_update, replace=False)`: Updates a node's data in the flow.

## Edge Hooks

- `get_edges()`: Returns an array of all edges in the flow.
- `set_edges(edges)`: Sets the edges in the flow.
- `add_edges(edges)`: Adds edges to the flow.
- `get_edge(id)`: Returns an edge by its ID.
- `update_edge(id, edge_update, replace=False)`: Updates an edge in the flow.
- `update_edge_data(id, data_update, replace=False)`: Updates an edge's data in the flow.

## Viewport Hooks

- `screen_to_flow_position(x, y, snap_to_grid=False)`: Translates a screen pixel position to a flow position.
- `flow_to_screen_position(x, y)`: Translates a position inside the flow’s canvas to a screen pixel position.

## Other Hooks

- `to_object()`: Converts the React Flow state to a JSON object.
- `get_intersecting_nodes(node, partially=True, nodes=None)`: Find all the nodes currently intersecting with a given node or rectangle.
- `get_node_connections(id=None, handle_type=None, handle_id=None)`: This hook returns an array of connections on a specific node, handle type ("source", "target") or handle ID.
- `get_connection()`: Returns the current connection state when there is an active connection interaction.

# Utility Functions

The `rxe.flow.util` module provides utility functions for working with Flow components.

## Path Utilities

These functions are used to calculate the path for an edge.

- `get_simple_bezier_path(source_x, source_y, target_x, target_y, source_position="bottom", target_position="top")`: Returns everything you need to render a simple bezier edge between two nodes.
- `get_bezier_path(source_x, source_y, target_x, target_y, source_position="bottom", target_position="top", curvature=0.5)`: Returns everything you need to render a bezier edge between two nodes.
- `get_straight_path(source_x, source_y, target_x, target_y)`: Calculates the straight line path between two points.
- `get_smooth_step_path(source_x, source_y, target_x, target_y, source_position="bottom", target_position="top", border_radius=5, center_x=None, center_y=None, offset=20, step_position=0.5)`: Returns everything you need to render a stepped path between two nodes.

## Change Handlers

These functions are used to apply changes to nodes and edges from the `on_nodes_change` and `on_edges_change` event handlers.

- `apply_node_changes(nodes, changes)`: Applies changes to nodes in the flow.
- `apply_edge_changes(edges, changes)`: Applies changes to edges in the flow.

## Edge and Connection Utilities

- `add_edge(params, edges)`: Creates a new edge in the flow.

## Graph Utilities

- `get_incomers(node_id, nodes, edges)`: Returns all incoming nodes connected to the given node.
- `get_outgoers(node_id, nodes, edges)`: Returns all outgoing nodes connected to the given node.
- `get_connected_edges(nodes, edges)`: Returns all edges connected to the given nodes.

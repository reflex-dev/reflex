# Flow Components

This page documents the main components provided by the `rxe.flow` library.

## rxe.flow.provider

The `FlowProvider` component is a context provider that makes it possible to access a flow’s internal state outside of the `<ReactFlow />` component. Many of the hooks we provide rely on this component to work.

**Props:**

- `initial_nodes`: `Sequence[Node]` - These nodes are used to initialize the flow. They are not dynamic.
- `default_edges`: `Sequence[Edge]` - These edges are used to initialize the flow. They are not dynamic.
- `initial_width`: `float` - The initial width is necessary to be able to use fitView on the server.
- `initial_height`: `float` - The initial height is necessary to be able to use fitView on the server.
- `fit_view`: `bool` - When true, the flow will be zoomed and panned to fit all the nodes initially provided.
- `initial_fit_view_options`: `FitViewOptions` - You can provide an object of options to customize the initial fitView behavior.
- `initial_min_zoom`: `float` - Initial minimum zoom level.
- `initial_max_zoom`: `float` - Initial maximum zoom level.
- `node_origin`: `NodeOrigin` - The origin of the node to use when placing it in the flow or looking up its x and y position.
- `node_extent`: `CoordinateExtent` - The boundary a node can be moved in.

## rxe.flow

The `Flow` component is the main component that renders the flow. It takes in nodes and edges, and provides event handlers for user interactions.

**Props:**

- `nodes`: `Sequence[Node]` - An array of nodes to render in a controlled flow.
- `edges`: `Sequence[Edge]` - An array of edges to render in a controlled flow.
- `default_nodes`: `Sequence[Node]` - The initial nodes to render in an uncontrolled flow.
- `default_edges`: `Sequence[Edge]` - The initial edges to render in an uncontrolled flow.
- `node_types`: `Mapping[str, Any]` - Custom node types.
- `edge_types`: `Mapping[str, Any]` - Custom edge types.
- `on_nodes_change`: Event handler for when nodes change.
- `on_edges_change`: Event handler for when edges change.
- `on_connect`: Event handler for when a connection is made.
- `fit_view`: `bool` - When true, the flow will be zoomed and panned to fit all the nodes initially provided.
- `fit_view_options`: `FitViewOptions` - Options for `fit_view`.
- `style`: The style of the component.

## rxe.flow.background

The `Background` component renders a background for the flow. It can be a pattern of lines, dots, or a cross.

**Props:**

- `color`: `str` - Color of the pattern.
- `bg_color`: `str` - Color of the background.
- `variant`: `Literal["lines", "dots", "cross"]` - The type of pattern to render.
- `gap`: `float | tuple[float, float]` - The gap between patterns.
- `size`: `float` - The size of the pattern elements.

**Example:**

```python
rxe.flow.background(variant="dots", gap=20, size=1)
```

## rxe.flow.controls

The `Controls` component renders a panel with buttons to zoom in, zoom out, fit the view, and lock the viewport.

**Props:**

- `show_zoom`: `bool` - Whether to show the zoom buttons.
- `show_fit_view`: `bool` - Whether to show the fit view button.
- `show_interactive`: `bool` - Whether to show the lock button.
- `position`: `PanelPosition` - The position of the controls on the pane.

**Example:**

```python
rxe.flow.controls()
```

## rxe.flow.mini_map

The `MiniMap` component renders a small overview of your flow.

**Props:**

- `node_color`: `str | Any` - Color of nodes on minimap.
- `node_stroke_color`: `str | Any` - Stroke color of nodes on minimap.
- `pannable`: `bool` - Determines whether you can pan the viewport by dragging inside the minimap.
- `zoomable`: `bool` - Determines whether you can zoom the viewport by scrolling inside the minimap.
- `position`: `PanelPosition` - Position of minimap on pane.

**Example:**

```python
rxe.flow.mini_map(pannable=True, zoomable=True)
```

# Overview

At its core, a flow diagram is an interactive graph composed of nodes connected by edges. To help understand the key concepts, let’s go over the main components of a flow.

### Nodes

Nodes are the building blocks of a flow. While there are a few default node types available, the real power comes from customizing them. You can design nodes to include interactive elements, display dynamic data, or support multiple connection points. The framework provides the foundation—you provide the functionality and style.

### Handles

Handles are the points on a node where edges attach. They typically appear on the top, bottom, left, or right sides of a node, but can be positioned and styled freely. Nodes can have multiple handles, allowing for complex connection setups.

### Edges

Edges are the connections between nodes. Each edge requires a source node and a target node. Edges can be styled and customized, and nodes with multiple handles can support multiple edges. Custom edges can include interactive elements, specialized routing, or unique visual styles beyond simple lines.

### Connection Line

When creating a new edge, you can click and drag from one handle to another. While dragging, the placeholder edge is called a connection line. Connection lines behave like edges and can be customized in appearance and behavior.

### Viewport

The viewport is the visible area containing the flow. Each node has x- and y-coordinates representing its position. Moving the viewport changes these coordinates, and zooming in or out adjusts the zoom level. The viewport ensures the diagram remains navigable and interactive.

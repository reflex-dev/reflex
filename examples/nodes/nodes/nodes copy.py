"""Welcome to Reflex! This file outlines the steps to create a basic app."""
import reflex as rx
from .react_flow import react_flow, background, controls
import random
from typing import Any, Dict, List, Union
import json


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


class State(rx.State):
    """The app state."""
    nodes = initial_nodes
    edges: List[Dict[str, Any]] = initial_edges
    
    def add_node(self):
        new_node_id = f'{len(self.nodes) + 1}'
        node_type = random.choice(['default'])
        # Label is random number
        label = new_node_id
        x = random.randint(0, 500)
        y = random.randint(0, 500)

        new_node = {
            'id': new_node_id,
            'type': node_type,
            'data': {'label': label},
            'position': {'x': x, 'y': y},
            'draggable': True,
        }
        self.nodes.append(new_node)

    def add_edge(self):
        # Get a list of valid source and target node IDs
        valid_source_nodes = [node['id'] for node in self.nodes if node.get('type') in ['input', 'default']]
        valid_target_nodes = [node['id'] for node in self.nodes if node.get('type') in ['default', 'output']]

        # If there are no valid source nodes, add a default type node as the source
        if not valid_source_nodes:
            new_node_id = f'{len(self.nodes) + 1}'
            x = random.randint(0, 500)
            y = random.randint(0, 500)
            new_node = {
                'id': new_node_id,
                'type': 'default',
                'data': {'label': f'{random.randint(0, 100)}'},
                'position': {'x': x, 'y': y},
            }
            self.nodes.append(new_node)
            valid_source_nodes = [new_node_id]

        # If there are no valid target nodes, add a default type node as the target
        if not valid_target_nodes:
            new_node_id = f'{len(self.nodes) + 1}'
            x = random.randint(0, 500)
            y = random.randint(0, 500)
            new_node = {
                'id': new_node_id,
                'type': 'default',
                'data': {'label': f'{random.randint(0, 100)}'},
                'position': {'x': x, 'y': y},
            }
            self.nodes.append(new_node)
            valid_target_nodes = [new_node_id]

        # Select a random source and target node
        source_node_id = random.choice(valid_source_nodes)
        target_node_id = random.choice(valid_target_nodes)

        # Generate a unique edge ID (you can use a counter or some other method)
        edge_id = f'e{len(self.edges) + 1}'

        # Create the new edge
        new_edge = {
            'id': edge_id,
            'source': source_node_id,
            'target': target_node_id,
            'animated': True,  # You can set this as needed
        }

        self.edges.append(new_edge)

    def clear_graph(self):
        self.nodes = []  # Clear the nodes list
        self.edges = []  # Clear the edges list

    def on_edges_change(self, new_edge):
        found = False
        
        for edge in self.edges:
            if edge["id"] == f"e{new_edge['source']}-{new_edge['target']}":
                edge["animated"] = True
                found = True
                break
        if not found:
            self.edges.append({
                "id": f"e{new_edge['source']}-{new_edge['target']}",
                "source": new_edge["source"],
                "target": new_edge["target"],
                "label": random.choice(["+", "-", "*", "/"]),
                "animated": True,
            })
        

def index() -> rx.Component:
    return rx.vstack(
        react_flow(
            background(),
            controls(),
            nodes_draggable=True,
            nodes_connectable=True,
            on_connect=lambda e0: State.on_edges_change(e0),
            nodes=State.nodes,
            edges=State.edges,
            fit_view=True,
        ),
        rx.vstack(
            rx.hstack(
                rx.button(
                "Clear graph",
                on_click=State.clear_graph,
                width="100%",
                ),
                width="100%",
            ),
            rx.hstack(
                rx.button("Add node", on_click=State.add_node, width="100%"),
                rx.button("Add edge", on_click=State.add_edge, width="100%"),
                width="100%",
            ),
            width="100%",
        ),
        height="100vh",
        width="100vw",
    )


# Add state and page to the app.
app = rx.App()
app.add_page(index)
app.compile()

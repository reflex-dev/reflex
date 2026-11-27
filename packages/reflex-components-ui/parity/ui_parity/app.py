"""The app the harness drives, generated from the declarations.

A parity page shows every element of one component's matrix twice, the Radix
component beside the rx.ui one, each in a frame of a fixed size. A contract
page shows one component of one system and nothing else, so the keyboard meets
only what the contract declared.
"""

from __future__ import annotations

from typing import Any

import reflex as rx
from ui_parity.components import CONTRACTS, MATRICES
from ui_parity.contract import Contract
from ui_parity.matrix import Matrix
from ui_parity.systems import SYSTEMS, System

# The space between two frames and around the page, in CSS pixels. Whole
# pixels keep every frame on the pixel grid.
GAP = 8
# The space between a frame and its element, where an outline is drawn.
PADDING = 16


def parity_route(component: str) -> str:
    """Get the route of a component's parity page.

    Args:
        component: The name of the component.

    Returns:
        The route.
    """
    return f"/parity/{component}"


def contract_route(component: str, system: System) -> str:
    """Get the route of a component's contract page for one system.

    Args:
        component: The name of the component.
        system: The system the page renders the component of.

    Returns:
        The route.
    """
    return f"/contract/{component}/{system.slug}"


def stage_label(system: System, props_id: str) -> str:
    """Name a frame in the accessibility tree.

    Args:
        system: The system of the frame's element.
        props_id: The props id of the element.

    Returns:
        The accessible name of the frame.
    """
    return f"{system.role}:{props_id}"


def _stage(matrix: Matrix, system: System, props_id: str, props: Any) -> rx.Component:
    """Render one element of a matrix in its frame.

    Args:
        matrix: The matrix.
        system: The system to create the element from.
        props_id: The props id of the element.
        props: The props of the element.

    Returns:
        The frame.
    """
    width, height = matrix.stage
    return rx.el.div(
        matrix.create(system.namespace, props),
        # A group with a name splits the page's accessibility tree by frame.
        role="group",
        custom_attrs={
            "aria-label": stage_label(system, props_id),
            "data-parity-stage": props_id,
            "data-parity-system": system.role,
        },
        style={
            "width": f"{width}px",
            "height": f"{height}px",
            "padding": f"{PADDING}px",
            "box_sizing": "border-box",
            "overflow": "hidden",
            "position": "relative",
        },
    )


def parity_page(matrix: Matrix) -> rx.Component:
    """Render the parity page of a component.

    Args:
        matrix: The matrix of the component.

    Returns:
        The page: for each element, the reference frame then the candidate's.
    """
    return rx.el.main(
        *(
            _stage(matrix, system, props_id, props)
            for props_id, props in matrix.rendered().items()
            for system in SYSTEMS
        ),
        style={
            "display": "grid",
            "grid_template_columns": f"repeat(auto-fill, {matrix.stage[0]}px)",
            "gap": f"{GAP}px",
            "padding": f"{GAP}px",
        },
    )


def contract_page(contract: Contract, system: System) -> rx.Component:
    """Render the contract page of a component for one system.

    Args:
        contract: The contract of the component.
        system: The system to create the component from.

    Returns:
        The page.
    """
    return rx.el.main(
        contract.render(system.namespace),
        custom_attrs={"data-contract-root": system.name},
        style={"padding": f"{PADDING}px"},
    )


def _index() -> rx.Component:
    """Render the list of every page, for a person browsing the app.

    Returns:
        The page.
    """
    routes = [
        *(parity_route(component) for component in MATRICES),
        *(
            contract_route(component, system)
            for component in CONTRACTS
            for system in SYSTEMS
        ),
    ]
    return rx.el.main(
        rx.el.ul(*(rx.el.li(rx.el.a(route, href=route)) for route in routes)),
        style={"padding": f"{PADDING}px"},
    )


def create_app() -> rx.App:
    """Build the app from every declared matrix and contract.

    Returns:
        The app.
    """
    app = rx.App()
    app.add_page(_index, route="/")
    for component, matrix in MATRICES.items():
        app.add_page(parity_page(matrix), route=parity_route(component))
    for component, contract in CONTRACTS.items():
        for system in SYSTEMS:
            app.add_page(
                contract_page(contract, system),
                route=contract_route(component, system),
            )
    return app

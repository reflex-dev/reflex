"""Enterprise lab app: map + dnd + flow combined with core reflex features.

Purpose (pre-release QA for reflex 0.9.11a1 + reflex-enterprise 0.9.5):

* `/dnd`  - a NON-`@rxe.static` `can_drop` lambda whose return expression pulls
  an import from a `bundle_library()`-bundled package (the exact construct that
  crashed at component-construction time on reflex 0.9.9a1, previous campaign
  FINDING-022).  Driven end-to-end so the generated JS is exercised in the
  browser, not just constructed in Python.  A `@rxe.static` `can_drop` sits next
  to it as the control.  Combined with `rx.foreach`, `rx.cond`,
  `rx._x.client_state` and a `@rx.event(background=True)` handler.
* `/map`  - leaflet markers built with `rx.foreach` from a state list, popups
  driven by state, `rx.cond` layer toggle, and an `rx.ComponentState` counter.
* `/flow` - xyflow nodes/edges from a computed var, add/connect/delete through
  the `apply_node_changes` / `apply_edge_changes` round-trip.
"""

from typing import Any, Mapping

import reflex as rx
from reflex.components.dynamic import bundle_library
from reflex.utils.imports import ImportVar
from reflex_base.vars.base import Var, VarData

import reflex_enterprise as rxe
from reflex_enterprise.components.dnd.dnd import DropTargetMonitor
from reflex_enterprise.components.flow.types import Edge, Node
from reflex_enterprise.components.map.types import LatLng, latlng

# --------------------------------------------------------------------------
# dnd: the bundle_library() + non-static can_drop path (FINDING-022 surface)
# --------------------------------------------------------------------------

bundle_library("d3-format")  # import-time registration: silently reset by
# compile_app() -> reset_bundled_libraries() before any page is evaluated
# (see NOTES.md "bundle_library reset"), so it has to be repeated inside the
# page function below for the LambdaVar validator to see it.


class LabState(rx.State):
    """State for the dnd lab page."""

    # item id -> which bin it currently sits in (-1 == the tray)
    placement: dict[str, int] = {"cheap": -1, "pricey": -1}
    prices: dict[str, int] = {"cheap": 42, "pricey": 130000}
    drop_log: list[str] = []
    bg_ticks: int = 0

    @rx.event
    def record_drop(self, item_id: str, bin_index: int):
        """Record a drop and move the item."""
        self.placement[item_id] = bin_index
        self.drop_log = [*self.drop_log, f"{item_id}->{bin_index}"]

    @rx.event(background=True)
    async def bg_bump(self):
        """Background handler fired from the drop event chain."""
        async with self:
            self.bg_ticks += 1

    @rx.var
    def log_text(self) -> str:
        """Serialized drop log for the driver to assert on."""
        return ",".join(self.drop_log)


hover_count = rx._x.client_state("hover_count", default=0)


def _big_number_can_drop(
    item: rx.vars.ObjectVar[Mapping[str, Any]], monitor: DropTargetMonitor
):
    """Plain (NON-static) can_drop whose return expr carries a bundled import.

    `format(",")` comes from the d3-format package registered above with
    `bundle_library()`; LiteralLambdaVar._validate_and_extend_return_expr has to
    resolve it through the bundled-library list.  Accepts only items whose
    price formats to something with a thousands separator.
    """
    return Var(
        f'(format(",")({item.price}).indexOf(",") !== -1)',
        _var_data=VarData(imports={"d3-format": [ImportVar(tag="format")]}),
    ).to(bool)


@rxe.static
def _static_can_drop(
    item: rx.vars.ObjectVar[Mapping[str, Any]], monitor: DropTargetMonitor
):
    """Control: a @rxe.static can_drop (the path the shipped kanban demo uses)."""
    return item.price.to(int) < 1000


@rx.memo
def lab_chip(item_id: rx.Var[str], price: rx.Var[int]) -> rx.Component:
    """A draggable chip.

    Wrapped in @rx.memo because rxe.dnd.draggable emits a `useDrag` hook: a
    hook-bearing component used directly inside rx.foreach has its hook hoisted
    out of the map() closure and throws `ReferenceError: <loopvar> is not
    defined` in the browser (see NOTES.md, anomaly "hooks inside foreach").
    """
    return rxe.dnd.draggable(
        rx.card(
            rx.text(item_id, weight="bold"),
            rx.text("price ", price, size="1"),
            padding="6px",
        ),
        type="LabItem",
        item={"id": item_id, "price": price},
        border="1px solid #888",
        margin="4px",
    )


ITEMS = (("cheap", 42), ("pricey", 130000))


def _slot(item_id: str, price: int, index: int):
    return rx.cond(
        LabState.placement[item_id] == index,
        lab_chip(item_id=item_id, price=price),
        rx.fragment(),
    )


def _bin(index: int, label: str, can_drop_fn):
    params = rxe.dnd.DropTarget.collected_params
    return rxe.dnd.drop_target(
        rx.vstack(
            rx.text(label, weight="bold"),
            *[_slot(iid, price, index) for iid, price in ITEMS],
            spacing="1",
        ),
        accept=["LabItem"],
        can_drop=can_drop_fn,
        on_drop=lambda item: [
            LabState.record_drop(item.to(dict)["id"].to(str), index),
            LabState.bg_bump(),
            rx.toast(f"dropped into {label}"),
        ],
        on_hover=hover_count.set_value(hover_count.value + 1),
        id=f"bin-{index}",
        width="220px",
        min_height="150px",
        padding="8px",
        border="2px solid black",
        background_color=rx.cond(
            params.is_over,
            rx.cond(params.can_drop, "lightgreen", "salmon"),
            "white",
        ),
    )


@rx.page(route="/dnd", title="dnd lab")
def dnd_page() -> rx.Component:
    bundle_library("d3-format")  # must be re-registered at page-eval time
    return rx.vstack(
        hover_count,
        rx.heading("dnd lab"),
        rx.hstack(
            rx.box(
                rx.text("tray", weight="bold"),
                *[_slot(iid, price, -1) for iid, price in ITEMS],
                id="tray",
                width="220px",
                min_height="150px",
                border="2px dashed #666",
                padding="8px",
            ),
            _bin(0, "bundled (>=1000 only)", _big_number_can_drop),
            _bin(1, "static (<1000 only)", _static_can_drop),
            spacing="4",
        ),
        rx.text("log: ", LabState.log_text, id="log"),
        rx.text("bg_ticks: ", LabState.bg_ticks, id="bgticks"),
        rx.text("hovers: ", hover_count.value, id="hovers"),
        rx.link("map", href="/map"),
        rx.link("flow", href="/flow"),
        padding="1em",
    )


# --------------------------------------------------------------------------
# map: foreach markers + ComponentState + cond layer
# --------------------------------------------------------------------------


class MapState(rx.State):
    """State for the map lab page."""

    points: list[dict[str, Any]] = [
        {"name": "alpha", "lat": 51.505, "lng": -0.09},
        {"name": "beta", "lat": 51.515, "lng": -0.10},
        {"name": "gamma", "lat": 51.495, "lng": -0.08},
    ]
    show_circle: bool = True
    last_clicked: str = ""
    center: LatLng = latlng(lat=51.505, lng=-0.09)

    @rx.event
    def pick(self, name: str):
        """Record the marker the user clicked."""
        self.last_clicked = name

    @rx.event
    def toggle_circle(self):
        """Toggle the vector overlay."""
        self.show_circle = not self.show_circle

    @rx.event
    def add_point(self):
        """Append a marker; exercises foreach over a growing list."""
        n = len(self.points)
        self.points = [
            *self.points,
            {"name": f"extra{n}", "lat": 51.505 + 0.004 * n, "lng": -0.09 + 0.004 * n},
        ]


class Clicks(rx.ComponentState):
    """A tiny ComponentState living next to enterprise components."""

    n: int = 0

    @rx.event
    def bump(self):
        """Increment the per-instance counter."""
        self.n += 1

    @classmethod
    def get_component(cls, **props):
        """Render the counter button.

        Args:
            props: extra props forwarded to the button.

        Returns:
            The button component.
        """
        return rx.button(
            "clicks: ", cls.n, on_click=cls.bump, id=props.pop("id", "clicks"), **props
        )


@rx.page(route="/map", title="map lab")
def map_page() -> rx.Component:
    map_id = "lab-map"
    api = rxe.map.api(map_id)
    return rx.vstack(
        rx.heading("map lab"),
        rx.hstack(
            rx.button("add point", on_click=MapState.add_point, id="addpoint"),
            rx.button("toggle circle", on_click=MapState.toggle_circle, id="togglecircle"),
            rx.button("recenter", on_click=api.fly_to(MapState.center, 13), id="recenter"),
            Clicks.create(),
        ),
        rx.text("clicked: ", MapState.last_clicked, id="clicked"),
        rxe.map(
            rxe.map.tile_layer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
            rx.foreach(
                MapState.points,
                lambda pt: rxe.map.marker(
                    rxe.map.tooltip(pt["name"].to(str)),
                    rxe.map.popup(
                        rx.button(
                            "pick ",
                            pt["name"].to(str),
                            on_click=MapState.pick(pt["name"].to(str)),
                        )
                    ),
                    position=latlng(lat=pt["lat"].to(float), lng=pt["lng"].to(float)),
                ),
            ),
            rx.cond(
                MapState.show_circle,
                rxe.map.circle(
                    center=latlng(lat=51.505, lng=-0.09),
                    radius=400,
                    path_options=rxe.map.path_options(color="#c00", fill_opacity=0.3),
                ),
                rx.fragment(),
            ),
            id=map_id,
            center=MapState.center,
            zoom=13,
            width="100%",
            height="50vh",
        ),
        rx.link("dnd", href="/dnd"),
        rx.link("flow", href="/flow"),
        padding="1em",
        width="100%",
    )


# --------------------------------------------------------------------------
# flow: computed nodes/edges + add/connect/delete round-trip
# --------------------------------------------------------------------------


class FlowState(rx.State):
    """State for the flow lab page."""

    raw_nodes: list[Node] = [
        {"id": "n1", "position": {"x": 0, "y": 0}, "data": {"label": "one"}},
        {"id": "n2", "position": {"x": 220, "y": 90}, "data": {"label": "two"}},
    ]
    edges: list[Edge] = []

    @rx.var
    def nodes(self) -> list[Node]:
        """Computed nodes (exercises a computed var feeding an enterprise prop)."""
        return self.raw_nodes

    @rx.var
    def counts(self) -> str:
        """Node/edge counts for the driver to assert on."""
        return f"{len(self.raw_nodes)}/{len(self.edges)}"

    @rx.event
    def set_nodes(self, nodes: list[Node]):
        """Apply node changes coming back from xyflow."""
        self.raw_nodes = nodes

    @rx.event
    def set_edges(self, edges: list[Edge]):
        """Apply edge changes coming back from xyflow."""
        self.edges = edges

    @rx.event
    def add_node(self):
        """Add a node from the backend."""
        n = len(self.raw_nodes) + 1
        self.raw_nodes = [
            *self.raw_nodes,
            {
                "id": f"n{n}",
                "position": {"x": 60 * n, "y": 40 * n},
                "data": {"label": f"node {n}"},
            },
        ]


@rx.page(route="/flow", title="flow lab")
def flow_page() -> rx.Component:
    return rx.vstack(
        rx.heading("flow lab"),
        rx.hstack(
            rx.button("add node", on_click=FlowState.add_node, id="addnode"),
            rx.text("counts: ", FlowState.counts, id="counts"),
        ),
        rx.box(
            rxe.flow(
                rxe.flow.background(),
                rxe.flow.controls(),
                nodes=FlowState.nodes,
                edges=FlowState.edges,
                on_nodes_change=lambda changes: FlowState.set_nodes(
                    rxe.flow.util.apply_node_changes(FlowState.nodes, changes)
                ),
                on_edges_change=lambda changes: FlowState.set_edges(
                    rxe.flow.util.apply_edge_changes(FlowState.edges, changes)
                ),
                on_connect=lambda conn: FlowState.set_edges(
                    rxe.flow.util.add_edge(conn, FlowState.edges)
                ),
                fit_view=True,
            ),
            width="100%",
            height="60vh",
            border="1px solid #999",
        ),
        rx.link("dnd", href="/dnd"),
        rx.link("map", href="/map"),
        padding="1em",
        width="100%",
    )


@rx.page(route="/", title="ent lab")
def index() -> rx.Component:
    return rx.vstack(
        rx.heading("enterprise lab"),
        rx.link("dnd", href="/dnd"),
        rx.link("map", href="/map"),
        rx.link("flow", href="/flow"),
        padding="1em",
    )


app = rxe.App()

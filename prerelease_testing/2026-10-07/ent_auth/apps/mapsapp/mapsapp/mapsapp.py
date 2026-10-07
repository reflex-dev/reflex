"""Enterprise maps: draggable marker -> State, layers control, geolocation, 200 markers updated by a background task."""

import asyncio
import importlib.metadata
import math
import random

import reflex_enterprise as rxe
from reflex_enterprise.components.map.controls import LayersControlBaseLayer, LayersControlOverlay
from reflex_enterprise.components.map.types import LatLng, latlng, locate_options

import reflex as rx
from reflex.vars.object import ObjectVar

print(f"MAPSAPP_PROVENANCE reflex={importlib.metadata.version('reflex')} rxe={importlib.metadata.version('reflex-enterprise')} file={rx.__file__}", flush=True)

CENTER = (51.505, -0.09)
N_MARKERS = 200
OSM = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
TOPO = "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"


def _ring(tick: int) -> list[dict]:
    """200 points on a ring around the center, rotated by `tick` degrees."""
    out = []
    for i in range(N_MARKERS):
        a = math.radians(i * 360 / N_MARKERS + tick)
        r = 0.02 + 0.004 * (i % 5)
        out.append({"id": i, "lat": round(CENTER[0] + r * math.sin(a), 6), "lng": round(CENTER[1] + r * 1.6 * math.cos(a), 6)})
    return out


def drag_end_spec(e: ObjectVar[dict]) -> tuple[rx.Var[dict]]:
    """dragend has no args spec in rxe (falls back to no-args); read the marker's latlng from the event target."""
    return (e.to(dict)["target"].to(dict)["_latlng"].to(dict),)


class MapState(rx.State):
    markers: list[dict] = _ring(0)
    tick: int = 0
    running: bool = False
    drag_count: int = 0
    drag_noarg_count: int = 0
    last_drag: str = ""
    drag_pos: LatLng = latlng(lat=CENTER[0], lng=CENTER[1])
    loc_error: str = ""
    loc_found: str = ""
    layer_adds: int = 0
    clicks: int = 0

    @rx.event
    def on_drag_end(self, pos: dict):
        self.drag_count += 1
        self.last_drag = f"{round(pos.get('lat', 0), 5)},{round(pos.get('lng', 0), 5)}"
        self.drag_pos = latlng(lat=pos["lat"], lng=pos["lng"])

    @rx.event
    def on_drag_end_noarg(self):
        self.drag_noarg_count += 1

    @rx.event(background=True)
    async def run_ticker(self, seconds: int = 10):
        async with self:
            if self.running:
                return
            self.running = True
        try:
            for _ in range(seconds):
                await asyncio.sleep(1)
                async with self:
                    self.tick += 1
                    self.markers = _ring(self.tick * 3)
        finally:
            async with self:
                self.running = False

    @rx.event
    def handle_loc_error(self, err: dict):
        self.loc_error = f"code={err.get('code')} msg={err.get('message')}"

    @rx.event
    def handle_loc_found(self, ll: dict):
        self.loc_found = f"{round(ll['lat'], 4)},{round(ll['lng'], 4)}"

    @rx.event
    def count_layer_add(self, _evt: dict):
        self.layer_adds += 1

    @rx.event
    def marker_click(self, _evt: dict):
        self.clicks += 1


def status() -> rx.Component:
    return rx.hstack(
        rx.text("tick=", MapState.tick, id="tick"),
        rx.text("running=", MapState.running.to_string(), id="running"),
        rx.text("n=", MapState.markers.length(), id="n-markers"),
        rx.text("drags=", MapState.drag_count, id="drag-count"),
        rx.text("noarg=", MapState.drag_noarg_count, id="drag-noarg-count"),
        rx.text(MapState.last_drag, id="last-drag"),
        rx.text("clicks=", MapState.clicks, id="clicks"),
        rx.link("markers", href="/", id="nav-markers"),
        rx.link("layers", href="/layers", id="nav-layers"),
        rx.link("geo", href="/geo", id="nav-geo"),
        wrap="wrap",
    )


@rx.page(route="/")
def index() -> rx.Component:
    return rx.vstack(
        status(),
        rx.button("start ticker", id="start", on_click=MapState.run_ticker(8)),
        rxe.map(
            rxe.map.tile_layer(url=OSM),
            rx.foreach(
                MapState.markers,
                lambda m: rxe.map.circle_marker(
                    center=latlng(lat=m["lat"].to(float), lng=m["lng"].to(float)),
                    radius=4,
                ),
            ),
            rxe.map.marker(
                position=MapState.drag_pos,
                draggable=True,
                custom_attrs={"title": "drag-me", "alt": "drag-me"},
                event_handlers={"dragend": rx.EventChain.create(value=MapState.on_drag_end, args_spec=drag_end_spec)},
                on_click=MapState.marker_click,
            ),
            rxe.map.marker(
                position=latlng(lat=CENTER[0] + 0.01, lng=CENTER[1] - 0.03),
                draggable=True,
                custom_attrs={"title": "drag-noarg", "alt": "drag-noarg"},
                event_handlers={"dragend": MapState.on_drag_end_noarg},
            ),
            id="markers-map",
            center=latlng(lat=CENTER[0], lng=CENTER[1]),
            zoom=12,
            width="900px",
            height="600px",
        ),
    )


@rx.page(route="/layers")
def layers() -> rx.Component:
    return rx.vstack(
        status(),
        rx.text("layer adds=", MapState.layer_adds, id="layer-adds"),
        rxe.map(
            rxe.map.layers_control(
                LayersControlBaseLayer.create(rxe.map.tile_layer(url=OSM), name="OSM", checked=True),
                LayersControlBaseLayer.create(rxe.map.tile_layer(url=TOPO), name="Topo"),
                LayersControlOverlay.create(
                    rxe.map.circle(center=latlng(lat=CENTER[0], lng=CENTER[1]), radius=1500,
                                   path_options=rxe.map.path_options(color="#ff0000", fill_color="#ff3333", fill_opacity=0.5)),
                    name="Circle", checked=True,
                ),
                LayersControlOverlay.create(rxe.map.marker(position=latlng(lat=CENTER[0], lng=CENTER[1]), custom_attrs={"title": "overlay-marker"}), name="Marker", checked=False),
                position="topright",
                collapsed=False,
            ),
            id="layers-map",
            center=latlng(lat=CENTER[0], lng=CENTER[1]),
            zoom=12,
            width="900px",
            height="500px",
            on_layeradd=MapState.count_layer_add,
        ),
    )


@rx.page(route="/geo")
def geo() -> rx.Component:
    api = rxe.map.api("geo-map")
    return rx.vstack(
        status(),
        rx.text(MapState.loc_error, id="loc-error"),
        rx.text(MapState.loc_found, id="loc-found"),
        rx.button("locate", id="locate", on_click=api.locate(locate_options(set_view=True, max_zoom=14, timeout=3000))),
        rxe.map(
            rxe.map.tile_layer(url=OSM),
            id="geo-map",
            center=latlng(lat=CENTER[0], lng=CENTER[1]),
            zoom=12,
            width="600px",
            height="400px",
            on_locationfound=MapState.handle_loc_found,
            on_locationerror=MapState.handle_loc_error,
        ),
    )


app = rxe.App()

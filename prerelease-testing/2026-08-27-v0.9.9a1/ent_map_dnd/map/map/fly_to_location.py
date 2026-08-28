"""Map demo showing how to fly to different locations."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.map.types import (
    LatLng,
    ZoomLevelsChangeEvent,
    latlng,
    locate_options,
)

from .common import demo


class FlyToLocationState(rx.State):
    """State class for the fly-to-location map demo."""

    # Define state variables
    zoom: float = 13
    center: LatLng = latlng(lat=51.505, lng=-0.09)
    location_found: LatLng | None = None
    zoom_levels_changed: bool = False

    @rx.event
    def handle_event(self, evt: dict):
        yield rx.toast(
            f"{evt['type']} {evt['latlng']}",
            position="top-center",
        )

    @rx.event
    def handle_zoom_levels_change(self, evt: ZoomLevelsChangeEvent):
        self.zoom_levels_changed = True
        yield rx.toast(
            f"Zoom levels changed! Min zoom: {evt['min_zoom']}, Max zoom: {evt['max_zoom']}",
            position="top-center",
            level="success",
        )

    @rx.event
    def handle_zoom(self, evt: dict):
        self.zoom = round(evt["target"]["zoom"], 4)

    @rx.event
    def handle_location_found(self, latlng_: LatLng):
        """Handle location found event."""
        self.location_found = latlng(lat=latlng_["lat"], lng=latlng_["lng"], nround=4)


pos = latlng(lat=51.505, lng=-0.09)


@demo(
    route="/fly-to-location",
    title="Fly to Location",
    description="Demonstrates flying to different map locations and using geolocation.",
)
def fly_to_location() -> rx.Component:
    map_id = "my-map-foo"
    my_api = rxe.map.api(map_id)
    return rx.vstack(
        rx.hstack(
            rx.heading("Map Demo with Events"),
            rx.text("Zoom: ", FlyToLocationState.zoom),
            rx.text("Located: ", FlyToLocationState.location_found),
        ),
        # Map container with tile layer
        rx.hstack(
            rx.button(
                "Locate",
                on_click=my_api.locate(
                    locate_options(
                        max_zoom=16,
                    )
                ),
            ),
            rx.button(
                "Locate and setView",
                on_click=my_api.locate(
                    locate_options(
                        set_view=True,
                    )
                ),
            ),
            rx.button(
                "Fly to Found Location",
                on_click=rx.cond(
                    FlyToLocationState.location_found,
                    my_api.fly_to(
                        FlyToLocationState.location_found, FlyToLocationState.zoom
                    ),
                    None,
                ),
            ),
            rx.button(
                "Fly to center",
                on_click=my_api.fly_to(
                    FlyToLocationState.center, FlyToLocationState.zoom
                ),
            ),
        ),
        rxe.map(
            # Base tile layer
            rxe.map.tile_layer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            ),
            rxe.map.marker(
                rxe.map.popup(
                    rx.button("Foo bar", on_click=rx.toast("foo bar from popup"))
                ),
                rxe.map.tooltip("Baz bum"),
                position=pos,
            ),
            rxe.map.marker(
                position=latlng(lat=51.515, lng=-0.1),
                draggable=True,
            ),
            id=map_id,
            zoom=FlyToLocationState.zoom,
            width="100%",
            center=FlyToLocationState.center,
            height="50vh",
            on_click=lambda e: my_api.set_view(
                e.latlng, FlyToLocationState.zoom, {"animate": True}
            ),
            on_zoom=FlyToLocationState.handle_zoom.debounce(100),
            on_locationfound=FlyToLocationState.handle_location_found,
            on_locationerror=rx.toast(
                "Failed to find location",
                description="Check your permissions.",
                level="error",
                position="top-center",
            ),
        ),
        width="100%",
        padding="1em",
    )

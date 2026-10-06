"""Map demo showcasing different map controls."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.map.types import latlng

from .common import demo


class ControlsState(rx.State):
    """State class for the map controls demo."""

    pass


@demo(
    route="/map-controls",
    title="Map Controls",
    description="Demonstrates different map controls including zoom, scale, attribution, and layers.",
)
def map_controls() -> rx.Component:
    # Create coordinates for map center
    london = latlng(lat=51.505, lng=-0.09)
    map_id = "map-controls-demo"

    return rx.vstack(
        rx.heading("Map Controls Demo"),
        rx.text("This map demonstrates different controls available in Leaflet."),
        rxe.map(
            # Basic tile layer
            rxe.map.tile_layer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            ),
            # Layers control (commented out as it doesn't work as expected yet)
            # rxe.map.layers_control(
            #     position="topright",
            #     collapsed=False,
            # ),
            # Note: The following code is commented out as it doesn't work as expected yet
            # LayersControl with BaseLayer and Overlay will be implemented in a future update
            # rxe.map.layers_control(
            #     rxe.map.layers_control_base_layer(
            #         rxe.map.tile_layer(
            #             url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            #         ),
            #         name="OpenStreetMap",
            #         checked=True,
            #     ),
            #     rxe.map.layers_control_base_layer(
            #         rxe.map.tile_layer(
            #             url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            #         ),
            #         name="Satellite",
            #     ),
            #     # Overlay layers
            #     rxe.map.layers_control_overlay(
            #         rxe.map.circle(
            #             center=london,
            #             radius=1000,  # 1000 meters
            #             path_options=rxe.map.path_options(
            #                 color="#ff0000",
            #                 fill_color="#ff3333",
            #                 fill_opacity=0.5,
            #             ),
            #         ),
            #         name="Circle (1km)",
            #         checked=True,
            #     ),
            #     rxe.map.layers_control_overlay(
            #         rxe.map.marker(
            #             rxe.map.tooltip("London"),
            #             position=london,
            #         ),
            #         name="Marker",
            #         checked=True,
            #     ),
            #     position="topright",
            #     collapsed=False,
            # ),
            # Add ZoomControl
            rxe.map.zoom_control(
                position="topright",
            ),
            # # Add ScaleControl
            rxe.map.scale_control(
                position="bottomleft",
            ),
            # # Add AttributionControl
            rxe.map.attribution_control(
                position="topleft",
            ),
            # Map settings
            id=map_id,
            zoom=13,
            center=london,
            zoom_control=False,  # Disable default zoom control
            attribution_control=False,  # Disable default attribution control
            width="100%",
            height="50vh",
        ),
        rx.vstack(
            rx.text("Available Controls:"),
            rx.unordered_list(
                rx.list_item("Zoom Control - Located at topright (default is topleft)"),
                rx.list_item("Scale Control - Located at bottom-left (default is off)"),
                rx.list_item(
                    "Attribution Control - Located at topleft (default is bottom-right)"
                ),
                # rx.list_item(
                #     rx.text(
                #         "Layers Control - Located at top-right (base layer and overlay functionality coming soon)"
                #     )
                # ),
            ),
            align_items="flex-start",
            spacing="2",
            width="100%",
        ),
        width="100%",
        padding="1em",
    )

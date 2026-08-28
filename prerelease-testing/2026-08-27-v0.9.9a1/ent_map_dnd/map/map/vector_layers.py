"""Map demo showcasing vector layers."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.map.types import LatLng, latlng, latlng_bounds

from .common import demo


class VectorLayersState(rx.State):
    """State class for the vector layers map demo."""

    # Define state variables
    zoom: float = 13
    center: LatLng = latlng(lat=51.505, lng=-0.09)


@demo(
    route="/vector-layers",
    title="Vector Layers",
    description="Demonstrates different vector layers like circles, polygons, polylines, and rectangles.",
)
def vector_layers() -> rx.Component:
    # Create coordinates for our vector layers
    center = latlng(lat=51.505, lng=-0.09)
    map_id = "vector-layers-demo"

    # Create polygon coordinates
    polygon_points = [
        latlng(lat=51.51, lng=-0.1),
        latlng(lat=51.51, lng=-0.08),
        latlng(lat=51.5, lng=-0.07),
        latlng(lat=51.49, lng=-0.08),
        latlng(lat=51.49, lng=-0.1),
    ]

    # Create polyline coordinates
    polyline_points = [
        latlng(lat=51.52, lng=-0.12),
        latlng(lat=51.53, lng=-0.11),
        latlng(lat=51.51, lng=-0.06),
        latlng(lat=51.52, lng=-0.05),
    ]

    # Create rectangle bounds
    rect_bounds = latlng_bounds(
        corner1_lat=51.49,  # Southwest corner
        corner1_lng=-0.13,
        corner2_lat=51.51,  # Northeast corner
        corner2_lng=-0.11,
    )

    # Create path options for styling
    circle_options = rxe.map.path_options(
        color="#ff0000",
        fill_color="#ff3333",
        fill_opacity=0.5,
    )

    polygon_options = rxe.map.path_options(
        color="#0033ff",
        fill_color="#3366ff",
        fill_opacity=0.4,
        weight=2,
    )

    polyline_options = rxe.map.path_options(
        color="#166516FF",
        weight=5,
        opacity=0.7,
        line_cap="round",
        dash_array="5,10",
    )

    rectangle_options = rxe.map.path_options(
        color="#ff9900",
        fill_color="#ffcc00",
        fill_opacity=0.3,
        weight=3,
    )

    return rx.vstack(
        rx.heading("Vector Layers Demo"),
        rx.text("This map demonstrates different vector layers available in Leaflet."),
        rx.button(
            "Get Bounds",
            on_click=rxe.map.api(map_id).get_bounds(
                callback=rx.console_log,
            ),
        ),
        rxe.map(
            # Base tile layer
            rxe.map.tile_layer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            ),
            # Add Circle
            rxe.map.circle(
                center=center,
                radius=500,  # 500 meters
                path_options=circle_options,
            ),
            # Add CircleMarker (radius in pixels)
            rxe.map.circle_marker(
                rxe.map.tooltip("Circle Marker A"),
                center=latlng(lat=51.515, lng=-0.09),
                radius=15,  # 15 pixels
                path_options=circle_options,
            ),
            # Add Polygon
            rxe.map.polygon(
                positions=polygon_points,
                path_options=polygon_options,
            ),
            # Add Polyline
            rxe.map.polyline(
                positions=polyline_points,
                path_options=polyline_options,
            ),
            # Add Rectangle
            rxe.map.rectangle(
                bounds=rect_bounds,
                path_options=rectangle_options,
            ),
            # Add markers to help with orientation
            rxe.map.marker(
                rxe.map.tooltip("Center point"),
                position=latlng(lat=51.505, lng=-0.09),
            ),
            # Map settings
            id=map_id,
            zoom=VectorLayersState.zoom,
            center=VectorLayersState.center,
            width="100%",
            height="50vh",
        ),
        rx.text(
            "The map shows: a red circle (500m radius), a red circle marker (15px), a blue polygon, "
            "a green dashed polyline, and an orange rectangle."
        ),
        width="100%",
        padding="1em",
    )

---
title: Interactive Maps
---

# Interactive Maps

```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

The map components in Reflex Enterprise provide interactive mapping capabilities built on top of **Leaflet**, one of the most popular open-source JavaScript mapping libraries. These components enable you to create rich, interactive maps with markers, layers, controls, and event handling.

```md alert info
# All map components are built using Leaflet and react-leaflet, providing a familiar and powerful mapping experience.
For advanced Leaflet features, refer to the [Leaflet documentation](https://leafletjs.com/reference.html).
```

🌍 **[View Live Demo](https://map.reflex.run)** - See the map components in action with interactive examples.

## Installation & Setup

Map components are included with `reflex-enterprise`. No additional installation is required.

## Basic Usage

Here's a simple example of creating a map with a marker:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class MapState(rx.State):
    center: rxe.map.LatLng = rxe.map.latlng(lat=51.505, lng=-0.09)
    zoom: float = 13.0

def basic_map():
    return rxe.map(
        rxe.map.tile_layer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        ),
        rxe.map.marker(
            rxe.map.popup("Hello from London!"),
            position=MapState.center,
        ),
        id="basic-map",
        center=MapState.center,
        zoom=MapState.zoom,
        height="400px",
        width="100%",
    )
```

## Core Components

### Map Container

The `rxe.map()` component is the primary container that holds all other map elements:

```python
rxe.map(
    # Child components (markers, layers, controls)
    id="my-map",
    center=rxe.map.latlng(lat=51.505, lng=-0.09),
    zoom=13,
    height="400px",
    width="100%"
)
```

**Key Properties:**
- `center`: Initial map center coordinates
- `zoom`: Initial zoom level (0-18+ depending on tile provider)
- `bounds`: Alternative to center/zoom, fits map to bounds
- `height`/`width`: Map container dimensions

### Tile Layers

Tile layers provide the base map imagery. The most common is OpenStreetMap:

```python
rxe.map.tile_layer(
    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution='&copy; OpenStreetMap contributors'
)
```


### Markers

Add point markers to specific locations:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def markers_example():
    return rxe.map(
        rxe.map.tile_layer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution='&copy; OpenStreetMap contributors'
        ),
        rxe.map.marker(
            rxe.map.popup(
                rx.vstack(
                    rx.text("Big Ben", weight="bold"),
                    rx.text("Famous clock tower in London"),
                    spacing="2"
                )
            ),
            position=rxe.map.latlng(lat=51.4994, lng=-0.1245),
        ),
        rxe.map.marker(
            rxe.map.popup("London Eye"),
            position=rxe.map.latlng(lat=51.5033, lng=-0.1196),
        ),
        id="markers-map",
        center=rxe.map.latlng(lat=51.501, lng=-0.122),
        zoom=14,
        height="400px",
        width="100%",
    )
```

### Vector Layers

Draw shapes and areas on the map:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def vectors_example():
    return rxe.map(
        rxe.map.tile_layer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution='&copy; OpenStreetMap contributors'
        ),
        # Circle (radius in meters)
        rxe.map.circle(
            center=rxe.map.latlng(lat=51.505, lng=-0.09),
            radius=500,
            path_options=rxe.map.path_options(
                color="#ff0000",
                fill_color="#ff3333",
                fill_opacity=0.3,
                weight=2
            )
        ),
        # Polygon
        rxe.map.polygon(
            positions=[
                rxe.map.latlng(lat=51.515, lng=-0.08),
                rxe.map.latlng(lat=51.515, lng=-0.07),
                rxe.map.latlng(lat=51.520, lng=-0.07),
                rxe.map.latlng(lat=51.520, lng=-0.08),
            ],
            path_options=rxe.map.path_options(
                color="#0000ff",
                fill_color="#3333ff",
                fill_opacity=0.3
            )
        ),
        # Polyline
        rxe.map.polyline(
            positions=[
                rxe.map.latlng(lat=51.500, lng=-0.095),
                rxe.map.latlng(lat=51.510, lng=-0.085),
                rxe.map.latlng(lat=51.515, lng=-0.095),
            ],
            path_options=rxe.map.path_options(
                color="#00ff00",
                weight=4
            )
        ),
        id="vectors-map",
        center=rxe.map.latlng(lat=51.510, lng=-0.08),
        zoom=13,
        height="400px",
        width="100%",
    )
```

## Interactive Features

### Event Handling

Maps support comprehensive event handling for user interactions:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class InteractiveMapState(rx.State):
    last_click: str = "No clicks yet"
    current_zoom: float = 13.0

    def handle_map_click(self, event):
        lat = event.get("latlng", {}).get("lat", 0)
        lng = event.get("latlng", {}).get("lng", 0)
        self.last_click = f"Clicked at: {lat:.4f}, {lng:.4f}"

    def handle_zoom_change(self, event):
        self.current_zoom = float(event.get("target", {}).get("_zoom", 13.0))

def interactive_example():
    return rx.vstack(
        rx.text(f"Last click: {InteractiveMapState.last_click}"),
        rx.text(f"Current zoom: {InteractiveMapState.current_zoom}"),
        rxe.map(
            rxe.map.tile_layer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                attribution='&copy; OpenStreetMap contributors'
            ),
            id="interactive-map",
            center=rxe.map.latlng(lat=51.505, lng=-0.09),
            zoom=InteractiveMapState.current_zoom,
            height="350px",
            width="100%",
            on_click=InteractiveMapState.handle_map_click,
            on_zoom=InteractiveMapState.handle_zoom_change,
        ),
        spacing="3"
    )
```

### Map Controls

Add UI controls for enhanced user interaction:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def controls_example():
    return rxe.map(
        rxe.map.tile_layer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution='&copy; OpenStreetMap contributors'
        ),
        rxe.map.zoom_control(position="topright"),
        rxe.map.scale_control(position="bottomleft"),
        rxe.map.attribution_control(position="bottomright"),
        id="controls-map",
        center=rxe.map.latlng(lat=51.505, lng=-0.09),
        zoom=13,
        height="400px",
        width="100%",
    )
```

## Helper Functions

### Coordinate Creation

```python
# Create latitude/longitude coordinates
center = rxe.map.latlng(lat=51.505, lng=-0.09, nround=4)

# Create bounds
bounds = rxe.map.latlng_bounds(
    corner1_lat=51.49, corner1_lng=-0.11,
    corner2_lat=51.52, corner2_lng=-0.07
)
```

## Map API

The Map API provides programmatic control over your maps, allowing you to manipulate the map programmatically from your Reflex state methods.

### Getting the API Reference

To access the Map API, you need to get a reference to your map using its ID:

```python
map_api = rxe.map.api("my-map-id")
```

### Interactive Demo

Here are some commonly used API methods demonstrated in action:

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

map_api = rxe.map.api("api-demo-map")

class MapAPIState(rx.State):
    current_location: str = "London"

    def fly_to_london(self):
        yield map_api.fly_to([51.505, -0.09], 13)
        self.current_location = "London"

    def fly_to_paris(self):
        yield map_api.fly_to([48.8566, 2.3522], 13)
        self.current_location = "Paris"

def map_api_example():
    return rx.vstack(
        rx.text(f"Current location: {MapAPIState.current_location}"),
        rx.hstack(
            rx.button("Fly to London", on_click=MapAPIState.fly_to_london),
            rx.button("Fly to Paris", on_click=MapAPIState.fly_to_paris),
            rx.button("Zoom Out", on_click=map_api.set_zoom(8)),
            rx.button("Log Center", on_click=map_api.get_center(callback=rx.console_log)),
            spacing="2"
        ),
        rxe.map(
            rxe.map.tile_layer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                attribution='&copy; OpenStreetMap contributors'
            ),
            id="api-demo-map",
            center=rxe.map.latlng(lat=51.505, lng=-0.09),
            zoom=13.0,
            height="350px",
            width="100%",
        ),
        spacing="3"
    )
```

### Common API Methods

**View Control:**
- `fly_to(latlng, zoom, options)` - Smooth animated movement to location
- `set_view(latlng, zoom, options)` - Instant movement to location
- `set_zoom(zoom)` - Change zoom level
- `zoom_in()` / `zoom_out()` - Zoom by one level
- `fit_bounds(bounds, options)` - Fit map to specific bounds

**Location Services:**
- `locate(options)` - Get user's current location
- `stop_locate()` - Stop location tracking

**Information Retrieval:**
- `get_center(callback)` - Get current map center
- `get_zoom(callback)` - Get current zoom level
- `get_bounds(callback)` - Get current map bounds
- `get_size(callback)` - Get map container size

**Layer Management:**
- `add_layer(layer)` - Add a layer to the map
- `remove_layer(layer)` - Remove a layer from the map
- `has_layer(layer)` - Check if layer exists on map

### Full Leaflet API Access

```md alert info
# The Map API provides access to the complete Leaflet map API. Any method available on a Leaflet map instance can be called through the MapAPI instance.
Function names are automatically converted from snake_case (Python) to camelCase (JavaScript).
```

This means you can use any method from the [Leaflet Map documentation](https://leafletjs.com/reference.html#map). For example:

**Python (snake_case) → JavaScript (camelCase):**
- `map_api.pan_to(latlng)` → `map.panTo(latlng)`
- `map_api.set_max_bounds(bounds)` → `map.setMaxBounds(bounds)`
- `map_api.get_pixel_bounds()` → `map.getPixelBounds()`
- `map_api.container_point_to_lat_lng(point)` → `map.containerPointToLatLng(point)`

### Advanced Example

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class AdvancedMapState(rx.State):
    constraints_applied: bool = False
    location_tracking: bool = False
    location_status: str = "Location tracking disabled"

    def set_location_status(self, status: str):
        self.location_status = status

    def setup_map_constraints(self):
        map_api = rxe.map.api("advanced-demo-map")

        # Set maximum bounds (restrict panning to London area)
        max_bounds = rxe.map.latlng_bounds(
            corner1_lat=51.4, corner1_lng=-0.3,
            corner2_lat=51.6, corner2_lng=0.1
        )
        yield map_api.set_max_bounds(max_bounds)

        # Set min/max zoom levels
        yield map_api.set_min_zoom(10)
        yield map_api.set_max_zoom(16)

        # Disable scroll wheel zoom
        yield map_api.scroll_wheel_zoom(False)

        self.constraints_applied = True

    def remove_constraints(self):
        map_api = rxe.map.api("advanced-demo-map")

        # Remove bounds restriction
        yield map_api.set_max_bounds(None)

        # Reset zoom limits
        yield map_api.set_min_zoom(1)
        yield map_api.set_max_zoom(18)

        # Re-enable scroll wheel zoom
        yield map_api.scroll_wheel_zoom(True)

        self.constraints_applied = False

    def toggle_location_tracking(self):
        map_api = rxe.map.api("advanced-demo-map")

        if self.location_tracking == False:
            # Start location tracking
            locate_options = rxe.map.locate_options(
                set_view=True,
                max_zoom=16,
                timeout=10000,
                enable_high_accuracy=True,
                watch=False  # Single location request
            )
            yield map_api.locate(locate_options)
            self.location_tracking = True
            self.location_status = "Requesting location..."
        else:
            # Stop location tracking
            yield map_api.stop_locate()
            self.location_tracking = False
            self.location_status = "Location tracking disabled"

def advanced_example():
    return rx.vstack(
        rx.hstack(
            rx.button(
                rx.cond(AdvancedMapState.constraints_applied, "Remove Constraints", "Apply Constraints"),
                on_click=rx.cond(AdvancedMapState.constraints_applied, AdvancedMapState.remove_constraints, AdvancedMapState.setup_map_constraints),
                color_scheme="blue"
            ),
            rx.button(
                rx.cond(AdvancedMapState.location_tracking, "Disable Location", "Enable Location"),
                on_click=AdvancedMapState.toggle_location_tracking,
                color_scheme="green"
            ),
            spacing="3"
        ),
        rx.text(f"Status: {AdvancedMapState.location_status}"),
        rx.text(
            rx.cond(
                AdvancedMapState.constraints_applied,
                "Constraints: Applied (restricted to London area, zoom 10-16, no scroll wheel)",
                "Constraints: None"
            )
        ),
        rxe.map(
            rxe.map.tile_layer(
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
                attribution='&copy; OpenStreetMap contributors'
            ),
            rxe.map.marker(
                rxe.map.popup("Try panning and zooming when constraints are applied!"),
                position=rxe.map.latlng(lat=51.505, lng=-0.09),
            ),
            id="advanced-demo-map",
            center=rxe.map.latlng(lat=51.505, lng=-0.09),
            zoom=12.0,
            height="400px",
            width="100%",
            on_locationfound=lambda e: AdvancedMapState.set_location_status("Location found!"),
            on_locationerror=lambda e: AdvancedMapState.set_location_status("Location error - permission denied or unavailable"),
        ),
        spacing="3"
    )
```

### Callback Handling

Many API methods that retrieve information require callbacks to handle the results:

```python
class CallbackMapState(rx.State):
    map_info: str = ""

    def handle_center_result(self, result):
        lat = result.get("lat", 0)
        lng = result.get("lng", 0)
        self.map_info = f"Center: {lat:.4f}, {lng:.4f}"

    def handle_bounds_result(self, result):
        # result will contain bounds information
        self.map_info = f"Bounds: {result}"

    def get_map_info(self):
        map_api = rxe.map.api("info-map")
        yield map_api.get_center(self.handle_center_result)
        # or
        yield map_api.get_bounds(self.handle_bounds_result)
```

## Available Events

The map components support a comprehensive set of events:

**Map Events:**
- `on_click`, `on_dblclick` - Mouse click events
- `on_zoom`, `on_zoom_start`, `on_zoom_end` - Zoom events
- `on_move`, `on_move_start`, `on_move_end` - Pan events
- `on_resize` - Map container resize
- `on_load`, `on_unload` - Map lifecycle

**Location Events:**
- `on_locationfound`, `on_locationerror` - Geolocation

**Layer Events:**
- `on_layeradd`, `on_layerremove` - Layer management

**Popup Events:**
- `on_popupopen`, `on_popupclose` - Popup lifecycle
- `on_tooltipopen`, `on_tooltipclose` - Tooltip lifecycle

## Common Patterns

### Dynamic Markers

```python
class DynamicMapState(rx.State):
    markers: list[dict] = [
        {"lat": 51.505, "lng": -0.09, "title": "London"},
        {"lat": 48.8566, "lng": 2.3522, "title": "Paris"},
        {"lat": 52.5200, "lng": 13.4050, "title": "Berlin"},
    ]

def dynamic_markers():
    return rxe.map(
        rxe.map.tile_layer(url="..."),
        rx.foreach(
            DynamicMapState.markers,
            lambda marker: rxe.map.marker(
                rxe.map.popup(marker["title"]),
                position=rxe.map.latlng(
                    lat=marker["lat"],
                    lng=marker["lng"]
                )
            )
        ),
        # ... map configuration
    )
```


## Best Practices

1. **Always include attribution** for tile providers
2. **Set reasonable zoom levels** (typically 1-18)
3. **Use bounds for multiple markers** instead of arbitrary center/zoom
4. **Handle loading states** for dynamic map content
5. **Optimize marker rendering** for large datasets using clustering
6. **Test on mobile devices** for touch interactions

---

[← Back to main documentation]({enterprise.overview.path})

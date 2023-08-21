from typing import Dict, List, Tuple
import reflex as rx
from reflex.style import Style

attribution: str = "&copy; \
            <a href='https://www.openstreetmap.org'>OpenStreetMap</a> \
            contributors"
tileset_url: str = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"


class LeafletLib(rx.Component):
    """Base class for all leaflet components."""

    def _get_imports(self):
        return {}

    @classmethod
    def create(cls, *children, **props):
        custom_style = props.pop("style", {})

        # Transfer style props to the custom style prop.
        for key, value in props.items():
            if key not in cls.get_fields():
                custom_style[key] = value

        # Create the component.
        return super().create(
            *children,
            **props,
            custom_style=Style(custom_style),
        )

    def _add_style(self, style):
        self.custom_style = (  # pylint: disable=attribute-defined-outside-init
            self.custom_style or {}
        )
        self.custom_style.update(style)  # type: ignore

    def _render(self):
        out = super()._render()
        return out.add_props(style=self.custom_style).remove_props(
            "custom_style"
        )


class MapContainer(LeafletLib):
    """The map container."""

    library = "react-leaflet"
    tag = "MapContainer"

    center: rx.Var[list[float]]
    zoom: rx.Var[int]
    scroll_wheel_zoom: rx.Var[bool]

    def _get_custom_code(self) -> str:
        return """import "leaflet/dist/leaflet.css";
        import dynamic from 'next/dynamic'
        const MapContainer = dynamic(() =>
        import('react-leaflet').then((mod) => mod.MapContainer),
        { ssr: false });
        """


class TileLayer(LeafletLib):
    """The tile layer."""

    library = "react-leaflet"
    tag = "TileLayer"

    def _get_custom_code(self) -> str:
        return """const TileLayer = dynamic(() =>
        import('react-leaflet').then((mod) => mod.TileLayer),
        { ssr: false });"""

    attribution: rx.Var[str]
    url: rx.Var[str]


class UseMap(LeafletLib):
    """The useMap hook."""

    library = "react-leaflet"
    tag = "useMap"


class Marker(LeafletLib):
    """The marker."""

    library = "react-leaflet"
    tag = "Marker"

    def _get_custom_code(self) -> str:
        return """const Marker = dynamic(() =>
        import('react-leaflet').then((mod) => mod.Marker), { ssr: false });"""

    position: rx.Var[list[float]]


class Popup(LeafletLib):
    """The popup."""

    library = "react-leaflet"
    tag = "Popup"

    def _get_custom_code(self) -> str:
        return """const Popup = dynamic(() =>
        import('react-leaflet').then((mod) => mod.Popup), { ssr: false });"""


class LayersControl(LeafletLib):
    """The layers control."""

    library = "react-leaflet"
    tag = "LayersControl"

    baseLayers: rx.Var[dict]
    attributions: rx.Var[dict]

    def _get_custom_code(self) -> str:
        return """
        const LayersControl = dynamic(() => {
          return Promise.all([
            import('leaflet'),
            import('react-leaflet'),
          ]).then(([L, RL]) => {
            const { useMap } = RL;
            const LayersControlComponent = (props) => {
              const map = useMap();

              useEffect(() => {
                if (typeof window !== 'undefined') {
                  if (!map._layersControl) {
                    const baseLayers = Object.entries(props.baseLayers)
                    .reduce((result, [name, url]) => {
                      const layer = L.tileLayer(url,
                      { attribution: props.attributions[name] });

                      // Add the initial layer to the map
                      if (name === 'OpenStreetMap') {
                        layer.addTo(map);
                      }

                      result[name] = layer;
                      return result;
                    }, {});

                    const layersControl = L.control.layers(baseLayers)
                    .addTo(map);
                    map._layersControl = layersControl;
                  }
                }
              }, [map]);

              return null;
            };

            return LayersControlComponent;
          });
        }, { ssr: false });

        export { LayersControl };
        """


layers_control = LayersControl.create
map_container = MapContainer.create
tile_layer = TileLayer.create
use_map = UseMap.create
marker = Marker.create
popup = Popup.create


class Devices:
    def __init__(self):
        self._items = {
            "123456789012345": ("Device A", "Info A"),
            "223456789012345": ("Device B", "Info B"),
        }

    def items(self) -> List[Tuple[str, Tuple[str, str]]]:
        return list(self._items.items())


class GPSModule:
    def __init__(self):
        self.devices = Devices()


class GPSElement:
    def __init__(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude


gps_element = GPSElement("40.730610", "-73.935242")
gps_element2 = GPSElement("38.89511", "-77.03637")
gps_module = GPSModule()


class State(rx.State):
    """The app state."""

    device_names: List[str] = [
        name for imei, (name, _) in gps_module.devices.items()
    ]
    device_font_weights: Dict[str, str] = {
        name: "bold" if index == 0 else "normal"  # Bold the first device
        for index, name in enumerate(device_names)
    }

    def toggle_device_font_weight(self, device_name: str):
        """Toggle the font weight of a device button."""
        new_weight = (
            "normal"
            if self.device_font_weights[device_name] == "bold"
            else "bold"
        )
        self.device_font_weights = {
            **self.device_font_weights,
            device_name: new_weight,
        }


def render_device_button(device_name: str):
    """
    Render device list buttons.

    :param device_name: The name of the device.
    :return: A button representing the device.
    """
    return rx.button(
        device_name,
        style={"fontWeight": State.device_font_weights[device_name]},
        on_click=(lambda: State.toggle_device_font_weight(device_name)),
    )


def render_active_device_marker(device_name: str):
    """
    Render active device markers.

    :param device_name: The name of the device.
    :return: A marker representing the device.
    """
    # print("-----------------------------------------")
    # print("Rendering active device marker")
    # print(f"device name: {device_name}")
    gps = None
    if device_name == "Device A":
        print("Errm device A")
        gps = gps_element
    elif device_name == "Device B":
        print("ERRM device B")
        gps = gps_element2
    # print(f"gps is : {gps} - device font weight : {State.device_font_weights[device_name]}")
    if gps and State.device_font_weights[device_name] == "bold":
        # return rx.text(
        #     "THis ia a very very loooooooong gtriiiign",
        #     color="red",
        #     font_size="4xl"
        # )
        print(f"OKay Got here: gps: {gps_element2}")
        return marker(
            popup(
                rx.hstack(
                    rx.span("Device: ", font_weight="bold"),
                    rx.span(device_name, font_size="4xl"),
                ),
                rx.hstack(
                    rx.span("Latitude: ", font_weight="bold"),
                    rx.span(str(gps.latitude)),
                ),
                rx.hstack(
                    rx.span("Longitude: ", font_weight="bold"),
                    rx.span(str(gps.longitude)),
                ),
            ),
            position=[
                gps.latitude,
                gps.longitude,
            ],
        )
    return None  # Return None if the device is not active


def index() -> rx.Component:
    """The index page, rendering the main UI"""
    return rx.flex(
        rx.vstack(
            rx.text("Devices", font_weight="bold"),
            rx.foreach(State.device_names, render_device_button),
        ),
        map_container(
            tile_layer(
                attribution="",  # attribution is handled by layers control
                url="",  # url is handled by layers control
            ),
            rx.foreach(State.device_names, render_active_device_marker),
            layers_control(
                baseLayers={
                    "OpenStreetMap": tileset_url,
                },
                attributions={
                    "OpenStreetMap": attribution,
                },
            ),
            center=[gps_element.latitude, gps_element.longitude],
            zoom=12,
            scroll_wheel_zoom=True,
            height="100vh",
            width="100%",
        ),
    )


# Add state and page to the app.
app = rx.App(state=State)
app.add_page(index)
app.compile()

"""Media classes."""

from typing import Any, Literal

from reflex import Component, ComponentNamespace
from reflex.components.el.elements.inline import ReferrerPolicy
from reflex.constants.colors import Color
from reflex.vars.base import Var

from .base import BaseHTML


class Area(BaseHTML):
    """Display the area element."""

    tag = "area"

    # Alternate text for the area, used for accessibility
    alt: Var[str]

    # Coordinates to define the shape of the area
    coords: Var[str]

    # Specifies that the target will be downloaded when clicked
    download: Var[str | bool]

    # Hyperlink reference for the area
    href: Var[str]

    # Language of the linked resource
    href_lang: Var[str]

    # Specifies what media/device the linked resource is optimized for
    media: Var[str]

    # Specifies which referrer information to send with the link
    referrer_policy: Var[ReferrerPolicy]

    # Specifies the relationship of the target object to the link object
    rel: Var[str]

    # Defines the shape of the area (rectangle, circle, polygon)
    shape: Var[str]

    # Specifies where to open the linked document
    target: Var[str]


CrossOrigin = Literal["anonymous", "use-credentials", ""]


class Audio(BaseHTML):
    """Display the audio element."""

    tag = "audio"

    # Specifies that the audio will start playing as soon as it is ready
    auto_play: Var[bool]

    # Displays the standard audio controls
    controls: Var[bool]

    # Configures the CORS requests for the element
    cross_origin: Var[CrossOrigin]

    # Specifies that the audio will loop
    loop: Var[bool]

    # Indicates whether the audio is muted by default
    muted: Var[bool]

    # Specifies how the audio file should be preloaded
    preload: Var[str]

    # URL of the audio to play
    src: Var[str]


ImageDecoding = Literal["async", "auto", "sync"]
ImageLoading = Literal["eager", "lazy"]


class Img(BaseHTML):
    """Display the img element."""

    tag = "img"

    # Alternative text for the image
    alt: Var[str]

    # Configures the CORS requests for the image
    cross_origin: Var[CrossOrigin]

    # How the image should be decoded
    decoding: Var[ImageDecoding]

    # Specifies the loading behavior of the image
    loading: Var[ImageLoading]

    # Referrer policy for the image
    referrer_policy: Var[ReferrerPolicy]

    # Sizes of the image for different layouts
    sizes: Var[str]

    # URL of the image to display
    src: Var[Any]

    # A set of source sizes and URLs for responsive images
    src_set: Var[str]

    # The name of the map to use with the image
    use_map: Var[str]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Override create method to apply source attribute to value if user fails to pass in attribute.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        return (
            super().create(src=children[0], **props)
            if children
            else super().create(*children, **props)
        )


class Map(BaseHTML):
    """Display the map element."""

    tag = "map"

    # Name of the map, referenced by the 'usemap' attribute in 'img' and 'object' elements
    name: Var[str]


class Track(BaseHTML):
    """Display the track element."""

    tag = "track"

    # Indicates that the track should be enabled unless the user's preferences indicate otherwise
    default: Var[bool]

    # Specifies the kind of text track
    kind: Var[str]

    # Title of the text track, used by the browser when listing available text tracks
    label: Var[str]

    # URL of the track file
    src: Var[str]

    # Language of the track text data
    src_lang: Var[str]


class Video(BaseHTML):
    """Display the video element."""

    tag = "video"

    # Specifies that the video will start playing as soon as it is ready
    auto_play: Var[bool]

    # Displays the standard video controls
    controls: Var[bool]

    # Configures the CORS requests for the video
    cross_origin: Var[CrossOrigin]

    # Specifies that the video will loop
    loop: Var[bool]

    # Indicates whether the video is muted by default
    muted: Var[bool]

    # Indicates that the video should play 'inline', inside its element's playback area
    plays_inline: Var[bool]

    # URL of an image to show while the video is downloading, or until the user hits the play button
    poster: Var[str]

    # Specifies how the video file should be preloaded
    preload: Var[str]

    # URL of the video to play
    src: Var[str]


class Embed(BaseHTML):
    """Display the embed element."""

    tag = "embed"

    # URL of the embedded content
    src: Var[str]

    # Media type of the embedded content
    type: Var[str]


class Iframe(BaseHTML):
    """Display the iframe element."""

    tag = "iframe"

    # Permissions policy for the iframe
    allow: Var[str]

    # Specifies the loading behavior of the iframe
    loading: Var[Literal["eager", "lazy"]]

    # Name of the iframe, used as a target for hyperlinks and forms
    name: Var[str]

    # Referrer policy for the iframe
    referrer_policy: Var[ReferrerPolicy]

    # Security restrictions for the content in the iframe
    sandbox: Var[str]

    # URL of the document to display in the iframe
    src: Var[str]

    # HTML content to embed directly within the iframe
    src_doc: Var[str]


class Object(BaseHTML):
    """Display the object element."""

    tag = "object"

    # URL of the data to be used by the object
    data: Var[str]

    # Associates the object with a form element
    form: Var[str]

    # Name of the object, used for scripting or as a target for forms and links
    name: Var[str]

    # Media type of the data specified in the data attribute
    type: Var[str]

    # Name of an image map to use with the object
    use_map: Var[str]


class Picture(BaseHTML):
    """Display the picture element."""

    tag = "picture"


class Portal(BaseHTML):
    """Display the portal element."""

    tag = "portal"


class Source(BaseHTML):
    """Display the source element."""

    tag = "source"

    # Media query indicating what device the linked resource is optimized for
    media: Var[str]

    # Sizes of the source for different layouts
    sizes: Var[str]

    # URL of the media file or an image for the element to use
    src: Var[str]

    # A set of source sizes and URLs for responsive images
    src_set: Var[str]

    # Media type of the source
    type: Var[str]


class Svg(BaseHTML):
    """Display the svg element."""

    tag = "svg"
    # The width of the svg.
    width: Var[str | int]
    # The height of the svg.
    height: Var[str | int]
    # The XML namespace declaration.
    xmlns: Var[str]


class Text(BaseHTML):
    """The SVG text component."""

    tag = "text"
    # The x coordinate of the starting point of the text baseline.
    x: Var[str | int]
    # The y coordinate of the starting point of the text baseline.
    y: Var[str | int]
    # Shifts the text position horizontally from a previous text element.
    dx: Var[str | int]
    # Shifts the text position vertically from a previous text element.
    dy: Var[str | int]
    # Rotates orientation of each individual glyph.
    rotate: Var[str | int]
    # How the text is stretched or compressed to fit the width defined by the text_length attribute.
    length_adjust: Var[str]
    # A width that the text should be scaled to fit.
    text_length: Var[str | int]


class Line(BaseHTML):
    """The SVG line component."""

    tag = "line"
    # The x-axis coordinate of the line starting point.
    x1: Var[str | int]
    # The x-axis coordinate of the the line ending point.
    x2: Var[str | int]
    # The y-axis coordinate of the line starting point.
    y1: Var[str | int]
    # The y-axis coordinate of the the line ending point.
    y2: Var[str | int]
    # The total path length, in user units.
    path_length: Var[int]


class Circle(BaseHTML):
    """The SVG circle component."""

    tag = "circle"
    # The x-axis coordinate of the center of the circle.
    cx: Var[str | int]
    # The y-axis coordinate of the center of the circle.
    cy: Var[str | int]
    # The radius of the circle.
    r: Var[str | int]
    # The total length for the circle's circumference, in user units.
    path_length: Var[int]


class Ellipse(BaseHTML):
    """The SVG ellipse component."""

    tag = "ellipse"
    # The x position of the center of the ellipse.
    cx: Var[str | int]
    # The y position of the center of the ellipse.
    cy: Var[str | int]
    # The radius of the ellipse on the x axis.
    rx: Var[str | int]
    # The radius of the ellipse on the y axis.
    ry: Var[str | int]
    # The total length for the ellipse's circumference, in user units.
    path_length: Var[int]


class Rect(BaseHTML):
    """The SVG rect component."""

    tag = "rect"
    # The x coordinate of the rect.
    x: Var[str | int]
    # The y coordinate of the rect.
    y: Var[str | int]
    # The width of the rect
    width: Var[str | int]
    # The height of the rect.
    height: Var[str | int]
    # The horizontal corner radius of the rect. Defaults to ry if it is specified.
    rx: Var[str | int]
    # The vertical corner radius of the rect. Defaults to rx if it is specified.
    ry: Var[str | int]
    # The total length of the rectangle's perimeter, in user units.
    path_length: Var[int]


class Polygon(BaseHTML):
    """The SVG polygon component."""

    tag = "polygon"
    # defines the list of points (pairs of x,y absolute coordinates) required to draw the polygon.
    points: Var[str]
    # This prop lets specify the total length for the path, in user units.
    path_length: Var[int]


class Defs(BaseHTML):
    """Display the defs element."""

    tag = "defs"


class LinearGradient(BaseHTML):
    """Display the linearGradient element."""

    tag = "linearGradient"

    # Units for the gradient.
    gradient_units: Var[str | bool]

    # Transform applied to the gradient.
    gradient_transform: Var[str | bool]

    # Method used to spread the gradient.
    spread_method: Var[str | bool]

    # X coordinate of the starting point of the gradient.
    x1: Var[str | int | float]

    # X coordinate of the ending point of the gradient.
    x2: Var[str | int | float]

    # Y coordinate of the starting point of the gradient.
    y1: Var[str | int | float]

    # Y coordinate of the ending point of the gradient.
    y2: Var[str | int | float]


class RadialGradient(BaseHTML):
    """Display the radialGradient element."""

    tag = "radialGradient"

    # The x coordinate of the end circle of the radial gradient.
    cx: Var[str | int | float]

    # The y coordinate of the end circle of the radial gradient.
    cy: Var[str | int | float]

    # The radius of the start circle of the radial gradient.
    fr: Var[str | int | float]

    # The x coordinate of the start circle of the radial gradient.
    fx: Var[str | int | float]

    # The y coordinate of the start circle of the radial gradient.
    fy: Var[str | int | float]

    # Units for the gradient.
    gradient_units: Var[str | bool]

    # Transform applied to the gradient.
    gradient_transform: Var[str | bool]

    # The radius of the end circle of the radial gradient.
    r: Var[str | int | float]

    # Method used to spread the gradient.
    spread_method: Var[str | bool]


class Stop(BaseHTML):
    """Display the stop element."""

    tag = "stop"

    # Offset of the gradient stop.
    offset: Var[str | float | int]

    # Color of the gradient stop.
    stop_color: Var[str | Color | bool]

    # Opacity of the gradient stop.
    stop_opacity: Var[str | float | int | bool]


class Path(BaseHTML):
    """Display the path element."""

    tag = "path"

    # Defines the shape of the path.
    d: Var[str | int | float]


class G(BaseHTML):
    """The SVG g component, used to group other SVG elements."""

    tag = "g"

    # The fill color of the group.
    fill: Var[str | Color]

    # The fill opacity of the group.
    fill_opacity: Var[str | int | float]

    # The stroke color of the group.
    stroke: Var[str | Color]

    # The stroke opacity of the group.
    stroke_opacity: Var[str | int | float]

    # The stroke width of the group.
    stroke_width: Var[str | int | float]

    # The transform applied to the group.
    transform: Var[str]


class SVG(ComponentNamespace):
    """SVG component namespace."""

    text = staticmethod(Text.create)
    line = staticmethod(Line.create)
    circle = staticmethod(Circle.create)
    ellipse = staticmethod(Ellipse.create)
    rect = staticmethod(Rect.create)
    polygon = staticmethod(Polygon.create)
    path = staticmethod(Path.create)
    stop = staticmethod(Stop.create)
    linear_gradient = staticmethod(LinearGradient.create)
    radial_gradient = staticmethod(RadialGradient.create)
    defs = staticmethod(Defs.create)
    g = staticmethod(G.create)
    __call__ = staticmethod(Svg.create)


text = Text.create
line = Line.create
circle = Circle.create
ellipse = Ellipse.create
rect = Rect.create
polygon = Polygon.create
path = Path.create
stop = Stop.create
linear_gradient = LinearGradient.create
radial_gradient = RadialGradient.create
defs = Defs.create
g = G.create
area = Area.create
audio = Audio.create
image = img = Img.create
map = Map.create
track = Track.create
video = Video.create
embed = Embed.create
iframe = Iframe.create
object = Object.create
picture = Picture.create
portal = Portal.create
source = Source.create
svg = SVG()

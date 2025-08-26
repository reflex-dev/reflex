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
    # The viewBox attribute defines the position and dimension, in user space, of an SVG viewport.
    view_box: Var[str]
    # Controls how the SVG scales to fit its viewport.
    preserve_aspect_ratio: Var[str]
    # Defines a list of transform definitions that are applied to an element and the element's children.
    transform: Var[str]


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


class Polyline(BaseHTML):
    """The SVG polyline component."""

    tag = "polyline"
    # List of points (pairs of x,y coordinates) that define the polyline.
    points: Var[str]
    # The total path length, in user units.
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

    # Reference to another gradient to inherit from.
    href: Var[str]

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

    # Reference to another gradient to inherit from.
    href: Var[str]

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
    # The total path length, in user units.
    path_length: Var[int]


class Marker(BaseHTML):
    """Display the marker element."""

    tag = "marker"

    # The height of the marker viewport.
    marker_height: Var[str | int | float]

    # The width of the marker viewport.
    marker_width: Var[str | int | float]

    # The coordinate system for the marker attributes.
    marker_units: Var[str]

    # The orientation of the marker relative to the shape it is attached to.
    orient: Var[str | int | float]

    # How the svg fragment must be deformed if it is embedded in a container with a different aspect ratio.
    preserve_aspect_ratio: Var[str]

    # The x coordinate for the reference point of the marker.
    ref_x: Var[str | int | float]

    # The y coordinate for the reference point of the marker.
    ref_y: Var[str | int | float]

    # The bound of the SVG viewport for the current SVG fragment.
    view_box: Var[str]


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


class SvgImage(BaseHTML):
    """The SVG image component."""

    tag = "image"

    # URL of the image to display.
    href: Var[str]

    # X coordinate of the image.
    x: Var[str | int]

    # Y coordinate of the image.
    y: Var[str | int]

    # Width of the image.
    width: Var[str | int]

    # Height of the image.
    height: Var[str | int]

    # How the image should scale to fit its viewport.
    preserve_aspect_ratio: Var[str]

    # CORS settings for the image.
    crossorigin: Var[str]


class Use(BaseHTML):
    """The SVG use component for reusing defined elements."""

    tag = "use"

    # Reference to the element to reuse.
    href: Var[str]

    # X coordinate where the referenced element should be positioned.
    x: Var[str | int]

    # Y coordinate where the referenced element should be positioned.
    y: Var[str | int]

    # Width of the referenced element.
    width: Var[str | int]

    # Height of the referenced element.
    height: Var[str | int]


class TSpan(BaseHTML):
    """The SVG tspan component for text spans within text elements."""

    tag = "tspan"

    # X coordinate of the text.
    x: Var[str | int]

    # Y coordinate of the text.
    y: Var[str | int]

    # Horizontal offset from the previous text element.
    dx: Var[str | int]

    # Vertical offset from the previous text element.
    dy: Var[str | int]

    # Rotation of the text.
    rotate: Var[str | int]

    # How the text is stretched or compressed to fit the width defined by text_length.
    length_adjust: Var[str]

    # A width that the text should be scaled to fit.
    text_length: Var[str | int]


class TextPath(BaseHTML):
    """The SVG textPath component for text along a path."""

    tag = "textPath"

    # Reference to the path along which the text should be rendered.
    href: Var[str]

    # Inline path data.
    path: Var[str]

    # Distance along the path from its beginning to the initial position of the text.
    start_offset: Var[str | int]

    # Method for rendering text along the path.
    method: Var[str]

    # Spacing method for text.
    spacing: Var[str]

    # Which side of the path the text should be rendered on.
    side: Var[str]

    # How the text is stretched or compressed to fit the specified length.
    length_adjust: Var[str]

    # Target length for the text.
    text_length: Var[str | int]


class Pattern(BaseHTML):
    """The SVG pattern component for defining repeating patterns."""

    tag = "pattern"

    # X coordinate of the pattern.
    x: Var[str | int]

    # Y coordinate of the pattern.
    y: Var[str | int]

    # Width of the pattern.
    width: Var[str | int]

    # Height of the pattern.
    height: Var[str | int]

    # Units for the pattern coordinates.
    pattern_units: Var[str]

    # Units for the pattern content coordinates.
    pattern_content_units: Var[str]

    # Transform applied to the pattern.
    pattern_transform: Var[str]

    # ViewBox definition for the pattern.
    view_box: Var[str]

    # How the pattern should scale to fit its viewport.
    preserve_aspect_ratio: Var[str]

    # Reference to another pattern to inherit from.
    href: Var[str]


class ClipPath(BaseHTML):
    """The SVG clipPath component for defining clipping paths."""

    tag = "clipPath"

    # Units for the clipping path coordinates.
    clip_path_units: Var[str]


class Symbol(BaseHTML):
    """The SVG symbol component for defining reusable symbols."""

    tag = "symbol"

    # ViewBox definition for the symbol.
    view_box: Var[str]

    # How the symbol should scale to fit its viewport.
    preserve_aspect_ratio: Var[str]

    # Reference X coordinate.
    ref_x: Var[str | int]

    # Reference Y coordinate.
    ref_y: Var[str | int]


class Mask(BaseHTML):
    """The SVG mask component for defining masks."""

    tag = "mask"

    # X coordinate of the mask.
    x: Var[str | int]

    # Y coordinate of the mask.
    y: Var[str | int]

    # Width of the mask.
    width: Var[str | int]

    # Height of the mask.
    height: Var[str | int]

    # Units for the mask coordinates.
    mask_units: Var[str]

    # Units for the mask content coordinates.
    mask_content_units: Var[str]


class ForeignObject(BaseHTML):
    """The SVG foreignObject component for embedding foreign content."""

    tag = "foreignObject"

    # X coordinate of the foreign object.
    x: Var[str | int]

    # Y coordinate of the foreign object.
    y: Var[str | int]

    # Width of the foreign object.
    width: Var[str | int]

    # Height of the foreign object.
    height: Var[str | int]


class SvgA(BaseHTML):
    """The SVG anchor component for creating links."""

    tag = "a"

    # URL of the link.
    href: Var[str]

    # Where to open the linked resource.
    target: Var[str]

    # Download attribute for the link.
    download: Var[str]

    # Relationship between the current document and the linked resource.
    rel: Var[str]

    # Language of the linked resource.
    hreflang: Var[str]

    # MIME type of the linked resource.
    type: Var[str]

    # Referrer policy for the link.
    referrerpolicy: Var[str]


class Animate(BaseHTML):
    """The SVG animate component for animations."""

    tag = "animate"

    # Name of the attribute to animate.
    attribute_name: Var[str]

    # Starting value of the animation.
    from_: Var[str]

    # Ending value of the animation.
    to: Var[str]

    # Duration of the animation.
    dur: Var[str]

    # When the animation should begin.
    begin: Var[str]

    # When the animation should end.
    end: Var[str]

    # Number of times to repeat the animation.
    repeat_count: Var[str]

    # How values should be calculated during the animation.
    calc_mode: Var[str]

    # List of values for the animation.
    values: Var[str]

    # Key times for the animation values.
    key_times: Var[str]

    # Key splines for smooth transitions.
    key_splines: Var[str]

    # Whether animation values should accumulate.
    accumulate: Var[str]

    # Whether animation values should be additive.
    additive: Var[str]

    # Reference to the target element.
    href: Var[str]


class AnimateMotion(BaseHTML):
    """The SVG animateMotion component for motion animations."""

    tag = "animateMotion"

    # Path along which to animate.
    path: Var[str]

    # Duration of the animation.
    dur: Var[str]

    # When the animation should begin.
    begin: Var[str]

    # When the animation should end.
    end: Var[str]

    # Number of times to repeat the animation.
    repeat_count: Var[str]

    # Rotation behavior during motion.
    rotate: Var[str]

    # Key times for the motion.
    key_times: Var[str]

    # Key points along the path.
    key_points: Var[str]

    # Reference to the target element.
    href: Var[str]


class AnimateTransform(BaseHTML):
    """The SVG animateTransform component for transform animations."""

    tag = "animateTransform"

    # Name of the transform attribute to animate.
    attribute_name: Var[str]

    # Type of transformation.
    type: Var[str]

    # Starting value of the transformation.
    from_: Var[str]

    # Ending value of the transformation.
    to: Var[str]

    # Duration of the animation.
    dur: Var[str]

    # When the animation should begin.
    begin: Var[str]

    # When the animation should end.
    end: Var[str]

    # Number of times to repeat the animation.
    repeat_count: Var[str]

    # List of values for the transformation.
    values: Var[str]

    # Reference to the target element.
    href: Var[str]


class Set(BaseHTML):
    """The SVG set component for setting attribute values."""

    tag = "set"

    # Name of the attribute to set.
    attribute_name: Var[str]

    # Value to set the attribute to.
    to: Var[str]

    # When to set the attribute.
    begin: Var[str]

    # Duration for which to maintain the value.
    dur: Var[str]

    # When to end the setting.
    end: Var[str]

    # Reference to the target element.
    href: Var[str]


class MPath(BaseHTML):
    """The SVG mpath component for motion path references."""

    tag = "mpath"

    # Reference to a path element.
    href: Var[str]


class Desc(BaseHTML):
    """The SVG desc component for descriptions."""

    tag = "desc"


class Title(BaseHTML):
    """The SVG title component for titles."""

    tag = "title"


class Metadata(BaseHTML):
    """The SVG metadata component for metadata."""

    tag = "metadata"


class Script(BaseHTML):
    """The SVG script component for scripts."""

    tag = "script"

    # MIME type of the script.
    type: Var[str]

    # URL of external script.
    href: Var[str]

    # CORS settings for the script.
    crossorigin: Var[str]


class SvgStyle(BaseHTML):
    """The SVG style component for stylesheets."""

    tag = "style"

    # MIME type of the stylesheet.
    type: Var[str]

    # Media query for the stylesheet.
    media: Var[str]

    # Title of the stylesheet.
    title: Var[str]


class Switch(BaseHTML):
    """The SVG switch component for conditional processing."""

    tag = "switch"


class View(BaseHTML):
    """The SVG view component for view definitions."""

    tag = "view"

    # ViewBox definition for the view.
    view_box: Var[str]

    # How the view should scale to fit its viewport.
    preserve_aspect_ratio: Var[str]


class SVG(ComponentNamespace):
    """SVG component namespace."""

    text = staticmethod(Text.create)
    line = staticmethod(Line.create)
    circle = staticmethod(Circle.create)
    ellipse = staticmethod(Ellipse.create)
    rect = staticmethod(Rect.create)
    polygon = staticmethod(Polygon.create)
    polyline = staticmethod(Polyline.create)
    path = staticmethod(Path.create)
    stop = staticmethod(Stop.create)
    linear_gradient = staticmethod(LinearGradient.create)
    radial_gradient = staticmethod(RadialGradient.create)
    defs = staticmethod(Defs.create)
    marker = staticmethod(Marker.create)
    g = staticmethod(G.create)
    image = staticmethod(SvgImage.create)
    use = staticmethod(Use.create)
    tspan = staticmethod(TSpan.create)
    text_path = staticmethod(TextPath.create)
    pattern = staticmethod(Pattern.create)
    clip_path = staticmethod(ClipPath.create)
    symbol = staticmethod(Symbol.create)
    mask = staticmethod(Mask.create)
    foreign_object = staticmethod(ForeignObject.create)
    a = staticmethod(SvgA.create)
    animate = staticmethod(Animate.create)
    animate_motion = staticmethod(AnimateMotion.create)
    animate_transform = staticmethod(AnimateTransform.create)
    set = staticmethod(Set.create)
    mpath = staticmethod(MPath.create)
    desc = staticmethod(Desc.create)
    title = staticmethod(Title.create)
    metadata = staticmethod(Metadata.create)
    script = staticmethod(Script.create)
    style = staticmethod(SvgStyle.create)
    switch = staticmethod(Switch.create)
    view = staticmethod(View.create)
    __call__ = staticmethod(Svg.create)


text = Text.create
line = Line.create
circle = Circle.create
ellipse = Ellipse.create
rect = Rect.create
polygon = Polygon.create
polyline = Polyline.create
path = Path.create
stop = Stop.create
linear_gradient = LinearGradient.create
radial_gradient = RadialGradient.create
defs = Defs.create
marker = Marker.create
g = G.create
use = Use.create
tspan = TSpan.create
text_path = TextPath.create
pattern = Pattern.create
clip_path = ClipPath.create
symbol = Symbol.create
mask = Mask.create
foreign_object = ForeignObject.create
animate = Animate.create
animate_motion = AnimateMotion.create
animate_transform = AnimateTransform.create
set_svg = Set.create
mpath = MPath.create
desc = Desc.create
metadata = Metadata.create
switch = Switch.create
view = View.create
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

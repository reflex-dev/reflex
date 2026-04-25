"""Media classes."""

from typing import Any, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.constants.colors import Color
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.inline import ReferrerPolicy

from .base import BaseHTML


class Area(BaseHTML):
    """Display the area element."""

    tag = "area"

    alt: Var[str] = field(doc="Alternate text for the area, used for accessibility")

    coords: Var[str] = field(doc="Coordinates to define the shape of the area")

    download: Var[str | bool] = field(
        doc="Specifies that the target will be downloaded when clicked"
    )

    href: Var[str] = field(doc="Hyperlink reference for the area")

    href_lang: Var[str] = field(doc="Language of the linked resource")

    media: Var[str] = field(
        doc="Specifies what media/device the linked resource is optimized for"
    )

    referrer_policy: Var[ReferrerPolicy] = field(
        doc="Specifies which referrer information to send with the link"
    )

    rel: Var[str] = field(
        doc="Specifies the relationship of the target object to the link object"
    )

    shape: Var[str] = field(
        doc="Defines the shape of the area (rectangle, circle, polygon)"
    )

    target: Var[str] = field(doc="Specifies where to open the linked document")


CrossOrigin = Literal["anonymous", "use-credentials", ""]


class Audio(BaseHTML):
    """Display the audio element."""

    tag = "audio"

    auto_play: Var[bool] = field(
        doc="Specifies that the audio will start playing as soon as it is ready"
    )

    controls: Var[bool] = field(doc="Displays the standard audio controls")

    cross_origin: Var[CrossOrigin] = field(
        doc="Configures the CORS requests for the element"
    )

    loop: Var[bool] = field(doc="Specifies that the audio will loop")

    muted: Var[bool] = field(doc="Indicates whether the audio is muted by default")

    preload: Var[str] = field(doc="Specifies how the audio file should be preloaded")

    src: Var[str] = field(doc="URL of the audio to play")


ImageDecoding = Literal["async", "auto", "sync"]
ImageLoading = Literal["eager", "lazy"]


class Img(BaseHTML):
    """Display the img element."""

    tag = "img"

    alt: Var[str] = field(doc="Alternative text for the image")

    cross_origin: Var[CrossOrigin] = field(
        doc="Configures the CORS requests for the image"
    )

    decoding: Var[ImageDecoding] = field(doc="How the image should be decoded")

    loading: Var[ImageLoading] = field(
        doc="Specifies the loading behavior of the image"
    )

    referrer_policy: Var[ReferrerPolicy] = field(doc="Referrer policy for the image")

    sizes: Var[str] = field(doc="Sizes of the image for different layouts")

    src: Var[Any] = field(doc="URL of the image to display")

    src_set: Var[str] = field(
        doc="A set of source sizes and URLs for responsive images"
    )

    use_map: Var[str] = field(doc="The name of the map to use with the image")

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

    name: Var[str] = field(
        doc="Name of the map, referenced by the 'usemap' attribute in 'img' and 'object' elements"
    )


class Track(BaseHTML):
    """Display the track element."""

    tag = "track"

    default: Var[bool] = field(
        doc="Indicates that the track should be enabled unless the user's preferences indicate otherwise"
    )

    kind: Var[str] = field(doc="Specifies the kind of text track")

    label: Var[str] = field(
        doc="Title of the text track, used by the browser when listing available text tracks"
    )

    src: Var[str] = field(doc="URL of the track file")

    src_lang: Var[str] = field(doc="Language of the track text data")


class Video(BaseHTML):
    """Display the video element."""

    tag = "video"

    auto_play: Var[bool] = field(
        doc="Specifies that the video will start playing as soon as it is ready"
    )

    controls: Var[bool] = field(doc="Displays the standard video controls")

    cross_origin: Var[CrossOrigin] = field(
        doc="Configures the CORS requests for the video"
    )

    loop: Var[bool] = field(doc="Specifies that the video will loop")

    muted: Var[bool] = field(doc="Indicates whether the video is muted by default")

    plays_inline: Var[bool] = field(
        doc="Indicates that the video should play 'inline', inside its element's playback area"
    )

    poster: Var[str] = field(
        doc="URL of an image to show while the video is downloading, or until the user hits the play button"
    )

    preload: Var[str] = field(doc="Specifies how the video file should be preloaded")

    src: Var[str] = field(doc="URL of the video to play")


class Embed(BaseHTML):
    """Display the embed element."""

    tag = "embed"

    src: Var[str] = field(doc="URL of the embedded content")

    type: Var[str] = field(doc="Media type of the embedded content")


class Iframe(BaseHTML):
    """Display the iframe element."""

    tag = "iframe"

    allow: Var[str] = field(doc="Permissions policy for the iframe")

    loading: Var[Literal["eager", "lazy"]] = field(
        doc="Specifies the loading behavior of the iframe"
    )

    name: Var[str] = field(
        doc="Name of the iframe, used as a target for hyperlinks and forms"
    )

    referrer_policy: Var[ReferrerPolicy] = field(doc="Referrer policy for the iframe")

    sandbox: Var[str] = field(doc="Security restrictions for the content in the iframe")

    src: Var[str] = field(doc="URL of the document to display in the iframe")

    src_doc: Var[str] = field(doc="HTML content to embed directly within the iframe")


class Object(BaseHTML):
    """Display the object element."""

    tag = "object"

    data: Var[str] = field(doc="URL of the data to be used by the object")

    form: Var[str] = field(doc="Associates the object with a form element")

    name: Var[str] = field(
        doc="Name of the object, used for scripting or as a target for forms and links"
    )

    type: Var[str] = field(doc="Media type of the data specified in the data attribute")

    use_map: Var[str] = field(doc="Name of an image map to use with the object")


class Picture(BaseHTML):
    """Display the picture element."""

    tag = "picture"


class Portal(BaseHTML):
    """Display the portal element."""

    tag = "portal"


class Source(BaseHTML):
    """Display the source element."""

    tag = "source"

    media: Var[str] = field(
        doc="Media query indicating what device the linked resource is optimized for"
    )

    sizes: Var[str] = field(doc="Sizes of the source for different layouts")

    src: Var[str] = field(
        doc="URL of the media file or an image for the element to use"
    )

    src_set: Var[str] = field(
        doc="A set of source sizes and URLs for responsive images"
    )

    type: Var[str] = field(doc="Media type of the source")


class Svg(BaseHTML):
    """Display the svg element."""

    tag = "svg"
    width: Var[str | int] = field(doc="The width of the svg.")
    height: Var[str | int] = field(doc="The height of the svg.")
    xmlns: Var[str] = field(doc="The XML namespace declaration.")
    view_box: Var[str] = field(
        doc="The viewBox attribute defines the position and dimension, in user space, of an SVG viewport."
    )
    preserve_aspect_ratio: Var[str] = field(
        doc="Controls how the SVG scales to fit its viewport."
    )
    transform: Var[str] = field(
        doc="Defines a list of transform definitions that are applied to an element and the element's children."
    )


class Text(BaseHTML):
    """The SVG text component."""

    tag = "text"
    x: Var[str | int] = field(
        doc="The x coordinate of the starting point of the text baseline."
    )
    y: Var[str | int] = field(
        doc="The y coordinate of the starting point of the text baseline."
    )
    dx: Var[str | int] = field(
        doc="Shifts the text position horizontally from a previous text element."
    )
    dy: Var[str | int] = field(
        doc="Shifts the text position vertically from a previous text element."
    )
    rotate: Var[str | int] = field(doc="Rotates orientation of each individual glyph.")
    length_adjust: Var[str] = field(
        doc="How the text is stretched or compressed to fit the width defined by the text_length attribute."
    )
    text_length: Var[str | int] = field(
        doc="A width that the text should be scaled to fit."
    )


class Line(BaseHTML):
    """The SVG line component."""

    tag = "line"
    x1: Var[str | int] = field(doc="The x-axis coordinate of the line starting point.")
    x2: Var[str | int] = field(
        doc="The x-axis coordinate of the the line ending point."
    )
    y1: Var[str | int] = field(doc="The y-axis coordinate of the line starting point.")
    y2: Var[str | int] = field(
        doc="The y-axis coordinate of the the line ending point."
    )
    path_length: Var[int] = field(doc="The total path length, in user units.")


class Circle(BaseHTML):
    """The SVG circle component."""

    tag = "circle"
    cx: Var[str | int] = field(doc="The x-axis coordinate of the center of the circle.")
    cy: Var[str | int] = field(doc="The y-axis coordinate of the center of the circle.")
    r: Var[str | int] = field(doc="The radius of the circle.")
    path_length: Var[int] = field(
        doc="The total length for the circle's circumference, in user units."
    )


class Ellipse(BaseHTML):
    """The SVG ellipse component."""

    tag = "ellipse"
    cx: Var[str | int] = field(doc="The x position of the center of the ellipse.")
    cy: Var[str | int] = field(doc="The y position of the center of the ellipse.")
    rx: Var[str | int] = field(doc="The radius of the ellipse on the x axis.")
    ry: Var[str | int] = field(doc="The radius of the ellipse on the y axis.")
    path_length: Var[int] = field(
        doc="The total length for the ellipse's circumference, in user units."
    )


class Rect(BaseHTML):
    """The SVG rect component."""

    tag = "rect"
    x: Var[str | int] = field(doc="The x coordinate of the rect.")
    y: Var[str | int] = field(doc="The y coordinate of the rect.")
    width: Var[str | int] = field(doc="The width of the rect")
    height: Var[str | int] = field(doc="The height of the rect.")
    rx: Var[str | int] = field(
        doc="The horizontal corner radius of the rect. Defaults to ry if it is specified."
    )
    ry: Var[str | int] = field(
        doc="The vertical corner radius of the rect. Defaults to rx if it is specified."
    )
    path_length: Var[int] = field(
        doc="The total length of the rectangle's perimeter, in user units."
    )


class Polygon(BaseHTML):
    """The SVG polygon component."""

    tag = "polygon"
    points: Var[str] = field(
        doc="defines the list of points (pairs of x,y absolute coordinates) required to draw the polygon."
    )
    path_length: Var[int] = field(
        doc="This prop lets specify the total length for the path, in user units."
    )


class Polyline(BaseHTML):
    """The SVG polyline component."""

    tag = "polyline"
    points: Var[str] = field(
        doc="List of points (pairs of x,y coordinates) that define the polyline."
    )
    path_length: Var[int] = field(doc="The total path length, in user units.")


class Defs(BaseHTML):
    """Display the defs element."""

    tag = "defs"


class LinearGradient(BaseHTML):
    """Display the linearGradient element."""

    tag = "linearGradient"

    gradient_units: Var[str | bool] = field(doc="Units for the gradient.")

    gradient_transform: Var[str | bool] = field(
        doc="Transform applied to the gradient."
    )

    spread_method: Var[str | bool] = field(doc="Method used to spread the gradient.")

    href: Var[str] = field(doc="Reference to another gradient to inherit from.")

    x1: Var[str | int | float] = field(
        doc="X coordinate of the starting point of the gradient."
    )

    x2: Var[str | int | float] = field(
        doc="X coordinate of the ending point of the gradient."
    )

    y1: Var[str | int | float] = field(
        doc="Y coordinate of the starting point of the gradient."
    )

    y2: Var[str | int | float] = field(
        doc="Y coordinate of the ending point of the gradient."
    )


class RadialGradient(BaseHTML):
    """Display the radialGradient element."""

    tag = "radialGradient"

    cx: Var[str | int | float] = field(
        doc="The x coordinate of the end circle of the radial gradient."
    )

    cy: Var[str | int | float] = field(
        doc="The y coordinate of the end circle of the radial gradient."
    )

    fr: Var[str | int | float] = field(
        doc="The radius of the start circle of the radial gradient."
    )

    fx: Var[str | int | float] = field(
        doc="The x coordinate of the start circle of the radial gradient."
    )

    fy: Var[str | int | float] = field(
        doc="The y coordinate of the start circle of the radial gradient."
    )

    gradient_units: Var[str | bool] = field(doc="Units for the gradient.")

    gradient_transform: Var[str | bool] = field(
        doc="Transform applied to the gradient."
    )

    href: Var[str] = field(doc="Reference to another gradient to inherit from.")

    r: Var[str | int | float] = field(
        doc="The radius of the end circle of the radial gradient."
    )

    spread_method: Var[str | bool] = field(doc="Method used to spread the gradient.")


class Stop(BaseHTML):
    """Display the stop element."""

    tag = "stop"

    offset: Var[str | float | int] = field(doc="Offset of the gradient stop.")

    stop_color: Var[str | Color | bool] = field(doc="Color of the gradient stop.")

    stop_opacity: Var[str | float | int | bool] = field(
        doc="Opacity of the gradient stop."
    )


class Path(BaseHTML):
    """Display the path element."""

    tag = "path"

    d: Var[str | int | float] = field(doc="Defines the shape of the path.")
    path_length: Var[int] = field(doc="The total path length, in user units.")


class Marker(BaseHTML):
    """Display the marker element."""

    tag = "marker"

    marker_height: Var[str | int | float] = field(
        doc="The height of the marker viewport."
    )

    marker_width: Var[str | int | float] = field(
        doc="The width of the marker viewport."
    )

    marker_units: Var[str] = field(
        doc="The coordinate system for the marker attributes."
    )

    orient: Var[str | int | float] = field(
        doc="The orientation of the marker relative to the shape it is attached to."
    )

    preserve_aspect_ratio: Var[str] = field(
        doc="How the svg fragment must be deformed if it is embedded in a container with a different aspect ratio."
    )

    ref_x: Var[str | int | float] = field(
        doc="The x coordinate for the reference point of the marker."
    )

    ref_y: Var[str | int | float] = field(
        doc="The y coordinate for the reference point of the marker."
    )

    view_box: Var[str] = field(
        doc="The bound of the SVG viewport for the current SVG fragment."
    )


class G(BaseHTML):
    """The SVG g component, used to group other SVG elements."""

    tag = "g"

    fill: Var[str | Color] = field(doc="The fill color of the group.")

    fill_opacity: Var[str | int | float] = field(doc="The fill opacity of the group.")

    stroke: Var[str | Color] = field(doc="The stroke color of the group.")

    stroke_opacity: Var[str | int | float] = field(
        doc="The stroke opacity of the group."
    )

    stroke_width: Var[str | int | float] = field(doc="The stroke width of the group.")

    transform: Var[str] = field(doc="The transform applied to the group.")


class SvgImage(BaseHTML):
    """The SVG image component."""

    tag = "image"

    href: Var[str] = field(doc="URL of the image to display.")

    x: Var[str | int] = field(doc="X coordinate of the image.")

    y: Var[str | int] = field(doc="Y coordinate of the image.")

    width: Var[str | int] = field(doc="Width of the image.")

    height: Var[str | int] = field(doc="Height of the image.")

    preserve_aspect_ratio: Var[str] = field(
        doc="How the image should scale to fit its viewport."
    )

    crossorigin: Var[str] = field(doc="CORS settings for the image.")


class Use(BaseHTML):
    """The SVG use component for reusing defined elements."""

    tag = "use"

    href: Var[str] = field(doc="Reference to the element to reuse.")

    x: Var[str | int] = field(
        doc="X coordinate where the referenced element should be positioned."
    )

    y: Var[str | int] = field(
        doc="Y coordinate where the referenced element should be positioned."
    )

    width: Var[str | int] = field(doc="Width of the referenced element.")

    height: Var[str | int] = field(doc="Height of the referenced element.")


class TSpan(BaseHTML):
    """The SVG tspan component for text spans within text elements."""

    tag = "tspan"

    x: Var[str | int] = field(doc="X coordinate of the text.")

    y: Var[str | int] = field(doc="Y coordinate of the text.")

    dx: Var[str | int] = field(doc="Horizontal offset from the previous text element.")

    dy: Var[str | int] = field(doc="Vertical offset from the previous text element.")

    rotate: Var[str | int] = field(doc="Rotation of the text.")

    length_adjust: Var[str] = field(
        doc="How the text is stretched or compressed to fit the width defined by text_length."
    )

    text_length: Var[str | int] = field(
        doc="A width that the text should be scaled to fit."
    )


class TextPath(BaseHTML):
    """The SVG textPath component for text along a path."""

    tag = "textPath"

    href: Var[str] = field(
        doc="Reference to the path along which the text should be rendered."
    )

    path: Var[str] = field(doc="Inline path data.")

    start_offset: Var[str | int] = field(
        doc="Distance along the path from its beginning to the initial position of the text."
    )

    method: Var[str] = field(doc="Method for rendering text along the path.")

    spacing: Var[str] = field(doc="Spacing method for text.")

    side: Var[str] = field(doc="Which side of the path the text should be rendered on.")

    length_adjust: Var[str] = field(
        doc="How the text is stretched or compressed to fit the specified length."
    )

    text_length: Var[str | int] = field(doc="Target length for the text.")


class Pattern(BaseHTML):
    """The SVG pattern component for defining repeating patterns."""

    tag = "pattern"

    x: Var[str | int] = field(doc="X coordinate of the pattern.")

    y: Var[str | int] = field(doc="Y coordinate of the pattern.")

    width: Var[str | int] = field(doc="Width of the pattern.")

    height: Var[str | int] = field(doc="Height of the pattern.")

    pattern_units: Var[str] = field(doc="Units for the pattern coordinates.")

    pattern_content_units: Var[str] = field(
        doc="Units for the pattern content coordinates."
    )

    pattern_transform: Var[str] = field(doc="Transform applied to the pattern.")

    view_box: Var[str] = field(doc="ViewBox definition for the pattern.")

    preserve_aspect_ratio: Var[str] = field(
        doc="How the pattern should scale to fit its viewport."
    )

    href: Var[str] = field(doc="Reference to another pattern to inherit from.")


class ClipPath(BaseHTML):
    """The SVG clipPath component for defining clipping paths."""

    tag = "clipPath"

    clip_path_units: Var[str] = field(doc="Units for the clipping path coordinates.")


class Symbol(BaseHTML):
    """The SVG symbol component for defining reusable symbols."""

    tag = "symbol"

    view_box: Var[str] = field(doc="ViewBox definition for the symbol.")

    preserve_aspect_ratio: Var[str] = field(
        doc="How the symbol should scale to fit its viewport."
    )

    ref_x: Var[str | int] = field(doc="Reference X coordinate.")

    ref_y: Var[str | int] = field(doc="Reference Y coordinate.")


class Mask(BaseHTML):
    """The SVG mask component for defining masks."""

    tag = "mask"

    x: Var[str | int] = field(doc="X coordinate of the mask.")

    y: Var[str | int] = field(doc="Y coordinate of the mask.")

    width: Var[str | int] = field(doc="Width of the mask.")

    height: Var[str | int] = field(doc="Height of the mask.")

    mask_units: Var[str] = field(doc="Units for the mask coordinates.")

    mask_content_units: Var[str] = field(doc="Units for the mask content coordinates.")


class ForeignObject(BaseHTML):
    """The SVG foreignObject component for embedding foreign content."""

    tag = "foreignObject"

    x: Var[str | int] = field(doc="X coordinate of the foreign object.")

    y: Var[str | int] = field(doc="Y coordinate of the foreign object.")

    width: Var[str | int] = field(doc="Width of the foreign object.")

    height: Var[str | int] = field(doc="Height of the foreign object.")


class SvgA(BaseHTML):
    """The SVG anchor component for creating links."""

    tag = "a"

    href: Var[str] = field(doc="URL of the link.")

    target: Var[str] = field(doc="Where to open the linked resource.")

    download: Var[str] = field(doc="Download attribute for the link.")

    rel: Var[str] = field(
        doc="Relationship between the current document and the linked resource."
    )

    hreflang: Var[str] = field(doc="Language of the linked resource.")

    type: Var[str] = field(doc="MIME type of the linked resource.")

    referrerpolicy: Var[str] = field(doc="Referrer policy for the link.")


class Animate(BaseHTML):
    """The SVG animate component for animations."""

    tag = "animate"

    attribute_name: Var[str] = field(doc="Name of the attribute to animate.")

    from_: Var[str] = field(doc="Starting value of the animation.")

    to: Var[str] = field(doc="Ending value of the animation.")

    dur: Var[str] = field(doc="Duration of the animation.")

    begin: Var[str] = field(doc="When the animation should begin.")

    end: Var[str] = field(doc="When the animation should end.")

    repeat_count: Var[str] = field(doc="Number of times to repeat the animation.")

    calc_mode: Var[str] = field(
        doc="How values should be calculated during the animation."
    )

    values: Var[str] = field(doc="List of values for the animation.")

    key_times: Var[str] = field(doc="Key times for the animation values.")

    key_splines: Var[str] = field(doc="Key splines for smooth transitions.")

    accumulate: Var[str] = field(doc="Whether animation values should accumulate.")

    additive: Var[str] = field(doc="Whether animation values should be additive.")

    href: Var[str] = field(doc="Reference to the target element.")


class AnimateMotion(BaseHTML):
    """The SVG animateMotion component for motion animations."""

    tag = "animateMotion"

    path: Var[str] = field(doc="Path along which to animate.")

    dur: Var[str] = field(doc="Duration of the animation.")

    begin: Var[str] = field(doc="When the animation should begin.")

    end: Var[str] = field(doc="When the animation should end.")

    repeat_count: Var[str] = field(doc="Number of times to repeat the animation.")

    rotate: Var[str] = field(doc="Rotation behavior during motion.")

    key_times: Var[str] = field(doc="Key times for the motion.")

    key_points: Var[str] = field(doc="Key points along the path.")

    href: Var[str] = field(doc="Reference to the target element.")


class AnimateTransform(BaseHTML):
    """The SVG animateTransform component for transform animations."""

    tag = "animateTransform"

    attribute_name: Var[str] = field(doc="Name of the transform attribute to animate.")

    type: Var[str] = field(doc="Type of transformation.")

    from_: Var[str] = field(doc="Starting value of the transformation.")

    to: Var[str] = field(doc="Ending value of the transformation.")

    dur: Var[str] = field(doc="Duration of the animation.")

    begin: Var[str] = field(doc="When the animation should begin.")

    end: Var[str] = field(doc="When the animation should end.")

    repeat_count: Var[str] = field(doc="Number of times to repeat the animation.")

    values: Var[str] = field(doc="List of values for the transformation.")

    href: Var[str] = field(doc="Reference to the target element.")


class Set(BaseHTML):
    """The SVG set component for setting attribute values."""

    tag = "set"

    attribute_name: Var[str] = field(doc="Name of the attribute to set.")

    to: Var[str] = field(doc="Value to set the attribute to.")

    begin: Var[str] = field(doc="When to set the attribute.")

    dur: Var[str] = field(doc="Duration for which to maintain the value.")

    end: Var[str] = field(doc="When to end the setting.")

    href: Var[str] = field(doc="Reference to the target element.")


class MPath(BaseHTML):
    """The SVG mpath component for motion path references."""

    tag = "mpath"

    href: Var[str] = field(doc="Reference to a path element.")


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

    type: Var[str] = field(doc="MIME type of the script.")

    href: Var[str] = field(doc="URL of external script.")

    crossorigin: Var[str] = field(doc="CORS settings for the script.")


class SvgStyle(BaseHTML):
    """The SVG style component for stylesheets."""

    tag = "style"

    type: Var[str] = field(doc="MIME type of the stylesheet.")

    media: Var[str] = field(doc="Media query for the stylesheet.")

    title: Var[str] = field(doc="Title of the stylesheet.")


class Switch(BaseHTML):
    """The SVG switch component for conditional processing."""

    tag = "switch"


class View(BaseHTML):
    """The SVG view component for view definitions."""

    tag = "view"

    view_box: Var[str] = field(doc="ViewBox definition for the view.")

    preserve_aspect_ratio: Var[str] = field(
        doc="How the view should scale to fit its viewport."
    )


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

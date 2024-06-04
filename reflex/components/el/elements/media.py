"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Any, Union

from reflex import Component
from reflex.vars import Var as Var

from .base import BaseHTML


class Area(BaseHTML):
    """Display the area element."""

    tag = "area"

    # Alternate text for the area, used for accessibility
    alt: Var[Union[str, int, bool]]

    # Coordinates to define the shape of the area
    coords: Var[Union[str, int, bool]]

    # Specifies that the target will be downloaded when clicked
    download: Var[Union[str, int, bool]]

    # Hyperlink reference for the area
    href: Var[Union[str, int, bool]]

    # Language of the linked resource
    href_lang: Var[Union[str, int, bool]]

    # Specifies what media/device the linked resource is optimized for
    media: Var[Union[str, int, bool]]

    # A list of URLs to be notified if the user follows the hyperlink
    ping: Var[Union[str, int, bool]]

    # Specifies which referrer information to send with the link
    referrer_policy: Var[Union[str, int, bool]]

    # Specifies the relationship of the target object to the link object
    rel: Var[Union[str, int, bool]]

    # Defines the shape of the area (rectangle, circle, polygon)
    shape: Var[Union[str, int, bool]]

    # Specifies where to open the linked document
    target: Var[Union[str, int, bool]]


class Audio(BaseHTML):
    """Display the audio element."""

    tag = "audio"

    # Specifies that the audio will start playing as soon as it is ready
    auto_play: Var[Union[str, int, bool]]

    # Represents the time range of the buffered media
    buffered: Var[Union[str, int, bool]]

    # Displays the standard audio controls
    controls: Var[Union[str, int, bool]]

    # Configures the CORS requests for the element
    cross_origin: Var[Union[str, int, bool]]

    # Specifies that the audio will loop
    loop: Var[Union[str, int, bool]]

    # Indicates whether the audio is muted by default
    muted: Var[Union[str, int, bool]]

    # Specifies how the audio file should be preloaded
    preload: Var[Union[str, int, bool]]

    # URL of the audio to play
    src: Var[Union[str, int, bool]]


class Img(BaseHTML):
    """Display the img element."""

    tag = "img"

    # Image alignment with respect to its surrounding elements
    align: Var[Union[str, int, bool]]

    # Alternative text for the image
    alt: Var[Union[str, int, bool]]

    # Configures the CORS requests for the image
    cross_origin: Var[Union[str, int, bool]]

    # How the image should be decoded
    decoding: Var[Union[str, int, bool]]

    # Specifies an intrinsic size for the image
    intrinsicsize: Var[Union[str, int, bool]]

    # Whether the image is a server-side image map
    ismap: Var[Union[str, int, bool]]

    # Specifies the loading behavior of the image
    loading: Var[Union[str, int, bool]]

    # Referrer policy for the image
    referrer_policy: Var[Union[str, int, bool]]

    # Sizes of the image for different layouts
    sizes: Var[Union[str, int, bool]]

    # URL of the image to display
    src: Var[Any]

    # A set of source sizes and URLs for responsive images
    src_set: Var[Union[str, int, bool]]

    # The name of the map to use with the image
    use_map: Var[Union[str, int, bool]]

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
    name: Var[Union[str, int, bool]]


class Track(BaseHTML):
    """Display the track element."""

    tag = "track"

    # Indicates that the track should be enabled unless the user's preferences indicate otherwise
    default: Var[Union[str, int, bool]]

    # Specifies the kind of text track
    kind: Var[Union[str, int, bool]]

    # Title of the text track, used by the browser when listing available text tracks
    label: Var[Union[str, int, bool]]

    # URL of the track file
    src: Var[Union[str, int, bool]]

    # Language of the track text data
    src_lang: Var[Union[str, int, bool]]


class Video(BaseHTML):
    """Display the video element."""

    tag = "video"

    # Specifies that the video will start playing as soon as it is ready
    auto_play: Var[Union[str, int, bool]]

    # Represents the time range of the buffered media
    buffered: Var[Union[str, int, bool]]

    # Displays the standard video controls
    controls: Var[Union[str, int, bool]]

    # Configures the CORS requests for the video
    cross_origin: Var[Union[str, int, bool]]

    # Specifies that the video will loop
    loop: Var[Union[str, int, bool]]

    # Indicates whether the video is muted by default
    muted: Var[Union[str, int, bool]]

    # Indicates that the video should play 'inline', inside its element's playback area
    plays_inline: Var[Union[str, int, bool]]

    # URL of an image to show while the video is downloading, or until the user hits the play button
    poster: Var[Union[str, int, bool]]

    # Specifies how the video file should be preloaded
    preload: Var[Union[str, int, bool]]

    # URL of the video to play
    src: Var[Union[str, int, bool]]


class Embed(BaseHTML):
    """Display the embed element."""

    tag = "embed"

    # URL of the embedded content
    src: Var[Union[str, int, bool]]

    # Media type of the embedded content
    type: Var[Union[str, int, bool]]


class Iframe(BaseHTML):
    """Display the iframe element."""

    tag = "iframe"

    # Alignment of the iframe within the page or surrounding elements
    align: Var[Union[str, int, bool]]

    # Permissions policy for the iframe
    allow: Var[Union[str, int, bool]]

    # Content Security Policy to apply to the iframe's content
    csp: Var[Union[str, int, bool]]

    # Specifies the loading behavior of the iframe
    loading: Var[Union[str, int, bool]]

    # Name of the iframe, used as a target for hyperlinks and forms
    name: Var[Union[str, int, bool]]

    # Referrer policy for the iframe
    referrer_policy: Var[Union[str, int, bool]]

    # Security restrictions for the content in the iframe
    sandbox: Var[Union[str, int, bool]]

    # URL of the document to display in the iframe
    src: Var[Union[str, int, bool]]

    # HTML content to embed directly within the iframe
    src_doc: Var[Union[str, int, bool]]


class Object(BaseHTML):
    """Display the object element."""

    tag = "object"

    # URL of the data to be used by the object
    data: Var[Union[str, int, bool]]

    # Associates the object with a form element
    form: Var[Union[str, int, bool]]

    # Name of the object, used for scripting or as a target for forms and links
    name: Var[Union[str, int, bool]]

    # Media type of the data specified in the data attribute
    type: Var[Union[str, int, bool]]

    # Name of an image map to use with the object
    use_map: Var[Union[str, int, bool]]


class Picture(BaseHTML):
    """Display the picture element."""

    tag = "picture"
    # No unique attributes, only common ones are inherited


class Portal(BaseHTML):
    """Display the portal element."""

    tag = "portal"
    # No unique attributes, only common ones are inherited


class Source(BaseHTML):
    """Display the source element."""

    tag = "source"

    # Media query indicating what device the linked resource is optimized for
    media: Var[Union[str, int, bool]]

    # Sizes of the source for different layouts
    sizes: Var[Union[str, int, bool]]

    # URL of the media file or an image for the element to use
    src: Var[Union[str, int, bool]]

    # A set of source sizes and URLs for responsive images
    src_set: Var[Union[str, int, bool]]

    # Media type of the source
    type: Var[Union[str, int, bool]]


class Svg(BaseHTML):
    """Display the svg element."""

    tag = "svg"


class Path(BaseHTML):
    """Display the path element."""

    tag = "path"

    # Defines the shape of the path
    d: Var[Union[str, int, bool]]


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
svg = Svg.create
path = Path.create

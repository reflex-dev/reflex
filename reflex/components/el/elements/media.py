"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Any, Optional, Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Area(BaseHTML):
    """Display the area element."""

    tag: str = "area"

    # Alternate text for the area, used for accessibility
    alt: Optional[Var[Union[str, int, bool]]] = None

    # Coordinates to define the shape of the area
    coords: Optional[Var[Union[str, int, bool]]] = None

    # Specifies that the target will be downloaded when clicked
    download: Optional[Var[Union[str, int, bool]]] = None

    # Hyperlink reference for the area
    href: Optional[Var[Union[str, int, bool]]] = None

    # Language of the linked resource
    href_lang: Optional[Var[Union[str, int, bool]]] = None

    # Specifies what media/device the linked resource is optimized for
    media: Optional[Var[Union[str, int, bool]]] = None

    # A list of URLs to be notified if the user follows the hyperlink
    ping: Optional[Var[Union[str, int, bool]]] = None

    # Specifies which referrer information to send with the link
    referrer_policy: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the relationship of the target object to the link object
    rel: Optional[Var[Union[str, int, bool]]] = None

    # Defines the shape of the area (rectangle, circle, polygon)
    shape: Optional[Var[Union[str, int, bool]]] = None

    # Specifies where to open the linked document
    target: Optional[Var[Union[str, int, bool]]] = None


class Audio(BaseHTML):
    """Display the audio element."""

    tag: str = "audio"

    # Specifies that the audio will start playing as soon as it is ready
    auto_play: Optional[Var[Union[str, int, bool]]] = None

    # Represents the time range of the buffered media
    buffered: Optional[Var[Union[str, int, bool]]] = None

    # Displays the standard audio controls
    controls: Optional[Var[Union[str, int, bool]]] = None

    # Configures the CORS requests for the element
    cross_origin: Optional[Var[Union[str, int, bool]]] = None

    # Specifies that the audio will loop
    loop: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether the audio is muted by default
    muted: Optional[Var[Union[str, int, bool]]] = None

    # Specifies how the audio file should be preloaded
    preload: Optional[Var[Union[str, int, bool]]] = None

    # URL of the audio to play
    src: Optional[Var[Union[str, int, bool]]] = None


class Img(BaseHTML):
    """Display the img element."""

    tag: str = "img"

    # Image alignment with respect to its surrounding elements
    align: Optional[Var[Union[str, int, bool]]] = None

    # Alternative text for the image
    alt: Optional[Var[Union[str, int, bool]]] = None

    # Configures the CORS requests for the image
    cross_origin: Optional[Var[Union[str, int, bool]]] = None

    # How the image should be decoded
    decoding: Optional[Var[Union[str, int, bool]]] = None

    # Specifies an intrinsic size for the image
    intrinsicsize: Optional[Var[Union[str, int, bool]]] = None

    # Whether the image is a server-side image map
    ismap: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the loading behavior of the image
    loading: Optional[Var[Union[str, int, bool]]] = None

    # Referrer policy for the image
    referrer_policy: Optional[Var[Union[str, int, bool]]] = None

    # Sizes of the image for different layouts
    sizes: Optional[Var[Union[str, int, bool]]] = None

    # URL of the image to display
    src: Optional[Var[Any]] = None

    # A set of source sizes and URLs for responsive images
    src_set: Optional[Var[Union[str, int, bool]]] = None

    # The name of the map to use with the image
    use_map: Optional[Var[Union[str, int, bool]]] = None


class Map(BaseHTML):
    """Display the map element."""

    tag: str = "map"

    # Name of the map, referenced by the 'usemap' attribute in 'img' and 'object' elements
    name: Optional[Var[Union[str, int, bool]]] = None


class Track(BaseHTML):
    """Display the track element."""

    tag: str = "track"

    # Indicates that the track should be enabled unless the user's preferences indicate otherwise
    default: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the kind of text track
    kind: Optional[Var[Union[str, int, bool]]] = None

    # Title of the text track, used by the browser when listing available text tracks
    label: Optional[Var[Union[str, int, bool]]] = None

    # URL of the track file
    src: Optional[Var[Union[str, int, bool]]] = None

    # Language of the track text data
    src_lang: Optional[Var[Union[str, int, bool]]] = None


class Video(BaseHTML):
    """Display the video element."""

    tag: str = "video"

    # Specifies that the video will start playing as soon as it is ready
    auto_play: Optional[Var[Union[str, int, bool]]] = None

    # Represents the time range of the buffered media
    buffered: Optional[Var[Union[str, int, bool]]] = None

    # Displays the standard video controls
    controls: Optional[Var[Union[str, int, bool]]] = None

    # Configures the CORS requests for the video
    cross_origin: Optional[Var[Union[str, int, bool]]] = None

    # Specifies that the video will loop
    loop: Optional[Var[Union[str, int, bool]]] = None

    # Indicates whether the video is muted by default
    muted: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the video should play 'inline', inside its element's playback area
    plays_inline: Optional[Var[Union[str, int, bool]]] = None

    # URL of an image to show while the video is downloading, or until the user hits the play button
    poster: Optional[Var[Union[str, int, bool]]] = None

    # Specifies how the video file should be preloaded
    preload: Optional[Var[Union[str, int, bool]]] = None

    # URL of the video to play
    src: Optional[Var[Union[str, int, bool]]] = None


class Embed(BaseHTML):
    """Display the embed element."""

    tag: str = "embed"

    # URL of the embedded content
    src: Optional[Var[Union[str, int, bool]]] = None

    # Media type of the embedded content
    type: Optional[Var[Union[str, int, bool]]] = None


class Iframe(BaseHTML):
    """Display the iframe element."""

    tag: str = "iframe"

    # Alignment of the iframe within the page or surrounding elements
    align: Optional[Var[Union[str, int, bool]]] = None

    # Permissions policy for the iframe
    allow: Optional[Var[Union[str, int, bool]]] = None

    # Content Security Policy to apply to the iframe's content
    csp: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the loading behavior of the iframe
    loading: Optional[Var[Union[str, int, bool]]] = None

    # Name of the iframe, used as a target for hyperlinks and forms
    name: Optional[Var[Union[str, int, bool]]] = None

    # Referrer policy for the iframe
    referrer_policy: Optional[Var[Union[str, int, bool]]] = None

    # Security restrictions for the content in the iframe
    sandbox: Optional[Var[Union[str, int, bool]]] = None

    # URL of the document to display in the iframe
    src: Optional[Var[Union[str, int, bool]]] = None

    # HTML content to embed directly within the iframe
    src_doc: Optional[Var[Union[str, int, bool]]] = None


class Object(BaseHTML):
    """Display the object element."""

    tag: str = "object"

    # URL of the data to be used by the object
    data: Optional[Var[Union[str, int, bool]]] = None

    # Associates the object with a form element
    form: Optional[Var[Union[str, int, bool]]] = None

    # Name of the object, used for scripting or as a target for forms and links
    name: Optional[Var[Union[str, int, bool]]] = None

    # Media type of the data specified in the data attribute
    type: Optional[Var[Union[str, int, bool]]] = None

    # Name of an image map to use with the object
    use_map: Optional[Var[Union[str, int, bool]]] = None


class Picture(BaseHTML):
    """Display the picture element."""

    tag: str = "picture"
    # No unique attributes, only common ones are inherited


class Portal(BaseHTML):
    """Display the portal element."""

    tag: str = "portal"
    # No unique attributes, only common ones are inherited


class Source(BaseHTML):
    """Display the source element."""

    tag: str = "source"

    # Media query indicating what device the linked resource is optimized for
    media: Optional[Var[Union[str, int, bool]]] = None

    # Sizes of the source for different layouts
    sizes: Optional[Var[Union[str, int, bool]]] = None

    # URL of the media file or an image for the element to use
    src: Optional[Var[Union[str, int, bool]]] = None

    # A set of source sizes and URLs for responsive images
    src_set: Optional[Var[Union[str, int, bool]]] = None

    # Media type of the source
    type: Optional[Var[Union[str, int, bool]]] = None


class Svg(BaseHTML):
    """Display the svg element."""

    tag: str = "svg"


class Path(BaseHTML):
    """Display the path element."""

    tag: str = "path"

    # Defines the shape of the path
    d: Optional[Var[Union[str, int, bool]]] = None

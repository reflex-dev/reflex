"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.el.element import Element
from reflex.vars import Var as Var_
from .base import BaseHTML



class Area(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the area element."""

    tag = "area"
    alt: Var_[Union[str, int, bool]]
    coords: Var_[Union[str, int, bool]]
    download: Var_[Union[str, int, bool]]
    href: Var_[Union[str, int, bool]]
    href_lang: Var_[Union[str, int, bool]]
    media: Var_[Union[str, int, bool]]
    ping: Var_[Union[str, int, bool]]
    referrer_policy: Var_[Union[str, int, bool]]
    rel: Var_[Union[str, int, bool]]
    shape: Var_[Union[str, int, bool]]
    target: Var_[Union[str, int, bool]]


class Audio(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the audio element."""

    tag = "audio"
    auto_play: Var_[Union[str, int, bool]]
    buffered: Var_[Union[str, int, bool]]
    controls: Var_[Union[str, int, bool]]
    cross_origin: Var_[Union[str, int, bool]]
    loop: Var_[Union[str, int, bool]]
    muted: Var_[Union[str, int, bool]]
    preload: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]


class Img(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the img element."""

    tag = "img"
    align: Var_[Union[str, int, bool]]
    alt: Var_[Union[str, int, bool]]
    border: Var_[Union[str, int, bool]]
    cross_origin: Var_[Union[str, int, bool]]
    decoding: Var_[Union[str, int, bool]]
    height: Var_[Union[str, int, bool]]
    intrinsicsize: Var_[Union[str, int, bool]]
    ismap: Var_[Union[str, int, bool]]
    loading: Var_[Union[str, int, bool]]
    referrer_policy: Var_[Union[str, int, bool]]
    sizes: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    src_set: Var_[Union[str, int, bool]]
    use_map: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


class Map(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the map element."""

    tag = "map"
    name: Var_[Union[str, int, bool]]


class Track(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the track element."""

    tag = "track"
    default: Var_[Union[str, int, bool]]
    kind: Var_[Union[str, int, bool]]
    label: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    src_lang: Var_[Union[str, int, bool]]


class Video(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the video element."""

    tag = "video"
    auto_play: Var_[Union[str, int, bool]]
    buffered: Var_[Union[str, int, bool]]
    controls: Var_[Union[str, int, bool]]
    cross_origin: Var_[Union[str, int, bool]]
    height: Var_[Union[str, int, bool]]
    loop: Var_[Union[str, int, bool]]
    muted: Var_[Union[str, int, bool]]
    plays_inline: Var_[Union[str, int, bool]]
    poster: Var_[Union[str, int, bool]]
    preload: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


class Embed(BaseHTML):
    """Display the embed element."""

    tag = "embed"
    height: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


class Iframe(BaseHTML):
    """Display the iframe element."""

    tag = "iframe"
    align: Var_[Union[str, int, bool]]
    allow: Var_[Union[str, int, bool]]
    csp: Var_[Union[str, int, bool]]
    height: Var_[Union[str, int, bool]]
    loading: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    referrer_policy: Var_[Union[str, int, bool]]
    sandbox: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    src_doc: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


class Object(BaseHTML):
    """Display the object element."""

    tag = "object"
    border: Var_[Union[str, int, bool]]
    data: Var_[Union[str, int, bool]]
    form: Var_[Union[str, int, bool]]
    height: Var_[Union[str, int, bool]]
    name: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]
    use_map: Var_[Union[str, int, bool]]
    width: Var_[Union[str, int, bool]]


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
    media: Var_[Union[str, int, bool]]
    sizes: Var_[Union[str, int, bool]]
    src: Var_[Union[str, int, bool]]
    src_set: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]

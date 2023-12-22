"""Namespace for components provided by next packages."""

from .base import NextComponent
from .image import Image
from .link import NextLink
from .video import Video

image = Image.create
video = Video.create
next_link = NextLink.create

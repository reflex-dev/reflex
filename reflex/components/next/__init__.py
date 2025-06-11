"""Namespace for components provided by next packages."""

from .base import NextComponent
from .image import Image
from .link import NextLink

image = Image.create
next_link = NextLink.create

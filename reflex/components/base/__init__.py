"""Base components."""

from .body import Body
from .document import DocumentHead, Html, Main, NextScript
from .fragment import Fragment
from .head import Head
from .link import RawLink, ScriptTag
from .meta import Description, Image, Meta, Title
from .script import Script

fragment = Fragment.create
script = Script.create

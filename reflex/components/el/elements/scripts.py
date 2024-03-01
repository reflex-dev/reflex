"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Optional, Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Canvas(BaseHTML):
    """Display the canvas element."""

    tag: str = "canvas"


class Noscript(BaseHTML):
    """Display the noscript element."""

    tag: str = "noscript"
    # No unique attributes, only common ones are inherited


class Script(BaseHTML):
    """Display the script element."""

    tag: str = "script"

    # Indicates that the script should be executed asynchronously
    async_: Optional[Var[Union[str, int, bool]]] = None

    # Character encoding of the external script
    char_set: Optional[Var[Union[str, int, bool]]] = None

    # Configures the CORS requests for the script
    cross_origin: Optional[Var[Union[str, int, bool]]] = None

    # Indicates that the script should be executed after the page has finished parsing
    defer: Optional[Var[Union[str, int, bool]]] = None

    # Security feature allowing browsers to verify what they fetch
    integrity: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the scripting language used in the type attribute
    language: Optional[Var[Union[str, int, bool]]] = None

    # Specifies which referrer information to send when fetching the script
    referrer_policy: Optional[Var[Union[str, int, bool]]] = None

    # URL of an external script
    src: Optional[Var[Union[str, int, bool]]] = None

    # Specifies the MIME type of the script
    type: Optional[Var[Union[str, int, bool]]] = None

"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from typing import Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Canvas(BaseHTML):
    """Display the canvas element."""

    tag = "canvas"


class Noscript(BaseHTML):
    """Display the noscript element."""

    tag = "noscript"
    # No unique attributes, only common ones are inherited


class Script(BaseHTML):
    """Display the script element."""

    tag = "script"

    # Indicates that the script should be executed asynchronously
    async_: Var[Union[str, int, bool]]

    # Character encoding of the external script
    char_set: Var[Union[str, int, bool]]

    # Configures the CORS requests for the script
    cross_origin: Var[Union[str, int, bool]]

    # Indicates that the script should be executed after the page has finished parsing
    defer: Var[Union[str, int, bool]]

    # Security feature allowing browsers to verify what they fetch
    integrity: Var[Union[str, int, bool]]

    # Specifies the scripting language used in the type attribute
    language: Var[Union[str, int, bool]]

    # Specifies which referrer information to send when fetching the script
    referrer_policy: Var[Union[str, int, bool]]

    # URL of an external script
    src: Var[Union[str, int, bool]]

    # Specifies the MIME type of the script
    type: Var[Union[str, int, bool]]


canvas = Canvas.create
noscript = Noscript.create
script = Script.create

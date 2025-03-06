"""Scripts classes."""

from reflex.components.el.elements.inline import ReferrerPolicy
from reflex.components.el.elements.media import CrossOrigin
from reflex.vars.base import Var

from .base import BaseHTML


class Canvas(BaseHTML):
    """Display the canvas element."""

    tag = "canvas"


class Noscript(BaseHTML):
    """Display the noscript element."""

    tag = "noscript"


class Script(BaseHTML):
    """Display the script element."""

    tag = "script"

    # Indicates that the script should be executed asynchronously
    async_: Var[bool]

    # Character encoding of the external script
    char_set: Var[str]

    # Configures the CORS requests for the script
    cross_origin: Var[CrossOrigin]

    # Indicates that the script should be executed after the page has finished parsing
    defer: Var[bool]

    # Security feature allowing browsers to verify what they fetch
    integrity: Var[str]

    # Specifies which referrer information to send when fetching the script
    referrer_policy: Var[ReferrerPolicy]

    # URL of an external script
    src: Var[str]

    # Specifies the MIME type of the script
    type: Var[str]


canvas = Canvas.create
noscript = Noscript.create
script = Script.create

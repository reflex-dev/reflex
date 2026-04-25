"""Scripts classes."""

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.inline import ReferrerPolicy
from reflex_components_core.el.elements.media import CrossOrigin

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

    async_: Var[bool] = field(
        doc="Indicates that the script should be executed asynchronously"
    )

    char_set: Var[str] = field(doc="Character encoding of the external script")

    cross_origin: Var[CrossOrigin] = field(
        doc="Configures the CORS requests for the script"
    )

    defer: Var[bool] = field(
        doc="Indicates that the script should be executed after the page has finished parsing"
    )

    integrity: Var[str] = field(
        doc="Security feature allowing browsers to verify what they fetch"
    )

    referrer_policy: Var[ReferrerPolicy] = field(
        doc="Specifies which referrer information to send when fetching the script"
    )

    src: Var[str] = field(doc="URL of an external script")

    type: Var[str] = field(doc="Specifies the MIME type of the script")


canvas = Canvas.create
noscript = Noscript.create
script = Script.create

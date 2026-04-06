"""Display the title of the current page."""

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.base import BaseHTML


class RawLink(BaseHTML):
    """A component that displays the title of the current page."""

    tag = "link"

    href: Var[str] = field(doc="The href.")

    rel: Var[str] = field(doc="The type of link.")


class ScriptTag(BaseHTML):
    """A script tag with the specified type and source."""

    tag = "script"

    type_: Var[str] = field(doc="The type of script represented.")

    source: Var[str] = field(doc="The URI of an external script.")

    integrity: Var[str] = field(doc="Metadata to verify the content of the script.")

    crossorigin: Var[str] = field(doc="Whether to allow cross-origin requests.")

    referrer_policy: Var[str] = field(
        doc="Indicates which referrer to send when fetching the script."
    )

    is_async: Var[bool] = field(doc="Whether to asynchronously load the script.")

    defer: Var[bool] = field(doc="Whether to defer loading the script.")
